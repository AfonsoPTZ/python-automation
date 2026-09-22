# Automação de Auditoria de Qualidade

Projeto acadêmico da disciplina de **Qualidade de Software**.

A aplicação tem duas partes:

1. **Ferramenta rápida** (`/`): recebe um PDF, avalia contra o checklist
   padrão da disciplina (30 critérios) via IA (Gemini) e mostra o resultado —
   nada é salvo em disco ou banco.
2. **Painel do Auditor** (`/projetos`): gerencia projetos/auditorias de ponta
   a ponta — cadastro de projetos e integrantes, upload de documentos,
   avaliação por IA com geração de Não Conformidades (título, evidência,
   impacto e ação corretiva), envio de e-mail de notificação com prazo (SLA),
   contador regressivo de prazo, escalonamento automático (via rotina
   agendada) ou manual ao superior/orientador, reavaliação e fechamento com
   parecer final.

A análise é feita **por uma IA** (Google Gemini), que julga cada critério com
base no conteúdo do(s) documento(s).

A análise é feita **por uma IA** (Google Gemini), que julga cada critério com
base no conteúdo do documento. O documento é processado em memória: **nada é
salvo** em disco ou em banco de dados, além do texto enviado à API do Gemini
para a avaliação.

## Fluxo

```
enviar PDF → extrair texto → enviar checklist + texto para a IA → calcular aderência → identificar as NCs
```

Cada um dos 30 critérios resulta em **CF** (conforme), **NC** (não conforme)
ou **N/A** (não aplicável — quando a IA não encontra base no documento para
julgar aquele critério). A aderência considera só os itens avaliáveis:
CF ÷ (CF + NC).

## Tecnologias

| Camada          | Tecnologia                                |
|-----------------|--------------------------------------------|
| Front-end       | HTML, CSS, JavaScript (server-rendered)    |
| Back-end        | Python + Flask                             |
| Banco de dados  | SQLite (`sqlite3` da stdlib)               |
| Upload          | `werkzeug`/Flask (`request.files`)         |
| Leitura de docs | pypdf, python-docx, openpyxl               |
| Avaliação       | Google Gemini (`google-genai`)             |
| E-mail          | link "Redigir" do Gmail pré-preenchido (nenhum envio automático) |
| Agendamento     | APScheduler (verificação de SLA)           |

## Estrutura

```
app.py                    → cria a app Flask, registra blueprints e a rotina agendada
config.py                 → configuração (banco, uploads, SLA) via variáveis de ambiente
database.py                → conexão SQLite e inicialização do schema
schema.sql                 → tabelas: projetos, participantes, documentos, auditorias,
                              nao_conformidades, logs_emails
auditoria/                 → motor de auditoria
  leitura_pdf.py           → extrai texto de PDF (ferramenta rápida)
  leitura_documentos.py    → extrai texto de pdf/docx/xlsx/txt (Painel do Auditor)
  criterios.py             → os 30 critérios do checklist padrão da disciplina
  ia.py                    → monta o prompt, chama o Gemini e interpreta o JSON de resposta
  checklist.py             → orquestra a extração + avaliação e calcula a aderência
routes/                    → blueprints Flask: projetos, auditorias (encerrar), nc (notificar/escalonar
                              por NC individual, editar, excluir)
services/
  gmail_link.py             → monta o texto pronto (sem IA) e o link "Redigir" do Gmail, por NC
  scheduler.py              → rotina periódica que marca NCs com prazo vencido como escalonadas
templates/                  → páginas HTML (Jinja2): ferramenta rápida + Painel do Auditor
static/                     → style.css/app.js (ferramenta rápida) e gestor.css/gestor.js (painel)
uploads/<id_projeto>/       → documentos enviados por projeto (não versionado)
data/qa_audit.db            → banco SQLite (não versionado)
requirements.txt            → dependências Python
.env                         → configuração local (não versionado, veja `.env.example`)
```

## Como executar

```bash
py -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate    # Linux/Mac
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha `GEMINI_API_KEY`. **Não há
configuração de SMTP/senha**: o sistema nunca envia e-mail sozinho. Depois de
revisar as NCs e definir o prazo, o Painel do Auditor monta um link "Redigir"
do Gmail com destinatário, assunto e corpo já prontos (texto fixo, montado em
código — sem gastar token de IA a cada envio); o auditor só abre o link e
clica em enviar, pela própria conta dele. O mesmo vale para o e-mail de
escalonamento (manual ou quando o prazo vence automaticamente).

Depois:

```bash
py app.py
```

O banco SQLite (`data/qa_audit.db`) é criado automaticamente na primeira
execução. Acesse <http://localhost:5000> para a ferramenta rápida (1 PDF por
vez) ou <http://localhost:5000/projetos> para o Painel do Auditor.

## Deploy (Railway)

A aplicação usa SQLite em arquivo, salva os documentos enviados em disco e
roda uma rotina agendada em processo (`APScheduler`) para escalonamento
automático de prazo vencido — por isso precisa de um host com **processo
contínuo e disco persistente** (não serverless). Railway atende isso direto,
sem mudar nada no código.

1. Suba o repositório no GitHub (se ainda não estiver).
2. No Railway: **New Project → Deploy from GitHub repo**, selecione este
   repositório. O `Procfile` já diz como rodar (`gunicorn`, 1 worker — ver
   nota abaixo); a versão do Python vem do `.python-version`.
3. Adicione um **Volume** ao serviço (aba *Settings → Volumes*) e monte em
   `/data`. Sem isso, o banco e os documentos são apagados a cada novo deploy.
4. Em *Variables*, defina:
   - `GEMINI_API_KEY` — obrigatória.
   - `SECRET_KEY` — recomendada (qualquer string aleatória; sem ela, usa um
     valor padrão fixo do código, inadequado pra produção).
   - `DATABASE_PATH=/data/qa_audit.db`
   - `UPLOAD_FOLDER=/data/uploads`
5. Deploy. O Railway expõe a porta via a variável `$PORT`, que o `Procfile`
   já usa.

**Por que `--workers 1` no Procfile:** o scheduler de escalonamento
automático roda dentro do próprio processo Flask, iniciado uma vez quando o
app sobe (`app.py`). Com mais de 1 worker do gunicorn, cada um subiria seu
próprio scheduler, verificando e escalonando os mesmos prazos vencidos em
paralelo — daí o `--threads 4` no lugar de múltiplos workers, pra manter
alguma concorrência sem duplicar o agendador.

## Como a análise é feita (e suas limitações)

O texto extraído do PDF é enviado, junto com a descrição dos 30 critérios,
para o modelo Gemini, que responde em JSON estruturado com o status (CF/NC/N-A)
e uma evidência textual para cada critério.

É uma avaliação por IA, então pode haver **inconsistência entre execuções**
(o mesmo documento pode receber avaliações levemente diferentes em chamadas
distintas) e a evidência apontada deve ser conferida — a IA pode
ocasionalmente citar um trecho impreciso. Por isso cada item mostra a
**evidência** que sustentou a decisão, e as NCs geradas devem ser
**revisadas por um auditor humano**.

Erros da API são tratados: sobrecarga temporária do modelo (503) é repetida
automaticamente algumas vezes antes de falhar; cota gratuita esgotada (429)
falha imediatamente com uma mensagem explicando o motivo, sem ficar
tentando à toa.

## Checklist aplicado

A lista completa aparece na página inicial e na tela de resultado (ambas
expansíveis), e em `CRITERIOS`, no `auditoria/criterios.py`. Cobre:
identificação e contexto do sistema avaliado, planejamento das tarefas e
heurísticas de Nielsen, técnica de caixa preta, execução e evidências,
análise de usabilidade e problemas críticos, conclusão e recomendações,
checklist do processo, referências bibliográficas e consistência documental.

## Mapeamento com os entregáveis do trabalho

| Requisito da especificação                   | Onde é atendido |
|-----------------------------------------------|-----------------|
| Ler o conteúdo do documento                   | `auditoria.leitura_pdf.extrair_texto` |
| Checklist específico para o artefato avaliado | `auditoria.criterios.CRITERIOS` |
| Executar o checklist automaticamente          | `auditoria.ia.avaliar_com_ia` |
| Informar critérios conformes / não conformes  | página `templates/resultado.html` |
| Calcular a % de aderência                     | `auditoria.checklist.auditar` |
| Identificar as NCs                            | `auditoria.checklist.auditar` (`nao_conformidades`) |

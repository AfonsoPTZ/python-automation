# Automação de Auditoria de Qualidade

Projeto acadêmico da disciplina de **Qualidade de Software**.

A aplicação recebe um **Relatório de Teste de Usabilidade** em PDF, envia o
texto extraído junto com o checklist padrão da disciplina (30 critérios) para
uma IA (Gemini), e devolve as **Não Conformidades (NCs)** encontradas, junto
com a % de aderência.

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

| Camada         | Tecnologia            |
|----------------|------------------------|
| Front-end      | HTML, CSS, JavaScript |
| Back-end       | Python + Flask        |
| Leitura de PDF | pypdf                 |
| Avaliação      | Google Gemini (`google-genai`) |

## Estrutura

```
app.py                → aplicação Flask: rotas e ligação com o motor de auditoria
auditoria/             → motor de auditoria
  leitura_pdf.py       → extrai o texto do PDF
  criterios.py         → os 30 critérios do checklist padrão da disciplina
  ia.py                → monta o prompt, chama o Gemini e interpreta o JSON de resposta
  checklist.py         → orquestra a extração + avaliação e calcula a aderência
templates/             → páginas HTML (Jinja2): index e resultado
static/                → style.css e app.js
requirements.txt       → dependências Python
.env                   → GEMINI_API_KEY (não versionado)
```

## Como executar

```bash
py -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate    # Linux/Mac
pip install -r requirements.txt
```

Crie um arquivo `.env` na raiz com sua chave da API do Gemini:

```
GEMINI_API_KEY=sua-chave-aqui
```

Depois:

```bash
py app.py
```

Acesse <http://localhost:5000>, envie o PDF e veja o resultado da auditoria.

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

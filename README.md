# Automação de Auditoria de Qualidade

Projeto acadêmico da disciplina de **Qualidade de Software**.

A aplicação recebe um **Relatório de Teste de Usabilidade** em PDF, executa
automaticamente o checklist padrão da disciplina (30 critérios) e devolve as
**Não Conformidades (NCs)** encontradas, junto com a % de aderência.

A análise é feita **por regras definidas no código** (pacote `auditoria/`) —
não usa inteligência artificial. O documento é processado em memória: **nada
é salvo** em disco ou em banco de dados.

## Fluxo

```
enviar PDF → executar checklist → calcular aderência → identificar as NCs
```

Cada um dos 30 critérios resulta em **CF** (conforme), **NC** (não conforme)
ou **N/A** (não aplicável — checagem que exige comparar números ou
identificadores entre seções do documento, fina demais para uma busca de
texto; fica marcada para revisão manual em vez de arriscar um veredito
errado). A aderência considera só os itens avaliáveis: CF ÷ (CF + NC).

## Tecnologias

| Camada         | Tecnologia            |
|----------------|-----------------------|
| Front-end      | HTML, CSS, JavaScript |
| Back-end       | Python + Flask        |
| Leitura de PDF | pypdf                 |

## Estrutura

```
app.py                → aplicação Flask: rotas e ligação com o motor de auditoria
auditoria/             → motor de auditoria
  leitura_pdf.py       → extrai e normaliza o texto do PDF
  verificadores.py     → fábricas de verificador (termos, regex, combinado...), reutilizáveis por qualquer critério
  criterios.py         → os 30 critérios do checklist padrão da disciplina
  checklist.py         → executa o checklist e calcula a aderência
projeto-avaliado/       → checklist/template/exemplo de referência da disciplina (Excel, Word, PDF)
templates/             → páginas HTML (Jinja2): base, index e resultado
static/                → style.css e app.js
requirements.txt       → dependências Python
```

## Como executar

```bash
py -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate    # Linux/Mac
pip install -r requirements.txt
py app.py
```

Acesse <http://localhost:5000>, envie o PDF e veja o resultado da auditoria.

## Como a análise é feita (e suas limitações)

O texto extraído do PDF é **normalizado** (minúsculas + remoção de acentos) e
cada critério procura por evidências dentro da seção certa do documento (ex.:
uma fonte bibliográfica só conta se estiver na seção de Referências, não em
qualquer parte do texto). Alguns critérios comparam identificadores de tarefa
(`CT01`, `CT02`...) entre o planejamento, a execução e a análise, pra checar
se os números "batem" de uma seção pra outra.

Ainda assim é uma **triagem automática**: pode haver falso negativo (o autor
usou um termo não previsto) ou falso positivo (citou o termo de passagem). Por
isso cada item mostra a **evidência** que sustentou a decisão, e as NCs
geradas devem ser **revisadas por um auditor humano**.

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
| Executar o checklist automaticamente          | `auditoria.checklist.executar_checklist` |
| Informar critérios conformes / não conformes  | página `templates/resultado.html` |
| Calcular a % de aderência                     | `auditoria.checklist.auditar` |
| Identificar as NCs                            | `auditoria.checklist.auditar` (`nao_conformidades`) |

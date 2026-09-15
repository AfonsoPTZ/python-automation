# Motor de auditoria de qualidade.
#
# Audita um Relatório de Teste de Usabilidade a partir de um PDF, executando
# o checklist padrão da disciplina (30 critérios). A análise é feita por
# regras definidas no código — não usa inteligência artificial.
#
# Módulos do pacote:
#   leitura_pdf   -> extrai e normaliza o texto do PDF
#   verificadores -> fábricas de verificador reutilizáveis (termos, regex, ...)
#   criterios     -> os 30 critérios do checklist padrão da disciplina
#   checklist     -> executa o checklist e calcula a aderência
#
# Cada critério resulta em CF (conforme), NC (não conforme) ou N/A (não
# aplicável / fora do alcance de uma checagem automática de texto).
#
# É uma triagem automática — falsos positivos/negativos são possíveis; a
# finalidade da ferramenta é identificar as Não Conformidades (NCs) para
# revisão humana, não substituir o avaliador.
from .checklist import auditar
from .criterios import CRITERIOS, NOME

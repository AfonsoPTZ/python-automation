# Checklist de Avaliação — Relatório de Teste de Usabilidade (v1.2).
#
# Este é o checklist padrão da disciplina: o escopo definido pela professora
# para o trabalho (ver projeto-avaliado/template-padrao.docx), transformado
# nos 30 critérios avaliatórios usados para auditar o relatório entregue por
# qualquer equipe (ver projeto-avaliado/Checklist_Avaliacao_V1.xlsx).
#
# Cada critério tem uma função verificar(contexto) -> (resultado, evidencia),
# onde "resultado" pode ser:
#   True  -> CF  (conforme)
#   False -> NC  (não conforme)
#   None  -> N/A (não aplicável — checagem fina demais para o motor de
#            texto, ex.: reconciliar identificadores entre duas seções do
#            documento)
import re

from .verificadores import combinado, contagem_regex, regex, sem_marcadores_de_template, termos

# As 10 heurísticas de Nielsen, como aparecem no template padrão.
_HEURISTICAS_NIELSEN = [
    "visibilidade do status do sistema",
    "correspondencia entre o sistema e o mundo real",
    "controle e liberdade",
    "consistencia e padroes",
    "prevencao de erros",
    "reconhecimento em vez de memorizacao",
    "flexibilidade e eficiencia de uso",
    "design estetico e minimalista",
    "reconhecimento, diagnostico",
    "ajuda e documentacao",
]

# Cabeçalhos das seções do template padrão, na ordem esperada. Usamos o
# título completo (não só "conclusao") para não casar com uma palavra solta
# no meio de outra seção (ex.: "...antes da conclusao da acao..." dentro da
# execução, que não é o título "5. Conclusão e Recomendações").
_SECOES_DO_TEMPLATE = [
    "introducao", "metodologia", "execucao do teste",
    "analise de usabilidade", "conclusao e recomendacoes", "checklist do processo", "referencias",
]


# Recorta o texto normalizado entre duas âncoras de seção (ex.: entre o
# início de "execucao do teste" e o início de "analise de usabilidade").
# Permite checar uma evidência DENTRO da seção certa, em vez do documento
# inteiro — é o que resolve a maior parte dos falsos positivos/negativos
# (uma palavra que aparece de passagem em outra seção não deveria contar).
def _texto_da_secao(contexto, inicio, fim=None):
    texto = contexto["texto"]
    posicao_inicio = texto.find(inicio)
    if posicao_inicio < 0:
        return ""
    posicao_inicio += len(inicio)
    posicao_fim = texto.find(fim, posicao_inicio) if fim else -1
    return texto[posicao_inicio: posicao_fim if posicao_fim >= 0 else len(texto)]


# Extrai os identificadores de caso de teste (CT01, CT02...) citados no trecho.
def _ids_de_tarefa(texto):
    return set(re.findall(r"\bct\d{1,3}\b", texto))


# U16 — a análise contempla as dez heurísticas de Nielsen?
def _heuristicas_de_nielsen(contexto):
    encontradas = [h for h in _HEURISTICAS_NIELSEN if h in contexto["texto"]]
    conforme = len(encontradas) >= 8
    return conforme, (
        f"{len(encontradas)}/10 heuristicas de Nielsen mencionadas na analise." if conforme
        else f"Apenas {len(encontradas)}/10 heuristicas de Nielsen encontradas; esperado >= 8."
    )


# U15 — cada evidência sustenta o resultado atribuído à tarefa? Não basta ter
# a palavra "evidência"/"link": o link citado por tarefa precisa ser um
# endereço real (verificável), não só um rótulo de referência solto.
def _evidencia_sustenta_resultado(contexto):
    secao_execucao = _texto_da_secao(contexto, "execucao do teste", "analise de usabilidade")
    referencias_a_evidencia = re.findall(r"link\s*[:\-]?\s*ct\d{1,3}", secao_execucao)
    if not referencias_a_evidencia:
        return False, "Nenhuma evidencia (link/captura) associada as tarefas foi encontrada na execucao."
    links_reais = re.findall(r"https?://\S+", secao_execucao)
    if not links_reais:
        return False, (f"{len(referencias_a_evidencia)} tarefa(s) citam uma evidencia (ex.: \"Link: CT01\"), "
                       "mas nenhum link/endereco real e verificavel foi encontrado — a evidencia nao e conferivel.")
    return True, f"{len(links_reais)} link(s) real(is) de evidencia encontrados, associados aos resultados das tarefas."


# U17 — os achados da análise são rastreáveis aos testes executados? Conta
# quantas vezes a análise cita um identificador de caso de teste (CT01,
# CT02...) — é o que torna um achado rastreável até a execução.
def _achados_rastreaveis(contexto):
    secao_analise = _texto_da_secao(contexto, "analise de usabilidade", "checklist do processo")
    ids_citados = _ids_de_tarefa(secao_analise)
    conforme = len(ids_citados) >= 3
    return conforme, (
        f"Analise cita {len(ids_citados)} caso(s) de teste distintos (ex.: {', '.join(sorted(ids_citados)[:3])})."
        if conforme else
        f"Apenas {len(ids_citados)} caso(s) de teste citados na analise; esperado >= 3 para rastreabilidade."
    )


# Fábrica U25/U26 — a fonte precisa estar DENTRO da seção de Referências, não
# em qualquer parte do documento (senão bastaria mencionar "Nielsen" na
# metodologia para o critério passar, mesmo sem uma referência bibliográfica).
def _fonte_citada_nas_referencias(*termos_esperados):
    def verificar(contexto):
        secao_referencias = _texto_da_secao(contexto, "referencias")
        termo_encontrado = next((t for t in termos_esperados if t in secao_referencias), None)
        if termo_encontrado:
            return True, f'Fonte encontrada na secao de referencias (termo "{termo_encontrado}").'
        return False, (f"Nenhuma referencia bibliografica sobre \"{termos_esperados[0]}\" "
                       "encontrada na secao de Referencias.")
    return verificar


# U27 — a estrutura do documento segue a ordem definida no template?
def _estrutura_segue_template(contexto):
    posicoes = [contexto["texto"].find(secao) for secao in _SECOES_DO_TEMPLATE]
    encontradas = [(secao, pos) for secao, pos in zip(_SECOES_DO_TEMPLATE, posicoes) if pos >= 0]
    em_ordem = encontradas == sorted(encontradas, key=lambda par: par[1])
    conforme = len(encontradas) >= 5 and em_ordem
    return conforme, (
        f"{len(encontradas)}/7 secoes do template encontradas, na ordem esperada." if conforme
        else f"{len(encontradas)}/7 secoes do template encontradas"
             + ("" if em_ordem else ", fora da ordem esperada") + "."
    )


# U29 — os identificadores das tarefas (CT01, CT02...) coincidem entre
# planejamento e execução? Compara o conjunto de IDs citados na seção de
# planejamento com o conjunto citado na execução.
def _identificadores_de_tarefa_coincidem(contexto):
    ids_planejamento = _ids_de_tarefa(_texto_da_secao(contexto, "planejamento do teste", "tecnica de teste utilizada"))
    ids_execucao = _ids_de_tarefa(_texto_da_secao(contexto, "execucao do teste", "analise de usabilidade"))

    if not ids_execucao:
        return None, "Nenhum identificador de tarefa encontrado na execucao; nao ha o que comparar."
    if not ids_planejamento:
        return False, (f"A execucao usa {len(ids_execucao)} identificador(es) de tarefa (ex.: "
                       f"{', '.join(sorted(ids_execucao)[:3])}), mas o planejamento nao define identificadores "
                       "para comparar.")
    if ids_planejamento == ids_execucao:
        return True, f"Os {len(ids_execucao)} identificadores de tarefa coincidem entre planejamento e execucao."
    return False, (f"Identificadores nao coincidem entre planejamento ({len(ids_planejamento)}) "
                   f"e execucao ({len(ids_execucao)}).")


# U30 — os quantitativos apresentados na análise coincidem com os resultados
# da execução? Todo identificador de tarefa citado na análise precisa ser um
# caso realmente executado (nenhum número/CT inventado).
def _quantitativos_coincidem(contexto):
    ids_analise = _ids_de_tarefa(_texto_da_secao(contexto, "analise de usabilidade", "checklist do processo"))
    ids_execucao = _ids_de_tarefa(_texto_da_secao(contexto, "execucao do teste", "analise de usabilidade"))

    if not ids_analise:
        return None, "A analise nao cita identificadores de tarefa; nao ha quantitativo para reconciliar."
    if ids_analise.issubset(ids_execucao):
        return True, (f"Os {len(ids_analise)} identificadores citados na analise "
                      "correspondem a casos realmente executados.")
    invalidos = sorted(ids_analise - ids_execucao)
    return False, f"A analise cita identificador(es) que nao aparecem na execucao: {', '.join(invalidos)}."


CRITERIOS = [
    {"codigo": "U01", "categoria": "Introdução e contexto",
     "descricao": "O contexto caracteriza o sistema web avaliado?",
     "verificar": combinado(termos("contexto do projeto"),
                            regex(r"(publico[- ]?alvo|endereco eletronico|\bhttp|www\.)", "público-alvo/endereço do sistema"))},
    {"codigo": "U02", "categoria": "Introdução e contexto",
     "descricao": "A justificativa para a escolha do sistema foi apresentada?",
     "verificar": regex(r"(justificativ[ae]\s+(da|para|pela)\s+escolha|motivo\s+da\s+escolha|"
                        r"escolhid[oa]\s+(pois|porque|por)|raz[aã]o\s+da\s+escolha|"
                        r"crit[eé]rio\s+de\s+escolha|por\s+(isso|essa\s+raz[aã]o)[, ]+(foi\s+)?escolhid)",
                        "justificativa explícita da escolha do sistema")},
    {"codigo": "U03", "categoria": "Introdução e contexto",
     "descricao": "Os objetivos específicos do teste foram descritos?",
     "verificar": termos("objetivos do teste", "objetivo do teste", "objetivos especificos")},
    {"codigo": "U04", "categoria": "Introdução e contexto",
     "descricao": "O aspecto de qualidade avaliado foi identificado?",
     "verificar": termos("usabilidade")},
    {"codigo": "U05", "categoria": "Metodologia e planejamento",
     "descricao": "As tarefas planejadas para os participantes foram listadas?",
     "verificar": combinado(termos("planejamento do teste"), termos("tarefa", "cenario"))},
    {"codigo": "U06", "categoria": "Metodologia e planejamento",
     "descricao": "Cada tarefa indica uma heurística de Nielsen?",
     "verificar": contagem_regex(r"heuristica", 3, "menções a heurística associada às tarefas")},
    {"codigo": "U07", "categoria": "Metodologia e planejamento",
     "descricao": "Cada tarefa possui um cenário de uso definido?",
     "verificar": termos("cenario")},
    {"codigo": "U08", "categoria": "Metodologia e planejamento",
     "descricao": "Cada tarefa identifica a interface avaliada?",
     "verificar": termos("interface")},
    {"codigo": "U09", "categoria": "Metodologia e planejamento",
     "descricao": "A aplicação da técnica de caixa preta foi explicada?",
     "verificar": termos("caixa preta", "tecnica de teste utilizada", "black box")},
    {"codigo": "U10", "categoria": "Metodologia e planejamento",
     "descricao": "A relevância da técnica de caixa preta para o teste foi justificada?",
     "verificar": combinado(termos("caixa preta", "black box"),
                            regex(r"(relevanci|importante para|contribui para)", "relevância da técnica"))},
    {"codigo": "U11", "categoria": "Metodologia e planejamento",
     "descricao": "Os recursos utilizados no teste foram identificados?",
     "verificar": termos("ferramentas e recursos", "ferramentas utilizadas", "gravacao de tela", "software especifico")},
    {"codigo": "U12", "categoria": "Execução do teste",
     "descricao": "O processo de execução do teste foi descrito?",
     "verificar": termos("processo de teste e resultados", "execucao do teste", "processo de execucao")},
    {"codigo": "U13", "categoria": "Execução do teste",
     "descricao": "Cada tarefa planejada possui um resultado registrado?",
     "verificar": termos("resultado")},
    {"codigo": "U14", "categoria": "Execução do teste",
     "descricao": "Cada tarefa executada possui uma evidência verificável?",
     "verificar": termos("evidencia", "print", "captura de tela", "imagem")},
    {"codigo": "U15", "categoria": "Execução do teste",
     "descricao": "Cada evidência sustenta o resultado atribuído à tarefa?",
     "verificar": _evidencia_sustenta_resultado},
    {"codigo": "U16", "categoria": "Análise de usabilidade",
     "descricao": "A análise contempla as dez heurísticas de Nielsen?",
     "verificar": _heuristicas_de_nielsen},
    {"codigo": "U17", "categoria": "Análise de usabilidade",
     "descricao": "Os achados da análise são rastreáveis aos testes executados?",
     "verificar": _achados_rastreaveis},
    {"codigo": "U18", "categoria": "Análise de usabilidade",
     "descricao": "Os problemas de maior impacto foram identificados?",
     "verificar": termos("problemas criticos", "problemas de maior impacto", "principais problemas")},
    {"codigo": "U19", "categoria": "Análise de usabilidade",
     "descricao": "Cada problema de maior impacto possui uma classificação?",
     "verificar": combinado(termos("problemas criticos", "problemas de maior impacto", "principais problemas"),
                            contagem_regex(r"\b(alto|alta|medio|media|baixo|baixa)\b", 2, "níveis de impacto classificados"))},
    {"codigo": "U20", "categoria": "Conclusão e recomendações",
     "descricao": "A conclusão sintetiza a avaliação geral da qualidade do sistema?",
     "verificar": termos("conclusao geral", "conclusao")},
    {"codigo": "U21", "categoria": "Conclusão e recomendações",
     "descricao": "As recomendações decorrem dos problemas identificados?",
     "verificar": termos("recomendacoes de melhoria", "recomendacao")},
    {"codigo": "U22", "categoria": "Checklist do processo",
     "descricao": "O checklist registra as etapas previstas do processo de teste?",
     "verificar": combinado(termos("checklist do processo"),
                            contagem_regex(r"(planejamento|preparacao|execucao|analise|revisao)", 4, "etapas do processo"))},
    {"codigo": "U23", "categoria": "Checklist do processo",
     "descricao": "O responsável pela aplicação do checklist foi identificado?",
     "verificar": termos("aplicado por", "responsavel pela aplicacao")},
    {"codigo": "U24", "categoria": "Checklist do processo",
     "descricao": "O responsável pela revisão do checklist foi identificado?",
     "verificar": termos("revisado por", "responsavel pela revisao")},
    {"codigo": "U25", "categoria": "Referências",
     "descricao": "A fonte utilizada para as heurísticas de Nielsen foi citada?",
     "verificar": _fonte_citada_nas_referencias("nielsen")},
    {"codigo": "U26", "categoria": "Referências",
     "descricao": "A fonte utilizada para a técnica de caixa preta foi citada?",
     "verificar": _fonte_citada_nas_referencias("caixa preta", "black box", "istqb", "teste funcional")},
    {"codigo": "U27", "categoria": "Consistência documental",
     "descricao": "A estrutura do documento segue a ordem definida no template?",
     "verificar": _estrutura_segue_template},
    {"codigo": "U28", "categoria": "Consistência documental",
     "descricao": "Os textos de orientação do template foram removidos da versão avaliada?",
     "verificar": sem_marcadores_de_template},
    {"codigo": "U29", "categoria": "Consistência documental",
     "descricao": "Os identificadores das tarefas coincidem entre planejamento e execução?",
     "verificar": _identificadores_de_tarefa_coincidem},
    {"codigo": "U30", "categoria": "Consistência documental",
     "descricao": "Os quantitativos apresentados na análise coincidem com os resultados da execução?",
     "verificar": _quantitativos_coincidem},
]

NOME = "Relatório de Teste de Usabilidade"

# Faixas de interpretação da aderência geral (aba "Resumo e Regras" da planilha).
FAIXAS_DE_ADERENCIA = [
    (60, "Baixa", "Revisar o artefato antes da aprovação."),
    (90, "Média", "Corrigir as NC antes da aprovação."),
    (100, "Alta", "Tratar as NC remanescentes."),
]

# Funções de verificação específicas demais para as fábricas genéricas de verificadores.py.
import re

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

_SECOES_DO_TEMPLATE = [
    "introducao", "metodologia", "execucao do teste",
    "analise de usabilidade", "conclusao e recomendacoes", "checklist do processo", "referencias",
]


# Recorta o texto entre duas âncoras de seção.
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


# U15 — cada evidência sustenta o resultado atribuído à tarefa?
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


# U17 — os achados da análise são rastreáveis aos testes executados?
def _achados_rastreaveis(contexto):
    secao_analise = _texto_da_secao(contexto, "analise de usabilidade", "checklist do processo")
    ids_citados = _ids_de_tarefa(secao_analise)
    conforme = len(ids_citados) >= 3
    return conforme, (
        f"Analise cita {len(ids_citados)} caso(s) de teste distintos (ex.: {', '.join(sorted(ids_citados)[:3])})."
        if conforme else
        f"Apenas {len(ids_citados)} caso(s) de teste citados na analise; esperado >= 3 para rastreabilidade."
    )


# Fábrica U25/U26 — a fonte precisa estar dentro da seção de Referências.
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


# U29 — os identificadores das tarefas coincidem entre planejamento e execução?
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


# U30 — os quantitativos apresentados na análise coincidem com os resultados da execução?
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

# Avalia o checklist enviando o texto do documento para a IA (Gemini).
import json
import os
import time

from google import genai
from google.genai import errors, types

from .criterios import CRITERIOS, NOME

_MODELO = "gemini-2.5-flash"

_STATUS_VALIDOS = {"CF", "NC", "N/A"}

_TENTATIVAS = 3
_ESPERA_BASE_SEGUNDOS = 2

_INSTRUCAO_SISTEMA = (
    "Voce e um auditor academico que avalia relatorios de Teste de Usabilidade "
    "contra um checklist fixo. Para cada criterio do checklist, decida se o "
    "documento esta conforme (CF), nao conforme (NC) ou nao aplicavel (N/A), "
    "e cite uma evidencia curta e especifica extraida do proprio texto do "
    "documento (ou explique objetivamente a ausencia). Baseie-se somente no "
    "conteudo do documento fornecido, nao invente evidencias. Escreva sempre "
    "em linguagem simples e direta, como se estivesse explicando o problema "
    "para o proprio grupo que fez o trabalho, nao para outro auditor — evite "
    "jargao tecnico de auditoria sempre que houver uma forma mais clara de dizer."
)

_ESQUEMA_RESPOSTA = {
    "type": "object",
    "properties": {
        "itens": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "codigo": {"type": "string"},
                    "status": {"type": "string", "enum": sorted(_STATUS_VALIDOS)},
                    "evidencia": {"type": "string"},
                },
                "required": ["codigo", "status", "evidencia"],
            },
        },
    },
    "required": ["itens"],
}

# Esquema estendido, usado pelo Painel do Auditor: além do status e da evidência,
# pede um título curto, o impacto e a ação corretiva esperada para cada item
# não conforme (usados para montar as Não Conformidades - NCs).
_ESQUEMA_RESPOSTA_NC = {
    "type": "object",
    "properties": {
        "itens": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "codigo": {"type": "string"},
                    "status": {"type": "string", "enum": sorted(_STATUS_VALIDOS)},
                    "evidencia": {"type": "string"},
                    "titulo": {"type": "string"},
                    "impacto": {"type": "string"},
                    "acao_corretiva": {"type": "string"},
                },
                # "titulo" é obrigatório mesmo quando N/A ou CF: sem isso, o item
                # herdaria como título o texto formal do critério do checklist
                # (ex.: "Verificar aderência às heurísticas de Nielsen"), que é
                # jargão de auditoria, não algo que o grupo avaliado entenda de cara.
                "required": ["codigo", "status", "evidencia", "titulo"],
            },
        },
    },
    "required": ["itens"],
}


def _montar_prompt(texto_documento, criterios, incluir_nc=False):
    checklist = "\n".join(
        f'{criterio["codigo"]} ({criterio.get("categoria") or "Geral"}): {criterio["descricao"]}'
        for criterio in criterios
    )
    instrucao_extra = (
        " Para todo item, preencha 'titulo': uma frase curta e direta, em "
        "linguagem simples, que qualquer integrante do grupo avaliado (sem "
        "formacao em auditoria) entenda de imediato — descreva o problema "
        "encontrado, nao repita o nome tecnico do criterio do checklist. "
        "Para cada item avaliado como NC (nao conforme), preencha tambem: "
        "'impacto' (por que isso e um problema para a qualidade do trabalho, "
        "em linguagem simples) e 'acao_corretiva' (o que o grupo precisa fazer "
        "para corrigir, de forma pratica e objetiva)."
        if incluir_nc
        else ""
    )
    return (
        f'Checklist do "{NOME}":\n{checklist}\n\n'
        f'Documento avaliado:\n"""\n{texto_documento}\n"""\n\n'
        "Avalie o documento contra cada item do checklist e devolva um item "
        "de resultado para cada codigo, na mesma ordem em que aparecem."
        f"{instrucao_extra}"
    )


def _cliente():
    chave_api = os.environ.get("GEMINI_API_KEY")
    if not chave_api:
        raise RuntimeError("GEMINI_API_KEY nao configurada (verifique o arquivo .env).")
    return genai.Client(api_key=chave_api)


# Chama a IA, repetindo com espera crescente se o modelo estiver sobrecarregado (503).
# Cota esgotada (429) não é repetida: tentar de novo não resolve e só consome mais cota.
def _gerar_com_retentativas(cliente, prompt, esquema=_ESQUEMA_RESPOSTA, instrucao_sistema=_INSTRUCAO_SISTEMA):
    for tentativa in range(1, _TENTATIVAS + 1):
        try:
            return cliente.models.generate_content(
                model=_MODELO,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=instrucao_sistema,
                    response_mime_type="application/json",
                    response_schema=esquema,
                ),
            )
        except errors.ClientError as erro:
            if erro.code == 429:
                raise RuntimeError(
                    "A cota gratuita da API do Gemini acabou por agora. "
                    "Aguarde o reset da cota (geralmente 1 minuto ou 1 dia, "
                    "dependendo do limite atingido) ou use outra chave de API."
                ) from erro
            raise
        except errors.ServerError:
            if tentativa == _TENTATIVAS:
                raise
            time.sleep(_ESPERA_BASE_SEGUNDOS * tentativa)


# Interpreta o JSON devolvido pela IA. Cobre os casos em que o modelo não
# retornou um candidato válido (bloqueio de segurança, resposta vazia) ou
# devolveu um JSON fora do esquema esperado — nesses casos, uma mensagem
# clara em vez de deixar o KeyError/ValueError estourar sem contexto.
def _interpretar_resposta(resposta):
    texto = getattr(resposta, "text", None)
    if not texto:
        raise RuntimeError(
            "A IA não retornou uma resposta válida (pode ter sido bloqueada "
            "pelos filtros de segurança do modelo). Tente novamente."
        )
    try:
        dados = json.loads(texto)
        return {item["codigo"]: item for item in dados.get("itens", []) if "codigo" in item}
    except (json.JSONDecodeError, AttributeError, TypeError) as erro:
        raise RuntimeError(
            "A IA retornou uma resposta em formato inesperado. Tente novamente."
        ) from erro


# Envia o checklist e o texto do documento para a IA e devolve a lista de resultados.
def avaliar_com_ia(texto_documento):
    resposta = _gerar_com_retentativas(_cliente(), _montar_prompt(texto_documento, CRITERIOS))
    resultados_por_codigo = _interpretar_resposta(resposta)

    itens = []
    for criterio in CRITERIOS:
        resultado = resultados_por_codigo.get(criterio["codigo"])
        status = resultado.get("status") if resultado else None
        itens.append({
            "codigo": criterio["codigo"],
            "categoria": criterio["categoria"],
            "descricao": criterio["descricao"],
            "status": status if status in _STATUS_VALIDOS else "NC",
            "evidencia": (resultado.get("evidencia") if resultado else None)
            or "A IA nao retornou avaliacao para este criterio.",
        })
    return itens


# Igual a avaliar_com_ia, mas também pede título, impacto e ação corretiva
# para os itens não conformes — usado pelo Painel do Auditor (QA Audit Manager)
# para gerar as Não Conformidades (NCs) de um projeto. `criterios` é o
# checklist padrão da disciplina por padrão, mas pode ser um checklist
# próprio do projeto (ver auditoria/checklist.py).
def avaliar_projeto_com_ia(texto_documento, criterios=None):
    criterios = criterios if criterios is not None else CRITERIOS
    prompt = _montar_prompt(texto_documento, criterios, incluir_nc=True)
    resposta = _gerar_com_retentativas(_cliente(), prompt, esquema=_ESQUEMA_RESPOSTA_NC)
    resultados_por_codigo = _interpretar_resposta(resposta)

    itens = []
    for criterio in criterios:
        resultado = resultados_por_codigo.get(criterio["codigo"])
        status = resultado.get("status") if resultado else None
        status = status if status in _STATUS_VALIDOS else "NC"
        itens.append({
            "codigo": criterio["codigo"],
            "categoria": criterio["categoria"],
            "descricao": criterio["descricao"],
            "status": status,
            "evidencia": (resultado.get("evidencia") if resultado else None)
            or "A IA nao retornou avaliacao para este criterio.",
            "titulo": (resultado.get("titulo") if resultado else None)
            or (criterio["descricao"] if status == "NC" else None),
            "impacto": resultado.get("impacto") if resultado else None,
            "acao_corretiva": resultado.get("acao_corretiva") if resultado else None,
        })
    return itens


# ===================== Relatório final do projeto =====================
# Ao encerrar a auditoria, a IA escreve a parte narrativa do relatório a
# partir de um resumo (em JSON) de tudo o que aconteceu no projeto. Os
# números e tabelas do PDF saem direto do banco (services/relatorio_final.py);
# a IA só interpreta e escreve, não é a fonte dos dados.
_INSTRUCAO_SISTEMA_RELATORIO = (
    "Voce e um auditor de qualidade escrevendo o relatorio final de um processo "
    "de auditoria academica. Use somente os dados fornecidos em JSON: nao "
    "invente numeros, datas, nomes ou fatos que nao estejam neles. Quando um "
    "dado nao existir, simplesmente nao fale dele. Escreva em portugues do "
    "Brasil, em tom profissional e objetivo, com frases claras. Nao use "
    "markdown, emojis nem marcadores dentro dos textos."
)

_ESQUEMA_RELATORIO = {
    "type": "object",
    "properties": {
        "resumo_executivo": {"type": "string"},
        "historico_do_processo": {"type": "string"},
        "analise_das_nao_conformidades": {"type": "string"},
        "comunicacao_e_prazos": {"type": "string"},
        "conclusao": {"type": "string"},
        "recomendacoes": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "resumo_executivo", "historico_do_processo", "analise_das_nao_conformidades",
        "comunicacao_e_prazos", "conclusao", "recomendacoes",
    ],
}


def gerar_relatorio_final_com_ia(dados_projeto):
    prompt = (
        "Escreva o relatorio final do processo de auditoria descrito nos dados abaixo.\n"
        "- resumo_executivo: 1 paragrafo com o essencial (projeto, parecer final, "
        "aderencia, quantas NCs, como terminou).\n"
        "- historico_do_processo: a linha do tempo, auditoria por auditoria "
        "(ex.: 'na primeira auditoria foram encontradas X NCs...'), versoes de "
        "documento enviadas e a evolucao da aderencia.\n"
        "- analise_das_nao_conformidades: quais categorias do checklist "
        "concentraram mais problemas, quantas foram resolvidas, quais ficaram "
        "em aberto e o que isso indica sobre o trabalho.\n"
        "- comunicacao_e_prazos: e-mails de correcao preparados, prazos "
        "definidos, escalonamentos ao responsavel e o que isso mostra sobre o "
        "cumprimento de prazos pela equipe.\n"
        "- conclusao: 1 paragrafo justificando o parecer final com base nos dados.\n"
        "- recomendacoes: de 3 a 5 recomendacoes curtas para a equipe ou para "
        "proximas auditorias.\n"
        "Separe paragrafos com uma linha em branco.\n\n"
        f"Dados do processo (JSON):\n{json.dumps(dados_projeto, ensure_ascii=False, indent=1)}"
    )
    resposta = _gerar_com_retentativas(
        _cliente(), prompt, esquema=_ESQUEMA_RELATORIO,
        instrucao_sistema=_INSTRUCAO_SISTEMA_RELATORIO,
    )
    texto = getattr(resposta, "text", None)
    if not texto:
        raise RuntimeError("A IA não retornou o texto do relatório. Tente gerar novamente.")
    try:
        secoes = json.loads(texto)
    except json.JSONDecodeError as erro:
        raise RuntimeError("A IA retornou o relatório em formato inesperado. Tente novamente.") from erro
    if not isinstance(secoes, dict):
        raise RuntimeError("A IA retornou o relatório em formato inesperado. Tente novamente.")
    return secoes

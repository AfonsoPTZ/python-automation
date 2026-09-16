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
    "conteudo do documento fornecido, nao invente evidencias."
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


def _montar_prompt(texto_documento):
    checklist = "\n".join(
        f'{criterio["codigo"]} ({criterio["categoria"]}): {criterio["descricao"]}'
        for criterio in CRITERIOS
    )
    return (
        f'Checklist do "{NOME}":\n{checklist}\n\n'
        f'Documento avaliado:\n"""\n{texto_documento}\n"""\n\n'
        "Avalie o documento contra cada item do checklist e devolva um item "
        "de resultado para cada codigo, na mesma ordem em que aparecem."
    )


def _cliente():
    chave_api = os.environ.get("GEMINI_API_KEY")
    if not chave_api:
        raise RuntimeError("GEMINI_API_KEY nao configurada (verifique o arquivo .env).")
    return genai.Client(api_key=chave_api)


# Chama a IA, repetindo com espera crescente se o modelo estiver sobrecarregado (503).
# Cota esgotada (429) não é repetida: tentar de novo não resolve e só consome mais cota.
def _gerar_com_retentativas(cliente, prompt):
    for tentativa in range(1, _TENTATIVAS + 1):
        try:
            return cliente.models.generate_content(
                model=_MODELO,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_INSTRUCAO_SISTEMA,
                    response_mime_type="application/json",
                    response_schema=_ESQUEMA_RESPOSTA,
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


# Envia o checklist e o texto do documento para a IA e devolve a lista de resultados.
def avaliar_com_ia(texto_documento):
    resposta = _gerar_com_retentativas(_cliente(), _montar_prompt(texto_documento))
    dados = json.loads(resposta.text)
    resultados_por_codigo = {item["codigo"]: item for item in dados.get("itens", [])}

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

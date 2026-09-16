# Executa o checklist contra o documento e calcula a aderência.
from .criterios import CRITERIOS
from .leitura_pdf import extrair_texto, normalizar

_RESULTADO_POR_CONFORME = {True: "CF", False: "NC", None: "N/A"}


# Roda cada critério contra o texto e devolve a lista de resultados (CF/NC/N-A + evidência).
def executar_checklist(texto, paginas, palavras):
    contexto = {"texto": normalizar(texto), "original": texto,
                "paginas": paginas, "palavras": palavras}
    itens = []
    for criterio in CRITERIOS:
        try:
            conforme, evidencia = criterio["verificar"](contexto)
        except Exception as erro:
            conforme, evidencia = False, f"Falha ao avaliar o criterio: {erro}"
        itens.append({
            "codigo": criterio["codigo"],
            "categoria": criterio["categoria"],
            "descricao": criterio["descricao"],
            "status": _RESULTADO_POR_CONFORME.get(conforme, "NC"),
            "evidencia": evidencia,
        })
    return itens


# Lê o PDF, roda o checklist e calcula a % de aderência (CF / (CF + NC)).
def auditar(arquivo_pdf, nome_arquivo):
    texto, paginas, palavras = extrair_texto(arquivo_pdf)
    itens = executar_checklist(texto, paginas, palavras)

    conformes = [item for item in itens if item["status"] == "CF"]
    nao_conformes = [item for item in itens if item["status"] == "NC"]
    avaliaveis = len(conformes) + len(nao_conformes)
    aderencia = round(len(conformes) / avaliaveis * 100, 1) if avaliaveis else 0.0

    return {
        "arquivo": nome_arquivo,
        "total_criterios": len(itens),
        "aderencia": aderencia,
        "nao_conformidades": nao_conformes,
        "itens": itens,
    }

# Execução da auditoria e cálculo da aderência.
#
# Rodar cada critério do checklist contra o documento (executar_checklist) e
# consolidar o resultado com a porcentagem de aderência e as não
# conformidades encontradas (auditar).
#
# Cada critério resulta em um de três estados, resolvido aqui a partir do
# que a função "verificar" do critério retornou:
#   True  -> "CF"  (conforme)
#   False -> "NC"  (não conforme)
#   None  -> "N/A" (não aplicável / não verificável automaticamente)
#
# A aderência considera apenas os itens avaliáveis: CF ÷ (CF + NC). Itens
# N/A ficam de fora da conta, do mesmo jeito que na planilha de avaliação
# da disciplina.
from .criterios import CRITERIOS, FAIXAS_DE_ADERENCIA
from .leitura_pdf import extrair_texto, normalizar

_RESULTADO_POR_CONFORME = {True: "CF", False: "NC", None: "N/A"}


# Roda cada critério do checklist contra o documento e devolve a lista de
# resultados (um dicionário por critério, com status CF/NC/N-A e evidência).
# Se um critério falhar ao avaliar, isso não derruba a auditoria inteira — o
# item correspondente só é marcado como NC.
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


# Traduz a % de aderência geral na faixa da disciplina (Baixa/Média/Alta) e
# sua interpretação.
def classificar_aderencia(aderencia):
    for limite, nivel, interpretacao in FAIXAS_DE_ADERENCIA:
        if aderencia <= limite:
            return nivel, interpretacao
    return FAIXAS_DE_ADERENCIA[-1][1], FAIXAS_DE_ADERENCIA[-1][2]


# Função principal do motor: lê o PDF, executa o checklist e calcula a
# porcentagem de aderência.
def auditar(arquivo_pdf, nome_arquivo):
    texto, paginas, palavras = extrair_texto(arquivo_pdf)
    itens = executar_checklist(texto, paginas, palavras)

    conformes = [item for item in itens if item["status"] == "CF"]
    nao_conformes = [item for item in itens if item["status"] == "NC"]
    nao_aplicaveis = [item for item in itens if item["status"] == "N/A"]
    avaliaveis = len(conformes) + len(nao_conformes)
    aderencia = round(len(conformes) / avaliaveis * 100, 1) if avaliaveis else 0.0
    nivel_aderencia, interpretacao_aderencia = classificar_aderencia(aderencia)

    return {
        "arquivo": nome_arquivo,
        "paginas": paginas,
        "palavras": palavras,
        "total_criterios": len(itens),
        "aderencia": aderencia,
        "nivel_aderencia": nivel_aderencia,
        "interpretacao_aderencia": interpretacao_aderencia,
        "nao_conformidades": nao_conformes,
        "nao_aplicaveis": nao_aplicaveis,
        "itens": itens,
    }

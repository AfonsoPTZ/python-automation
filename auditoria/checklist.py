# Executa o checklist (via IA) contra o documento e calcula a aderência.
from .ia import avaliar_com_ia, avaliar_projeto_com_ia
from .leitura_documentos import extrair_texto_documentos
from .leitura_pdf import extrair_texto


# Lê o PDF, avalia o checklist com a IA e calcula a % de aderência (CF / (CF + NC)).
def auditar(arquivo_pdf, nome_arquivo):
    texto, _paginas, _palavras = extrair_texto(arquivo_pdf)
    itens = avaliar_com_ia(texto)

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


# Lê um ou mais documentos de um projeto (pdf/docx/xlsx/txt), avalia o
# checklist com a IA (pedindo título/impacto/ação corretiva para as NCs) e
# calcula a % de aderência. Usado pelo Painel do Auditor.
def auditar_projeto(caminhos_arquivos):
    texto = extrair_texto_documentos(caminhos_arquivos)
    itens = avaliar_projeto_com_ia(texto)

    conformes = [item for item in itens if item["status"] == "CF"]
    nao_conformes = [item for item in itens if item["status"] == "NC"]
    avaliaveis = len(conformes) + len(nao_conformes)
    aderencia = round(len(conformes) / avaliaveis * 100, 1) if avaliaveis else 0.0

    return {
        "total_criterios": len(itens),
        "aderencia": aderencia,
        "nao_conformidades": nao_conformes,
        "itens": itens,
    }

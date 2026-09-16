# Extrai o texto do PDF auditado.
import re

from pypdf import PdfReader


# Lê o PDF (caminho ou arquivo enviado) e devolve (texto, páginas, palavras).
def extrair_texto(arquivo_pdf):
    leitor = PdfReader(arquivo_pdf)
    texto = "\n".join((pagina.extract_text() or "") for pagina in leitor.pages)
    return texto, len(leitor.pages), len(re.findall(r"\w+", texto))


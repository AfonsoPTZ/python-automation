# Extrai e normaliza o texto do PDF auditado.
import re
import unicodedata

from pypdf import PdfReader


# Minúsculas + sem acentos.
def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
    return texto.lower()


# Lê o PDF (caminho ou arquivo enviado) e devolve (texto, páginas, palavras).
def extrair_texto(arquivo_pdf):
    leitor = PdfReader(arquivo_pdf)
    texto = "\n".join((pagina.extract_text() or "") for pagina in leitor.pages)
    return texto, len(leitor.pages), len(re.findall(r"\w+", texto))


# Leitura do documento auditado.
#
# Transforma o PDF enviado em texto utilizável pelo restante do motor —
# extrai o conteúdo, normaliza (minúsculas + sem acentos) e recorta trechos
# legíveis para exibir como evidência.
import re
import unicodedata

from pypdf import PdfReader


# Minúsculas + remoção de acentos, preservando o comprimento da string.
def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
    return texto.lower()


# Lê o PDF (caminho ou arquivo enviado) e devolve (texto, páginas, palavras).
def extrair_texto(arquivo_pdf):
    leitor = PdfReader(arquivo_pdf)
    texto = "\n".join((pagina.extract_text() or "") for pagina in leitor.pages)
    return texto, len(leitor.pages), len(re.findall(r"\w+", texto))


# Recorta um pedaço legível do texto ao redor da 1ª ocorrência do termo,
# para mostrar como evidência ao auditor.
def trecho_ao_redor(texto_original, texto_normalizado, termo_normalizado):
    posicao = texto_normalizado.find(termo_normalizado)
    if posicao < 0:
        return ""
    inicio = max(0, posicao - 45)
    fim = min(len(texto_original), posicao + len(termo_normalizado) + 45)
    return re.sub(r"\s+", " ", texto_original[inicio:fim]).strip()

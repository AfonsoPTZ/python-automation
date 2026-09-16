# Fábricas de verificadores de critério: verificar(contexto) -> (True/False/None, evidencia).
import re

from .leitura_pdf import normalizar


# Conforme se algum dos termos (ou sinônimos) aparecer no texto.
def termos(*termos_esperados, quantidade_exemplos=5):
    termos_normalizados = [(termo, normalizar(termo)) for termo in termos_esperados]

    def verificar(contexto):
        for termo_original, termo_normalizado in termos_normalizados:
            if termo_normalizado in contexto["texto"]:
                return True, f'Evidencia (termo "{termo_original}") localizada no documento.'
        amostra = ", ".join(f'"{termo}"' for termo, _ in termos_normalizados[:quantidade_exemplos])
        return False, f"Nenhuma evidencia textual localizada. Esperado algo como: {amostra}."

    return verificar


# Conforme se o padrão (regex) casar em algum ponto do texto.
def regex(padrao, descricao):
    padrao_compilado = re.compile(padrao, re.MULTILINE)

    def verificar(contexto):
        correspondencia = padrao_compilado.search(contexto["texto"])
        if correspondencia:
            return True, f'Evidencia ({descricao}): "{correspondencia.group(0).strip()[:80]}"'
        return False, f"Padrao nao encontrado ({descricao})."

    return verificar


# Conforme se o padrão ocorrer pelo menos `quantidade_minima` vezes.
def contagem_regex(padrao, quantidade_minima, descricao):
    padrao_compilado = re.compile(padrao, re.MULTILINE)

    def verificar(contexto):
        ocorrencias = padrao_compilado.findall(contexto["texto"])
        conforme = len(ocorrencias) >= quantidade_minima
        return conforme, (
            f"{len(ocorrencias)} ocorrencia(s) de {descricao} encontradas." if conforme
            else f"Apenas {len(ocorrencias)} ocorrencia(s) de {descricao}; esperado >= {quantidade_minima}."
        )

    return verificar


# Conforme somente se todos os verificadores informados forem conformes.
def combinado(*verificadores):
    def verificar(contexto):
        evidencias = []
        for verificador in verificadores:
            conforme, evidencia = verificador(contexto)
            if not conforme:
                return conforme, evidencia
            evidencias.append(evidencia)
        return True, " | ".join(evidencias)
    return verificar


# Reprova se ainda houver texto de instrução do template (ex.: "<Descreva...>").
def sem_marcadores_de_template(contexto):
    ocorrencias = re.findall(r"<[^<>]{5,200}>", contexto["original"])
    if ocorrencias:
        exemplo = re.sub(r"\s+", " ", ocorrencias[0]).strip()[:100]
        return False, f"{len(ocorrencias)} trecho(s) de instrucao do template ainda presentes, ex.: \"{exemplo}\"."
    return True, "Nenhum texto de instrucao do template (<...>) encontrado na versao avaliada."

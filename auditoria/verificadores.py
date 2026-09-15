# Fábricas de verificadores de critério, reutilizáveis por qualquer checklist.
#
# Dado o contexto de um documento (texto normalizado, texto original,
# páginas, palavras), devolvem funções que checam uma evidência específica
# no texto. Cada verificador tem a assinatura:
#
#   verificar(contexto) -> (resultado, evidencia: str)
#
# Onde "resultado" pode ser:
#   True  -> critério conforme (CF)
#   False -> critério não conforme (NC)
#   None  -> critério não aplicável / não verificável automaticamente (N/A)
#            (ex.: exige comparação fina entre seções que só um revisor
#            humano faz bem)
#
# Quem interpreta esse resultado em CF/NC/N-A é o motor, em checklist.py.
# Este módulo não conhece nenhum checklist específico — só fornece os
# blocos de construção (evita repetir a mesma lógica de regex/termos em
# cada critério).
import re

from .leitura_pdf import normalizar, trecho_ao_redor

# Expressões que costumam indicar um documento inacabado (rascunho) ou um
# template preenchido pela metade.
MARCADORES_DE_PENDENCIA = [
    r"\btodo\b", r"\btbd\b", r"\bxxx\b", r"\bfixme\b",
    r"a definir", r"a ser definido", r"a ser definida", r"a ser preenchido",
    r"preencher aqui", r"lorem ipsum", r"\[\.\.\.\]", r"<inserir",
    r"pendente de defini", r"sera detalhado posteriormente",
    r"sera revisado posteriormente", r"posteriormente podem ser adicionad",
]


# Critério conforme se QUALQUER um dos termos (ou sinônimos) aparecer no texto.
def termos(*termos_esperados, quantidade_exemplos=5):
    termos_normalizados = [(termo, normalizar(termo)) for termo in termos_esperados]

    def verificar(contexto):
        for termo_original, termo_normalizado in termos_normalizados:
            if termo_normalizado in contexto["texto"]:
                trecho = trecho_ao_redor(contexto["original"], contexto["texto"], termo_normalizado)
                return True, f'Evidencia (termo "{termo_original}"): "...{trecho}..."'
        amostra = ", ".join(f'"{termo}"' for termo, _ in termos_normalizados[:quantidade_exemplos])
        return False, f"Nenhuma evidencia textual localizada. Esperado algo como: {amostra}."

    return verificar


# Critério conforme se o padrão (regex) casar em algum ponto do texto.
def regex(padrao, descricao):
    padrao_compilado = re.compile(padrao, re.MULTILINE)

    def verificar(contexto):
        correspondencia = padrao_compilado.search(contexto["texto"])
        if correspondencia:
            return True, f'Evidencia ({descricao}): "{correspondencia.group(0).strip()[:80]}"'
        return False, f"Padrao nao encontrado ({descricao})."

    return verificar


# Critério conforme se o padrão ocorrer pelo menos `quantidade_minima` vezes
# (ex.: exigir várias menções a "heurística" ao longo do planejamento).
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


# Critério conforme somente se TODOS os verificadores informados forem conformes.
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


# Critério conforme se QUALQUER um dos verificadores informados for conforme
# (ex.: aceitar duas formas diferentes de comprovar o mesmo critério).
def qualquer(*verificadores):
    def verificar(contexto):
        evidencias_negativas = []
        for verificador in verificadores:
            conforme, evidencia = verificador(contexto)
            if conforme:
                return True, evidencia
            evidencias_negativas.append(evidencia)
        return False, evidencias_negativas[0]
    return verificar


# Critério estrutural: exige pelo menos 4 títulos de seção numerados (ex.:
# "1.", "2.1", "3.") — indício de que o documento tem estrutura formal.
def secoes_numeradas(contexto):
    titulos_encontrados = re.findall(r"(?m)^\s*\d+(?:\.\d+)*\.?\s+[a-z]", contexto["texto"])
    conforme = len(titulos_encontrados) >= 4
    return conforme, (
        f"{len(titulos_encontrados)} titulos de secao numerados detectados." if conforme
        else f"Apenas {len(titulos_encontrados)} titulo(s) numerado(s); esperado >= 4."
    )


# Critério editorial: reprova o documento se houver marcadores típicos de
# rascunho inacabado (TODO, TBD, "a definir"...).
def sem_pendencias(contexto):
    marcadores_encontrados = sorted({
        correspondencia.group(0)
        for padrao in MARCADORES_DE_PENDENCIA
        for correspondencia in re.finditer(padrao, contexto["texto"])
    })
    if marcadores_encontrados:
        return False, "Marcadores de pendencia / documento incompleto: " + ", ".join(marcadores_encontrados)
    return True, "Nenhum marcador de pendencia (TODO/TBD/'a definir'...) encontrado."


# Critério de consistência: reprova se ainda houver texto de instrução do
# template (ex.: "<Descreva...>") que o aluno deveria ter apagado.
def sem_marcadores_de_template(contexto):
    ocorrencias = re.findall(r"<[^<>]{5,200}>", contexto["original"])
    if ocorrencias:
        exemplo = re.sub(r"\s+", " ", ocorrencias[0]).strip()[:100]
        return False, f"{len(ocorrencias)} trecho(s) de instrucao do template ainda presentes, ex.: \"{exemplo}\"."
    return True, "Nenhum texto de instrucao do template (<...>) encontrado na versao avaliada."


# Critério editorial: exige um tamanho mínimo de documento, para evitar
# aprovar rascunhos muito curtos para serem um artefato completo.
def extensao_minima(paginas_minimas, palavras_minimas):
    def verificar(contexto):
        conforme = contexto["paginas"] >= paginas_minimas and contexto["palavras"] >= palavras_minimas
        return conforme, (
            f"Documento com {contexto['paginas']} paginas e {contexto['palavras']} palavras." if conforme
            else f"Documento curto: {contexto['paginas']} paginas / {contexto['palavras']} "
                 f"palavras (minimo {paginas_minimas} paginas e {palavras_minimas} palavras)."
        )
    return verificar

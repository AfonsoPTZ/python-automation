# Relatório final do projeto (PDF), gerado ao encerrar a auditoria.
#
# Duas partes:
# - coletar_dados: junta do banco tudo o que aconteceu no projeto (auditorias,
#   NCs, versões de documento, e-mails, escalonamentos). Esses números são a
#   fonte da verdade — vão para as tabelas do PDF e para o prompt da IA.
# - montar_pdf: monta o PDF com os números + o texto narrativo que a IA
#   escreveu (auditorias.relatorio_ia). Sem texto da IA, o PDF sai só com os
#   dados, para o download nunca depender da IA estar disponível.
import json
from collections import Counter
from datetime import datetime

from fpdf import FPDF
from fpdf.fonts import FontFace

from auditoria.criterios import CRITERIOS, NOME

FORMATO_DATA = "%Y-%m-%d %H:%M:%S"
_CATEGORIA_POR_CODIGO = {c["codigo"]: c["categoria"] for c in CRITERIOS}


def _data_br(valor, com_hora=True):
    if not valor:
        return "-"
    try:
        dt = datetime.strptime(str(valor)[:19], FORMATO_DATA)
    except ValueError:
        return str(valor)
    return dt.strftime("%d/%m/%Y %H:%M" if com_hora else "%d/%m/%Y")


def coletar_dados(db, auditoria_id):
    auditoria_final = db.execute("SELECT * FROM auditorias WHERE id = ?", (auditoria_id,)).fetchone()
    projeto_id = auditoria_final["projeto_id"]
    projeto = db.execute("SELECT * FROM projetos WHERE id = ?", (projeto_id,)).fetchone()
    participantes = db.execute(
        "SELECT nome, email FROM participantes WHERE projeto_id = ? ORDER BY nome", (projeto_id,)
    ).fetchall()
    documentos = db.execute(
        "SELECT nome_original, versao, uploaded_at FROM documentos WHERE projeto_id = ? "
        "ORDER BY versao, uploaded_at",
        (projeto_id,),
    ).fetchall()
    # Só as auditorias até a que está sendo encerrada (inclusive).
    auditorias = db.execute(
        "SELECT * FROM auditorias WHERE projeto_id = ? AND id <= ? ORDER BY id",
        (projeto_id, auditoria_id),
    ).fetchall()
    logs = db.execute(
        "SELECT tipo, destinatarios, data_envio, corpo_resumido FROM logs_emails "
        "WHERE projeto_id = ? ORDER BY id",
        (projeto_id,),
    ).fetchall()

    versoes = {}
    for doc in documentos:
        versoes.setdefault(doc["versao"], {"versao": doc["versao"], "enviado_em": _data_br(doc["uploaded_at"]), "arquivos": []})
        versoes[doc["versao"]]["arquivos"].append(doc["nome_original"])

    lista_auditorias = []
    for indice, auditoria in enumerate(auditorias):
        ncs = db.execute(
            "SELECT * FROM nao_conformidades WHERE auditoria_id = ? "
            "ORDER BY item_checklist IS NULL, item_checklist, id",
            (auditoria["id"],),
        ).fetchall()
        categorias = Counter(_CATEGORIA_POR_CODIGO.get(nc["item_checklist"], "Sem item do checklist") for nc in ncs)
        lista_auditorias.append({
            "nome": "Auditoria inicial" if indice == 0 else f"Reavaliação #{indice}",
            "data": _data_br(auditoria["data_auditoria"]),
            "aderencia_percentual": auditoria["aderencia"],
            "status": auditoria["status"],
            "parecer_final": auditoria["parecer_final"],
            "total_ncs": len(ncs),
            "ncs_pela_ia": sum(1 for nc in ncs if nc["origem"] == "ia"),
            "ncs_manuais": sum(1 for nc in ncs if nc["origem"] == "manual"),
            "ncs_resolvidas": sum(1 for nc in ncs if nc["status"] == "resolvida"),
            "ncs_em_aberto": sum(1 for nc in ncs if nc["status"] == "aberta"),
            "ncs_notificadas_com_prazo": sum(1 for nc in ncs if nc["notificado_em"]),
            "ncs_escalonadas": sum(1 for nc in ncs if nc["escalonado"]),
            "ncs_por_categoria": dict(categorias.most_common()),
            "nao_conformidades": [
                {
                    "item_checklist": nc["item_checklist"],
                    "titulo": nc["titulo"],
                    "status": nc["status"],
                    "origem": nc["origem"],
                    "escalonada": bool(nc["escalonado"]),
                    "prazo_limite": _data_br(nc["prazo_limite"]),
                }
                for nc in ncs
            ],
        })

    tipos_email = Counter(log["tipo"] for log in logs)
    aderencias = [a["aderencia"] for a in auditorias if a["aderencia"] is not None]
    inicio = projeto["created_at"]
    fim = auditoria_final["encerrada_em"]
    duracao_dias = None
    try:
        duracao_dias = (datetime.strptime(fim[:19], FORMATO_DATA) - datetime.strptime(inicio[:19], FORMATO_DATA)).days
    except (TypeError, ValueError):
        pass

    return {
        "projeto": {
            "nome": projeto["nome"],
            "descricao": projeto["descricao"],
            "responsavel_superior": projeto["responsavel_superior_email"],
            "criado_em": _data_br(inicio),
            "encerrado_em": _data_br(fim),
            "duracao_em_dias": duracao_dias,
            "checklist_utilizado": f"{NOME} ({len(CRITERIOS)} itens)",
        },
        "equipe": [{"nome": p["nome"], "email": p["email"]} for p in participantes],
        "parecer_final": auditoria_final["parecer_final"],
        "resumo": {
            "total_auditorias": len(auditorias),
            "versoes_de_documento_enviadas": len(versoes),
            "aderencia_inicial_percentual": aderencias[0] if aderencias else None,
            "aderencia_final_percentual": aderencias[-1] if aderencias else None,
            "ncs_encontradas_na_primeira_auditoria": lista_auditorias[0]["total_ncs"] if lista_auditorias else 0,
            "ncs_na_ultima_auditoria": lista_auditorias[-1]["total_ncs"] if lista_auditorias else 0,
            "ncs_resolvidas_na_ultima_auditoria": lista_auditorias[-1]["ncs_resolvidas"] if lista_auditorias else 0,
            "ncs_em_aberto_no_encerramento": lista_auditorias[-1]["ncs_em_aberto"] if lista_auditorias else 0,
            "emails_de_correcao_preparados": tipos_email.get("correcao", 0),
            "escalonamentos_ao_responsavel": tipos_email.get("escalonamento", 0),
            "total_emails_preparados": len(logs),
        },
        "versoes_de_documento": list(versoes.values()),
        "auditorias": lista_auditorias,
        "historico_de_emails": [
            {
                "tipo": log["tipo"],
                "data": _data_br(log["data_envio"]),
                "destinatarios": log["destinatarios"],
                "resumo": log["corpo_resumido"],
            }
            for log in logs
        ],
    }


# ===================== PDF =====================
# As fontes padrão do PDF (Helvetica) só cobrem latin-1: acentos do português
# funcionam, mas aspas curvas, travessões e emojis que a IA às vezes usa não.
_TROCAS = {"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "…": "...", "•": "-", " ": " "}


def _t(texto):
    texto = "" if texto is None else str(texto)
    for de, para in _TROCAS.items():
        texto = texto.replace(de, para)
    return texto.encode("latin-1", "replace").decode("latin-1")


_AZUL = (44, 80, 144)
_CINZA = (110, 118, 134)
_TEXTO = (31, 39, 51)
_STATUS_NC = {"aberta": "Aberta", "resolvida": "Resolvida"}
_TIPO_EMAIL = {"correcao": "Correção", "escalonamento": "Escalonamento", "fechamento": "Fechamento"}


class _PDF(FPDF):
    def __init__(self, nome_projeto):
        super().__init__(format="A4")
        self.nome_projeto = nome_projeto
        self.set_margins(18, 18, 18)
        self.set_auto_page_break(True, margin=18)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*_CINZA)
        self.cell(0, 6, _t(f"Relatório final de auditoria - {self.nome_projeto}"), align="L")
        self.ln(10)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*_CINZA)
        self.cell(0, 6, _t(f"Página {self.page_no()}/{{nb}}"), align="C")

    def titulo_secao(self, texto):
        if self.get_y() > self.h - 50:
            self.add_page()
        self.ln(4)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*_AZUL)
        self.cell(0, 8, _t(texto), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*_AZUL)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def paragrafos(self, texto):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*_TEXTO)
        for paragrafo in [p.strip() for p in str(texto or "").split("\n") if p.strip()]:
            self.multi_cell(0, 5.2, _t(paragrafo), new_x="LMARGIN", new_y="NEXT")
            self.ln(2)

    def tabela(self, cabecalho, linhas, larguras):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*_TEXTO)
        with self.table(
            col_widths=larguras, text_align="LEFT", line_height=5,
            headings_style=FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=_AZUL),
            borders_layout="HORIZONTAL_LINES",
        ) as tabela:
            linha = tabela.row()
            for coluna in cabecalho:
                linha.cell(_t(coluna))
            for valores in linhas:
                linha = tabela.row()
                for valor in valores:
                    linha.cell(_t(valor))
        self.ln(3)


def montar_pdf(dados, texto_ia=None):
    projeto = dados["projeto"]
    resumo = dados["resumo"]
    pdf = _PDF(projeto["nome"])
    pdf.alias_nb_pages()
    pdf.add_page()

    # Capa / cabeçalho
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*_TEXTO)
    pdf.multi_cell(0, 10, _t("Relatório final de auditoria"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*_AZUL)
    pdf.multi_cell(0, 8, _t(projeto["nome"]), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*_CINZA)
    for rotulo, valor in [
        ("Parecer final", dados["parecer_final"]),
        ("Período", f'{projeto["criado_em"]} a {projeto["encerrado_em"]}'
                    + (f' ({projeto["duracao_em_dias"]} dia(s))' if projeto["duracao_em_dias"] is not None else "")),
        ("Responsável superior", projeto["responsavel_superior"]),
        ("Equipe", ", ".join(p["nome"] for p in dados["equipe"]) or "-"),
        ("Checklist", projeto["checklist_utilizado"]),
    ]:
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.cell(42, 5.5, _t(rotulo + ":"))
        pdf.set_font("Helvetica", "", 9.5)
        pdf.multi_cell(0, 5.5, _t(valor), new_x="LMARGIN", new_y="NEXT")

    # Indicadores em números
    pdf.titulo_secao("Indicadores do processo")
    aderencia = "-"
    if resumo["aderencia_inicial_percentual"] is not None:
        aderencia = f'{resumo["aderencia_inicial_percentual"]}% -> {resumo["aderencia_final_percentual"]}%'
    pdf.tabela(
        ["Indicador", "Valor"],
        [
            ["Auditorias realizadas", resumo["total_auditorias"]],
            ["Versões de documento enviadas", resumo["versoes_de_documento_enviadas"]],
            ["Aderência (inicial -> final)", aderencia],
            ["NCs encontradas na primeira auditoria", resumo["ncs_encontradas_na_primeira_auditoria"]],
            ["NCs na última auditoria", resumo["ncs_na_ultima_auditoria"]],
            ["NCs resolvidas na última auditoria", resumo["ncs_resolvidas_na_ultima_auditoria"]],
            ["NCs em aberto no encerramento", resumo["ncs_em_aberto_no_encerramento"]],
            ["E-mails de correção preparados", resumo["emails_de_correcao_preparados"]],
            ["Escalonamentos ao responsável", resumo["escalonamentos_ao_responsavel"]],
        ],
        (3, 1),
    )

    secoes_ia = [
        ("Resumo executivo", "resumo_executivo"),
        ("Histórico do processo", "historico_do_processo"),
        ("Análise das não conformidades", "analise_das_nao_conformidades"),
        ("Comunicação e prazos", "comunicacao_e_prazos"),
        ("Conclusão", "conclusao"),
    ]
    if texto_ia:
        for titulo, chave in secoes_ia:
            if texto_ia.get(chave):
                pdf.titulo_secao(titulo)
                pdf.paragrafos(texto_ia[chave])
        recomendacoes = [r for r in texto_ia.get("recomendacoes") or [] if str(r).strip()]
        if recomendacoes:
            pdf.titulo_secao("Recomendações")
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*_TEXTO)
            for numero, recomendacao in enumerate(recomendacoes, start=1):
                pdf.multi_cell(0, 5.2, _t(f"{numero}. {recomendacao}"), new_x="LMARGIN", new_y="NEXT")
                pdf.ln(1)
    else:
        pdf.titulo_secao("Análise")
        pdf.paragrafos(
            "O texto de análise escrito pela IA não está disponível para este relatório. "
            "Os dados abaixo foram extraídos diretamente do sistema. Use o botão "
            "\"Gerar novamente com IA\" na página do projeto para incluir a análise."
        )

    # Anexos com os dados brutos
    pdf.titulo_secao("Auditorias realizadas")
    pdf.tabela(
        ["Auditoria", "Data", "Aderência", "NCs", "Resolvidas", "Escalonadas"],
        [
            [a["nome"], a["data"], f'{a["aderencia_percentual"]}%' if a["aderencia_percentual"] is not None else "-",
             a["total_ncs"], a["ncs_resolvidas"], a["ncs_escalonadas"]]
            for a in dados["auditorias"]
        ],
        (3, 3, 2, 1.3, 2, 2),
    )

    if dados["versoes_de_documento"]:
        pdf.titulo_secao("Versões de documento")
        pdf.tabela(
            ["Versão", "Enviado em", "Arquivos"],
            [[f'Documento {v["versao"]}', v["enviado_em"], ", ".join(v["arquivos"])] for v in dados["versoes_de_documento"]],
            (1.3, 2, 5),
        )

    ultima = dados["auditorias"][-1] if dados["auditorias"] else None
    if ultima and ultima["nao_conformidades"]:
        pdf.titulo_secao(f'Não conformidades - {ultima["nome"]}')
        pdf.tabela(
            ["Item", "Título", "Origem", "Situação"],
            [
                [nc["item_checklist"] or "-", nc["titulo"], "IA" if nc["origem"] == "ia" else "Manual",
                 _STATUS_NC.get(nc["status"], nc["status"]) + (" (escalonada)" if nc["escalonada"] else "")]
                for nc in ultima["nao_conformidades"]
            ],
            (1, 6, 1.3, 2.2),
        )

    if dados["historico_de_emails"]:
        pdf.titulo_secao("Histórico de e-mails e escalonamentos")
        pdf.tabela(
            ["Data", "Tipo", "Para"],
            [[e["data"], _TIPO_EMAIL.get(e["tipo"], e["tipo"]), e["destinatarios"]] for e in dados["historico_de_emails"]],
            (2, 2, 5),
        )

    return bytes(pdf.output())


def carregar_texto_ia(auditoria):
    if not auditoria["relatorio_ia"]:
        return None
    try:
        return json.loads(auditoria["relatorio_ia"])
    except (TypeError, json.JSONDecodeError):
        return None

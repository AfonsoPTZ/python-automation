# Ações sobre uma auditoria: encerrar com o parecer final. Notificação de
# correção e escalonamento agora são por não conformidade (ver routes/nc.py)
# — cada NC tem seu próprio prazo e seu próprio e-mail, em vez de um resumo
# único da auditoria inteira.
import json
import re
import unicodedata
from datetime import datetime

from flask import Blueprint, Response, abort, flash, redirect, request, url_for

from auditoria.ia import gerar_relatorio_final_com_ia
from database import get_db
from services.relatorio_final import carregar_texto_ia, coletar_dados, montar_pdf

bp = Blueprint("auditorias", __name__, url_prefix="/auditorias")

PARECERES_VALIDOS = ["Aprovado", "Aprovado com Ressalvas", "Reprovado"]


def _buscar_auditoria_e_projeto(auditoria_id):
    db = get_db()
    auditoria = db.execute("SELECT * FROM auditorias WHERE id = ?", (auditoria_id,)).fetchone()
    if auditoria is None:
        return None, None
    projeto = db.execute("SELECT * FROM projetos WHERE id = ?", (auditoria["projeto_id"],)).fetchone()
    return auditoria, projeto


@bp.post("/<int:auditoria_id>/encerrar")
def encerrar(auditoria_id):
    db = get_db()
    auditoria, projeto = _buscar_auditoria_e_projeto(auditoria_id)
    if auditoria is None:
        flash("Auditoria não encontrada.", "erro")
        return redirect(url_for("projetos.listar"))

    parecer_final = request.form.get("parecer_final")
    if parecer_final not in PARECERES_VALIDOS:
        flash("Selecione um parecer final válido.", "erro")
        return redirect(url_for("projetos.detalhe", projeto_id=projeto["id"]))

    # Verifica NCs abertas antes de encerrar.
    total_nc_abertas = db.execute(
        "SELECT COUNT(*) AS total FROM nao_conformidades "
        "WHERE auditoria_id = ? AND status = 'aberta'",
        (auditoria_id,),
    ).fetchone()["total"]

    # Aprovar (com ou sem ressalvas) com NCs abertas é um estado inválido:
    # bloqueia e orienta o usuário a resolver as pendências primeiro.
    if total_nc_abertas > 0 and parecer_final in ("Aprovado", "Aprovado com Ressalvas"):
        flash(
            f"Não é possível encerrar como \"{parecer_final}\" com "
            f"{total_nc_abertas} não conformidade(s) ainda aberta(s). "
            "Resolva ou exclua as NCs pendentes antes de emitir este parecer.",
            "erro",
        )
        return redirect(url_for("projetos.detalhe", projeto_id=projeto["id"]))

    db.execute(
        "UPDATE auditorias SET parecer_final = ?, status = 'encerrada', encerrada_em = ? WHERE id = ?",
        (parecer_final, datetime.now().strftime(FORMATO_DATA), auditoria_id),
    )
    db.execute("UPDATE projetos SET status = 'Encerrado' WHERE id = ?", (projeto["id"],))
    db.commit()

    # O encerramento já está salvo: se a IA falhar aqui, a auditoria continua
    # encerrada e o relatório pode ser gerado de novo pelo botão da página.
    erro_relatorio = _gerar_relatorio(db, auditoria_id)
    if erro_relatorio:
        flash(f"O relatório final não foi gerado pela IA: {erro_relatorio}", "erro")

    if total_nc_abertas > 0:
        # Reprovado com NCs abertas — permitido, mas avisar.
        flash(
            f"Auditoria encerrada com parecer: {parecer_final}. "
            f"Atenção: {total_nc_abertas} não conformidade(s) permanecem em aberto no registro.",
            "ok",
        )
    else:
        flash(f"Auditoria encerrada com parecer: {parecer_final}.", "ok")
    return redirect(url_for("projetos.detalhe", projeto_id=projeto["id"]))


FORMATO_DATA = "%Y-%m-%d %H:%M:%S"


# Pede à IA o texto do relatório final e salva na auditoria. Devolve a
# mensagem de erro (ou None se deu certo) para quem chamou decidir o flash.
def _gerar_relatorio(db, auditoria_id):
    try:
        secoes = gerar_relatorio_final_com_ia(coletar_dados(db, auditoria_id))
    except Exception as erro:
        return str(erro)
    db.execute(
        "UPDATE auditorias SET relatorio_ia = ?, relatorio_gerado_em = ? WHERE id = ?",
        (json.dumps(secoes, ensure_ascii=False), datetime.now().strftime(FORMATO_DATA), auditoria_id),
    )
    db.commit()
    return None


@bp.post("/<int:auditoria_id>/relatorio/gerar")
def gerar_relatorio(auditoria_id):
    db = get_db()
    auditoria, projeto = _buscar_auditoria_e_projeto(auditoria_id)
    if auditoria is None:
        abort(404)
    if auditoria["status"] != "encerrada":
        flash("O relatório final só pode ser gerado depois de encerrar a auditoria.", "erro")
    else:
        erro = _gerar_relatorio(db, auditoria_id)
        if erro:
            flash(f"Não foi possível gerar o relatório pela IA: {erro}", "erro")
        else:
            flash("Relatório final gerado. Já pode baixar o PDF.", "ok")
    return redirect(url_for("projetos.detalhe", projeto_id=projeto["id"]))


@bp.get("/<int:auditoria_id>/relatorio.pdf")
def baixar_relatorio(auditoria_id):
    db = get_db()
    auditoria, projeto = _buscar_auditoria_e_projeto(auditoria_id)
    if auditoria is None or auditoria["status"] != "encerrada":
        abort(404)
    pdf = montar_pdf(coletar_dados(db, auditoria_id), carregar_texto_ia(auditoria))
    sem_acento = unicodedata.normalize("NFKD", projeto["nome"]).encode("ascii", "ignore").decode()
    nome_arquivo = re.sub(r"[^A-Za-z0-9_-]+", "_", sem_acento).strip("_") or "projeto"
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="relatorio_final_{nome_arquivo}.pdf"'},
    )

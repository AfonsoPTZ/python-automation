# Ações sobre uma auditoria: encerrar com o parecer final. Notificação de
# correção e escalonamento agora são por não conformidade (ver routes/nc.py)
# — cada NC tem seu próprio prazo e seu próprio e-mail, em vez de um resumo
# único da auditoria inteira.
from flask import Blueprint, flash, redirect, request, url_for

from database import get_db

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
        "UPDATE auditorias SET parecer_final = ?, status = 'encerrada' WHERE id = ?",
        (parecer_final, auditoria_id),
    )
    db.execute("UPDATE projetos SET status = 'Encerrado' WHERE id = ?", (projeto["id"],))
    db.commit()

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

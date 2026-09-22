# Revisão manual das Não Conformidades (NCs): editar, adicionar, excluir,
# marcar como resolvida/pendente, notificar (definir prazo + e-mail) e
# escalonar — tudo por NC individual, não por auditoria inteira.
from datetime import datetime, timedelta

from flask import Blueprint, abort, flash, redirect, request, url_for

from database import get_db

bp = Blueprint("nc", __name__)

FORMATO_DATA = "%Y-%m-%d %H:%M:%S"


def _buscar_nc_com_projeto(nc_id):
    row = get_db().execute(
        "SELECT nao_conformidades.*, auditorias.projeto_id AS projeto_id "
        "FROM nao_conformidades "
        "JOIN auditorias ON auditorias.id = nao_conformidades.auditoria_id "
        "WHERE nao_conformidades.id = ?",
        (nc_id,),
    ).fetchone()
    if row is None:
        abort(404)
    return row


def _calcular_prazo_limite():
    horas = request.form.get("prazo_horas")
    prazo_customizado = request.form.get("prazo_customizado")

    if prazo_customizado:
        try:
            return datetime.strptime(prazo_customizado, "%Y-%m-%dT%H:%M").strftime(FORMATO_DATA)
        except ValueError:
            return None

    try:
        horas = int(horas)
    except (TypeError, ValueError):
        return None
    return (datetime.now() + timedelta(hours=horas)).strftime(FORMATO_DATA)


@bp.post("/auditorias/<int:auditoria_id>/nc")
def adicionar(auditoria_id):
    db = get_db()
    auditoria = db.execute("SELECT * FROM auditorias WHERE id = ?", (auditoria_id,)).fetchone()
    if auditoria is None:
        abort(404)

    titulo = (request.form.get("titulo") or "").strip()
    descricao_erro = (request.form.get("descricao_erro") or "").strip()
    evidencia = (request.form.get("evidencia") or "").strip()
    impacto = (request.form.get("impacto") or "").strip()
    acao_corretiva = (request.form.get("acao_corretiva") or "").strip()

    if not titulo or not descricao_erro:
        flash("Informe ao menos o título e a descrição da não conformidade.", "erro")
        return redirect(url_for("projetos.detalhe", projeto_id=auditoria["projeto_id"]))

    db.execute(
        "INSERT INTO nao_conformidades "
        "(auditoria_id, titulo, descricao_erro, evidencia, impacto, acao_corretiva, "
        "origem, status) VALUES (?, ?, ?, ?, ?, ?, 'manual', 'aberta')",
        (auditoria_id, titulo, descricao_erro, evidencia, impacto, acao_corretiva),
    )
    db.commit()
    flash("Não conformidade adicionada.", "ok")
    return redirect(url_for("projetos.detalhe", projeto_id=auditoria["projeto_id"]))


@bp.post("/nc/<int:nc_id>/editar")
def editar(nc_id):
    db = get_db()
    nc = _buscar_nc_com_projeto(nc_id)

    # O formulário sempre reenvia os valores atuais nos campos (são pré-preenchidos
    # no template), então um campo vazio aqui significa "o usuário apagou de
    # propósito" — mas só para título/descrição, que são obrigatórios; nos
    # opcionais, campo vazio no POST às vezes é só o valor atual "None" virando
    # string vazia no HTML, então preserva o valor existente nesse caso.
    titulo = (request.form.get("titulo") or nc["titulo"]).strip()
    descricao_erro = (request.form.get("descricao_erro") or nc["descricao_erro"]).strip()
    evidencia = (request.form.get("evidencia") or nc["evidencia"] or "").strip()
    impacto = (request.form.get("impacto") or nc["impacto"] or "").strip()
    acao_corretiva = (request.form.get("acao_corretiva") or nc["acao_corretiva"] or "").strip()

    db.execute(
        "UPDATE nao_conformidades SET titulo = ?, descricao_erro = ?, evidencia = ?, "
        "impacto = ?, acao_corretiva = ? WHERE id = ?",
        (titulo, descricao_erro, evidencia, impacto, acao_corretiva, nc_id),
    )
    db.commit()
    flash("Não conformidade atualizada.", "ok")
    return redirect(url_for("projetos.detalhe", projeto_id=nc["projeto_id"]))


@bp.post("/nc/<int:nc_id>/status")
def alternar_status(nc_id):
    db = get_db()
    nc = _buscar_nc_com_projeto(nc_id)
    novo_status = "resolvida" if nc["status"] == "aberta" else "aberta"
    db.execute("UPDATE nao_conformidades SET status = ? WHERE id = ?", (novo_status, nc_id))
    db.commit()
    flash(f"NC marcada como {novo_status}.", "ok")
    return redirect(url_for("projetos.detalhe", projeto_id=nc["projeto_id"]))


@bp.post("/nc/<int:nc_id>/excluir")
def excluir(nc_id):
    db = get_db()
    nc = _buscar_nc_com_projeto(nc_id)
    db.execute("DELETE FROM nao_conformidades WHERE id = ?", (nc_id,))
    db.commit()
    flash("Não conformidade removida.", "ok")
    return redirect(url_for("projetos.detalhe", projeto_id=nc["projeto_id"]))


@bp.post("/nc/<int:nc_id>/notificar")
def notificar(nc_id):
    db = get_db()
    nc = _buscar_nc_com_projeto(nc_id)

    if nc["status"] != "aberta":
        flash("Só é possível notificar uma NC ainda aberta.", "erro")
        return redirect(url_for("projetos.detalhe", projeto_id=nc["projeto_id"]))

    prazo_limite = _calcular_prazo_limite()
    if not prazo_limite:
        flash("Informe um prazo válido (horas ou data/hora customizada).", "erro")
        return redirect(url_for("projetos.detalhe", projeto_id=nc["projeto_id"]))

    participantes = db.execute(
        "SELECT * FROM participantes WHERE projeto_id = ?", (nc["projeto_id"],)
    ).fetchall()
    if not participantes:
        flash("Cadastre ao menos um integrante com e-mail antes de notificar.", "erro")
        return redirect(url_for("projetos.detalhe", projeto_id=nc["projeto_id"]))

    # O auditor escolhe quem recebe, por NC (checkboxes no modal de e-mail) —
    # aqui só confirma que o(s) e-mail(s) marcado(s) realmente pertence(m) a
    # um integrante do projeto, pra não aceitar valor arbitrário do form.
    emails_validos = {participante["email"] for participante in participantes}
    destinatarios = [
        email for email in request.form.getlist("participante_email") if email in emails_validos
    ]
    if not destinatarios:
        flash("Selecione ao menos um integrante para receber o e-mail.", "erro")
        return redirect(url_for("projetos.detalhe", projeto_id=nc["projeto_id"]))

    agora = datetime.now().strftime(FORMATO_DATA)
    db.execute(
        "UPDATE nao_conformidades SET prazo_limite = ?, escalonado = 0, notificado_em = ? WHERE id = ?",
        (prazo_limite, agora, nc_id),
    )
    db.execute(
        "UPDATE projetos SET status = 'Aguardando Correção' WHERE id = ? AND status != 'Encerrado'",
        (nc["projeto_id"],),
    )
    db.execute(
        "INSERT INTO logs_emails (projeto_id, tipo, destinatarios, corpo_resumido) "
        "VALUES (?, 'correcao', ?, ?)",
        (
            nc["projeto_id"],
            ", ".join(destinatarios),
            f'Prazo definido para "{nc["titulo"]}": {prazo_limite}. E-mail preparado para envio pelo Gmail.',
        ),
    )
    db.commit()

    flash("Prazo definido. Clique em \"Abrir e-mail no Gmail\" para enviar ao grupo.", "ok")
    return redirect(url_for("projetos.detalhe", projeto_id=nc["projeto_id"]))


@bp.post("/nc/<int:nc_id>/escalonar")
def escalonar(nc_id):
    db = get_db()
    nc = _buscar_nc_com_projeto(nc_id)
    projeto = db.execute("SELECT * FROM projetos WHERE id = ?", (nc["projeto_id"],)).fetchone()

    if nc["status"] != "aberta":
        flash("Só é possível escalonar uma NC ainda aberta.", "erro")
        return redirect(url_for("projetos.detalhe", projeto_id=nc["projeto_id"]))

    db.execute("UPDATE nao_conformidades SET escalonado = 1 WHERE id = ?", (nc_id,))
    db.execute(
        "UPDATE projetos SET status = 'Escalonado / Prazo Vencido' WHERE id = ?", (nc["projeto_id"],)
    )
    db.execute(
        "INSERT INTO logs_emails (projeto_id, tipo, destinatarios, corpo_resumido) "
        "VALUES (?, 'escalonamento', ?, ?)",
        (
            nc["projeto_id"],
            projeto["responsavel_superior_email"],
            f'Escalonamento manual da NC "{nc["titulo"]}". E-mail preparado para envio pelo Gmail.',
        ),
    )
    db.commit()

    flash("NC marcada como escalonada. Clique em \"Abrir e-mail no Gmail\" para enviar ao responsável.", "ok")
    return redirect(url_for("projetos.detalhe", projeto_id=nc["projeto_id"]))

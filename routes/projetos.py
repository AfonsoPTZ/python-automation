# Cadastro/listagem de projetos, upload de documentos e disparo da auditoria por IA.
from datetime import datetime
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

import config
from auditoria import auditar_projeto
from auditoria.criterios import NOME as CHECKLIST_PADRAO_NOME
from database import get_db
from services.gmail_link import montar_link_gmail, texto_escalonamento_nc, texto_notificacao_nc

FORMATO_DATA = "%Y-%m-%d %H:%M:%S"

bp = Blueprint("projetos", __name__, url_prefix="/projetos")

STATUS_VALIDOS = [
    "Em Auditoria",
    "Aguardando Correção",
    "Escalonado / Prazo Vencido",
    "Encerrado",
]


def _inserir_participantes(db, projeto_id, nomes, emails):
    # Linhas totalmente vazias são normais (sobra do formulário dinâmico), mas
    # uma linha com só nome OU só e-mail é um erro de preenchimento — sem
    # avisar, o integrante simplesmente não é salvo e o usuário não percebe.
    incompletos = []
    for nome, email in zip(nomes, emails):
        nome = (nome or "").strip()
        email = (email or "").strip()
        if nome and email:
            db.execute(
                "INSERT INTO participantes (projeto_id, nome, email) VALUES (?, ?, ?)",
                (projeto_id, nome, email),
            )
        elif nome or email:
            incompletos.append(nome or email)
    return incompletos


def _inserir_checklist_itens(db, checklist_id, codigos, categorias, descricoes):
    # Mesma lógica de _inserir_participantes: linha totalmente vazia é normal
    # (sobra do formulário dinâmico), mas descrição vazia é erro de
    # preenchimento — sem avisar, o item some sem o usuário perceber. Código
    # é opcional: fica auto-numerado ("C1", "C2"...) quando não informado.
    ordem = 0
    for codigo, categoria, descricao in zip(codigos, categorias, descricoes):
        codigo = (codigo or "").strip()
        categoria = (categoria or "").strip()
        descricao = (descricao or "").strip()
        if not descricao:
            continue
        ordem += 1
        db.execute(
            "INSERT INTO checklist_itens (checklist_id, codigo, categoria, descricao, ordem) "
            "VALUES (?, ?, ?, ?, ?)",
            (checklist_id, codigo or f"C{ordem}", categoria, descricao, ordem),
        )
    return ordem


def _buscar_projeto_ou_404(projeto_id):
    projeto = get_db().execute("SELECT * FROM projetos WHERE id = ?", (projeto_id,)).fetchone()
    if projeto is None:
        raise LookupError(f"Projeto {projeto_id} não encontrado.")
    return projeto


@bp.get("/")
def listar():
    db = get_db()
    status_filtro = request.args.get("status") or None
    alerta_filtro = request.args.get("alerta") or None
    busca = (request.args.get("q") or "").strip()
    agora = datetime.now().strftime(FORMATO_DATA)

    condicoes = []
    parametros = []
    if status_filtro:
        condicoes.append("status = ?")
        parametros.append(status_filtro)
    if alerta_filtro == "escalonados":
        condicoes.append("status = ?")
        parametros.append("Escalonado / Prazo Vencido")
    elif alerta_filtro == "vencidos":
        condicoes.append(
            "EXISTS (SELECT 1 FROM auditorias a "
            "JOIN nao_conformidades nc ON nc.auditoria_id = a.id "
            "WHERE a.projeto_id = projetos.id AND nc.status = 'aberta' "
            "AND nc.escalonado = 0 AND nc.notificado_em IS NOT NULL "
            "AND nc.prazo_limite IS NOT NULL AND nc.prazo_limite < ?)"
        )
        parametros.append(agora)
    elif alerta_filtro == "aguardando":
        condicoes.append("status = ?")
        parametros.append("Aguardando Correção")
        condicoes.append(
            "NOT EXISTS (SELECT 1 FROM auditorias a "
            "JOIN nao_conformidades nc ON nc.auditoria_id = a.id "
            "WHERE a.projeto_id = projetos.id AND nc.status = 'aberta' "
            "AND nc.escalonado = 0 AND nc.prazo_limite IS NOT NULL AND nc.prazo_limite < ?)"
        )
        parametros.append(agora)
    if busca:
        condicoes.append("nome LIKE ?")
        parametros.append(f"%{busca}%")

    sql = "SELECT * FROM projetos"
    if condicoes:
        sql += " WHERE " + " AND ".join(condicoes)
    sql += " ORDER BY created_at DESC"
    projetos = db.execute(sql, parametros).fetchall()

    contagem_status = {
        linha["status"]: linha["total"]
        for linha in db.execute(
            "SELECT status, COUNT(*) AS total FROM projetos GROUP BY status"
        ).fetchall()
    }
    total_projetos = sum(contagem_status.values())

    projetos_com_prazo = []
    for projeto in projetos:
        auditoria_atual = db.execute(
            "SELECT * FROM auditorias WHERE projeto_id = ? ORDER BY id DESC LIMIT 1",
            (projeto["id"],),
        ).fetchone()
        proximo_prazo = None
        alertas = {"abertas": 0, "aguardando": 0, "escalonadas": 0, "vencidos": 0}
        if auditoria_atual:
            # Prazo é por NC: no cartão do projeto, mostra só o mais próximo
            # entre as NCs abertas, notificadas e ainda não escalonadas.
            linha_prazo = db.execute(
                "SELECT MIN(prazo_limite) AS prazo FROM nao_conformidades "
                "WHERE auditoria_id = ? AND status = 'aberta' AND escalonado = 0 "
                "AND prazo_limite IS NOT NULL",
                (auditoria_atual["id"],),
            ).fetchone()
            proximo_prazo = linha_prazo["prazo"] if linha_prazo else None
            contagem_nc = db.execute(
                "SELECT "
                "SUM(CASE WHEN status = 'aberta' AND escalonado = 0 "
                "AND notificado_em IS NULL THEN 1 ELSE 0 END) AS abertas, "
                "SUM(CASE WHEN status = 'aberta' AND escalonado = 1 THEN 1 ELSE 0 END) AS escalonadas, "
                "SUM(CASE WHEN status = 'aberta' AND escalonado = 0 "
                "AND notificado_em IS NOT NULL AND prazo_limite >= ? THEN 1 ELSE 0 END) AS aguardando, "
                "SUM(CASE WHEN status = 'aberta' AND escalonado = 0 "
                "AND prazo_limite IS NOT NULL AND prazo_limite < ? THEN 1 ELSE 0 END) AS vencidos "
                "FROM nao_conformidades WHERE auditoria_id = ?",
                (agora, agora, auditoria_atual["id"]),
            ).fetchone()
            alertas = {chave: contagem_nc[chave] or 0 for chave in alertas}
        projetos_com_prazo.append(
            {
                "projeto": projeto,
                "auditoria": auditoria_atual,
                "proximo_prazo": proximo_prazo,
                "alertas": alertas,
            }
        )

    return render_template(
        "dashboard.html",
        projetos=projetos_com_prazo,
        status_opcoes=STATUS_VALIDOS,
        status_filtro=status_filtro,
        alerta_filtro=alerta_filtro,
        busca=busca,
        contagem_status=contagem_status,
        total_projetos=total_projetos,
    )


@bp.get("/novo")
def novo():
    return render_template("projeto_novo.html")


@bp.post("/")
def criar():
    db = get_db()
    nome = (request.form.get("nome") or "").strip()
    descricao = (request.form.get("descricao") or "").strip()
    responsavel_email = (request.form.get("responsavel_superior_email") or "").strip()

    nomes_participantes = request.form.getlist("participante_nome")
    emails_participantes = request.form.getlist("participante_email")

    if not nome or not responsavel_email:
        flash("Informe ao menos o nome do projeto e o e-mail do responsável.", "erro")
        return redirect(url_for("projetos.novo"))

    cursor = db.execute(
        "INSERT INTO projetos (nome, descricao, responsavel_superior_email) VALUES (?, ?, ?)",
        (nome, descricao, responsavel_email),
    )
    projeto_id = cursor.lastrowid

    incompletos = _inserir_participantes(db, projeto_id, nomes_participantes, emails_participantes)

    db.commit()
    if incompletos:
        flash(
            "Projeto criado, mas os integrantes " + ", ".join(f'"{i}"' for i in incompletos) +
            " não foram salvos: preencha nome e e-mail juntos.",
            "erro",
        )
    else:
        flash("Projeto criado com sucesso.", "ok")
    return redirect(url_for("projetos.detalhe", projeto_id=projeto_id))


@bp.get("/<int:projeto_id>/editar")
def editar(projeto_id):
    db = get_db()
    try:
        projeto = _buscar_projeto_ou_404(projeto_id)
    except LookupError:
        flash("Projeto não encontrado.", "erro")
        return redirect(url_for("projetos.listar"))

    participantes = db.execute(
        "SELECT * FROM participantes WHERE projeto_id = ? ORDER BY nome", (projeto_id,)
    ).fetchall()
    return render_template("projeto_editar.html", projeto=projeto, participantes=participantes)


@bp.post("/<int:projeto_id>/editar")
def atualizar(projeto_id):
    db = get_db()
    try:
        _buscar_projeto_ou_404(projeto_id)
    except LookupError:
        flash("Projeto não encontrado.", "erro")
        return redirect(url_for("projetos.listar"))

    nome = (request.form.get("nome") or "").strip()
    descricao = (request.form.get("descricao") or "").strip()
    responsavel_email = (request.form.get("responsavel_superior_email") or "").strip()

    if not nome or not responsavel_email:
        flash("Informe ao menos o nome do projeto e o e-mail do responsável.", "erro")
        return redirect(url_for("projetos.editar", projeto_id=projeto_id))

    db.execute(
        "UPDATE projetos SET nome = ?, descricao = ?, responsavel_superior_email = ? WHERE id = ?",
        (nome, descricao, responsavel_email, projeto_id),
    )

    nomes_participantes = request.form.getlist("participante_nome")
    emails_participantes = request.form.getlist("participante_email")
    incompletos = _inserir_participantes(db, projeto_id, nomes_participantes, emails_participantes)

    db.commit()
    if incompletos:
        flash(
            "Projeto atualizado, mas os integrantes " + ", ".join(f'"{i}"' for i in incompletos) +
            " não foram salvos: preencha nome e e-mail juntos.",
            "erro",
        )
    else:
        flash("Projeto atualizado com sucesso.", "ok")
    return redirect(url_for("projetos.detalhe", projeto_id=projeto_id))


@bp.post("/<int:projeto_id>/participantes/<int:participante_id>/editar")
def editar_participante(projeto_id, participante_id):
    db = get_db()
    nome = (request.form.get("nome") or "").strip()
    email = (request.form.get("email") or "").strip()
    if not nome or not email:
        flash("Informe nome e e-mail do integrante.", "erro")
        return redirect(request.referrer or url_for("projetos.editar", projeto_id=projeto_id))

    db.execute(
        "UPDATE participantes SET nome = ?, email = ? WHERE id = ? AND projeto_id = ?",
        (nome, email, participante_id, projeto_id),
    )
    db.commit()
    flash("Integrante atualizado.", "ok")
    return redirect(request.referrer or url_for("projetos.editar", projeto_id=projeto_id))


@bp.post("/<int:projeto_id>/participantes/<int:participante_id>/excluir")
def excluir_participante(projeto_id, participante_id):
    db = get_db()
    db.execute(
        "DELETE FROM participantes WHERE id = ? AND projeto_id = ?", (participante_id, projeto_id)
    )
    db.commit()
    flash("Integrante removido.", "ok")
    return redirect(request.referrer or url_for("projetos.editar", projeto_id=projeto_id))


@bp.post("/<int:projeto_id>/checklists")
def criar_checklist(projeto_id):
    db = get_db()
    try:
        _buscar_projeto_ou_404(projeto_id)
    except LookupError:
        flash("Projeto não encontrado.", "erro")
        return redirect(url_for("projetos.listar"))

    nome = (request.form.get("nome") or "").strip()
    if not nome:
        flash("Informe um nome para o checklist.", "erro")
        return redirect(url_for("projetos.detalhe", projeto_id=projeto_id))

    codigos = request.form.getlist("item_codigo")
    categorias = request.form.getlist("item_categoria")
    descricoes = request.form.getlist("item_descricao")

    cursor = db.execute(
        "INSERT INTO checklists (projeto_id, nome) VALUES (?, ?)", (projeto_id, nome)
    )
    checklist_id = cursor.lastrowid
    total_itens = _inserir_checklist_itens(db, checklist_id, codigos, categorias, descricoes)

    if total_itens == 0:
        db.execute("DELETE FROM checklists WHERE id = ?", (checklist_id,))
        db.commit()
        flash("Adicione ao menos um item com descrição para criar o checklist.", "erro")
        return redirect(url_for("projetos.detalhe", projeto_id=projeto_id))

    db.commit()
    flash(f'Checklist "{nome}" criado com {total_itens} {"item" if total_itens == 1 else "itens"}.', "ok")
    return redirect(url_for("projetos.detalhe", projeto_id=projeto_id))


@bp.post("/<int:projeto_id>/checklists/<int:checklist_id>/excluir")
def excluir_checklist(projeto_id, checklist_id):
    db = get_db()
    checklist = db.execute(
        "SELECT * FROM checklists WHERE id = ? AND projeto_id = ?", (checklist_id, projeto_id)
    ).fetchone()
    if checklist is None:
        flash("Checklist não encontrado.", "erro")
        return redirect(url_for("projetos.detalhe", projeto_id=projeto_id))

    db.execute("DELETE FROM checklists WHERE id = ?", (checklist_id,))
    db.commit()
    flash(f'Checklist "{checklist["nome"]}" removido.', "ok")
    return redirect(url_for("projetos.detalhe", projeto_id=projeto_id))


@bp.post("/<int:projeto_id>/documentos/<int:documento_id>/excluir")
def excluir_documento(projeto_id, documento_id):
    db = get_db()
    documento = db.execute(
        "SELECT * FROM documentos WHERE id = ? AND projeto_id = ?", (documento_id, projeto_id)
    ).fetchone()
    if documento is None:
        flash("Documento não encontrado.", "erro")
        return redirect(url_for("projetos.detalhe", projeto_id=projeto_id))

    caminho = Path(documento["caminho_arquivo"])
    caminho.unlink(missing_ok=True)
    db.execute("DELETE FROM documentos WHERE id = ?", (documento_id,))
    db.commit()
    flash(f"Documento \"{documento['nome_original']}\" removido.", "ok")
    return redirect(url_for("projetos.detalhe", projeto_id=projeto_id))


@bp.post("/<int:projeto_id>/excluir")
def excluir(projeto_id):
    db = get_db()
    try:
        projeto = _buscar_projeto_ou_404(projeto_id)
    except LookupError:
        flash("Projeto não encontrado.", "erro")
        return redirect(url_for("projetos.listar"))

    documentos = db.execute(
        "SELECT caminho_arquivo FROM documentos WHERE projeto_id = ?", (projeto_id,)
    ).fetchall()
    for documento in documentos:
        Path(documento["caminho_arquivo"]).unlink(missing_ok=True)

    db.execute("DELETE FROM projetos WHERE id = ?", (projeto_id,))
    db.commit()
    flash(f"Projeto \"{projeto['nome']}\" excluído.", "ok")
    return redirect(url_for("projetos.listar"))


@bp.get("/<int:projeto_id>")
def detalhe(projeto_id):
    db = get_db()
    try:
        projeto = _buscar_projeto_ou_404(projeto_id)
    except LookupError:
        flash("Projeto não encontrado.", "erro")
        return redirect(url_for("projetos.listar"))

    participantes = db.execute(
        "SELECT * FROM participantes WHERE projeto_id = ? ORDER BY nome", (projeto_id,)
    ).fetchall()
    documentos = db.execute(
        "SELECT * FROM documentos WHERE projeto_id = ? ORDER BY uploaded_at DESC", (projeto_id,)
    ).fetchall()
    versao_maxima = max((documento["versao"] for documento in documentos), default=0)
    auditorias = db.execute(
        "SELECT * FROM auditorias WHERE projeto_id = ? ORDER BY id DESC", (projeto_id,)
    ).fetchall()

    auditoria_atual = auditorias[0] if auditorias else None
    nao_conformidades = []
    if auditoria_atual:
        nao_conformidades = db.execute(
            "SELECT * FROM nao_conformidades WHERE auditoria_id = ? ORDER BY id",
            (auditoria_atual["id"],),
        ).fetchall()

    logs_emails = db.execute(
        "SELECT * FROM logs_emails WHERE projeto_id = ? ORDER BY id DESC", (projeto_id,)
    ).fetchall()

    checklists = db.execute(
        "SELECT checklists.*, COUNT(checklist_itens.id) AS total_itens "
        "FROM checklists LEFT JOIN checklist_itens ON checklist_itens.checklist_id = checklists.id "
        "WHERE checklists.projeto_id = ? GROUP BY checklists.id ORDER BY checklists.created_at DESC",
        (projeto_id,),
    ).fetchall()

    checklist_atual_nome = CHECKLIST_PADRAO_NOME
    if auditoria_atual and auditoria_atual["checklist_id"]:
        linha_checklist = db.execute(
            "SELECT nome FROM checklists WHERE id = ?", (auditoria_atual["checklist_id"],)
        ).fetchone()
        checklist_atual_nome = linha_checklist["nome"] if linha_checklist else "Checklist removido"

    resumo_nc = {"abertas": 0, "escalonadas": 0, "aguardando": 0, "vencidas": 0}
    agora = datetime.now().strftime(FORMATO_DATA)
    for nc in nao_conformidades:
        if nc["status"] != "aberta":
            continue
        if nc["escalonado"]:
            resumo_nc["escalonadas"] += 1
        elif nc["prazo_limite"] and nc["prazo_limite"] < agora:
            resumo_nc["vencidas"] += 1
        elif nc["notificado_em"] and nc["prazo_limite"]:
            resumo_nc["aguardando"] += 1
        else:
            resumo_nc["abertas"] += 1

    # E-mail e prazo são por NC (não um resumo da auditoria inteira): cada NC
    # aberta ganha o link "Redigir" já pronto para notificar o grupo (se tem
    # prazo definido) ou para escalonar ao responsável (se já foi marcada
    # como escalonada). Um corpo por NC também evita estourar o limite de
    # tamanho da URL do Gmail (o antigo resumo com várias NCs de uma vez
    # causava "Bad Request" ao abrir o link).
    destinatarios_grupo = [participante["email"] for participante in participantes]
    nc_links = {}
    agora = datetime.now().strftime(FORMATO_DATA)
    for nc in nao_conformidades:
        if nc["status"] != "aberta":
            continue
        links = {"vencida": bool(nc["prazo_limite"]) and nc["prazo_limite"] < agora}
        if nc["escalonado"]:
            links["escalonar"] = montar_link_gmail(
                [projeto["responsavel_superior_email"]],
                f"[Auditoria de Qualidade] Escalonamento - {projeto['nome']} - {nc['titulo']}",
                texto_escalonamento_nc(projeto, nc),
            )
        elif nc["prazo_limite"] and destinatarios_grupo:
            links["notificar"] = montar_link_gmail(
                destinatarios_grupo,
                f"[Auditoria de Qualidade] Não Conformidade encontrada - {projeto['nome']} - {nc['titulo']}",
                texto_notificacao_nc(projeto, nc, nc["prazo_limite"]),
            )
        nc_links[nc["id"]] = links

    prazos_abertos = [
        nc["prazo_limite"]
        for nc in nao_conformidades
        if nc["status"] == "aberta" and not nc["escalonado"] and nc["prazo_limite"]
    ]
    proximo_prazo = min(prazos_abertos) if prazos_abertos else None

    # Lista simples (nome + e-mail) pro JS montar os checkboxes de "enviar
    # para" no modal de e-mail, sem precisar de outra rota/requisição.
    participantes_json = [{"nome": p["nome"], "email": p["email"]} for p in participantes]

    return render_template(
        "projeto_detalhe.html",
        projeto=projeto,
        participantes=participantes,
        participantes_json=participantes_json,
        documentos=documentos,
        versao_maxima=versao_maxima,
        auditorias=auditorias,
        auditoria_atual=auditoria_atual,
        nao_conformidades=nao_conformidades,
        logs_emails=logs_emails,
        nc_links=nc_links,
        proximo_prazo=proximo_prazo,
        resumo_nc=resumo_nc,
        checklists=checklists,
        checklist_padrao_nome=CHECKLIST_PADRAO_NOME,
        checklist_atual_nome=checklist_atual_nome,
    )


@bp.post("/<int:projeto_id>/documentos")
def upload_documento(projeto_id):
    db = get_db()
    try:
        _buscar_projeto_ou_404(projeto_id)
    except LookupError:
        flash("Projeto não encontrado.", "erro")
        return redirect(url_for("projetos.listar"))

    # Cada envio é uma versão nova, numerada automaticamente (Documento 1,
    # Documento 2...) — o usuário não escolhe mais "inicial" ou "correção".
    versao_atual = db.execute(
        "SELECT COALESCE(MAX(versao), 0) AS maximo FROM documentos WHERE projeto_id = ?", (projeto_id,)
    ).fetchone()["maximo"]
    nova_versao = versao_atual + 1

    arquivos = request.files.getlist("documentos")
    pasta_projeto = config.UPLOAD_FOLDER / str(projeto_id)
    pasta_projeto.mkdir(parents=True, exist_ok=True)

    salvos = 0
    for arquivo in arquivos:
        if not arquivo or not arquivo.filename:
            continue
        extensao = Path(arquivo.filename).suffix.lower()
        if extensao not in config.EXTENSOES_PERMITIDAS:
            flash(f"Formato não suportado: {arquivo.filename}", "erro")
            continue

        nome_seguro = secure_filename(arquivo.filename)
        caminho_destino = pasta_projeto / nome_seguro
        # Evita sobrescrever arquivo existente com o mesmo nome.
        contador = 1
        while caminho_destino.exists():
            caminho_destino = pasta_projeto / f"{caminho_destino.stem}_{contador}{extensao}"
            contador += 1

        arquivo.save(str(caminho_destino))
        db.execute(
            "INSERT INTO documentos (projeto_id, nome_original, caminho_arquivo, versao) "
            "VALUES (?, ?, ?, ?)",
            (projeto_id, arquivo.filename, str(caminho_destino), nova_versao),
        )
        salvos += 1

    db.commit()
    if salvos:
        flash(f"{salvos} documento(s) enviado(s) como Documento {nova_versao}.", "ok")
    else:
        flash("Nenhum documento válido foi enviado.", "erro")
    return redirect(url_for("projetos.detalhe", projeto_id=projeto_id))


@bp.post("/<int:projeto_id>/auditorias")
def rodar_auditoria(projeto_id):
    db = get_db()
    try:
        _buscar_projeto_ou_404(projeto_id)
    except LookupError:
        flash("Projeto não encontrado.", "erro")
        return redirect(url_for("projetos.listar"))

    # Sempre roda sobre a versão mais recente enviada — sem selecionar tipo.
    documentos = db.execute(
        "SELECT * FROM documentos WHERE projeto_id = ? "
        "AND versao = (SELECT COALESCE(MAX(versao), 0) FROM documentos WHERE projeto_id = ?) "
        "ORDER BY uploaded_at",
        (projeto_id, projeto_id),
    ).fetchall()

    if not documentos:
        flash("Envie ao menos um documento antes de rodar a auditoria por IA.", "erro")
        return redirect(url_for("projetos.detalhe", projeto_id=projeto_id))

    # Checklist da auditoria: o padrão da disciplina (sem seleção ou "padrao")
    # ou um checklist próprio do projeto, criado do zero pelo usuário.
    checklist_id_form = (request.form.get("checklist_id") or "").strip()
    checklist_id = None
    criterios = None
    if checklist_id_form and checklist_id_form != "padrao":
        checklist = db.execute(
            "SELECT * FROM checklists WHERE id = ? AND projeto_id = ?",
            (checklist_id_form, projeto_id),
        ).fetchone()
        if checklist is None:
            flash("Checklist selecionado não foi encontrado.", "erro")
            return redirect(url_for("projetos.detalhe", projeto_id=projeto_id))

        itens_checklist = db.execute(
            "SELECT * FROM checklist_itens WHERE checklist_id = ? ORDER BY ordem, id",
            (checklist["id"],),
        ).fetchall()
        criterios = [
            {
                "codigo": item["codigo"],
                "categoria": item["categoria"] or "",
                "descricao": item["descricao"],
            }
            for item in itens_checklist
        ]
        checklist_id = checklist["id"]

    caminhos = [documento["caminho_arquivo"] for documento in documentos]

    try:
        resultado = auditar_projeto(caminhos, criterios)
    except Exception as erro:
        flash(f"Não foi possível concluir a avaliação por IA: {erro}", "erro")
        return redirect(url_for("projetos.detalhe", projeto_id=projeto_id))

    cursor = db.execute(
        "INSERT INTO auditorias (projeto_id, checklist_id, aderencia, status) VALUES (?, ?, ?, 'em_revisao')",
        (projeto_id, checklist_id, resultado["aderencia"]),
    )
    auditoria_id = cursor.lastrowid

    for nc in resultado["nao_conformidades"]:
        db.execute(
            "INSERT INTO nao_conformidades "
            "(auditoria_id, item_checklist, titulo, descricao_erro, evidencia, impacto, "
            "acao_corretiva, origem, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'ia', 'aberta')",
            (
                auditoria_id,
                nc["codigo"],
                nc.get("titulo") or nc["descricao"],
                nc["descricao"],
                nc.get("evidencia"),
                nc.get("impacto"),
                nc.get("acao_corretiva"),
            ),
        )

    db.execute("UPDATE projetos SET status = 'Em Auditoria' WHERE id = ?", (projeto_id,))
    db.commit()

    flash(
        f"Auditoria por IA concluída: {resultado['aderencia']}% de aderência, "
        f"{len(resultado['nao_conformidades'])} NC(s) encontrada(s). Revise antes de notificar o grupo.",
        "ok",
    )
    return redirect(url_for("projetos.detalhe", projeto_id=projeto_id))

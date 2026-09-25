# Aplicação Flask: ferramenta rápida de auditoria (legado) + Painel do
# Auditor de Processos de Qualidade (QA Audit Manager).
import os

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

load_dotenv()

import config
import database
from auditoria import CRITERIOS, NOME, auditar
from routes import registrar_blueprints

# Mapeia o status (livre, em português) para uma classe CSS previsível.
_STATUS_CSS = {
    "Em Auditoria": "status-em-auditoria",
    "Aguardando Correção": "status-aguardando-correcao",
    "Escalonado / Prazo Vencido": "status-escalonado",
    "Encerrado": "status-encerrado",
}

# Rótulo com ícone pro status do projeto — mais fácil de reconhecer de
# relance numa lista do que o texto puro, sem mudar o valor guardado no banco
# (usado em filtros/URLs).
_STATUS_ICONE = {
    "Em Auditoria": "🔎",
    "Aguardando Correção": "🕒",
    "Escalonado / Prazo Vencido": "🚨",
    "Encerrado": "✅",
}
_STATUS_LABEL = {
    "Em Auditoria": "Em auditoria",
    "Aguardando Correção": "Aguardando correção",
    "Escalonado / Prazo Vencido": "Escalonado",
    "Encerrado": "Encerrado",
}

# auditoria.status/logs_emails.tipo ficam em snake_case no banco; aqui viram
# rótulo legível + classe de badge, para não vazar nome de coluna pra tela.
_AUDITORIA_STATUS_LABEL = {
    "em_revisao": "Em revisão",
    "aguardando_correcao": "Aguardando correção",
    "escalonado": "Escalonado",
    "encerrada": "Encerrada",
}
_AUDITORIA_STATUS_CSS = {
    "em_revisao": "status-em-auditoria",
    "aguardando_correcao": "status-aguardando-correcao",
    "escalonado": "status-escalonado",
    "encerrada": "status-encerrado",
}
_LOG_TIPO_LABEL = {
    "correcao": "Notificação de correção",
    "escalonamento": "Escalonamento",
    "fechamento": "Fechamento",
}


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

    database.init_app(app)
    registrar_blueprints(app)

    @app.template_filter("status_css")
    def status_css(status):
        return _STATUS_CSS.get(status, "status-em-auditoria")

    @app.template_filter("status_com_icone")
    def status_com_icone(status):
        icone = _STATUS_ICONE.get(status)
        label = _STATUS_LABEL.get(status, status)
        return f"{icone} {label}" if icone else label

    @app.template_filter("iso_datetime")
    def iso_datetime(valor):
        # SQLite guarda "YYYY-MM-DD HH:MM:SS"; o JS precisa do "T" para um
        # parse confiável de data local em todos os navegadores.
        return valor.replace(" ", "T") if valor else ""

    @app.template_filter("formatar_data")
    def formatar_data(valor):
        # Converte "YYYY-MM-DD HH:MM:SS" → "DD/MM/YYYY às HH:MM" para exibição.
        if not valor:
            return ""
        try:
            from datetime import datetime
            dt = datetime.strptime(str(valor)[:19], "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%d/%m/%Y às %H:%M")
        except (ValueError, TypeError):
            return str(valor)

    @app.template_filter("auditoria_status_label")
    def auditoria_status_label(status):
        return _AUDITORIA_STATUS_LABEL.get(status, status)

    @app.template_filter("auditoria_status_css")
    def auditoria_status_css(status):
        return _AUDITORIA_STATUS_CSS.get(status, "status-em-auditoria")

    # Checklist da disciplina nos templates: badge "U11" em cada NC (com a
    # pergunta no tooltip) e <select> de item nos formulários de NC.
    app.jinja_env.globals["criterios"] = CRITERIOS
    app.jinja_env.globals["criterios_por_codigo"] = {c["codigo"]: c for c in CRITERIOS}

    @app.template_filter("log_tipo_label")
    def log_tipo_label(tipo):
        return _LOG_TIPO_LABEL.get(tipo, tipo)

    # A raiz do site abre direto no Painel do Auditor (dashboard de projetos).
    @app.route("/")
    def index():
        return redirect(url_for("projetos.listar"))

    # Ferramenta rápida (legado): audita um único PDF avulso, sem salvar nada.
    # Fica escondida atrás de um link secundário, fora do fluxo principal.
    @app.route("/ferramenta-rapida")
    def ferramenta_rapida():
        return render_template("index.html", nome=NOME, criterios=CRITERIOS)

    @app.route("/ferramenta-rapida/auditar", methods=["POST"])
    def auditar_documento():
        arquivo = request.files.get("documento")
        if not arquivo or not (arquivo.filename or "").lower().endswith(".pdf"):
            flash("Selecione um arquivo no formato PDF.", "erro")
            return redirect(url_for("ferramenta_rapida"))

        try:
            resultado = auditar(arquivo.stream, arquivo.filename)
        except Exception as erro:
            flash(f"Não foi possível concluir a auditoria: {erro}", "erro")
            return redirect(url_for("ferramenta_rapida"))

        return render_template("resultado.html", resultado=resultado)

    # Só inicia a rotina agendada de verificação de prazos no processo principal
    # (evita duplicar o scheduler quando o reloader do Flask sobe 2 processos).
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        from services.scheduler import iniciar_scheduler

        iniciar_scheduler()

    return app


app = create_app()

if __name__ == "__main__":
    # Em produção o ideal é gunicorn (ver Procfile/railway.json), mas se
    # algum builder rodar "python app.py" direto mesmo assim (foi o caso na
    # Railway com o Railpack ignorando o Procfile), isto ainda funciona:
    # escuta em todas as interfaces (0.0.0.0, não só localhost — senão o
    # proxy da hospedagem não alcança o processo) na porta que a plataforma
    # definir via $PORT. Debug fica ligado só localmente (sem $PORT definido);
    # hospedagens como a Railway sempre definem $PORT, então lá já desliga
    # sozinho — sem precisar configurar nada a mais.
    modo_debug = os.environ.get("FLASK_DEBUG") == "1" or "PORT" not in os.environ
    porta = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=porta, debug=modo_debug)

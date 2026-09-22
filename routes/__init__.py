# Registra os blueprints do Painel do Auditor de Processos de Qualidade.
from .auditorias import bp as auditorias_bp
from .nc import bp as nc_bp
from .projetos import bp as projetos_bp


def registrar_blueprints(app):
    app.register_blueprint(projetos_bp)
    app.register_blueprint(auditorias_bp)
    app.register_blueprint(nc_bp)

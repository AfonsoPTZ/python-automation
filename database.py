# Conexão SQLite (via stdlib sqlite3) e inicialização do schema.
import sqlite3

import click
from flask import g

import config


def get_db():
    if "db" not in g:
        config.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(str(config.DATABASE_PATH), detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# Colunas adicionadas depois da primeira versão do schema. `CREATE TABLE IF
# NOT EXISTS` não altera tabelas já existentes, então quem já tinha o banco
# criado precisa dessas colunas adicionadas manualmente aqui, sem perder dados.
_MIGRACOES = [
    ("nao_conformidades", "prazo_limite", "TEXT"),
    ("nao_conformidades", "escalonado", "INTEGER NOT NULL DEFAULT 0"),
    ("documentos", "versao", "INTEGER NOT NULL DEFAULT 1"),
    ("nao_conformidades", "notificado_em", "TEXT"),
    ("auditorias", "checklist_id", "INTEGER REFERENCES checklists(id) ON DELETE SET NULL"),
    ("auditorias", "encerrada_em", "TEXT"),
    ("auditorias", "relatorio_ia", "TEXT"),
    ("auditorias", "relatorio_gerado_em", "TEXT"),
]


def _aplicar_migracoes(db):
    for tabela, coluna, tipo in _MIGRACOES:
        colunas_existentes = {linha["name"] for linha in db.execute(f"PRAGMA table_info({tabela})")}
        if coluna not in colunas_existentes:
            db.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
    db.commit()


def _criar_tabelas(db):
    # CREATE TABLE/INDEX IF NOT EXISTS: seguro rodar de novo em bancos que já
    # existiam antes de uma tabela nova (ex.: checklists) ser adicionada aqui.
    with open(config.BASE_DIR / "schema.sql", "r", encoding="utf-8") as arquivo:
        db.executescript(arquivo.read())


def init_db():
    config.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(config.DATABASE_PATH))
    db.row_factory = sqlite3.Row
    _criar_tabelas(db)
    _aplicar_migracoes(db)
    db.close()


@click.command("init-db")
def init_db_command():
    """Cria/atualiza as tabelas do banco de dados SQLite."""
    init_db()
    click.echo(f"Banco de dados inicializado em {config.DATABASE_PATH}")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    # Garante que o schema exista mesmo em ambientes onde `flask init-db`
    # não foi executado manualmente (ex.: primeira execução com `py app.py`).
    if not config.DATABASE_PATH.exists():
        init_db()
    else:
        # Banco já existia de uma versão anterior do schema: cria só as
        # tabelas/colunas novas (tudo com IF NOT EXISTS), sem perder dados.
        db = sqlite3.connect(str(config.DATABASE_PATH))
        db.row_factory = sqlite3.Row
        _criar_tabelas(db)
        _aplicar_migracoes(db)
        db.close()

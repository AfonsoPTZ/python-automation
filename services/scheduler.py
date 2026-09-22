# Rotina agendada (node-cron equivalente) que verifica prazos de NCs vencidos
# e marca a NC como escalonada. O sistema não envia e-mail sozinho: ele só
# deixa o escalonamento pronto para o auditor abrir o link do Gmail (já
# preenchido) na tela do projeto e enviar com um clique.
import sqlite3
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

import config
from database import init_db


def _conectar():
    config.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(str(config.DATABASE_PATH))
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


# Escalona uma NC: marca como escalonada e atualiza o status do projeto. O
# link do Gmail para o e-mail de escalonamento fica disponível na tela do
# projeto assim que o auditor abrir — ele que clica em enviar.
def _escalonar_nc(db, nc, projeto_id, responsavel_email):
    db.execute("UPDATE nao_conformidades SET escalonado = 1 WHERE id = ?", (nc["id"],))
    db.execute(
        "UPDATE projetos SET status = 'Escalonado / Prazo Vencido' WHERE id = ?",
        (projeto_id,),
    )
    db.execute(
        "INSERT INTO logs_emails (projeto_id, tipo, destinatarios, corpo_resumido) "
        "VALUES (?, 'escalonamento', ?, ?)",
        (
            projeto_id,
            responsavel_email,
            f'Escalonamento automático (prazo vencido) da NC "{nc["titulo"]}". '
            "E-mail preparado para envio pelo Gmail.",
        ),
    )
    db.commit()


# Verifica todas as NCs abertas, notificadas e com prazo vencido, ainda não
# escalonadas, e escalona cada uma delas.
def verificar_prazos_vencidos():
    db = _conectar()
    try:
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        vencidas = db.execute(
            "SELECT nao_conformidades.*, auditorias.projeto_id AS projeto_id "
            "FROM nao_conformidades "
            "JOIN auditorias ON auditorias.id = nao_conformidades.auditoria_id "
            "WHERE nao_conformidades.status = 'aberta' AND nao_conformidades.escalonado = 0 "
            "AND nao_conformidades.prazo_limite IS NOT NULL AND nao_conformidades.prazo_limite < ?",
            (agora,),
        ).fetchall()

        for nc in vencidas:
            projeto = db.execute(
                "SELECT * FROM projetos WHERE id = ?", (nc["projeto_id"],)
            ).fetchone()
            if projeto:
                _escalonar_nc(db, nc, projeto["id"], projeto["responsavel_superior_email"])
    finally:
        db.close()


def iniciar_scheduler():
    if not config.DATABASE_PATH.exists():
        init_db()

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        verificar_prazos_vencidos,
        "interval",
        minutes=config.SLA_CHECK_INTERVAL_MINUTOS,
        id="verificar_prazos_vencidos",
        next_run_time=datetime.now(),
    )
    scheduler.start()
    return scheduler

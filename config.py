# Configuração da aplicação, lida a partir de variáveis de ambiente (.env).
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "data" / "qa_audit.db"))
UPLOAD_FOLDER = Path(os.environ.get("UPLOAD_FOLDER", BASE_DIR / "uploads"))

SECRET_KEY = os.environ.get("SECRET_KEY", "auditoria-qualidade-academico")

# Extensões aceitas para upload de documentos do grupo auditado.
EXTENSOES_PERMITIDAS = {".pdf", ".docx", ".xlsx", ".txt"}
MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32 MB por upload

# Rotina de verificação de prazos vencidos (node-cron equivalente).
SLA_CHECK_INTERVAL_MINUTOS = int(os.environ.get("SLA_CHECK_INTERVAL_MINUTOS", "60"))


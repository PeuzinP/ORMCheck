import json
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _path_from_env(nome_variavel: str, padrao: Path):
    valor = os.getenv(nome_variavel, "").strip()

    if not valor:
        return padrao

    caminho = Path(valor)

    if not caminho.is_absolute():
        caminho = BASE_DIR / caminho

    return caminho


def _json_dict_from_env(nome_variavel: str) -> dict:
    valor = os.getenv(nome_variavel, "").strip()

    if not valor:
        return {}

    try:
        carregado = json.loads(valor)
    except json.JSONDecodeError:
        return {}

    return carregado if isinstance(carregado, dict) else {}


APP_DATA_DIR = _path_from_env("APP_DATA_DIR", BASE_DIR)
APP_ENV = os.getenv("APP_ENV", "production").strip().lower() or "production"
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "America/Sao_Paulo").strip() or "America/Sao_Paulo"

PASTA_PROCESSAMENTOS = _path_from_env(
    "APP_PROCESSAMENTOS_DIR",
    APP_DATA_DIR / "processamentos"
)
PASTA_UPLOADS_TEMP = _path_from_env(
    "APP_UPLOADS_TEMP_DIR",
    APP_DATA_DIR / "uploads_temp"
)
PASTA_RUNTIME = _path_from_env(
    "APP_RUNTIME_DIR",
    APP_DATA_DIR / "runtime"
)
PASTA_LOGS = _path_from_env(
    "APP_LOG_DIR",
    APP_DATA_DIR / "logs"
)
PASTA_BACKUPS = _path_from_env(
    "APP_BACKUP_DIR",
    APP_DATA_DIR / "backups"
)
PASTA_TEMPLATES_OMR = _path_from_env("APP_TEMPLATES_OMR_DIR", BASE_DIR / "templates_omr")
PASTA_BASE = _path_from_env("APP_BASE_DIR", BASE_DIR / "base")
PASTA_ASSETS = _path_from_env("APP_ASSETS_DIR", BASE_DIR / "assets")

CAMINHO_MODELO_CARTAO = PASTA_TEMPLATES_OMR / "modelo_cartao.xtmpl"
CAMINHO_BASE_ALUNOS = PASTA_BASE / "alunos.csv"
CAMINHO_ICONE = PASTA_ASSETS / "omrcheck.ico"
CAMINHO_JOBS = PASTA_RUNTIME / "jobs.json"
CAMINHO_LOG_APP = PASTA_LOGS / f"omrcheck-{APP_ENV}.log"

KEEPEDU_BUSCAR_ID_URL = os.getenv(
    "KEEPEDU_BUSCAR_ID_URL",
    "https://develop.keepedu.com.br/api/customers/buscar-id-aluno"
)

KEEPEDU_API_KEY = os.getenv("KEEPEDU_API_KEY", "")

KEEPEDU_INSTITUTE = os.getenv(
    "KEEPEDU_INSTITUTE",
    ""
)
ID_PROVA_KEEPEDU = os.getenv("ID_PROVA_KEEPEDU", "")
KEEPEDU_IMPORTAR_RESPOSTAS_URL = os.getenv(
    "KEEPEDU_IMPORTAR_RESPOSTAS_URL",
    "http://localhost/github-app/keepedu/api/avaliacoes/importar-respostas-presenciais"
).strip()
KEEPEDU_SIMULAR_IMPORTAR_RESPOSTAS_URL = os.getenv(
    "KEEPEDU_SIMULAR_IMPORTAR_RESPOSTAS_URL",
    ""
).strip()
KEEPEDU_IMPORTAR_DIA_AVAL = os.getenv("KEEPEDU_IMPORTAR_DIA_AVAL", "1").strip() or "1"
KEEPEDU_IMPORTAR_USUARIO_ID = int(os.getenv("KEEPEDU_IMPORTAR_USUARIO_ID", "0"))
KEEPEDU_IMPORTAR_TIMEOUT_SECONDS = max(
    1,
    int(os.getenv("KEEPEDU_IMPORTAR_TIMEOUT_SECONDS", "30"))
)
BERNOULLI_USUARIOS_URL = os.getenv(
    "BERNOULLI_USUARIOS_URL",
    "http://api.bernoulli.com.br/api/gerenciar/acessos/usuarios/listar"
).strip()
BERNOULLI_AUTHORIZATION = os.getenv("BERNOULLI_AUTHORIZATION", "").strip()
BERNOULLI_COOKIE = os.getenv("BERNOULLI_COOKIE", "").strip()
BERNOULLI_PAGE_SIZE = max(1, int(os.getenv("BERNOULLI_PAGE_SIZE", "10")))
BERNOULLI_GRUPO_USUARIO = os.getenv("BERNOULLI_GRUPO_USUARIO", "5").strip() or "5"
BERNOULLI_FRONT_VERSION = os.getenv("BERNOULLI_FRONT_VERSION", "4.25.72").strip()
BERNOULLI_PLATAFORMA = os.getenv("BERNOULLI_PLATAFORMA", "2").strip()
BERNOULLI_ORIGIN = os.getenv("BERNOULLI_ORIGIN", "https://mb4.bernoulli.com.br").strip()
BERNOULLI_REFERER = os.getenv("BERNOULLI_REFERER", "https://mb4.bernoulli.com.br/").strip()
BERNOULLI_LOGIN_URL = os.getenv("BERNOULLI_LOGIN_URL", "").strip()
BERNOULLI_LOGIN_METHOD = os.getenv("BERNOULLI_LOGIN_METHOD", "POST").strip().upper() or "POST"
BERNOULLI_LOGIN_USERNAME = os.getenv("BERNOULLI_LOGIN_USERNAME", "").strip()
BERNOULLI_LOGIN_PASSWORD = os.getenv("BERNOULLI_LOGIN_PASSWORD", "").strip()
BERNOULLI_LOGIN_USERNAME_FIELD = os.getenv("BERNOULLI_LOGIN_USERNAME_FIELD", "usuario").strip() or "usuario"
BERNOULLI_LOGIN_PASSWORD_FIELD = os.getenv("BERNOULLI_LOGIN_PASSWORD_FIELD", "senha").strip() or "senha"
BERNOULLI_LOGIN_USE_FORM = os.getenv("BERNOULLI_LOGIN_USE_FORM", "false").strip().lower() in {
    "1", "true", "yes", "on"
}
BERNOULLI_LOGIN_EXTRA_PAYLOAD = _json_dict_from_env("BERNOULLI_LOGIN_EXTRA_PAYLOAD")
BERNOULLI_LOGIN_HEADERS = _json_dict_from_env("BERNOULLI_LOGIN_HEADERS")
BERNOULLI_LOGIN_TOKEN_PATH = os.getenv("BERNOULLI_LOGIN_TOKEN_PATH", "token").strip() or "token"
BERNOULLI_LOGIN_COOKIE_NAMES = [
    item.strip()
    for item in os.getenv("BERNOULLI_LOGIN_COOKIE_NAMES", "").split(",")
    if item.strip()
]
BERNOULLI_PARAMETROS_URL = os.getenv(
    "BERNOULLI_PARAMETROS_URL",
    "https://api.bernoulli.com.br/api/autenticado/parametros"
).strip()
BERNOULLI_PARAMETROS_METHOD = os.getenv("BERNOULLI_PARAMETROS_METHOD", "POST").strip().upper() or "POST"
BERNOULLI_PARAMETROS_USE_FORM = os.getenv("BERNOULLI_PARAMETROS_USE_FORM", "false").strip().lower() in {
    "1", "true", "yes", "on"
}
BERNOULLI_PARAMETROS_PAYLOAD = _json_dict_from_env("BERNOULLI_PARAMETROS_PAYLOAD")
BERNOULLI_PARAMETROS_HEADERS = _json_dict_from_env("BERNOULLI_PARAMETROS_HEADERS")
BERNOULLI_PARAMETROS_TOKEN_PATH = os.getenv(
    "BERNOULLI_PARAMETROS_TOKEN_PATH",
    "access_token"
).strip() or "access_token"
BERNOULLI_AUTH_HEADER_PREFIX = os.getenv("BERNOULLI_AUTH_HEADER_PREFIX", "Bearer").strip() or "Bearer"
BERNOULLI_AUTH_REFRESH_MARGIN_SECONDS = max(
    0,
    int(os.getenv("BERNOULLI_AUTH_REFRESH_MARGIN_SECONDS", "300"))
)
BERNOULLI_AUTH_CACHE_FILE = _path_from_env(
    "BERNOULLI_AUTH_CACHE_FILE",
    PASTA_RUNTIME / "bernoulli_auth.json"
)

APP_ENABLE_AUTH = os.getenv("APP_ENABLE_AUTH", "false").strip().lower() in {
    "1", "true", "yes", "on"
}
APP_BASIC_AUTH_USER = os.getenv("APP_BASIC_AUTH_USER", "").strip()
APP_BASIC_AUTH_PASSWORD = os.getenv("APP_BASIC_AUTH_PASSWORD", "").strip()
APP_ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("APP_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

MAX_UPLOAD_FILES = int(os.getenv("MAX_UPLOAD_FILES", "300"))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "15"))
MAX_TOTAL_UPLOAD_SIZE_MB = int(os.getenv("MAX_TOTAL_UPLOAD_SIZE_MB", "512"))
APP_LOG_LEVEL = os.getenv("APP_LOG_LEVEL", "INFO").strip().upper()
APP_RETENTION_DAYS = max(1, int(os.getenv("APP_RETENTION_DAYS", "45")))
APP_UPLOAD_TEMP_RETENTION_HOURS = max(
    1,
    int(os.getenv("APP_UPLOAD_TEMP_RETENTION_HOURS", "24"))
)
APP_BACKUP_ENABLED = os.getenv("APP_BACKUP_ENABLED", "true").strip().lower() in {
    "1", "true", "yes", "on"
}

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))


def garantir_pastas():
    PASTA_PROCESSAMENTOS.mkdir(parents=True, exist_ok=True)
    PASTA_UPLOADS_TEMP.mkdir(parents=True, exist_ok=True)
    PASTA_RUNTIME.mkdir(parents=True, exist_ok=True)
    PASTA_LOGS.mkdir(parents=True, exist_ok=True)
    PASTA_BACKUPS.mkdir(parents=True, exist_ok=True)
    PASTA_TEMPLATES_OMR.mkdir(parents=True, exist_ok=True)
    PASTA_BASE.mkdir(parents=True, exist_ok=True)
    PASTA_ASSETS.mkdir(parents=True, exist_ok=True)

    if not CAMINHO_JOBS.exists():
        CAMINHO_JOBS.write_text("{}", encoding="utf-8")

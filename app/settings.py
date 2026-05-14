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


APP_DATA_DIR = _path_from_env("APP_DATA_DIR", BASE_DIR)

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
PASTA_TEMPLATES_OMR = _path_from_env("APP_TEMPLATES_OMR_DIR", BASE_DIR / "templates_omr")
PASTA_BASE = _path_from_env("APP_BASE_DIR", BASE_DIR / "base")
PASTA_ASSETS = _path_from_env("APP_ASSETS_DIR", BASE_DIR / "assets")

CAMINHO_MODELO_CARTAO = PASTA_TEMPLATES_OMR / "modelo_cartao.xtmpl"
CAMINHO_BASE_ALUNOS = PASTA_BASE / "alunos.csv"
CAMINHO_ICONE = PASTA_ASSETS / "omrcheck.ico"
CAMINHO_JOBS = PASTA_RUNTIME / "jobs.json"

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

MAX_UPLOAD_FILES = int(os.getenv("MAX_UPLOAD_FILES", "300"))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "15"))
MAX_TOTAL_UPLOAD_SIZE_MB = int(os.getenv("MAX_TOTAL_UPLOAD_SIZE_MB", "512"))

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))


def garantir_pastas():
    PASTA_PROCESSAMENTOS.mkdir(exist_ok=True)
    PASTA_UPLOADS_TEMP.mkdir(exist_ok=True)
    PASTA_RUNTIME.mkdir(exist_ok=True)
    PASTA_TEMPLATES_OMR.mkdir(exist_ok=True)
    PASTA_BASE.mkdir(exist_ok=True)
    PASTA_ASSETS.mkdir(exist_ok=True)

    if not CAMINHO_JOBS.exists():
        CAMINHO_JOBS.write_text("{}", encoding="utf-8")

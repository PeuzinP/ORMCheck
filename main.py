import base64
import logging
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.routes import router
from app.logging_config import setup_logging
from app.settings import (
    APP_ALLOWED_HOSTS,
    APP_BASIC_AUTH_PASSWORD,
    APP_BASIC_AUTH_USER,
    APP_BACKUP_ENABLED,
    APP_ENV,
    APP_ENABLE_AUTH,
    BASE_DIR,
    CAMINHO_MODELO_CARTAO,
    CAMINHO_JOBS,
    KEEPEDU_API_KEY,
    PASTA_BACKUPS,
    PASTA_LOGS,
    garantir_pastas
)


garantir_pastas()
setup_logging()
logger = logging.getLogger("omrcheck.main")

app = FastAPI(title="OMRCheck Web")

app.add_middleware(GZipMiddleware, minimum_size=1024)

if APP_ALLOWED_HOSTS:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=APP_ALLOWED_HOSTS)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "web" / "static")),
    name="static"
)

app.mount(
    "/assets",
    StaticFiles(directory=str(BASE_DIR / "assets")),
    name="assets"
)

app.state.templates = Jinja2Templates(
    directory=str(BASE_DIR / "web" / "templates")
)


@app.middleware("http")
async def autenticacao_basica(request: Request, call_next):
    if (
        not APP_ENABLE_AUTH
        or request.url.path == "/healthz"
    ):
        return await call_next(request)

    header = request.headers.get("Authorization", "")

    if header.startswith("Basic "):
        try:
            credenciais = base64.b64decode(header[6:]).decode("utf-8")
            usuario, senha = credenciais.split(":", 1)
        except Exception:
            usuario = ""
            senha = ""

        if (
            APP_BASIC_AUTH_USER
            and APP_BASIC_AUTH_PASSWORD
            and secrets.compare_digest(usuario, APP_BASIC_AUTH_USER)
            and secrets.compare_digest(senha, APP_BASIC_AUTH_PASSWORD)
        ):
            return await call_next(request)

    return PlainTextResponse(
        "Autenticacao obrigatoria.",
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="OMRCheck Web"'}
    )


@app.middleware("http")
async def adicionar_headers_de_seguranca(request: Request, call_next):
    resposta = await call_next(request)
    resposta.headers.setdefault("X-Frame-Options", "DENY")
    resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
    resposta.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resposta.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()"
    )
    return resposta


@app.get("/healthz")
async def healthcheck():
    return {
        "status": "ok",
        "app_env": APP_ENV,
        "auth_enabled": APP_ENABLE_AUTH,
        "modelo_cartao_existe": CAMINHO_MODELO_CARTAO.exists(),
        "keepedu_api_configurada": bool(str(KEEPEDU_API_KEY).strip()),
        "jobs_store_existe": CAMINHO_JOBS.exists(),
        "logs_dir": str(PASTA_LOGS),
        "backups_dir": str(PASTA_BACKUPS),
        "backup_enabled": APP_BACKUP_ENABLED
    }


@app.on_event("startup")
async def registrar_inicio():
    logger.info(
        "Aplicacao iniciada | env=%s | auth=%s | jobs=%s",
        APP_ENV,
        APP_ENABLE_AUTH,
        CAMINHO_JOBS
    )


app.include_router(router)

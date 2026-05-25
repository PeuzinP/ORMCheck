import logging
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.db import init_db, storage_usa_banco
from app.routes import router
from app.logging_config import setup_logging
from app.settings import (
    APP_ALLOWED_HOSTS,
    APP_BACKUP_ENABLED,
    APP_ENV,
    APP_ENABLE_AUTH,
    APP_SESSION_COOKIE_NAME,
    APP_SESSION_SECRET,
    APP_STORAGE_BACKEND,
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


class AutenticacaoWebMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if (
            not APP_ENABLE_AUTH
            or request.url.path == "/healthz"
            or request.url.path == "/login"
            or request.url.path == "/logout"
            or request.url.path == "/favicon.ico"
            or request.url.path.startswith("/static/")
            or request.url.path.startswith("/assets/")
        ):
            return await call_next(request)

        sessao = request.scope.get("session") or {}
        if bool(sessao.get("authenticated")):
            return await call_next(request)

        aceita_json = "application/json" in str(request.headers.get("accept", "")).lower()
        destino = str(request.url.path or "/")
        if request.url.query:
            destino = f"{destino}?{request.url.query}"

        if aceita_json or request.url.path.startswith("/status-") or request.method.upper() != "GET":
            return JSONResponse(
                {
                    "status": "erro",
                    "mensagem": "Autenticação obrigatória. Faça login novamente.",
                    "redirect": f"/login?next={quote(destino, safe='/=?&')}",
                },
                status_code=401,
            )

        return RedirectResponse(url=f"/login?next={quote(destino, safe='/=?&')}", status_code=303)


app = FastAPI(title="OMRCheck Web")

app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(AutenticacaoWebMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=APP_SESSION_SECRET,
    session_cookie=APP_SESSION_COOKIE_NAME,
    same_site="lax",
    https_only=False,
)

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
        "storage_backend": APP_STORAGE_BACKEND,
        "auth_enabled": APP_ENABLE_AUTH,
        "modelo_cartao_existe": CAMINHO_MODELO_CARTAO.exists(),
        "keepedu_api_configurada": bool(str(KEEPEDU_API_KEY).strip()),
        "jobs_store_existe": storage_usa_banco() or CAMINHO_JOBS.exists(),
        "logs_dir": str(PASTA_LOGS),
        "backups_dir": str(PASTA_BACKUPS),
        "backup_enabled": APP_BACKUP_ENABLED
    }


@app.on_event("startup")
async def registrar_inicio():
    init_db()
    logger.info(
        "Aplicacao iniciada | env=%s | auth=%s | storage=%s | jobs=%s",
        APP_ENV,
        APP_ENABLE_AUTH,
        APP_STORAGE_BACKEND,
        CAMINHO_JOBS
    )


app.include_router(router)

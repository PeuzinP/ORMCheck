import logging
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse
from app.auth import obter_sessao_usuario
from starlette.middleware.base import BaseHTTPMiddleware



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


from fastapi import FastAPI, Request
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import RedirectResponse

# GZIP
class AutenticacaoMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):

        caminho = request.url.path

        if caminho != "/":
            caminho = caminho.rstrip("/")

        rotas_livres = {
            "/",
            "/login",
            "/logout",
            "/healthz",
            "/favicon.ico"
        }

        if (
            not APP_ENABLE_AUTH
            or caminho in rotas_livres
            or caminho.startswith("/static")
            or caminho.startswith("/assets")
        ):
            return await call_next(request)

        sessao = request.session

        usuario_id = sessao.get("usuario_id")
        session_id = sessao.get("session_id")

        if not usuario_id or not session_id:
            return RedirectResponse(
                url=f"/login?next={quote(caminho)}",
                status_code=303
            )

        sessao_banco = obter_sessao_usuario(usuario_id)

        if (
            not sessao_banco
            or sessao_banco != session_id
        ):
            request.session.clear()

            return RedirectResponse(
                url=f"/login?next={quote(caminho)}",
                status_code=303
            )

        return await call_next(request)


app = FastAPI(title="OMRCheck Web")

app.add_middleware(AutenticacaoMiddleware)

app.add_middleware(
    GZipMiddleware,
    minimum_size=1024
)

app.add_middleware(
    SessionMiddleware,
    secret_key=APP_SESSION_SECRET,
    session_cookie=APP_SESSION_COOKIE_NAME,
    same_site="lax",
    https_only=False,
    max_age=60 * 60 * 5
)

# HOSTS
if APP_ALLOWED_HOSTS:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=APP_ALLOWED_HOSTS
    )

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

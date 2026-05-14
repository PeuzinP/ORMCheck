from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.routes import router
from app.settings import (
    BASE_DIR,
    CAMINHO_MODELO_CARTAO,
    CAMINHO_JOBS,
    KEEPEDU_API_KEY,
    garantir_pastas
)


garantir_pastas()

app = FastAPI(title="OMRCheck Web")

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "web" / "static")),
    name="static"
)

app.state.templates = Jinja2Templates(
    directory=str(BASE_DIR / "web" / "templates")
)


@app.get("/healthz")
async def healthcheck():
    return {
        "status": "ok",
        "modelo_cartao_existe": CAMINHO_MODELO_CARTAO.exists(),
        "keepedu_api_configurada": bool(str(KEEPEDU_API_KEY).strip()),
        "jobs_store_existe": CAMINHO_JOBS.exists()
    }


app.include_router(router)

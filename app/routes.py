from app.gerador_csv import gerar_csv_final, caminho_csv_final
from app.validacao_cadastral import gerar_validacao_cadastral, salvar_correcao_manual
import json
import os

from app.settings import (
    PASTA_UPLOADS_TEMP,
    MAX_UPLOAD_FILES,
    MAX_FILE_SIZE_MB,
    MAX_TOTAL_UPLOAD_SIZE_MB
)
from app.progresso import criar_job, obter_job, atualizar_job
from app.services import processar_pasta_temporaria_com_progresso

from fastapi import APIRouter, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel

from app.services import (
    listar_processamentos,
    listar_imagens_debug,
    processar_pasta_local,
    processar_uploads,
    caminho_imagem_debug,
    caminho_leituras,
    caminho_log,
    caminho_correcoes_web
)


router = APIRouter()
EXTENSOES_PERMITIDAS = {".jpg", ".jpeg", ".png"}


class CorrecoesPayload(BaseModel):
    correcoes: dict


async def salvar_uploads_em_pasta(arquivos: list[UploadFile], pasta_upload):
    if len(arquivos) > MAX_UPLOAD_FILES:
        raise ValueError(
            f"Limite excedido: envie no máximo {MAX_UPLOAD_FILES} arquivo(s) por processamento."
        )

    total_salvos = 0
    total_bytes = 0
    limite_total_bytes = MAX_TOTAL_UPLOAD_SIZE_MB * 1024 * 1024
    limite_arquivo_bytes = MAX_FILE_SIZE_MB * 1024 * 1024

    for arquivo in arquivos:
        nome_arquivo = os.path.basename(arquivo.filename)

        if not nome_arquivo:
            continue

        extensao = os.path.splitext(nome_arquivo)[1].lower()

        if extensao not in EXTENSOES_PERMITIDAS:
            continue

        conteudo = await arquivo.read()
        tamanho_arquivo = len(conteudo)

        if tamanho_arquivo > limite_arquivo_bytes:
            raise ValueError(
                f"O arquivo {nome_arquivo} excede o limite de {MAX_FILE_SIZE_MB} MB."
            )

        total_bytes += tamanho_arquivo

        if total_bytes > limite_total_bytes:
            raise ValueError(
                f"O envio excedeu o limite total de {MAX_TOTAL_UPLOAD_SIZE_MB} MB."
            )

        destino = pasta_upload / nome_arquivo

        with open(destino, "wb") as f:
            f.write(conteudo)

        total_salvos += 1

    return total_salvos


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    processamentos = listar_processamentos()

    return request.app.state.templates.TemplateResponse(
        request,
        "index.html",
        {
            "processamentos": processamentos
        }
    )


@router.post("/processar-pasta")
async def rota_processar_pasta(pasta_origem: str = Form(...)):
    try:
        nome_processamento = processar_pasta_local(pasta_origem)

        return RedirectResponse(
            url=f"/processamento/{nome_processamento}",
            status_code=303
        )

    except Exception as e:
        return HTMLResponse(
            f"""
            <h1>Erro ao processar pasta</h1>
            <p>{str(e)}</p>
            <p><a href="/">Voltar</a></p>
            """,
            status_code=400
        )


@router.post("/processar")
async def rota_processar_upload(
    background_tasks: BackgroundTasks,
    arquivos: list[UploadFile] = File(...)
):
    job_id = criar_job(total_arquivos=len(arquivos))

    pasta_upload = PASTA_UPLOADS_TEMP / f"upload_{job_id}"
    pasta_upload.mkdir(parents=True, exist_ok=True)

    try:
        total_salvos = await salvar_uploads_em_pasta(arquivos, pasta_upload)

        if total_salvos == 0:
            atualizar_job(
                job_id,
                status="erro",
                percentual=100,
                mensagem="Nenhuma imagem válida foi enviada.",
                erro="Nenhuma imagem .jpg, .jpeg ou .png encontrada."
            )

            return RedirectResponse(
                url=f"/processando/{job_id}",
                status_code=303
            )

        atualizar_job(
            job_id,
            status="processando",
            percentual=5,
            mensagem=f"{total_salvos} imagem(ns) recebida(s). Preparando leitura..."
        )

        background_tasks.add_task(
            processar_pasta_temporaria_com_progresso,
            job_id,
            pasta_upload
        )

        return RedirectResponse(
            url=f"/processando/{job_id}",
            status_code=303
        )

    except Exception as e:
        atualizar_job(
            job_id,
            status="erro",
            percentual=100,
            mensagem="Erro ao receber imagens.",
            erro=str(e)
        )

        return RedirectResponse(
            url=f"/processando/{job_id}",
            status_code=303
        )


@router.get("/processamento/{nome_processamento}", response_class=HTMLResponse)
async def ver_processamento(request: Request, nome_processamento: str):
    imagens_debug = listar_imagens_debug(nome_processamento)

    return request.app.state.templates.TemplateResponse(
        request,
        "processamento.html",
        {
            "nome_processamento": nome_processamento,
            "imagens_debug": imagens_debug
        }
    )


@router.get("/correcao/{nome_processamento}", response_class=HTMLResponse)
async def correcao(request: Request, nome_processamento: str):
    imagens_debug = listar_imagens_debug(nome_processamento)

    return request.app.state.templates.TemplateResponse(
        request,
        "correcao.html",
        {
            "nome_processamento": nome_processamento,
            "imagens_debug": imagens_debug
        }
    )


@router.get("/imagem/{nome_processamento}/{nome_imagem}")
async def servir_imagem(nome_processamento: str, nome_imagem: str):
    caminho = caminho_imagem_debug(nome_processamento, nome_imagem)

    if not caminho.exists():
        return JSONResponse(
            {"erro": "Imagem não encontrada."},
            status_code=404
        )

    return FileResponse(str(caminho))


@router.get("/leituras/{nome_processamento}")
async def obter_leituras(nome_processamento: str):
    caminho = caminho_leituras(nome_processamento)

    if not caminho.exists():
        return JSONResponse({})

    return FileResponse(str(caminho), media_type="application/json")


@router.get("/download-log/{nome_processamento}")
async def download_log(nome_processamento: str):
    caminho = caminho_log(nome_processamento)

    if not caminho.exists():
        return JSONResponse(
            {"erro": "Log não encontrado."},
            status_code=404
        )

    return FileResponse(
        str(caminho),
        filename="log_leitura_omr.csv"
    )


@router.get("/correcoes/{nome_processamento}")
async def obter_correcoes(nome_processamento: str):
    caminho = caminho_correcoes_web(nome_processamento)

    if not caminho.exists():
        return JSONResponse({})

    return FileResponse(str(caminho), media_type="application/json")


@router.post("/correcoes/{nome_processamento}")
async def salvar_correcoes(nome_processamento: str, payload: CorrecoesPayload):
    caminho = caminho_correcoes_web(nome_processamento)

    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(payload.correcoes, f, ensure_ascii=False, indent=4)

    return {
        "status": "ok",
        "arquivo": str(caminho)
    }
    
@router.get("/validacao/{nome_processamento}", response_class=HTMLResponse)
async def validacao_cadastral(request: Request, nome_processamento: str):
    dados_validacao = gerar_validacao_cadastral(nome_processamento)

    return request.app.state.templates.TemplateResponse(
        request,
        "validacao.html",
        {
            "nome_processamento": nome_processamento,
            "resumo": dados_validacao["resumo"],
            "validacoes": dados_validacao["validacoes"]
        }
    )
    
@router.get("/gerar-csv/{nome_processamento}")
async def rota_gerar_csv(nome_processamento: str, forcar: bool = False):
    resultado = gerar_csv_final(nome_processamento, forcar=forcar)

    if resultado["status"] != "ok":
        return JSONResponse(resultado, status_code=400)

    return RedirectResponse(
        url=f"/download-csv/{nome_processamento}",
        status_code=303
    )


@router.get("/download-csv/{nome_processamento}")
async def rota_download_csv(nome_processamento: str):
    caminho = caminho_csv_final(nome_processamento)

    if not caminho.exists():
        return JSONResponse(
            {"erro": "CSV final não encontrado."},
            status_code=404
        )

    return FileResponse(
        str(caminho),
        filename=f"{nome_processamento}_csv_final_keepedu.csv",
        media_type="text/csv"
    )
    
@router.post("/validacao/manual/{nome_processamento}")
async def rota_salvar_validacao_manual(
    nome_processamento: str,
    nome_imagem: str = Form(...),
    id_aluno_manual: str = Form(...)
):
    try:
        salvar_correcao_manual(
            nome_processamento=nome_processamento,
            nome_imagem=nome_imagem,
            valor_manual=id_aluno_manual
        )

        return RedirectResponse(
            url=f"/validacao/{nome_processamento}",
            status_code=303
        )

    except Exception as e:
        return HTMLResponse(
            f"""
            <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Erro na validação manual</title>
                </head>
                <body style="font-family: Arial; padding: 30px;">
                    <h1>Erro ao salvar validação manual</h1>
                    <p>{str(e)}</p>
                    <p><a href="/validacao/{nome_processamento}">Voltar para validação</a></p>
                </body>
            </html>
            """,
            status_code=400
        )

@router.get("/processando/{job_id}", response_class=HTMLResponse)
async def tela_processando(request: Request, job_id: str):
    return request.app.state.templates.TemplateResponse(
        request,
        "processando.html",
        {
            "job_id": job_id
        }
    )


@router.get("/status-processamento/{job_id}")
async def status_processamento(job_id: str):
    return JSONResponse(obter_job(job_id))

@router.post("/processar-ajax")
async def rota_processar_ajax(
    background_tasks: BackgroundTasks,
    arquivos: list[UploadFile] = File(...)
):
    job_id = criar_job(total_arquivos=len(arquivos))

    pasta_upload = PASTA_UPLOADS_TEMP / f"upload_{job_id}"
    pasta_upload.mkdir(parents=True, exist_ok=True)

    try:
        total_salvos = await salvar_uploads_em_pasta(arquivos, pasta_upload)

        if total_salvos == 0:
            atualizar_job(
                job_id,
                status="erro",
                percentual=100,
                mensagem="Nenhuma imagem válida foi enviada.",
                erro="Nenhuma imagem .jpg, .jpeg ou .png encontrada."
            )

            return JSONResponse({
                "status": "erro",
                "job_id": job_id,
                "mensagem": "Nenhuma imagem válida foi enviada."
            })

        atualizar_job(
            job_id,
            status="processando",
            percentual=5,
            mensagem=f"{total_salvos} imagem(ns) recebida(s). Preparando leitura..."
        )

        background_tasks.add_task(
            processar_pasta_temporaria_com_progresso,
            job_id,
            pasta_upload
        )

        return JSONResponse({
            "status": "ok",
            "job_id": job_id
        })

    except Exception as e:
        atualizar_job(
            job_id,
            status="erro",
            percentual=100,
            mensagem="Erro ao receber imagens.",
            erro=str(e)
        )

        return JSONResponse({
            "status": "erro",
            "job_id": job_id,
            "mensagem": str(e)
        })

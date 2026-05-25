from app.gerador_csv import gerar_csv_final, caminho_csv_final, carregar_leituras
from app.bernoulli import transformar_vetor_keepedu_para_bernoulli, EXTENSOES_PLANILHA, PASTA_BERNOULLI
from app.keepedu_importacao import (
    contar_alunos_importacao,
    importar_respostas_presenciais,
    processar_mock_importacao_keepedu,
    simular_importacao_respostas_presenciais,
)
from app.keepedu_auth import autenticar_keepedu
from app.validacao_cadastral import gerar_validacao_cadastral, salvar_correcao_manual
import json
import os
from html import escape

from app.settings import (
    APP_ENABLE_AUTH,
    ID_PROVA_KEEPEDU,
    KEEPEDU_LOGIN_SCHOOL,
    KEEPEDU_LOGIN_URL,
    PASTA_UPLOADS_TEMP,
    MAX_UPLOAD_FILES,
    MAX_FILE_SIZE_MB,
    MAX_TOTAL_UPLOAD_SIZE_MB
)
from app.progresso import criar_job, obter_job, atualizar_job, registrar_evento_job
from app.services import processar_pasta_temporaria_com_progresso

from fastapi import APIRouter, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel

from app.services import (
    listar_processamentos,
    listar_imagens_debug,
    resumo_processamento,
    processar_pasta_local,
    processar_uploads,
    caminho_imagem_debug,
    caminho_leituras,
    caminho_log,
    caminho_correcoes_web,
    reprocessar_imagem_processamento
)


router = APIRouter()
EXTENSOES_PERMITIDAS = {".jpg", ".jpeg", ".png"}


class CorrecoesPayload(BaseModel):
    correcoes: dict


class ReprocessarImagemPayload(BaseModel):
    nome_imagem: str
    pontos_cantos: dict


class ImportarRespostasPayload(BaseModel):
    idAval: str | int | None = None
    diaAval: str | int | None = None
    usuario_id: str | int | None = None
    idAluno: str | int | None = None


def render_template(request: Request, nome_template: str, contexto: dict, status_code: int = 200):
    resposta = request.app.state.templates.TemplateResponse(
        request,
        nome_template,
        contexto,
        status_code=status_code
    )
    resposta.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resposta.headers["Pragma"] = "no-cache"
    resposta.headers["Expires"] = "0"
    return resposta


def _destino_pos_login(destino: str | None) -> str:
    texto = str(destino or "").strip()

    if not texto.startswith("/") or texto.startswith("//"):
        return "/"

    return texto


def _resultado_job_importacao(resultado: dict | None):
    if not isinstance(resultado, dict):
        return {}

    return {
        "status": resultado.get("status", ""),
        "success": bool(resultado.get("success")),
        "modo": resultado.get("modo", ""),
        "idAval": resultado.get("idAval"),
        "id_aluno": resultado.get("id_aluno"),
        "total": int(resultado.get("total", 0) or 0),
        "importadas": int(resultado.get("importadas", 0) or 0),
        "erros": int(resultado.get("erros", 0) or 0),
        "mensagem": resultado.get("mensagem", []),
        "pendencias_avaliacao": resultado.get("pendencias_avaliacao", []),
        "validacao_atualizada": bool(resultado.get("validacao_atualizada")),
        "arquivo_relatorio": resultado.get("arquivo_relatorio", ""),
    }


def _executar_importacao_respostas_em_background(
    job_id: str,
    nome_processamento: str,
    payload: ImportarRespostasPayload,
    modo: str,
):
    def progresso_callback(
        percentual,
        mensagem,
        arquivo_atual="",
        resultado=None,
        tipo=None,
        titulo=None,
        descricao="",
    ):
        atualizar_job(
            job_id,
            status="processando",
            percentual=percentual,
            mensagem=mensagem,
            arquivo_atual=arquivo_atual,
            resultado=_resultado_job_importacao(resultado),
        )

        if titulo:
            registrar_evento_job(
                job_id,
                tipo or "info",
                titulo,
                descricao or mensagem,
                arquivo=arquivo_atual,
            )

    try:
        atualizar_job(
            job_id,
            status="processando",
            percentual=1,
            mensagem="Preparando envio em JSON...",
        )
        registrar_evento_job(
            job_id,
            "info",
            "Envio iniciado",
            f"Lote {nome_processamento} em modo {modo}.",
        )

        if modo == "simulacao":
            resultado = simular_importacao_respostas_presenciais(
                nome_processamento=nome_processamento,
                id_aval=payload.idAval,
                dia_aval=payload.diaAval,
                usuario_id=payload.usuario_id,
                id_aluno=payload.idAluno,
                progresso_callback=progresso_callback,
            )
        else:
            resultado = importar_respostas_presenciais(
                nome_processamento=nome_processamento,
                id_aval=payload.idAval,
                dia_aval=payload.diaAval,
                usuario_id=payload.usuario_id,
                id_aluno=payload.idAluno,
                progresso_callback=progresso_callback,
            )

        resultado_job = _resultado_job_importacao(resultado)
        status_resultado = resultado.get("status")

        if status_resultado == "erro":
            atualizar_job(
                job_id,
                status="erro",
                percentual=100,
                mensagem="Envio em JSON encerrado com erro.",
                erro=" | ".join(resultado.get("mensagem", [])[:3]) or "Erro na importação.",
                resultado=resultado_job,
            )
            registrar_evento_job(
                job_id,
                "error",
                "Envio com erro",
                " | ".join(resultado.get("mensagem", [])[:3]) or "Falha na importação.",
            )
            return

        atualizar_job(
            job_id,
            status="concluido",
            percentual=100,
            mensagem=(
                "Simulação concluída."
                if modo == "simulacao" else
                "Envio em JSON concluído."
            ),
            resultado=resultado_job,
        )
        registrar_evento_job(
            job_id,
            "success" if status_resultado == "ok" else "warning",
            "Envio finalizado",
            f"{resultado.get('importadas', 0)}/{resultado.get('total', 0)} importada(s), "
            f"{resultado.get('erros', 0)} erro(s).",
        )
    except Exception as erro:
        atualizar_job(
            job_id,
            status="erro",
            percentual=100,
            mensagem="Erro ao executar envio em JSON.",
            erro=str(erro),
        )
        registrar_evento_job(
            job_id,
            "error",
            "Falha no envio",
            str(erro),
        )


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


async def salvar_arquivo_upload(arquivo: UploadFile, pasta_destino):
    nome_arquivo = os.path.basename(arquivo.filename or "")

    if not nome_arquivo:
        raise ValueError("Arquivo enviado sem nome.")

    extensao = os.path.splitext(nome_arquivo)[1].lower()

    if extensao not in EXTENSOES_PLANILHA:
        raise ValueError(f"Formato não suportado: {nome_arquivo}")

    conteudo = await arquivo.read()
    destino = pasta_destino / nome_arquivo

    with open(destino, "wb") as f:
        f.write(conteudo)

    return destino


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    processamentos = listar_processamentos()

    return render_template(
        request,
        "index.html",
        {
            "processamentos": processamentos
        }
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/"):
    if not APP_ENABLE_AUTH:
        return RedirectResponse(url="/", status_code=303)

    if request.session.get("authenticated"):
        return RedirectResponse(url=_destino_pos_login(next), status_code=303)

    return render_template(
        request,
        "login.html",
        {
            "erro_login": "",
            "email_login": "",
            "next_url": _destino_pos_login(next),
            "keepedu_login_habilitado": bool(KEEPEDU_LOGIN_URL),
            "keepedu_school": KEEPEDU_LOGIN_SCHOOL,
        },
    )


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(""),
    senha: str = Form(""),
    next_url: str = Form("/"),
):
    if not APP_ENABLE_AUTH:
        return RedirectResponse(url="/", status_code=303)

    sucesso, mensagem, dados_usuario = autenticar_keepedu(email, senha)

    if not sucesso:
        return render_template(
            request,
            "login.html",
            {
                "erro_login": mensagem or "Não foi possível entrar.",
                "email_login": str(email or "").strip(),
                "next_url": _destino_pos_login(next_url),
                "keepedu_login_habilitado": bool(KEEPEDU_LOGIN_URL),
                "keepedu_school": KEEPEDU_LOGIN_SCHOOL,
            },
            status_code=401,
        )

    request.session.clear()
    request.session["authenticated"] = True
    request.session["user_email"] = str(dados_usuario.get("email") or email or "").strip()
    request.session["auth_source"] = str(dados_usuario.get("origem") or "keepedu")

    return RedirectResponse(url=_destino_pos_login(next_url), status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@router.get("/bernoulli", response_class=HTMLResponse)
async def bernoulli(request: Request):
    return render_template(
        request,
        "bernoulli.html",
        {}
    )


def _rotulo_dia_bernoulli(dia: str) -> str:
    return "1 dia" if str(dia) == "1" else "2 dia"


def _montar_logs_bernoulli(resultado: dict, nome_arquivo_entrada: str, nome_arquivo_download: str):
    return [
        {
            "tipo": "info",
            "titulo": "Arquivo recebido",
            "descricao": nome_arquivo_entrada
        },
        {
            "tipo": "info",
            "titulo": "Modo selecionado",
            "descricao": f"{_rotulo_dia_bernoulli(resultado.get('dia', '1'))} | q{resultado.get('primeira_questao', 1)} a q{resultado.get('ultima_questao', 90)}"
        },
        {
            "tipo": "success",
            "titulo": "Estrutura validada",
            "descricao": f"{resultado['questoes_encontradas_no_keepedu']} coluna(s) de questao reconhecida(s)."
        },
        {
            "tipo": "success",
            "titulo": "Consulta Bernoulli concluida",
            "descricao": f"{resultado['rmb_encontrados']} RMB(s) localizado(s) e {resultado['sem_rmb']} pendencia(s) de inscricao."
        },
        {
            "tipo": "success",
            "titulo": "Arquivo pronto",
            "descricao": nome_arquivo_download
        }
    ]


def _processar_arquivo_bernoulli(caminho_keepedu, nome_arquivo_entrada: str, dia: str, progresso_callback=None):
    resultado = transformar_vetor_keepedu_para_bernoulli(
        caminho_arquivo_keepedu=caminho_keepedu,
        dia=dia,
        progresso_callback=progresso_callback
    )
    nome_saida_real = os.path.basename(str(resultado["caminho_saida"]))
    nome_arquivo_download = (
        f"vetor_bernoulli_dia{resultado['dia']}_{resultado['linhas']}lin_"
        f"q{resultado['primeira_questao']}-q{resultado['ultima_questao']}.xlsx"
    )

    return {
        "resultado": resultado,
        "nome_arquivo_entrada": nome_arquivo_entrada,
        "nome_arquivo_real": nome_saida_real,
        "nome_arquivo_download": nome_arquivo_download,
        "download_url": f"/bernoulli/download/{nome_saida_real}",
        "logs": _montar_logs_bernoulli(resultado, nome_arquivo_entrada, nome_arquivo_download)
    }


def _resultado_job_bernoulli(dados: dict):
    return {
        "resultado": dados["resultado"],
        "nome_arquivo_entrada": dados["nome_arquivo_entrada"],
        "nome_arquivo_real": dados["nome_arquivo_real"],
        "nome_arquivo_download": dados["nome_arquivo_download"],
        "download_url": dados["download_url"]
    }


async def executar_processamento_bernoulli(arquivo_keepedu: UploadFile, dia: str = "1", progresso_callback=None):
    pasta_tmp = PASTA_UPLOADS_TEMP / f"bernoulli_{os.urandom(8).hex()}"
    pasta_tmp.mkdir(parents=True, exist_ok=True)

    try:
        caminho_keepedu = await salvar_arquivo_upload(arquivo_keepedu, pasta_tmp)
        return _processar_arquivo_bernoulli(
            caminho_keepedu=caminho_keepedu,
            nome_arquivo_entrada=os.path.basename(arquivo_keepedu.filename or caminho_keepedu.name),
            dia=dia,
            progresso_callback=progresso_callback
        )
    finally:
        for arquivo in pasta_tmp.glob("*"):
            try:
                arquivo.unlink(missing_ok=True)
            except Exception:
                pass

        try:
            pasta_tmp.rmdir()
        except Exception:
            pass


def processar_arquivo_bernoulli_em_background(job_id: str, caminho_keepedu, nome_arquivo_entrada: str, dia: str):
    pasta_tmp = caminho_keepedu.parent

    def progresso_callback(percentual, mensagem, tipo=None, titulo=None, descricao="", resultado=None):
        atualizar_job(
            job_id,
            status="processando",
            percentual=percentual,
            mensagem=mensagem,
            arquivo_atual=nome_arquivo_entrada,
            resultado=resultado
        )

        if titulo:
            registrar_evento_job(
                job_id,
                tipo or "info",
                titulo,
                descricao or mensagem,
                arquivo=nome_arquivo_entrada
            )

    try:
        atualizar_job(
            job_id,
            status="processando",
            percentual=5,
            mensagem=f"Arquivo recebido. Preparando processamento do {_rotulo_dia_bernoulli(dia)}...",
            arquivo_atual=nome_arquivo_entrada
        )
        registrar_evento_job(job_id, "info", "Arquivo recebido", nome_arquivo_entrada, arquivo=nome_arquivo_entrada)

        dados = _processar_arquivo_bernoulli(
            caminho_keepedu=caminho_keepedu,
            nome_arquivo_entrada=nome_arquivo_entrada,
            dia=dia,
            progresso_callback=progresso_callback
        )

        registrar_evento_job(
            job_id,
            "success",
            "Arquivo pronto",
            dados["nome_arquivo_download"],
            arquivo=nome_arquivo_entrada
        )
        atualizar_job(
            job_id,
            status="concluido",
            percentual=100,
            mensagem="Simulado Bernoulli gerado com sucesso.",
            arquivo_atual=nome_arquivo_entrada,
            resultado=_resultado_job_bernoulli(dados)
        )
    except Exception as erro:
        atualizar_job(
            job_id,
            status="erro",
            percentual=100,
            mensagem="Erro ao gerar o Simulado Bernoulli.",
            arquivo_atual=nome_arquivo_entrada,
            erro=str(erro)
        )
        registrar_evento_job(
            job_id,
            "error",
            "Falha na conversao",
            str(erro),
            arquivo=nome_arquivo_entrada
        )
    finally:
        for arquivo in pasta_tmp.glob("*"):
            try:
                arquivo.unlink(missing_ok=True)
            except Exception:
                pass

        try:
            pasta_tmp.rmdir()
        except Exception:
            pass


@router.post("/bernoulli/processar")
async def bernoulli_processar(
    arquivo_keepedu: UploadFile = File(...),
    dia: str = Form("1")
):
    try:
        dados = await executar_processamento_bernoulli(arquivo_keepedu, dia=dia)
        return FileResponse(
            str(PASTA_BERNOULLI / dados["nome_arquivo_real"]),
            filename=dados["nome_arquivo_download"],
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except ValueError as e:
        return HTMLResponse(
            f"""
            <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Erro no Simulado Bernoulli</title>
                </head>
                <body style="font-family: Arial; padding: 30px;">
                    <h1>Erro ao gerar Simulado Bernoulli</h1>
                    <p>{escape(str(e))}</p>
                    <p><a href="/bernoulli">Voltar</a></p>
                </body>
            </html>
            """,
            status_code=400
        )
    except Exception as e:
        return HTMLResponse(
            f"""
            <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Erro no Simulado Bernoulli</title>
                </head>
                <body style="font-family: Arial; padding: 30px;">
                    <h1>Erro interno ao gerar Simulado Bernoulli</h1>
                    <p>{escape(str(e))}</p>
                    <p><a href="/bernoulli">Voltar</a></p>
                </body>
            </html>
            """,
            status_code=500
        )


@router.post("/bernoulli/processar-ajax")
async def bernoulli_processar_ajax(
    background_tasks: BackgroundTasks,
    arquivo_keepedu: UploadFile = File(...),
    dia: str = Form("1")
):
    job_id = criar_job(total_arquivos=1)
    pasta_tmp = PASTA_UPLOADS_TEMP / f"bernoulli_{job_id}"
    pasta_tmp.mkdir(parents=True, exist_ok=True)

    try:
        caminho_keepedu = await salvar_arquivo_upload(arquivo_keepedu, pasta_tmp)
        nome_arquivo_entrada = os.path.basename(arquivo_keepedu.filename or caminho_keepedu.name)
        atualizar_job(
            job_id,
            status="processando",
            percentual=3,
            mensagem=f"Arquivo recebido. Aguardando inicio do processamento do {_rotulo_dia_bernoulli(dia)}...",
            arquivo_atual=nome_arquivo_entrada
        )
        background_tasks.add_task(
            processar_arquivo_bernoulli_em_background,
            job_id,
            caminho_keepedu,
            nome_arquivo_entrada,
            dia
        )

        return JSONResponse(
            {
                "status": "ok",
                "job_id": job_id
            }
        )
    except ValueError as erro:
        atualizar_job(
            job_id,
            status="erro",
            percentual=100,
            mensagem="Erro ao receber o arquivo do KeepEdu.",
            erro=str(erro)
        )
        try:
            pasta_tmp.rmdir()
        except Exception:
            pass
        return JSONResponse(
            {
                "status": "erro",
                "job_id": job_id,
                "mensagem": str(erro)
            },
            status_code=400
        )
    except Exception as erro:
        atualizar_job(
            job_id,
            status="erro",
            percentual=100,
            mensagem="Erro ao iniciar o processamento do Simulado Bernoulli.",
            erro=str(erro)
        )
        for arquivo in pasta_tmp.glob("*"):
            try:
                arquivo.unlink(missing_ok=True)
            except Exception:
                pass
        try:
            pasta_tmp.rmdir()
        except Exception:
            pass
        return JSONResponse(
            {
                "status": "erro",
                "job_id": job_id,
                "mensagem": str(erro)
            },
            status_code=500
        )


@router.get("/bernoulli/download/{nome_arquivo}")
async def bernoulli_download(nome_arquivo: str):
    nome_seguro = os.path.basename(nome_arquivo or "")

    if not nome_seguro:
        return HTMLResponse("<h1>Arquivo inválido.</h1>", status_code=400)

    caminho_saida = (PASTA_BERNOULLI / nome_seguro).resolve()

    try:
        caminho_saida.relative_to(PASTA_BERNOULLI.resolve())
    except ValueError:
        return HTMLResponse("<h1>Arquivo inválido.</h1>", status_code=400)

    if not caminho_saida.exists():
        return HTMLResponse("<h1>Arquivo não encontrado.</h1>", status_code=404)

    return FileResponse(
        str(caminho_saida),
        filename=nome_seguro,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
    resumo = resumo_processamento(nome_processamento)

    return render_template(
        request,
        "processamento.html",
        {
            "nome_processamento": nome_processamento,
            "imagens_debug": imagens_debug,
            "resumo": resumo
        }
    )


@router.get("/correcao/{nome_processamento}", response_class=HTMLResponse)
async def correcao(request: Request, nome_processamento: str):
    imagens_debug = listar_imagens_debug(nome_processamento)

    return render_template(
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


@router.post("/reprocessar-imagem/{nome_processamento}")
async def rota_reprocessar_imagem(nome_processamento: str, payload: ReprocessarImagemPayload):
    try:
        return JSONResponse(
            reprocessar_imagem_processamento(
                nome_processamento=nome_processamento,
                nome_imagem=payload.nome_imagem,
                pontos_cantos=payload.pontos_cantos
            )
        )
    except Exception as e:
        return JSONResponse(
            {
                "status": "erro",
                "mensagem": str(e)
            },
            status_code=400
        )
    
@router.get("/validacao/{nome_processamento}", response_class=HTMLResponse)
async def validacao_cadastral(request: Request, nome_processamento: str):
    caminho = caminho_leituras(nome_processamento)

    if not caminho.exists():
        return HTMLResponse(
            (
                "<h1>Processamento não encontrado.</h1>"
                "<p>O lote solicitado não existe no diretório configurado em APP_PROCESSAMENTOS_DIR.</p>"
            ),
            status_code=404,
        )

    dados_validacao = gerar_validacao_cadastral(nome_processamento)
    resumo = dados_validacao["resumo"]

    return render_template(
        request,
        "validacao.html",
        {
            "nome_processamento": nome_processamento,
            "resumo": resumo,
            "validacoes": dados_validacao["validacoes"],
            "importacao_defaults": {
                "id_aval": resumo.get("id_prova_processamento") or ID_PROVA_KEEPEDU
            }
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


@router.post("/importar-respostas-presenciais/{nome_processamento}")
async def rota_importar_respostas_presenciais(
    nome_processamento: str,
    payload: ImportarRespostasPayload
):
    resultado = importar_respostas_presenciais(
        nome_processamento=nome_processamento,
        id_aval=payload.idAval,
        dia_aval=payload.diaAval,
        usuario_id=payload.usuario_id,
        id_aluno=payload.idAluno,
    )

    if resultado.get("status") == "erro":
        return JSONResponse(resultado, status_code=400)

    return JSONResponse(resultado)


@router.post("/importar-respostas-presenciais-ajax/{nome_processamento}")
async def rota_importar_respostas_presenciais_ajax(
    nome_processamento: str,
    payload: ImportarRespostasPayload,
    background_tasks: BackgroundTasks,
):
    total_arquivos = contar_alunos_importacao(nome_processamento, id_aluno=payload.idAluno)
    job_id = criar_job(total_arquivos=total_arquivos)

    background_tasks.add_task(
        _executar_importacao_respostas_em_background,
        job_id,
        nome_processamento,
        payload,
        "importacao",
    )

    return JSONResponse(
        {
            "status": "ok",
            "job_id": job_id,
            "mensagem": "Envio em JSON iniciado.",
        }
    )


@router.post("/simular-importacao-respostas-presenciais/{nome_processamento}")
async def rota_simular_importacao_respostas_presenciais(
    nome_processamento: str,
    payload: ImportarRespostasPayload
):
    resultado = simular_importacao_respostas_presenciais(
        nome_processamento=nome_processamento,
        id_aval=payload.idAval,
        dia_aval=payload.diaAval,
        usuario_id=payload.usuario_id,
        id_aluno=payload.idAluno,
    )

    if resultado.get("status") == "erro":
        return JSONResponse(resultado, status_code=400)

    return JSONResponse(resultado)


@router.post("/simular-importacao-respostas-presenciais-ajax/{nome_processamento}")
async def rota_simular_importacao_respostas_presenciais_ajax(
    nome_processamento: str,
    payload: ImportarRespostasPayload,
    background_tasks: BackgroundTasks,
):
    total_arquivos = contar_alunos_importacao(nome_processamento, id_aluno=payload.idAluno)
    job_id = criar_job(total_arquivos=total_arquivos)

    background_tasks.add_task(
        _executar_importacao_respostas_em_background,
        job_id,
        nome_processamento,
        payload,
        "simulacao",
    )

    return JSONResponse(
        {
            "status": "ok",
            "job_id": job_id,
            "mensagem": "Simulação em JSON iniciada.",
        }
    )

@router.post("/mock/importar-respostas-presenciais")
async def mock_importar_respostas_presenciais(request: Request):
    try:
        dados = await request.json()
    except Exception:
        return JSONResponse(
            {
                "success": False,
                "mensagem": ["JSON inválido no corpo da requisição."],
                "arquivoErros": []
            },
            status_code=400
        )

    status_code, resposta = processar_mock_importacao_keepedu(dados)
    return JSONResponse(resposta, status_code=status_code)
    
@router.post("/validacao/manual/{nome_processamento}")
async def rota_salvar_validacao_manual(
    request: Request,
    nome_processamento: str,
    nome_imagem: str = Form(...),
    id_aluno_manual: str = Form(...)
):
    try:
        registro = salvar_correcao_manual(
            nome_processamento=nome_processamento,
            nome_imagem=nome_imagem,
            valor_manual=id_aluno_manual
        )

        aceita_json = (
            request.query_params.get("ajax") == "1"
            or request.query_params.get("modo") == "ajax"
            or
            "application/json" in (request.headers.get("accept") or "").lower()
            or (request.headers.get("x-requested-with") or "").lower() == "fetch"
        )

        if aceita_json:
            return JSONResponse(
                {
                    "status": "ok",
                    "nome_imagem": nome_imagem,
                    "registro": registro,
                }
            )

        return RedirectResponse(
            url=f"/validacao/{nome_processamento}",
            status_code=303
        )

    except Exception as e:
        aceita_json = (
            request.query_params.get("ajax") == "1"
            or request.query_params.get("modo") == "ajax"
            or
            "application/json" in (request.headers.get("accept") or "").lower()
            or (request.headers.get("x-requested-with") or "").lower() == "fetch"
        )

        if aceita_json:
            return JSONResponse(
                {"status": "erro", "mensagem": str(e)},
                status_code=400
            )

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
    return render_template(
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

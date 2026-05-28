import ast
import secrets
from urllib.parse import unquote
from app.gerador_csv import gerar_csv_final, caminho_csv_final
from app.bernoulli import transformar_vetor_keepedu_para_bernoulli, EXTENSOES_PLANILHA, PASTA_BERNOULLI
from app.keepedu_importacao import (
    importar_respostas_presenciais,
    importar_imagens_folha_resposta,
)
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
from app.auth import gerenciar_lembre_me, verificar_autologin_cookie, remover_token_banco
from app.auth import (
    salvar_sessao_usuario,
    obter_sessao_usuario,
    remover_sessao_usuario
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BASE_DIR)

from app.settings import (
    APP_ENABLE_AUTH,
    ID_PROVA_KEEPEDU,
    KEEPEDU_LOGIN_SCHOOL,
    KEEPEDU_LOGIN_URL,
    PASTA_PROCESSAMENTOS,
    PASTA_UPLOADS_TEMP,
    MAX_UPLOAD_FILES,
    MAX_FILE_SIZE_MB,
    MAX_TOTAL_UPLOAD_SIZE_MB
)
from app.progresso import criar_job, obter_job, atualizar_job, registrar_evento_job
from app.services import processar_pasta_temporaria_com_progresso

from fastapi import APIRouter, Request, UploadFile, File, Form, Response, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from pathlib import Path

from app.services import (
    carregar_json,
    caminho_leituras,
    listar_processamentos,
    listar_processamentos_recentes,
    listar_imagens_debug,
    localizar_imagem_original,
    resumo_processamento,
    processar_pasta_local,
    processar_uploads,
    caminho_imagem_debug,
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
    nome_processamento: str | None = None
    modelo_ia : str | None = None


def listar_processamentos_local():
    return listar_processamentos()

@router.get("/validacao/")
@router.get("/validacao")
async def tratar_validacao_vazia():
    lotes = listar_processamentos_local()
    if lotes:
        lote_recente = lotes[0]
        return RedirectResponse(url=f"/validacao/{lote_recente}", status_code=303)
    return HTMLResponse("<h1>Avaliação não encontrada.</h1><p>Nenhuma pasta de lote foi detectada no diretório físico de processamentos.</p>", status_code=404)

def carregar_leitura(nome_avaliacao: str, em_json: bool = True):
    """
    Resolve o arquivo principal do lote a partir do diretório configurado.
    """
    caminho_principal = caminho_leituras(nome_avaliacao)
    if caminho_principal.exists():
        return caminho_principal

    nome_puro = nome_avaliacao.replace("processamento_", "")
    candidatos = [
        PASTA_PROCESSAMENTOS / nome_avaliacao / "leituras_omr.json",
        PASTA_PROCESSAMENTOS / nome_puro / "leituras_omr.json",
        PASTA_PROCESSAMENTOS / f"{nome_avaliacao}.json",
        PASTA_PROCESSAMENTOS / f"{nome_puro}.json",
    ]

    for candidato in candidatos:
        if candidato.exists() and candidato.is_file():
            return candidato

    return caminho_principal


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
    nome_avaliacao: str,
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
            mensagem="Preparando envio de Vetores...",
        )
        registrar_evento_job(
            job_id,
            "info",
            "Envio iniciado",
            f"Lote {nome_avaliacao} em modo {modo}.",
        )

        # PASSAGEM POSICIONAL PURA: Passando 'nome_avaliacao' direto como primeiro argumento
        # Isso ignora se o nome interno é 'nome_processamento' ou 'nome_avaliacao' e preenche a posição correta.
        if modo == "simulacao":
            resultado = simular_importacao_respostas_presenciais(
                nome_avaliacao,  # <--- Sem chaves, direto na primeira posição
                id_aval=payload.idAval,
                dia_aval=payload.diaAval,
                usuario_id=payload.usuario_id,
                id_aluno=payload.idAluno,
                progresso_callback=progresso_callback,
            )
        else:
            resultado = importar_respostas_presenciais(
                nome_avaliacao,  # <--- Sem chaves, direto na primeira posição
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
                mensagem="Envio de Vetores encerrado com erro.",
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
                "Progresso de envio de Vetores concluído."
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
            mensagem="Erro ao executar envio de Vetores.",
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


@router.get("/")
async def index():
    return RedirectResponse(
        url="/painel",
        status_code=303
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/"):
    if not APP_ENABLE_AUTH:
        return RedirectResponse(url="/", status_code=303)
        
    usuario_id = request.session.get("usuario_id")
    session_id = request.session.get("session_id")

    if usuario_id and session_id:
        sessao_banco = obter_sessao_usuario(usuario_id)

        if (
            sessao_banco
            and sessao_banco.get("session_id") == session_id
        ):
            return RedirectResponse(
                url=_destino_pos_login(next),
                status_code=303
            )

    # 2. FLUXO DO AUTO-LOGIN: Se não tiver sessão, checa o Cookie de "Lembre-me"
    usuario_id_valido = verificar_autologin_cookie(request)
    
    if usuario_id_valido:

        session_id = secrets.token_hex(32)

        request.session["authenticated"] = True
        request.session["session_id"] = session_id
        request.session["usuario_id"] = usuario_id_valido

        salvar_sessao_usuario(
            usuario_id_valido,
            session_id
        )

        request.session["user_email"] = "operador.lembrado@colegioproposito.com.br"
        request.session["auth_source"] = "keepedu_remember"

        return RedirectResponse(
            url=_destino_pos_login(next),
            status_code=303
        )

    # 3. Se não houver cookie ou o token estiver vencido, renderiza a tela normalmente
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
    response: Response, # <--- ADICIONADO PARA MANIPULAR OS COOKIES
    email: str = Form(""),
    senha: str = Form(""),
    lembre_me: bool = Form(False), # <--- CAPTURA O CHECKBOX DO HTML
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

    # Limpa a sessão local antiga
    # Limpa sessão antiga
    request.session.clear()

    # Gera session_id
    import secrets
    session_id = secrets.token_hex(32)

    # Obtém usuário
    usuario_id = dados_usuario.get("id") or 1

    # Salva sessão
    request.session["authenticated"] = True
    request.session["session_id"] = session_id
    request.session["usuario_id"] = usuario_id

    request.session["user_email"] = str(
        dados_usuario.get("email") or email or ""
    ).strip()

    request.session["auth_source"] = str(
        dados_usuario.get("origem") or "keepedu"
    )

    # Salva no banco/cache
    salvar_sessao_usuario(
        usuario_id,
        session_id
    )
    
    redirecionamento = RedirectResponse(
        url=_destino_pos_login(next_url),
        status_code=303
    )

    if lembre_me and dados_usuario:
        usuario_id = dados_usuario.get("id") or 1
        gerenciar_lembre_me(redirecionamento, usuario_id)

    return redirecionamento


@router.get("/logout")
async def logout(request: Request, response: Response):
    # Verifica se existe o cookie de lembre-me e apaga do banco de dados
    token_cookie = request.cookies.get("remember_token")
    if token_cookie:
        remover_token_banco(token_cookie)
        
    # Limpa a sessão local da memória do FastAPI
    request.session.clear()
    
    # Cria a resposta limpando fisicamente o cookie do navegador
    resposta = RedirectResponse(url="/login", status_code=303)
    resposta.delete_cookie("remember_token")
    return resposta


@router.get("/bernoulli", response_class=HTMLResponse)
async def bernoulli(request: Request):
    return render_template(request, "bernoulli.html", {})


def _rotulo_dia_bernoulli(dia: str) -> str:
    return "1 dia" if str(dia) == "1" else "2 dia"


def _montar_logs_bernoulli(resultado: dict, nome_arquivo_entrada: str, nome_arquivo_download: str):
    return [
        {"tipo": "info", "titulo": "Arquivo recebido", "descricao": nome_arquivo_entrada},
        {"tipo": "info", "titulo": "Modo selecionado", "descricao": f"{_rotulo_dia_bernoulli(resultado.get('dia', '1'))} | q{resultado.get('primeira_questao', 1)} a q{resultado.get('ultima_questao', 90)}"},
        {"tipo": "success", "titulo": "Estrutura validada", "descricao": f"{resultado['questoes_encontradas_no_keepedu']} coluna(s) de questao reconhecida(s)."},
        {"tipo": "success", "titulo": "Consulta Bernoulli concluida", "descricao": f"{resultado['rmb_encontrados']} RMB(s) localizado(s) e {resultado['sem_rmb']} pendencia(s) de inscricao."},
        {"tipo": "success", "titulo": "Arquivo pronto", "descricao": nome_arquivo_download}
    ]


def _processar_arquivo_bernoulli(caminho_keepedu, nome_arquivo_entrada: str, dia: str, progresso_callback=None):
    resultado = transformar_vetor_keepedu_para_bernoulli(
        caminho_arquivo_keepedu=caminho_keepedu, dia=dia, progresso_callback=progresso_callback
    )
    nome_saida_real = os.path.basename(str(resultado["caminho_saida"]))
    nome_arquivo_download = f"vetor_bernoulli_dia{resultado['dia']}_{resultado['linhas']}lin_q{resultado['primeira_questao']}-q{resultado['ultima_questao']}.xlsx"

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


def processar_arquivo_bernoulli_em_background(job_id: str, caminho_keepedu, nome_arquivo_entrada: str, dia: str):
    pasta_tmp = caminho_keepedu.parent
    def progresso_callback(percentual, mensagem, tipo=None, titulo=None, descricao="", resultado=None):
        atualizar_job(job_id, status="processando", percentual=percentual, mensagem=mensagem, arquivo_atual=nome_arquivo_entrada, resultado=resultado)
        if titulo:
            registrar_evento_job(job_id, tipo or "info", titulo, descricao or mensagem, arquivo=nome_arquivo_entrada)

    try:
        atualizar_job(job_id, status="processando", percentual=5, mensagem=f"Arquivo recebido. Preparando processamento...", arquivo_atual=nome_arquivo_entrada)
        registrar_evento_job(job_id, "info", "Arquivo recebido", nome_arquivo_entrada, arquivo=nome_arquivo_entrada)

        dados = _processar_arquivo_bernoulli(caminho_keepedu=caminho_keepedu, nome_arquivo_entrada=nome_arquivo_entrada, dia=dia, progresso_callback=progresso_callback)

        registrar_evento_job(job_id, "success", "Arquivo pronto", dados["nome_arquivo_download"], arquivo=nome_arquivo_entrada)
        atualizar_job(job_id, status="concluido", percentual=100, mensagem="Simulado Bernoulli gerado com sucesso.", arquivo_atual=nome_arquivo_entrada, resultado=_resultado_job_bernoulli(dados))
    except Exception as erro:
        atualizar_job(job_id, status="erro", percentual=100, mensagem="Erro ao gerar o Simulado Bernoulli.", arquivo_atual=nome_arquivo_entrada, erro=str(erro))
        registrar_evento_job(job_id, "error", "Falha na conversao", str(erro), arquivo=nome_arquivo_entrada)
    finally:
        for arquivo in pasta_tmp.glob("*"):
            try: arquivo.unlink(missing_ok=True)
            except Exception: pass
        try: pasta_tmp.rmdir()
        except Exception: pass


@router.post("/bernoulli/processar")
async def bernoulli_processar(arquivo_keepedu: UploadFile = File(...), dia: str = Form("1")):
    try:
        dados = await executar_processamento_bernoulli(arquivo_keepedu, dia=dia)
        return FileResponse(
            str(PASTA_BERNOULLI / dados["nome_arquivo_real"]),
            filename=dados["nome_arquivo_download"],
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        return HTMLResponse(f"<h1>Erro</h1><p>{escape(str(e))}</p>", status_code=400)


@router.post("/bernoulli/processar-ajax")
async def bernoulli_processar_ajax(background_tasks: BackgroundTasks, arquivo_keepedu: UploadFile = File(...), dia: str = Form("1")):
    job_id = criar_job(total_arquivos=1)
    pasta_tmp = PASTA_UPLOADS_TEMP / f"bernoulli_{job_id}"
    pasta_tmp.mkdir(parents=True, exist_ok=True)
    try:
        caminho_keepedu = await salvar_arquivo_upload(arquivo_keepedu, pasta_tmp)
        nome_arquivo_entrada = os.path.basename(arquivo_keepedu.filename or caminho_keepedu.name)
        atualizar_job(job_id, status="processando", percentual=3, mensagem="Aguardando início...", arquivo_atual=nome_arquivo_entrada)
        background_tasks.add_task(processar_arquivo_bernoulli_em_background, job_id, caminho_keepedu, nome_arquivo_entrada, dia)
        return JSONResponse({"status": "ok", "job_id": job_id})
    except Exception as erro:
        atualizar_job(job_id, status="erro", percentual=100, mensagem="Erro", erro=str(erro))
        return JSONResponse({"status": "erro", "mensagem": str(erro)}, status_code=400)


@router.get("/bernoulli/download/{nome_arquivo}")
async def bernoulli_download(nome_arquivo: str):
    nome_seguro = os.path.basename(nome_arquivo or "")
    caminho_saida = (PASTA_BERNOULLI / nome_seguro).resolve()
    if not caminho_saida.exists():
        return HTMLResponse("<h1>Arquivo não encontrado.</h1>", status_code=404)
    return FileResponse(str(caminho_saida), filename=nome_seguro)


@router.post("/nova-avaliacao-pasta")
async def rota_nova_avaliacao_pasta(pasta_origem: str = Form(...)):
    try:
        nome_avaliacao = processar_pasta_local(pasta_origem)
        return RedirectResponse(url=f"/avaliacao/{nome_avaliacao}", status_code=303)
    except Exception as e:
        return HTMLResponse(f"<h1>Erro</h1><p>{escape(str(e))}</p>", status_code=400)


# CORREÇÃO AQUI: Esta rota agora responde com JSON Puro para alinhar com o JavaScript AJAX
@router.post("/processar-ajax")
async def rota_nova_avaliacao_upload(
    background_tasks: BackgroundTasks,
    arquivos: list[UploadFile] = File(...)
):
    job_id = criar_job(total_arquivos=len(arquivos))
    pasta_upload = PASTA_UPLOADS_TEMP / f"upload_{job_id}"
    pasta_upload.mkdir(parents=True, exist_ok=True)

    try:
        total_salvos = await salvar_uploads_em_pasta(arquivos, pasta_upload)
        if total_salvos == 0:
            atualizar_job(job_id, status="erro", percentual=100, mensagem="Nenhuma imagem válida.", erro="Sem arquivos válidos.")
            return JSONResponse({"status": "erro", "job_id": job_id, "mensagem": "Nenhuma imagem válida foi enviada."})

        atualizar_job(job_id, status="processando", percentual=5, mensagem=f"{total_salvos} imagem(ns) recebida(s). Lendo...")
        background_tasks.add_task(processar_pasta_temporaria_com_progresso, job_id, pasta_upload)
        
        return JSONResponse({"status": "ok", "job_id": job_id})
    except Exception as e:
        atualizar_job(job_id, status="erro", percentual=100, mensagem="Erro", erro=str(e))
        return JSONResponse({"status": "erro", "job_id": job_id, "mensagem": str(e)})


@router.get("/avaliacao/{nome_avaliacao}", response_class=HTMLResponse)
async def ver_avaliacao(request: Request, nome_avaliacao: str):
    imagens_debug = listar_imagens_debug(nome_avaliacao)
    resumo = resumo_processamento(nome_avaliacao)
    return render_template(
        request,
        "processamento.html",
        {
            "nome_processamento": nome_avaliacao,
            "imagens_debug": imagens_debug,
            "resumo": resumo,
        },
    )


@router.get("/imagem/{nome_avaliacao}/{nome_imagem}")
async def servir_imagem(nome_avaliacao: str, nome_imagem: str):
    caminho = caminho_imagem_debug(nome_avaliacao, nome_imagem)
    if not caminho.exists():
        leituras = carregar_json(caminho_leituras(nome_avaliacao), {})
        caminho = localizar_imagem_original(nome_avaliacao, nome_imagem, leituras)
    if not caminho or not caminho.exists():
        return JSONResponse({"erro": "Imagem não encontrada."}, status_code=404)
    return FileResponse(str(caminho))


@router.get("/leituras/{nome_avaliacao}")
async def obter_leituras(nome_avaliacao: str):
    caminho = carregar_leitura(nome_avaliacao, em_json=True)
    if not caminho or not caminho.exists():
        return JSONResponse({})
    return FileResponse(str(caminho), media_type="application/json")


@router.get("/download-log/{nome_avaliacao}")
async def download_log(nome_avaliacao: str):
    caminho = caminho_log(nome_avaliacao)
    if not caminho.exists():
        return JSONResponse({"erro": "Log não encontrado."}, status_code=404)
    return FileResponse(str(caminho), filename=f"log_avaliacao_{nome_avaliacao}.csv")


@router.get("/correcoes/{nome_avaliacao}")
async def obter_correcoes(nome_avaliacao: str):
    caminho = caminho_correcoes_web(nome_avaliacao)
    if not caminho.exists():
        return JSONResponse({})
    return FileResponse(str(caminho), media_type="application/json")


@router.post("/correcoes/{nome_avaliacao}")
async def salvar_correcoes(nome_avaliacao: str, payload: CorrecoesPayload):
    caminho = caminho_correcoes_web(nome_avaliacao)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(payload.correcoes, f, ensure_ascii=False, indent=4)
    return {"status": "ok", "arquivo": str(caminho)}


@router.post("/reprocessar-imagem/{nome_avaliacao}")
async def rota_reprocessar_imagem(nome_avaliacao: str, payload: ReprocessarImagemPayload):
    try:
        return JSONResponse(reprocessar_imagem_processamento(nome_processamento=nome_avaliacao, nome_imagem=payload.nome_imagem, pontos_cantos=payload.pontos_cantos))
    except Exception as e:
        return JSONResponse({"status": "erro", "mensagem": str(e)}, status_code=400)


@router.get("/gerar-csv/{nome_avaliacao}")
async def rota_gerar_csv(nome_avaliacao: str, forcar: bool = False):
    resultado = gerar_csv_final(nome_avaliacao, forcar=forcar)
    if resultado["status"] != "ok":
        return JSONResponse(resultado, status_code=400)
    return RedirectResponse(url=f"/download-csv/{nome_avaliacao}", status_code=303)


@router.get("/download-csv/{nome_avaliacao}")
async def rota_download_csv(nome_avaliacao: str):
    caminho = caminho_csv_final(nome_avaliacao)
    if not caminho.exists():
        return JSONResponse({"erro": "CSV não encontrado."}, status_code=404)
    return FileResponse(str(caminho), filename=f"{nome_avaliacao}_csv_final.csv", media_type="text/csv")


@router.post("/importar-respostas-presenciais")
async def rota_importar_respostas_presenciais(payload: ImportarRespostasPayload):

    # Pegamos o nome que veio no payload ou usamos o idAval como fallback seguro
    nome_lote = payload.nome_processamento or f"avaliacao_{payload.idAval}"

    # PASSO 1 — Importa vetores/respostas
    resultado = importar_respostas_presenciais(
        nome_lote,
        id_aval=payload.idAval,
        dia_aval=payload.diaAval,
        usuario_id=payload.usuario_id,
        id_aluno=payload.idAluno
    )

    # Se deu erro nos vetores, já encerra
    if resultado.get("status") == "erro":
        return JSONResponse(resultado, status_code=400)

    # PASSO 2 — Upload das imagens originais
    resultado_imagens = importar_imagens_folha_resposta(
        nome_processamento=nome_lote,
        id_aval=payload.idAval
    )

    # Retorno final
    return JSONResponse({
        "status": "ok",
        "vetores": resultado,
        "imagens": resultado_imagens
    })
    

@router.post("/importar-respostas-presenciais-ajax/{nome_avaliacao}")
async def rota_importar_respostas_presenciais_ajax(nome_avaliacao: str, payload: ImportarRespostasPayload, background_tasks: BackgroundTasks):
    total_arquivos = contar_alunos_importacao(nome_avaliacao, id_aluno=payload.idAluno)
    job_id = criar_job(total_arquivos=total_arquivos)
    background_tasks.add_task(_executar_importacao_respostas_em_background, job_id, nome_avaliacao, payload, "importacao")
    return JSONResponse({"status": "ok", "job_id": job_id, "mensagem": "Envio de Vetores iniciado."})


@router.post("/simular-importacao-respostas-presenciais/{nome_avaliacao}")
async def rota_simular_importacao_respostas_presenciais(nome_avaliacao: str, payload: ImportarRespostasPayload):
    resultado = simular_importacao_respostas_presenciais(nome_avaliacao=nome_avaliacao, id_aval=payload.idAval, dia_aval=payload.diaAval, usuario_id=payload.usuario_id, id_aluno=payload.idAluno)
    if resultado.get("status") == "erro": return JSONResponse(resultado, status_code=400)
    return JSONResponse(resultado)


@router.post("/simular-importacao-respostas-presenciais-ajax/{nome_avaliacao}")
async def rota_simular_importacao_respostas_presenciais_ajax(nome_avaliacao: str, payload: ImportarRespostasPayload, background_tasks: BackgroundTasks):
    total_arquivos = contar_alunos_importacao(nome_avaliacao, id_aluno=payload.idAluno)
    job_id = criar_job(total_arquivos=total_arquivos)
    background_tasks.add_task(_executar_importacao_respostas_em_background, job_id, nome_avaliacao, payload, "simulacao")
    return JSONResponse({"status": "ok", "job_id": job_id, "mensagem": "Simulação de Vetores iniciada."})


@router.post("/mock/importar-respostas-presenciais")
async def mock_importar_respostas_presenciais(request: Request):
    try: dados = await request.json()
    except Exception: return JSONResponse({"success": False, "mensagem": ["JSON inválido."]}, status_code=400)
    status_code, resposta = processar_mock_importacao_keepedu(dados)
    return JSONResponse(resposta, status_code=status_code)


@router.post("/validacao/manual/{nome_avaliacao}")
async def rota_salvar_validacao_manual(request: Request, nome_avaliacao: str, nome_imagem: str = Form(...), id_aluno_manual: str = Form(...)):
    try:
        registro = salvar_correcao_manual(nome_processamento=nome_avaliacao, nome_imagem=nome_imagem, valor_manual=id_aluno_manual)
        aceita_json = "application/json" in (request.headers.get("accept") or "").lower() or (request.headers.get("x-requested-with") or "").lower() == "fetch"
        if aceita_json: return JSONResponse({"status": "ok", "nome_imagem": nome_imagem, "registro": registro})
        return RedirectResponse(url=f"/validacao/{nome_avaliacao}", status_code=303)
    except Exception as e:
        return JSONResponse({"status": "erro", "mensagem": str(e)}, status_code=400)


@router.get("/status-processamento/{job_id}")
async def status_processamento(job_id: str):
    return JSONResponse(obter_job(job_id))


@router.post("/nova-avaliacao-ajax")
async def rota_nova_avaliacao_ajax(background_tasks: BackgroundTasks, arquivos: list[UploadFile] = File(...)):
    job_id = criar_job(total_arquivos=len(arquivos))
    pasta_upload = PASTA_UPLOADS_TEMP / f"upload_{job_id}"
    pasta_upload.mkdir(parents=True, exist_ok=True)
    try:
        total_salvos = await salvar_uploads_em_pasta(arquivos, pasta_upload)
        if total_salvos == 0: return JSONResponse({"status": "erro", "job_id": job_id, "mensagem": "Nenhuma imagem válida."})
        atualizar_job(job_id, status="processando", percentual=5, mensagem="Lendo imagens...")
        background_tasks.add_task(processar_pasta_temporaria_com_progresso, job_id, pasta_upload)
        return JSONResponse({"status": "ok", "job_id": job_id})
    except Exception as e:
        return JSONResponse({"status": "erro", "job_id": job_id, "mensagem": str(e)})
    
# Rota de compatibilidade para a tela de monitoramento/detalhes
@router.get("/processamento/{nome_avaliacao}")
async def redirecionar_processamento_antigo(nome_avaliacao: str):
    return RedirectResponse(url=f"/avaliacao/{nome_avaliacao}", status_code=301)

# Rota de compatibilidade caso o sistema tente monitorar o progresso com o nome antigo
@router.get("/processando/{job_id}", response_class=HTMLResponse)
async def tela_processando_compatibilidade(request: Request, job_id: str):
    return render_template(request, "processando.html", {"job_id": job_id})

def extrair_nome_lote_seguro(parametro: str) -> str:
    """
    Decodifica a URL e extrai o nome do lote mesmo se o frontend 
    enviar um dicionário Python formatado como string.
    """
    texto_puro = unquote(parametro).strip()
    
    # Se o frontend enviou um dicionário mascarado de string (ex: {'nome': '...'})
    if texto_puro.startswith("{") and ("['nome']" in texto_puro or "'nome'" in texto_puro):
        try:
            dados_dict = ast.literal_eval(texto_puro)
            if isinstance(dados_dict, dict) and "nome" in dados_dict:
                return str(dados_dict["nome"])
        except Exception:
            pass
            
    return texto_puro

@router.get("/validacao/{nome_avaliacao:path}", response_class=HTMLResponse)
async def validacao_cadastral(request: Request, nome_avaliacao: str):
    # Limpa a sujeira do link se ela existir
    nome_limpo = extrair_nome_lote_seguro(nome_avaliacao)
    
    # Se detectou que veio o dicionário no link, faz o redirecionamento limpo
    if nome_limpo != nome_avaliacao:
        return RedirectResponse(url=f"/validacao/{nome_limpo}", status_code=303)

    caminho = carregar_leitura(nome_limpo, em_json=True)
    if not caminho or not caminho.exists():
        return HTMLResponse("<h1>Avaliação não encontrada.</h1><p>O lote solicitado não existe no diretório.</p>", status_code=404)

    dados_validacao = gerar_validacao_cadastral(nome_limpo)
    resumo = dados_validacao["resumo"]
    return render_template(request, "validacao.html", {
        "nome_processamento": nome_limpo,
        "resumo": resumo,
        "validacoes": dados_validacao["validacoes"],
        "importacao_defaults": {"id_aval": resumo.get("id_prova_processamento") or ID_PROVA_KEEPEDU}
    })

@router.get("/correcao/{nome_avaliacao:path}", response_class=HTMLResponse)
async def correcao(request: Request, nome_avaliacao: str):
    # Limpa a sujeira do link se ela existir
    nome_limpo = extrair_nome_lote_seguro(nome_avaliacao)
    
    # Se detectou que veio o dicionário no link, faz o redirecionamento limpo
    if nome_limpo != nome_avaliacao:
        return RedirectResponse(url=f"/correcao/{nome_limpo}", status_code=303)

    imagens_debug = listar_imagens_debug(nome_limpo)
    return render_template(request, "correcao.html", {
        "nome_processamento": nome_limpo,
        "imagens_debug": imagens_debug
    })
    
@router.get("/painel", response_class=HTMLResponse)
async def painel(request: Request):
    processamentos = listar_processamentos_recentes()

    return render_template(
        request,
        "index.html",
        {"processamentos": processamentos}
    )
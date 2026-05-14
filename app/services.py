import os
import shutil
from datetime import datetime

from app.settings import PASTA_PROCESSAMENTOS, PASTA_UPLOADS_TEMP
from omr_reader import processar_imagens_omr
from app.progresso import atualizar_job


EXTENSOES_IMAGEM = [".jpg", ".jpeg", ".png"]


def listar_processamentos():
    itens = []

    for pasta in sorted(PASTA_PROCESSAMENTOS.glob("processamento_*"), reverse=True):
        if pasta.is_dir():
            itens.append({
                "nome": pasta.name,
                "caminho": str(pasta)
            })

    return itens


def listar_imagens_debug(nome_processamento: str):
    pasta_debug = PASTA_PROCESSAMENTOS / nome_processamento / "debug_omr"

    if not pasta_debug.exists():
        return []

    imagens = []

    for arquivo in sorted(pasta_debug.iterdir()):
        if arquivo.suffix.lower() in EXTENSOES_IMAGEM:
            if arquivo.name.startswith("template_"):
                imagens.append(arquivo.name)

    return imagens


def processar_pasta_local(pasta_origem: str):
    pasta_origem = pasta_origem.strip().strip('"')

    if not os.path.exists(pasta_origem):
        raise FileNotFoundError(f"Pasta não encontrada: {pasta_origem}")

    if not os.path.isdir(pasta_origem):
        raise NotADirectoryError(f"O caminho informado não é uma pasta: {pasta_origem}")

    resultado = processar_imagens_omr(
        pasta_origem,
        pasta_saida=str(PASTA_PROCESSAMENTOS)
    )

    return os.path.basename(resultado["pasta_processamento"])


async def processar_uploads(arquivos):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta_upload = PASTA_UPLOADS_TEMP / f"upload_{timestamp}"
    pasta_upload.mkdir(parents=True, exist_ok=True)

    try:
        for arquivo in arquivos:
            # Quando o navegador envia uma pasta, o filename pode vir com subpastas.
            # Aqui pegamos apenas o nome final do arquivo para evitar erro de diretório.
            nome_arquivo = os.path.basename(arquivo.filename)

            if not nome_arquivo:
                continue

            extensao = os.path.splitext(nome_arquivo)[1].lower()

            if extensao not in EXTENSOES_IMAGEM:
                continue

            destino = pasta_upload / nome_arquivo

            with open(destino, "wb") as f:
                conteudo = await arquivo.read()
                f.write(conteudo)

        resultado = processar_imagens_omr(
            str(pasta_upload),
            pasta_saida=str(PASTA_PROCESSAMENTOS)
        )

        return os.path.basename(resultado["pasta_processamento"])

    finally:
        shutil.rmtree(pasta_upload, ignore_errors=True)


def caminho_imagem_debug(nome_processamento: str, nome_imagem: str):
    return PASTA_PROCESSAMENTOS / nome_processamento / "debug_omr" / nome_imagem


def caminho_leituras(nome_processamento: str):
    return PASTA_PROCESSAMENTOS / nome_processamento / "leituras_omr.json"


def caminho_log(nome_processamento: str):
    return PASTA_PROCESSAMENTOS / nome_processamento / "log_leitura_omr.csv"


def caminho_correcoes_web(nome_processamento: str):
    pasta_manual = PASTA_PROCESSAMENTOS / nome_processamento / "manual_omr"
    pasta_manual.mkdir(parents=True, exist_ok=True)

    return pasta_manual / "correcoes_web.json"

def processar_pasta_temporaria_com_progresso(job_id, pasta_upload):
    try:
        atualizar_job(
            job_id,
            status="processando",
            percentual=10,
            mensagem="Arquivos recebidos. Iniciando leitura OMR..."
        )

        arquivos = [
            arquivo for arquivo in pasta_upload.iterdir()
            if arquivo.suffix.lower() in EXTENSOES_IMAGEM
        ]

        total = len(arquivos)

        if total == 0:
            raise ValueError("Nenhuma imagem válida encontrada para processamento.")

        def progresso_callback(atual, total_arquivos, nome_arquivo=""):
            percentual = 10 + int((atual / total_arquivos) * 85)

            atualizar_job(
                job_id,
                status="processando",
                percentual=percentual,
                mensagem=f"Lendo cartão {atual} de {total_arquivos}...",
                arquivo_atual=nome_arquivo
            )

        try:
            resultado = processar_imagens_omr(
                str(pasta_upload),
                pasta_saida=str(PASTA_PROCESSAMENTOS),
                progresso_callback=progresso_callback
            )

        except TypeError:
            atualizar_job(
                job_id,
                status="processando",
                percentual=35,
                mensagem="Lendo cartões OMR..."
            )

            resultado = processar_imagens_omr(
                str(pasta_upload),
                pasta_saida=str(PASTA_PROCESSAMENTOS)
            )

        nome_processamento = os.path.basename(resultado["pasta_processamento"])

        atualizar_job(
            job_id,
            status="concluido",
            percentual=100,
            mensagem="Processamento concluído.",
            nome_processamento=nome_processamento
        )

    except Exception as e:
        atualizar_job(
            job_id,
            status="erro",
            percentual=100,
            mensagem="Erro durante o processamento.",
            erro=str(e)
        )

    finally:
        shutil.rmtree(pasta_upload, ignore_errors=True)
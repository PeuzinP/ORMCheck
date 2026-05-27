import os
import csv
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from app.settings import PASTA_PROCESSAMENTOS, PASTA_UPLOADS_TEMP
from app.time_utils import agora_local, fromtimestamp_local
from omr_reader import (
    processar_imagens_omr,
    detectar_respostas_por_template,
    caminho_modelo_omr_padrao
)
from app.progresso import atualizar_job, registrar_evento_job


EXTENSOES_IMAGEM = [".jpg", ".jpeg", ".png"]


def _obter_data_hora_processamento(nome_pasta: str, pasta: Path) -> datetime:
    candidatos = [
        pasta / "log_leitura_omr.csv",
        pasta / "leituras_omr.json",
        pasta
    ]

    for candidato in candidatos:
        if candidato.exists():
            try:
                return fromtimestamp_local(candidato.stat().st_mtime)
            except OSError:
                pass

    match = re.match(r"^processamento_(\d{8})_(\d{6})$", str(nome_pasta or "").strip())

    if match:
        try:
            return datetime.strptime(f"{match.group(1)}_{match.group(2)}", "%Y%m%d_%H%M%S")
        except ValueError:
            pass

    return agora_local()


def _formatar_data_hora_processamento(nome_pasta: str, pasta: Path) -> tuple[str, str]:
    data_hora = _obter_data_hora_processamento(nome_pasta, pasta)
    return (
        data_hora.strftime("%d/%m/%Y"),
        data_hora.strftime("%H:%M:%S")
    )


def _rotulo_data_processamento(nome_pasta: str, pasta: Path) -> str:
    data_hora = _obter_data_hora_processamento(nome_pasta, pasta)
    hoje = agora_local().date()
    data_referencia = data_hora.date()

    if data_referencia == hoje:
        return "Hoje"
    if data_referencia == hoje.fromordinal(hoje.toordinal() - 1):
        return "Ontem"

    dias_semana = {
        0: "Segunda",
        1: "Terça",
        2: "Quarta",
        3: "Quinta",
        4: "Sexta",
        5: "Sábado",
        6: "Domingo",
    }
    return dias_semana.get(data_referencia.weekday(), "Lote")


from pathlib import Path
import os

def listar_processamentos():
    """
    Lista todos os lotes de cartões-resposta escaneados a partir
    do diretório configurado pelo aplicativo.
    """
    nomes_lotes = []

    if PASTA_PROCESSAMENTOS.exists() and PASTA_PROCESSAMENTOS.is_dir():
        for subpasta in PASTA_PROCESSAMENTOS.iterdir():
            if subpasta.is_dir() and not subpasta.name.startswith("."):
                nomes_lotes.append(subpasta.name)

    return sorted(nomes_lotes, reverse=True)


def listar_processamentos_recentes():
    """
    Monta os metadados exibidos na home para os lotes recentes.
    """
    lotes = []

    if not PASTA_PROCESSAMENTOS.exists() or not PASTA_PROCESSAMENTOS.is_dir():
        return lotes

    for subpasta in PASTA_PROCESSAMENTOS.iterdir():
        if not subpasta.is_dir() or subpasta.name.startswith("."):
            continue

        data_texto, hora_texto = _formatar_data_hora_processamento(subpasta.name, subpasta)
        lotes.append(
            {
                "nome": subpasta.name,
                "titulo": subpasta.name.replace("_", " "),
                "rotulo": _rotulo_data_processamento(subpasta.name, subpasta),
                "data": data_texto,
                "hora": hora_texto,
                "timestamp": _obter_data_hora_processamento(subpasta.name, subpasta),
            }
        )

    lotes.sort(key=lambda item: item["timestamp"], reverse=True)

    for item in lotes:
        item.pop("timestamp", None)

    return lotes


def resumo_processamento(nome_processamento: str):
    caminho_csv = caminho_log(nome_processamento)
    resumo = {
        "total_imagens": 0,
        "total_ok": 0,
        "total_erro": 0,
        "total_manual": 0,
        "total_pendencias": 0
    }

    if not caminho_csv.exists():
        return resumo

    with open(caminho_csv, "r", encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f, delimiter=";")
        linhas = list(leitor)

    resumo["total_imagens"] = len(linhas)
    resumo["total_ok"] = sum(1 for linha in linhas if linha.get("status") == "OK")
    resumo["total_erro"] = sum(1 for linha in linhas if linha.get("status") == "ERRO")
    resumo["total_manual"] = sum(1 for linha in linhas if linha.get("correcao_manual") == "SIM")

    caminho_json = caminho_leituras(nome_processamento)
    leituras = carregar_json(caminho_json, {})
    resumo["total_pendencias"] = sum(
        1
        for dados in leituras.values()
        if (dados.get("erros") or []) or int(dados.get("total_pendencias_confianca", 0) or 0) > 0
    )

    return resumo


def listar_imagens_debug(nome_processamento: str):
    pasta_debug = PASTA_PROCESSAMENTOS / nome_processamento / "debug_omr"
    imagens = set()

    if pasta_debug.exists():
        for arquivo in pasta_debug.iterdir():
            if arquivo.suffix.lower() in EXTENSOES_IMAGEM and arquivo.name.startswith("template_"):
                imagens.add(arquivo.name)

    caminho_leitura = caminho_leituras(nome_processamento)
    leituras = carregar_json(caminho_leitura, {})

    for nome_imagem in leituras.keys():
        if str(nome_imagem).startswith("template_"):
            imagens.add(str(nome_imagem))

    return sorted(imagens)


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
    timestamp = agora_local().strftime("%Y%m%d_%H%M%S")
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

def carregar_leitura(nome_avaliacao: str, em_json: bool = True):
    """
    Resolve o arquivo principal do lote a partir do diretório configurado.
    """
    caminho_principal = caminho_leituras(nome_avaliacao)
    if caminho_principal.exists():
        return caminho_principal

    nome_puro = str(nome_avaliacao or "").replace("processamento_", "")
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

def caminho_leituras(nome_processamento: str):
    return PASTA_PROCESSAMENTOS / nome_processamento / "leituras_omr.json"


def caminho_log(nome_processamento: str):
    return PASTA_PROCESSAMENTOS / nome_processamento / "log_leitura_omr.csv"


def caminho_correcoes_web(nome_processamento: str):
    pasta_manual = PASTA_PROCESSAMENTOS / nome_processamento / "manual_omr"
    pasta_manual.mkdir(parents=True, exist_ok=True)

    return pasta_manual / "correcoes_web.json"


def caminho_pasta_processamento(nome_processamento: str):
    return PASTA_PROCESSAMENTOS / nome_processamento


def caminho_originais(nome_processamento: str):
    pasta = caminho_pasta_processamento(nome_processamento) / "originais"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def caminho_manual_arquivo(nome_processamento: str, nome_arquivo: str):
    pasta_manual = caminho_pasta_processamento(nome_processamento) / "manual_omr"
    pasta_manual.mkdir(parents=True, exist_ok=True)
    nome_json = f"{os.path.splitext(nome_arquivo)[0]}.json"
    return pasta_manual / nome_json


def normalizar_nome_arquivo_debug(nome_imagem: str):
    return nome_imagem[9:] if nome_imagem.startswith("template_") else nome_imagem


def carregar_json(caminho, padrao):
    if not caminho.exists():
        return padrao

    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)


def pontos_cantos_para_lista(pontos_cantos):
    if not pontos_cantos:
        return None

    chaves = ["TOP_LEFT", "TOP_RIGHT", "BOTTOM_LEFT", "BOTTOM_RIGHT"]
    pontos = []

    for chave in chaves:
        ponto = pontos_cantos.get(chave) if isinstance(pontos_cantos, dict) else None

        if not ponto:
            return None

        pontos.append([float(ponto["x"]), float(ponto["y"])])

    return pontos


def localizar_imagem_original(nome_processamento: str, nome_imagem: str, leituras: dict):
    nome_arquivo = normalizar_nome_arquivo_debug(nome_imagem)
    candidatos = [
        caminho_originais(nome_processamento) / nome_arquivo,
        caminho_pasta_processamento(nome_processamento) / "pendencias" / nome_arquivo,
    ]

    leitura_atual = leituras.get(nome_imagem, {})
    caminho_salvo = leitura_atual.get("caminho_original_processamento", "")

    if caminho_salvo:
        candidatos.append(caminho_salvo)

    caminho_manual = caminho_manual_arquivo(nome_processamento, nome_arquivo)

    if caminho_manual.exists():
        dados_manual = carregar_json(caminho_manual, {})
        candidatos.extend([
            dados_manual.get("caminho_imagem_pendencia", ""),
            dados_manual.get("caminho_imagem", "")
        ])

    for candidato in candidatos:
        if not candidato:
            continue

        caminho = candidato if hasattr(candidato, "exists") else Path(str(candidato))

        if caminho.exists():
            return caminho

    return None


def atualizar_log_processamento(nome_processamento: str, nome_arquivo: str, resultado: dict, detalhe: str, caminho_manual: str):
    caminho = caminho_log(nome_processamento)

    if not caminho.exists():
        return

    with open(caminho, "r", encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f, delimiter=";")
        linhas = list(leitor)
        cabecalho = leitor.fieldnames or []

    if not cabecalho:
        return

    erros = resultado.get("erros", []) or []
    precisa_correcao_manual = "SIM" if erros else "NÃO"

    atualizacao = {
        "arquivo": nome_arquivo,
        "status": "OK",
        "registro_academico": resultado.get("registro_academico", ""),
        "codigo_barras": resultado.get("codigo_barras", ""),
        "total_perguntas_modelo": str(resultado.get("total_perguntas_modelo", 0)),
        "total_respostas_lidas": str(resultado.get("total_respostas_lidas", 0)),
        "total_erros": str(len(erros)),
        "correcao_manual": precisa_correcao_manual,
        "arquivo_manual": caminho_manual,
        "erros": " | ".join(erros),
        "debug_bolhas": resultado.get("debug_bolhas", ""),
        "debug_cantos": resultado.get("debug_cantos", ""),
        "detalhe": detalhe
    }

    linha_encontrada = False

    for linha in linhas:
        if linha.get("arquivo") == nome_arquivo:
            linha.update(atualizacao)
            linha_encontrada = True
            break

    if not linha_encontrada:
        nova_linha = {coluna: "" for coluna in cabecalho}
        nova_linha.update(atualizacao)
        linhas.append(nova_linha)

    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=cabecalho, delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)


def reprocessar_imagem_processamento(nome_processamento: str, nome_imagem: str, pontos_cantos: dict | None = None):
    caminho_leitura = caminho_leituras(nome_processamento)
    leituras = carregar_json(caminho_leitura, {})

    caminho_imagem = localizar_imagem_original(nome_processamento, nome_imagem, leituras)

    if caminho_imagem is None:
        raise FileNotFoundError(
            "Nao foi possivel localizar a imagem original deste processamento. "
            "Gere um novo processamento para habilitar o reprocessamento por cantos."
        )

    caminho_modelo = caminho_modelo_omr_padrao()

    if not os.path.exists(caminho_modelo):
        raise FileNotFoundError(f"Modelo .xtmpl nao encontrado: {caminho_modelo}")

    pontos_override = pontos_cantos_para_lista(pontos_cantos)
    pasta_debug = caminho_pasta_processamento(nome_processamento) / "debug_omr"
    pasta_debug.mkdir(parents=True, exist_ok=True)

    resultado, detalhe = detectar_respostas_por_template(
        str(caminho_imagem),
        caminho_modelo,
        str(pasta_debug),
        pontos_imagem_override=pontos_override
    )

    if not resultado:
        raise ValueError(detalhe)

    nome_arquivo = normalizar_nome_arquivo_debug(nome_imagem)
    leitura_atual = leituras.get(nome_imagem, {})
    leitura_atual.update({
        "arquivo_original": nome_arquivo,
        "caminho_original_processamento": str(caminho_imagem),
        "respostas": resultado.get("respostas", {}),
        "pontos_mapeados": resultado.get("pontos_mapeados", {}),
        "pontos_cantos": resultado.get("pontos_cantos", {}),
        "origem_cantos": resultado.get("origem_cantos", "AUTO"),
        "registro_academico": resultado.get("registro_academico", ""),
        "codigo_barras": resultado.get("codigo_barras", ""),
        "debug_bolhas": resultado.get("debug_bolhas", ""),
        "erros": resultado.get("erros", []),
        "confianca_questoes": resultado.get("confianca_questoes", {}),
        "pendencias_confianca": resultado.get("pendencias_confianca", []),
        "total_pendencias_confianca": resultado.get("total_pendencias_confianca", 0)
    })
    leituras[nome_imagem] = leitura_atual
    leitura_atual["status_revisao"] = "PENDENTE"
    salvar_json(caminho_leitura, leituras)

    caminho_manual = caminho_manual_arquivo(nome_processamento, nome_arquivo)
    erros = resultado.get("erros", []) or []

    if erros:
        salvar_json(caminho_manual, {
            "arquivo": nome_arquivo,
            "caminho_imagem": str(caminho_imagem),
            "caminho_imagem_pendencia": str(caminho_pasta_processamento(nome_processamento) / "pendencias" / nome_arquivo),
            "registro_academico": resultado.get("registro_academico", ""),
            "codigo_barras": resultado.get("codigo_barras", ""),
            "respostas": resultado.get("respostas", {}),
            "erros": erros,
            "pontos_mapeados": resultado.get("pontos_mapeados", {}),
            "corrigido_manualmente": resultado.get("origem_cantos", "") == "MANUAL"
        })
        caminho_manual_str = str(caminho_manual)
    else:
        if caminho_manual.exists():
            caminho_manual.unlink()
        caminho_manual_str = ""

    atualizar_log_processamento(
        nome_processamento,
        nome_arquivo,
        resultado,
        detalhe,
        caminho_manual_str
    )

    return {
        "status": "ok",
        "nome_imagem": nome_imagem,
        "arquivo_original": nome_arquivo,
        "detalhe": detalhe,
        "resultado": resultado
    }

def processar_pasta_temporaria_com_progresso(job_id, pasta_upload):
    nome_processamento = None
    try:
        arquivos = [
            arquivo for arquivo in pasta_upload.iterdir()
            if arquivo.suffix.lower() in EXTENSOES_IMAGEM
        ]
        total = len(arquivos)

        registrar_evento_job(
            job_id,
            tipo="info",
            titulo="Processamento iniciado",
            descricao="Arquivos recebidos e fila de leitura preparada."
        )
        atualizar_job(
            job_id,
            status="processando",
            percentual=10,
            mensagem="Arquivos recebidos. Iniciando leitura OMR...",
            resumo={
                "info": 0,
                "warning": 0,
                "error": 0,
                "success": 0,
                "total_eventos": 0,
                "total_imagens": total,
                "total_ok": 0,
                "total_erro": 0,
                "total_manual": 0
            }
        )

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

        def evento_callback(tipo, titulo, descricao="", arquivo=""):
            registrar_evento_job(
                job_id,
                tipo=tipo,
                titulo=titulo,
                descricao=descricao,
                arquivo=arquivo
            )

        try:
            resultado = processar_imagens_omr(
                str(pasta_upload),
                pasta_saida=str(PASTA_PROCESSAMENTOS),
                progresso_callback=progresso_callback,
                evento_callback=evento_callback
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
        resumo_atual = {
            "info": 0,
            "warning": 0,
            "error": 0,
            "success": 0,
            "total_eventos": 0,
            "total_imagens": int(resultado.get("total_imagens", 0)),
            "total_ok": int(resultado.get("total_ok", 0)),
            "total_erro": int(resultado.get("total_erro", 0)),
            "total_manual": int(resultado.get("total_manual", 0))
        }

        try:
            from app.progresso import obter_job
            resumo_atual.update(obter_job(job_id).get("resumo", {}))
            resumo_atual.update({
                "total_imagens": int(resultado.get("total_imagens", 0)),
                "total_ok": int(resultado.get("total_ok", 0)),
                "total_erro": int(resultado.get("total_erro", 0)),
                "total_manual": int(resultado.get("total_manual", 0))
            })
        except Exception:
            pass

        atualizar_job(
            job_id,
            status="concluido",
            percentual=100,
            mensagem="Processamento concluído.",
            nome_processamento=nome_processamento,
            resumo=resumo_atual
        )
        registrar_evento_job(
            job_id,
            tipo="success",
            titulo="Processamento concluído",
            descricao="Os arquivos já podem ser revisados no painel."
        )
    except Exception as e:
        registrar_evento_job(
            job_id,
            tipo="error",
            titulo="Erro durante o processamento",
            descricao=str(e)
        )
        atualizar_job(
            job_id,
            status="erro",
            percentual=100,
            mensagem="Erro durante o processamento.",
            erro=str(e)
        )

    finally:
        shutil.rmtree(pasta_upload, ignore_errors=True)
        
def limpar_pos_importacao_keepedu(nome_processamento: str, imagens_enviadas: list[str] | None = None):
    try:
        print(f"[LIMPEZA KEEPEDU] Iniciando limpeza para imagens enviadas em: {nome_processamento}")
        
        if not imagens_enviadas:
            print("[LIMPEZA KEEPEDU] Nenhuma imagem para limpar.")
            return

        pasta_processamento = caminho_pasta_processamento(nome_processamento)

        print(f"[DEBUG LIMPEZA] Pasta encontrada: {pasta_processamento}")
        print(f"[DEBUG LIMPEZA] Existe? {pasta_processamento.exists()}")

        pastas_para_remover = [
            pasta_processamento / "debug_omr",
            pasta_processamento / "originais",
            pasta_processamento / "pendencias",
            pasta_processamento / "manual_omr",
        ]

        for pasta in pastas_para_remover:
            print(f"[DEBUG LIMPEZA] Tentando remover: {pasta}")
            print(f"[DEBUG LIMPEZA] Existe? {pasta.exists()}")

            if pasta.exists() and pasta.is_dir():
                shutil.rmtree(pasta, ignore_errors=True)
                
        for nome_imagem_original in imagens_enviadas:
            # 1. Delete from debug_omr
            nome_debug = f"template_{nome_imagem_original}"
            caminho_debug = pasta_processamento / "debug_omr" / nome_debug
            if caminho_debug.exists():
                caminho_debug.unlink(missing_ok=True)

            # 2. Delete from originais
            caminho_original = pasta_processamento / "originais" / nome_imagem_original
            if caminho_original.exists():
                caminho_original.unlink(missing_ok=True)

            # 3. Delete from pendencias
            caminho_pendencia = pasta_processamento / "pendencias" / nome_imagem_original
            if caminho_pendencia.exists():
                caminho_pendencia.unlink(missing_ok=True)

            # 4. Delete from manual_omr
            nome_base_sem_ext = Path(nome_imagem_original).stem
            caminho_manual = pasta_processamento / "manual_omr" / f"{nome_base_sem_ext}.json"
            if caminho_manual.exists():
                caminho_manual.unlink(missing_ok=True)
        
        print(f"[LIMPEZA KEEPEDU] Limpeza de {len(imagens_enviadas)} imagem(ns) concluída.")
    except Exception as e:
        import traceback
        print("[ERRO LIMPEZA KEEPEDU]")
        traceback.print_exc()
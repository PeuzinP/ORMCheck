import json
from pathlib import Path
from threading import Lock
from datetime import datetime

from app.settings import CAMINHO_JOBS


JOBS_LOCK = Lock()


def _carregar_jobs():
    caminho = Path(CAMINHO_JOBS)

    if not caminho.exists():
        return {}

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _salvar_jobs(jobs):
    caminho = Path(CAMINHO_JOBS)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho_tmp = caminho.with_suffix(".tmp")

    with open(caminho_tmp, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

    caminho_tmp.replace(caminho)


def criar_job(total_arquivos=0):
    job_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    with JOBS_LOCK:
        jobs = _carregar_jobs()
        jobs[job_id] = {
            "job_id": job_id,
            "status": "aguardando",
            "percentual": 0,
            "mensagem": "Aguardando início do processamento...",
            "total_arquivos": total_arquivos,
            "arquivo_atual": "",
            "nome_processamento": "",
            "erro": "",
            "eventos": [],
            "atualizado_em": datetime.now().isoformat()
        }
        _salvar_jobs(jobs)

    return job_id


def atualizar_job(
    job_id,
    status=None,
    percentual=None,
    mensagem=None,
    arquivo_atual=None,
    nome_processamento=None,
    erro=None,
    eventos=None
):
    with JOBS_LOCK:
        jobs = _carregar_jobs()
        job = jobs.get(job_id)

        if not job:
            return

        if status is not None:
            job["status"] = status

        if percentual is not None:
            job["percentual"] = max(0, min(100, int(percentual)))

        if mensagem is not None:
            job["mensagem"] = mensagem

        if arquivo_atual is not None:
            job["arquivo_atual"] = arquivo_atual

        if nome_processamento is not None:
            job["nome_processamento"] = nome_processamento

        if erro is not None:
            job["erro"] = erro

        if eventos is not None:
            job["eventos"] = eventos

        job["atualizado_em"] = datetime.now().isoformat()
        jobs[job_id] = job
        _salvar_jobs(jobs)


def registrar_evento_job(job_id, tipo, titulo, descricao="", arquivo=""):
    with JOBS_LOCK:
        jobs = _carregar_jobs()
        job = jobs.get(job_id)

        if not job:
            return

        eventos = list(job.get("eventos", []))
        evento = {
            "tipo": str(tipo or "info"),
            "titulo": str(titulo or "").strip(),
            "descricao": str(descricao or "").strip(),
            "arquivo": str(arquivo or "").strip(),
            "criado_em": datetime.now().isoformat()
        }

        # Evita duplicidade em polling quando a mesma mensagem se repete.
        if not eventos or eventos[-1] != evento:
            eventos.append(evento)

        job["eventos"] = eventos[-20:]
        job["atualizado_em"] = datetime.now().isoformat()
        jobs[job_id] = job
        _salvar_jobs(jobs)


def obter_job(job_id):
    with JOBS_LOCK:
        jobs = _carregar_jobs()

    return jobs.get(job_id, {
        "job_id": job_id,
        "status": "nao_encontrado",
        "percentual": 0,
        "mensagem": "Processamento não encontrado.",
        "total_arquivos": 0,
        "arquivo_atual": "",
        "nome_processamento": "",
        "erro": "Job não encontrado.",
        "eventos": []
    })

import json
from pathlib import Path
from threading import Lock

from app.db import get_db_session, storage_usa_banco
from app.db_models import JobModel
from app.settings import CAMINHO_JOBS
from app.time_utils import agora_local


JOBS_LOCK = Lock()


def _normalizar_para_json(valor):
    if isinstance(valor, Path):
        return str(valor)

    if isinstance(valor, dict):
        return {
            str(chave): _normalizar_para_json(item)
            for chave, item in valor.items()
        }

    if isinstance(valor, (list, tuple, set)):
        return [_normalizar_para_json(item) for item in valor]

    return valor


def _carregar_jobs():
    caminho = Path(CAMINHO_JOBS)

    if not caminho.exists():
        return {}

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _resumo_padrao(total_arquivos=0):
    return {
        "info": 0,
        "warning": 0,
        "error": 0,
        "success": 0,
        "total_eventos": 0,
        "total_imagens": total_arquivos,
        "total_ok": 0,
        "total_erro": 0,
        "total_manual": 0
    }


def _job_padrao(job_id, total_arquivos=0):
    return {
        "job_id": job_id,
        "status": "aguardando",
        "percentual": 0,
        "mensagem": "Aguardando início do processamento...",
        "total_arquivos": total_arquivos,
        "arquivo_atual": "",
        "nome_processamento": "",
        "erro": "",
        "eventos": [],
        "resultado": {},
        "resumo": _resumo_padrao(total_arquivos),
        "atualizado_em": agora_local().isoformat()
    }


def _job_model_para_dict(job: JobModel) -> dict:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "percentual": job.percentual,
        "mensagem": job.mensagem,
        "total_arquivos": job.total_arquivos,
        "arquivo_atual": job.arquivo_atual,
        "nome_processamento": job.nome_processamento,
        "erro": job.erro,
        "eventos": list(job.eventos or []),
        "resultado": dict(job.resultado or {}),
        "resumo": dict(job.resumo or _resumo_padrao(job.total_arquivos)),
        "atualizado_em": (
            job.atualizado_em.isoformat()
            if job.atualizado_em else
            agora_local().isoformat()
        ),
    }


def _salvar_jobs(jobs):
    caminho = Path(CAMINHO_JOBS)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho_tmp = caminho.with_suffix(".tmp")

    with open(caminho_tmp, "w", encoding="utf-8") as f:
        json.dump(_normalizar_para_json(jobs), f, ensure_ascii=False, indent=2)

    caminho_tmp.replace(caminho)


def criar_job(total_arquivos=0):
    job_id = agora_local().strftime("%Y%m%d_%H%M%S_%f")

    if storage_usa_banco():
        with JOBS_LOCK, get_db_session() as session:
            dados_job = _job_padrao(job_id, total_arquivos)
            session.add(
                JobModel(
                    job_id=job_id,
                    status=dados_job["status"],
                    percentual=dados_job["percentual"],
                    mensagem=dados_job["mensagem"],
                    total_arquivos=dados_job["total_arquivos"],
                    arquivo_atual=dados_job["arquivo_atual"],
                    nome_processamento=dados_job["nome_processamento"],
                    erro=dados_job["erro"],
                    eventos=dados_job["eventos"],
                    resultado=dados_job["resultado"],
                    resumo=dados_job["resumo"],
                )
            )
        return job_id

    with JOBS_LOCK:
        jobs = _carregar_jobs()
        jobs[job_id] = _job_padrao(job_id, total_arquivos)
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
    eventos=None,
    resultado=None,
    resumo=None
):
    if storage_usa_banco():
        with JOBS_LOCK, get_db_session() as session:
            job = session.query(JobModel).filter(JobModel.job_id == job_id).one_or_none()

            if not job:
                return

            if status is not None:
                job.status = status

            if percentual is not None:
                job.percentual = max(0, min(100, int(percentual)))

            if mensagem is not None:
                job.mensagem = mensagem

            if arquivo_atual is not None:
                job.arquivo_atual = arquivo_atual

            if nome_processamento is not None:
                job.nome_processamento = nome_processamento

            if erro is not None:
                job.erro = erro

            if eventos is not None:
                job.eventos = _normalizar_para_json(eventos)

            if resultado is not None:
                job.resultado = _normalizar_para_json(resultado)

            if resumo is not None:
                job.resumo = _normalizar_para_json(resumo)
        return

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

        if resultado is not None:
            job["resultado"] = resultado

        if resumo is not None:
            job["resumo"] = resumo

        job["atualizado_em"] = agora_local().isoformat()
        jobs[job_id] = job
        _salvar_jobs(jobs)


def registrar_evento_job(job_id, tipo, titulo, descricao="", arquivo=""):
    if storage_usa_banco():
        with JOBS_LOCK, get_db_session() as session:
            job = session.query(JobModel).filter(JobModel.job_id == job_id).one_or_none()

            if not job:
                return

            eventos = list(job.eventos or [])
            evento = {
                "tipo": str(tipo or "info"),
                "titulo": str(titulo or "").strip(),
                "descricao": str(descricao or "").strip(),
                "arquivo": str(arquivo or "").strip(),
                "criado_em": agora_local().isoformat()
            }

            if not eventos or eventos[-1] != evento:
                eventos.append(evento)

            eventos = eventos[-20:]
            resumo = dict(job.resumo or _resumo_padrao(job.total_arquivos))
            tipo_evento = evento["tipo"]
            resumo[tipo_evento] = int(resumo.get(tipo_evento, 0)) + 1
            resumo["total_eventos"] = len(eventos)

            job.eventos = eventos
            job.resumo = resumo
        return

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
            "criado_em": agora_local().isoformat()
        }

        # Evita duplicidade em polling quando a mesma mensagem se repete.
        if not eventos or eventos[-1] != evento:
            eventos.append(evento)

        job["eventos"] = eventos[-20:]
        resumo = dict(job.get("resumo", {}))
        tipo = evento["tipo"]
        resumo[tipo] = int(resumo.get(tipo, 0)) + 1
        resumo["total_eventos"] = len(eventos[-20:])
        job["resumo"] = resumo
        job["atualizado_em"] = agora_local().isoformat()
        jobs[job_id] = job
        _salvar_jobs(jobs)


def obter_job(job_id):
    if storage_usa_banco():
        with JOBS_LOCK, get_db_session() as session:
            job = session.query(JobModel).filter(JobModel.job_id == job_id).one_or_none()

            if job:
                return _job_model_para_dict(job)

        return {
            **_job_padrao(job_id, 0),
            "status": "nao_encontrado",
            "mensagem": "Processamento não encontrado.",
            "erro": "Job não encontrado.",
        }

    with JOBS_LOCK:
        jobs = _carregar_jobs()

    return jobs.get(job_id, {
        **_job_padrao(job_id, 0),
        "status": "nao_encontrado",
        "mensagem": "Processamento não encontrado.",
        "erro": "Job não encontrado.",
    })

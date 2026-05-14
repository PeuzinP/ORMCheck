import requests
import re

from app.settings import (
    KEEPEDU_BUSCAR_ID_URL,
    KEEPEDU_API_KEY,
    KEEPEDU_INSTITUTE
)


def _extrair_objeto_aluno(resposta_api):
    """
    Tenta encontrar o objeto do aluno em diferentes formatos possíveis de resposta.
    Como ainda não sabemos o JSON exato da API, deixamos flexível.
    """

    if isinstance(resposta_api, list):
        if len(resposta_api) == 1 and isinstance(resposta_api[0], dict):
            return resposta_api[0]
        return None

    if not isinstance(resposta_api, dict):
        return None

    possiveis_chaves = [
        "aluno",
        "data",
        "dados",
        "result",
        "resultado",
        "response"
    ]

    for chave in possiveis_chaves:
        valor = resposta_api.get(chave)

        if isinstance(valor, dict):
            return valor

        if isinstance(valor, list) and len(valor) == 1 and isinstance(valor[0], dict):
            return valor[0]

    return resposta_api


def _extrair_id_aluno(aluno):
    if not isinstance(aluno, dict):
        return ""

    possiveis_campos_id = [
        "id",
        "id_aluno",
        "idAluno",
        "id_pessoa",
        "idPessoa",
        "codigo",
        "codigo_aluno",
        "codigoAluno"
    ]

    for campo in possiveis_campos_id:
        valor = aluno.get(campo)

        if valor:
            return str(valor).strip()

    return ""


def buscar_aluno_por_ra(ra: str):
    """
    Consulta a API do KeepEdu pelo RA e retorna o ID do aluno.

    Entrada:
    {
        "ra": "123456"
    }

    Retorno esperado internamente:
    {
        "encontrado": True,
        "id": "...",
        "ra": "...",
        "nome": "...",
        "raw": {...}
    }
    """

    ra = str(ra or "").strip()
    ra = re.sub(r"\D", "", ra)

    if not ra or len(ra) < 5 or ra == "000000":
        return {
            "encontrado": False,
            "motivo": f"RA inválido para consulta: {ra or 'vazio'}",
            "ra": ra
        }

    if not KEEPEDU_API_KEY:
        return {
            "encontrado": False,
            "motivo": "ApiKey não configurada no arquivo .env."
        }

    headers = {
        "ApiKey": KEEPEDU_API_KEY,
        "Institute": KEEPEDU_INSTITUTE,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "ra": ra
    }

    try:
        resposta = requests.post(
            KEEPEDU_BUSCAR_ID_URL,
            json=payload,
            headers=headers,
            timeout=20
        )

        if resposta.status_code == 404:
            return {
                "encontrado": False,
                "motivo": "RA não encontrado na API.",
                "status_code": resposta.status_code
            }

        resposta.raise_for_status()

        dados = resposta.json()
        aluno = _extrair_objeto_aluno(dados)
        id_aluno = _extrair_id_aluno(aluno)

        if not id_aluno:
            return {
                "encontrado": False,
                "motivo": "API respondeu, mas não foi possível localizar o campo de ID do aluno.",
                "ra": ra,
                "raw": dados
            }

        return {
            "encontrado": True,
            "id": id_aluno,
            "ra": str(aluno.get("ra", ra)) if isinstance(aluno, dict) else ra,
            "nome": str(aluno.get("nome", "")) if isinstance(aluno, dict) else "",
            "turma": str(aluno.get("turma", "")) if isinstance(aluno, dict) else "",
            "unidade": str(aluno.get("unidade", "")) if isinstance(aluno, dict) else "",
            "status_matricula": str(aluno.get("status_matricula", "")) if isinstance(aluno, dict) else "",
            "raw": dados
        }

    except requests.exceptions.Timeout:
        return {
            "encontrado": False,
            "motivo": "Tempo limite excedido ao consultar a API."
        }

    except requests.exceptions.RequestException as e:
        return {
            "encontrado": False,
            "motivo": f"Erro ao consultar API: {str(e)}"
        }

    except ValueError:
        return {
            "encontrado": False,
            "motivo": "A API não retornou um JSON válido."
        }


def buscar_aluno_por_nome(nome: str):
    """
    Por enquanto não será usado no fluxo principal.
    Regra atual:
    - Se tiver ID no cartão, usa ID.
    - Se não tiver ID, usa RA para buscar ID.
    - Se não tiver RA, cai em validação cadastral.
    """

    return {
        "encontrado": False,
        "motivo": "Consulta por nome não será usada neste fluxo."
    }
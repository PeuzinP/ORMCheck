import json

import requests

from app.settings import (
    APP_BASIC_AUTH_PASSWORD,
    APP_BASIC_AUTH_USER,
    KEEPEDU_IMPORTAR_TIMEOUT_SECONDS,
    KEEPEDU_LOGIN_SCHOOL,
    KEEPEDU_LOGIN_URL,
)


def _mensagem_resposta(resposta: requests.Response, prefixo: str) -> str:
    status_code = resposta.status_code

    try:
        dados = resposta.json()
    except ValueError:
        texto = " ".join(str(resposta.text or "").split())
        if "<html" in texto.lower() or "<!doctype" in texto.lower():
            return f"{prefixo}: HTTP {status_code} retornou HTML em vez de JSON."
        if texto:
            return f"{prefixo}: HTTP {status_code} - {texto[:220]}"
        return f"{prefixo}: HTTP {status_code}."

    if isinstance(dados, dict):
        for chave in ("mensagem", "message", "error", "erro"):
            valor = dados.get(chave)
            if isinstance(valor, list):
                itens = [str(item).strip() for item in valor if str(item).strip()]
                if itens:
                    return " | ".join(itens[:3])
            elif valor:
                return str(valor).strip()

        if dados.get("success") is False:
            return f"{prefixo}: credenciais rejeitadas."

    return f"{prefixo}: HTTP {status_code}."


def _resposta_indica_sucesso(status_code: int, dados) -> bool:
    if not (200 <= status_code < 300):
        return False

    if isinstance(dados, dict):
        if dados.get("success") is False:
            return False

        status = str(dados.get("status", "")).strip().lower()
        if status in {"erro", "error", "unauthorized", "forbidden"}:
            return False

    return True


def autenticar_keepedu(email: str, senha: str) -> tuple[bool, str, dict]:
    email = str(email or "").strip()
    senha = str(senha or "").strip()

    if not email or not senha:
        return False, "Informe e-mail e senha.", {}

    # if (
    #     APP_BASIC_AUTH_USER
    #     and APP_BASIC_AUTH_PASSWORD
    #     and email == APP_BASIC_AUTH_USER
    #     and senha == APP_BASIC_AUTH_PASSWORD
    # ):
    #     return True, "", {
    #         "email": email,
    #         "origem": "local",
    #     }
        
    print("KEEPEDU_LOGIN_URL:", KEEPEDU_LOGIN_URL)
    if KEEPEDU_LOGIN_URL:
        payload = {
            "email": email,
            "senha": senha,
            "school": KEEPEDU_LOGIN_SCHOOL,
        }

        try:
            resposta = requests.post(
                KEEPEDU_LOGIN_URL,
                json=payload,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=KEEPEDU_IMPORTAR_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            return False, f"Não foi possível conectar ao login Keep: {exc}", {}

        try:
            dados = resposta.json()
        except ValueError:
            dados = {}

        if not _resposta_indica_sucesso(resposta.status_code, dados):
            return False, _mensagem_resposta(resposta, "Login Keep"), {}

        return True, "", {
            "email": email,
            "origem": "keepedu",
        }

    return False, "Credenciais inválidas.", {}

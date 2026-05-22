import base64
import json
import re
import time
import unicodedata

import requests

from app.settings import (
    BERNOULLI_AUTH_CACHE_FILE,
    BERNOULLI_AUTH_HEADER_PREFIX,
    BERNOULLI_AUTHORIZATION,
    BERNOULLI_AUTH_REFRESH_MARGIN_SECONDS,
    BERNOULLI_COOKIE,
    BERNOULLI_FRONT_VERSION,
    BERNOULLI_GRUPO_USUARIO,
    BERNOULLI_LOGIN_COOKIE_NAMES,
    BERNOULLI_LOGIN_EXTRA_PAYLOAD,
    BERNOULLI_LOGIN_HEADERS,
    BERNOULLI_LOGIN_METHOD,
    BERNOULLI_LOGIN_PASSWORD,
    BERNOULLI_LOGIN_PASSWORD_FIELD,
    BERNOULLI_LOGIN_TOKEN_PATH,
    BERNOULLI_LOGIN_URL,
    BERNOULLI_LOGIN_USERNAME,
    BERNOULLI_LOGIN_USERNAME_FIELD,
    BERNOULLI_LOGIN_USE_FORM,
    BERNOULLI_ORIGIN,
    BERNOULLI_PAGE_SIZE,
    BERNOULLI_PARAMETROS_HEADERS,
    BERNOULLI_PARAMETROS_METHOD,
    BERNOULLI_PARAMETROS_PAYLOAD,
    BERNOULLI_PARAMETROS_TOKEN_PATH,
    BERNOULLI_PARAMETROS_URL,
    BERNOULLI_PARAMETROS_USE_FORM,
    BERNOULLI_PLATAFORMA,
    BERNOULLI_REFERER,
    BERNOULLI_USUARIOS_URL,
)


def _normalizar_ra(valor: str) -> str:
    return re.sub(r"\D", "", str(valor or "").strip())


def _normalizar_nome(valor: str) -> str:
    texto = str(valor or "").strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.lower()
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _normalizar_authorization(valor: str) -> str:
    texto = str(valor or "").strip()

    if not texto:
        return ""

    if re.match(r"^[A-Za-z]+\s+", texto):
        return texto

    return f"{BERNOULLI_AUTH_HEADER_PREFIX} {texto}".strip()


def _extrair_token_bruto(authorization: str) -> str:
    texto = str(authorization or "").strip()

    if not texto:
        return ""

    partes = texto.split(None, 1)
    return partes[1].strip() if len(partes) == 2 else texto


def _jwt_expira_em(authorization: str) -> int | None:
    token = _extrair_token_bruto(authorization)

    if token.count(".") < 2:
        return None

    try:
        segmento = token.split(".", 2)[1]
        padding = "=" * (-len(segmento) % 4)
        payload = base64.urlsafe_b64decode(f"{segmento}{padding}")
        dados = json.loads(payload.decode("utf-8"))
    except Exception:
        return None

    exp = dados.get("exp")
    return int(exp) if isinstance(exp, (int, float)) else None


def _authorization_expirado(authorization: str, margem: int = 0) -> bool:
    exp = _jwt_expira_em(authorization)

    if exp is None:
        return False

    return exp <= int(time.time()) + max(0, margem)


def _cookie_header_para_dict(cookie_header: str) -> dict[str, str]:
    cookies = {}

    for parte in str(cookie_header or "").split(";"):
        if "=" not in parte:
            continue

        nome, valor = parte.split("=", 1)
        nome = nome.strip()
        valor = valor.strip()

        if nome:
            cookies[nome] = valor

    return cookies


def _dict_para_cookie_header(cookies: dict[str, str]) -> str:
    return "; ".join(
        f"{nome}={valor}"
        for nome, valor in cookies.items()
        if str(nome).strip() and valor is not None
    )


def _obter_por_caminho(dados, caminho: str):
    valor_atual = dados

    for trecho in [item.strip() for item in str(caminho or "").split(".") if item.strip()]:
        if isinstance(valor_atual, dict):
            if trecho not in valor_atual:
                return None
            valor_atual = valor_atual[trecho]
            continue

        if isinstance(valor_atual, list) and trecho.isdigit():
            indice = int(trecho)
            if indice >= len(valor_atual):
                return None
            valor_atual = valor_atual[indice]
            continue

        return None

    return valor_atual


def _extrair_authorization_de_resposta(resposta: requests.Response) -> str:
    return _extrair_authorization_de_resposta_com_caminho(
        resposta,
        caminho_principal=BERNOULLI_LOGIN_TOKEN_PATH
    )


def _extrair_authorization_de_resposta_com_caminho(
    resposta: requests.Response,
    caminho_principal: str = ""
) -> str:
    header = resposta.headers.get("Authorization", "").strip()
    if header:
        return _normalizar_authorization(header)

    try:
        dados = resposta.json()
    except ValueError:
        return ""

    candidatos = []
    caminho_principal = str(caminho_principal or "").strip()
    if caminho_principal:
        candidatos.append(caminho_principal)
    candidatos.extend(
        caminho
        for caminho in [
            "token",
            "access_token",
            "jwt",
            "data.token",
            "data.access_token",
            "data.jwt",
            "authorization",
            "data.authorization",
        ]
        if caminho != caminho_principal
    )

    for caminho in candidatos:
        valor = _obter_por_caminho(dados, caminho)
        if isinstance(valor, str) and valor.strip():
            return _normalizar_authorization(valor)

    return ""


def _resposta_indica_falha_de_auth(resposta: requests.Response) -> bool:
    if resposta.status_code in {401, 403}:
        return True

    conteudo = (resposta.text or "").lstrip()
    tipo_conteudo = resposta.headers.get("Content-Type", "")

    if "json" not in tipo_conteudo.lower() and conteudo.startswith("<"):
        return True

    return False


class _BernoulliAuthManager:
    def __init__(self):
        self._authorization = _normalizar_authorization(BERNOULLI_AUTHORIZATION)
        self._cookies = _cookie_header_para_dict(BERNOULLI_COOKIE)
        self._estado_carregado = False

    def _carregar_estado(self):
        if self._estado_carregado:
            return

        self._estado_carregado = True

        if not BERNOULLI_AUTH_CACHE_FILE.exists():
            return

        try:
            dados = json.loads(BERNOULLI_AUTH_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return

        if not self._authorization:
            self._authorization = _normalizar_authorization(dados.get("authorization", ""))

        if not self._cookies:
            cookies = dados.get("cookies", {})
            if isinstance(cookies, dict):
                self._cookies = {
                    str(nome).strip(): str(valor)
                    for nome, valor in cookies.items()
                    if str(nome).strip()
                }

    def _salvar_estado(self):
        BERNOULLI_AUTH_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        dados = {
            "authorization": self._authorization,
            "cookies": self._cookies,
            "salvo_em_epoch": int(time.time()),
        }
        BERNOULLI_AUTH_CACHE_FILE.write_text(
            json.dumps(dados, ensure_ascii=True, indent=2),
            encoding="utf-8"
        )

    def _limpar_estado_dinamico(self):
        self._authorization = ""
        self._cookies = {}

        if BERNOULLI_AUTH_CACHE_FILE.exists():
            BERNOULLI_AUTH_CACHE_FILE.unlink(missing_ok=True)

    def _possui_login_configurado(self) -> bool:
        return bool(
            BERNOULLI_LOGIN_URL
            and BERNOULLI_LOGIN_USERNAME
            and BERNOULLI_LOGIN_PASSWORD
        )

    def _possui_parametros_configurado(self) -> bool:
        return bool(BERNOULLI_PARAMETROS_URL and BERNOULLI_PARAMETROS_PAYLOAD)

    def _deve_renovar_authorization(self) -> bool:
        if not self._authorization:
            return not bool(self._cookies)

        return _authorization_expirado(
            self._authorization,
            margem=BERNOULLI_AUTH_REFRESH_MARGIN_SECONDS
        )

    def _criar_sessao(self) -> requests.Session:
        sessao = requests.Session()
        if self._cookies:
            sessao.cookies.update(self._cookies)
        return sessao

    def _capturar_estado_da_sessao(self, sessao: requests.Session, resposta: requests.Response | None = None):
        cookies_sessao = requests.utils.dict_from_cookiejar(sessao.cookies)
        cookies_filtrados = {
            str(nome).strip(): str(valor)
            for nome, valor in cookies_sessao.items()
            if str(nome).strip()
        }

        if BERNOULLI_LOGIN_COOKIE_NAMES:
            cookies_filtrados = {
                nome: valor
                for nome, valor in cookies_filtrados.items()
                if nome in BERNOULLI_LOGIN_COOKIE_NAMES
            }

        authorization = ""
        if resposta is not None:
            authorization = _extrair_authorization_de_resposta(resposta)

        if authorization:
            self._authorization = authorization

        if cookies_filtrados:
            self._cookies = cookies_filtrados

        if self._authorization or self._cookies:
            self._salvar_estado()

    def _fazer_login(self):
        if not self._possui_login_configurado():
            raise RuntimeError(
                "Autenticacao Bernoulli nao configurada para renovacao automatica. "
                "Preencha BERNOULLI_LOGIN_URL, BERNOULLI_LOGIN_USERNAME e "
                "BERNOULLI_LOGIN_PASSWORD no .env."
            )

        sessao = requests.Session()
        payload = dict(BERNOULLI_LOGIN_EXTRA_PAYLOAD)
        payload[BERNOULLI_LOGIN_USERNAME_FIELD] = BERNOULLI_LOGIN_USERNAME
        payload[BERNOULLI_LOGIN_PASSWORD_FIELD] = BERNOULLI_LOGIN_PASSWORD
        headers = {
            str(chave): str(valor)
            for chave, valor in BERNOULLI_LOGIN_HEADERS.items()
            if str(chave).strip()
        }
        headers.setdefault("Accept", "application/json, text/plain, */*")

        if BERNOULLI_LOGIN_USE_FORM:
            resposta = sessao.request(
                BERNOULLI_LOGIN_METHOD,
                BERNOULLI_LOGIN_URL,
                data=payload,
                headers=headers,
                timeout=20,
            )
        else:
            headers.setdefault("Content-Type", "application/json")
            resposta = sessao.request(
                BERNOULLI_LOGIN_METHOD,
                BERNOULLI_LOGIN_URL,
                json=payload,
                headers=headers,
                timeout=20,
            )

        resposta.raise_for_status()
        self._capturar_estado_da_sessao(sessao, resposta=resposta)

        if self._authorization and self._possui_parametros_configurado():
            self._fazer_parametros()

        if not self._authorization and not self._cookies:
            raise RuntimeError(
                "O login Bernoulli foi executado, mas nao retornou token nem cookies "
                "reaproveitaveis. Revise BERNOULLI_LOGIN_TOKEN_PATH, "
                "BERNOULLI_LOGIN_HEADERS e BERNOULLI_LOGIN_COOKIE_NAMES."
            )

    def _fazer_parametros(self):
        if not self._authorization:
            raise RuntimeError(
                "A etapa /api/autenticado/parametros exige um token previo do login Bernoulli."
            )

        sessao = self._criar_sessao()
        headers = self.headers_para_requisicao()
        headers.update(
            {
                str(chave): str(valor)
                for chave, valor in BERNOULLI_PARAMETROS_HEADERS.items()
                if str(chave).strip()
            }
        )
        headers.setdefault("Accept", "application/json, text/plain, */*")
        payload = dict(BERNOULLI_PARAMETROS_PAYLOAD)

        if BERNOULLI_PARAMETROS_USE_FORM:
            resposta = sessao.request(
                BERNOULLI_PARAMETROS_METHOD,
                BERNOULLI_PARAMETROS_URL,
                data=payload,
                headers=headers,
                timeout=20,
            )
        else:
            headers.setdefault("Content-Type", "application/json")
            resposta = sessao.request(
                BERNOULLI_PARAMETROS_METHOD,
                BERNOULLI_PARAMETROS_URL,
                json=payload,
                headers=headers,
                timeout=20,
            )

        resposta.raise_for_status()
        authorization = _extrair_authorization_de_resposta_com_caminho(
            resposta,
            caminho_principal=BERNOULLI_PARAMETROS_TOKEN_PATH
        )
        self._capturar_estado_da_sessao(sessao)

        if authorization:
            self._authorization = authorization
            self._salvar_estado()
            return

        if not self._cookies:
            raise RuntimeError(
                "A etapa /api/autenticado/parametros foi executada, mas nao retornou "
                "token reaproveitavel. Revise BERNOULLI_PARAMETROS_TOKEN_PATH e "
                "BERNOULLI_PARAMETROS_PAYLOAD."
            )

    def preparar_requisicao(self, forcar_renovacao: bool = False):
        self._carregar_estado()

        if forcar_renovacao:
            self._limpar_estado_dinamico()

        precisa_login = self._deve_renovar_authorization() and self._possui_login_configurado()

        if precisa_login:
            self._fazer_login()

    def headers_para_requisicao(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
        }

        if BERNOULLI_FRONT_VERSION:
            headers["front-version"] = BERNOULLI_FRONT_VERSION

        if BERNOULLI_PLATAFORMA:
            headers["plataforma"] = BERNOULLI_PLATAFORMA

        if BERNOULLI_ORIGIN:
            headers["Origin"] = BERNOULLI_ORIGIN

        if BERNOULLI_REFERER:
            headers["Referer"] = BERNOULLI_REFERER

        if self._authorization and not _authorization_expirado(self._authorization):
            headers["Authorization"] = self._authorization

        if self._cookies:
            headers["Cookie"] = _dict_para_cookie_header(self._cookies)

        return headers

    def get(self, url: str, **kwargs):
        self.preparar_requisicao(forcar_renovacao=False)

        for tentativa in range(2):
            sessao = self._criar_sessao()
            resposta = sessao.get(
                url,
                headers=self.headers_para_requisicao(),
                timeout=20,
                **kwargs,
            )

            if _resposta_indica_falha_de_auth(resposta) and tentativa == 0 and self._possui_login_configurado():
                self.preparar_requisicao(forcar_renovacao=True)
                continue

            self._capturar_estado_da_sessao(sessao)
            return resposta

        raise RuntimeError("Falha inesperada ao consultar a API do Bernoulli.")


_AUTH_MANAGER = _BernoulliAuthManager()


def _buscar_usuarios(search: str):
    resposta = _AUTH_MANAGER.get(
        BERNOULLI_USUARIOS_URL,
        params=[
            ("grupoUsuario[]", BERNOULLI_GRUPO_USUARIO),
            ("search", str(search or "").strip()),
            ("sortOrder", "asc"),
            ("sortBy", "nm_pessoa"),
            ("pageSize", BERNOULLI_PAGE_SIZE),
            ("page", 1),
        ],
    )
    resposta.raise_for_status()

    conteudo = (resposta.text or "").lstrip()
    tipo_conteudo = resposta.headers.get("Content-Type", "")

    if "json" not in tipo_conteudo.lower() and conteudo.startswith("<"):
        raise ValueError(
            "A API do Bernoulli retornou HTML em vez de JSON. Isso normalmente indica "
            "que a requisicao precisa de autenticacao (Cookie/Authorization) ou que a "
            "sessao utilizada expirou."
        )

    dados = resposta.json()
    if isinstance(dados, dict):
        lista = dados.get("data", [])
        if isinstance(lista, list):
            return lista

    return []


def _selecionar_usuario(candidatos: list[dict], ra: str, nome: str = ""):
    ra_normalizado = _normalizar_ra(ra)
    nome_normalizado = _normalizar_nome(nome)

    for usuario in candidatos:
        if _normalizar_ra(usuario.get("cd_ra", "")) == ra_normalizado:
            return usuario

    if nome_normalizado:
        for usuario in candidatos:
            if _normalizar_nome(usuario.get("nm_pessoa", "")) == nome_normalizado:
                return usuario

    return None


def buscar_aluno_bernoulli(ra: str, nome: str = ""):
    ra_normalizado = _normalizar_ra(ra)

    if not ra_normalizado:
        return {
            "encontrado": False,
            "motivo": "RA inválido para consulta na API do Bernoulli.",
            "ra": ra_normalizado,
        }

    try:
        candidatos = _buscar_usuarios(ra_normalizado)
        usuario = _selecionar_usuario(candidatos, ra_normalizado, nome)

        if usuario is None and nome:
            candidatos = _buscar_usuarios(nome)
            usuario = _selecionar_usuario(candidatos, ra_normalizado, nome)

        if usuario is None:
            return {
                "encontrado": False,
                "motivo": "Aluno não encontrado na API do Bernoulli.",
                "ra": ra_normalizado,
                "nome": str(nome or "").strip(),
            }

        return {
            "encontrado": True,
            "rmb": str(usuario.get("cd_aluno", "") or "").strip(),
            "ra": _normalizar_ra(usuario.get("cd_ra", ra_normalizado)),
            "nome": str(usuario.get("nm_pessoa", "") or "").strip(),
            "email": str(usuario.get("ds_email", "") or "").strip(),
            "ativo": str(usuario.get("nu_ativo", "") or "").strip(),
            "raw": usuario,
        }

    except requests.exceptions.Timeout:
        return {
            "encontrado": False,
            "motivo": "Tempo limite excedido ao consultar a API do Bernoulli.",
            "ra": ra_normalizado,
        }

    except requests.exceptions.RequestException as erro:
        return {
            "encontrado": False,
            "motivo": f"Erro ao consultar API do Bernoulli: {erro}",
            "ra": ra_normalizado,
        }

    except ValueError as erro:
        return {
            "encontrado": False,
            "motivo": str(erro) or "A API do Bernoulli não retornou um JSON válido.",
            "ra": ra_normalizado,
        }

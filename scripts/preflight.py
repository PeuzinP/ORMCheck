import sys
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

load_dotenv(BASE_DIR / ".env")

from app.settings import (  # noqa: E402
    APP_ALLOWED_HOSTS,
    APP_BASIC_AUTH_PASSWORD,
    APP_BASIC_AUTH_USER,
    APP_ENABLE_AUTH,
    APP_ENV,
    BERNOULLI_AUTHORIZATION,
    BERNOULLI_COOKIE,
    BERNOULLI_LOGIN_PASSWORD,
    BERNOULLI_LOGIN_URL,
    BERNOULLI_LOGIN_USERNAME,
    BERNOULLI_PARAMETROS_PAYLOAD,
    BERNOULLI_PARAMETROS_URL,
    CAMINHO_ICONE,
    CAMINHO_MODELO_CARTAO,
    KEEPEDU_API_KEY,
    KEEPEDU_INSTITUTE,
    PASTA_BACKUPS,
    PASTA_LOGS,
    PASTA_PROCESSAMENTOS,
    PASTA_RUNTIME,
    PASTA_UPLOADS_TEMP,
    garantir_pastas,
)


def check_ok(message):
    print(f"[OK] {message}")


def check_warn(message):
    print(f"[WARN] {message}")


def check_fail(message):
    print(f"[FAIL] {message}")


def is_placeholder(value, placeholders):
    texto = str(value or "").strip()
    if not texto:
        return True
    return texto.lower() in {item.lower() for item in placeholders}


def usa_caminho_linux_de_container():
    env_file = BASE_DIR / ".env"

    if not env_file.exists():
        return False

    try:
        for linha in env_file.read_text(encoding="utf-8").splitlines():
            conteudo = linha.strip()
            if not conteudo or conteudo.startswith("#") or "=" not in conteudo:
                continue

            chave, valor = conteudo.split("=", 1)
            if chave.strip() == "APP_DATA_DIR":
                return valor.strip().startswith("/")
    except Exception:
        return False

    return False


def main():
    falhas = 0
    avisos = 0

    env_file = BASE_DIR / ".env"
    if env_file.exists():
        check_ok(".env encontrado")
    else:
        check_fail(".env nao encontrado na raiz do projeto")
        falhas += 1

    if APP_ENV == "production":
        check_ok("APP_ENV configurado como production")
    else:
        check_fail(f"APP_ENV atual: {APP_ENV}. O recomendado para implantacao e production")
        falhas += 1

    if APP_ENABLE_AUTH:
        check_ok("Autenticacao basica habilitada")
    else:
        check_warn("APP_ENABLE_AUTH esta false; a aplicacao ficara sem login")
        avisos += 1

    if not APP_ENABLE_AUTH:
        check_warn("Usuario e senha nao serao exigidos na implantacao atual")
        avisos += 1
    elif is_placeholder(APP_BASIC_AUTH_USER, {"operador", "usuario", "admin"}):
        check_warn("APP_BASIC_AUTH_USER parece generico; troque antes da implantacao")
        avisos += 1
    else:
        check_ok("Usuario de autenticacao definido")

    if not APP_ENABLE_AUTH:
        check_warn("Senha de autenticacao nao sera usada enquanto APP_ENABLE_AUTH=false")
        avisos += 1
    elif is_placeholder(APP_BASIC_AUTH_PASSWORD, {"troque-esta-senha", "123456", "senha"}):
        check_fail("APP_BASIC_AUTH_PASSWORD ainda parece padrao")
        falhas += 1
    else:
        check_ok("Senha de autenticacao personalizada")

    allowed_hosts = [item.strip() for item in APP_ALLOWED_HOSTS if str(item).strip()]
    placeholders_hosts = {"localhost", "127.0.0.1"}
    hosts_validos = [host for host in allowed_hosts if host.lower() not in placeholders_hosts]
    if hosts_validos:
        check_ok(f"APP_ALLOWED_HOSTS configurado para implantacao: {', '.join(hosts_validos)}")
    else:
        check_fail("APP_ALLOWED_HOSTS ainda esta apenas com localhost/127.0.0.1")
        falhas += 1

    if KEEPEDU_API_KEY.strip():
        check_ok("KEEPEDU_API_KEY preenchida")
    else:
        check_fail("KEEPEDU_API_KEY nao preenchida")
        falhas += 1

    if KEEPEDU_INSTITUTE.strip():
        check_ok("KEEPEDU_INSTITUTE preenchido")
    else:
        check_fail("KEEPEDU_INSTITUTE nao preenchido")
        falhas += 1

    bernoulli_login_configurado = bool(
        BERNOULLI_LOGIN_URL.strip()
        and BERNOULLI_LOGIN_USERNAME.strip()
        and BERNOULLI_LOGIN_PASSWORD.strip()
    )
    bernoulli_manual_configurado = bool(
        BERNOULLI_AUTHORIZATION.strip() or BERNOULLI_COOKIE.strip()
    )
    bernoulli_parametros_configurado = bool(
        BERNOULLI_PARAMETROS_URL.strip() and BERNOULLI_PARAMETROS_PAYLOAD
    )
    if bernoulli_login_configurado:
        if bernoulli_parametros_configurado:
            check_ok("Bernoulli com fluxo login + parametros configurado")
        else:
            check_ok("Bernoulli com login automatico configurado")
    elif bernoulli_manual_configurado:
        check_warn(
            "Bernoulli depende de token/cookie manual; considere preencher BERNOULLI_LOGIN_* "
            "para renovacao automatica"
        )
        avisos += 1
    else:
        check_warn("Bernoulli sem autenticacao configurada; consultas RMB podem falhar")
        avisos += 1

    if CAMINHO_MODELO_CARTAO.exists():
        check_ok("Template OMR encontrado")
    else:
        check_fail(f"Template OMR ausente em {CAMINHO_MODELO_CARTAO}")
        falhas += 1

    if CAMINHO_ICONE.exists():
        check_ok("Icone da aplicacao encontrado")
    else:
        check_warn("Icone da aplicacao nao encontrado")
        avisos += 1

    if sys.platform.startswith("win") and usa_caminho_linux_de_container():
        check_warn(
            "APP_DATA_DIR usa caminho Linux de container (/data); "
            "validacao local das pastas foi ignorada no Windows"
        )
        avisos += 1
        check_ok(f"Pastas operacionais esperadas no container a partir de {PASTA_PROCESSAMENTOS.parent}")
        check_ok(f"Logs esperados em {PASTA_LOGS}")
        check_ok(f"Backups esperados em {PASTA_BACKUPS}")
        check_ok(f"Runtime esperado em {PASTA_RUNTIME}")
        check_ok(f"Uploads temporarios esperados em {PASTA_UPLOADS_TEMP}")
    else:
        try:
            garantir_pastas()
            check_ok(f"Pastas operacionais verificadas em {PASTA_PROCESSAMENTOS.parent}")
            check_ok(f"Logs em {PASTA_LOGS}")
            check_ok(f"Backups em {PASTA_BACKUPS}")
            check_ok(f"Runtime em {PASTA_RUNTIME}")
            check_ok(f"Uploads temporarios em {PASTA_UPLOADS_TEMP}")
        except Exception as erro:
            check_fail(f"Nao foi possivel preparar as pastas operacionais: {erro}")
            falhas += 1

    print("")
    print(f"Resumo: {falhas} falha(s), {avisos} aviso(s)")

    if falhas:
        print("Preflight reprovado. Corrija as falhas antes da implantacao.")
        raise SystemExit(1)

    print("Preflight aprovado para seguir com a implantacao.")


if __name__ == "__main__":
    main()

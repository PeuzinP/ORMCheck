import logging
from logging.handlers import RotatingFileHandler

from app.settings import APP_ENV, APP_LOG_LEVEL, CAMINHO_LOG_APP


def setup_logging():
    logger_raiz = logging.getLogger()

    if getattr(logger_raiz, "_omrcheck_configurado", False):
        return logger_raiz

    nivel = getattr(logging, APP_LOG_LEVEL, logging.INFO)
    logger_raiz.setLevel(nivel)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    handler_console = logging.StreamHandler()
    handler_console.setLevel(nivel)
    handler_console.setFormatter(formatter)

    CAMINHO_LOG_APP.parent.mkdir(parents=True, exist_ok=True)
    handler_arquivo = RotatingFileHandler(
        CAMINHO_LOG_APP,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    handler_arquivo.setLevel(nivel)
    handler_arquivo.setFormatter(formatter)

    logger_raiz.handlers.clear()
    logger_raiz.addHandler(handler_console)
    logger_raiz.addHandler(handler_arquivo)
    logger_raiz._omrcheck_configurado = True

    logging.getLogger("omrcheck").info(
        "Logging inicializado | env=%s | arquivo=%s",
        APP_ENV,
        CAMINHO_LOG_APP
    )

    return logger_raiz

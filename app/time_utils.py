from datetime import datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.settings import APP_TIMEZONE


@lru_cache(maxsize=1)
def obter_timezone_app():
    for nome_timezone in (APP_TIMEZONE, "America/Sao_Paulo"):
        try:
            return ZoneInfo(nome_timezone)
        except ZoneInfoNotFoundError:
            continue

    return timezone.utc


def agora_local() -> datetime:
    return datetime.now(obter_timezone_app())


def fromtimestamp_local(timestamp: float) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=obter_timezone_app())

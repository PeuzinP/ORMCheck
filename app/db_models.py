from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class JobModel(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="aguardando")
    percentual: Mapped[int] = mapped_column(Integer, default=0)
    mensagem: Mapped[str] = mapped_column(Text, default="")
    total_arquivos: Mapped[int] = mapped_column(Integer, default=0)
    arquivo_atual: Mapped[str] = mapped_column(String(255), default="")
    nome_processamento: Mapped[str] = mapped_column(String(255), default="")
    erro: Mapped[str] = mapped_column(Text, default="")
    eventos: Mapped[list] = mapped_column(JSON, default=list)
    resultado: Mapped[dict] = mapped_column(JSON, default=dict)
    resumo: Mapped[dict] = mapped_column(JSON, default=dict)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

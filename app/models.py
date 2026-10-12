from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.db import Base
from app.schemas import ConsultaCliente, EstadoAnalisis


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


class FechaUTC(TypeDecorator):
    """DateTime que siempre devuelve fechas con zona UTC.

    SQLite no guarda la zona horaria y devolvería fechas sin ella; PostgreSQL sí.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class Analisis(Base):
    __tablename__ = "analisis"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cliente_id: Mapped[str] = mapped_column(String(64), index=True)
    texto: Mapped[str] = mapped_column(Text)
    # pendiente -> completado | fallido. Un proceso nocturno puede reanalizar lo no completado.
    estado: Mapped[str] = mapped_column(String(16), index=True, default=EstadoAnalisis.PENDIENTE.value)
    error: Mapped[str | None] = mapped_column(Text, default=None)

    categoria: Mapped[str | None] = mapped_column(String(16), default=None)
    prioridad: Mapped[str | None] = mapped_column(String(16), default=None)
    consulta_cliente: Mapped[str] = mapped_column(
        String(16), default=ConsultaCliente.NO_REQUERIDA.value
    )
    info_cliente: Mapped[dict | None] = mapped_column(JSON, default=None)
    respuesta_sugerida: Mapped[str | None] = mapped_column(Text, default=None)

    tokens_entrada: Mapped[int] = mapped_column(Integer, default=0)
    tokens_salida: Mapped[int] = mapped_column(Integer, default=0)
    tokens_estimados: Mapped[bool] = mapped_column(Boolean, default=False)
    # Se guarda el costo calculado: un cambio de precios no altera el histórico.
    costo_estimado_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), default=Decimal(0))

    creado_en: Mapped[datetime] = mapped_column(FechaUTC, default=_ahora)
    actualizado_en: Mapped[datetime] = mapped_column(FechaUTC, default=_ahora, onupdate=_ahora)

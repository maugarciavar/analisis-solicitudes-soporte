from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Categoria(str, Enum):
    FACTURACION = "facturacion"
    TECNICO = "tecnico"
    COMERCIAL = "comercial"
    OTRO = "otro"


class Prioridad(str, Enum):
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


class Clasificacion(BaseModel):
    """Salida estructurada del paso de clasificación."""

    categoria: Categoria = Field(description="Tema de la solicitud")
    prioridad: Prioridad = Field(description="Urgencia de la solicitud")


class ConsultaCliente(str, Enum):
    NO_REQUERIDA = "no_requerida"  # la prioridad no era alta
    OK = "ok"
    FALLIDA = "fallida"  # el CRM no respondió tras los reintentos


class EstadoAnalisis(str, Enum):
    PENDIENTE = "pendiente"
    COMPLETADO = "completado"
    FALLIDO = "fallido"


class SolicitudEntrada(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    texto: str = Field(min_length=1, max_length=10_000)
    cliente_id: str = Field(min_length=1, max_length=64)


class AnalisisSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    cliente_id: str
    estado: EstadoAnalisis
    categoria: Categoria | None
    prioridad: Prioridad | None
    consulta_cliente: ConsultaCliente
    info_cliente: dict | None
    respuesta_sugerida: str | None
    tokens_entrada: int
    tokens_salida: int
    # True cuando el modelo no reporta uso y los tokens se estimaron.
    tokens_estimados: bool
    costo_estimado_usd: Decimal
    creado_en: datetime

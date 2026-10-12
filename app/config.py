from decimal import Decimal
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del servicio, leída de variables de entorno (o de un .env local)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./solicitudes.db"
    crm_url: str = "http://localhost:9000"

    # Sin clave se usa el modelo simulado.
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # USD por millón de tokens.
    precio_entrada_por_millon: Decimal = Field(default=Decimal("0.15"), ge=0)
    precio_salida_por_millon: Decimal = Field(default=Decimal("0.60"), ge=0)

    crm_max_intentos: int = Field(default=3, ge=1)
    crm_espera_base_segundos: float = Field(default=0.5, ge=0)
    crm_espera_maxima_segundos: float = Field(default=4.0, ge=0)
    # Límite de cada intento y límite de toda la consulta, reintentos incluidos.
    crm_timeout_segundos: float = Field(default=2.0, gt=0)
    crm_tiempo_total_segundos: float = Field(default=8.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()

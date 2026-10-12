import logging
import random
import time
from collections.abc import Callable
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


def _es_reintentable(status_code: int) -> bool:
    # 429 y 5xx son fallos transitorios; el resto de 4xx no cambia por repetir la petición.
    return status_code == 429 or status_code >= 500


class ClienteCRM:
    """Consulta de clientes con reintentos, espera progresiva y tiempo máximo.

    Nunca lanza excepción: si no logra obtener el cliente devuelve None, para que
    el análisis pueda continuar sin ese dato.
    """

    def __init__(
        self,
        base_url: str,
        *,
        max_intentos: int = 3,
        espera_base: float = 0.5,
        espera_maxima: float = 4.0,
        timeout: float = 2.0,
        tiempo_total: float = 8.0,
        transport: httpx.BaseTransport | None = None,
        dormir: Callable[[float], None] = time.sleep,
        reloj: Callable[[], float] = time.monotonic,
        aleatorio: Callable[[], float] = random.random,
    ) -> None:
        self._base_url = base_url
        self._max_intentos = max_intentos
        self._espera_base = espera_base
        self._espera_maxima = espera_maxima
        self._timeout = timeout
        self._tiempo_total = tiempo_total
        # transport, dormir, reloj y aleatorio se inyectan para probar sin red ni esperas reales.
        self._transport = transport
        self._dormir = dormir
        self._reloj = reloj
        self._aleatorio = aleatorio

    def _espera(self, intento: int) -> float:
        # Exponencial con tope y jitter (50 %-100 %) para no sincronizar reintentos entre instancias.
        exponencial = min(self._espera_maxima, self._espera_base * 2 ** (intento - 1))
        return exponencial * (0.5 + self._aleatorio() / 2)

    def obtener_cliente(self, cliente_id: str) -> dict | None:
        inicio = self._reloj()
        ruta = f"/clientes/{quote(cliente_id, safe='')}"

        with httpx.Client(base_url=self._base_url, transport=self._transport) as http:
            for intento in range(1, self._max_intentos + 1):
                restante = self._tiempo_total - (self._reloj() - inicio)
                if restante <= 0:
                    motivo = "tiempo total agotado"
                    break

                try:
                    respuesta = http.get(ruta, timeout=min(self._timeout, restante))
                    if respuesta.status_code == 200:
                        return respuesta.json()
                    if not _es_reintentable(respuesta.status_code):
                        logger.warning(
                            "CRM respondió %s para el cliente %s; no se reintenta",
                            respuesta.status_code,
                            cliente_id,
                        )
                        return None
                    motivo = f"HTTP {respuesta.status_code}"
                except httpx.TransportError as exc:  # timeouts y errores de red
                    motivo = type(exc).__name__
                except ValueError:  # 200 con un cuerpo que no es JSON
                    logger.warning("CRM devolvió un cuerpo inválido para el cliente %s", cliente_id)
                    return None

                if intento == self._max_intentos:
                    break

                espera = self._espera(intento)
                if self._reloj() - inicio + espera >= self._tiempo_total:
                    motivo = f"{motivo}; tiempo total agotado"
                    break
                logger.info("CRM falló (%s), intento %s; reintento en %.2fs", motivo, intento, espera)
                self._dormir(espera)

        logger.warning("CRM no disponible para el cliente %s: %s", cliente_id, motivo)
        return None

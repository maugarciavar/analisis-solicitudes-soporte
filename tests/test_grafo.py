import httpx
import pytest
from langchain_core.language_models import FakeListChatModel

from app.crm_client import ClienteCRM
from app.graph import analizar_solicitud
from app.llm import ClasificacionInvalida
from app.schemas import Categoria, ConsultaCliente, Prioridad

CLIENTE = {"id": "c-1", "nombre": "Cliente demo", "plan": "premium"}
RESPUESTA = "Hola, ya estamos revisando su caso."


def modelo_simulado(categoria: str, prioridad: str) -> FakeListChatModel:
    clasificacion = f'{{"categoria": "{categoria}", "prioridad": "{prioridad}"}}'
    return FakeListChatModel(responses=[clasificacion, RESPUESTA])


def crm_simulado(status_code: int):
    """ClienteCRM sobre un transporte simulado que siempre responde `status_code`."""
    llamadas = []

    def manejador(request: httpx.Request) -> httpx.Response:
        llamadas.append(request)
        return httpx.Response(status_code, json=CLIENTE if status_code == 200 else None)

    crm = ClienteCRM(
        "http://crm.test",
        transport=httpx.MockTransport(manejador),
        dormir=lambda _: None,
    )
    return crm, llamadas


def test_prioridad_alta_consulta_el_cliente():
    crm, llamadas = crm_simulado(200)

    resultado = analizar_solicitud(
        "El sistema está caído", "c-1", modelo_simulado("tecnico", "alta"), crm
    )

    assert resultado["clasificacion"].categoria is Categoria.TECNICO
    assert resultado["clasificacion"].prioridad is Prioridad.ALTA
    assert resultado["consulta_cliente"] is ConsultaCliente.OK
    assert resultado["info_cliente"] == CLIENTE
    assert resultado["respuesta_sugerida"] == RESPUESTA
    assert len(llamadas) == 1
    assert llamadas[0].url.path == "/clientes/c-1"


def test_prioridad_baja_no_consulta_el_cliente():
    crm, llamadas = crm_simulado(200)

    resultado = analizar_solicitud(
        "¿Qué planes ofrecen?", "c-1", modelo_simulado("comercial", "baja"), crm
    )

    assert resultado["consulta_cliente"] is ConsultaCliente.NO_REQUERIDA
    assert resultado["info_cliente"] is None
    assert resultado["respuesta_sugerida"] == RESPUESTA
    assert llamadas == []


def test_continua_sin_datos_si_el_crm_no_responde():
    crm, llamadas = crm_simulado(500)

    resultado = analizar_solicitud(
        "Urgente: no puedo facturar", "c-1", modelo_simulado("facturacion", "alta"), crm
    )

    assert resultado["consulta_cliente"] is ConsultaCliente.FALLIDA
    assert resultado["info_cliente"] is None
    assert resultado["respuesta_sugerida"] == RESPUESTA
    assert len(llamadas) == 3  # agotó los intentos por defecto


def test_acumula_los_tokens_de_los_dos_pasos_del_modelo():
    crm, _ = crm_simulado(200)

    resultado = analizar_solicitud("Hola", "c-1", modelo_simulado("otro", "media"), crm)

    assert resultado["tokens_entrada"] > 0
    # Salida = clasificación + respuesta, estimadas porque el modelo simulado no reporta uso.
    assert resultado["tokens_salida"] > len(RESPUESTA) // 4
    assert resultado["tokens_estimados"] is True


def test_clasificacion_invalida_lanza_error():
    crm, _ = crm_simulado(200)
    modelo = FakeListChatModel(responses=['{"categoria": "ventas", "prioridad": "altísima"}'])

    with pytest.raises(ClasificacionInvalida):
        analizar_solicitud("Hola", "c-1", modelo, crm)

import httpx

from app.crm_client import ClienteCRM

CLIENTE = {"id": "c-1", "nombre": "Cliente demo", "plan": "premium"}


def crear_cliente(respuestas, esperas, **opciones):
    """ClienteCRM cuyo transporte devuelve `respuestas` en orden y anota las esperas."""
    pendientes = iter(respuestas)
    llamadas = []

    def manejador(request: httpx.Request) -> httpx.Response:
        llamadas.append(request)
        respuesta = next(pendientes)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    crm = ClienteCRM(
        "http://crm.test",
        transport=httpx.MockTransport(manejador),
        dormir=esperas.append,
        aleatorio=lambda: 1.0,  # sin jitter: esperas deterministas
        **opciones,
    )
    return crm, llamadas


def test_reintenta_fallos_transitorios_con_espera_progresiva():
    esperas = []
    crm, llamadas = crear_cliente(
        [httpx.Response(500), httpx.Response(429), httpx.Response(200, json=CLIENTE)],
        esperas,
        max_intentos=3,
        espera_base=0.5,
    )

    assert crm.obtener_cliente("c-1") == CLIENTE
    assert len(llamadas) == 3
    assert esperas == [0.5, 1.0]


def test_devuelve_none_al_agotar_los_intentos():
    esperas = []
    crm, llamadas = crear_cliente([httpx.Response(500)] * 3, esperas, max_intentos=3)

    assert crm.obtener_cliente("c-1") is None
    assert len(llamadas) == 3
    assert len(esperas) == 2  # no espera después del último intento


def test_reintenta_errores_de_red_y_timeouts():
    esperas = []
    crm, llamadas = crear_cliente(
        [httpx.ReadTimeout("lento"), httpx.ConnectError("caído"), httpx.Response(200, json=CLIENTE)],
        esperas,
    )

    assert crm.obtener_cliente("c-1") == CLIENTE
    assert len(llamadas) == 3


def test_no_reintenta_errores_del_cliente():
    esperas = []
    crm, llamadas = crear_cliente([httpx.Response(404)], esperas)

    assert crm.obtener_cliente("no-existe") is None
    assert len(llamadas) == 1
    assert esperas == []


def test_respeta_el_tiempo_total():
    # Cada lectura del reloj avanza 3 s: el presupuesto de 5 s se agota tras el primer intento.
    instantes = iter(range(0, 300, 3))
    esperas = []
    crm, llamadas = crear_cliente(
        [httpx.Response(500)] * 5,
        esperas,
        max_intentos=5,
        tiempo_total=5.0,
        reloj=lambda: float(next(instantes)),
    )

    assert crm.obtener_cliente("c-1") is None
    assert len(llamadas) == 1
    assert esperas == []

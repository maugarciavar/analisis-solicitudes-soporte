import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models import FakeListChatModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import llm
from app.crm_client import ClienteCRM
from app.db import Base, get_db
from app.main import app, get_crm

CLIENTE = {"id": "c-1", "nombre": "Cliente demo", "plan": "premium"}


@pytest.fixture
def api(monkeypatch):
    """Cliente de la API con SQLite en memoria, CRM simulado y sin clave de OpenAI."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sesiones = sessionmaker(bind=engine, expire_on_commit=False)

    def db_de_prueba():
        with sesiones() as sesion:
            yield sesion

    def crm_de_prueba():
        transporte = httpx.MockTransport(lambda request: httpx.Response(200, json=CLIENTE))
        return ClienteCRM("http://crm.test", transport=transporte)

    monkeypatch.setattr(llm, "crear_modelo", lambda settings, texto: llm.crear_modelo_simulado(texto))
    app.dependency_overrides[get_db] = db_de_prueba
    app.dependency_overrides[get_crm] = crm_de_prueba
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_analiza_guarda_y_permite_consultar(api):
    solicitud = {"id": "s-1", "texto": "Urgente: el sistema está caído", "cliente_id": "c-1"}

    creado = api.post("/solicitudes/analizar", json=solicitud)

    assert creado.status_code == 200
    cuerpo = creado.json()
    assert cuerpo["estado"] == "completado"
    assert cuerpo["categoria"] == "tecnico"
    assert cuerpo["prioridad"] == "alta"
    assert cuerpo["consulta_cliente"] == "ok"
    assert cuerpo["info_cliente"] == CLIENTE
    assert cuerpo["tokens_entrada"] > 0 and cuerpo["tokens_salida"] > 0
    assert float(cuerpo["costo_estimado_usd"]) > 0

    assert api.get("/solicitudes/s-1").json() == cuerpo


def test_devuelve_404_si_no_existe(api):
    assert api.get("/solicitudes/no-existe").status_code == 404


def test_rechaza_un_id_ya_analizado(api):
    solicitud = {"id": "s-1", "texto": "¿Qué planes ofrecen?", "cliente_id": "c-1"}

    assert api.post("/solicitudes/analizar", json=solicitud).status_code == 200
    assert api.post("/solicitudes/analizar", json=solicitud).status_code == 409


def test_un_analisis_fallido_queda_registrado_y_se_puede_reintentar(api, monkeypatch):
    solicitud = {"id": "s-1", "texto": "Hola", "cliente_id": "c-1"}
    invalido = FakeListChatModel(responses=["esto no es JSON"])
    monkeypatch.setattr(llm, "crear_modelo", lambda settings, texto: invalido)

    assert api.post("/solicitudes/analizar", json=solicitud).status_code == 502
    assert api.get("/solicitudes/s-1").json()["estado"] == "fallido"

    monkeypatch.setattr(llm, "crear_modelo", lambda settings, texto: llm.crear_modelo_simulado(texto))
    reintento = api.post("/solicitudes/analizar", json=solicitud)
    assert reintento.status_code == 200
    assert reintento.json()["estado"] == "completado"

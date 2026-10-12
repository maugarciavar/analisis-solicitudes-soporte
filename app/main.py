import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import llm
from app.config import Settings, get_settings
from app.crm_client import ClienteCRM
from app.db import Base, engine, get_db
from app.graph import analizar_solicitud
from app.models import Analisis
from app.schemas import AnalisisSalida, EstadoAnalisis, SolicitudEntrada

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Suficiente para la prueba; en producción las tablas se gestionan con migraciones.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Análisis de solicitudes de soporte", lifespan=lifespan)


def get_crm(settings: Settings = Depends(get_settings)) -> ClienteCRM:
    return ClienteCRM(
        settings.crm_url,
        max_intentos=settings.crm_max_intentos,
        espera_base=settings.crm_espera_base_segundos,
        espera_maxima=settings.crm_espera_maxima_segundos,
        timeout=settings.crm_timeout_segundos,
        tiempo_total=settings.crm_tiempo_total_segundos,
    )


def _reservar(db: Session, entrada: SolicitudEntrada) -> Analisis:
    """Crea (o reutiliza, si falló antes) el registro en estado pendiente.

    Reservar el id antes de llamar al modelo evita pagar dos análisis del mismo id.
    """
    analisis = db.get(Analisis, entrada.id)
    if analisis is None:
        analisis = Analisis(id=entrada.id)
        db.add(analisis)
    elif analisis.estado != EstadoAnalisis.FALLIDO.value:
        raise HTTPException(status_code=409, detail="Ya existe un análisis para ese id")

    analisis.cliente_id = entrada.cliente_id
    analisis.texto = entrada.texto
    analisis.estado = EstadoAnalisis.PENDIENTE.value
    analisis.error = None
    try:
        db.commit()
    except IntegrityError:
        # Otra petición con el mismo id ganó la carrera.
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un análisis para ese id")
    return analisis


# Endpoints síncronos: FastAPI los ejecuta en un pool de hilos, así las llamadas
# bloqueantes (modelo, CRM, base de datos) no detienen el event loop.
@app.post("/solicitudes/analizar", response_model=AnalisisSalida)
def analizar(
    entrada: SolicitudEntrada,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    crm: ClienteCRM = Depends(get_crm),
) -> Analisis:
    analisis = _reservar(db, entrada)

    try:
        modelo = llm.crear_modelo(settings, entrada.texto)
        resultado = analizar_solicitud(entrada.texto, entrada.cliente_id, modelo, crm)
    except Exception as exc:
        # Cualquier fallo del análisis queda registrado para poder reprocesarlo.
        logger.exception("Falló el análisis de la solicitud %s", entrada.id)
        analisis.estado = EstadoAnalisis.FALLIDO.value
        analisis.error = f"{type(exc).__name__}: {exc}"[:2000]
        db.commit()
        raise HTTPException(status_code=502, detail="No fue posible analizar la solicitud")

    analisis.estado = EstadoAnalisis.COMPLETADO.value
    analisis.categoria = resultado["clasificacion"].categoria.value
    analisis.prioridad = resultado["clasificacion"].prioridad.value
    analisis.consulta_cliente = resultado["consulta_cliente"].value
    analisis.info_cliente = resultado["info_cliente"]
    analisis.respuesta_sugerida = resultado["respuesta_sugerida"]
    analisis.tokens_entrada = resultado["tokens_entrada"]
    analisis.tokens_salida = resultado["tokens_salida"]
    analisis.tokens_estimados = resultado["tokens_estimados"]
    analisis.costo_estimado_usd = llm.calcular_costo(
        resultado["tokens_entrada"], resultado["tokens_salida"], settings
    )
    db.commit()
    return analisis


@app.get("/solicitudes/{solicitud_id}", response_model=AnalisisSalida)
def obtener(solicitud_id: str, db: Session = Depends(get_db)) -> Analisis:
    analisis = db.get(Analisis, solicitud_id)
    if analisis is None:
        raise HTTPException(status_code=404, detail="No existe un análisis para ese id")
    return analisis


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

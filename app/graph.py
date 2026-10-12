import operator
from typing import Annotated, Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from app import llm
from app.crm_client import ClienteCRM
from app.schemas import Clasificacion, ConsultaCliente, Prioridad


class Estado(TypedDict, total=False):
    texto: str
    cliente_id: str
    clasificacion: Clasificacion
    consulta_cliente: ConsultaCliente
    info_cliente: dict | None
    respuesta_sugerida: str
    # Reductores: cada nodo devuelve solo su consumo y el grafo lo acumula.
    tokens_entrada: Annotated[int, operator.add]
    tokens_salida: Annotated[int, operator.add]
    tokens_estimados: Annotated[bool, operator.or_]


def _tokens(uso: llm.Uso) -> dict:
    return {
        "tokens_entrada": uso.entrada,
        "tokens_salida": uso.salida,
        "tokens_estimados": uso.estimado,
    }


def construir_grafo(modelo: BaseChatModel, crm: ClienteCRM):
    """clasificar -> (solo prioridad alta) consultar_cliente -> proponer_respuesta."""

    def clasificar(estado: Estado) -> dict:
        clasificacion, uso = llm.clasificar(modelo, estado["texto"])
        return {"clasificacion": clasificacion, **_tokens(uso)}

    def consultar_cliente(estado: Estado) -> dict:
        info = crm.obtener_cliente(estado["cliente_id"])
        return {
            "info_cliente": info,
            "consulta_cliente": ConsultaCliente.OK if info else ConsultaCliente.FALLIDA,
        }

    def proponer_respuesta(estado: Estado) -> dict:
        respuesta, uso = llm.redactar_respuesta(
            modelo, estado["texto"], estado["clasificacion"], estado.get("info_cliente")
        )
        return {"respuesta_sugerida": respuesta, **_tokens(uso)}

    def siguiente_paso(estado: Estado) -> Literal["consultar_cliente", "proponer_respuesta"]:
        if estado["clasificacion"].prioridad is Prioridad.ALTA:
            return "consultar_cliente"
        return "proponer_respuesta"

    grafo = StateGraph(Estado)
    grafo.add_node("clasificar", clasificar)
    grafo.add_node("consultar_cliente", consultar_cliente)
    grafo.add_node("proponer_respuesta", proponer_respuesta)
    grafo.add_edge(START, "clasificar")
    grafo.add_conditional_edges(
        "clasificar", siguiente_paso, ["consultar_cliente", "proponer_respuesta"]
    )
    grafo.add_edge("consultar_cliente", "proponer_respuesta")
    grafo.add_edge("proponer_respuesta", END)
    return grafo.compile()


def analizar_solicitud(
    texto: str, cliente_id: str, modelo: BaseChatModel, crm: ClienteCRM
) -> Estado:
    inicial: Estado = {
        "texto": texto,
        "cliente_id": cliente_id,
        "consulta_cliente": ConsultaCliente.NO_REQUERIDA,
        "info_cliente": None,
        "tokens_entrada": 0,
        "tokens_salida": 0,
        "tokens_estimados": False,
    }
    return construir_grafo(modelo, crm).invoke(inicial)

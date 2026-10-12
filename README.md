# Análisis de solicitudes de soporte

Servicio en FastAPI que clasifica solicitudes de soporte, consulta los datos del cliente
cuando la solicitud es urgente y propone una respuesta. El análisis es un grafo de LangGraph
y cada resultado se guarda con SQLAlchemy junto con los tokens y el costo estimado.

| Documento | Contenido |
| --- | --- |
| [ARQUITECTURA.md](ARQUITECTURA.md) | Parte 2: despliegue en Azure |
| [REVISION.md](REVISION.md) | Parte 3: revisión de código |
| [frontend/](frontend/) | Parte 4: componente y servicio de Angular |
| [RESPUESTAS.md](RESPUESTAS.md) | Parte 5: preguntas de criterio |

## Instalación

Requiere Python 3.11 o superior.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Configuración

Copie `.env.example` como `.env` y ajuste los valores. Todos tienen un valor por defecto,
de modo que el servicio arranca sin configurar nada.

| Variable | Por defecto | Descripción |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./solicitudes.db` | Conexión de SQLAlchemy. Acepta `postgresql://...` |
| `CRM_URL` | `http://localhost:9000` | Dirección de la API externa de clientes |
| `OPENAI_API_KEY` | vacía | Si está vacía se usa un modelo simulado |
| `OPENAI_MODEL` | `gpt-4o-mini` | Modelo de OpenAI cuando hay clave |
| `PRECIO_ENTRADA_POR_MILLON` | `0.15` | USD por millón de tokens de entrada |
| `PRECIO_SALIDA_POR_MILLON` | `0.60` | USD por millón de tokens de salida |
| `CRM_MAX_INTENTOS` | `3` | Intentos máximos hacia el CRM |
| `CRM_ESPERA_BASE_SEGUNDOS` | `0.5` | Espera antes del primer reintento; se duplica en cada uno |
| `CRM_ESPERA_MAXIMA_SEGUNDOS` | `4` | Tope de la espera entre reintentos |
| `CRM_TIMEOUT_SEGUNDOS` | `2` | Tiempo máximo de cada intento |
| `CRM_TIEMPO_TOTAL_SEGUNDOS` | `8` | Tiempo máximo de toda la consulta, reintentos incluidos |

## Ejecución

En dos terminales:

```bash
uvicorn mock_crm:app --port 9000
uvicorn app.main:app --port 8000
```

Con Docker, la API sola:

```bash
docker build -t analisis-solicitudes .
docker run --rm -p 8000:8000 -e CRM_URL=http://host.docker.internal:9000 analisis-solicitudes
```

O el entorno completo (API, CRM simulado y PostgreSQL):

```bash
docker compose up --build
```

Ejemplo de uso (la documentación interactiva queda en `http://localhost:8000/docs`):

```bash
curl -X POST http://localhost:8000/solicitudes/analizar \
  -H "Content-Type: application/json" \
  -d '{"id": "s-1", "texto": "Urgente: el sistema está caído", "cliente_id": "c-1"}'

curl http://localhost:8000/solicitudes/s-1
```

Con el modelo simulado, las palabras como "urgente", "caído" o "no funciona" producen prioridad
alta, lo que permite recorrer la rama del grafo que consulta al CRM.

## Pruebas

```bash
pytest
```

No necesitan red, clave de OpenAI ni el CRM en ejecución: las respuestas HTTP se simulan con
`httpx.MockTransport` y el modelo con `FakeListChatModel`.

- `tests/test_crm_client.py`: reintentos, espera progresiva, errores no reintentables y tiempo total.
- `tests/test_grafo.py`: las dos ramas del grafo, el CRM caído, los tokens y la clasificación inválida.
- `tests/test_api.py`: los endpoints con SQLite en memoria (200, 404, 409 y 502).

## Estructura

```
app/config.py       configuración desde variables de entorno
app/schemas.py      modelos de Pydantic: entrada, salida y clasificación
app/crm_client.py   cliente HTTP del CRM con reintentos
app/llm.py          llamadas al modelo, conteo de tokens, costo y fábrica de modelos
app/graph.py        grafo de LangGraph
app/models.py       tabla de análisis
app/db.py           engine y sesiones
app/main.py         endpoints
```

## Decisiones técnicas

**Grafo.** `clasificar -> consultar_cliente -> proponer_respuesta`, con una arista condicional
que salta la consulta si la prioridad no es alta. El nodo de consulta llama al CRM directamente:
es un paso determinista y no hay razón para que el modelo decida. El modelo y el cliente del CRM
se inyectan al construir el grafo, por eso las pruebas usan las mismas piezas que producción.

**Salida estructurada.** Con OpenAI se usa `with_structured_output(..., include_raw=True)`;
`include_raw` conserva el mensaje original, que es el que trae el uso de tokens. Si el modelo no
soporta salida estructurada (los simulados), se pide JSON y se valida con `PydanticOutputParser`.
La elección se hace por capacidad del modelo, no por su tipo.

**Modelo simulado.** `FakeListChatModel` recorre una lista con un índice interno, así que se crea
una instancia por solicitud: una instancia compartida mezclaría respuestas entre peticiones
concurrentes. Su clasificación sale de una regla de palabras clave.

**Reintentos.** Implementados a mano en `ClienteCRM` (unas 30 líneas) para que cada regla sea
visible: se reintenta solo ante 429, 5xx y errores de red, porque un 404 no cambia por repetir;
la espera es exponencial con tope y jitter, para que varias instancias no reintenten a la vez;
hay un tiempo máximo por intento y otro para toda la consulta. Si se agota, devuelve `None`, el
análisis continúa y el resultado lo declara en `consulta_cliente: "fallida"`.

**Tokens y costo.** Se usa `usage_metadata` cuando el modelo lo reporta. Si no, se estima con
cuatro caracteres por token y se marca `tokens_estimados: true`. No se usa `tiktoken` porque
descarga su vocabulario de internet en el primer uso. El costo se guarda calculado, con los
precios del momento, para que un cambio de precios no altere el histórico.

**Persistencia.** El `id` se reserva en estado `pendiente` antes de llamar al modelo. Así un `id`
repetido responde 409 sin gastar tokens y dos peticiones simultáneas no pagan dos análisis. Si el
análisis falla, el registro queda `fallido` con el error, la API responde 502 y el mismo `id` se
puede volver a enviar. No se inventa una clasificación por defecto.

**Endpoints síncronos.** El modelo, el CRM y la base de datos se llaman de forma bloqueante, así
que los endpoints son `def`: FastAPI los ejecuta en un pool de hilos y el event loop queda libre.

**Texto del cliente como dato.** Va delimitado en el prompt y el mensaje de sistema indica que
no se sigan instrucciones contenidas en él.

## Pendiente: qué haría y por qué

- **Evaluar las respuestas con un conjunto de casos.** La ruta de OpenAI se probó a mano con
  `gpt-4o-mini`: salida estructurada, tokens reales y un intento de inyección de prompts que el
  modelo ignoró. En esa prueba el modelo inventó un precio; se corrigió en el prompt, pero todavía
  puede describir un plan con datos que no tiene. Darle la información del producto como
  contexto y medirlo con casos fijos es el paso siguiente.
- **Migraciones con Alembic.** Las tablas se crean con `create_all` al arrancar, que no sirve
  para cambiar un esquema que ya tiene datos.
- **Proceso de reanálisis.** Un comando que tome los registros `fallido` y los `pendiente`
  antiguos (un proceso que murió a mitad) y los vuelva a analizar. Ver ARQUITECTURA.md.
- **Autenticación.** La API está abierta. Validaría el token de Entra ID (firma, audiencia y
  alcance) y habilitaría CORS solo para el origen del frontend.
- **Versión asíncrona.** Con mucho tráfico, el pool de hilos es el límite. Pasaría a
  `ainvoke`, `httpx.AsyncClient` y SQLAlchemy asíncrono.
- **Respetar `Retry-After`** en los 429 y añadir un cortacircuitos, para no insistirle a un CRM
  que está caído.
- **Registrar los tokens de un análisis fallido.** Hoy se pierden los que se consumieron antes
  del fallo, y también cuestan.
- **Observabilidad.** Logs estructurados con el `id` de la solicitud y trazas de OpenTelemetry
  por nodo del grafo.

# Arquitectura en Azure

```
Azure DevOps ──> Azure Container Registry ──> Container Apps (entorno integrado a una VNet)
                                               ├─ API (ingress HTTPS, escala por peticiones)
                                               └─ Job nocturno (cron, misma imagen)
                                                     │ identidad administrada
                          Key Vault <────────────────┤
                          PostgreSQL (privado) <─────┤──> Azure OpenAI
                          Application Insights <─────┘
```

## Despliegue de la API y proceso nocturno

- La imagen del `Dockerfile` se publica en Azure Container Registry y se despliega como una
  **Container App** con ingress HTTPS, sondas contra `/health`, escalado por peticiones
  concurrentes y un mínimo de una réplica en producción para evitar arranques en frío.
- Cada despliegue crea una **revisión** nueva, que recibe el tráfico cuando sus sondas
  responden bien. Si algo falla en producción, se reactiva la revisión anterior.
- El reanálisis nocturno es un **Container Apps Job con disparador cron**, con la misma imagen
  y otro comando. Toma los registros `fallido` y los `pendiente` antiguos, por lotes. No va
  como tarea programada dentro de la API porque con varias réplicas se ejecutaría varias veces.

## Claves y cadenas de conexión

- En **Azure Key Vault**, uno por ambiente. La Container App tiene una **identidad
  administrada** con permiso de solo lectura de secretos.
- Los secretos de Container Apps se definen como **referencias a Key Vault** y se exponen como
  variables de entorno. La aplicación no cambia: sigue leyendo `DATABASE_URL` y las demás
  variables con `pydantic-settings`.
- Donde se pueda, sin secreto: la identidad administrada autentica contra el registro de
  imágenes, Azure OpenAI y PostgreSQL (autenticación de Entra ID).

## Pipeline de CI/CD en Azure DevOps

Un pipeline YAML de varias etapas. **La imagen se construye una sola vez y es la misma que se
promueve entre ambientes**; lo que cambia es la configuración.

1. **Solicitud de cambio:** linter, `pytest` y detección de secretos. Sin esto no se fusiona.
2. **Build (rama principal):** construye la imagen, la etiqueta con el hash del commit, la
   analiza en busca de vulnerabilidades y la publica en el registro.
3. **DEV:** despliegue automático, migraciones de base de datos y pruebas de humo.
4. **QA:** aprobación manual en el *Environment* de Azure DevOps y pruebas de integración.
5. **PROD:** aprobación manual después de validar en QA, despliegue y pruebas de humo.

## PostgreSQL sin acceso público

- El entorno de Container Apps se crea **integrado a una red virtual**.
- PostgreSQL Flexible Server se expone con un **Private Endpoint** en una subred de esa red y
  una **zona DNS privada** enlazada a ella, de modo que el nombre del servidor resuelve a una
  dirección privada. Conexión con TLS obligatorio.
- Las migraciones corren como un Job dentro del mismo entorno, porque los agentes hospedados
  de Azure DevOps no alcanzan la base.

## Monitoreo y costo del modelo

- **Servicio (Application Insights):** latencia p95, tasa de errores 5xx, réplicas, conexiones a
  la base y resultado del job nocturno.
- **Negocio:** porcentaje de análisis `fallido`, porcentaje con `consulta_cliente = fallida`
  (salud del CRM), reintentos hacia el CRM y clasificaciones inválidas.
- **Modelo:** tokens y costo por solicitud (ya se guardan en la tabla), agregados por día y
  categoría, con alerta al superar un presupuesto diario.
- **Control del costo:** un modelo pequeño para clasificar; tope de tokens de salida y de tamaño
  del texto de entrada; no reanalizar un `id` ya analizado; cuota de tokens por minuto en el
  despliegue de Azure OpenAI como límite duro; y la API por lotes para el job nocturno, que no
  necesita respuesta inmediata.

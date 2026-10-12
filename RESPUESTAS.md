# Preguntas de criterio

## 1. ¿Cuándo n8n y cuándo LangGraph?

**n8n** cuando el proceso es sobre todo integrar sistemas con conectores ya hechos, el flujo es
lineal y conviene que alguien no desarrollador lo pueda leer y cambiar. Ejemplo: al llegar un
correo a soporte, resumirlo con un modelo, crear el ticket y avisar en Teams.
**LangGraph** cuando la lógica tiene estado, ramas, ciclos o pausas para aprobación humana, y debe
versionarse y probarse como código. Ejemplo: este servicio, o un agente que investiga un caso.

## 2. ¿Cómo evitar que el costo se dispare con el volumen?

Primero medir: tokens y costo por solicitud y por paso, con presupuesto y alertas. Después, usar
el modelo más pequeño que pase la evaluación en cada paso y reservar el grande para los casos
difíciles; acortar prompts y limitar los tokens de salida; aprovechar la caché de prompts y no
reprocesar lo ya analizado; usar la API por lotes para lo que no es urgente; y resolver con
reglas, sin modelo, lo que no lo necesite.

## 3. ¿Cómo evaluar la calidad de un agente antes de producción?

Con un conjunto de casos reales anonimizados y su respuesta esperada, que incluya casos límite
e intentos de inyección de prompts. Lo estructurado (categoría, prioridad) se mide con métricas
exactas; el texto libre, con una rúbrica aplicada por un modelo juez y calibrada contra una
muestra revisada por personas. Esa evaluación corre en el pipeline ante cada cambio de prompt o
de modelo. Luego, salida gradual con revisión humana de una muestra.

## 4. Un desarrollador junior rompe el pipeline con frecuencia

Primero entender por qué: casi siempre es un problema del proceso y no de la persona. Reviso con
él los últimos fallos para encontrar el patrón. Luego hago que el error sea difícil de cometer:
las mismas verificaciones en local con un solo comando, hooks de pre-commit y rama principal
protegida, de modo que un fallo bloquee su solicitud de cambio y no al equipo. Y lo acompaño:
cambios pequeños, revisión en pareja por un tiempo y seguimiento, sin señalarlo en público.

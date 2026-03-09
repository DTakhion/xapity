# QiCore + Xapity + Ollama --- Flujo de Prueba Local

Este documento describe el flujo completo para probar:

-   Ollama (modelo base)
-   Xapity (orquestador)
-   QiCore (motor de evaluación y control de riesgo)
-   Registro de uso (quota tracking)

------------------------------------------------------------------------

# Preparación del entorno

## Terminal 1 --- Iniciar Ollama

``` bash
ollama serve
```

Debe quedar escuchando en:

http://localhost:11434

------------------------------------------------------------------------

## Terminal 2 --- Descargar modelo

``` bash
ollama pull llama3.2
```

Verificar que esté disponible:

``` bash
ollama list
```

------------------------------------------------------------------------

## Terminal 3 --- Levantar Xapity

Desde la raíz del proyecto `xapity`:

``` bash
uvicorn api.main:app --reload --port 8000
```

Servidor disponible en:

http://127.0.0.1:8000

------------------------------------------------------------------------

# Pruebas de endpoints

## A. Prueba directa contra Ollama (sin QiCore)

``` bash
curl -s -X POST "http://127.0.0.1:8000/llm/generate" \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: test-001" \
  -d '{
        "prompt":"Dame el PIB exacto de Chile 2024 con fuente oficial y número exacto.",
        "temperature":0.2
      }'
```

Esperamos: - Respuesta cruda del modelo - Sin bloqueo - Sin evaluación
de riesgo

------------------------------------------------------------------------

## B. Prueba con Gate (Ollama + QiCore)

``` bash
curl -s -X POST "http://127.0.0.1:8000/lab/gate" \
  -H "Content-Type: application/json" \
  -d '{
        "prompt":"Dame el PIB exacto de Chile 2024 con fuente oficial y número exacto.",
        "temperature":0.2
      }'
```

Resultado esperado si hay señales de riesgo:

-   "blocked": true
-   "reason_codes": \["CONTRADICTION"\]
-   "risk_score": alto

------------------------------------------------------------------------

## C. Prompt seguro (no debería bloquear)

``` bash
curl -s -X POST "http://127.0.0.1:8000/lab/gate" \
  -H "Content-Type: application/json" \
  -d '{
        "prompt":"Explica en 5 bullets qué es una alucinación en un LLM.",
        "temperature":0.2
      }'
```

Resultado esperado:

-   "blocked": false
-   "risk_score": bajo

------------------------------------------------------------------------

# Validar registro de uso (Quota)

Cada ejecución vía `/lab/gate` debe:

-   Registrar tokens_in
-   Registrar tokens_out
-   Actualizar usage_monthly
-   Insertar evento en usage_events

Validación en Mongo:

``` javascript
db.usage_monthly.find().pretty()
db.usage_events.find().sort({created_at:-1}).limit(5)
```

------------------------------------------------------------------------

# Arquitectura simplificada

Usuario\
↓\
Xapity (/lab/gate)\
↓\
Ollama (llama3.2)\
↓\
QiCoreEnginePiecewise\
↓\
Decision (allow / block)\
↓\
Quota commit\
↓\
Respuesta final estructurada
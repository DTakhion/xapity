# xapity

Laboratorio para pruebas de integración LLM + Middleware (QiCore).

xapity permite:
- Ejecutar modelos LLM locales vía Ollama.
- Exponer un endpoint `/llm/generate`.
- Encadenar la respuesta con QiCore (`/lab/gate`) para evaluar alucinaciones.
- Probar el flujo completo: Prompt → LLM → QiCore → Resultado.

---

# Setup Local

## Clonar repositorio

```bash
git clone https://github.com/DTakhion/xapity.git
cd xapity
```

## Crear entorno virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

# Instalación de Ollama (macOS)

Ollama es un servicio local que expone una API HTTP en `http://localhost:11434`.

## Instalar

```bash
brew install ollama
ollama --version
```

## Levantar servicio

En una terminal independiente:

```bash
ollama serve
```

Esto deja corriendo el servidor en:

```
http://localhost:11434
```

## Descargar modelo

En otra terminal:

```bash
ollama pull llama3.2
```

## Probar modelo manualmente

```bash
ollama run llama3.2
```

---

# Probar API directa de Ollama

```bash
curl http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2",
    "prompt": "Dame el PIB exacto de Chile 2024 con fuente.",
    "stream": false
}'
```

Si responde JSON con `"response": "..."` → Ollama está operativo.

---

# Levantar API de xapity

```bash
uvicorn api.main:app --reload --port 8000
```

API disponible en:

```
http://127.0.0.1:8000
```

---

# Probar Endpoint LLM

```bash
curl -X POST "http://127.0.0.1:8000/llm/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explica en 2 líneas qué es un número primo.",
    "temperature": 0.2
  }'
```

Flujo:
Prompt → Ollama → Respuesta cruda

---

# Probar Pipeline Completo (LLM + QiCore)

Asegurar configuración de variables de entorno:

```bash
export QICORE_BASE_URL="https://TU-URL-QICORE.run.app"
export QICORE_API_KEY="qk_live_..."
```

Luego ejecutar:

```bash
curl -X POST "http://127.0.0.1:8000/lab/gate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Dame el PIB exacto de Chile 2024 con fuente.",
    "temperature": 0.2
  }'
```

Flujo completo:

Prompt  
→ Ollama (respuesta raw)  
→ QiCore Gate (evaluación anti-alucinaciones)  
→ Resultado final  

---

# Estructura del Proyecto

```
xapity/
│
├── api/
│   └── main.py
│
├── services/
│   ├── ollama_client.py
│   └── qicore_client.py
│
├── requirements.txt
└── README.md
```

---

# Objetivo del Proyecto

xapity actúa como laboratorio de pruebas para:

- Comparar motores LLM (Ollama, OpenAI, Gemini, etc.)
- Evaluar alucinaciones factuales
- Medir comportamiento ante prompts de alta precisión
- Validar middleware QiCore como sistema de control

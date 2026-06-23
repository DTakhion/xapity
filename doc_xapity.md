# Primera iteración:

| Etapa del flujo                     | Componente usado             | Qué hace                                                                 |
|-----------------------------------|------------------------------|-------------------------------------------------------------------------|
| Entrada del mensaje del usuario   | XapityChatRequest            | Recibe y valida el texto enviado a Xapity.                             |
| Análisis de intención             | XapityIntentAnalysis         | Estructura el resultado del entendimiento del mensaje.                 |
| Trazabilidad técnica              | XapityResponseMetadata       | Identifica versión, fuente y modelo usado en la detección.             |
| Respuesta final del endpoint      | XapityChatResponse           | Devuelve todo consolidado en una respuesta consistente.                |

No esta considerado: historial, contexto y campos de error complejos.

# data_loader/movimientos_ventas.py

Guarda por defecto en results/ en un archivo tipo; ventas_business_5_2026-03-01_to_2026-03-31.json

``` bash
python -m data_loader.movimientos_ventas \
  --business-id 5 \
  --start-date 2026-03-01 \
  --end-date 2026-03-31 \
  --include-documents 33,34,39
```

# Arquitectura modelo RAG Xapity para MAF

xapity-backend/
│
├── rag/
│   │
│   ├── knowledge_base/
│   │   │
│   │   ├── raw/
│   │   │   └── manual_beneficios_2025_2027.pdf
│   │   │
│   │   ├── structured/
│   │   │   ├── permiso_legal_matrimonio.json
│   │   │   ├── bono_natalidad.json
│   │   │   └── permiso_nacimiento.json
│   │   │
│   │   ├── chunks/
│   │   │   └── generated_chunks.json
│   │   │
│   │   ├── embeddings/
│   │   │   └── generated_embeddings.json
│   │   │
│   │   └── prompts/
│   │       ├── system_prompt.txt
│   │       └── fallback_prompt.txt
│   │
│   ├── loaders/
│   ├── retrievers/
│   ├── vectorstores/
│   ├── llm/
│   └── utils/
│
└── main.py

Pregunta del usuario
   ↓
Clasificación de intención
   ↓
Búsqueda en conocimiento estructurado JSON
   ↓
Búsqueda semántica en chunks/embeddings
   ↓
Inyección de contexto controlado
   ↓
Prompt final
   ↓
LLM responde
   ↓
Validación mínima de respuesta

# Xapity-maf

# rag/scripts/build_chunks.py

``` bash
python rag/scripts/build_chunks.py
```

# rag/scripts/build_embeddings.py

``` bash
python rag/scripts/build_embeddings.py
```

# rag/scripts/retrieve_context.py
## Se debe tener arriba ollama 'ollama serve' y luego 'ollama pull nomic-embed-text'/'ollama pull llama3.2:3b' (terminales independientes)

``` bash
python rag/scripts/retrieve_context.py "¿Qué beneficios tiene el trabajador?"
```

# rag/scripts/answer_with_context.py
## Se debe tener arriba ollama 'ollama serve' y luego 'ollama pull llama3.2:3b' (terminales independientes)
``` bash
python rag/scripts/answer_with_context.py "¿Qué permiso tiene un padre por nacimiento de un hijo?"
```

# rag/deterministic/matcher.py

``` bash
python rag/deterministic/matcher.py
```

# rag/deterministic/responder.py

``` bash
python rag/deterministic/responder.py
```

# Para build dockerfile
``` bash
docker build --platform linux/amd64 -t xapity-api:local .
```

# levantamos api desde la imagen docker construida
``` bash
docker run --env-file .env -p 8080:8080 xapity-api:local
```
## abrimos en 


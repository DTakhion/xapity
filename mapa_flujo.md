---
marp: true
theme: default
size: 16:9
paginate: true
style: |
  section {
    background: #f8fafc;
    color: #172554;
    font-family: Arial, sans-serif;
    padding: 38px 48px;
  }
  h1 {
    font-size: 30px;
    margin-bottom: 12px;
  }
  h2 {
    font-size: 21px;
  }
  p, li {
    font-size: 18px;
  }
  table {
    width: 100%;
    font-size: 16px;
  }
  th {
    background: #dbeafe;
    color: #172554;
  }
  td {
    padding: 10px 13px;
  }
  blockquote {
    border-left: 5px solid #2563eb;
    background: #eff6ff;
    padding: 7px 15px;
    font-size: 17px;
  }
---

# 1. Xapity–Luca: arquitectura híbrida

**Flujo de una consulta comercial**

| Etapa | Componente | Función |
|:---:|---|---|
| 👤 **1** | **Usuario** | Formula una pregunta en lenguaje natural |
| ↓ **2** | `sales_agent.py` | Recibe la solicitud y coordina el flujo |
| ↓ **3** | `sales_hybrid_router.py` | Prioriza la clasificación determinista |
| ↓ **4** | `sales_intent_router.py` | Identifica intención y entidades mediante reglas |
| ↳ **5** | `sales_ollama_router.py` | Interpreta la pregunta si las reglas no resuelven |
| ↓ **6** | **Servicio especializado** | Consulta, analiza, propone o ejecuta |
| ↓ **7** | `sales_response_builder.py` | Construye la respuesta comprensible |
| ↓ **8** | `sales_agent.py` | Entrega respuesta, datos y trazabilidad |

> **`sales_intents.py`:** contrato compartido de intenciones, operaciones y entidades utilizado por los clasificadores y el agente.

---

# 2. Servicios de negocio y responsabilidades

**Una arquitectura modular con cuatro tipos de operación**

| Operación | Componente | Responsabilidad |
|:---:|---|---|
| 🔎 **QUERY** | `sales_query_service.py` | Consulta datos y calcula indicadores comerciales |
| 📊 **EXPLAIN** | `sales_analysis_service.py` | Analiza resultados y explica variaciones |
| 💡 **PROPOSE** | `sales_proposal_service.py` | Genera propuestas basadas en datos |
| ⚙️ **EXECUTE** | `sales_execute_service.py` | Realiza acciones autorizadas |

### Principios arquitectónicos

- **Interpretación híbrida:** reglas deterministas y Ollama como alternativa semántica.
- **Contrato común:** `sales_intents.py` estandariza la comunicación entre componentes.
- **Lógica controlada:** los servicios especializados realizan las operaciones comerciales.
- **Trazabilidad:** `sales_agent.py` devuelve la respuesta junto con los datos y el origen de la clasificación.

> **El LLM interpreta la pregunta; no inventa cifras ni sustituye la lógica de negocio.**

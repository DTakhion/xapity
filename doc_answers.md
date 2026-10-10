
# Xapity-Luca — Contrato de intenciones comerciales

**Módulo:** `luca/sales_intents.py`  
**Objetivo:** Definir las capacidades comerciales del agente, las operaciones que puede solicitar el usuario y la estructura normalizada del resultado de clasificación.

## 1. SalesIntent — Catálogo de capacidades comerciales

`SalesIntent` es un `Enum` que contiene las intenciones comerciales reconocidas por el agente. Cada intención representa una capacidad que posteriormente se enlaza con una función de `sales_query_service.py`.

| Categoría | SalesIntent | Capacidad comercial |
|---|---|---|
| Resumen general | `SALES_OVERVIEW` | Obtener un resumen general de ventas |
| Resumen general | `TOTAL_DOCUMENTS` | Consultar la cantidad de documentos de venta |
| Resumen general | `TOTAL_SALES_AMOUNT` | Consultar el monto total vendido |
| Resumen general | `TOTAL_CUSTOMERS` | Consultar la cantidad de clientes |
| Cuentas por cobrar | `TOTAL_RECEIVABLE` | Consultar el monto total por cobrar |
| Cuentas por cobrar | `RECEIVABLE_DOCUMENTS` | Consultar las facturas pendientes |
| Conciliación comercial | `UNRECONCILED_CUSTOMERS` | Identificar clientes no conciliados |
| Conciliación comercial | `RECONCILIATION_PROPOSAL` | Proponer posibles conciliaciones |
| Clientes | `TOP_CUSTOMERS` | Identificar los principales clientes |
| Clientes | `CUSTOMER_DETAIL` | Consultar información de un cliente específico |
| Clientes | `CUSTOMERS_WITH_MULTIPLE_DOCUMENTS` | Identificar clientes con más de un documento |
| Documentos comerciales | `CREDIT_NOTES` | Consultar notas de crédito |
| Documentos comerciales | `CANCELLED_DOCUMENTS` | Consultar documentos anulados |
| Documentos comerciales | `LINKED_DOCUMENTS` | Consultar documentos vinculados |
| Documentos comerciales | `LARGEST_DOCUMENT` | Identificar el documento de mayor monto |
| Documentos comerciales | `SMALLEST_DOCUMENT` | Identificar el documento de menor monto |
| Clasificaciones | `DOCUMENT_TYPES` | Consultar la distribución por tipo de documento |
| Clasificaciones | `DOCUMENT_STATUS` | Consultar la distribución por estado |
| Fechas y vencimientos | `DOCUMENTS_DUE_TODAY` | Consultar documentos que vencen hoy |
| Fechas y vencimientos | `DOCUMENTS_DUE_THIS_WEEK` | Consultar documentos que vencen esta semana |
| Fechas y vencimientos | `DOCUMENTS_DUE_THIS_MONTH` | Consultar documentos que vencen este mes |
| Fechas y vencimientos | `OVERDUE_DOCUMENTS` | Consultar documentos vencidos |
| Fechas y vencimientos | `DOCUMENTS_WITHOUT_DUE_DATE` | Consultar documentos sin fecha de vencimiento |
| Comparaciones y tendencias | `MONTHLY_SALES` | Consultar ventas mensuales |
| Comparaciones y tendencias | `SALES_COMPARISON` | Comparar ventas entre períodos |
| Comparaciones y tendencias | `SALES_TREND` | Analizar la evolución de las ventas |
| Control | `UNKNOWN` | Representar una intención no reconocida |

**Total:** 26 capacidades comerciales y una intención de control (`UNKNOWN`).

---

## 2. SalesOperation — Operaciones comerciales

`SalesOperation` define qué desea hacer el usuario con una capacidad comercial.

| Operación | Valor | Significado |
|---|---|---|
| `QUERY` | `query` | Consultar información comercial |
| `EXPLAIN` | `explain` | Solicitar una explicación |
| `PROPOSE` | `propose` | Solicitar una propuesta |
| `EXECUTE` | `execute` | Solicitar la ejecución de una acción |

### 2.1. Relación entre SalesIntent y SalesOperation

Una intención determina **sobre qué información se trabaja**, mientras que una operación determina **qué desea hacer el usuario con esa información**.

El módulo declara las cuatro operaciones globalmente, pero no establece una matriz de operaciones habilitadas por intención.

Por tanto, la siguiente tabla es una matriz de documentación pendiente de verificar, no una afirmación de que todas las combinaciones estén implementadas.

| SalesIntent | QUERY | EXPLAIN | PROPOSE | EXECUTE |
|---|:---:|:---:|:---:|:---:|
| `SALES_OVERVIEW` | ? | ? | ? | ? |
| `TOTAL_DOCUMENTS` | ? | ? | ? | ? |
| `TOTAL_SALES_AMOUNT` | ? | ? | ? | ? |
| `TOTAL_CUSTOMERS` | ? | ? | ? | ? |
| `TOTAL_RECEIVABLE` | ? | ? | ? | ? |
| `RECEIVABLE_DOCUMENTS` | ? | ? | ? | ? |
| `UNRECONCILED_CUSTOMERS` | ? | ? | ? | ? |
| `RECONCILIATION_PROPOSAL` | ? | ? | ? | ? |
| `TOP_CUSTOMERS` | ? | ? | ? | ? |
| `CUSTOMER_DETAIL` | ? | ? | ? | ? |
| `CUSTOMERS_WITH_MULTIPLE_DOCUMENTS` | ? | ? | ? | ? |
| `CREDIT_NOTES` | ? | ? | ? | ? |
| `CANCELLED_DOCUMENTS` | ? | ? | ? | ? |
| `LINKED_DOCUMENTS` | ? | ? | ? | ? |
| `LARGEST_DOCUMENT` | ? | ? | ? | ? |
| `SMALLEST_DOCUMENT` | ? | ? | ? | ? |
| `DOCUMENT_TYPES` | ? | ? | ? | ? |
| `DOCUMENT_STATUS` | ? | ? | ? | ? |
| `DOCUMENTS_DUE_TODAY` | ? | ? | ? | ? |
| `DOCUMENTS_DUE_THIS_WEEK` | ? | ? | ? | ? |
| `DOCUMENTS_DUE_THIS_MONTH` | ? | ? | ? | ? |
| `OVERDUE_DOCUMENTS` | ? | ? | ? | ? |
| `DOCUMENTS_WITHOUT_DUE_DATE` | ? | ? | ? | ? |
| `MONTHLY_SALES` | ? | ? | ? | ? |
| `SALES_COMPARISON` | ? | ? | ? | ? |
| `SALES_TREND` | ? | ? | ? | ? |

**Leyenda:** `?` = combinación pendiente de verificar en el router y los servicios.

`UNKNOWN` queda fuera de esta matriz porque representa una intención no reconocida, no una capacidad comercial.

### 2.2. Ejemplo documentado: SALES_TREND

El módulo incluye explícitamente los siguientes significados:

- `QUERY`: consultar la evolución de las ventas.
- `EXPLAIN`: explicar qué está ocurriendo con esa evolución.
- `PROPOSE`: proponer qué hacer al respecto.

No se especifica en este módulo una acción `EXECUTE` para `SALES_TREND`.

### 2.3. Ejemplos conceptuales

Los siguientes ejemplos ilustran las diferencias entre operaciones; no implican que todas estén implementadas.

| Pregunta | Intent | Operation |
|---|---|---|
| ¿Qué facturas tengo pendientes? | `RECEIVABLE_DOCUMENTS` | `QUERY` |
| ¿Por qué tengo tantas facturas pendientes? | `RECEIVABLE_DOCUMENTS` | `EXPLAIN` |
| ¿Qué acciones de cobranza propones? | `RECEIVABLE_DOCUMENTS` | `PROPOSE` |
| Envía un correo de cobranza al cliente. | `RECEIVABLE_DOCUMENTS` | `EXECUTE` |

---

## 3. IntentResult — Estructura del resultado

`IntentResult` es un `dataclass` inmutable (`frozen=True`) que representa el resultado estructurado producido por el router de intenciones.

### 3.1. Atributos

| Atributo | Tipo | Valor predeterminado | Descripción |
|---|---|---|---|
| `intent` | `SalesIntent` | Obligatorio | Intención comercial identificada |
| `confidence` | `float` | Obligatorio | Confianza entre 0.0 y 1.0 |
| `operation` | `SalesOperation` | `QUERY` | Operación solicitada |
| `entities` | `dict[str, Any]` | `{}` | Entidades extraídas de la pregunta |
| `matched_rule` | `str \| None` | `None` | Regla que produjo la clasificación |
| `normalized_question` | `str \| None` | `None` | Pregunta normalizada |
| `original_question` | `str \| None` | `None` | Pregunta original |

### 3.2. Ejemplo de resultado serializado

El método `to_dict()` devuelve un diccionario con esta estructura:

```json
{
  "intent": "customer_detail",
  "operation": "query",
  "confidence": 0.95,
  "entities": {
    "customer": "Frogmi",
    "limit": 10,
    "year": 2026,
    "month": 1
  },
  "matchedRule": "customer_detail_rule",
  "normalizedQuestion": "cuanto le he vendido a frogmi",
  "originalQuestion": "¿Cuánto le he vendido a Frogmi?",
  "isUnknown": false
}
```

Los valores son ilustrativos. La regla efectiva, las entidades y la confianza dependerán del clasificador.

### 3.3. Validaciones

El método `__post_init__()` comprueba que:

1. `intent` sea una instancia de `SalesIntent`.
2. `operation` sea una instancia de `SalesOperation`.
3. `confidence` sea numérica, excluyendo valores booleanos.
4. `confidence` esté entre `0.0` y `1.0`.
5. `entities` sea un diccionario.

Además, convierte `confidence` a `float`.

### 3.4. Propiedades y métodos auxiliares

| Elemento | Función |
|---|---|
| `is_unknown` | Indica si la intención es `UNKNOWN` |
| `has_entities` | Indica si existen entidades extraídas |
| `get_entity(name, default)` | Obtiene una entidad por nombre |
| `to_dict()` | Serializa el resultado |
| `unknown()` | Construye un resultado estándar de intención desconocida |

El método `unknown()` devuelve una intención `UNKNOWN`, confianza `0.0`, entidades vacías y, opcionalmente, la pregunta original, la normalizada y la regla asociada.

---

## 4. Implicaciones para la arquitectura híbrida

La estructura actual permite que un clasificador determinista y un futuro clasificador basado en Ollama compartan el mismo contrato `IntentResult`.

**Principio de diseño propuesto:**

- `SalesIntent` define las capacidades permitidas.
- `SalesOperation` expresa la acción solicitada.
- `IntentResult` normaliza la interpretación.
- El router decide cómo clasificar.
- Los servicios validan y ejecutan las operaciones autorizadas.

La incorporación de Ollama no requiere ampliar el catálogo de intenciones por sí sola.

**Pendiente para la siguiente revisión:** examinar `luca/sales_intent_router.py` y los servicios asociados para identificar las operaciones realmente implementadas, las reglas de clasificación, los mecanismos de confianza y el punto de integración del LLM.

Dame un resumen de mis ventas, Dame un resumen general de las ventas, Cuéntame cómo nos ha ido vendiendo
¿Cuántos documentos de venta tengo?... "¿Cuántas facturas de venta tengo?", "¿Cuántas notas de crédito tengo?, "¿Qué cantidad de facturas hemos emitido?", "Dime el número de notas de crédito"
¿Cuánto he vendido?, ¿Cuánto he vendido en marzo de 2026?, ¿Qué monto llevamos vendido este mes?, ¿Cuánto dinero hemos generado en ventas durante el año?


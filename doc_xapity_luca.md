## scripts/login.py
Login a Luca para obtener el bearer token (y la validación del businessId)

``` bash
python3 -m scripts.login
```

## tests/test_movimientos_ventas.py 
Para solo un mes 

``` bash
python3 -m tests.test_movimientos_ventas \
  --business-id 70 \
  --year 2026 \
  --month 1
```

Para todo el 2026 y persistido

``` bash
python3 -m tests.test_movimientos_ventas \
  --year 2026 \
  --month 0 \
  --persist
```

Persistir y guardar resumen local.
cuando usamos --persist, el JSON exportado guarda metadata, trace, resumen y resultado de persistencia, pero no vuelve a copiar los más de mil registros. Estos ya quedan persistidos en Mongo. Para una ejecución sin persistencia, podemos agregar --include-records si necesitamos inspeccionar el universo completo localmente.

``` bash
python3 -m tests.test_movimientos_ventas \
  --year 2026 \
  --month 0 \
  --persist \
  --save-json
```

## tests/test_sales_query_service.py

``` bash
python3 -m tests.test_sales_query_service \
  --business-id 70 \
  --year 2026 \
  --month 1
```

Esta prueba es mas valiosa. Esa segunda ejecución no se limita a imprimir resultados: compara la persistencia con los valores obtenidos directamente desde Luca y falla inmediatamente si encuentra alguna diferencia.

``` bash
python3 -m tests.test_sales_query_service \
  --business-id 70 \
  --year 2026 \
  --month 1 \
  --validate-known-january
```

Para guardar con resultados, 

``` bash
python3 -m tests.test_sales_query_service \
  --business-id 70 \
  --year 2026 \
  --month 1 \
  --validate-known-january \
  --save-json
```

``` text
sales_overview
total_documents
total_sales_amount
total_customers
total_receivable
receivable_documents
top_customers
customer_detail
customers_with_multiple_documents
credit_notes
cancelled_documents
linked_documents
largest_document
smallest_document
document_types
document_status
documents_due_today
documents_due_this_week
documents_due_this_month
overdue_documents
documents_without_due_date
monthly_sales
sales_comparison
sales_trend
unknown
```

## tests/test_sales_intent_router.py

Toda la bateria del test (unas 54 preguntas) 

``` bash
python3 -m tests.test_sales_intent_router
```

Salida facil de revisar

``` bash
python3 -m tests.test_sales_intent_router \
  --compact
```

Pregunta individual 

``` bash
python3 -m tests.test_sales_intent_router \
  --question "¿Cuánto dinero tengo por cobrar?"
```

Ver solo errores

``` bash
python3 -m tests.test_sales_intent_router \
  --only-errors
```

Guardar resultados 

``` bash
python3 -m tests.test_sales_intent_router \
  --compact \
  --save-json
```

# luca/sales_agent.py

``` bash
python3 -m luca.sales_agent \
  --business-id 5 \
  --question "¿Cuánto dinero tengo por cobrar?"
```

```text
1. sales_intents.py
   ↓
   declara QUÉ sabe responder Xapity

2. sales_intent_router.py
   ↓
   entiende QUÉ está preguntando el usuario
   + extrae entidades

3. sales_query_service.py
   ↓
   CALCULA LA RESPUESTA REAL
   leyendo luca_sales_items
```

```text
1. sales_intents.py
   → existe SALES_OVERVIEW

2. sales_intent_router.py
   → interpreta la pregunta
   → retorna IntentResult(
         intent=SALES_OVERVIEW,
         ...
     )

3. sales_query_service.py
   → get_sales_overview(...)
   → calcula los datos reales desde Mongo

4. sales_agent.py
   → conecta todo lo anterior
   → construye la respuesta final
```

```text
CAPA 1 — sales_intents.py
¿Qué capacidades existen?

CAPA 2 — sales_intent_router.py
¿Qué está preguntando el usuario?

CAPA 3 — sales_query_service.py
¿Cuál es el resultado numérico/factual correcto?

CAPA 4 — sales_agent.py
¿Qué piezas tengo que ejecutar y en qué orden?

CAPA 5 — sales_response_builder.py
¿Cómo expreso esos hechos al usuario?
```

```text
SalesIntent
MONTHLY_SALES
      │
      ├── QUERY
      │     ¿Cuánto vendí el mes pasado?
      │
      └── EXPLAIN
            ¿Por qué vendí menos el mes pasado?
```

``` text
sales_intents.py
├── SalesIntent <- Intención/Pregunta
├── SalesOperation <- Explicación/Operación
└── IntentResult
```

``` text

```


``` text

```




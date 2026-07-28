## scripts/login.py
Login a Luca para obtener el bearer token (y la validación del businessId)

``` bash
python3 -m scripts.login
```

## tests/test_movimientos_ventas.py 
Para solo un mes 

``` bash
python3 -m tests.test_movimientos_ventas \
  --year 2026 \
  --month 1
```

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

``` bash

```

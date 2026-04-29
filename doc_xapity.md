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

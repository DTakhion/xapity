# Primera iteración:

| Etapa del flujo                     | Componente usado             | Qué hace                                                                 |
|-----------------------------------|------------------------------|-------------------------------------------------------------------------|
| Entrada del mensaje del usuario   | XapityChatRequest            | Recibe y valida el texto enviado a Xapity.                             |
| Análisis de intención             | XapityIntentAnalysis         | Estructura el resultado del entendimiento del mensaje.                 |
| Trazabilidad técnica              | XapityResponseMetadata       | Identifica versión, fuente y modelo usado en la detección.             |
| Respuesta final del endpoint      | XapityChatResponse           | Devuelve todo consolidado en una respuesta consistente.                |

No esta considerado: historial, contexto y campos de error complejos.
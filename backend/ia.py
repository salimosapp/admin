"""
Cliente de inteligencia artificial para extracción de eventos.

Usa Google Gemini para analizar textos de noticias y determinar
cuáles describen eventos culturales concretos y próximos.
"""

import json

from google import genai

from backend.config import AI_API_KEY, AI_MODEL

# Constantes
MAX_TEXTO_LARGO = 2000  # caracteres máxima por texto enviado a la IA
MAX_LOG_LARGO = 200     # caracteres para logs truncados

# Cliente global de Gemini (se inicializa una vez)
_cliente = genai.Client(api_key=AI_API_KEY)

PROMPT_EXTRAER = """Sos un asistente que analiza textos de noticias/artículos culturales de Berisso, Argentina, y determina cuáles describen un EVENTO CONCRETO Y PRÓXIMO (con fecha específica, no una fiesta genérica sin fecha ni una nota vieja).

Hoy es {fecha_hoy}.

Para cada texto, determiná si es un evento concreto y futuro. Si no lo es (sin fecha, fecha pasada, nota genérica), el elemento del array debe ser: {{"es_evento": false}}

Si SÍ es un evento concreto y futuro, el elemento debe ser:
{{
  "es_evento": true,
  "titulo": "...",
  "fecha": "YYYY-MM-DD",
  "hora": "HH:MM o null si no se menciona",
  "lugar": "...",
  "categoria": "una palabra: Teatro, Música, Fiestas, u Otro",
  "precio": "texto tal cual aparece, o null si no se menciona",
  "descripcion_corta": "máximo 20 palabras"
}}

Respondé EXACTAMENTE con un array JSON con exactamente {cantidad} elementos, uno por cada texto, en el mismo orden. Sin texto extra, sin explicaciones.

Textos a analizar:
{textos}
"""


def extraer_eventos(items: list[dict], fecha_hoy: str) -> list[dict | None]:
    """
    Analiza textos con la IA y devuelve eventos extraídos.

    Args:
        items: Lista de dicts con al menos la key "texto".
        fecha_hoy: Fecha actual en formato YYYY-MM-DD.

    Returns:
        Lista del mismo largo que items. Cada elemento es:
        - dict con datos del evento si es un evento válido
        - None si no es evento o si hubo error
    """
    if not items:
        return []

    # Formatear textos para el prompt
    partes = []
    for i, item in enumerate(items):
        texto_corto = item["texto"][:MAX_TEXTO_LARGO]
        partes.append(f"\n--- TEXTO {i+1} ---\n{texto_corto}\n")
    textos_formateados = "".join(partes)

    prompt = PROMPT_EXTRAER.format(
        fecha_hoy=fecha_hoy,
        cantidad=len(items),
        textos=textos_formateados,
    )

    try:
        respuesta = _cliente.models.generate_content(
            model=AI_MODEL,
            contents=prompt,
        )
        texto_respuesta = respuesta.text.strip()
        # Limpiar fences de markdown si los hay
        texto_respuesta = (
            texto_respuesta
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )

        resultados = json.loads(texto_respuesta)

        if not isinstance(resultados, list):
            print(f"La IA no devolvió un array: {str(resultados)[:MAX_LOG_LARGO]}")
            return [None] * len(items)

        # Ajustar largo: si hay menos resultados que items, completar con None
        if len(resultados) < len(items):
            print(
                f"WARNING: Se esperaban {len(items)} resultados, "
                f"se obtuvieron {len(resultados)}"
            )
            resultados.extend([None] * (len(items) - len(resultados)))

        # Si hay más resultados que items, recortar
        resultados = resultados[:len(items)]

        # Filtrar solo eventos válidos
        eventos = []
        for resultado in resultados:
            if isinstance(resultado, dict) and resultado.get("es_evento"):
                eventos.append(resultado)
            else:
                eventos.append(None)

        return eventos

    except json.JSONDecodeError:
        print(f"La IA no devolvió un JSON válido: {texto_respuesta[:MAX_LOG_LARGO]}")
        return [None] * len(items)
    except Exception as e:
        print(f"Error consultando la IA: {e}")
        return [None] * len(items)

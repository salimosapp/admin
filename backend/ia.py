"""
Cliente de inteligencia artificial para extracción de eventos.

Usa Google Gemini para analizar textos de noticias y determinar
cuáles describen eventos culturales concretos y próximos.
"""

import json

import requests
from bs4 import BeautifulSoup

from google import genai

from backend.config import AI_API_KEY, AI_MODEL, SCRAPING_USER_AGENT

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


PROMPT_SELECTORES = """Sos un experto en HTML y CSS. Te doy el HTML del comienzo de la página {url} de un sitio de {tipo_label} de Berisso, Argentina.

Necesito que me digas los selectores CSS para extraer datos de este sitio:
- "selector_link": los links a cada noticia/artículo. SOLO si el sitio es un listado de noticias.
- "selector_item": las tarjetas/cajas de cada evento. SOLO si el sitio es una cartelera de eventos.
- "selector_imagen": la imagen dentro de cada noticia/tarjeta (opcional).
- "lugar_fijo": el nombre del lugar/teatro/cine si TODO el sitio pertenece a un solo lugar fijo (ej: un teatro). Si el sitio lista eventos de varios lugares distintos, poné null.

Respondé EXACTAMENTE con un JSON así, sin texto extra:
{{
  "selector_link": "css o null",
  "selector_item": "css o null",
  "selector_imagen": "css o null",
  "lugar_fijo": "texto o null"
}}

Reglas:
- Usá las clases reales que ves en el HTML, no inventes.
- Preferí un selector corto y representativo (ej: a.titulo3, article.obra-card).
- Si el selector principal no se corresponde con el tipo de sitio, poné null en la clave que no corresponde.

HTML:
{html}
"""


def _selectores_vacios() -> dict:
    """Devuelve un dict con todos los selectores sin detectar (None)."""
    return {
        "selector_link": None,
        "selector_item": None,
        "selector_imagen": None,
        "lugar_fijo": None,
    }


def detectar_selectores(url: str, tipo: str) -> dict:
    """
    Analiza la página de una fuente con la IA y detecta los selectores CSS.

    La IA decide:
    - selector_link: links a artículos (fuentes tipo 'listado_noticias').
    - selector_item: tarjetas de eventos (fuentes tipo 'cartelera').
    - selector_imagen: imagen dentro de cada tarjeta (opcional).
    - lugar_fijo: nombre del lugar si el sitio es de un solo lugar (solo cartelera).

    Nunca lanza excepción: si la descarga o la IA fallan, devuelve todos
    los selectores como None (es la señal de "no se pudo detectar").
    """
    # 1) Descargar la página de la fuente.
    try:
        respuesta = requests.get(url, headers={"User-Agent": SCRAPING_USER_AGENT}, timeout=15)
        respuesta.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error descargando {url} para detectar selectores: {e}")
        return _selectores_vacios()

    # Recortamos el HTML: no hace falta mandárselo todo a la IA.
    soup = BeautifulSoup(respuesta.text, "html.parser")
    html_recortado = str(soup)[:30000]

    etiqueta = "listado de noticias" if tipo == "listado_noticias" else "cartelera"
    prompt = PROMPT_SELECTORES.format(url=url, tipo_label=etiqueta, html=html_recortado)

    # 2) Preguntarle a la IA.
    try:
        respuesta = _cliente.models.generate_content(model=AI_MODEL, contents=prompt)
        texto_respuesta = (
            respuesta.text.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        datos = json.loads(texto_respuesta)
        if not isinstance(datos, dict):
            print(f"La IA no devolvió un JSON de selectores: {texto_respuesta[:MAX_LOG_LARGO]}")
            return _selectores_vacios()
    except (json.JSONDecodeError, AttributeError):
        print(f"La IA no devolvió un JSON de selectores válido")
        return _selectores_vacios()
    except Exception as e:
        print(f"Error consultando la IA para detectar selectores: {e}")
        return _selectores_vacios()

    # 3) Normalizar: solo textos no vacíos (o None).
    claves = ["selector_link", "selector_item", "selector_imagen", "lugar_fijo"]
    resultado = {}
    for clave in claves:
        valor = datos.get(clave)
        if isinstance(valor, str) and valor.strip() and valor.strip().lower() != "null":
            resultado[clave] = valor.strip()
        else:
            resultado[clave] = None
    return resultado

"""
Extractor principal de eventos culturales.

Orquesta el scraping de todas las fuentes, envía los textos a la IA
para identificar eventos, y los guarda en la base de datos.
"""

import time
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from backend.config import (
    SCRAPING_LOTE_TAMANO,
    SCRAPING_ENTRE_LOTES_PAUSA,
    SCRAPING_USER_AGENT,
)
from backend.db import conectar
from backend.fuentes import obtener_fuentes
from backend.ia import extraer_eventos
from backend.utilidades import descargar_imagen

HEADERS = {"User-Agent": SCRAPING_USER_AGENT}


# --- Helpers ---


def extraer_url_base(url: str) -> str:
    """Extrae el esquema + host de una URL. Ej: 'https://berissociudad.com.ar'."""
    return "/".join(url.split("/")[:3])


# --- Procesamiento de fuentes ---


def procesar_fuente_listado(fuente: dict) -> list[dict]:
    """
    Procesa una fuente tipo 'listado_noticias'.

    1. Descarga la página principal con los links a artículos.
    2. Sigue cada link y extrae el texto completo del artículo.
    3. Devuelve una lista de items con texto, link e imagen.
    """
    base = extraer_url_base(fuente["url"])
    respuesta = requests.get(fuente["url"], headers=HEADERS, timeout=15)
    respuesta.raise_for_status()
    soup = BeautifulSoup(respuesta.text, "html.parser")

    items = []
    for a in soup.select(fuente["selector_link"]):
        href = a.get("href")
        if not href:
            continue

        # Resolver URL relativa
        if href.startswith("./"):
            href = base + href[1:]
        elif href.startswith("/"):
            href = base + href

        # Buscar imagen en el bloque del link
        imagen_url = _extraer_imagen_del_bloque(a, base)

        # Descargar artículo completo
        texto = _descargar_articulo(href)
        if texto is None:
            continue

        items.append({
            "texto": texto,
            "link": href,
            "imagen_url": imagen_url,
            "imagen_base": base,
        })

    return items


def _extraer_imagen_del_bloque(elemento, base: str) -> str | None:
    """Busca una imagen en el bloque HTML que contiene al elemento."""
    bloque_fila = elemento.find_parent("div", class_="row")
    if not bloque_fila:
        return None

    img_tag = bloque_fila.find("img")
    if not img_tag:
        return None

    imagen_url = img_tag.get("data-src") or img_tag.get("src")
    if not imagen_url or "blankphoto" in imagen_url:
        return None

    if imagen_url.startswith("/"):
        imagen_url = base + imagen_url

    return imagen_url


def _descargar_articulo(url: str) -> str | None:
    """Descarga una página y extrae su texto completo."""
    try:
        respuesta = requests.get(url, headers=HEADERS, timeout=15)
        respuesta.raise_for_status()
        soup = BeautifulSoup(respuesta.text, "html.parser")
        return soup.get_text(" ", strip=True)
    except requests.exceptions.RequestException as e:
        print(f"  Error leyendo {url}: {e}")
        return None


def procesar_fuente_cartelera(fuente: dict) -> list[dict]:
    """
    Procesa una fuente tipo 'cartelera'.

    Cada card de la página ya tiene el texto completo,
    no hace falta seguir links adicionales.
    """
    base = extraer_url_base(fuente["url"])
    respuesta = requests.get(fuente["url"], headers=HEADERS, timeout=15)
    respuesta.raise_for_status()
    soup = BeautifulSoup(respuesta.text, "html.parser")

    items = []
    for card in soup.select(fuente["selector_item"]):
        texto = card.get_text(" ", strip=True)

        # Agregar lugar fijo si está definido
        if fuente.get("lugar_fijo"):
            texto += f" Lugar: {fuente['lugar_fijo']}."

        # Extraer imagen de la card
        imagen_tag = (
            card.select_one(fuente["selector_imagen"])
            if fuente.get("selector_imagen")
            else None
        )
        imagen_url = (
            imagen_tag["src"]
            if imagen_tag and imagen_tag.get("src")
            else None
        )

        items.append({
            "texto": texto,
            "link": fuente["url"],
            "imagen_url": imagen_url,
            "imagen_base": base,
        })

    return items


# --- Guardado en base de datos ---


def _parsear_fecha_hora(datos: dict) -> datetime | None:
    """Convierte fecha y hora del dict de la IA a un datetime."""
    if not datos.get("fecha"):
        return None

    hora_str = datos.get("hora") or "00:00"
    try:
        return datetime.strptime(f"{datos['fecha']} {hora_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        print(f"  Fecha/hora inválida: {datos.get('fecha')} {datos.get('hora')}")
        return None


def guardar_evento(datos: dict, item: dict) -> str | None:
    """
    Guarda un evento en la base de datos y devuelve el resultado.

    Usa INSERT ... ON CONFLICT para hacer upsert:
    si ya existe un evento con el mismo título, fecha y lugar,
    actualiza precio e imagen.

    Returns:
        "nuevo" si se insertó por primera vez,
        "actualizado" si solo se actualizó uno que ya existía,
        None si hubo un error guardando.
    """
    fecha_hora = _parsear_fecha_hora(datos)

    # Descargar imagen si hay URL
    imagen_local = None
    if item.get("imagen_url"):
        imagen_local = descargar_imagen(
            item["imagen_url"],
            datos["titulo"],
            base_url=item.get("imagen_base", ""),
        )

    conexion = None
    try:
        conexion = conectar()
        cursor = conexion.cursor()

        cursor.execute("""
            INSERT INTO eventos
                (titulo, fecha_hora, lugar, categoria, precio,
                 link_fuente, descripcion, imagen_url, aprobado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, false)
            ON CONFLICT (titulo, fecha_hora, lugar)
            DO UPDATE SET
                precio = EXCLUDED.precio,
                imagen_url = COALESCE(EXCLUDED.imagen_url, eventos.imagen_url),
                actualizado_en = NOW()
            RETURNING (xmax = 0) AS insertado
        """, (
            datos["titulo"],
            fecha_hora,
            datos.get("lugar"),
            datos.get("categoria", "Otro"),
            datos.get("precio"),
            item["link"],
            datos.get("descripcion_corta"),
            imagen_local,
        ))

        # xmax = 0 significa que la fila se insertó (no se actualizó).
        fila = cursor.fetchone()
        insertado = bool(fila and fila[0])

        conexion.commit()
        cursor.close()

        return "nuevo" if insertado else "actualizado"

    except Exception as e:
        print(f"  Error guardando evento '{datos.get('titulo')}': {e}")
        if conexion:
            conexion.rollback()
        return None
    finally:
        if conexion:
            conexion.close()


# --- Orquestación ---


def ejecutar() -> dict:
    """
    Ejecuta el scraping completo de todas las fuentes.

    Flujo:
    1. Para cada fuente, descarga y parsea el HTML.
    2. Agrupa los items en lotes de SCRAPING_LOTE_TAMANO.
    3. Cada lote se envía a la IA para identificar eventos.
    4. Los eventos encontrados se guardan en la base de datos.

    Returns:
        dict con "nuevos" (insertados por primera vez),
        "actualizados" (ya existían, se actualizaron) y "total".
    """
    fecha_hoy = date.today().isoformat()
    nuevos = 0
    actualizados = 0

    for fuente in obtener_fuentes():
        # Si la fuente no tiene el selector obligatorio para su tipo
        # (porque la IA no pudo detectarlo y quedó mal configurada),
        # la salteamos con un aviso en vez de romper el lote.
        selector_obligatorio = (
            "selector_item" if fuente["tipo"] == "cartelera" else "selector_link"
        )
        if not fuente.get(selector_obligatorio):
            print(
                f"  La fuente {fuente['url']} no tiene {selector_obligatorio}; "
                f"se saltea. Revisala en /fuentes."
            )
            continue

        print(f"\nRevisando fuente ({fuente['tipo']}): {fuente['url']}")
        try:
            items = _procesar_fuente(fuente)
        except Exception as e:
            print(f"Error accediendo a {fuente['url']}: {e}")
            continue

        print(f"  {len(items)} items encontrados")

        for i in range(0, len(items), SCRAPING_LOTE_TAMANO):
            lote = items[i : i + SCRAPING_LOTE_TAMANO]
            num_lote = i // SCRAPING_LOTE_TAMANO + 1
            print(f"  Procesando lote {num_lote} ({len(lote)} items)...")

            resultados = extraer_eventos(lote, fecha_hoy)

            for item, resultado in zip(lote, resultados):
                if resultado:
                    estado = guardar_evento(resultado, item)
                    if estado == "nuevo":
                        nuevos += 1
                    elif estado == "actualizado":
                        actualizados += 1
                    print(
                        f"    ✓ Evento: {resultado['titulo']} "
                        f"({resultado['fecha']}) [{estado}]"
                    )
                else:
                    print("    · No es evento (o no se pudo interpretar)")

            # Pausa entre lotes para no saturar
            if i + SCRAPING_LOTE_TAMANO < len(items):
                time.sleep(SCRAPING_ENTRE_LOTES_PAUSA)

    total = nuevos + actualizados
    print(f"\nTotal: {total} eventos ({nuevos} nuevos, {actualizados} actualizados)")
    return {
        "total": total,
        "nuevos": nuevos,
        "actualizados": actualizados,
    }


def _procesar_fuente(fuente: dict) -> list[dict]:
    """Despacha al procesador correcto según el tipo de fuente."""
    tipo = fuente["tipo"]

    if tipo == "listado_noticias":
        return procesar_fuente_listado(fuente)

    if tipo == "cartelera":
        return procesar_fuente_cartelera(fuente)

    raise ValueError(f"Tipo de fuente desconocido: {tipo}")

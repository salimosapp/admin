"""
Panel de administración de Salimos.

Aplicación Flask con htmx para gestionar eventos culturales.
- Flask: el framework web (Python) que atiende las peticiones HTTP.
- htmx: librería JavaScript que permite "navegar" sin recargar la página,
  usando atributos como hx-get / hx-post en el HTML.

Estructura de carpetas:
- app.py: este archivo, define las rutas (URLs) de la app.
- backend/: lógica de Python (base de datos, scraping, IA).
- templates/: archivos HTML (con plantillas Jinja2).
"""

import sys
import os
import json
import logging
from datetime import datetime

# Agregamos el directorio raíz al path para que el paquete "backend"
# sea importable (Python necesita saber dónde buscar los módulos).
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, render_template, request, abort, Response

from backend.db import inicializar_db, conectar
from backend.eventos import (
    obtener_eventos,
    obtener_evento_por_id,
    toggle_aprobacion,
    eliminar_evento,
    actualizar_evento,
    aprobar_muchos,
    eliminar_muchos,
)
from backend.fuentes import (
    obtener_todas_las_fuentes,
    obtener_fuente_por_id,
    insertar_fuente,
    actualizar_fuente,
    toggle_estado,
    eliminar_fuente,
)
from backend.extractor import ejecutar
from backend.scrapings import obtener_historial
from backend.ia import detectar_selectores

# Creamos la aplicación Flask.
app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Al iniciar, creamos las tablas en la base de datos si no existen.
with app.app_context():
    inicializar_db()


# --- Helpers ---


def _render_pagina(plantilla: str, seccion: str = "", **contexto):
    """
    Decide qué devolver para cada URL:
    - Si la petición llega por htmx (cabecera HX-Request), devuelve SOLO el
      parcial (pedazo de HTML), que htmx inyecta sin recargar.
    - Si el navegador pidió la página directo (ej: refrescar en /inicio,
      o escribir la URL a mano), devuelve la página COMPLETA con los estilos,
      con el parcial ya adentro. Así nunca se ve "sin estilo".

    "seccion" indica qué item del menú debe quedar resaltado.
    """
    parcial = render_template(plantilla, **contexto)
    if request.headers.get("HX-Request"):
        return parcial
    return render_template("index.html", contenido=parcial, seccion=seccion)


def _leer_filtros() -> tuple[str, str, bool | None]:
    """
    Lee los filtros que llegan por URL (GET) o formulario (POST):
    - estado: "" (todos), "aprobados" o "pendientes".
    - q: texto de búsqueda (título, lugar o categoría).
    Devuelve (estado, q, aprobados) donde aprobados es True/False/None.
    """
    estado = request.values.get("estado", "").strip()
    q = request.values.get("q", "").strip()
    aprobados = {"aprobados": True, "pendientes": False}.get(estado)
    return estado, q, aprobados


def _render_evento_card(evento_id: int):
    """
    Devuelve la tarjeta de UN evento (con fecha formateada).
    Se usa cuando una acción modifica una sola tarjeta y htmx debe
    reemplazarla sin recargar toda la página.
    """
    evento = obtener_evento_por_id(evento_id)
    if evento is None:
        abort(404)
    if evento["fecha_hora"] is not None:
        evento["fecha_hora"] = evento["fecha_hora"].strftime("%d/%m/%Y %H:%M")
    estado, q, _ = _leer_filtros()
    return render_template(
        "partials/evento_card.html",
        evento=evento,
        estado=estado,
        q=q,
    )


def _render_grilla(mensaje: str | None = None):
    """
    Devuelve la vista de gestión de eventos (tarjetas + selección),
    respetando los filtros de estado y búsqueda vigentes.
    """
    estado, q, aprobados = _leer_filtros()
    eventos = obtener_eventos(aprobados=aprobados, texto=q)
    return _render_pagina(
        "partials/inicio.html",
        eventos=eventos,
        estado=estado,
        q=q,
        mensaje=mensaje,
        seccion="inicio",
    )


def _render_tabla():
    """Devuelve la vista de SOLO visualización de eventos (tabla), con filtros."""
    estado, q, aprobados = _leer_filtros()
    eventos = obtener_eventos(aprobados=aprobados, texto=q)
    return _render_pagina(
        "partials/eventos.html",
        eventos=eventos,
        estado=estado,
        q=q,
        seccion="eventos",
    )


def _render_fuentes(mensaje: str | None = None, error: str | None = None):
    """Devuelve la vista de administración de fuentes."""
    fuentes = obtener_todas_las_fuentes()
    return _render_pagina(
        "partials/fuentes.html",
        fuentes=fuentes,
        mensaje=mensaje,
        error=error,
        seccion="fuentes",
    )


def _parsear_ids(ids_texto: str) -> list[int]:
    """
    Convierte el texto '"1","2","3"' (que envía htmx con hx-vals) en una
    lista de números. Si viene algo raro, devuelve lista vacía.
    """
    try:
        return [int(x) for x in json.loads(ids_texto)]
    except (ValueError, TypeError, json.JSONDecodeError):
        return []


# --- Rutas de la app ---


@app.route("/")
def root():
    """Página principal: muestra el layout con el menú de navegación."""
    return _render_grilla()


@app.route("/inicio")
def inicio():
    """Vista de gestión: tarjetas de eventos con Aceptar/Modificar/Eliminar."""
    return _render_grilla()


@app.route("/eventos")
def eventos():
    """Vista de solo visualización: tabla con todos los eventos."""
    return _render_tabla()


# --- Acciones por evento ---


@app.route("/imagenes/eventos/<int:evento_id>")
def imagen_evento(evento_id: int):
    """
    Sirve la imagen de un evento desde la base de datos (columna imagen_datos).

    La base es la única fuente de verdad para las imágenes: el scraper las
    guarda ahí y tanto el panel admin como la web las sirven por esta ruta.
    """
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT imagen_datos, imagen_mime FROM eventos WHERE id = %s",
        (evento_id,),
    )
    fila = cursor.fetchone()
    cursor.close()
    conexion.close()

    if fila is None or not fila[0] or len(fila[0]) == 0:
        abort(404)

    return Response(
        bytes(fila[0]),
        mimetype=fila[1] or "image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.route("/eventos/<int:evento_id>/aprobar", methods=["POST"])
def eventos_aprobar(evento_id: int):
    """Acepta/desaprueba un evento y devuelve su tarjeta actualizada."""
    toggle_aprobacion(evento_id)
    return _render_evento_card(evento_id)


@app.route("/eventos/<int:evento_id>/eliminar", methods=["POST"])
def eventos_eliminar(evento_id: int):
    """Elimina un evento y devuelve la grilla actualizada (sin recargar)."""
    eliminar_evento(evento_id)
    return _render_grilla(mensaje="Evento eliminado.")


@app.route("/eventos/<int:evento_id>/editar")
def eventos_editar(evento_id: int):
    """Devuelve el formulario de edición reemplazando la tarjeta."""
    evento = obtener_evento_por_id(evento_id)
    if evento is None:
        abort(404)
    estado, q, _ = _leer_filtros()
    return render_template(
        "partials/evento_editar.html",
        evento=evento,
        estado=estado,
        q=q,
    )


@app.route("/eventos/<int:evento_id>/actualizar", methods=["POST"])
def eventos_actualizar(evento_id: int):
    """
    Recibe el form de edición, actualiza el evento y devuelve la tarjeta
    actualizada (para que htmx la vuelva a poner en su lugar).
    """
    evento_viejo = obtener_evento_por_id(evento_id)
    if evento_viejo is None:
        abort(404)

    # Leemos cada campo del formulario.
    titulo = request.form.get("titulo", "").strip()
    lugar = request.form.get("lugar", "").strip() or None
    categoria = request.form.get("categoria", "").strip() or None
    precio = request.form.get("precio", "").strip() or None
    descripcion = request.form.get("descripcion", "").strip() or None
    link_fuente = request.form.get("link_fuente", "").strip() or None
    aprobado = request.form.get("aprobado") == "on"

    # La fecha llega como "YYYY-MM-DD HH:MM". Si no se puede interpretar,
    # conservamos la fecha que ya tenía el evento.
    fecha_texto = request.form.get("fecha_hora", "").strip()
    try:
        fecha_hora = datetime.strptime(fecha_texto, "%Y-%m-%d %H:%M")
    except ValueError:
        fecha_hora = evento_viejo["fecha_hora"]

    actualizar_evento(
        evento_id, titulo, fecha_hora, lugar, categoria,
        precio, descripcion, link_fuente, aprobado,
    )
    return _render_evento_card(evento_id)


# --- Acciones en lote (con checkboxes) ---


@app.route("/eventos/aprobar-batch", methods=["POST"])
def eventos_aprobar_batch():
    """Aproba todos los eventos seleccionados a la vez."""
    ids = _parsear_ids(request.form.get("ids", "[]"))
    aprobar_muchos(ids)
    mensaje = (
        f"Se aprobaron {len(ids)} evento(s)."
        if ids else "No seleccionaste ningún evento."
    )
    return _render_grilla(mensaje=mensaje)


@app.route("/eventos/eliminar-batch", methods=["POST"])
def eventos_eliminar_batch():
    """Elimina todos los eventos seleccionados a la vez."""
    ids = _parsear_ids(request.form.get("ids", "[]"))
    eliminar_muchos(ids)
    mensaje = (
        f"Se eliminaron {len(ids)} evento(s)."
        if ids else "No seleccionaste ningún evento."
    )
    return _render_grilla(mensaje=mensaje)


# --- Fuentes ---


@app.route("/fuentes")
def fuentes():
    """Lista todas las fuentes de scraping (activas e inactivas)."""
    return _render_fuentes()


@app.route("/fuentes/nueva", methods=["POST"])
def fuentes_nueva():
    """Crea una fuente nueva. La IA detecta los selectores automáticamente."""
    nombre = request.form.get("nombre", "").strip()
    tipo = request.form.get("tipo", "").strip()
    url = request.form.get("url", "").strip()

    if not nombre or not tipo or not url:
        return _render_fuentes(
            error="Faltan datos obligatorios (nombre, tipo y URL)."
        )

    # La IA mira la página y detecta los selectores según el tipo elegido.
    detectados = detectar_selectores(url, tipo)

    # El selector obligatorio depende del tipo de fuente.
    selector_clave = "selector_item" if tipo == "cartelera" else "selector_link"
    tiene_selector = bool(detectados.get(selector_clave))

    insertar_fuente(
        nombre=nombre,
        tipo=tipo,
        url=url,
        selector_link=detectados.get("selector_link"),
        selector_item=detectados.get("selector_item"),
        selector_imagen=detectados.get("selector_imagen"),
        lugar_fijo=detectados.get("lugar_fijo"),
        activa=tiene_selector,
    )

    if tiene_selector:
        partes = [
            f"{campo.replace('_', ' ')}: {valor}"
            for campo, valor in detectados.items()
            if valor
        ]
        mensaje = "Fuente guardada. Selectores detectados por la IA: " + ", ".join(partes) + "."
    else:
        mensaje = (
            "La fuente se guardó pero la IA no encontró los selectores; "
            "quedó desactivada para no romper el scraping. Revisá el sitio "
            "para configurarla a mano."
        )

    return _render_fuentes(mensaje=mensaje)


@app.route("/fuentes/<int:fuente_id>/editar")
def fuentes_editar(fuente_id: int):
    """Devuelve el pop-up de edición de una fuente."""
    fuente = obtener_fuente_por_id(fuente_id)
    if fuente is None:
        abort(404)
    return render_template("partials/fuente_editar.html", fuente=fuente)


@app.route("/fuentes/<int:fuente_id>/actualizar", methods=["POST"])
def fuentes_actualizar(fuente_id: int):
    """Recibe el form de edición y actualiza la fuente."""
    fuente = obtener_fuente_por_id(fuente_id)
    if fuente is None:
        abort(404)

    nombre = request.form.get("nombre", "").strip()
    tipo = request.form.get("tipo", "").strip()
    url = request.form.get("url", "").strip()

    if not nombre or not tipo or not url:
        return _render_fuentes(
            error="Faltan datos obligatorios (nombre, tipo y URL)."
        )

    actualizar_fuente(
        fuente_id,
        nombre=nombre,
        tipo=tipo,
        url=url,
        selector_link=request.form.get("selector_link", "").strip() or None,
        selector_item=request.form.get("selector_item", "").strip() or None,
        selector_imagen=request.form.get("selector_imagen", "").strip() or None,
        lugar_fijo=request.form.get("lugar_fijo", "").strip() or None,
        activa=request.form.get("activa") == "on",
    )

    return _render_fuentes(mensaje=f"Fuente «{nombre}» actualizada.")


@app.route("/fuentes/<int:fuente_id>/estado", methods=["POST"])
def fuentes_cambiar_estado(fuente_id: int):
    """Activa o desactiva una fuente sin borrarla."""
    toggle_estado(fuente_id)
    return _render_fuentes()


@app.route("/fuentes/<int:fuente_id>/eliminar", methods=["POST"])
def fuentes_eliminar(fuente_id: int):
    """Borra definitivamente una fuente."""
    fuente = obtener_fuente_por_id(fuente_id)
    if fuente is None:
        abort(404)
    eliminar_fuente(fuente_id)
    return _render_fuentes(mensaje=f"Fuente «{fuente['nombre']}» eliminada.")


@app.route("/fuentes/<int:fuente_id>/probar", methods=["POST"])
def fuentes_probar(fuente_id: int):
    """Escrapea UNA sola fuente y muestra el resultado."""
    fuente = obtener_fuente_por_id(fuente_id)
    if fuente is None:
        abort(404)

    if not fuente["activa"]:
        return _render_fuentes(
            error=f"La fuente «{fuente['nombre']}» está desactivada; "
                  f"activala para poder probarla."
        )

    selector_obligatorio = (
        "selector_item" if fuente["tipo"] == "cartelera" else "selector_link"
    )
    if not fuente.get(selector_obligatorio):
        etiqueta = "items" if fuente["tipo"] == "cartelera" else "links"
        return _render_fuentes(
            error=f"La fuente «{fuente['nombre']}» no tiene selector de {etiqueta}; "
                  f"editá la fuente para configurarlo."
        )

    resultado = ejecutar(fuente_id=fuente_id)

    partes = [
        f"{resultado['nuevos']} nuevo(s)",
        f"{resultado['actualizados']} actualizado(s)",
    ]
    if resultado["errores"]:
        partes.append(f"{resultado['errores']} con error")
    partes.append(f"{resultado['duracion']} seg")
    mensaje = f"Fuente «{fuente['nombre']}» escrapeada: {', '.join(partes)}."

    return _render_fuentes(mensaje=mensaje)


# --- Scraping ---


@app.route("/scraping")
def scraping():
    """Vista con el botón que inicia el scraping y el historial de corridas."""
    historial = obtener_historial()
    return _render_pagina(
        "partials/scraping.html",
        historial=historial,
        seccion="scraping",
    )


@app.route("/scraping/iniciar", methods=["POST"])
def scraping_iniciar():
    """Recorre las fuentes, extrae eventos con IA y los guarda en la base."""
    resultado = ejecutar()
    historial = obtener_historial()
    return _render_pagina(
        "partials/scraping.html",
        historial=historial,
        resultado=resultado,
        seccion="scraping",
    )


if __name__ == "__main__":
    app.run()
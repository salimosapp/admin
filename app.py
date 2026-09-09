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

from flask import Flask, render_template, request, abort

from backend.db import inicializar_db
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
    insertar_fuente,
    toggle_estado,
)
from backend.extractor import ejecutar
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


def _render_pagina(plantilla: str, **contexto):
    """
    Decide qué devolver para cada URL:
    - Si la petición llega por htmx (cabecera HX-Request), devuelve SOLO el
      parcial (pedazo de HTML), que htmx inyecta sin recargar.
    - Si el navegador pidió la página directo (ej: refrescar en /inicio,
      o escribir la URL a mano), devuelve la página COMPLETA con los estilos,
      con el parcial ya adentro. Así nunca se ve "sin estilo".
    """
    parcial = render_template(plantilla, **contexto)
    if request.headers.get("HX-Request"):
        return parcial
    return render_template("index.html", contenido=parcial)


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
    return render_template("partials/evento_card.html", evento=evento)


def _render_grilla():
    """Devuelve la vista de gestión de eventos (tarjetas + selección)."""
    eventos = obtener_eventos()
    return _render_pagina("partials/inicio.html", eventos=eventos)


def _render_tabla():
    """Devuelve la vista de SOLO visualización de eventos (tabla)."""
    eventos = obtener_eventos()
    return _render_pagina("partials/eventos.html", eventos=eventos)


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


@app.route("/eventos/<int:evento_id>/aprobar", methods=["POST"])
def eventos_aprobar(evento_id: int):
    """Acepta/desaprueba un evento y devuelve su tarjeta actualizada."""
    toggle_aprobacion(evento_id)
    return _render_evento_card(evento_id)


@app.route("/eventos/<int:evento_id>/eliminar", methods=["POST"])
def eventos_eliminar(evento_id: int):
    """Elimina un evento y devuelve la grilla actualizada (sin recargar)."""
    eliminar_evento(evento_id)
    eventos = obtener_eventos()
    return render_template(
        "partials/inicio.html",
        eventos=eventos,
        mensaje="Evento eliminado.",
    )


@app.route("/eventos/<int:evento_id>/editar")
def eventos_editar(evento_id: int):
    """Devuelve el formulario de edición reemplazando la tarjeta."""
    evento = obtener_evento_por_id(evento_id)
    if evento is None:
        abort(404)
    return render_template("partials/evento_editar.html", evento=evento)


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
    eventos = obtener_eventos()
    mensaje = (
        f"Se aprobaron {len(ids)} evento(s)."
        if ids else "No seleccionaste ningún evento."
    )
    return render_template("partials/inicio.html", eventos=eventos, mensaje=mensaje)


@app.route("/eventos/eliminar-batch", methods=["POST"])
def eventos_eliminar_batch():
    """Elimina todos los eventos seleccionados a la vez."""
    ids = _parsear_ids(request.form.get("ids", "[]"))
    eliminar_muchos(ids)
    eventos = obtener_eventos()
    mensaje = (
        f"Se eliminaron {len(ids)} evento(s)."
        if ids else "No seleccionaste ningún evento."
    )
    return render_template("partials/inicio.html", eventos=eventos, mensaje=mensaje)


# --- Fuentes ---


@app.route("/fuentes")
def fuentes():
    """Lista todas las fuentes de scraping (activas e inactivas)."""
    fuentes = obtener_todas_las_fuentes()
    return _render_pagina("partials/fuentes.html", fuentes=fuentes)


@app.route("/fuentes/nueva", methods=["POST"])
def fuentes_nueva():
    """Crea una fuente nueva. La IA detecta los selectores automáticamente."""
    nombre = request.form.get("nombre", "").strip()
    tipo = request.form.get("tipo", "").strip()
    url = request.form.get("url", "").strip()

    if not nombre or not tipo or not url:
        fuentes = obtener_todas_las_fuentes()
        return render_template(
            "partials/fuentes.html",
            fuentes=fuentes,
            error="Faltan datos obligatorios (nombre, tipo y URL).",
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

    fuentes = obtener_todas_las_fuentes()

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

    return render_template(
        "partials/fuentes.html",
        fuentes=fuentes,
        mensaje=mensaje,
    )


@app.route("/fuentes/<int:fuente_id>/estado", methods=["POST"])
def fuentes_cambiar_estado(fuente_id: int):
    """Activa o desactiva una fuente sin borrarla."""
    toggle_estado(fuente_id)
    fuentes = obtener_todas_las_fuentes()
    return render_template("partials/fuentes.html", fuentes=fuentes)


# --- Scraping ---


@app.route("/scraping")
def scraping():
    """Vista con el botón que inicia el scraping."""
    return _render_pagina("partials/scraping.html")


@app.route("/scraping/iniciar", methods=["POST"])
def scraping_iniciar():
    """Recorre las fuentes, extrae eventos con IA y los guarda en la base."""
    resultado = ejecutar()
    return render_template("partials/scraping_resultado.html", resultado=resultado)


if __name__ == "__main__":
    app.run()
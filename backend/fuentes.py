"""
Fuentes de scraping.

Una "fuente" es un sitio web del que sacamos eventos (ej: Berisso Ciudad,
Cine Teatro Victoria). Acá guardamos cómo llegar a cada fuente: su URL y los
"selectores" CSS que dicen dónde están los links o las tarjetas de eventos.
"""

from backend.db import conectar


def obtener_fuentes():
    """Devuelve SOLO las fuentes activas (las que se scrapean)."""
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT id, nombre, tipo, url, selector_link, selector_item, "
        "selector_imagen, lugar_fijo, activa "
        "FROM fuentes WHERE activa = true ORDER BY id"
    )
    # Convertimos cada fila a un dict (nombre de columna -> valor).
    columnas = [desc[0] for desc in cursor.description]
    fuentes = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    cursor.close()
    conexion.close()
    return fuentes


def obtener_todas_las_fuentes():
    """Devuelve TODAS las fuentes, incluyendo las desactivadas (activa=false)."""
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT id, nombre, tipo, url, selector_link, selector_item, "
        "selector_imagen, lugar_fijo, activa "
        "FROM fuentes ORDER BY id"
    )
    columnas = [desc[0] for desc in cursor.description]
    fuentes = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    cursor.close()
    conexion.close()
    return fuentes


def insertar_fuente(nombre, tipo, url, selector_link=None, selector_item=None,
                    selector_imagen=None, lugar_fijo=None, activa=True):
    """Inserta una fuente NUEVA en la base de datos."""
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        "INSERT INTO fuentes "
        "(nombre, tipo, url, selector_link, selector_item, selector_imagen, "
        "lugar_fijo, activa) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (nombre, tipo, url, selector_link, selector_item, selector_imagen,
         lugar_fijo, activa),
    )
    conexion.commit()
    cursor.close()
    conexion.close()


def eliminar_fuente(fuente_id):
    """Desactiva una fuente (soft delete: no la borra, la apaga)."""
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("UPDATE fuentes SET activa = false WHERE id = %s", (fuente_id,))
    conexion.commit()
    cursor.close()
    conexion.close()


def toggle_estado(fuente_id):
    """
    Cambia el estado de una fuente: si estaba activa la desactiva y viceversa.
    Se usa desde el panel con el botón "Activada / Desactivada".
    """
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("UPDATE fuentes SET activa = NOT activa WHERE id = %s", (fuente_id,))
    conexion.commit()
    cursor.close()
    conexion.close()
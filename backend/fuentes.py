"""
Fuentes de scraping.

Una "fuente" es un sitio web del que sacamos eventos (ej: Berisso Ciudad,
Cine Teatro Victoria). Acá guardamos cómo llegar a cada fuente: su URL y los
"selectores" CSS que dicen dónde están los links o las tarjetas de eventos.
"""

from backend.db import conectar


COLUMNAS = (
    "id, nombre, tipo, url, selector_link, selector_item, "
    "selector_imagen, lugar_fijo, activa"
)


def obtener_fuentes():
    """Devuelve SOLO las fuentes activas (las que se scrapean)."""
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        f"SELECT {COLUMNAS} FROM fuentes WHERE activa = true ORDER BY id"
    )
    columnas = [desc[0] for desc in cursor.description]
    fuentes = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    cursor.close()
    conexion.close()
    return fuentes


def obtener_todas_las_fuentes():
    """Devuelve TODAS las fuentes, incluyendo las desactivadas (activa=false)."""
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(f"SELECT {COLUMNAS} FROM fuentes ORDER BY id")
    columnas = [desc[0] for desc in cursor.description]
    fuentes = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    cursor.close()
    conexion.close()
    return fuentes


def obtener_fuente_por_id(fuente_id: int) -> dict | None:
    """Devuelve UNA fuente (esté activa o no). None si no existe."""
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(f"SELECT {COLUMNAS} FROM fuentes WHERE id = %s", (fuente_id,))
    columnas = [desc[0] for desc in cursor.description]
    fila = cursor.fetchone()
    cursor.close()
    conexion.close()
    if fila is None:
        return None
    return dict(zip(columnas, fila))


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


def actualizar_fuente(fuente_id, nombre, tipo, url, selector_link=None,
                      selector_item=None, selector_imagen=None, lugar_fijo=None,
                      activa=True):
    """Actualiza los datos editables de una fuente."""
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        "UPDATE fuentes SET nombre = %s, tipo = %s, url = %s, "
        "selector_link = %s, selector_item = %s, selector_imagen = %s, "
        "lugar_fijo = %s, activa = %s WHERE id = %s",
        (nombre, tipo, url, selector_link, selector_item, selector_imagen,
         lugar_fijo, activa, fuente_id),
    )
    conexion.commit()
    cursor.close()
    conexion.close()


def eliminar_fuente(fuente_id):
    """Borra definitivamente una fuente de la base de datos."""
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM fuentes WHERE id = %s", (fuente_id,))
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
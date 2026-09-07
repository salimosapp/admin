"""
Fuentes de scraping.
"""

from backend.db import conectar


def obtener_fuentes():
    """Devuelve todas las fuentes activas."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, tipo, url, selector_link, selector_item, selector_imagen, lugar_fijo, activa FROM fuentes WHERE activa = true ORDER BY id")
    columnas = [desc[0] for desc in cur.description]
    fuentes = [dict(zip(columnas, fila)) for fila in cur.fetchall()]
    cur.close()
    conn.close()
    return fuentes


def obtener_todas_las_fuentes():
    """Devuelve todas las fuentes (incluyendo inactivas)."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, tipo, url, selector_link, selector_item, selector_imagen, lugar_fijo, activa FROM fuentes ORDER BY id")
    columnas = [desc[0] for desc in cur.description]
    fuentes = [dict(zip(columnas, fila)) for fila in cur.fetchall()]
    cur.close()
    conn.close()
    return fuentes


def insertar_fuente(nombre, tipo, url, selector_link=None, selector_item=None, selector_imagen=None, lugar_fijo=None):
    """Inserta una fuente nueva."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO fuentes (nombre, tipo, url, selector_link, selector_item, selector_imagen, lugar_fijo) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (nombre, tipo, url, selector_link, selector_item, selector_imagen, lugar_fijo),
    )
    conn.commit()
    cur.close()
    conn.close()


def eliminar_fuente(fuente_id):
    """Desactiva una fuente (soft delete)."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute("UPDATE fuentes SET activa = false WHERE id = %s", (fuente_id,))
    conn.commit()
    cur.close()
    conn.close()

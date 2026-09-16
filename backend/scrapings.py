"""
Historial de ejecuciones de scraping.

Guarda cada corrida (una fuente puntual o todas) con sus contadores,
para poder auditarlas desde la pestaña Scraping del panel.
"""

from backend.db import conectar


def registrar_scraping(fuente_id=None, total=0, nuevos=0, actualizados=0,
                       errores=0, duracion_seg=None) -> None:
    """Guarda una corrida de scraping en el historial."""
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        "INSERT INTO scrapings "
        "(fuente_id, total, nuevos, actualizados, errores, duracion_seg) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (fuente_id, total, nuevos, actualizados, errores, duracion_seg),
    )
    conexion.commit()
    cursor.close()
    conexion.close()


def obtener_historial(limite: int = 10) -> list[dict]:
    """
    Devuelve las últimas corridas de scraping, de la más reciente a la más vieja.
    Si la fuente fue borrada, fuente_nombre queda como None (y se muestra "borrada").
    """
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT s.id, s.fecha, s.fuente_id, s.total, s.nuevos, "
        "s.actualizados, s.errores, s.duracion_seg, f.nombre AS fuente_nombre "
        "FROM scrapings s "
        "LEFT JOIN fuentes f ON f.id = s.fuente_id "
        "ORDER BY s.id DESC LIMIT %s",
        (limite,),
    )
    columnas = [desc[0] for desc in cursor.description]
    filas = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    cursor.close()
    conexion.close()
    return filas
"""
Consultas de eventos a la base de datos.

Este módulo se encarga de leer Y modificar los eventos que viven en la tabla
`eventos`. Quien scrapea los carga, y desde el panel de administración se
pueden aprobar, modificar o eliminar.
"""

from backend.db import conectar


def _procesar_fechas(eventos: list[dict]) -> None:
    """
    Convierte la fecha_hora (objeto datetime de Python) a texto legible
    (ej: 15/11/2026 20:30), para mostrarla fácil en las plantillas.
    Modifica la lista "en el lugar" (no devuelve nada).
    """
    for evento in eventos:
        if evento["fecha_hora"] is not None:
            evento["fecha_hora"] = evento["fecha_hora"].strftime("%d/%m/%Y %H:%M")


COLUMNAS = (
    "id, titulo, fecha_hora, lugar, categoria, precio, "
    "link_fuente, descripcion, imagen_url, aprobado"
)


def obtener_eventos(aprobados=None) -> list[dict]:
    """
    Devuelve los eventos de la base, ordenados por fecha (el próximo primero).

    Args:
        aprobados: None = todos; True = solo aprobados; False = solo pendientes.
    """
    conexion = conectar()
    cursor = conexion.cursor()

    sql = f"""
        SELECT {COLUMNAS}
        FROM eventos
    """
    parametros = None
    if aprobados is not None:
        sql += " WHERE aprobado = %s"
        parametros = (aprobados,)
    sql += " ORDER BY fecha_hora ASC"

    cursor.execute(sql, parametros)
    columnas = [desc[0] for desc in cursor.description]
    eventos = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    cursor.close()
    conexion.close()

    _procesar_fechas(eventos)
    return eventos


def obtener_evento_por_id(evento_id: int) -> dict | None:
    """
    Devuelve UN evento (con su fecha SIN formatear, o sea datetime puro),
    sin importar si está aprobado o no. Se usa para editar/actualizar.
    Devuelve None si no existe.
    """
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(f"SELECT {COLUMNAS} FROM eventos WHERE id = %s", (evento_id,))
    columnas = [desc[0] for desc in cursor.description]
    fila = cursor.fetchone()
    cursor.close()
    conexion.close()

    if fila is None:
        return None
    return dict(zip(columnas, fila))


def toggle_aprobacion(evento_id: int) -> bool:
    """
    Cambia el estado "aprobado" de un evento (si estaba aprobado lo desaprueba
    y viceversa). Devuelve el estado NUEVO (True o False).
    """
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        "UPDATE eventos SET aprobado = NOT aprobado, actualizado_en = NOW() "
        "WHERE id = %s RETURNING aprobado",
        (evento_id,),
    )
    nuevo_estado = cursor.fetchone()[0]
    conexion.commit()
    cursor.close()
    conexion.close()
    return nuevo_estado


def eliminar_evento(evento_id: int) -> None:
    """Borra definitivamente un evento de la base."""
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM eventos WHERE id = %s", (evento_id,))
    conexion.commit()
    cursor.close()
    conexion.close()


def actualizar_evento(evento_id: int, titulo, fecha_hora, lugar, categoria,
                      precio, descripcion, link_fuente, aprobado) -> None:
    """
    Actualiza los datos editables de un evento (todo lo que muestra el form).
    """
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        """
        UPDATE eventos
        SET titulo = %s, fecha_hora = %s, lugar = %s, categoria = %s,
            precio = %s, descripcion = %s, link_fuente = %s,
            aprobado = %s, actualizado_en = NOW()
        WHERE id = %s
        """,
        (titulo, fecha_hora, lugar, categoria, precio,
         descripcion, link_fuente, aprobado, evento_id),
    )
    conexion.commit()
    cursor.close()
    conexion.close()


def aprobar_muchos(evento_ids: list[int]) -> None:
    """Apruena varios eventos de una (se usa con los checkboxes)."""
    if not evento_ids:
        return
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        "UPDATE eventos SET aprobado = true, actualizado_en = NOW() "
        "WHERE id = ANY(%s)",
        (evento_ids,),
    )
    conexion.commit()
    cursor.close()
    conexion.close()


def eliminar_muchos(evento_ids: list[int]) -> None:
    """Elimina varios eventos de una (se usa con los checkboxes)."""
    if not evento_ids:
        return
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM eventos WHERE id = ANY(%s)", (evento_ids,))
    conexion.commit()
    cursor.close()
    conexion.close()
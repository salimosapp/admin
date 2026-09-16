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
    "link_fuente, descripcion, imagen_url, aprobado, "
    "(imagen_datos IS NOT NULL AND octet_length(imagen_datos) > 0) AS tiene_imagen"
)


def _resolver_imagen(eventos):
    """
    Convierte la presencia de imagen en la BD a una URL servible.

    La imagen vive en la columna imagen_datos (BYTEA). La "URL" que se pasa a
    las plantillas es una ruta interna que cada app sirve desde la base
    (/imagenes/eventos/<id>). Si el evento no tiene imagen, queda None y la
    tarjeta muestra el placeholder.
    """
    for evento in eventos:
        if evento.get("tiene_imagen"):
            evento["imagen_url"] = f"/imagenes/eventos/{evento['id']}"
        else:
            evento["imagen_url"] = None


def obtener_eventos(aprobados=None, texto=None) -> list[dict]:
    """
    Devuelve los eventos de la base, ordenados por fecha (el próximo primero).

    Args:
        aprobados: None = todos; True = solo aprobados; False = solo pendientes.
        texto: si se pasa, filtra por coincidencia en título, lugar o categoría.
    """
    conexion = conectar()
    cursor = conexion.cursor()

    condiciones = ["fecha_hora >= NOW()"]
    parametros = []

    if aprobados is not None:
        condiciones.append("aprobado = %s")
        parametros.append(aprobados)

    if texto:
        condiciones.append(
            "(titulo ILIKE %s OR lugar ILIKE %s OR categoria ILIKE %s)"
        )
        patron = f"%{texto}%"
        parametros.extend([patron, patron, patron])

    sql = f"SELECT {COLUMNAS} FROM eventos"
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY fecha_hora ASC"

    cursor.execute(sql, parametros)
    columnas = [desc[0] for desc in cursor.description]
    eventos = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    cursor.close()
    conexion.close()

    _resolver_imagen(eventos)
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
    evento = dict(zip(columnas, fila))
    _resolver_imagen([evento])
    return evento


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
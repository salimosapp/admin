"""
Solicitudes de eventos enviadas por el público.

El público propone eventos desde la web (tabla `solicitudes_eventos`) y el
panel los revisa acá. Aprobar una solicitud crea el evento ya aprobado (así
aparece en la web pública) y la marca como aprobada (no la borra), para poder
"devolverla" después; eliminar sí la descarta.

El botón "Solicitar un evento" de la web depende de un interruptor que vive en
la tabla `configuracion` (clave `solicitudes_habilitadas`): el panel lo prende
o lo apaga desde acá, sin tocar la otra app.

Las tablas las crea `inicializar_db()` en backend/db.py al arrancar.
"""

from backend.db import conectar


# Columnas de la lista. En lugar de traer el BYTEA entero (que pesa), solo
# averiguamos si hay imagen con una bandera; la imagen se sirve aparte.
COLUMNAS = (
    "id, titulo, fecha_hora, lugar, categoria, precio, descripcion, "
    "link_fuente, contacto, estado, evento_id, "
    "(imagen_datos IS NOT NULL AND octet_length(imagen_datos) > 0) AS tiene_imagen"
)


def solicitudes_habilitadas() -> bool:
    """True si el interruptor de solicitudes está prendido ('true')."""
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT valor FROM configuracion WHERE clave = %s",
        ("solicitudes_habilitadas",),
    )
    fila = cursor.fetchone()
    cursor.close()
    conexion.close()

    if not fila:
        return False
    return str(fila[0]).strip().lower() in {"true", "1", "on", "si", "sí"}


def establecer_solicitudes_habilitadas(habilitada: bool) -> None:
    """
    Prende o apaga el botón "Solicitar un evento" de la web (upsert).
    """
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        """
        INSERT INTO configuracion (clave, valor)
        VALUES ('solicitudes_habilitadas', %s)
        ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor
        """,
        ("true" if habilitada else "false",),
    )
    conexion.commit()
    cursor.close()
    conexion.close()


def _resolver_imagen(solicitudes: list[dict]) -> None:
    """
    Convierte la presencia de imagen en la BD a una URL servible por el panel,
    igual que hace backend/eventos.py con los eventos.
    """
    for solicitud in solicitudes:
        if solicitud.get("tiene_imagen"):
            solicitud["imagen_url"] = f"/imagenes/solicitudes/{solicitud['id']}"
        else:
            solicitud["imagen_url"] = None


def _formatear_fechas(solicitudes: list[dict]) -> None:
    """Convierte fecha_hora (datetime) a texto legible para las plantillas."""
    for solicitud in solicitudes:
        if solicitud.get("fecha_hora") is not None:
            solicitud["fecha_hora"] = solicitud["fecha_hora"].strftime("%d/%m/%Y %H:%M")


def obtener_solicitudes() -> list[dict]:
    """
    Devuelve TODAS las solicitudes (pendientes y aprobadas), igual que Inicio
    muestra todos los eventos. Las pendientes van primero; dentro de cada grupo,
    la más nueva primero.
    """
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        f"SELECT {COLUMNAS} FROM solicitudes_eventos "
        "ORDER BY (estado = 'pendiente') DESC, creado_en DESC"
    )
    columnas = [desc[0] for desc in cursor.description]
    solicitudes = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    cursor.close()
    conexion.close()

    _resolver_imagen(solicitudes)
    _formatear_fechas(solicitudes)
    return solicitudes


def obtener_solicitud_por_id(solicitud_id: int) -> dict | None:
    """
    Devuelve UNA solicitud completa (incluida la imagen en BYTEA y su mime).
    None si no existe.
    """
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT id, titulo, fecha_hora, lugar, categoria, precio, descripcion, "
        "link_fuente, contacto, imagen_datos, imagen_mime, estado, evento_id, "
        "creado_en FROM solicitudes_eventos WHERE id = %s",
        (solicitud_id,),
    )
    columnas = [desc[0] for desc in cursor.description]
    fila = cursor.fetchone()
    cursor.close()
    conexion.close()

    if fila is None:
        return None
    return dict(zip(columnas, fila))


def obtener_solicitud_card(solicitud_id: int) -> dict | None:
    """
    Devuelve UNA solicitud lista para pintar en una tarjeta: con la URL de la
    imagen resuelta y la fecha ya formateada. None si no existe.
    """
    solicitud = obtener_solicitud_por_id(solicitud_id)
    if solicitud is None:
        return None

    solicitud["tiene_imagen"] = bool(solicitud.get("imagen_datos"))
    _resolver_imagen([solicitud])
    _formatear_fechas([solicitud])
    return solicitud


def actualizar_solicitud(solicitud_id: int, titulo, fecha_hora, lugar, categoria,
                         precio, descripcion, link_fuente, contacto) -> None:
    """Actualiza los datos editables de una solicitud antes de aprobarla."""
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute(
        """
        UPDATE solicitudes_eventos
        SET titulo = %s, fecha_hora = %s, lugar = %s, categoria = %s,
            precio = %s, descripcion = %s, link_fuente = %s, contacto = %s
        WHERE id = %s
        """,
        (titulo, fecha_hora, lugar, categoria, precio, descripcion,
         link_fuente, contacto, solicitud_id),
    )
    conexion.commit()
    cursor.close()
    conexion.close()


def aprobar_solicitud(solicitud_id: int) -> bool:
    """
    Convierte la solicitud en un evento APROBADO y la marca como aprobada
    (guarda en `evento_id` el evento que generó, para poder devolverla).

    Usa INSERT ... ON CONFLICT porque `eventos` tiene un UNIQUE sobre
    (titulo, fecha_hora, lugar): si el evento ya existía (por ejemplo un
    evento scrapeado) lo actualiza y lo aprueba en vez de fallar, pero SIN
    marcarlo como `es_solicitud`: queda visible en Inicio para gestionarlo a
    mano. Solo los eventos nuevos que genera la solicitud quedan ocultos de
    Inicio (es_solicitud = true). Devuelve False si la solicitud no existe.
    """
    solicitud = obtener_solicitud_por_id(solicitud_id)
    if solicitud is None:
        return False

    conexion = conectar()
    try:
        cursor = conexion.cursor()
        cursor.execute(
            """
            INSERT INTO eventos
                (titulo, fecha_hora, lugar, categoria, precio, descripcion,
                 link_fuente, imagen_datos, imagen_mime, aprobado, es_solicitud)
            VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s, ''), %s, %s, true, true)
            ON CONFLICT (titulo, fecha_hora, lugar)
            DO UPDATE SET
                categoria = COALESCE(EXCLUDED.categoria, eventos.categoria),
                precio = COALESCE(EXCLUDED.precio, eventos.precio),
                descripcion = COALESCE(EXCLUDED.descripcion, eventos.descripcion),
                link_fuente = COALESCE(EXCLUDED.link_fuente, eventos.link_fuente),
                imagen_datos = COALESCE(EXCLUDED.imagen_datos, eventos.imagen_datos),
                imagen_mime = COALESCE(EXCLUDED.imagen_mime, eventos.imagen_mime),
                aprobado = true,
                actualizado_en = NOW()
            RETURNING id
            """,
            (
                solicitud["titulo"],
                solicitud["fecha_hora"],
                solicitud["lugar"],
                solicitud["categoria"],
                solicitud["precio"],
                solicitud["descripcion"],
                solicitud["link_fuente"],
                solicitud["imagen_datos"],
                solicitud["imagen_mime"],
            ),
        )
        evento_id = cursor.fetchone()[0]
        cursor.execute(
            "UPDATE solicitudes_eventos "
            "SET estado = 'aprobado', evento_id = %s WHERE id = %s",
            (evento_id, solicitud_id),
        )
        conexion.commit()
        cursor.close()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()

    return True


def devolver_solicitud(solicitud_id: int) -> bool:
    """
    Deshace la aprobación: despublica el evento que creó (aprobado=false) y
    vuelve la solicitud a 'pendiente'. Devuelve False si no existe.
    """
    solicitud = obtener_solicitud_por_id(solicitud_id)
    if solicitud is None:
        return False

    conexion = conectar()
    try:
        cursor = conexion.cursor()
        if solicitud.get("evento_id"):
            cursor.execute(
                "UPDATE eventos SET aprobado = false, actualizado_en = NOW() "
                "WHERE id = %s",
                (solicitud["evento_id"],),
            )
        cursor.execute(
            "UPDATE solicitudes_eventos SET estado = 'pendiente' WHERE id = %s",
            (solicitud_id,),
        )
        conexion.commit()
        cursor.close()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()

    return True


def eliminar_solicitud(solicitud_id: int) -> int:
    """
    Descarta una solicitud.

    Si todavía estaba aprobada y el evento que generó es de origen solicitud
    (es_solicitud = true), también lo borra: así no queda un evento publicado
    en la web que el panel ya no puede gestionar (está oculto de Inicio).
    Devuelve cuántos eventos eliminó.
    """
    solicitud = obtener_solicitud_por_id(solicitud_id)

    conexion = conectar()
    try:
        cursor = conexion.cursor()
        borrados = 0
        if solicitud and solicitud.get("evento_id"):
            cursor.execute(
                "DELETE FROM eventos WHERE id = %s AND es_solicitud = true",
                (solicitud["evento_id"],),
            )
            borrados = cursor.rowcount
        cursor.execute("DELETE FROM solicitudes_eventos WHERE id = %s", (solicitud_id,))
        conexion.commit()
        cursor.close()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()

    return borrados

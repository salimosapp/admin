"""
Utilidades compartidas del proyecto.
"""

import os
import hashlib
from pathlib import Path

import requests

from backend.config import SCRAPING_USER_AGENT, IMAGENES_DIR, IMAGEN_TIMEOUT


HEADERS = {"User-Agent": SCRAPING_USER_AGENT}


def _asegurar_directorio_imagenes():
    """Crea el directorio de imágenes si no existe."""
    Path(IMAGENES_DIR).mkdir(parents=True, exist_ok=True)


def descargar_imagen(url_imagen: str, titulo: str, base_url: str = "") -> str | None:
    """
    Descarga una imagen desde una URL y la guarda con nombre hasheado.

    Args:
        url_imagen: URL de la imagen a descargar.
        titulo: Título del evento (no se usa para el nombre, pero se mantiene por compatibilidad).
        base_url: URL base para resolver URLs relativas.

    Returns:
        Ruta relativa de la imagen guardada (ej: "img/eventos/abc123.jpg"),
        o None si falla.
    """
    if not url_imagen:
        return None

    try:
        # Resolver URLs relativas
        if url_imagen.startswith("/"):
            url_imagen = base_url + url_imagen

        # Descargar
        respuesta = requests.get(
            url_imagen, headers=HEADERS, timeout=IMAGEN_TIMEOUT
        )
        respuesta.raise_for_status()

        # Validar que sea imagen
        content_type = respuesta.headers.get("Content-Type", "")
        if "image" not in content_type:
            print(f"URL no es imagen ({content_type}): {url_imagen}")
            return None

        # Generar nombre con hash MD5 (evita duplicados)
        extension = os.path.splitext(url_imagen.split("?")[0])[1] or ".jpg"
        nombre_hash = hashlib.md5(url_imagen.encode()).hexdigest()[:12]
        nombre_archivo = f"{nombre_hash}{extension}"

        # Guardar archivo
        _asegurar_directorio_imagenes()
        ruta = os.path.join(IMAGENES_DIR, nombre_archivo)
        with open(ruta, "wb") as f:
            f.write(respuesta.content)

        return Path("img", "eventos", nombre_archivo).as_posix()

    except requests.exceptions.RequestException as e:
        print(f"Error de red descargando imagen: {e}")
        return None
    except OSError as e:
        print(f"Error guardando imagen: {e}")
        return None

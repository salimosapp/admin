"""
Utilidades compartidas del proyecto.
"""

import mimetypes
from urllib.parse import urlparse

import requests

from backend.config import SCRAPING_USER_AGENT, IMAGEN_TIMEOUT


HEADERS = {"User-Agent": SCRAPING_USER_AGENT}


def descargar_imagen(url_imagen: str, titulo: str, base_url: str = "") -> tuple[bytes | None, str | None]:
    """
    Descarga una imagen y devuelve (bytes, mime_type).

    Las imágenes se guardan en la base de datos (columna imagen_datos de
    eventos), así ambas apps (admin y web) las leen desde ahí sin depender
    de archivos en disco.

    Args:
        url_imagen: URL de la imagen a descargar.
        titulo: Título del evento (se mantiene por compatibilidad).
        base_url: URL base para resolver URLs relativas.

    Returns:
        Tupla (bytes, mime). Si falla la descarga o no es imagen: (None, None).
    """
    if not url_imagen:
        return None, None

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
            return None, None

        # Inferir mime si el servidor mandó algo genérico
        mime = content_type.split(";")[0].strip()
        if mime not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
            mime = mimetypes.guess_type(urlparse(url_imagen).path)[0] or "image/jpeg"

        return respuesta.content, mime

    except requests.exceptions.RequestException as e:
        print(f"Error de red descargando imagen: {e}")
        return None, None
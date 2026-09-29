"""
Autenticación del panel.

Un único usuario administrador, con las credenciales definidas en variables de
entorno (ADMIN_USER y ADMIN_PASSWORD). No se guardan en el código: van en el
.env, que está en .gitignore, o en el panel del hosting.

La comparación de la clave usa hmac.compare_digest, que no se puede "acortar"
midiendo cuánto tarda, a diferencia de un `==` normal.
"""

import hmac

from flask import abort, redirect, request, session, url_for

from backend.config import ADMIN_USER, ADMIN_PASSWORD


def usuario_autenticado() -> bool:
    """True si la sesión actual tiene un usuario válido."""
    return session.get("usuario") == ADMIN_USER


def credenciales_validas(usuario: str, clave: str) -> bool:
    """Comprueba usuario y contraseña contra lo configurado."""
    usuario_ok = hmac.compare_digest(usuario, ADMIN_USER)
    clave_ok = hmac.compare_digest(clave, ADMIN_PASSWORD)
    return usuario_ok and clave_ok


def destino_despues_de_login() -> str:
    """A dónde redirigir tras un login exitoso.

    Toma el parámetro ?next= que envía la redirección, pero solo si apunta a
    una ruta interna. Si no, vuelve a la portada. Sin esta validación, un
    enlace como ?next=https://sitio-peligroso.com usaría la app para
    redirigir a un phishing.
    """
    destino = request.values.get("next", "")
    if destino.startswith("/") and not destino.startswith("//"):
        return destino
    return url_for("inicio")


def exigir_login():
    """
    Se ejecuta antes de cada petición (app.before_request).

   Deja pasar las rutas públicas (login, archivos estáticos) y el resto exige
    sesión abierta. Para las peticiones de htmx devuelve 401 en vez de
    redirigir: si redirigiera, htmx seguiría la redirección e inyectaría el
    HTML del login dentro de #contenido. Con un 401, el index.html escucha el
    evento y manda al navegador a /login con una recarga normal.
    """
    if request.endpoint in {"login", "static"}:
        return None

    if usuario_autenticado():
        return None

    if request.headers.get("HX-Request"):
        abort(401)

    destino = request.full_path
    if destino.endswith("?"):
        destino = destino[:-1]
    return redirect(url_for("login", next=destino))


def cerrar_sesion():
    """Vacía la sesión y vuelve al login."""
    session.clear()
    return redirect(url_for("login"))

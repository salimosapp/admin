"""
Configuración central de la aplicación.

Carga variables de entorno desde .env y las expone como constantes.
Todas las configuraciones de la app deben estar acá.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- IA ---
AI_API_KEY = os.getenv("AI_API_KEY")
AI_MODEL = os.getenv("AI_MODEL")

if not AI_API_KEY:
    raise ValueError(
        "Falta AI_API_KEY en el archivo .env. "
        "Agregala con tu clave de Google Gemini."
    )

# --- Base de datos ---
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
# Postgres administrados (Neon, Supabase) exigen conexión cifrada.
# Vacío = comportamiento por defecto de psycopg2, que sirve para tu Postgres local.
DB_SSLMODE = os.getenv("DB_SSLMODE")

# --- Sesión / login ---
# Firma las cookies de sesión. Si cambiás esta clave, se cierran las sesiones
# abiertas. Sin ella, Flask reinicia la sesión en cada arranque.
SECRET_KEY = os.getenv("SECRET_KEY") or os.urandom(32).hex()
# Credenciales del único administrador. Los valores por defecto son para
# probar en tu máquina: cambialos antes de publicar la app.
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "123456")
# La cookie de sesión solo viaja por HTTPS cuando esto está en True.
# Ponelo en True en el hosting (Render), dejalo False en local (http://).
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

# --- Scraping ---
SCRAPING_LOTE_TAMANO = 10
SCRAPING_ENTRE_LOTES_PAUSA = 2  # segundos entre lotes
SCRAPING_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# --- Imágenes ---
IMAGENES_DIR = os.path.join("static", "img", "eventos")
IMAGEN_TIMEOUT = 10  # segundos para descarga de imágenes

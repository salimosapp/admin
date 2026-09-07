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

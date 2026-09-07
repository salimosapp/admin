"""
Conexión a la base de datos.
"""

import psycopg2
from backend.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


def conectar():
    """Abre una conexión a la base de datos."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


SCHEMA = """
CREATE TABLE IF NOT EXISTS fuentes (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('listado_noticias', 'cartelera')),
    url TEXT NOT NULL,
    selector_link TEXT,
    selector_item TEXT,
    selector_imagen TEXT,
    lugar_fijo TEXT,
    activa BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS eventos (
    id SERIAL PRIMARY KEY,
    titulo TEXT NOT NULL,
    fecha_hora TIMESTAMP NOT NULL,
    lugar TEXT,
    categoria TEXT,
    precio TEXT,
    link_fuente TEXT,
    descripcion TEXT,
    imagen_url TEXT,
    aprobado BOOLEAN NOT NULL DEFAULT false,
    actualizado_en TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (titulo, fecha_hora, lugar)
);
"""


def inicializar_db():
    """Crea las tablas si no existen."""
    conn = conectar()
    conn.cursor().execute(SCHEMA)
    conn.commit()
    conn.close()

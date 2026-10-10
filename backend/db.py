"""
Conexión a la base de datos.
"""

import psycopg2
from backend.config import (
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_USER,
    DB_PASSWORD,
    DB_SSLMODE,
)


def conectar():
    """Abre una conexión a la base de datos."""
    parametros = {
        "host": DB_HOST,
        "port": DB_PORT,
        "database": DB_NAME,
        "user": DB_USER,
        "password": DB_PASSWORD,
    }
    if DB_SSLMODE:
        parametros["sslmode"] = DB_SSLMODE

    return psycopg2.connect(**parametros)


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
    imagen_datos BYTEA,
    imagen_mime TEXT,
    aprobado BOOLEAN NOT NULL DEFAULT false,
    es_solicitud BOOLEAN NOT NULL DEFAULT false,
    actualizado_en TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (titulo, fecha_hora, lugar)
);

-- Migración: si la tabla ya existía sin las columnas de imagen en BD,
-- las agregamos (IF NOT EXISTS para poder correr esto varias veces).
ALTER TABLE eventos ADD COLUMN IF NOT EXISTS imagen_datos BYTEA;
ALTER TABLE eventos ADD COLUMN IF NOT EXISTS imagen_mime TEXT;
-- Los eventos que vienen de aprobar una solicitud pública se marcan acá.
-- El panel no los muestra en Inicio/Eventos (se gestionan en Solicitudes),
-- pero la web pública sí los lee igual que a todos.
ALTER TABLE eventos ADD COLUMN IF NOT EXISTS es_solicitud BOOLEAN NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS scrapings (
    id SERIAL PRIMARY KEY,
    fecha TIMESTAMP NOT NULL DEFAULT NOW(),
    fuente_id INTEGER REFERENCES fuentes(id) ON DELETE SET NULL,
    total INTEGER NOT NULL DEFAULT 0,
    nuevos INTEGER NOT NULL DEFAULT 0,
    actualizados INTEGER NOT NULL DEFAULT 0,
    errores INTEGER NOT NULL DEFAULT 0,
    duracion_seg REAL
);

-- Tabla bisagra de configuración: el panel escribe acá valores que la web lee.
-- La clave 'solicitudes_habilitadas' prende/apaga el botón "Solicitar un evento"
-- de la web pública. La web la lee de forma defensiva: si falta o la tabla no
-- existe, el botón no aparece.
CREATE TABLE IF NOT EXISTS configuracion (
    clave VARCHAR(80) PRIMARY KEY,
    valor TEXT
);

-- Propuestas de eventos que manda el público desde la web. El panel las revisa
-- y, al aprobarlas, crea el evento en `eventos` (aprobado=true) y las marca
-- como aprobadas. `evento_id` recuerda qué evento generaron, para poder
-- "devolverlas" (despublicar) sin perder el vínculo.
-- Espejo de las columnas de `eventos` (misma base, mismas dos apps).
CREATE TABLE IF NOT EXISTS solicitudes_eventos (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(200) NOT NULL,
    fecha_hora TIMESTAMP,
    lugar VARCHAR(200),
    categoria VARCHAR(100),
    precio VARCHAR(120),
    descripcion TEXT,
    link_fuente TEXT,
    contacto VARCHAR(200),
    imagen_datos BYTEA,
    imagen_mime VARCHAR(50),
    estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',
    evento_id INTEGER,
    creado_en TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Migración: si la tabla ya existía sin la columna evento_id, la agregamos.
ALTER TABLE solicitudes_eventos ADD COLUMN IF NOT EXISTS evento_id INTEGER;
"""


def inicializar_db():
    """Crea las tablas si no existen."""
    conn = conectar()
    conn.cursor().execute(SCHEMA)
    conn.commit()
    conn.close()

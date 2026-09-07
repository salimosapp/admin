"""
Script para sembrar las fuentes iniciales en la base de datos.

Ejecutar una sola vez: python -m backend.seed
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.db import inicializar_db, conectar
from backend.fuentes import insertar_fuente


FUENTES_INICIALES = [
    {
        "nombre": "Berisso Ciudad - Cultura",
        "tipo": "listado_noticias",
        "url": "https://berissociudad.com.ar/seccion.php?s=2&ss=5&t=Cultura",
        "selector_link": "a.titulo3",
    },
    {
        "nombre": "Ahora Berisso OK - Cultura",
        "tipo": "listado_noticias",
        "url": "https://ahoraberissook.com/seccion.php?id=9&s=Cultura",
        "selector_link": "article.noticia-3 a",
    },
    {
        "nombre": "El Berissense - Cultura",
        "tipo": "listado_noticias",
        "url": "https://elberissense.com/seccion/cultura/",
        "selector_link": "article a[href*='./nota/']",
    },
    {
        "nombre": "Cine Teatro Victoria",
        "tipo": "cartelera",
        "url": "https://teatrocerca.com.ar/sala/cine-teatro-victoria",
        "selector_item": "article.obra-card",
        "selector_imagen": "img.obra-poster",
        "lugar_fijo": "Cine Teatro Victoria",
    },
]


def seed():
    inicializar_db()

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM fuentes")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()

    if count > 0:
        print(f"Ya hay {count} fuentes en la base de datos. No se sembran duplicados.")
        return

    for fuente in FUENTES_INICIALES:
        insertar_fuente(**fuente)
        print(f"  + {fuente['nombre']}")

    print(f"Se insertaron {len(FUENTES_INICIALES)} fuentes.")


if __name__ == "__main__":
    seed()

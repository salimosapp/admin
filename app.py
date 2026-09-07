"""
Panel de administración de Salimos.

Aplicación Flask con htmx para gestionar eventos culturales.
"""

import sys
import os
import logging

# Agregar el directorio raíz al path para que backend sea importable
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, render_template

from backend.db import inicializar_db
from backend.fuentes import obtener_todas_las_fuentes
from backend.extractor import ejecutar

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

with app.app_context():
    inicializar_db()


# --- Rutas de la app ---


@app.route("/")
def root():
    return render_template("index.html", pagina="inicio")


@app.route("/inicio")
def inicio():
    return render_template("partials/inicio.html")


@app.route("/eventos")
def eventos():
    return render_template("partials/eventos.html", eventos=["Evento 1", "Evento 2", "Evento 3"])


@app.route("/fuentes")
def fuentes():
    fuentes = obtener_todas_las_fuentes()
    return render_template("partials/fuentes.html", fuentes=fuentes)


@app.route("/scraping")
def scraping():
    return render_template("partials/scraping.html")


# --- Rutas de scraping ---


@app.route("/scraping/iniciar", methods=["POST"])
def scraping_iniciar():
    total = ejecutar()
    return render_template("partials/scraping_resultado.html", total=total)


if __name__ == "__main__":
    app.run()

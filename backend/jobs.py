"""
Corridas de scraping en background.

El scraping tarda varios minutos: descarga los sitios, sigue cada artículo,
manda los textos a la IA por lotes y baja las imágenes. Si eso corre dentro de
un request HTTP, gunicorn se aburre: el worker deja de contestar el heartbeat
y el master lo mata.

    [CRITICAL] WORKER TIMEOUT (pid:NN)
    [ERROR] Worker (pid:NN) was sent SIGKILL! Perhaps out of memory?

La conexión se cae a mitad de camino, la respuesta nunca llega y el botón
del panel parece no hacer nada.

Acá el scraping corre en un hilo aparte del request:
- POST /scraping/iniciar arranca la corrida y devuelve al instante.
- GET  /scraping/estado la consulta cada 2s hasta que termina.

El hilo vive dentro del proceso del worker, así que el estado no se comparte
entre procesos. Por eso el Procfile usa un solo worker: si hubiera más de uno,
el botón podría ver el estado de la corrida en otro proceso y no encontraría
nada.
"""

import threading
import traceback
from datetime import datetime

from backend.extractor import ejecutar

# Estados posibles de la corrida.
IDLE = "idle"        # no hay nada corriendo
RUNNING = "running"  # corriendo ahora
DONE = "done"        # terminó bien
ERROR = "error"      # terminó con excepción


class CorridaScraping:
    """
    Controla las corridas de scraping: una a la vez, con su estado.

    El estado vive en memoria (en este proceso). El panel lo lee por la ruta
    /scraping/estado y lo muestra mientras la corrida avanza.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hilo: threading.Thread | None = None
        self._cancelar = threading.Event()

        self.estado = IDLE
        self.mensaje = ""
        self.inicio: datetime | None = None
        self.fin: datetime | None = None
        self.resultado: dict | None = None
        self.error: str | None = None

    # --- Consultar el estado ---

    @property
    def corriendo(self) -> bool:
        """True si hay una corrida en este momento."""
        with self._lock:
            return self.estado == RUNNING

    def snapshot(self) -> dict:
        """Una foto del estado, para mandarlo a la plantilla."""
        with self._lock:
            return {
                "estado": self.estado,
                "mensaje": self.mensaje,
                "inicio": self.inicio,
                "fin": self.fin,
                "resultado": self.resultado,
                "error": self.error,
            }

    # --- Arrancar y cancelar ---

    def iniciar(self) -> bool:
        """
        Arranca una corrida en un hilo de fondo.

        Returns:
            True si la arrancó, False si ya había una corriendo.
        """
        with self._lock:
            if self.estado == RUNNING:
                return False

            self._cancelar.clear()
            self.estado = RUNNING
            self.mensaje = "Iniciando el scraping..."
            self.inicio = datetime.now()
            self.fin = None
            self.resultado = None
            self.error = None

            self._hilo = threading.Thread(
                target=self._correr,
                name="scraping",
                daemon=True,
            )
            self._hilo.start()
            return True

    def cancelar(self) -> bool:
        """
        Pide que la corrida se corte.

        No mata el hilo: le avisa y el scraping se va cortando en el próximo
        lote. Returns True si había una corrida que cortar.
        """
        with self._lock:
            if self.estado != RUNNING:
                return False
            self._cancelar.set()
            self.mensaje = "Cancelando..."
            return True

    # --- El hilo ---

    def _correr(self) -> None:
        """El cuerpo del hilo: llama al extractor y va anotando el avance."""
        try:
            resultado = ejecutar(
                progress=self._progreso,
                should_stop=self._cancelar.is_set,
            )
        except Exception as e:
            traceback.print_exc()
            with self._lock:
                self.estado = ERROR
                self.error = str(e)
                self.mensaje = f"Error: {e}"
                self.fin = datetime.now()
            return

        with self._lock:
            self.resultado = resultado
            self.estado = DONE
            self.mensaje = "Scraping terminado."
            self.fin = datetime.now()

    def _progreso(self, texto: str) -> None:
        """Guarda la última cosa que dijo el scraping (para mostrarla)."""
        with self._lock:
            self.mensaje = texto


# La corrida de la app. Es una sola porque el panel muestra una sola.
corrida_scraping = CorridaScraping()

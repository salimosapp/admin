"""
Formateo de textos para las vistas del panel.

Por ahora solo normaliza el precio (marca los eventos gratuitos). Se mantiene
separado para que las plantillas no tengan que saber cómo se detecta "gratis".
"""

# Palabras que indican que un evento es gratuito.
PALABRAS_GRATIS = ("grat", "libre", "sin cargo", "sin costo", "no pag")


def precio_display(precio) -> str | None:
    """Normaliza el precio para las tarjetas.

    - Sin precio (None/'') -> None (la línea del precio no se muestra).
    - Gratis ('Gratis', 'Entrada libre'...) -> 'Gratuito'.
    - Con costo -> el texto tal cual ('Desde $35.000').
    """
    if not precio:
        return None

    texto = str(precio).strip()
    if not texto:
        return None

    if any(palabra in texto.lower() for palabra in PALABRAS_GRATIS):
        return "Gratuito"

    return texto

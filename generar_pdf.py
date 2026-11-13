import io
from pathlib import Path
from html import escape

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, KeepTogether
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from estado_partida import consultar_estado, url_de_imagen
from imagenes import URL_UNSPLASH, ErrorImagen, con_utm, descargar_para_pdf

# Fuente incluida en el repo (permite tildes y ñ en cualquier sistema operativo)
RUTA_FUENTE = Path(__file__).parent / "fonts" / "DejaVuSans.ttf"
ANCHO_IMAGEN = 400
ALTO_MAX_IMAGEN = 260


def _imagen_del_capitulo(capitulo, estilo_credito):
    """Imagen escalada del capítulo con su crédito, o [] si no tiene o no se puede descargar.

    En la interfaz las fotos se muestran por hotlinking, pero un PDF necesita llevarlas
    adentro: acá se piden a su URL original y se incrustan desde memoria (sin guardarlas).
    """
    url = url_de_imagen(capitulo)
    if url is None:
        return []
    try:
        datos = descargar_para_pdf(url)
        ancho, alto = ImageReader(io.BytesIO(datos)).getSize()
    except (ErrorImagen, OSError, ValueError):
        return []  # sin red o foto ilegible: el capítulo sale sin imagen
    escala = min(ANCHO_IMAGEN / ancho, ALTO_MAX_IMAGEN / alto)
    imagen = capitulo["imagen"]
    credito = (
        "Foto: "
        f'<link href="{escape(con_utm(imagen["url_autor"]), quote=True)}" color="blue">'
        f"{escape(imagen['autor'])}</link> / "
        f'<link href="{escape(con_utm(URL_UNSPLASH), quote=True)}" color="blue">Unsplash</link>'
    )
    return [
        Spacer(1, 6),
        Image(io.BytesIO(datos), width=ancho * escala, height=alto * escala),
        Paragraph(credito, estilo_credito),
        Spacer(1, 10),
    ]


def generar_pdf(id_partida):
    estado = consultar_estado(id_partida)

    # El libro solo tiene sentido con la historia completa (capítulo 5 = desenlace)
    if not estado["finalizada"]:
        raise ValueError("La historia todavia no termino: solo se exporta al llegar al desenlace")

    carpeta = Path("historias_generadas")
    carpeta.mkdir(exist_ok=True)

    ruta = carpeta / f"{id_partida}.pdf"

    pdfmetrics.registerFont(TTFont("DejaVu", str(RUTA_FUENTE)))

    estilos = getSampleStyleSheet()

    for nombre in ["Title", "Heading2", "Normal"]:
        estilos[nombre].fontName = "DejaVu"

    estilo_credito = ParagraphStyle("Credito", parent=estilos["Normal"], fontSize=7)
    # Un título nunca queda solo al pie de una página
    estilos["Heading2"].keepWithNext = 1

    elementos = [Paragraph("Mi historia de misterio", estilos["Title"]), Spacer(1, 30)]

    for capitulo in estado["capitulos"]:
        # Título, imagen y crédito van juntos: si no entran en la página, pasan enteros a la siguiente
        encabezado = [Paragraph(escape(capitulo["titulo"]), estilos["Heading2"])]
        encabezado.extend(_imagen_del_capitulo(capitulo, estilo_credito))
        elementos.append(KeepTogether(encabezado))

        elementos.append(
            Paragraph(
                escape(capitulo["texto"]).replace("\n", "<br/>"), estilos["Normal"]
            )
        )

        # Buscamos la decisión tomada en este capítulo
        for decision in estado["decisiones"]:
            if decision["capitulo"] == capitulo["numero"]:
                opcion = capitulo["opciones"][decision["opcion"] - 1]

                elementos.append(Spacer(1, 12))
                elementos.append(
                    Paragraph("Tu decisión: " + escape(opcion), estilos["Normal"])
                )

        elementos.append(Spacer(1, 25))

    documento = SimpleDocTemplate(str(ruta))
    documento.build(elementos)

    return str(ruta)

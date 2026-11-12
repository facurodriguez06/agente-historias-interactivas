from pathlib import Path
from html import escape

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from estado_partida import archivo_de_imagen, consultar_estado
from imagenes import URL_UNSPLASH, con_utm

ANCHO_IMAGEN = 400
ALTO_MAX_IMAGEN = 260


def _imagen_del_capitulo(capitulo, estilo_credito):
    """Imagen escalada del capítulo con su crédito, o [] si no tiene (o falta el archivo)."""
    ruta = archivo_de_imagen(capitulo)
    if ruta is None:
        return []
    try:
        ancho, alto = ImageReader(str(ruta)).getSize()
    except Exception:
        return []  # archivo ilegible: el capítulo sale sin imagen
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
        Image(str(ruta), width=ancho * escala, height=alto * escala),
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

    # Fuente que permite escribir tildes y ñ
    fuente = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    pdfmetrics.registerFont(TTFont("DejaVu", fuente))

    estilos = getSampleStyleSheet()

    for nombre in ["Title", "Heading2", "Normal"]:
        estilos[nombre].fontName = "DejaVu"

    estilo_credito = ParagraphStyle("Credito", parent=estilos["Normal"], fontSize=7)

    elementos = [Paragraph("Mi historia de misterio", estilos["Title"]), Spacer(1, 30)]

    for capitulo in estado["capitulos"]:
        elementos.append(Paragraph(escape(capitulo["titulo"]), estilos["Heading2"]))
        elementos.extend(_imagen_del_capitulo(capitulo, estilo_credito))

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

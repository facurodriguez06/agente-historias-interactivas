from pathlib import Path
from html import escape

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from estado_partida import consultar_estado


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

    elementos = [Paragraph("Mi historia de misterio", estilos["Title"]), Spacer(1, 30)]

    for capitulo in estado["capitulos"]:
        elementos.append(Paragraph(escape(capitulo["titulo"]), estilos["Heading2"]))

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

"""Exporta la partida como un pequeño libro de misterio en formato PDF.

Usa solamente ReportLab y las funciones que ya tiene el proyecto.
No modifica el JSON ni la lógica de generación de la historia.
"""

import io
import math
import re
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from estado_partida import consultar_estado, url_de_imagen
from imagenes import URL_UNSPLASH, ErrorImagen, con_utm, descargar_para_pdf

# Paleta de novela antigua: papel marfil, tinta y acentos bordó/dorado.
PAPEL = colors.HexColor("#F5F0E4")
TINTA = colors.HexColor("#29282A")
TINTA_CLARA = colors.HexColor("#5D5753")
BURDEOS = colors.HexColor("#693D43")
DORADO = colors.HexColor("#B19565")
CAJA = colors.HexColor("#EAE0D0")
PORTADA = colors.HexColor("#20232B")
PORTADA_CLARA = colors.HexColor("#D5C5A6")

ANCHO, ALTO = A4
MARGEN_X = 60
MARGEN_SUP = 65
MARGEN_INF = 63
ANCHO_TEXTO = ANCHO - 2 * MARGEN_X


def _texto_pdf(texto):
    """Escapa HTML y convierte negritas/cursivas sencillas del relato."""
    texto = escape(str(texto or ""))
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    texto = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", texto)
    return texto


def _estilos():
    return {
        "capitulo": ParagraphStyle(
            "NumeroCapitulo", fontName="Helvetica-Bold", fontSize=8,
            leading=12, textColor=BURDEOS, spaceAfter=10,
        ),
        "titulo": ParagraphStyle(
            "TituloCapitulo", fontName="Times-Bold", fontSize=25,
            leading=29, textColor=TINTA, spaceAfter=13,
            keepWithNext=True,
        ),
        "cuerpo": ParagraphStyle(
            "CuerpoNovela", fontName="Times-Roman", fontSize=12,
            leading=17.6, textColor=TINTA, spaceAfter=10,
        ),
        "credito": ParagraphStyle(
            "CreditoFoto", fontName="Helvetica", fontSize=7.2,
            leading=10.5, textColor=TINTA_CLARA,
        ),
        "etiqueta": ParagraphStyle(
            "EtiquetaDecision", fontName="Helvetica-Bold", fontSize=8,
            leading=11, textColor=BURDEOS, spaceAfter=5,
        ),
        "decision": ParagraphStyle(
            "DecisionElegida", fontName="Times-Italic", fontSize=12.5,
            leading=17, textColor=TINTA,
        ),
        "titulo_anexo": ParagraphStyle(
            "TituloAnexo", fontName="Times-Bold", fontSize=26,
            leading=30, textColor=TINTA, spaceAfter=13,
        ),
        "subtitulo": ParagraphStyle(
            "SubtituloAnexo", fontName="Times-Bold", fontSize=16,
            leading=20, textColor=BURDEOS, spaceBefore=15, spaceAfter=9,
        ),
        "lista": ParagraphStyle(
            "ElementoAnexo", fontName="Times-Roman", fontSize=11.5,
            leading=16, leftIndent=16, firstLineIndent=-12,
            textColor=TINTA, spaceAfter=6,
        ),
        "epilogo": ParagraphStyle(
            "FinCapitulo", fontName="Helvetica-Bold", fontSize=9,
            leading=14, alignment=1, textColor=BURDEOS,
        ),
    }


def _dibujar_reloj(c, x, y, radio):
    """Ilustración vectorial para la portada, sin depender de imágenes externas."""
    c.saveState()
    c.setStrokeColor(DORADO)
    c.setLineWidth(1.1)
    c.circle(x, y, radio, stroke=1, fill=0)
    c.setLineWidth(0.5)
    c.circle(x, y, radio - 9, stroke=1, fill=0)

    for marca in range(12):
        ang = math.radians(90 - marca * 30)
        exterior = radio - 17
        interior = radio - (29 if marca % 3 == 0 else 23)
        c.setLineWidth(1.5 if marca % 3 == 0 else 0.7)
        c.line(
            x + interior * math.cos(ang),
            y + interior * math.sin(ang),
            x + exterior * math.cos(ang),
            y + exterior * math.sin(ang),
        )

    # Agujas detenidas a las 02:17, detalle canónico del misterio.
    for grados, largo, grosor in ((90 - 68.5, radio * 0.49, 3.0),
                                  (90 - 102, radio * 0.67, 1.7)):
        ang = math.radians(grados)
        c.setLineWidth(grosor)
        c.line(x, y, x + largo * math.cos(ang), y + largo * math.sin(ang))
    c.setFillColor(DORADO)
    c.circle(x, y, 4, stroke=0, fill=1)
    c.restoreState()


def _dibujar_portada(c, doc, titulo_inicial, total_capitulos):
    c.saveState()
    c.setFillColor(PORTADA)
    c.rect(0, 0, ANCHO, ALTO, stroke=0, fill=1)

    c.setStrokeColor(DORADO)
    c.setLineWidth(0.8)
    c.rect(36, 36, ANCHO - 72, ALTO - 72, stroke=1, fill=0)
    c.setLineWidth(0.35)
    c.rect(45, 45, ANCHO - 90, ALTO - 90, stroke=1, fill=0)

    _dibujar_reloj(c, ANCHO / 2, 583, 100)

    c.setFillColor(PORTADA_CLARA)
    c.setFont("Helvetica", 9)
    c.drawCentredString(ANCHO / 2, 743, "RELATO INTERACTIVO")
    c.setFillColor(DORADO)
    c.line(195, 726, 400, 726)

    c.setFont("Times-Bold", 42)
    c.setFillColor(colors.HexColor("#F5EBD7"))
    c.drawCentredString(ANCHO / 2, 417, "ARCHIVO DE")
    c.drawCentredString(ANCHO / 2, 363, "SOMBRAS")

    c.setStrokeColor(DORADO)
    c.setLineWidth(1)
    c.line(214, 336, 381, 336)
    c.setFillColor(PORTADA_CLARA)
    c.setFont("Times-Italic", 15)
    c.drawCentredString(ANCHO / 2, 307, "Una historia de misterio")

    # El título del capítulo inicial personaliza cada libro.
    titulo = titulo_inicial.strip()
    if len(titulo) > 53:
        titulo = titulo[:50].rstrip() + "..."
    c.setFont("Times-Italic", 13)
    c.drawCentredString(ANCHO / 2, 216, titulo)
    c.setFont("Helvetica", 8)
    c.drawCentredString(
        ANCHO / 2, 102,
        f"UNA PARTIDA  -  {total_capitulos} CAPÍTULOS  -  UN DESTINO",
    )
    c.restoreState()


def _dibujar_pagina(c, doc):
    c.saveState()
    c.setFillColor(PAPEL)
    c.rect(0, 0, ANCHO, ALTO, stroke=0, fill=1)

    c.setStrokeColor(DORADO)
    c.setLineWidth(0.7)
    c.line(MARGEN_X, ALTO - 47, ANCHO - MARGEN_X, ALTO - 47)
    c.line(MARGEN_X, 45, ANCHO - MARGEN_X, 45)

    c.setFont("Helvetica", 7.5)
    c.setFillColor(BURDEOS)
    c.drawString(MARGEN_X, ALTO - 35, "ARCHIVO DE SOMBRAS")
    c.setFillColor(TINTA_CLARA)
    c.drawRightString(ANCHO - MARGEN_X, ALTO - 35, "RELATO INTERACTIVO")
    c.drawString(MARGEN_X, 29, "UNA HISTORIA ELEGIDA POR VOS")
    c.setFont("Times-Roman", 10)
    c.drawRightString(ANCHO - MARGEN_X, 29, f"{doc.page - 1:02d}")
    c.restoreState()


def _foto_del_capitulo(capitulo, estilos):
    """Incrusta la foto original; si falla la descarga, el relato sale igual."""
    url = url_de_imagen(capitulo)
    if not url:
        return []
    try:
        datos = descargar_para_pdf(url)
        ancho, alto = ImageReader(io.BytesIO(datos)).getSize()
        if ancho <= 0 or alto <= 0:
            return []
    except (ErrorImagen, OSError, ValueError, TypeError):
        return []

    max_ancho = ANCHO_TEXTO - 28
    max_alto = 215
    escala = min(max_ancho / ancho, max_alto / alto)
    foto = Image(io.BytesIO(datos), width=ancho * escala, height=alto * escala)
    foto.hAlign = "CENTER"

    metadatos = capitulo.get("imagen") or {}
    autor = escape(str(metadatos.get("autor", "Autor desconocido")))
    url_autor = escape(con_utm(metadatos.get("url_autor", URL_UNSPLASH)), quote=True)
    url_unsplash = escape(con_utm(URL_UNSPLASH), quote=True)
    credito = Paragraph(
        f'Fotografía: <link href="{url_autor}" color="#693D43">{autor}</link>'
        f' / <link href="{url_unsplash}" color="#693D43">Unsplash</link>',
        estilos["credito"],
    )

    foto_enmarcada = Table(
        [[foto], [credito]], colWidths=[ANCHO_TEXTO], hAlign="CENTER"
    )
    foto_enmarcada.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF9ED")),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.7, DORADO),
        ("TOPPADDING", (0, 0), (0, 0), 10),
        ("BOTTOMPADDING", (0, 0), (0, 0), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 1), (0, 1), 0),
        ("BOTTOMPADDING", (0, 1), (0, 1), 9),
    ]))
    return [foto_enmarcada, Spacer(1, 16)]


def _caja_decision(opcion, estilos):
    contenido = [
        Paragraph("LA DECISIÓN QUE TOMASTE", estilos["etiqueta"]),
        Paragraph(_texto_pdf(opcion), estilos["decision"]),
    ]
    caja = Table([[contenido]], colWidths=[ANCHO_TEXTO])
    caja.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CAJA),
        ("LINEBEFORE", (0, 0), (0, 0), 3, BURDEOS),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    return caja


def _agregar_capitulo(elementos, capitulo, decisiones, estilos):
    numero = capitulo["numero"]
    titulo = escape(str(capitulo["titulo"]))

    elementos.append(Paragraph(f"CAPÍTULO {numero:02d} / 05", estilos["capitulo"]))
    elementos.append(Paragraph(titulo, estilos["titulo"]))
    elementos.append(_separador())
    elementos.append(Spacer(1, 12))
    elementos.extend(_foto_del_capitulo(capitulo, estilos))

    # Separar párrafos conserva el ritmo de lectura. También respeta cursivas y negritas.
    parrafos = re.split(r"\n\s*\n", str(capitulo.get("texto", "")).strip())
    for parrafo in parrafos:
        if parrafo.strip():
            elementos.append(
                Paragraph(_texto_pdf(parrafo).replace("\n", "<br/>"), estilos["cuerpo"])
            )

    decision = decisiones.get(numero)
    if decision and capitulo.get("opciones"):
        indice = decision["opcion"] - 1
        opciones = capitulo["opciones"]
        if 0 <= indice < len(opciones):
            elementos.append(Spacer(1, 10))
            elementos.append(_caja_decision(opciones[indice], estilos))

    if numero == 5:
        elementos.append(Spacer(1, 18))
        elementos.append(Paragraph("FIN DEL EXPEDIENTE", estilos["epilogo"]))


def _separador():
    linea = Table([[""]], colWidths=[ANCHO_TEXTO], rowHeights=[1])
    linea.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (0, 0), 0.8, DORADO),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return linea


def _agregar_registro(elementos, estado, estilos):
    elementos.append(Paragraph("REGISTRO FINAL", estilos["capitulo"]))
    elementos.append(Paragraph("Huellas de la investigación", estilos["titulo_anexo"]))
    elementos.append(_separador())
    elementos.append(Spacer(1, 17))

    elementos.append(Paragraph("Objetos que conservaste", estilos["subtitulo"]))
    inventario = estado.get("inventario", [])
    if inventario:
        for objeto in inventario:
            elementos.append(Paragraph("- " + escape(str(objeto)), estilos["lista"]))
    else:
        elementos.append(Paragraph("No conservaste objetos.", estilos["cuerpo"]))

    elementos.append(Paragraph("Pistas que descubriste", estilos["subtitulo"]))
    pistas = estado.get("pistas_descubiertas", [])
    if pistas:
        for pista in pistas:
            elementos.append(Paragraph("- " + escape(str(pista)), estilos["lista"]))
    else:
        elementos.append(Paragraph("No quedaron pistas registradas.", estilos["cuerpo"]))

    elementos.append(Spacer(1, 22))
    elementos.append(Paragraph(
        "Cada decisión cambió el camino. Esta es la versión de la historia que viviste.",
        estilos["decision"],
    ))


def generar_pdf(id_partida):
    estado = consultar_estado(id_partida)
    if not estado["finalizada"]:
        raise ValueError(
            "La historia todavía no terminó: el PDF se genera al llegar al desenlace"
        )

    carpeta = Path("historias_generadas")
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{id_partida}.pdf"

    capitulos = estado["capitulos"]
    estilos = _estilos()
    primer_titulo = capitulos[0]["titulo"] if capitulos else "Una noche de misterio"

    documento = BaseDocTemplate(
        str(ruta), pagesize=A4,
        leftMargin=MARGEN_X, rightMargin=MARGEN_X,
        topMargin=MARGEN_SUP, bottomMargin=MARGEN_INF,
        title="Archivo de sombras - Mi historia de misterio",
        author="Agente de historias interactivas",
    )
    marco = Frame(
        MARGEN_X, MARGEN_INF, ANCHO_TEXTO,
        ALTO - MARGEN_SUP - MARGEN_INF,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        showBoundary=0,
    )
    documento.addPageTemplates([
        PageTemplate(
            id="Portada", frames=[marco],
            onPage=lambda c, d: _dibujar_portada(c, d, primer_titulo, len(capitulos)),
        ),
        PageTemplate(id="Capitulos", frames=[marco], onPage=_dibujar_pagina),
    ])

    elementos = [
        Spacer(1, 1),
        NextPageTemplate("Capitulos"),
        PageBreak(),
    ]

    decisiones = {d["capitulo"]: d for d in estado.get("decisiones", [])}
    for i, capitulo in enumerate(capitulos):
        if i:
            elementos.append(PageBreak())
        _agregar_capitulo(elementos, capitulo, decisiones, estilos)

    elementos.append(PageBreak())
    _agregar_registro(elementos, estado, estilos)

    documento.build(elementos)
    return str(ruta)

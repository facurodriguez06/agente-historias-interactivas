"""Pruebas de comandos_chat. No usan LLM, ni red, ni Streamlit."""

import estado_partida as ep

import comandos_chat as cc


# --- parsear_comando --------------------------------------------------------


def test_reconoce_los_cuatro_comandos():
    assert cc.parsear_comando("/nueva") == "nueva"
    assert cc.parsear_comando("/retomar") == "retomar"
    assert cc.parsear_comando("/partidas") == "partidas"
    assert cc.parsear_comando("/ayuda") == "ayuda"


def test_comandos_insensibles_a_mayusculas():
    assert cc.parsear_comando("/NUEVA") == "nueva"
    assert cc.parsear_comando("/Retomar") == "retomar"
    assert cc.parsear_comando("/PARTIDAS") == "partidas"
    assert cc.parsear_comando("/Ayuda") == "ayuda"


def test_comandos_toleran_espacios():
    assert cc.parsear_comando("  /nueva  ") == "nueva"
    assert cc.parsear_comando("\t/retomar\n") == "retomar"


def test_sin_barra_no_es_comando():
    # "nueva" sin la barra va al agente como texto común.
    assert cc.parsear_comando("nueva") is None
    assert cc.parsear_comando("ayuda") is None


def test_texto_comun_no_es_comando():
    assert cc.parsear_comando("¿Qué pasó en la partida anterior?") is None
    assert cc.parsear_comando("") is None
    assert cc.parsear_comando("   ") is None


def test_comando_desconocido():
    assert cc.parsear_comando("/inventar") is None
    assert cc.parsear_comando("/nueva partida ya") is None


def test_retomar_y_partidas_son_tokens_distintos():
    assert cc.parsear_comando("/retomar") != cc.parsear_comando("/partidas")


# --- formatear_listado ------------------------------------------------------


def resumen(
    id_partida="a1b2c3d4" + "0" * 24,
    capitulos_escritos=2,
    titulo_ultimo_capitulo="El vestíbulo",
    resumen_ultimo_capitulo="Vos despertaste en un vestíbulo sin salida.",
):
    """Resumen con la forma exacta de estado_partida._resumen_de_partida."""
    return {
        "id_partida": id_partida,
        "capitulos_escritos": capitulos_escritos,
        "capitulo_actual": capitulos_escritos,
        "finalizada": False,
        "titulo_ultimo_capitulo": titulo_ultimo_capitulo,
        "resumen_ultimo_capitulo": resumen_ultimo_capitulo,
        "decision_pendiente": True,
    }


def test_listado_vacio():
    texto = cc.formatear_listado([])
    assert "no hay partidas abiertas" in texto.lower()


def test_listado_muestra_id_recortado_capitulos_titulo_y_resumen():
    texto = cc.formatear_listado([resumen()])
    assert "a1b2c3d4" in texto
    assert f"2 de {ep.TOTAL_CAPITULOS}" in texto
    assert "El vestíbulo" in texto
    assert "despertaste en un vestíbulo" in texto


def test_listado_numerado_con_encabezado_en_negrita():
    texto = cc.formatear_listado(
        [resumen(), resumen(id_partida="f" * 32, capitulos_escritos=1)]
    )
    assert "**" in texto
    assert "\n1." in texto
    assert "\n2." in texto


def test_listado_invita_a_elegir_en_voseo():
    texto = cc.formatear_listado([resumen()])
    assert "número" in texto.lower()


def test_listado_sin_capitulos_no_muestra_titulo():
    texto = cc.formatear_listado([resumen(capitulos_escritos=0, titulo_ultimo_capitulo="")])
    # "0 de 5 capítulos" sigue apareciendo; no hay título ni resumen que rompan.
    assert f"0 de {ep.TOTAL_CAPITULOS}" in texto


def test_listado_con_partida_de_cero_capitulos_no_rompe():
    """S8: partida abierta de 0 capítulos (título y resumen vacíos) no rompe el listado."""
    texto = cc.formatear_listado(
        [resumen(capitulos_escritos=0, titulo_ultimo_capitulo="", resumen_ultimo_capitulo="")]
    )
    # Sin título ni resumen que mostrar, pero con id recortado y capítulos en cero.
    assert "a1b2c3d4" in texto
    assert f"0 de {ep.TOTAL_CAPITULOS} capítulos" in texto
    assert "«" not in texto


def test_listado_con_resumen_de_primeras_lineas_en_blanco():
    """S8: si las primeras líneas del resumen están en blanco, se toma la primera con contenido."""
    texto = cc.formatear_listado(
        [
            resumen(
                resumen_ultimo_capitulo=(
                    "\n \nVos despertaste en un vestíbulo.\n\nSeguiste caminando."
                )
            )
        ]
    )
    assert "despertaste en un vestíbulo" in texto


def test_listado_con_resumen_totalmente_en_blanco():
    """S8: un resumen hecho solo de líneas en blanco se omite sin romper."""
    texto = cc.formatear_listado([resumen(resumen_ultimo_capitulo="\n  \n")])
    assert "a1b2c3d4" in texto
    assert f"2 de {ep.TOTAL_CAPITULOS}" in texto


def test_listado_con_resumenes_reales_de_estado_partida():
    """El formateo consume el dict que produce _resumen_de_partida sin tocar nada más."""
    estado = {
        "id_partida": "b" * 32,
        "capitulo_actual": 1,
        "capitulos": [
            {
                "numero": 1,
                "titulo": "La llegada",
                "texto": "Llegaste de noche.",
                "opciones": ["A", "B", "C"],
                "imagen": None,
                "contexto_narrativo": {},
            }
        ],
        "decisiones": [],
        "inventario": [],
        "pistas_descubiertas": [],
        "contexto_narrativo": {"resumen_ultimo_capitulo": "Llegaste de noche."},
        "finalizada": False,
    }
    texto = cc.formatear_listado([ep._resumen_de_partida(estado)])
    assert "b" * 8 in texto
    assert f"1 de {ep.TOTAL_CAPITULOS}" in texto
    assert "La llegada" in texto
    assert "Llegaste de noche" in texto


# --- eleccion_numerica ------------------------------------------------------


def test_numero_puro():
    assert cc.eleccion_numerica("1", 3) == 1
    assert cc.eleccion_numerica(" 2 ", 3) == 2


def test_con_la_articulo():
    assert cc.eleccion_numerica("la 2", 3) == 2
    assert cc.eleccion_numerica("LA 1", 3) == 1


def test_con_opcion():
    assert cc.eleccion_numerica("opcion 3", 3) == 3
    assert cc.eleccion_numerica("Opción 3", 3) == 3
    assert cc.eleccion_numerica("OPCIÓN 3", 3) == 3


def test_con_partida():
    assert cc.eleccion_numerica("partida 2", 3) == 2
    assert cc.eleccion_numerica("la partida 3", 3) == 3


def test_fuera_de_rango():
    assert cc.eleccion_numerica("4", 3) is None
    assert cc.eleccion_numerica("0", 3) is None
    assert cc.eleccion_numerica("-1", 3) is None
    assert cc.eleccion_numerica("12", 3) is None


def test_texto_no_numerico():
    assert cc.eleccion_numerica("la del vestíbulo", 3) is None
    assert cc.eleccion_numerica("", 3) is None
    assert cc.eleccion_numerica("1.5", 3) is None


def test_respuesta_ambigua():
    assert cc.eleccion_numerica("1 y 2", 3) is None
    assert cc.eleccion_numerica("2 o 3", 3) is None


def test_con_una_sola_partida_solo_acepta_uno():
    assert cc.eleccion_numerica("1", 1) == 1
    assert cc.eleccion_numerica("2", 1) is None


# --- texto_ayuda y saludo_inicial -------------------------------------------


def test_ayuda_menciona_los_cuatro_comandos():
    texto = cc.texto_ayuda()
    for comando in ("/nueva", "/retomar", "/partidas", "/ayuda"):
        assert comando in texto


def test_ayuda_explica_que_puede_hacer_el_chat():
    texto = cc.texto_ayuda().lower()
    assert "partidas anteriores" in texto
    assert "nueva" in texto
    assert "retomar" in texto


def test_saludo_inicial_menciona_la_ayuda():
    texto = cc.saludo_inicial()
    assert "/ayuda" in texto

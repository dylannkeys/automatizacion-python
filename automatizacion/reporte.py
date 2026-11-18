"""Genera un informe en Excel a partir de la lista de candidatos ya limpia."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .candidatos import COLUMNAS, Resultado

log = logging.getLogger(__name__)

AZUL = "1F3A5F"
CABECERA = PatternFill("solid", fgColor=AZUL)
TEXTO_CABECERA = Font(bold=True, color="FFFFFF")
TITULO = Font(bold=True, size=16, color=AZUL)
SUBTITULO = Font(bold=True, size=12, color=AZUL)

MESES = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]


def _cabecera(hoja: Worksheet, fila: int, columnas: list[str], col_inicio: int = 1) -> None:
    for i, texto in enumerate(columnas):
        celda = hoja.cell(row=fila, column=col_inicio + i, value=texto)
        celda.fill = CABECERA
        celda.font = TEXTO_CABECERA
        celda.alignment = Alignment(horizontal="center")


def _ajustar_anchos(hoja: Worksheet, minimo: int = 10, maximo: int = 50) -> None:
    for columna in hoja.columns:
        largo = max((len(str(c.value)) for c in columna if c.value is not None), default=0)
        hoja.column_dimensions[get_column_letter(columna[0].column)].width = max(minimo, min(largo + 2, maximo))


def _tabla_conteo(hoja: Worksheet, fila: int, titulo: str, conteo: Counter, total: int) -> int:
    """Escribe una tabla 'valor | candidatos | %' y devuelve la siguiente fila libre."""
    hoja.cell(row=fila, column=1, value=titulo).font = SUBTITULO
    _cabecera(hoja, fila + 1, [titulo.split(" por ")[-1].capitalize(), "Candidatos", "%"])
    actual = fila + 2
    for valor, cantidad in conteo.most_common():
        hoja.cell(row=actual, column=1, value=valor)
        hoja.cell(row=actual, column=2, value=cantidad)
        porcentaje = hoja.cell(row=actual, column=3, value=cantidad / total if total else 0)
        porcentaje.number_format = "0.0%"
        actual += 1
    return actual + 1


def generar_reporte(resultado: Resultado, destino: Path) -> Path:
    """Crea un Excel con tres hojas: Resumen (con gráfico), Candidatos y Errores."""
    candidatos = resultado.validos
    total = len(candidatos)
    libro = Workbook()

    # --- Hoja Resumen ---
    resumen = libro.active
    resumen.title = "Resumen"
    resumen["A1"] = "Reporte de postulaciones"
    resumen["A1"].font = TITULO
    resumen["A2"] = f"Generado el {datetime.now():%d/%m/%Y %H:%M}"
    resumen["A2"].font = Font(italic=True, color="666666")

    indicadores = [
        ("Candidatos válidos", total),
        ("Filas con errores", len(resultado.errores)),
        ("Duplicados eliminados", resultado.duplicados),
    ]
    for i, (nombre, valor) in enumerate(indicadores, start=4):
        resumen.cell(row=i, column=1, value=nombre).font = Font(bold=True)
        resumen.cell(row=i, column=2, value=valor)

    fila = 8
    inicio_carreras = fila
    por_carrera = Counter(c.carrera for c in candidatos)
    fila = _tabla_conteo(resumen, fila, "Candidatos por carrera", por_carrera, total)
    fila = _tabla_conteo(resumen, fila, "Candidatos por ciudad", Counter(c.ciudad for c in candidatos), total)

    por_mes = Counter((c.fecha_postulacion.year, c.fecha_postulacion.month) for c in candidatos)
    resumen.cell(row=fila, column=1, value="Candidatos por mes").font = SUBTITULO
    _cabecera(resumen, fila + 1, ["Mes", "Candidatos"])
    for i, ((anio, mes), cantidad) in enumerate(sorted(por_mes.items()), start=fila + 2):
        resumen.cell(row=i, column=1, value=f"{MESES[mes - 1].capitalize()} {anio}")
        resumen.cell(row=i, column=2, value=cantidad)

    if por_carrera:
        grafico = BarChart()
        grafico.title = "Candidatos por carrera"
        grafico.legend = None
        grafico.height, grafico.width = 7.5, 14
        datos = Reference(
            resumen, min_col=2, min_row=inicio_carreras + 1, max_row=inicio_carreras + 1 + len(por_carrera)
        )
        etiquetas = Reference(
            resumen, min_col=1, min_row=inicio_carreras + 2, max_row=inicio_carreras + 1 + len(por_carrera)
        )
        grafico.add_data(datos, titles_from_data=True)
        grafico.set_categories(etiquetas)
        resumen.add_chart(grafico, "E4")

    _ajustar_anchos(resumen, maximo=28)

    # --- Hoja Candidatos ---
    hoja = libro.create_sheet("Candidatos")
    _cabecera(hoja, 1, [c.replace("_", " ").capitalize() for c in COLUMNAS])
    for c in candidatos:
        hoja.append([c.nombre, c.email, c.telefono, c.ciudad, c.carrera, c.fecha_postulacion])
        hoja.cell(row=hoja.max_row, column=6).number_format = "DD/MM/YYYY"
    hoja.freeze_panes = "A2"
    hoja.auto_filter.ref = hoja.dimensions
    _ajustar_anchos(hoja)

    # --- Hoja Errores ---
    errores = libro.create_sheet("Errores")
    _cabecera(errores, 1, ["Fila", "Motivos", *[c.replace("_", " ").capitalize() for c in COLUMNAS]])
    for e in resultado.errores:
        errores.append([e.fila, "; ".join(e.motivos), *[e.datos[c] for c in COLUMNAS]])
    errores.freeze_panes = "A2"
    _ajustar_anchos(errores)

    destino.parent.mkdir(parents=True, exist_ok=True)
    libro.save(destino)
    log.info("Reporte guardado en %s", destino)
    return destino

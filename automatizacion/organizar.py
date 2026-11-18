"""Ordena los archivos de una carpeta (por ejemplo, Descargas) en subcarpetas según su tipo.

Primero se calcula un plan y se muestra; solo se mueven archivos si se pide con --aplicar.
"""

from __future__ import annotations

import logging
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

CATEGORIAS = {
    "Documentos": {".pdf", ".doc", ".docx", ".txt", ".odt", ".rtf", ".md"},
    "Hojas de cálculo": {".xls", ".xlsx", ".csv", ".ods"},
    "Presentaciones": {".ppt", ".pptx", ".odp", ".key"},
    "Imágenes": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".heic", ".bmp"},
    "Audio y video": {".mp3", ".wav", ".m4a", ".mp4", ".mov", ".avi", ".mkv"},
    "Comprimidos": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Instaladores": {".exe", ".msi", ".dmg", ".pkg", ".deb"},
    "Código": {".py", ".js", ".ts", ".html", ".css", ".json", ".sql", ".go", ".java"},
}
OTROS = "Otros"


@dataclass(frozen=True)
class Movimiento:
    origen: Path
    destino: Path


def categoria(archivo: Path) -> str:
    extension = archivo.suffix.lower()
    for nombre, extensiones in CATEGORIAS.items():
        if extension in extensiones:
            return nombre
    return OTROS


def _ruta_libre(destino: Path, ocupadas: set[Path]) -> Path:
    """Si ya existe un archivo con ese nombre, prueba 'nombre (1).ext', 'nombre (2).ext'..."""
    candidato, n = destino, 1
    while candidato.exists() or candidato in ocupadas:
        candidato = destino.with_name(f"{destino.stem} ({n}){destino.suffix}")
        n += 1
    return candidato


def planificar(carpeta: Path) -> list[Movimiento]:
    """Calcula qué se movería, sin tocar nada. Ignora subcarpetas y archivos ocultos."""
    if not carpeta.is_dir():
        raise NotADirectoryError(f"No existe la carpeta: {carpeta}")
    plan, ocupadas = [], set()
    for archivo in sorted(carpeta.iterdir()):
        if not archivo.is_file() or archivo.name.startswith("."):
            continue
        destino = _ruta_libre(carpeta / categoria(archivo) / archivo.name, ocupadas)
        ocupadas.add(destino)
        plan.append(Movimiento(archivo, destino))
    return plan


def resumen(plan: list[Movimiento]) -> Counter:
    return Counter(m.destino.parent.name for m in plan)


def aplicar(plan: list[Movimiento]) -> int:
    for movimiento in plan:
        movimiento.destino.parent.mkdir(exist_ok=True)
        shutil.move(movimiento.origen, movimiento.destino)
        log.debug("%s -> %s", movimiento.origen.name, movimiento.destino)
    log.info("%d archivos movidos", len(plan))
    return len(plan)

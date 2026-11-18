"""Limpieza y validación de una lista de candidatos exportada desde un formulario.

Normaliza nombres, correos, teléfonos de Ecuador, ciudades, carreras y fechas; separa las filas con
errores y elimina duplicados por correo (se queda con la postulación más reciente).
"""

from __future__ import annotations

import csv
import logging
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

log = logging.getLogger(__name__)

COLUMNAS = ["nombre", "email", "telefono", "ciudad", "carrera", "fecha_postulacion"]

# Valores conocidos: sirven para unificar variantes como "enfermeria", "ENFERMERÍA" o " Enfermería ".
CARRERAS = ["Enfermería", "Medicina", "Fisioterapia", "Laboratorio Clínico", "Nutrición"]
CIUDADES = ["Quito", "Guayaquil", "Cuenca", "Ambato", "Loja", "Manta", "Ibarra", "Riobamba"]

FORMATOS_FECHA = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$")
PARTICULAS = {"de", "del", "la", "las", "los", "y"}


@dataclass
class Candidato:
    nombre: str
    email: str
    telefono: str
    ciudad: str
    carrera: str
    fecha_postulacion: date


@dataclass
class FilaConError:
    fila: int  # número de fila en el CSV original (la cabecera es la fila 1)
    motivos: list[str]
    datos: dict[str, str]


@dataclass
class Resultado:
    validos: list[Candidato] = field(default_factory=list)
    errores: list[FilaConError] = field(default_factory=list)
    duplicados: int = 0


# ---------- Normalizadores: cada uno devuelve el valor limpio o None si no es válido ----------


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _espacios(texto: str) -> str:
    return " ".join(texto.split())


def normalizar_nombre(valor: str) -> str | None:
    """'  maria   JOSÉ  de la cruz ' -> 'Maria José de la Cruz'."""
    palabras = _espacios(valor).lower().split(" ")
    if not palabras[0]:
        return None
    resultado = [p if (i > 0 and p in PARTICULAS) else p.capitalize() for i, p in enumerate(palabras)]
    return " ".join(resultado)


def normalizar_email(valor: str) -> str | None:
    email = valor.strip().lower()
    return email if EMAIL_RE.match(email) else None


def normalizar_telefono(valor: str) -> str | None:
    """Acepta móviles y fijos de Ecuador en cualquier formato y los devuelve en formato internacional.

    '0991234567', '+593 99 123 4567' o '593991234567' -> '+593 99 123 4567'
    '(02) 2456-789' -> '+593 2 245 6789'
    """
    digitos = re.sub(r"\D", "", valor)
    if digitos.startswith("593"):
        numero = digitos[3:]
    elif digitos.startswith("0"):
        numero = digitos[1:]
    else:
        numero = digitos

    if len(numero) == 9 and numero.startswith("9"):  # móvil
        return f"+593 {numero[:2]} {numero[2:5]} {numero[5:]}"
    if len(numero) == 8 and numero[0] in "234567":  # fijo: un dígito de provincia + 7
        return f"+593 {numero[0]} {numero[1:4]} {numero[4:]}"
    return None


def normalizar_fecha(valor: str) -> date | None:
    texto = valor.strip()
    for formato in FORMATOS_FECHA:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def canonico(valor: str, conocidos: list[str]) -> str | None:
    """Devuelve la forma oficial de un valor conocido, sin importar mayúsculas, tildes ni espacios.
    Si no está en la lista, lo devuelve con formato de título."""
    limpio = _espacios(valor)
    if not limpio:
        return None
    clave = _sin_tildes(limpio).lower()
    for oficial in conocidos:
        if _sin_tildes(oficial).lower() == clave:
            return oficial
    return limpio.title()


# ---------- Proceso completo ----------


def limpiar(filas: Iterable[dict[str, str]]) -> Resultado:
    """Valida y normaliza cada fila. Las filas con errores no se corrigen a mano: se reportan."""
    resultado = Resultado()
    por_email: dict[str, Candidato] = {}

    for numero, fila in enumerate(filas, start=2):
        crudo = {col: (fila.get(col) or "") for col in COLUMNAS}
        nombre = normalizar_nombre(crudo["nombre"])
        email = normalizar_email(crudo["email"])
        telefono = normalizar_telefono(crudo["telefono"])
        ciudad = canonico(crudo["ciudad"], CIUDADES)
        carrera = canonico(crudo["carrera"], CARRERAS)
        fecha = normalizar_fecha(crudo["fecha_postulacion"])

        motivos = [
            mensaje
            for valor, mensaje in [
                (nombre, "Falta el nombre"),
                (email, "Correo no válido"),
                (telefono, "Teléfono no válido"),
                (ciudad, "Falta la ciudad"),
                (carrera, "Falta la carrera"),
                (fecha, "Fecha no válida"),
            ]
            if valor is None
        ]
        if motivos:
            resultado.errores.append(FilaConError(fila=numero, motivos=motivos, datos=crudo))
            continue

        candidato = Candidato(nombre, email, telefono, ciudad, carrera, fecha)  # type: ignore[arg-type]
        anterior = por_email.get(email)  # type: ignore[arg-type]
        if anterior is not None:
            resultado.duplicados += 1
            if candidato.fecha_postulacion < anterior.fecha_postulacion:
                continue  # nos quedamos con la postulación más reciente
        por_email[email] = candidato  # type: ignore[index]

    resultado.validos = sorted(por_email.values(), key=lambda c: (c.fecha_postulacion, c.nombre))
    log.info(
        "Limpieza: %d válidos, %d con errores, %d duplicados eliminados",
        len(resultado.validos),
        len(resultado.errores),
        resultado.duplicados,
    )
    return resultado


# ---------- Lectura y escritura de CSV ----------
# Se usa utf-8-sig para que Excel abra bien las tildes y la ñ.


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        faltan = set(COLUMNAS) - set(lector.fieldnames or [])
        if faltan:
            raise ValueError(f"Al CSV le faltan columnas: {', '.join(sorted(faltan))}")
        return list(lector)


def guardar_validos(candidatos: list[Candidato], ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
        escritor.writeheader()
        for c in candidatos:
            fila = asdict(c)
            fila["fecha_postulacion"] = c.fecha_postulacion.isoformat()
            escritor.writerow(fila)


def guardar_errores(errores: list[FilaConError], ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=["fila", "motivos", *COLUMNAS])
        escritor.writeheader()
        for e in errores:
            escritor.writerow({"fila": e.fila, "motivos": "; ".join(e.motivos), **e.datos})


def leer_validos(ruta: Path) -> list[Candidato]:
    """Lee un CSV ya limpio (el que genera guardar_validos)."""
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        return [
            Candidato(**{**fila, "fecha_postulacion": date.fromisoformat(fila["fecha_postulacion"])})
            for fila in csv.DictReader(archivo)
        ]

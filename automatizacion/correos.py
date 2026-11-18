"""Correos personalizados a partir de una plantilla (combinación de correspondencia).

Por seguridad, el modo por defecto NO envía nada: guarda cada correo como archivo .eml para revisarlo
antes. El envío real por SMTP solo ocurre si se pide explícitamente.
"""

from __future__ import annotations

import logging
import os
import re
import smtplib
import time
from dataclasses import asdict
from email.message import EmailMessage
from pathlib import Path
from string import Template

from .candidatos import Candidato

log = logging.getLogger(__name__)

CAMPOS = {"nombre", "email", "telefono", "ciudad", "carrera", "fecha"}


class PlantillaInvalida(ValueError):
    pass


def leer_plantilla(ruta: Path) -> tuple[Template, Template]:
    """La primera línea es 'Asunto: ...', luego una línea en blanco y el cuerpo."""
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    if not lineas or not lineas[0].lower().startswith("asunto:"):
        raise PlantillaInvalida("La plantilla debe empezar con una línea 'Asunto: ...'.")
    asunto = Template(lineas[0].split(":", 1)[1].strip())
    cuerpo = Template("\n".join(lineas[1:]).strip() + "\n")

    # Detecta errores de escritura en los campos ($nombr, $carerra...) antes de generar nada.
    desconocidos = (set(asunto.get_identifiers()) | set(cuerpo.get_identifiers())) - CAMPOS
    if desconocidos:
        raise PlantillaInvalida(
            f"Campos desconocidos en la plantilla: {', '.join(sorted(desconocidos))}. "
            f"Disponibles: {', '.join(sorted(CAMPOS))}."
        )
    return asunto, cuerpo


def preparar_correos(candidatos: list[Candidato], plantilla: Path, remitente: str) -> list[EmailMessage]:
    asunto, cuerpo = leer_plantilla(plantilla)
    mensajes = []
    for c in candidatos:
        datos = asdict(c)
        datos["nombre"] = c.nombre.split(" ")[0]  # saludo con el primer nombre
        datos["fecha"] = c.fecha_postulacion.strftime("%d/%m/%Y")
        mensaje = EmailMessage()
        mensaje["From"] = remitente
        mensaje["To"] = c.email
        mensaje["Subject"] = asunto.substitute(datos)
        mensaje.set_content(cuerpo.substitute(datos))
        mensajes.append(mensaje)
    return mensajes


def _nombre_archivo(indice: int, email: str) -> str:
    return f"{indice:03d}_{re.sub(r'[^a-z0-9]+', '_', email.lower()).strip('_')}.eml"


def guardar_borradores(mensajes: list[EmailMessage], carpeta: Path) -> list[Path]:
    """Guarda cada correo como .eml (se abre con Outlook, Thunderbird o el navegador)."""
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = []
    for i, mensaje in enumerate(mensajes, start=1):
        ruta = carpeta / _nombre_archivo(i, str(mensaje["To"]))
        ruta.write_bytes(bytes(mensaje))
        rutas.append(ruta)
    log.info("%d borradores guardados en %s (no se envió nada)", len(rutas), carpeta)
    return rutas


def enviar(mensajes: list[EmailMessage], pausa: float = 1.0) -> int:
    """Envía por SMTP con las credenciales de las variables de entorno SMTP_HOST, SMTP_PORT,
    SMTP_USER y SMTP_PASSWORD. Hace una pausa entre correos para no saturar el servidor."""
    host = os.environ.get("SMTP_HOST")
    usuario = os.environ.get("SMTP_USER")
    clave = os.environ.get("SMTP_PASSWORD")
    if not (host and usuario and clave):
        raise RuntimeError("Faltan SMTP_HOST, SMTP_USER o SMTP_PASSWORD en las variables de entorno.")
    puerto = int(os.environ.get("SMTP_PORT", "587"))

    enviados = 0
    with smtplib.SMTP(host, puerto, timeout=30) as servidor:
        servidor.starttls()
        servidor.login(usuario, clave)
        for mensaje in mensajes:
            try:
                servidor.send_message(mensaje)
                enviados += 1
                log.info("Enviado a %s", mensaje["To"])
            except smtplib.SMTPException as error:
                # Un correo que falla no detiene el resto: se registra y se sigue.
                log.error("No se pudo enviar a %s: %s", mensaje["To"], error)
            time.sleep(pausa)
    log.info("%d de %d correos enviados", enviados, len(mensajes))
    return enviados

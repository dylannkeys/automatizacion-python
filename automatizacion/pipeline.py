"""Encadena el proceso completo: limpiar candidatos -> reporte en Excel -> correos de confirmación."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from . import candidatos as cand
from . import correos, reporte

log = logging.getLogger(__name__)


@dataclass
class ResumenPipeline:
    validos: int
    errores: int
    duplicados: int
    reporte: Path
    correos: int
    enviados: bool
    segundos: float


def ejecutar(entrada: Path, salida: Path, plantilla: Path, remitente: str, enviar: bool = False) -> ResumenPipeline:
    inicio = time.perf_counter()

    log.info("Paso 1/3: limpiando %s", entrada)
    resultado = cand.limpiar(cand.leer_csv(entrada))
    cand.guardar_validos(resultado.validos, salida / "candidatos_limpios.csv")
    cand.guardar_errores(resultado.errores, salida / "errores.csv")

    log.info("Paso 2/3: generando el reporte en Excel")
    ruta_reporte = reporte.generar_reporte(resultado, salida / "reporte_postulaciones.xlsx")

    log.info("Paso 3/3: preparando correos de confirmación")
    mensajes = correos.preparar_correos(resultado.validos, plantilla, remitente)
    if enviar:
        correos.enviar(mensajes)
    else:
        correos.guardar_borradores(mensajes, salida / "correos")

    segundos = time.perf_counter() - inicio
    log.info("Proceso completo en %.2f s", segundos)
    return ResumenPipeline(
        validos=len(resultado.validos),
        errores=len(resultado.errores),
        duplicados=resultado.duplicados,
        reporte=ruta_reporte,
        correos=len(mensajes),
        enviados=enviar,
        segundos=segundos,
    )

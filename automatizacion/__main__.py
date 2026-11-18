"""Línea de comandos: python -m automatizacion <comando> [opciones]. Usa --help para ver la ayuda."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import candidatos as cand
from . import correos, organizar, pipeline, reporte

REMITENTE = "seleccion@example.com"


def _limpiar(args: argparse.Namespace) -> None:
    resultado = cand.limpiar(cand.leer_csv(args.entrada))
    cand.guardar_validos(resultado.validos, args.salida / "candidatos_limpios.csv")
    cand.guardar_errores(resultado.errores, args.salida / "errores.csv")
    print(
        f"Válidos: {len(resultado.validos)} | Con errores: {len(resultado.errores)} | "
        f"Duplicados eliminados: {resultado.duplicados}"
    )
    print(f"Archivos en: {args.salida}")


def _reporte(args: argparse.Namespace) -> None:
    resultado = cand.limpiar(cand.leer_csv(args.entrada))
    ruta = reporte.generar_reporte(resultado, args.salida / "reporte_postulaciones.xlsx")
    print(f"Reporte: {ruta}")


def _correos(args: argparse.Namespace) -> None:
    validos = cand.leer_validos(args.entrada)
    mensajes = correos.preparar_correos(validos, args.plantilla, args.remitente)
    if args.enviar:
        correos.enviar(mensajes)
    else:
        rutas = correos.guardar_borradores(mensajes, args.salida / "correos")
        print(f"{len(rutas)} borradores en {args.salida / 'correos'} (no se envió nada; usa --enviar para enviar)")


def _organizar(args: argparse.Namespace) -> None:
    plan = organizar.planificar(args.carpeta)
    if not plan:
        print("No hay archivos que ordenar.")
        return
    for nombre, cantidad in sorted(organizar.resumen(plan).items()):
        print(f"  {nombre}: {cantidad} archivo(s)")
    if args.aplicar:
        organizar.aplicar(plan)
        print(f"Listo: {len(plan)} archivos movidos.")
    else:
        print(f"Simulación: se moverían {len(plan)} archivos. Repite con --aplicar para moverlos.")


def _pipeline(args: argparse.Namespace) -> None:
    r = pipeline.ejecutar(args.entrada, args.salida, args.plantilla, args.remitente, enviar=args.enviar)
    estado = "enviados" if r.enviados else "guardados como borradores"
    print(f"Válidos: {r.validos} | Con errores: {r.errores} | Duplicados: {r.duplicados}")
    print(f"Reporte: {r.reporte}")
    print(f"Correos: {r.correos} {estado}")
    print(f"Tiempo: {r.segundos:.2f} s")


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m automatizacion", description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true", help="muestra el detalle de cada paso")
    sub = parser.add_subparsers(dest="comando", required=True)

    def con_entrada_salida(p: argparse.ArgumentParser, entrada: str) -> None:
        p.add_argument("--entrada", type=Path, default=Path(entrada), help=f"CSV de entrada (por defecto: {entrada})")
        p.add_argument(
            "--salida", type=Path, default=Path("salida"), help="carpeta de resultados (por defecto: salida)"
        )

    def con_correo(p: argparse.ArgumentParser) -> None:
        p.add_argument("--plantilla", type=Path, default=Path("plantillas/confirmacion.txt"))
        p.add_argument("--remitente", default=REMITENTE)
        p.add_argument("--enviar", action="store_true", help="envía de verdad por SMTP (ver README)")

    p = sub.add_parser("limpiar", help="valida y normaliza el CSV de candidatos")
    con_entrada_salida(p, "datos/candidatos.csv")
    p.set_defaults(func=_limpiar)

    p = sub.add_parser("reporte", help="genera el reporte en Excel")
    con_entrada_salida(p, "datos/candidatos.csv")
    p.set_defaults(func=_reporte)

    p = sub.add_parser("correos", help="prepara correos personalizados desde el CSV limpio")
    con_entrada_salida(p, "salida/candidatos_limpios.csv")
    con_correo(p)
    p.set_defaults(func=_correos)

    p = sub.add_parser("organizar", help="ordena una carpeta por tipo de archivo")
    p.add_argument("carpeta", type=Path, help="carpeta a ordenar, por ejemplo ~/Downloads")
    p.add_argument("--aplicar", action="store_true", help="mueve los archivos (sin esto solo simula)")
    p.set_defaults(func=_organizar)

    p = sub.add_parser("pipeline", help="ejecuta limpiar + reporte + correos en un solo paso")
    con_entrada_salida(p, "datos/candidatos.csv")
    con_correo(p)
    p.set_defaults(func=_pipeline)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        args.func(args)
    except (FileNotFoundError, NotADirectoryError, ValueError, RuntimeError) as error:
        logging.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

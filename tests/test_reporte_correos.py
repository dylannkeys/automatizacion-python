from email import message_from_bytes
from email.policy import default
from pathlib import Path

import pytest
from openpyxl import load_workbook

from automatizacion import candidatos as cand
from automatizacion import correos, pipeline, reporte

DATOS = Path("datos/candidatos.csv")
PLANTILLA = Path("plantillas/confirmacion.txt")


@pytest.fixture
def resultado():
    return cand.limpiar(cand.leer_csv(DATOS))


def test_reporte_excel(resultado, tmp_path):
    ruta = reporte.generar_reporte(resultado, tmp_path / "reporte.xlsx")
    libro = load_workbook(ruta)
    assert libro.sheetnames == ["Resumen", "Candidatos", "Errores"]

    resumen = libro["Resumen"]
    assert resumen["B4"].value == 17  # candidatos válidos
    assert resumen["B5"].value == 6  # filas con errores
    assert resumen["B6"].value == 2  # duplicados
    assert len(resumen._charts) == 1

    hoja = libro["Candidatos"]
    assert hoja.max_row == 1 + 17
    assert hoja.freeze_panes == "A2"
    assert libro["Errores"].max_row == 1 + 6


def test_correos_personalizados(resultado, tmp_path):
    mensajes = correos.preparar_correos(resultado.validos, PLANTILLA, "seleccion@example.com")
    assert len(mensajes) == 17

    primero = mensajes[0]
    candidato = resultado.validos[0]
    nombre = candidato.nombre.split(" ")[0]
    assert primero["To"] == candidato.email
    assert primero["Subject"] == f"Hemos recibido tu postulación, {nombre}"
    cuerpo = primero.get_content()
    assert f"Hola, {nombre}:" in cuerpo
    assert candidato.carrera in cuerpo
    assert "$" not in cuerpo  # no quedó ningún campo sin reemplazar

    rutas = correos.guardar_borradores(mensajes, tmp_path / "correos")
    assert len(list((tmp_path / "correos").glob("*.eml"))) == 17
    leido = message_from_bytes(rutas[0].read_bytes(), policy=default)
    assert leido["To"] == candidato.email


def test_plantilla_con_campo_mal_escrito(tmp_path):
    plantilla = tmp_path / "mala.txt"
    plantilla.write_text("Asunto: Hola $nombre\n\nTu carrera es $carerra.\n", encoding="utf-8")
    with pytest.raises(correos.PlantillaInvalida, match="carerra"):
        correos.leer_plantilla(plantilla)


def test_plantilla_sin_asunto(tmp_path):
    plantilla = tmp_path / "sin_asunto.txt"
    plantilla.write_text("Hola $nombre\n", encoding="utf-8")
    with pytest.raises(correos.PlantillaInvalida, match="Asunto"):
        correos.leer_plantilla(plantilla)


def test_enviar_sin_credenciales_falla_sin_conectar(monkeypatch):
    for variable in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"):
        monkeypatch.delenv(variable, raising=False)
    with pytest.raises(RuntimeError, match="SMTP_HOST"):
        correos.enviar([])


def test_pipeline_completo(tmp_path):
    r = pipeline.ejecutar(DATOS, tmp_path, PLANTILLA, "seleccion@example.com")
    assert (r.validos, r.errores, r.duplicados, r.correos) == (17, 6, 2, 17)
    assert not r.enviados
    for archivo in ("candidatos_limpios.csv", "errores.csv", "reporte_postulaciones.xlsx"):
        assert (tmp_path / archivo).exists()
    assert len(list((tmp_path / "correos").glob("*.eml"))) == 17

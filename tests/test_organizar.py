import pytest

from automatizacion import organizar
from automatizacion.__main__ import main


@pytest.fixture
def carpeta(tmp_path):
    for nombre in ["cv.pdf", "foto.JPG", "datos.xlsx", "instalador.exe", "raro.xyz", ".oculto"]:
        (tmp_path / nombre).write_text("x")
    (tmp_path / "Subcarpeta").mkdir()
    return tmp_path


def test_categoria_ignora_mayusculas():
    assert organizar.categoria(organizar.Path("FOTO.JPG")) == "Imágenes"
    assert organizar.categoria(organizar.Path("archivo.desconocido")) == "Otros"


def test_planificar_no_mueve_nada(carpeta):
    plan = organizar.planificar(carpeta)
    assert len(plan) == 5  # ignora el archivo oculto y la subcarpeta
    assert organizar.resumen(plan) == {
        "Documentos": 1,
        "Imágenes": 1,
        "Hojas de cálculo": 1,
        "Instaladores": 1,
        "Otros": 1,
    }
    assert (carpeta / "cv.pdf").exists()  # todo sigue en su sitio


def test_aplicar_mueve_y_evita_sobrescribir(carpeta):
    (carpeta / "Documentos").mkdir()
    (carpeta / "Documentos" / "cv.pdf").write_text("ya existía")

    organizar.aplicar(organizar.planificar(carpeta))

    assert (carpeta / "Documentos" / "cv.pdf").read_text() == "ya existía"
    assert (carpeta / "Documentos" / "cv (1).pdf").exists()
    assert (carpeta / "Imágenes" / "foto.JPG").exists()
    assert not (carpeta / "cv.pdf").exists()


def test_cli_simula_por_defecto(carpeta, capsys):
    assert main(["organizar", str(carpeta)]) == 0
    assert "Simulación" in capsys.readouterr().out
    assert (carpeta / "cv.pdf").exists()

    assert main(["organizar", str(carpeta), "--aplicar"]) == 0
    assert (carpeta / "Documentos" / "cv.pdf").exists()


def test_cli_carpeta_inexistente(tmp_path):
    assert main(["organizar", str(tmp_path / "no-existe")]) == 1

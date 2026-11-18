from datetime import date

import pytest

from automatizacion import candidatos as cand


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("  maria   JOSÉ  pérez ", "Maria José Pérez"),
        ("daniela DE LA cruz", "Daniela de la Cruz"),
        ("DE la Torre", "De la Torre"),  # la partícula inicial va en mayúscula
        ("   ", None),
    ],
)
def test_normalizar_nombre(entrada, esperado):
    assert cand.normalizar_nombre(entrada) == esperado


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (" Maria.Perez@Gmail.com ", "maria.perez@gmail.com"),
        ("carlos.gomez@gmail", None),
        ("mateo herrera@gmail.com", None),
        ("", None),
    ],
)
def test_normalizar_email(entrada, esperado):
    assert cand.normalizar_email(entrada) == esperado


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("0991234567", "+593 99 123 4567"),
        ("+593 99 123 4567", "+593 99 123 4567"),
        ("593991234567", "+593 99 123 4567"),
        ("(02) 2456-789", "+593 2 245 6789"),
        ("+593 4 260 1234", "+593 4 260 1234"),
        ("99123456", None),  # le falta un dígito
        ("12345", None),
        ("0812345678", None),  # no empieza por 9 ni es un fijo
    ],
)
def test_normalizar_telefono(entrada, esperado):
    assert cand.normalizar_telefono(entrada) == esperado


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("2026-10-03", date(2026, 10, 3)),
        ("05/10/2026", date(2026, 10, 5)),
        ("7-10-2026", date(2026, 10, 7)),
        ("2026/10/10", date(2026, 10, 10)),
        ("2026-13-01", None),
        ("ayer", None),
    ],
)
def test_normalizar_fecha(entrada, esperado):
    assert cand.normalizar_fecha(entrada) == esperado


def test_canonico_unifica_variantes():
    assert cand.canonico("ENFERMERIA", cand.CARRERAS) == "Enfermería"
    assert cand.canonico(" laboratorio   clinico ", cand.CARRERAS) == "Laboratorio Clínico"
    assert cand.canonico("santo domingo", cand.CIUDADES) == "Santo Domingo"  # desconocida: formato título
    assert cand.canonico("  ", cand.CIUDADES) is None


def fila(**cambios):
    base = {
        "nombre": "Ana Torres",
        "email": "ana@example.com",
        "telefono": "0991234567",
        "ciudad": "Quito",
        "carrera": "Medicina",
        "fecha_postulacion": "2026-10-01",
    }
    return {**base, **cambios}


def test_limpiar_reporta_todos_los_motivos_de_una_fila():
    resultado = cand.limpiar([fila(nombre="", email="mal", telefono="1")])
    assert resultado.validos == []
    error = resultado.errores[0]
    assert error.fila == 2
    assert error.motivos == ["Falta el nombre", "Correo no válido", "Teléfono no válido"]
    assert error.datos["email"] == "mal"  # se conserva el dato original para corregirlo


def test_limpiar_elimina_duplicados_quedandose_con_el_mas_reciente():
    resultado = cand.limpiar(
        [
            fila(nombre="Ana Antigua", fecha_postulacion="2026-10-01"),
            fila(nombre="Ana Reciente", email="ANA@example.com", fecha_postulacion="2026-10-20"),
            fila(nombre="Ana Intermedia", fecha_postulacion="2026-10-10"),
        ]
    )
    assert resultado.duplicados == 2
    assert [c.nombre for c in resultado.validos] == ["Ana Reciente"]


def test_csv_ida_y_vuelta(tmp_path):
    resultado = cand.limpiar([fila(), fila(email="luis@example.com", nombre="Luis Paredes")])
    ruta = tmp_path / "limpios.csv"
    cand.guardar_validos(resultado.validos, ruta)
    assert cand.leer_validos(ruta) == resultado.validos


def test_leer_csv_detecta_columnas_faltantes(tmp_path):
    ruta = tmp_path / "incompleto.csv"
    ruta.write_text("nombre,email\nAna,ana@example.com\n", encoding="utf-8")
    with pytest.raises(ValueError, match="faltan columnas"):
        cand.leer_csv(ruta)


def test_datos_de_ejemplo():
    resultado = cand.limpiar(cand.leer_csv(cand.Path("datos/candidatos.csv")))
    assert (len(resultado.validos), len(resultado.errores), resultado.duplicados) == (17, 6, 2)

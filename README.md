# Automatización de procesos con Python

Scripts para automatizar tareas administrativas repetitivas: limpiar y validar datos de un formulario, generar reportes en Excel, preparar correos personalizados y ordenar archivos. El caso de uso es un proceso de selección de candidatos, pero las piezas sirven para cualquier flujo de datos de una empresa.

![CI](https://github.com/dylannkeys/automatizacion-python/actions/workflows/ci.yml/badge.svg)

## El problema

Un equipo de selección recibe cada semana una exportación de su formulario de postulación. Antes de poder trabajar con ella, alguien tiene que:

1. Revisar fila por fila y corregir nombres en mayúsculas, correos mal escritos, teléfonos en formatos distintos y fechas inconsistentes.
2. Quitar postulaciones duplicadas.
3. Preparar un resumen para la dirección (cuántos candidatos por carrera, ciudad y mes).
4. Escribir a cada candidato para confirmar que se recibió su postulación.

Hecho a mano, son horas de trabajo cada semana y es fácil equivocarse.

## La solución

Un solo comando hace los cuatro pasos en menos de un segundo:

```
datos/candidatos.csv
        │
        ▼
 1. Limpieza y validación ──► candidatos_limpios.csv + errores.csv
        │
        ▼
 2. Reporte en Excel ───────► reporte_postulaciones.xlsx (resumen, gráfico y detalle)
        │
        ▼
 3. Correos personalizados ─► un borrador .eml por candidato (o envío por SMTP)
```

```bash
python -m automatizacion pipeline
```

```
Válidos: 17 | Con errores: 6 | Duplicados: 2
Reporte: salida/reporte_postulaciones.xlsx
Correos: 17 guardados como borradores
Tiempo: 0.17 s
```

Además, **GitHub Actions ejecuta el proceso cada lunes** ([reporte-semanal.yml](.github/workflows/reporte-semanal.yml)) y deja los resultados como un archivo descargable, sin que nadie tenga que acordarse de hacerlo.

## Los scripts

### 1. Limpieza y validación de datos ([candidatos.py](automatizacion/candidatos.py))

| Campo | Qué hace | Ejemplo |
| --- | --- | --- |
| Nombre | Quita espacios sobrantes y aplica mayúsculas correctas, respetando partículas | `  maria JOSÉ de la cruz ` → `Maria José de la Cruz` |
| Correo | Pasa a minúsculas y valida el formato | `Ana@Gmail.com` → `ana@gmail.com` |
| Teléfono | Acepta móviles y fijos de Ecuador en cualquier formato y los unifica | `0991234567`, `593 99 123 4567` → `+593 99 123 4567` |
| Ciudad y carrera | Unifica variantes sin importar tildes ni mayúsculas | `ENFERMERIA` → `Enfermería` |
| Fecha | Reconoce cuatro formatos habituales | `05/10/2026`, `7-10-2026` → `2026-10-05`, `2026-10-07` |

- Las filas que no se pueden corregir **no se descartan en silencio**: van a `errores.csv` con el número de fila original y todos los motivos, para que alguien las corrija en la fuente.
- Los **duplicados** se detectan por correo (sin distinguir mayúsculas) y se conserva la postulación más reciente.

### 2. Reporte en Excel ([reporte.py](automatizacion/reporte.py))

Genera un libro con tres hojas:
- **Resumen**: indicadores, tablas por carrera, ciudad y mes con porcentajes, y un gráfico de barras.
- **Candidatos**: el detalle limpio, con filtros, cabecera fija y anchos de columna ajustados.
- **Errores**: las filas que hay que revisar.

### 3. Correos personalizados ([correos.py](automatizacion/correos.py))

Combina una [plantilla de texto](plantillas/confirmacion.txt) con los datos de cada candidato (`$nombre`, `$carrera`, `$fecha`…).
- **Por defecto no envía nada**: guarda cada correo como `.eml` para revisarlo antes (se abre con Outlook o Thunderbird).
- Detecta campos mal escritos en la plantilla (por ejemplo, `$carerra`) **antes** de generar ningún correo.
- Con `--enviar`, los envía por SMTP usando credenciales de variables de entorno (nunca escritas en el código), con una pausa entre envíos. Si un correo falla, se registra y continúa con el resto.

### 4. Organizador de archivos ([organizar.py](automatizacion/organizar.py))

Ordena una carpeta en subcarpetas por tipo (Documentos, Imágenes, Hojas de cálculo, Instaladores…).
- Por defecto **solo simula** y muestra el plan; con `--aplicar` mueve los archivos.
- Nunca sobrescribe: si ya existe `cv.pdf`, guarda el nuevo como `cv (1).pdf`.

```bash
python -m automatizacion organizar ~/Downloads             # muestra qué haría
python -m automatizacion organizar ~/Downloads --aplicar   # lo hace
```

## Ejecutar

Requisitos: Python 3.10 o superior.

```bash
git clone https://github.com/dylannkeys/automatizacion-python.git
cd automatizacion-python
python -m venv .venv
.venv\Scripts\activate          # Windows (en macOS o Linux: source .venv/bin/activate)
pip install -r requirements.txt

python -m automatizacion pipeline     # proceso completo con los datos de ejemplo
python -m automatizacion --help       # todos los comandos
```

| Comando | Qué hace |
| --- | --- |
| `limpiar` | Valida y normaliza el CSV |
| `reporte` | Genera el Excel |
| `correos` | Prepara los correos desde el CSV limpio (`--enviar` para enviarlos) |
| `organizar <carpeta>` | Ordena una carpeta (`--aplicar` para mover) |
| `pipeline` | Limpieza + reporte + correos en un paso |

Todos aceptan `--entrada` y `--salida` para usar otros archivos, y `-v` para ver el detalle de cada paso.

### Enviar correos de verdad

```bash
set SMTP_HOST=smtp.gmail.com
set SMTP_USER=tu_correo@gmail.com
set SMTP_PASSWORD=tu_contraseña_de_aplicacion
python -m automatizacion pipeline --enviar --remitente tu_correo@gmail.com
```

Con Gmail hay que usar una *contraseña de aplicación*, no la contraseña normal de la cuenta.

### Programar la ejecución

- **GitHub Actions**: ya configurado para cada lunes (también se puede lanzar a mano desde la pestaña *Actions*).
- **Windows**: Programador de tareas, con la acción `python -m automatizacion pipeline` y la carpeta del proyecto como directorio de inicio.
- **Linux o macOS**: una línea de `cron`, por ejemplo `0 8 * * 1 cd /ruta/al/proyecto && .venv/bin/python -m automatizacion pipeline`.

## Tests

```bash
pip install pytest ruff
pytest
```

39 tests cubren cada normalizador con casos válidos e inválidos, la detección de duplicados, el contenido del Excel, la generación de correos (incluidas las plantillas con errores), el organizador con archivos temporales y el pipeline completo. El [CI](.github/workflows/ci.yml) los ejecuta con Python 3.10 y 3.12, junto con `ruff` para el estilo.

## Decisiones de diseño

- **Seguro por defecto**: las acciones con efectos (enviar correos, mover archivos) solo ocurren si se piden de forma explícita. Primero se puede revisar qué va a pasar.
- **Los errores se reportan, no se ocultan**: una automatización que descarta datos sin avisar es peor que no tener automatización.
- **Una sola dependencia externa** (`openpyxl`, para Excel). El resto usa la librería estándar de Python: `csv`, `email`, `smtplib`, `string.Template`, `argparse`, `logging`, `pathlib`.
- **Módulos independientes**: cada script se puede usar solo o importar desde otro programa. El pipeline solo los encadena.
- **Los CSV se guardan en UTF-8 con BOM** para que Excel muestre bien las tildes y la ñ.

## Posibles mejoras

- Leer las postulaciones directamente desde **Google Sheets** o un formulario (con la API de Google) en lugar de un CSV.
- Disparar el proceso con un flujo de **n8n** o **Make** cuando llegue una postulación nueva.
- Registrar los candidatos en un **CRM** como Odoo mediante su API.
- Guardar el historial en una base de datos para comparar semanas.

## Estructura

```
automatizacion-python/
├── automatizacion/
│   ├── candidatos.py   # limpieza y validación
│   ├── reporte.py      # Excel con resumen y gráfico
│   ├── correos.py      # plantillas, borradores .eml y envío SMTP
│   ├── organizar.py    # ordenar carpetas
│   ├── pipeline.py     # proceso completo
│   └── __main__.py     # línea de comandos
├── datos/              # CSV de ejemplo (datos ficticios)
├── plantillas/         # plantillas de correo
├── tests/
└── .github/workflows/  # CI y ejecución semanal
```

## Licencia

[MIT](LICENSE)

# Tarea 1 — INF396 Introducción a la Ciencia de Datos

Evaluación del Programa Semillas: tipos de datos, visualización e inferencia.

## Entregables

- `tarea1_fernandez_joaquin.ipynb`: cuaderno que se ejecuta de principio a fin, lee el CSV desde
  `https://aavelozb.github.io/data/semillas_2026.csv` y fija la semilla en la primera celda.
- `tarea1_fernandez_joaquin.pdf`: informe (10 páginas), con las figuras y las seis partes en orden.

## Cómo reproducir

```bash
python3.11 -m venv .venv && .venv/bin/pip install pandas numpy scipy matplotlib statsmodels jupyter nbconvert ipykernel nbformat markdown pypdf
.venv/bin/python build_notebook.py                       # escribe el .ipynb a partir de las celdas declaradas
.venv/bin/jupyter nbconvert --to notebook --execute --inplace tarea1_fernandez_joaquin.ipynb
.venv/bin/python build_informe.py                        # informe/informe.md -> informe/informe.html -> PDF (Chrome headless)
```

El cuaderno deja en `informe/fig/` las figuras y en `informe/resultados.json` todos los números que cita el informe;
`build_informe.py` arma el texto con esos valores, de modo que informe y cuaderno no pueden desincronizarse.

## Archivos

- `contexto`: enunciado de la tarea.
- `semillas_2026.csv`: copia local del archivo crudo (idéntica a la URL).
- `informe/semillas_2026_depurado.csv`: conjunto depurado (2.400 filas) que produce la parte 2.

"""Genera tarea1_fernandez_joaquin.ipynb a partir de celdas declaradas aquí.

Uso:  python build_notebook.py && jupyter nbconvert --to notebook --execute --inplace tarea1_fernandez_joaquin.ipynb
"""
import nbformat as nbf

cells = []
def md(s): cells.append(nbf.v4.new_markdown_cell(s.strip()))
def code(s): cells.append(nbf.v4.new_code_cell(s.strip()))

# --------------------------------------------------------------------------- 0
md(r"""
# Tarea 1 — Evaluación del Programa Semillas
**INF396, Introducción a la Ciencia de Datos** · Joaquín Fernández

Este cuaderno respalda los números del informe `tarea1_fernandez_joaquin.pdf`. Se ejecuta de principio a fin
leyendo el CSV desde la URL del enunciado; la semilla de la primera celda gobierna todo lo aleatorio
(bootstrap, permutaciones, simulaciones). Las figuras se guardan en `informe/fig/` y los números que cita el
informe en `informe/resultados.json`.

**Uso de IA.** El código y el texto se redactaron con ayuda de Claude Code (Anthropic) y fueron revisados por el autor.
""")
code(r"""
SEMILLA = 20261013
import numpy as np, pandas as pd, json, os, unicodedata, warnings
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
from scipy.cluster.hierarchy import linkage, leaves_list
from statsmodels.stats.multitest import multipletests
rng = np.random.default_rng(SEMILLA)
warnings.filterwarnings("ignore")
pd.set_option("display.width", 160); pd.set_option("display.max_columns", 40)

URL = "https://aavelozb.github.io/data/semillas_2026.csv"
os.makedirs("informe/fig", exist_ok=True)
R = {}                                   # resultados que cita el informe
def guardar(k, v): R[k] = v; return v

MATERIALES = ["cuaderno", "caja", "maletin", "cuentos"]
NOMBRE = {"cuaderno": "Cuaderno de Espera", "caja": "Caja de los Primeros Meses",
          "maletin": "Maletín Explorador", "cuentos": "Cuentos para Conversar"}
TRAMOS = ["Gestante", "0-11 meses", "12-35 meses", "36-59 meses"]
ZONAS = ["Norte", "Centro", "RM", "Sur"]
# tramo desde el cual cada material es elegible (índice en TRAMOS)
ELEGIBLE_DESDE = {"cuaderno": 0, "caja": 1, "maletin": 2, "cuentos": 3}
DISENO = pd.DataFrame({z: [120, 120, 150, 210] for z in ZONAS}, index=TRAMOS)

# estilo de figuras: paleta Okabe-Ito (legible en escala de grises con marcadores y tramas)
PALETA = ["#000000", "#E69F00", "#56B4E9", "#009E73", "#CC79A7", "#0072B2"]
MARCAS = ["o", "s", "^", "D"]
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 200, "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False})
def fig_guardar(fig, nombre):
    fig.tight_layout(); fig.savefig(f"informe/fig/{nombre}.png", bbox_inches="tight"); plt.show()

crudo = pd.read_csv(URL)
print("Archivo crudo:", crudo.shape)
""")

# --------------------------------------------------------------------------- 1
md(r"""
## Parte 1. Plan de análisis (preinscrito)

El plan completo está en la sección 1 del informe y se escribió antes de abrir el archivo. Aquí se deja
codificado lo que el cuaderno necesita: el nivel $\alpha$, los efectos mínimos relevantes y las reglas de
exclusión/corrección, para que las partes siguientes los usen tal como se declararon.

| Pregunta | $H_0$ | $H_1$ | Estadístico | Efecto mínimo relevante |
|---|---|---|---|---|
| Cobertura y uso | $p_{\text{frec}}$ igual entre macrozonas (por material) | difiere en algún par | Wald de dos proporciones, familia de 24 contrastes con Holm | 10 puntos porcentuales |
| Pertinencia y valoración | $p_{\text{pertinente}} \ge 0{,}80$ por material | $p_{\text{pertinente}} < 0{,}80$ | Wald de una proporción, unilateral | 10 puntos porcentuales bajo la meta |
| Resultados | mediana del índice igual entre uso frecuente y nunca del Cuaderno | difiere | permutación de la diferencia de medianas; IC bootstrap | 5 puntos del índice |

Control del error en la parte 4c: **Holm** (error global, FWER). Reglas de depuración: duplicado exacto → se
excluye; valor fuera de dominio o código centinela → se marca faltante; inconsistencia entre fechas → la fecha
de entrega se marca faltante; variante de escritura → se corrige a la forma canónica; unidades mezcladas →
se corrige por el factor que valide el cociente de modos.
""")
code(r"""
ALFA = 0.05
EMR = {"uso_pp": 10, "pertinencia_pp": 10, "indice_puntos": 5, "valoracion_puntos": 0.5}
META_PERTINENCIA = 0.80
CORRECCION_DECLARADA = "holm"
""")

# --------------------------------------------------------------------------- 2
md(r"""
## Parte 2. Tipos de variables y depuración

### 2a. Clasificación de columnas
""")
code(r"""
clasif = pd.DataFrame([
 ("id_cuidador","nominal","identificador","ninguna aritmética; sólo contar/unir"),
 ("id_centro","nominal","conglomerado","agrupar; define la unidad de muestreo"),
 ("macrozona","nominal","categórica","frecuencias, comparar proporciones"),
 ("region","nominal","categórica","frecuencias"),
 ("rural","nominal (dicotómica)","categórica","proporción; codificable 0/1"),
 ("tramo","ordinal","categórica","orden; mediana, no promedio"),
 ("edad_meses","razón","numérica","media, mediana, diferencias y cocientes"),
 ("semanas_gestacion","razón","numérica","media, mediana"),
 ("peso_nacimiento","razón","numérica","media, mediana; requiere unidad única"),
 ("sexo_cuidador","nominal (dicotómica)","categórica","proporción"),
 ("edad_cuidador","razón","numérica","media, mediana"),
 ("escolaridad","ordinal","categórica","orden, mediana; promedio sólo codificada y con supuesto de equidistancia"),
 ("migrante / pueblo_originario","nominal (dicotómica)","categórica","proporción"),
 ("n_hijos","razón (conteo)","numérica discreta","media, mediana"),
 ("recibio_<m>","nominal (dicotómica)","categórica","proporción (cobertura)"),
 ("uso_<m>","ordinal (Nunca<Ocasional<Frecuente)","categórica","orden; promediar no tiene sentido sin codificar"),
 ("valoracion_<m>","ordinal (Likert 1-5)","categórica ordenada","mediana; promediar supone intervalos iguales"),
 ("pertinente_<m>","nominal (dicotómica)","categórica","proporción"),
 ("indice_conocimientos","intervalo (0-100)","numérica","media, mediana, diferencias; cocientes dudosos"),
 ("lectura_semana","razón (conteo 0-7)","numérica discreta","media, mediana"),
 ("fecha_entrega / fecha_encuesta","intervalo (fecha)","fecha (cíclica en día de semana/mes)","diferencias de fechas; no promediar sin convertir"),
], columns=["columna","escala","estructura","operaciones con sentido"])
clasif
""")
md(r"""
### 2b. Vacío estructural vs. dato faltante por material

Un cuidador es *elegible* para un material si su tramo es el de entrega o posterior. Las columnas vacías de
un no elegible son **vacío estructural**; las vacías de un elegible son **dato faltante**. Para `uso`,
`valoracion` y `pertinente` la elegibilidad exige además haber recibido el material. Se cuantifica sobre el
archivo crudo (con duplicados) porque la pregunta es sobre el archivo tal como llegó.
""")
code(r"""
def elegible(df, m):
    return df["tramo"].map({t: i for i, t in enumerate(TRAMOS)}) >= ELEGIBLE_DESDE[m]

filas = []
for m in MATERIALES:
    el = elegible(crudo, m); rec = crudo[f"recibio_{m}"].eq("Sí")
    filas.append({"material": NOMBRE[m], "elegibles": int(el.sum()),
        "recibio: vacío estructural": int(crudo[f"recibio_{m}"].isna()[~el].sum()),
        "recibio: faltante": int(crudo[f"recibio_{m}"].isna()[el].sum()),
        "uso/valoracion/pertinente: vacío estructural": int((~(el & rec)).sum()),
        "uso: faltante": int(crudo[f"uso_{m}"].isna()[el & rec].sum()),
        "valoracion: faltante": int(crudo[f"valoracion_{m}"].isna()[el & rec].sum()),
        "pertinente: faltante": int(crudo[f"pertinente_{m}"].isna()[el & rec].sum())})
vacios = pd.DataFrame(filas).set_index("material"); guardar("vacios", vacios.reset_index().to_dict("records")); vacios
""")
md(r"""
### 2c. Depuración declarativa

Cada regla es una función del archivo crudo que devuelve una máscara de filas que la violan y una acción
(`excluir`, `faltante`, `corregir`). El bloque produce el informe de violaciones y el conjunto depurado sin
ninguna corrección manual. La regla de unidades mezcladas en `peso_nacimiento` se justifica antes, con el
cociente entre modos de una mezcla de dos normales en escala logarítmica.
""")
code(r"""
# --- Unidades mezcladas en peso_nacimiento: mezcla de dos normales en log10 -------------------
def em_dos_normales(x, iters=300):
    mu = np.array([np.percentile(x, 5), np.median(x)]); sd = np.array([0.1, 0.1]); w = np.array([0.1, 0.9])
    for _ in range(iters):
        r = w * stats.norm.pdf(x[:, None], mu, sd); r /= r.sum(1, keepdims=True)
        w = r.mean(0); mu = (r * x[:, None]).sum(0) / r.sum(0)
        sd = np.sqrt((r * (x[:, None] - mu) ** 2).sum(0) / r.sum(0))
    orden = np.argsort(mu); return w[orden], mu[orden], sd[orden]

x_log = np.log10(crudo["peso_nacimiento"].dropna().values)
w, mu, sd = em_dos_normales(x_log)
cociente_modos = 10 ** (mu[1] - mu[0])             # en log, la moda de cada componente es su media
B = 500
boot = np.empty(B)
for b in range(B):
    xb = rng.choice(x_log, size=x_log.size, replace=True)
    _, mub, _ = em_dos_normales(xb, iters=100); boot[b] = 10 ** (mub[1] - mub[0])
ic_cociente = np.percentile(boot, [2.5, 97.5])
FACTORES = {"kg -> g": 1000, "lb -> g": 453.59, "oz -> g": 28.35, "hg -> g": 100, "dag -> g": 10}
compatibles = [k for k, f in FACTORES.items() if ic_cociente[0] <= f <= ic_cociente[1]]
assert compatibles == ["kg -> g"], compatibles
FACTOR_PESO = FACTORES[compatibles[0]]
# frontera de decisión entre componentes (posterior 0,5), en gramos
grilla = np.linspace(mu[0], mu[1], 2000)
post0 = w[0]*stats.norm.pdf(grilla, mu[0], sd[0]) / (w[0]*stats.norm.pdf(grilla, mu[0], sd[0]) + w[1]*stats.norm.pdf(grilla, mu[1], sd[1]))
UMBRAL_PESO = 10 ** grilla[np.argmax(post0 < 0.5)]
guardar("peso_mezcla", {"pesos": w.round(3).tolist(), "modas_g": (10**mu).round(2).tolist(), "sd_log": sd.round(3).tolist(),
   "cociente_modos": round(float(cociente_modos), 1), "ic95_cociente": ic_cociente.round(1).tolist(),
   "factor_compatible": compatibles[0], "umbral_g": round(float(UMBRAL_PESO), 1)})
print(f"modas: {10**mu[0]:.2f} y {10**mu[1]:.0f}; cociente {cociente_modos:.1f}, IC bootstrap 95% [{ic_cociente[0]:.1f}, {ic_cociente[1]:.1f}]")
print("factor de la tabla compatible con el IC:", compatibles, "| umbral de decisión:", round(UMBRAL_PESO, 1), "g")

fig, ax = plt.subplots(figsize=(6.5, 3.2))
ax.hist(x_log, bins=60, density=True, color="0.75", edgecolor="white", label="peso_nacimiento (crudo)")
g = np.linspace(x_log.min(), x_log.max(), 400)
for i, est in enumerate(["--", "-"]):
    ax.plot(g, w[i]*stats.norm.pdf(g, mu[i], sd[i]), est, color="black", label=f"componente {i+1}: moda {10**mu[i]:,.0f} g" if i else f"componente {i+1}: moda {10**mu[i]:.2f}")
ax.set(title="Peso al nacer: mezcla de dos normales en escala log10", xlabel="log10(peso_nacimiento) [unidades mezcladas]", ylabel="densidad")
ax.legend(frameon=False, fontsize=8); fig_guardar(fig, "f00_peso_mezcla")
""")
code(r"""
# --- Reglas declarativas ---------------------------------------------------------------------
REGIONES = ["Arica y Parinacota","Tarapacá","Antofagasta","Atacama","Coquimbo","Valparaíso","Metropolitana",
            "O'Higgins","Maule","Ñuble","Biobío","La Araucanía","Los Ríos","Los Lagos","Aysén","Magallanes"]
# macrozonas del estudio: Ñuble y Biobío van en Sur (así vienen en el archivo; el enunciado no fija la composición)
ZONA_DE_REGION = {**{r: "Norte" for r in REGIONES[:5]}, **{r: "Centro" for r in ["Valparaíso","O'Higgins","Maule"]},
                  "Metropolitana": "RM", **{r: "Sur" for r in ["Ñuble","Biobío","La Araucanía","Los Ríos","Los Lagos","Aysén","Magallanes"]}}
def clave(s):  # forma canónica para comparar escrituras: sin tildes, minúsculas, sin espacios extra
    return "".join(c for c in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(c)).casefold().strip()
CANON_REGION = {clave(r): r for r in REGIONES}
fe = lambda df: pd.to_datetime(df["fecha_entrega"], errors="coerce")
fs = lambda df: pd.to_datetime(df["fecha_encuesta"], errors="coerce")

# (nombre, acción, máscara de filas que violan la regla, corrección opcional: función que devuelve un DataFrame)
REGLAS = [
 ("duplicado exacto (toda la fila repetida)", "excluir", lambda df: df.duplicated(keep="first"), None),
 ("id_cuidador repetido tras quitar duplicados exactos", "excluir", lambda df: df["id_cuidador"].duplicated(keep="first"), None),
 ("region: variante de escritura (mayúsculas/tildes)", "corregir", lambda df: df["region"].ne(df["region"].map(lambda s: CANON_REGION.get(clave(s), s))),
     lambda df: df.assign(region=df["region"].map(lambda s: CANON_REGION.get(clave(s), s)))),
 ("region no pertenece a la macrozona declarada", "faltante", lambda df: df["region"].map(ZONA_DE_REGION).ne(df["macrozona"]),
     lambda df: df.assign(region=df["region"].where(df["region"].map(ZONA_DE_REGION).eq(df["macrozona"])))),
 ("indice_conocimientos: código centinela -99", "faltante", lambda df: df["indice_conocimientos"].eq(-99),
     lambda df: df.assign(indice_conocimientos=df["indice_conocimientos"].replace(-99, np.nan))),
 ("indice_conocimientos fuera de [0, 100]", "faltante", lambda df: ~df["indice_conocimientos"].between(0, 100) & df["indice_conocimientos"].notna(),
     lambda df: df.assign(indice_conocimientos=df["indice_conocimientos"].where(df["indice_conocimientos"].between(0, 100)))),
 *[(f"valoracion_{m} fuera de la escala 1-5", "faltante",
     (lambda m: lambda df: ~df[f"valoracion_{m}"].between(1, 5) & df[f"valoracion_{m}"].notna())(m),
     (lambda m: lambda df: df.assign(**{f"valoracion_{m}": df[f"valoracion_{m}"].where(df[f"valoracion_{m}"].between(1, 5))}))(m)) for m in MATERIALES],
 (f"peso_nacimiento en kilogramos (valor < {UMBRAL_PESO:.0f} g, componente 1 de la mezcla)", "corregir",
     lambda df: df["peso_nacimiento"].lt(UMBRAL_PESO),
     lambda df: df.assign(peso_nacimiento=df["peso_nacimiento"].where(~df["peso_nacimiento"].lt(UMBRAL_PESO), df["peso_nacimiento"] * FACTOR_PESO))),
 ("fecha_entrega posterior a fecha_encuesta", "faltante", lambda df: fe(df) > fs(df),
     lambda df: df.assign(fecha_entrega=df["fecha_entrega"].where(~(fe(df) > fs(df))))),
 ("fecha no interpretable", "faltante", lambda df: fe(df).isna() & df["fecha_entrega"].notna() | fs(df).isna() & df["fecha_encuesta"].notna(), None),
 ("edad_meses fuera del tramo declarado", "faltante", lambda df: (df["tramo"].eq("0-11 meses") & ~df["edad_meses"].between(0, 11) |
     df["tramo"].eq("12-35 meses") & ~df["edad_meses"].between(12, 35) | df["tramo"].eq("36-59 meses") & ~df["edad_meses"].between(36, 59)) & df["edad_meses"].notna(), None),
 ("semanas_gestacion fuera de [4, 42]", "faltante", lambda df: ~df["semanas_gestacion"].between(4, 42) & df["semanas_gestacion"].notna(), None),
 ("lectura_semana fuera de [0, 7]", "faltante", lambda df: ~df["lectura_semana"].between(0, 7) & df["lectura_semana"].notna(), None),
 ("edad_cuidador fuera de [12, 90]", "faltante", lambda df: ~df["edad_cuidador"].between(12, 90), None),
 *[(f"uso/valoracion/pertinente_{m} informados sin recibir el material", "faltante",
     (lambda m: lambda df: df[f"recibio_{m}"].ne("Sí") & (df[f"uso_{m}"].notna() | df[f"valoracion_{m}"].notna() | df[f"pertinente_{m}"].notna()))(m), None) for m in MATERIALES],
 *[(f"recibio_{m} informado en tramo no elegible", "faltante",
     (lambda m: lambda df: ~elegible(df, m) & df[f"recibio_{m}"].notna())(m), None) for m in MATERIALES],
]

def depurar(df_crudo):
    df = df_crudo.copy(); informe = []
    for nombre, accion, mascara, correccion in REGLAS:
        viol = mascara(df).fillna(False).astype(bool); n = int(viol.sum())
        informe.append({"regla": nombre, "acción": accion, "registros": n})
        if n == 0: continue
        if accion == "excluir": df = df.loc[~viol]
        elif correccion is not None: df = correccion(df)
    df = df.copy()
    df["fecha_entrega"] = fe(df); df["fecha_encuesta"] = fs(df)
    df["escolaridad"] = pd.Categorical(df["escolaridad"], ["Básica","Media","Técnica","Universitaria"], ordered=True)
    df["tramo"] = pd.Categorical(df["tramo"], TRAMOS, ordered=True)
    for m in MATERIALES: df[f"uso_{m}"] = pd.Categorical(df[f"uso_{m}"], ["Nunca","Ocasional","Frecuente"], ordered=True)
    return df.reset_index(drop=True), pd.DataFrame(informe)

d, informe_depuracion = depurar(crudo)
print(f"Filas crudas: {len(crudo)}  ->  depuradas: {len(d)}  (diseño: {DISENO.values.sum()})")
assert len(d) == 2400 and pd.crosstab(d["macrozona"], d["tramo"]).T.loc[TRAMOS, ZONAS].equals(DISENO.astype("int64")), "no coincide con el diseño"
guardar("n_crudo", len(crudo)); guardar("n_depurado", len(d))
guardar("informe_depuracion", informe_depuracion.to_dict("records"))
informe_depuracion
""")
code(r"""
# Verificación de la corrección de unidades: una sola moda, rango plausible en gramos
print(d["peso_nacimiento"].describe().round(0))
""")
md(r"""
### 2d. Faltantes en escolaridad: ¿mecanismo completamente aleatorio?
""")
code(r"""
d["esc_falta"] = d["escolaridad"].isna().map({True: "sin escolaridad", False: "con escolaridad"})
guardar("esc_na", int(d["escolaridad"].isna().sum()))
tablas = {}
for v in ["rural", "macrozona"]:
    ct = pd.crosstab(d[v], d["esc_falta"]); pct = (ct / ct.sum() * 100).round(1)
    chi2, p, dof, _ = stats.chi2_contingency(ct)
    tablas[v] = {"pct": pct.to_dict(), "chi2": round(chi2, 2), "gl": dof, "p": round(p, 4)}
    print(f"\n{v}: chi2 = {chi2:.2f}, gl = {dof}, p = {p:.4f}"); print(pct)
# tasa de faltante por categoría (lectura directa del mecanismo)
tasa = {v: (d.groupby(v, observed=True)["escolaridad"].apply(lambda s: s.isna().mean() * 100).round(1).to_dict()) for v in ["rural", "macrozona", "tramo"]}
guardar("esc_na_tablas", tablas); guardar("esc_na_tasa", tasa); tasa
""")

# --------------------------------------------------------------------------- 3
md(r"""
## Parte 3. Análisis exploratorio y visualización

### 3a. Estructura de la muestra
""")
code(r"""
estructura = pd.crosstab(d["tramo"], d["macrozona"]).loc[TRAMOS, ZONAS]; estructura["Total"] = estructura.sum(1)
evaluan = pd.Series({NOMBRE[m]: int(elegible(d, m).sum()) for m in MATERIALES}, name="cuidadores que evalúan")
assert evaluan.tolist() == [2400, 1920, 1440, 840]
guardar("estructura", estructura.reset_index().to_dict("records")); guardar("evaluan", evaluan.to_dict())
display(estructura); evaluan
""")
md(r"""
### 3b. Figura principal: uso frecuente por material y macrozona (Wald 95 %, MAS)
""")
code(r"""
def wald(k, n, z=1.96):
    p = k / n; se = np.sqrt(p * (1 - p) / n); return p, se, p - z * se, p + z * se

# indicadores 0/1 de uso frecuente (NaN si no recibió) y cobertura
for m in MATERIALES:
    d[f"frec_{m}"] = d[f"uso_{m}"].eq("Frecuente").astype(float).where(d[f"recibio_{m}"].eq("Sí"))
    d[f"cob_{m}"] = d[f"recibio_{m}"].eq("Sí").astype(float).where(elegible(d, m))

filas = []
for m in MATERIALES:
    for z in ZONAS:
        s = d.loc[d["macrozona"].eq(z), f"frec_{m}"].dropna(); c = d.loc[d["macrozona"].eq(z), f"cob_{m}"].dropna()
        p, se, lo, hi = wald(s.sum(), len(s)); pc = c.mean()
        filas.append({"material": m, "macrozona": z, "n_elegibles": len(c), "cobertura": pc, "n_recibio": len(s), "k_frec": int(s.sum()), "p_frec": p, "se": se, "ic_lo": lo, "ic_hi": hi})
uso_zona = pd.DataFrame(filas); guardar("uso_zona", uso_zona.round(4).to_dict("records"))
uso_zona.pivot(index="material", columns="macrozona", values="p_frec").loc[MATERIALES, ZONAS].round(3)
""")
code(r"""
fig, axes = plt.subplots(1, 4, figsize=(11, 3.4), sharey=True)
for ax, m in zip(axes, MATERIALES):
    sub = uso_zona[uso_zona["material"].eq(m)].set_index("macrozona").loc[ZONAS]
    x = np.arange(len(ZONAS))
    ax.errorbar(x, sub["p_frec"] * 100, yerr=[(sub["p_frec"] - sub["ic_lo"]) * 100, (sub["ic_hi"] - sub["p_frec"]) * 100],
                fmt="o", color="black", capsize=3, lw=1.2)
    for xi, (z, r) in zip(x, sub.iterrows()):
        ax.text(xi, r["ic_hi"] * 100 + 1.2, f"{r['p_frec']*100:.0f}", ha="center", fontsize=8)
    ax.set_xticks(x, ZONAS); ax.set_title(f"{NOMBRE[m]}\n(n = {int(sub['n_recibio'].sum())} que lo recibieron)", fontsize=9)
    ax.grid(axis="y", color="0.9")
axes[0].set_ylabel("Uso frecuente (% de quienes lo recibieron)"); axes[0].set_ylim(30, 75)
fig.suptitle("Uso frecuente de cada material por macrozona, con intervalo de Wald del 95 % (muestreo aleatorio simple)", fontsize=10)
fig_guardar(fig, "f01_principal_uso_frecuente")
""")
code(r"""
# Versión deliberadamente mala del mismo contenido
fig, ax = plt.subplots(figsize=(7, 3.4))
piv = uso_zona.pivot(index="macrozona", columns="material", values="p_frec").loc[ZONAS, MATERIALES] * 100
abajo = np.zeros(len(ZONAS)); cmap = plt.get_cmap("jet")
for i, m in enumerate(MATERIALES):
    ax.bar(ZONAS, piv[m], bottom=abajo, color=cmap(i / 3), label=m); abajo += piv[m].values
ax.set_ylim(150, 240); ax.legend(loc="upper right", fontsize=7); ax.set_title("uso")
fig_guardar(fig, "f02_mala")
""")
md(r"""
### 3c. Distribución del índice de conocimientos por escolaridad y por tramo
""")
code(r"""
def resumen_robusto(g):
    q = g.quantile([.25, .5, .75]); return pd.Series({"n": g.notna().sum(), "Q1": q[.25], "mediana": q[.5], "Q3": q[.75], "media": g.mean(), "mín": g.min(), "máx": g.max()})
res_esc = d.groupby("escolaridad", observed=True)["indice_conocimientos"].apply(resumen_robusto).unstack().round(1)
res_tramo = d.groupby("tramo", observed=True)["indice_conocimientos"].apply(resumen_robusto).unstack().round(1)
guardar("indice_por_escolaridad", res_esc.reset_index().to_dict("records")); guardar("indice_por_tramo", res_tramo.reset_index().to_dict("records"))
guardar("indice_global", resumen_robusto(d["indice_conocimientos"]).round(1).to_dict())
guardar("indice_asimetria", round(float(stats.skew(d["indice_conocimientos"].dropna())), 2))
display(res_esc); res_tramo
""")
code(r"""
fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
for ax, (v, niveles) in zip(axes, [("escolaridad", ["Básica","Media","Técnica","Universitaria"]), ("tramo", TRAMOS)]):
    datos = [d.loc[d[v].eq(k), "indice_conocimientos"].dropna().values for k in niveles]
    ax.boxplot(datos, tick_labels=[f"{k}\n(n={len(x)})" for k, x in zip(niveles, datos)], widths=0.5, showmeans=True,
               meanprops=dict(marker="D", markerfacecolor="white", markeredgecolor="black", markersize=4),
               medianprops=dict(color="black", lw=1.5), boxprops=dict(color="0.3"), flierprops=dict(marker=".", markersize=3, color="0.5"))
    for i, x in enumerate(datos, 1):   # puntos con jitter detrás de la caja
        ax.scatter(i + rng.uniform(-.18, .18, len(x)), x, s=3, color="0.6", alpha=.25, zorder=0)
    ax.set_title(f"Índice de conocimientos por {v}", fontsize=10); ax.set_xlabel(v)
axes[0].set_ylabel("Índice de conocimientos sobre crianza (0-100)")
fig.suptitle("Caja = cuartiles y mediana (línea); rombo = media; puntos = cuidadores", fontsize=9, y=1.02)
fig_guardar(fig, "f03_indice_boxplot")
""")
md(r"""
### 3d. Lectura semanal vs. índice de conocimientos (sin sobreploteo)
""")
code(r"""
sub = d.dropna(subset=["lectura_semana", "indice_conocimientos"])
rho, p_rho = stats.spearmanr(sub["lectura_semana"], sub["indice_conocimientos"])
guardar("lectura_indice", {"n": len(sub), "spearman": round(rho, 3), "p": float(f"{p_rho:.2e}"),
        "mediana_por_dia": sub.groupby("lectura_semana")["indice_conocimientos"].median().round(1).to_dict()})
fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
ax = axes[0]
ax.scatter(sub["lectura_semana"] + rng.uniform(-.3, .3, len(sub)), sub["indice_conocimientos"], s=5, color="black", alpha=.15)
med = sub.groupby("lectura_semana")["indice_conocimientos"].median()
ax.plot(med.index, med.values, "o-", color=PALETA[1], lw=2, label="mediana por día")
ax.set(xlabel="Días por semana en que se lee al niño/a (0-7)", ylabel="Índice de conocimientos (0-100)", title="Dispersión con jitter horizontal y transparencia")
ax.legend(frameon=False, loc="lower right")
ax = axes[1]
hb = ax.hexbin(sub["lectura_semana"], sub["indice_conocimientos"], gridsize=(8, 18), cmap="Greys", mincnt=1)
fig.colorbar(hb, ax=ax, label="cuidadores por celda")
ax.set(xlabel="Días por semana en que se lee al niño/a (0-7)", ylabel="Índice de conocimientos (0-100)", title=f"Densidad en celdas hexagonales (ρ de Spearman = {rho:.2f})")
fig_guardar(fig, "f04_lectura_indice")
""")
md(r"""
### 3e. Uso frecuente del Cuaderno e índice: en toda la muestra y por escolaridad (confusión)
""")
code(r"""
sub = d[d["recibio_cuaderno"].eq("Sí")].dropna(subset=["indice_conocimientos"]).copy()
sub["grupo"] = np.where(sub["frec_cuaderno"].eq(1), "frecuente", "no frecuente")
def dif_medias(g):
    a = g.loc[g["grupo"].eq("frecuente"), "indice_conocimientos"]; b = g.loc[g["grupo"].eq("no frecuente"), "indice_conocimientos"]
    return pd.Series({"n frecuente": len(a), "media frecuente": a.mean(), "n no frecuente": len(b), "media no frecuente": b.mean(), "diferencia": a.mean() - b.mean(),
                      "% uso frecuente": len(a) / len(g) * 100})
simpson = pd.concat([dif_medias(sub).to_frame("Toda la muestra").T, sub.groupby("escolaridad", observed=True).apply(dif_medias, include_groups=False)]).round(1)
guardar("simpson", simpson.reset_index().rename(columns={"index": "estrato"}).to_dict("records")); simpson
""")
code(r"""
fig, ax = plt.subplots(figsize=(7, 3.4))
niveles = ["Básica", "Media", "Técnica", "Universitaria"]
for j, (g, mk) in enumerate([("no frecuente", "s"), ("frecuente", "o")]):
    ax.plot(niveles, [simpson.loc[k, "media " + g] for k in niveles], marker=mk, color=PALETA[j], ls="-" if j else "--", label=f"uso {g}")
for j, g in enumerate(["no frecuente", "frecuente"]):
    ax.axhline(simpson.loc["Toda la muestra", "media " + g], color=PALETA[j], ls=":", lw=1)
    ax.text(3.45, simpson.loc["Toda la muestra", "media " + g], f"media total {g}", fontsize=7, va="center", color=PALETA[j])
ax.set(title="Índice de conocimientos según uso del Cuaderno de Espera, por escolaridad", xlabel="Escolaridad del cuidador", ylabel="Media del índice (0-100)")
ax.legend(frameon=False, loc="upper left"); fig_guardar(fig, "f05_simpson")
""")
md(r"""
### 3f. Matriz de correlaciones con reordenamiento jerárquico
""")
code(r"""
d["escolaridad_ord"] = d["escolaridad"].cat.codes.replace(-1, np.nan) + 1   # 1=Básica … 4=Universitaria
d["rural01"] = d["rural"].eq("Rural").astype(int)
cols = {f"frec_{m}": "binaria" for m in MATERIALES} | {"escolaridad_ord": "ordinal", "rural01": "binaria"} | \
       {f"valoracion_{m}": "ordinal" for m in MATERIALES} | \
       {c: "numérica" for c in ["edad_meses","peso_nacimiento","edad_cuidador","n_hijos","indice_conocimientos","lectura_semana"]}
nombres = list(cols); k = len(nombres)
corr = pd.DataFrame(np.eye(k), index=nombres, columns=nombres); metodo = corr.copy().astype(object)
for i in range(k):
    for j in range(i + 1, k):
        a, b = nombres[i], nombres[j]; par = d[[a, b]].dropna()
        if len(par) < 30: r = np.nan; met = "—"
        elif "ordinal" in (cols[a], cols[b]): r = stats.spearmanr(par[a], par[b])[0]; met = "Spearman"
        else: r = stats.pearsonr(par[a], par[b])[0]; met = "Pearson"   # incluye punto-biserial y phi
        corr.loc[a, b] = corr.loc[b, a] = r; metodo.loc[a, b] = metodo.loc[b, a] = met
# reordenar por agrupamiento jerárquico (distancia 1 - |r|, enlace promedio)
dist = 1 - corr.abs().fillna(0).values; dist = dist[np.triu_indices(k, 1)]
orden = leaves_list(linkage(dist, method="average")); ordenados = [nombres[i] for i in orden]
corr_o = corr.loc[ordenados, ordenados]
guardar("corr_metodos", {"Spearman": int((metodo.values == "Spearman").sum() // 2), "Pearson": int((metodo.values == "Pearson").sum() // 2), "sin_par": int((metodo.values == "—").sum() // 2)})
pares = corr_o.where(np.triu(np.ones((k, k), bool), 1)).stack().sort_values(key=abs, ascending=False).head(10).round(2)
guardar("corr_top", [{"par": f"{a} ~ {b}", "r": float(v), "método": metodo.loc[a, b]} for (a, b), v in pares.items()]); pares
""")
code(r"""
fig, ax = plt.subplots(figsize=(8, 6.5))
im = ax.imshow(corr_o.values, cmap="PuOr_r", vmin=-1, vmax=1)
ax.set_xticks(range(k), ordenados, rotation=60, ha="right", fontsize=8); ax.set_yticks(range(k), ordenados, fontsize=8)
for i in range(k):
    for j in range(k):
        v = corr_o.values[i, j]
        if not np.isnan(v) and i != j: ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6, color="white" if abs(v) > .5 else "black")
fig.colorbar(im, ax=ax, shrink=.75, label="coeficiente (Pearson: numérica/binaria; Spearman: pares con ordinal)")
ax.set_title("Correlaciones reordenadas por agrupamiento jerárquico (enlace promedio, distancia 1 − |r|)", fontsize=10)
fig_guardar(fig, "f06_correlaciones")
""")

# --------------------------------------------------------------------------- 4
md(r"""
## Parte 4. Inferencia

### 4a. Proporción nacional de uso frecuente, correlación intraclase y efecto de diseño

La estimación nacional promedia las cuatro macrozonas con peso igual: $\hat p = \tfrac14\sum_z \hat p_z$ y
$\mathrm{Var}(\hat p)=\tfrac1{16}\sum_z \hat p_z(1-\hat p_z)/n_z$. Con $\rho_I$ y $\bar m$ se calcula
$\mathrm{deff}=1+(\bar m-1)\rho_I$ y el error estándar corregido es $\mathrm{EE}\cdot\sqrt{\mathrm{deff}}$
(el deff multiplica la varianza; el enunciado lo escribe sobre el error estándar y se interpreta como
$\sqrt{\mathrm{deff}}$).
""")
code(r"""
def icc_anova(y, grupo):
    g = pd.DataFrame({"y": y, "g": grupo}).dropna(); N = len(g); k = g["g"].nunique()
    medias = g.groupby("g")["y"].agg(["mean", "size"]); gran = g["y"].mean()
    ssb = (medias["size"] * (medias["mean"] - gran) ** 2).sum(); ssw = ((g["y"] - g["g"].map(medias["mean"])) ** 2).sum()
    cmb, cmd = ssb / (k - 1), ssw / (N - k); m_bar = N / k
    rho = (cmb - cmd) / (cmb + (m_bar - 1) * cmd)
    return rho, m_bar, k, cmb, cmd

filas = []
for m in MATERIALES:
    z_ = uso_zona[uso_zona["material"].eq(m)]
    p_nac = z_["p_frec"].mean(); se_nac = np.sqrt((z_["p_frec"] * (1 - z_["p_frec"]) / z_["n_recibio"]).sum()) / 4
    rec = d[d[f"recibio_{m}"].eq("Sí")]
    rho, m_bar, k_, cmb, cmd = icc_anova(rec[f"frec_{m}"], rec["id_centro"])
    rho_t = max(rho, 0.0); deff = 1 + (m_bar - 1) * rho_t
    filas.append({"material": NOMBRE[m], "n_recibio": len(rec), "p_nacional": p_nac, "ee_mas": se_nac, "ic_mas": (p_nac - 1.96 * se_nac, p_nac + 1.96 * se_nac),
                  "centros": k_, "m_barra": m_bar, "rho_I": rho, "rho_truncado": rho_t, "deff": deff, "ee_deff": se_nac * np.sqrt(deff),
                  "ic_deff": (p_nac - 1.96 * se_nac * np.sqrt(deff), p_nac + 1.96 * se_nac * np.sqrt(deff))})
nacional = pd.DataFrame(filas).set_index("material")
nacional["ancho_mas_pp"] = (nacional["ic_mas"].str[1] - nacional["ic_mas"].str[0]) * 100
nacional["ancho_deff_pp"] = (nacional["ic_deff"].str[1] - nacional["ic_deff"].str[0]) * 100
DEFF = {m: float(nacional.loc[NOMBRE[m], "deff"]) for m in MATERIALES}
guardar("nacional", [{k: (round(v, 4) if isinstance(v, float) else (tuple(round(x, 4) for x in v) if isinstance(v, tuple) else v)) for k, v in r.items()} for r in nacional.reset_index().to_dict("records")])
guardar("deff", {m: round(v, 3) for m, v in DEFF.items()}); guardar("deff_max", round(max(DEFF.values()), 3))
nacional.round(4)
""")
code(r"""
# Cobertura nacional (promedio de macrozonas), para la pregunta de cobertura
cob = uso_zona.pivot(index="material", columns="macrozona", values="cobertura").loc[MATERIALES, ZONAS]
cob["nacional"] = cob.mean(1); guardar("cobertura", (cob * 100).round(1).reset_index().to_dict("records")); (cob * 100).round(1)
""")
md(r"""
### 4b. Test de Wald para dos proporciones: dos contrastes puntuales
""")
code(r"""
def wald_dos_prop(k1, n1, k2, n2):
    p1, p2 = k1 / n1, k2 / n2; dif = p1 - p2; se = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    z = dif / se; p = 2 * stats.norm.sf(abs(z)); return dif, se, dif - 1.96 * se, dif + 1.96 * se, z, p
def fila_zona(m, z): r = uso_zona[(uso_zona["material"] == m) & (uso_zona["macrozona"] == z)].iloc[0]; return r["k_frec"], r["n_recibio"]
contrastes_b = []
for m, z1, z2 in [("cuaderno", "RM", "Norte"), ("cuentos", "Centro", "Sur")]:
    k1, n1 = fila_zona(m, z1); k2, n2 = fila_zona(m, z2); dif, se, lo, hi, z, p = wald_dos_prop(k1, n1, k2, n2)
    contrastes_b.append({"material": NOMBRE[m], "contraste": f"{z1} − {z2}", "p1": k1 / n1, "p2": k2 / n2, "diferencia_pp": dif * 100, "ic95_pp": (lo * 100, hi * 100), "z": z, "p": p,
                         "supera_EMR": abs(dif * 100) >= EMR["uso_pp"], "IC_excluye_EMR": not (lo * 100 <= EMR["uso_pp"] <= hi * 100 or lo * 100 <= -EMR["uso_pp"] <= hi * 100)})
contrastes_b = pd.DataFrame(contrastes_b)
guardar("contrastes_b", [{k: (round(v, 4) if isinstance(v, float) else (tuple(round(x, 2) for x in v) if isinstance(v, tuple) else v)) for k, v in r.items()} for r in contrastes_b.to_dict("records")])
contrastes_b.round(4)
""")
md(r"""
### 4c. Las 24 comparaciones por pares como una sola familia: Holm (declarado) y Benjamini-Hochberg
""")
code(r"""
from itertools import combinations
filas = []
for m in MATERIALES:
    for z1, z2 in combinations(ZONAS, 2):
        k1, n1 = fila_zona(m, z1); k2, n2 = fila_zona(m, z2); dif, se, lo, hi, z, p = wald_dos_prop(k1, n1, k2, n2)
        filas.append({"material": NOMBRE[m], "par": f"{z1} − {z2}", "dif_pp": dif * 100, "ic_lo_pp": lo * 100, "ic_hi_pp": hi * 100, "p": p})
fam = pd.DataFrame(filas).sort_values("p").reset_index(drop=True)
fam["rango"] = np.arange(1, len(fam) + 1)
fam["p_holm"] = multipletests(fam["p"], alpha=ALFA, method="holm")[1]
fam["p_BH"] = multipletests(fam["p"], alpha=ALFA, method="fdr_bh")[1]
fam["p_bonferroni"] = np.minimum(fam["p"] * len(fam), 1)
fam["sin_corregir"] = fam["p"] < ALFA; fam["Holm"] = fam["p_holm"] < ALFA; fam["BH"] = fam["p_BH"] < ALFA
guardar("familia", fam.round(4).to_dict("records"))
guardar("familia_resumen", {"sin_corregir": int(fam["sin_corregir"].sum()), "holm": int(fam["Holm"].sum()), "bh": int(fam["BH"].sum()), "bonferroni": int((fam["p_bonferroni"] < ALFA).sum()),
                            "umbral_holm_primero": round(ALFA / 24, 5),
                            "umbral_bh_ultimo_rechazado": round(ALFA * int(fam["BH"].sum()) / 24, 5)})
fam.round(4)
""")
md(r"""
### 4d. Independencia entre uso (tres niveles) y macrozona para el Maletín Explorador
""")
code(r"""
rec = d[d["recibio_maletin"].eq("Sí")]
tabla = pd.crosstab(rec["macrozona"], rec["uso_maletin"]).loc[ZONAS, ["Nunca", "Ocasional", "Frecuente"]]
chi2, p, gl, esperado = stats.chi2_contingency(tabla)
guardar("chi2_maletin", {"chi2": round(chi2, 2), "gl": int(gl), "p": round(p, 4), "tabla": tabla.reset_index().to_dict("records"),
        "pct_fila": (tabla.div(tabla.sum(1), axis=0) * 100).round(1).reset_index().to_dict("records"), "min_esperado": round(esperado.min(), 1)})
print(f"chi2 = {chi2:.2f}, gl = {gl}, p = {p:.4f}, mínimo esperado = {esperado.min():.1f}")
display(tabla); (tabla.div(tabla.sum(1), axis=0) * 100).round(1)
""")
md(r"""
### 4e. Diferencia de medianas del índice: uso frecuente vs. nunca del Cuaderno (bootstrap y permutación)
""")
code(r"""
rec = d[d["recibio_cuaderno"].eq("Sí")].dropna(subset=["indice_conocimientos"])
a = rec.loc[rec["uso_cuaderno"].eq("Frecuente"), "indice_conocimientos"].values
b = rec.loc[rec["uso_cuaderno"].eq("Nunca"), "indice_conocimientos"].values
dif_obs = np.median(a) - np.median(b)
B_BOOT, B_PERM = 4000, 10000
boot = np.array([np.median(rng.choice(a, a.size)) - np.median(rng.choice(b, b.size)) for _ in range(B_BOOT)])
ic_boot = np.percentile(boot, [2.5, 97.5])
todo = np.concatenate([a, b]); perm = np.empty(B_PERM)
for i in range(B_PERM):
    rng.shuffle(todo); perm[i] = np.median(todo[:a.size]) - np.median(todo[a.size:])
p_perm = (np.sum(np.abs(perm) >= abs(dif_obs)) + 1) / (B_PERM + 1)
guardar("medianas", {"n_frecuente": int(a.size), "n_nunca": int(b.size), "mediana_frecuente": float(np.median(a)), "mediana_nunca": float(np.median(b)),
        "dif": round(float(dif_obs), 2), "ic_boot": ic_boot.round(2).tolist(), "B_boot": B_BOOT, "B_perm": B_PERM, "p_perm": round(float(p_perm), 4),
        "dif_media": round(float(a.mean() - b.mean()), 2)})
print(f"mediana frecuente {np.median(a):.1f} (n={a.size}) − mediana nunca {np.median(b):.1f} (n={b.size}) = {dif_obs:.2f}; IC bootstrap 95% [{ic_boot[0]:.2f}, {ic_boot[1]:.2f}]; p permutación = {p_perm:.4f}")
""")
md(r"""
### 4f. Contraste de las hipótesis preinscritas en la parte 1

La hipótesis 1 se resuelve en 4c y la 3 en 4e. La hipótesis 2 (pertinencia $\ge 80\,\%$) se contrasta aquí para no dejarla sin respuesta.
""")
code(r"""
filas = []
for m in MATERIALES:
    s = d.loc[d[f"recibio_{m}"].eq("Sí"), f"pertinente_{m}"].dropna(); k_, n_ = s.eq("Sí").sum(), len(s); p_hat = k_ / n_
    se0 = np.sqrt(META_PERTINENCIA * (1 - META_PERTINENCIA) / n_); z = (p_hat - META_PERTINENCIA) / se0; p = stats.norm.cdf(z)   # unilateral: H1 p < 0,80
    val = d.loc[d[f"recibio_{m}"].eq("Sí"), f"valoracion_{m}"]
    filas.append({"material": NOMBRE[m], "n": n_, "pertinente_%": p_hat * 100, "ic95_%": (wald(k_, n_)[2] * 100, wald(k_, n_)[3] * 100), "z": z, "p_unilateral": p,
                  "valoracion_mediana": val.median(), "valoracion_media": val.mean(), "valoracion_%4o5": val.ge(4).mean() * 100})
pert = pd.DataFrame(filas)
guardar("pertinencia", [{k: (round(v, 4) if isinstance(v, float) else (tuple(round(x, 1) for x in v) if isinstance(v, tuple) else v)) for k, v in r.items()} for r in pert.to_dict("records")])
pert.round(3)
""")

# --------------------------------------------------------------------------- 5
md(r"""
## Parte 5. Potencia y tamaño de la muestra

Se usan los tamaños de **diseño** (2.400 nacional, 600 por macrozona, 840 para Cuentos), no los observados.
""")
code(r"""
z_a, z_b = stats.norm.ppf(0.975), stats.norm.ppf(0.80)
def margen(n, deff=1.0, p=0.5): return z_a * np.sqrt(p * (1 - p) / n) * np.sqrt(deff) * 100
def dmd(n_por_grupo, deff=1.0, p=0.5, z_alfa=z_a): return (z_alfa + z_b) * np.sqrt(2 * p * (1 - p) / (n_por_grupo / deff)) * 100
deff_max = max(DEFF.values())
filas = [("Nacional, cualquier material (n = 2.400)", 2400, deff_max), ("Por macrozona (n = 600)", 600, deff_max), ("Cuentos para Conversar, nacional (n = 840)", 840, DEFF["cuentos"]),
         ("Cuentos para Conversar, por macrozona (n = 210)", 210, DEFF["cuentos"])]
margenes = pd.DataFrame([{"estimación": e, "n": n, "deff usado": round(f, 3), "margen MAS (pp)": margen(n), "margen con deff (pp)": margen(n, f), "cumple 3,5 % (MAS)": margen(n) <= 3.5, "cumple 3,5 % (deff)": margen(n, f) <= 3.5} for e, n, f in filas])
# reducción de precisión por no recepción: n observado de quienes recibieron
recibidos = {m: int(d[f"recibio_{m}"].eq("Sí").sum()) for m in MATERIALES}
guardar("margenes", margenes.round(2).to_dict("records")); guardar("recibidos", recibidos)
guardar("margen_recibidos", {NOMBRE[m]: {"n_recibio": recibidos[m], "margen MAS": round(margen(recibidos[m]), 2), "margen deff": round(margen(recibidos[m], DEFF[m]), 2)} for m in MATERIALES})
margenes.round(2)
""")
code(r"""
dmds = pd.DataFrame([{"contraste": "Dos macrozonas, material de toda la muestra (600 vs 600)", "n por grupo": 600, "DMD MAS (pp)": dmd(600), "DMD con deff (pp)": dmd(600, deff_max)},
                     {"contraste": "Dos macrozonas, Cuentos para Conversar (210 vs 210)", "n por grupo": 210, "DMD MAS (pp)": dmd(210), "DMD con deff (pp)": dmd(210, DEFF["cuentos"])}])
guardar("dmd", dmds.round(2).to_dict("records")); dmds.round(2)
""")
md(r"""
### 5c. Tamaño de muestra del seguimiento 2027
""")
code(r"""
DELTA, DEFF27, RESP, ALFA_B = 0.05, 1.5, 0.80, 0.05 / 6
PROP_TRAMO = {"Gestante": .20, "0-11 meses": .20, "12-35 meses": .25, "36-59 meses": .35}
z_ab = stats.norm.ppf(1 - ALFA_B / 2)
n_eff = (z_ab + z_b) ** 2 * 2 * 0.25 / DELTA ** 2          # respondentes efectivos por macrozona en el tramo 36-59 (Cuentos)
n_resp = n_eff * DEFF27; n_contact_tramo = n_resp / RESP
n_contact_zona = n_contact_tramo / PROP_TRAMO["36-59 meses"]
por_tramo = {t: int(np.ceil(n_contact_zona * f)) for t, f in PROP_TRAMO.items()}
total_zona = sum(por_tramo.values()); total_nac = total_zona * 4
plan27 = {"z_alfa_bonf": round(z_ab, 3), "n_efectivo": int(np.ceil(n_eff)), "n_respondentes_36_59": int(np.ceil(n_resp)), "n_contactar_36_59": int(np.ceil(n_contact_tramo)),
          "por_tramo_por_zona": por_tramo, "total_por_zona": total_zona, "total_nacional": total_nac}
# verificación por simulación: MAS con n_eff, p = 0,50 vs 0,55, test de Wald a alfa/6
def potencia_sim(n_ef, delta=DELTA, sims=20000):
    n_ef = int(round(n_ef)); k1 = rng.binomial(n_ef, 0.5, sims); k2 = rng.binomial(n_ef, 0.5 + delta, sims)
    p1, p2 = k1 / n_ef, k2 / n_ef; z = (p2 - p1) / np.sqrt(p1 * (1 - p1) / n_ef + p2 * (1 - p2) / n_ef)
    return float(np.mean(np.abs(z) > z_ab))
plan27["potencia_simulada"] = potencia_sim(n_eff)
# con 4.000 contactados en total: qué diferencia es detectable
n_zona_4000 = 1000 * RESP
n_ef_cuentos = n_zona_4000 * PROP_TRAMO["36-59 meses"] / DEFF27; n_ef_todos = n_zona_4000 / DEFF27
plan27["con_4000"] = {"n_eff_cuentos": round(n_ef_cuentos, 1), "dmd_cuentos_pp": round(dmd(n_ef_cuentos, 1, z_alfa=z_ab), 1), "n_eff_todos": round(n_ef_todos, 1), "dmd_todos_pp": round(dmd(n_ef_todos, 1, z_alfa=z_ab), 1),
                     "potencia_sim_cuentos_delta_obj": potencia_sim(n_ef_cuentos), "potencia_sim_todos_delta_obj": potencia_sim(n_ef_todos)}
# qué supuesto encarece más: costo del total nacional al relajar cada uno
def total(delta=DELTA, deff=DEFF27, resp=RESP, alfa=ALFA_B, prop=PROP_TRAMO["36-59 meses"]):
    ne = (stats.norm.ppf(1 - alfa / 2) + z_b) ** 2 * 0.5 / delta ** 2; return int(np.ceil(ne * deff / resp / prop * 4))
plan27["sensibilidad_total"] = {"base": total(), "sin Bonferroni (alfa 0,05)": total(alfa=0.05), "deff 1": total(deff=1), "respuesta 100 %": total(resp=1), "delta 10 pp": total(delta=0.10), "sin restricción de tramo (prop 1)": total(prop=1)}
guardar("plan27", plan27); plan27
""")
code(r"""
json.dump(R, open("informe/resultados.json", "w"), ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
d.to_csv("informe/semillas_2026_depurado.csv", index=False)
print("Resultados guardados. Filas depuradas:", len(d))
""")

nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}, "language_info": {"name": "python"}})
nbf.write(nb, "tarea1_fernandez_joaquin.ipynb")
print("notebook escrito con", len(cells), "celdas")

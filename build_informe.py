"""Construye el informe (Markdown -> HTML -> PDF) a partir de informe/resultados.json y las figuras de informe/fig/.

Uso: python build_informe.py   (requiere haber ejecutado el cuaderno; usa google-chrome headless para el PDF)
"""
import json, subprocess, shutil, sys
from pathlib import Path
import markdown

R = json.load(open("informe/resultados.json", encoding="utf-8"))
F = lambda k: f"fig/{k}.png"

def n(x, d=1):
    """Número con coma decimal y punto de miles (es-CL)."""
    s = f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s
def pp(x, d=1): return n(x, d) + " pp"
def pct(x, d=1): return n(x, d) + " %"
def tabla(cols, filas, align=None):
    align = align or ["---"] * len(cols)
    out = ["| " + " | ".join(cols) + " |", "| " + " | ".join(align) + " |"]
    out += ["| " + " | ".join(str(c) for c in f) + " |" for f in filas]
    return "\n".join(out)

M = ["Cuaderno de Espera", "Caja de los Primeros Meses", "Maletín Explorador", "Cuentos para Conversar"]
Z = ["Norte", "Centro", "RM", "Sur"]
corto = {"cuaderno": "Cuaderno", "caja": "Caja", "maletin": "Maletín", "cuentos": "Cuentos"}
nac = {r["material"]: r for r in R["nacional"]}
pm = R["peso_mezcla"]; med = R["medianas"]; chi = R["chi2_maletin"]; p27 = R["plan27"]; fr = R["familia_resumen"]
dep = {r["regla"]: r for r in R["informe_depuracion"]}
cb = R["contrastes_b"]
uz = {(r["material"], r["macrozona"]): r for r in R["uso_zona"]}

# ----------------------------------------------------------------------------------------------- tablas con LaTeX (fuera del f-string)
T_HIP = tabla(["Pregunta", "$H_0$", "$H_1$", "Estadístico", "Efecto mínimo relevante (EMR)"], [
 ["Cobertura y uso", "La proporción de uso frecuente de cada material es igual en las cuatro macrozonas", "Difiere en al menos un par", "Test de Wald para dos proporciones, por pares, familia de 24 contrastes", "10 puntos porcentuales"],
 ["Pertinencia y valoración", "Al menos el 80 % de quienes reciben cada material lo considera pertinente ($p \\ge 0{,}80$)", "$p < 0{,}80$", "Test de Wald para una proporción, unilateral", "10 pp bajo la meta (70 %)"],
 ["Resultados", "La mediana del índice de conocimientos es igual entre quienes usan con frecuencia el Cuaderno y quienes nunca lo usan", "Difiere", "Test de permutación de la diferencia de medianas; IC bootstrap", "5 puntos del índice"],
])
T_NAC = tabla(["Material", "n recibió", "$\\hat p$ nacional", "IC 95 % (MAS)", "$\\bar m$", "$\\hat\\rho_I$", "deff", "IC 95 % con deff", "ancho MAS → deff"],
 [[r["material"], n(r["n_recibio"],0), pct(r["p_nacional"]*100), f"[{n(r['ic_mas'][0]*100)}; {n(r['ic_mas'][1]*100)}]", n(r["m_barra"]), n(r["rho_I"],3), n(r["deff"],2),
   f"[{n(r['ic_deff'][0]*100)}; {n(r['ic_deff'][1]*100)}]", f"{pp(r['ancho_mas_pp'])} → {pp(r['ancho_deff_pp'])}"] for r in R["nacional"]])
T_CB = tabla(["Material", "Contraste", "$\\hat p_1$", "$\\hat p_2$", "Diferencia", "IC 95 %", "z", "p bilateral"],
 [[r["material"], r["contraste"], pct(r["p1"]*100), pct(r["p2"]*100), pp(r["diferencia_pp"]), f"[{n(r['ic95_pp'][0])}; {n(r['ic95_pp'][1])}]", n(r["z"],2), n(r["p"],4) if r["p"] >= 0.001 else "< 0,001"] for r in cb])

# ----------------------------------------------------------------------------------------------- texto
md = []
A = md.append

A(f"""
# Evaluación del Programa Semillas: tipos de datos, visualización e inferencia

**Tarea 1 · INF396 Introducción a la Ciencia de Datos** · Joaquín Fernández · octubre de 2026

**Declaración de uso de IA.** El código del cuaderno `tarea1_fernandez_joaquin.ipynb` y la primera redacción de todas las secciones
de este informe se generaron con ayuda de Claude Code (Anthropic), a partir del enunciado y de los resultados que produce el cuaderno.
El autor revisó el código, los números y el texto, y es responsable de lo que aquí se afirma. Las conclusiones legales de la parte 6
son una lectura propia de las normas citadas, no asesoría jurídica.

## 1. Plan de análisis (preinscrito antes de abrir el archivo)

**1a. Hipótesis contrastables.** Nivel $\\alpha = 0{{,}}05$ bilateral en todos los casos.

{T_HIP}

*Por qué esos efectos.* Una brecha de 10 pp en uso frecuente entre macrozonas equivale a que, de cada diez familias que reciben el
material, una más lo deje en el cajón: es el umbral desde el cual el servicio redistribuiría acompañamiento o rediseñaría la entrega
en una zona. Una pertinencia bajo 70 % (meta 80 %) justifica rediseñar el material para la edad. Cinco puntos del índice (0-100)
es media desviación de lo que separa a un cuidador con educación básica de uno con media; menos que eso no cambia una decisión de
continuidad.

**1b. Control del error en la familia de la parte 4c.** Se aplicará **Holm** (control fuerte del error global, FWER, al 5 %). Un falso
positivo lleva al servicio a intervenir una macrozona (logística, capacitación, presupuesto) por una diferencia que no existe, y a
explicar públicamente una brecha territorial inexistente; ese costo es alto y concentrado, por lo que conviene controlar la
probabilidad de cometer *al menos un* error en la familia. Benjamini-Hochberg (FDR) se reportará como comparación, porque sería la
elección si el objetivo fuera sólo priorizar zonas para una segunda mirada.

**1c. Reglas de exclusión y corrección, fijadas antes de ver los datos.**

{tabla(["Problema", "Acción", "Regla"], [
 ["Duplicado exacto", "Se excluye", "Se conserva la primera aparición de cada fila repetida; luego se verifica que `id_cuidador` no se repita."],
 ["Valor fuera de dominio (escalas 1-5, índice 0-100, lectura 0-7, edades)", "Se marca faltante", "El registro se conserva; el valor pasa a `NaN`."],
 ["Código centinela en una numérica (p. ej. −99, 999)", "Se marca faltante", "Idem; se detecta como valor imposible y repetido."],
 ["Inconsistencia entre fechas (entrega posterior a la encuesta, fecha no interpretable)", "Se marca faltante la fecha de entrega", "No se usa en el análisis; el registro se conserva."],
 ["Variante de escritura en una categórica", "Se corrige", "Mapa a la forma canónica tras quitar tildes, mayúsculas y espacios."],
 ["Columna numérica con unidades mezcladas", "Se corrige", "Sólo si una mezcla de dos normales en escala log y el IC bootstrap del cociente de modos validan un factor de una tabla fijada de antemano (1.000 kg→g; 453,6 lb→g; 28,35 oz→g; 100; 10). Si ningún factor es compatible, se marca faltante."],
 ["Inconsistencia lógica (uso informado sin recibir; material informado en tramo no elegible)", "Se marca faltante", "Se reporta; el registro se conserva."],
])}

El plan no se modificó después. Donde el análisis se apartó de él se indica en la sección correspondiente.

## 2. Tipos de variables y depuración

**2a. Clasificación de columnas.**

{tabla(["Columna(s)", "Escala", "Estructura", "Operaciones con sentido"], [
 ["`id_cuidador`", "nominal", "identificador", "contar, unir; ninguna aritmética"],
 ["`id_centro`", "nominal", "conglomerado", "agrupar; define la unidad de muestreo y el deff"],
 ["`macrozona`, `region`, `rural`, `sexo_cuidador`, `migrante`, `pueblo_originario`", "nominal", "categórica (dicotómicas codificables 0/1)", "frecuencias y proporciones"],
 ["`tramo`, `escolaridad`", "ordinal", "categórica ordenada", "orden, mediana; promediar sólo codificada y suponiendo distancias iguales"],
 ["`uso_<m>`", "ordinal (Nunca < Ocasional < Frecuente)", "categórica ordenada", "orden, proporción por nivel; promediar no tiene sentido sin codificar"],
 ["`valoracion_<m>`", "ordinal (Likert 1-5)", "categórica ordenada", "mediana, % en 4-5; la media exige suponer equidistancia"],
 ["`recibio_<m>`, `pertinente_<m>`", "nominal", "categórica dicotómica", "proporción"],
 ["`edad_meses`, `semanas_gestacion`, `peso_nacimiento`, `edad_cuidador`", "razón", "numérica", "media, mediana, diferencias y cocientes (peso exige unidad única)"],
 ["`n_hijos`, `lectura_semana`", "razón (conteo)", "numérica discreta", "media, mediana; `lectura_semana` está acotada en 0-7"],
 ["`indice_conocimientos`", "intervalo (0-100)", "numérica", "media, mediana, diferencias; los cocientes no tienen sentido"],
 ["`fecha_entrega`, `fecha_encuesta`", "intervalo (fecha)", "fecha; cíclica en día de semana o mes", "diferencias entre fechas; no se promedian sin convertir"],
])}

**2b. Vacío estructural vs. dato faltante.** Un cuidador es elegible para un material si su tramo es el de entrega o uno posterior;
las columnas de `uso`, `valoracion` y `pertinente` exigen además haber recibido el material. Sobre el archivo crudo
({n(R['n_crudo'],0)} filas) se obtiene:

{tabla(["Material", "Elegibles", "`recibio`: vacío estructural", "`recibio`: faltante", "`uso`/`valoracion`/`pertinente`: vacío estructural", "faltantes en `uso` / `valoracion` / `pertinente`"],
 [[r["material"], n(r["elegibles"],0), n(r["recibio: vacío estructural"],0), r["recibio: faltante"], n(r["uso/valoracion/pertinente: vacío estructural"],0),
   f"{r['uso: faltante']} / {r['valoracion: faltante']} / {r['pertinente: faltante']}"] for r in R["vacios"]])}

Todo vacío de las columnas de materiales es estructural (no elegible o no recibió). El dato faltante real está en otras columnas:
`escolaridad` ({R['esc_na']} tras depurar) y, una vez convertidos los centinelas, `indice_conocimientos` ({dep['indice_conocimientos: código centinela -99']['registros']}).

**2c. Depuración declarativa.** Cada regla es una función del archivo crudo que devuelve las filas que la violan y una acción;
el bloque produce el informe y el conjunto depurado sin corrección manual (celdas «Reglas declarativas» del cuaderno). Resultado:
**{n(R['n_crudo'],0)} → {n(R['n_depurado'],0)} filas**, exactamente el diseño (120/120/150/210 por macrozona; se verifica con un `assert`).

{tabla(["Regla", "Acción", "Registros"], [[r["regla"], r["acción"], r["registros"]] for r in R["informe_depuracion"] if r["registros"] > 0] +
      [["Otras 15 reglas (id repetido, región fuera de su macrozona, índice fuera de 0-100, edad fuera de tramo, semanas de gestación, lectura 0-7, edad del cuidador, uso informado sin recibir, material en tramo no elegible, fecha no interpretable)", "—", "0"]])}

*Unidades mezcladas en `peso_nacimiento`.* En escala $\\log_{{10}}$ el peso tiene dos modas (figura 1). Una mezcla de dos normales
ajustada por EM da componentes con modas {n(pm['modas_g'][0],2)} y {n(pm['modas_g'][1],0)} (pesos {pct(pm['pesos'][0]*100)} y
{pct(pm['pesos'][1]*100)}) y un **cociente de modas de {n(pm['cociente_modos'])}, con IC bootstrap del 95 % [{n(pm['ic95_cociente'][0])}; {n(pm['ic95_cociente'][1])}]**
({500} réplicas). De la tabla de factores fijada en 1c, el único compatible con el intervalo es **kg → g (1.000)**; 453,6 y 28,35
quedan fuera. Por eso los {dep[[k for k in dep if k.startswith('peso')][0]]['registros']} valores del componente bajo (umbral de decisión de la mezcla:
{n(pm['umbral_g'],0)} g) se multiplican por 1.000. La inspección («parecen kilos») sólo sugiere; el intervalo del cociente es lo que
autoriza el factor. Tras corregir, el peso queda en 1.520-4.833 g, con una sola moda.

![Figura 1. Mezcla de dos normales del peso al nacer en escala log10.]({F('f00_peso_mezcla')}){{: .fig-s }}

**2d. Faltantes en `escolaridad`.** Faltan {R['esc_na']} valores ({pct(R['esc_na']/R['n_depurado']*100)}). Si el mecanismo fuera completamente
aleatorio (MCAR), la tasa de faltante sería la misma en todo subgrupo. No lo es: falta en el {pct(R['esc_na_tasa']['rural']['Rural'])} de los
rurales y en el {pct(R['esc_na_tasa']['rural']['Urbano'])} de los urbanos ($\\chi^2$ = {n(R['esc_na_tablas']['rural']['chi2'])}, gl = 1,
p < 0,001); por macrozona va de {pct(R['esc_na_tasa']['macrozona']['RM'])} en RM a {pct(R['esc_na_tasa']['macrozona']['Sur'])} en Sur
($\\chi^2$ = {n(R['esc_na_tablas']['macrozona']['chi2'])}, gl = 3, p < 0,001). Entre los registros sin escolaridad el
{pct(R['esc_na_tablas']['rural']['pct']['sin escolaridad']['Rural'])} es rural y el {pct(R['esc_na_tablas']['macrozona']['pct']['sin escolaridad']['Sur'])} es del Sur,
frente a {pct(R['esc_na_tablas']['rural']['pct']['con escolaridad']['Rural'])} y {pct(R['esc_na_tablas']['macrozona']['pct']['con escolaridad']['Sur'])} entre los
que sí la tienen. El mecanismo depende de variables observadas (al menos MAR, no MCAR). Imputar por la moda («Media») asignaría
educación media a cuidadores que son desproporcionadamente rurales y del Sur, donde la escolaridad básica es más frecuente: inflaría
la categoría modal, reduciría la varianza y sesgaría hacia arriba la escolaridad de esos grupos, atenuando la relación
escolaridad-índice. Si necesitara la variable completa usaría imputación múltiple (o, al menos, imputación por regresión/modelo
condicionada a `rural`, `macrozona`, `tramo`, `indice_conocimientos` y `lectura_semana`), reportando la varianza entre imputaciones;
para las tablas de este informe simplemente se excluye el faltante y se declara.

## 3. Análisis exploratorio y visualización

**3a. Estructura de la muestra.** Coincide con el diseño: 600 por macrozona, 120/120/150/210 por tramo.

{tabla(["Tramo"] + Z + ["Total"], [[r["tramo"]] + [r[z] for z in Z] + [r["Total"]] for r in R["estructura"]] + [["**Total**"] + ["600"]*4 + ["2.400"]])}

Cuidadores que evalúan cada material: Cuaderno {n(R['evaluan'][M[0]],0)}, Caja {n(R['evaluan'][M[1]],0)}, Maletín {n(R['evaluan'][M[2]],0)},
Cuentos {n(R['evaluan'][M[3]],0)} (elegibles por tramo). Recibieron el material: {n(nac[M[0]]['n_recibio'],0)}, {n(nac[M[1]]['n_recibio'],0)},
{n(nac[M[2]]['n_recibio'],0)} y {n(nac[M[3]]['n_recibio'],0)}; es decir, cobertura nacional (promedio de macrozonas) de
{pct(R['cobertura'][0]['nacional'])}, {pct(R['cobertura'][1]['nacional'])}, {pct(R['cobertura'][2]['nacional'])} y {pct(R['cobertura'][3]['nacional'])}.

**3b. Figura principal.**

![Figura 2. Uso frecuente por material y macrozona, con IC de Wald 95 % (MAS).]({F('f01_principal_uso_frecuente')})

*Canales.* La variable que se compara (proporción de uso frecuente) va a la **posición en una escala común** (eje vertical, el canal más
preciso en la jerarquía de Cleveland y McGill); la macrozona va a la **posición en el eje horizontal** dentro de cada panel, y el
material a las **facetas**, de modo que cada comparación entre macrozonas se hace dentro de un panel con el mismo eje. El intervalo se
codifica con **longitud** (barra de error), el siguiente canal en precisión. No se usa el color para codificar datos: todo se lee en
escala de grises. No se usó un gráfico de torta porque obligaría a juzgar **ángulos y áreas** (los canales menos precisos) y además no
admite intervalos de confianza; no se usaron barras apiladas porque sólo el segmento inferior tiene una base común: los demás se
comparan por **longitud sin alineación**, y cuatro materiales con distinto denominador (quienes lo recibieron) no suman nada
interpretable.

![Figura 3. Versión deliberadamente mala del mismo contenido.]({F('f02_mala')}){{: .fig-s }}

*Qué hace mala a la figura 3.* Apila proporciones con distinto denominador (la suma «{n(sum(uz[(m, 'Norte')]['p_frec']*100 for m in ['cuaderno','caja','maletin','cuentos']),0)} %» no
significa nada); el eje parte en 150, lo que exagera la diferencia entre Sur y el resto; las barras de arriba no comparten base y no se
pueden comparar; usa la paleta *jet*, que en escala de grises es indistinguible y cuyo brillo no es monótono; no hay intervalos, el
título es «uso» y los ejes no tienen rótulo ni unidad.

**3c. Índice de conocimientos por escolaridad y por tramo.**

{tabla(["Escolaridad", "n", "Q1", "Mediana", "Q3", "Media"], [[r["escolaridad"], n(r["n"],0), n(r["Q1"]), n(r["mediana"]), n(r["Q3"]), n(r["media"])] for r in R["indice_por_escolaridad"]])}

{tabla(["Tramo", "n", "Q1", "Mediana", "Q3", "Media"], [[r["tramo"], n(r["n"],0), n(r["Q1"]), n(r["mediana"]), n(r["Q3"]), n(r["media"])] for r in R["indice_por_tramo"]])}

![Figura 4. Distribución del índice por escolaridad y por tramo (cajas, media y puntos).]({F('f03_indice_boxplot')})

La mediana sube monótonamente con la escolaridad ({n(R['indice_por_escolaridad'][0]['mediana'])} → {n(R['indice_por_escolaridad'][3]['mediana'])}) y
con el tramo ({n(R['indice_por_tramo'][0]['mediana'])} → {n(R['indice_por_tramo'][3]['mediana'])}); los rangos intercuartílicos son parecidos
(18-20 puntos), así que las distribuciones se desplazan sin cambiar mucho de dispersión. La forma es aproximadamente simétrica
(asimetría global {n(R['indice_asimetria'],2)}), con cola corta hacia abajo (mínimos de 16-38) y techo en 100 que recorta levemente la cola
superior en los grupos altos. Los valores extremos son pocos y plausibles, no errores. Como media y mediana casi coinciden en cada grupo,
la media es un resumen apropiado para describir y comparar; la mediana se mantiene en la parte 4e porque es robusta al techo de la escala.

**3d. Lectura semanal e índice.**

![Figura 5. Lectura semanal vs. índice: jitter con transparencia y mediana por día (izq.) y hexbin (der.).]({F('f04_lectura_indice')})

`lectura_semana` toma ocho valores, de modo que un diagrama de dispersión crudo apila cientos de puntos en ocho columnas. Se resolvió
con **jitter horizontal, transparencia y la mediana por día** (izquierda) y con **densidad en celdas hexagonales** (derecha). La relación
es positiva y monótona: la mediana del índice pasa de {n(R['lectura_indice']['mediana_por_dia']['0.0'])} con 0 días a
{n(R['lectura_indice']['mediana_por_dia']['7.0'])} con 7 días ($\\rho$ de Spearman = {n(R['lectura_indice']['spearman'],2)}, n = {n(R['lectura_indice']['n'],0)}), con mucha
dispersión dentro de cada día.

**3e. Uso frecuente del Cuaderno e índice: toda la muestra y por escolaridad.**

{tabla(["Estrato", "n frecuente", "Media frecuente", "n no frecuente", "Media no frecuente", "Diferencia", "% con uso frecuente"],
 [[r["estrato"], n(r["n frecuente"],0), n(r["media frecuente"]), n(r["n no frecuente"],0), n(r["media no frecuente"]), n(r["diferencia"]), pct(r["% uso frecuente"])] for r in R["simpson"]])}

![Figura 6. Media del índice según uso del Cuaderno, por escolaridad.]({F('f05_simpson')}){{: .fig-s }}

En toda la muestra la diferencia es de {n(R['simpson'][0]['diferencia'])} puntos, pero dentro de cada nivel de escolaridad es menor
({n(min(r['diferencia'] for r in R['simpson'][1:]))} a {n(max(r['diferencia'] for r in R['simpson'][1:]))}). Es **confusión por escolaridad**: la escolaridad determina
a la vez el uso (uso frecuente del {pct(R['simpson'][1]['% uso frecuente'])} en básica al {pct(R['simpson'][4]['% uso frecuente'])} en universitaria) y el índice
(medianas de {n(R['indice_por_escolaridad'][0]['mediana'])} a {n(R['indice_por_escolaridad'][3]['mediana'])}). Al comparar usuarios frecuentes con el resto en la
muestra completa se compara, en parte, cuidadores más escolarizados con menos escolarizados, y una fracción de la brecha es de la
escolaridad, no del material. Aquí la confusión atenúa sin invertir el signo; la paradoja de Simpson es el caso extremo en que el signo
dentro de los estratos es contrario al global. La lectura honesta de la asociación es la diferencia dentro de estratos (unos 5 puntos),
que es justo el EMR declarado.

**3f. Matriz de correlaciones.**

![Figura 7. Correlaciones entre codificaciones y variables numéricas, reordenadas por agrupamiento jerárquico.]({F('f06_correlaciones')}){{: .fig-m }}

Se codificó uso frecuente como 0/1 por material, `escolaridad` como 1-4 y `rural` como 0/1. El coeficiente depende de la escala del par:
**Spearman** cuando interviene una ordinal (escolaridad, valoraciones), porque sólo el orden es interpretable y la codificación 1-4 no
garantiza equidistancia ({R['corr_metodos']['Spearman']} pares); **Pearson** entre numéricas y con binarias ({R['corr_metodos']['Pearson']} pares), donde
coincide con el punto-biserial (numérica-binaria) y con $\\phi$ (binaria-binaria). El reordenamiento (enlace promedio sobre la distancia
$1-|r|$) deja ver tres bloques: (i) cada indicador de uso frecuente con la valoración del mismo material ($r_s$ = 0,32-0,37) y con
`lectura_semana` (0,29-0,31); (ii) `escolaridad`, `lectura_semana` e `indice_conocimientos` ({n(R['corr_top'][0]['r'],2)} entre escolaridad e índice),
con `rural` en negativo (−0,21 con escolaridad); (iii) las demográficas del niño y del cuidador (`peso_nacimiento`, `edad_cuidador`,
`n_hijos`), prácticamente incorrelacionadas con todo. Ninguna correlación supera 0,40: las asociaciones son reales pero modestas.

## 4. Inferencia

**4a. Proporción nacional de uso frecuente, correlación intraclase y efecto de diseño.** La estimación nacional promedia las cuatro
macrozonas con peso igual, $\\hat p = \\frac14\\sum_z \\hat p_z$, con $\\mathrm{{EE}} = \\frac14\\sqrt{{\\sum_z \\hat p_z(1-\\hat p_z)/n_z}}$. Si
las macrozonas tuvieran pesos poblacionales distintos (la RM concentra cerca del 40 % de los nacimientos), el promedio ponderado se
movería hacia el valor de la RM y el error estándar cambiaría según $\\sum_z w_z^2 \\mathrm{{Var}}(\\hat p_z)$. El ICC se estima con el
ANOVA de un factor sobre el indicador 0/1 entre quienes recibieron el material, $\\hat\\rho_I = (CMB-CMD)/(CMB+(\\bar m-1)CMD)$, y
$\\mathrm{{deff}} = 1+(\\bar m-1)\\hat\\rho_I$. El deff multiplica la varianza, así que el error estándar se multiplica por $\\sqrt{{\\mathrm{{deff}}}}$
(interpreto así el enunciado). Ningún $\\hat\\rho_I$ resultó negativo; podría ocurrir porque el estimador ANOVA es una diferencia de cuadrados
medios: si los centros son *más* homogéneos entre sí de lo que daría el azar (CMB < CMD), la diferencia es negativa aunque el parámetro sea
$\\ge 0$, y se trunca en cero.

{T_NAC}

Cerca de la mitad de las familias que reciben un material lo usa con frecuencia ({pct(nac[M[2]]['p_nacional']*100,0)} el Maletín,
{pct(nac[M[1]]['p_nacional']*100,0)} la Caja). El ICC es pequeño (0,04-0,05) pero, con 10 a 18 cuidadores por centro, el deff llega a
{n(nac[M[0]]['deff'],2)} para el Cuaderno: los intervalos se ensanchan entre {pct((nac[M[3]]['ancho_deff_pp']/nac[M[3]]['ancho_mas_pp']-1)*100,0)} (Cuentos, pocos
cuidadores por centro) y {pct((nac[M[0]]['ancho_deff_pp']/nac[M[0]]['ancho_mas_pp']-1)*100,0)} (Cuaderno). El muestreo por conglomerados cuesta el
equivalente a perder entre un 20 % y un 45 % de la muestra.

**4b. Dos contrastes puntuales (Wald, dos proporciones, sin corrección por conglomerados).**

{T_CB}

*Cuaderno, RM vs. Norte:* la diferencia de {pp(cb[0]['diferencia_pp'])} no es significativa (p = {n(cb[0]['p'],2)}) y el intervalo incluye tanto
el cero como el EMR de 10 pp: el estudio no puede afirmar ni descartar una brecha relevante; es un resultado **no concluyente**, no una
igualdad. *Cuentos, Centro vs. Sur:* {pp(cb[1]['diferencia_pp'])} con p < 0,001; la estimación duplica el EMR, pero el intervalo
[{n(cb[1]['ic95_pp'][0])}; {n(cb[1]['ic95_pp'][1])}] es ancho (n = 210 por macrozona de diseño, {uz[('cuentos','Centro')]['n_recibio']} y {uz[('cuentos','Sur')]['n_recibio']} que recibieron) e incluye
valores apenas sobre el EMR: es significativa y probablemente relevante, con magnitud mal determinada. Sin corregir por conglomerados ni
por multiplicidad, ambos valores p son optimistas (ver 4a y 4c).

**4c. Las 24 comparaciones como una familia.** Valores p ordenados; Holm fue la corrección declarada, BH la alternativa.

{tabla(["#", "Material", "Par", "Dif. (pp)", "IC 95 % (pp)", "p", "p Holm", "p BH", "Holm", "BH"],
 [[r["rango"], r["material"].split(" ")[0], r["par"], n(r["dif_pp"]), f"[{n(r['ic_lo_pp'])}; {n(r['ic_hi_pp'])}]", n(r["p"],4) if r["p"] >= 0.0001 else "< 0,0001",
   n(min(r["p_holm"],1),4), n(r["p_BH"],4), "sí" if r["Holm"] else "no", "sí" if r["BH"] else "no"] for r in R["familia"]])}

Sin corrección «sobreviven» {fr['sin_corregir']} contrastes; con Holm, {fr['holm']}; con BH, {fr['bh']}: **Cuentos para Conversar, Sur frente a Norte y frente
a Centro** (unos 20 pp menos de uso frecuente en el Sur). Holm compara el $i$-ésimo valor p ordenado con $\\alpha/(m-i+1)$, que parte en
{n(fr['umbral_holm_primero'],5)} y crece lentamente; BH lo compara con $i\\alpha/m$, que crece linealmente ({n(fr['umbral_bh_ultimo_rechazado'],5)} para $i$ = 2,
{n(3*0.05/24,5)} para $i$ = 3). BH es más permisivo porque tolera que una fracción de los rechazos sea falsa; aquí ambos coinciden
porque hay un vacío entre los dos valores p muy pequeños (< 0,001) y el tercero (0,012), que no pasa ni el umbral de BH para $i$ = 3.
Las diferencias de 6-8 pp en Cuaderno y Caja que eran «significativas» sin corregir son el tipo de hallazgo que la familia de 24
contrastes produce por azar: uno o dos falsos positivos esperados a $\\alpha$ = 0,05.

**4d. Independencia entre uso (tres niveles) y macrozona para el Maletín Explorador.** Entre los {n(sum(r['Nunca']+r['Ocasional']+r['Frecuente'] for r in chi['tabla']),0)} que lo recibieron:

{tabla(["Macrozona", "Nunca", "Ocasional", "Frecuente", "% Nunca", "% Ocasional", "% Frecuente"],
 [[t["macrozona"], t["Nunca"], t["Ocasional"], t["Frecuente"], pct(p["Nunca"]), pct(p["Ocasional"]), pct(p["Frecuente"])] for t, p in zip(chi["tabla"], chi["pct_fila"])])}

$\\chi^2$ = {n(chi['chi2'],2)}, gl = {chi['gl']}, p = {n(chi['p'],2)} (mínimo esperado {n(chi['min_esperado'],0)}, condiciones del test holgadas). No hay evidencia
de que la distribución del uso dependa de la macrozona, lo que coincide con las seis comparaciones por pares del Maletín, ninguna
significativa ni siquiera sin corregir (diferencias de 0,5 a 4,6 pp). El $\\chi^2$ usa los tres niveles a la vez y un solo test, por lo que
no necesita corrección por multiplicidad; los pares sólo miran «frecuente vs. resto».

**4e. Diferencia de medianas del índice: uso frecuente vs. nunca del Cuaderno.** Mediana {n(med['mediana_frecuente'])} (n = {n(med['n_frecuente'],0)})
frente a {n(med['mediana_nunca'])} (n = {med['n_nunca']}): **diferencia {n(med['dif'])} puntos, IC bootstrap de percentiles 95 % [{n(med['ic_boot'][0])}; {n(med['ic_boot'][1])}]**
({n(med['B_boot'],0)} réplicas); test de permutación con {n(med['B_perm'],0)} permutaciones: p = {n(med['p_perm'],4)} (ninguna permutación alcanzó la
diferencia observada). La diferencia es estadísticamente clara y supera el EMR de 5 puntos. Aun así **no es el efecto del material**: los
cuidadores no fueron asignados al uso, lo eligieron, y la **escolaridad** (parte 3e) determina a la vez quién usa el Cuaderno y cuánto sabe
de crianza; la comparación mezcla el efecto del material con el de ser un cuidador más escolarizado (y, por la misma vía, más lector y de
zona urbana). Dentro de estratos de escolaridad la diferencia baja a unos 5 puntos, y puede haber confusores no medidos (interés previo
en la crianza, apoyo del centro de salud). Para estimar el efecto haría falta un diseño con asignación controlada: un ensayo
aleatorizado del acompañamiento al uso (por centros de salud, con el mismo deff en mente) o, si no se puede negar el material, un
escalonamiento aleatorio de la entrega (*stepped wedge*) o una regresión en discontinuidad sobre la fecha de inicio del programa, con medición
previa del índice.

**4f. Hipótesis preinscritas.** H1 (uso igual entre macrozonas) se rechaza sólo para Cuentos (4c); H3 se rechaza (4e). Para H2 (pertinencia
$\\ge$ 80 %): Cuaderno {pct(R['pertinencia'][0]['pertinente_%'])}, Caja {pct(R['pertinencia'][1]['pertinente_%'])}, Maletín {pct(R['pertinencia'][2]['pertinente_%'])},
Cuentos {pct(R['pertinencia'][3]['pertinente_%'])}; los valores unilaterales p son {n(R['pertinencia'][0]['p_unilateral'],3)}, {n(R['pertinencia'][1]['p_unilateral'],2)},
{n(R['pertinencia'][2]['p_unilateral'],3)} y {n(R['pertinencia'][3]['p_unilateral'],2)}. Cuaderno y Maletín quedan 1,5 y 2,2 pp bajo la meta, significativo al 5 % pero
muy lejos del EMR de 10 pp: estadísticamente «bajo 80 %», irrelevante para una decisión. La valoración mediana es 4 en los cuatro
materiales (68-71 % los califica 4 o 5).

## 5. Potencia y tamaño de la muestra

Se usan los tamaños de **diseño**. Lo que se pierde por no recepción: con los n que efectivamente recibieron cada material, el margen
nacional sube de 2,0 % a {pct(R['margen_recibidos'][M[0]]['margen MAS'])} (Cuaderno, n = {n(R['margen_recibidos'][M[0]]['n_recibio'],0)}) y de 3,4 % a
{pct(R['margen_recibidos'][M[3]]['margen MAS'])} (Cuentos, n = {R['margen_recibidos'][M[3]]['n_recibio']}), antes del deff.

**5a. Margen de error del 95 % con p = 0,5** ($1{{,}}96\\sqrt{{0{{,}}25/n}}$, por $\\sqrt{{\\mathrm{{deff}}}}$ en la segunda columna; deff = {n(R['deff_max'],2)}
(el mayor, Cuaderno) para las cifras nacionales y por macrozona, {n(R['deff']['cuentos'],2)} para Cuentos).

{tabla(["Estimación", "n", "Margen MAS", "Margen con deff", "Cumple 3,5 % (MAS / deff)"],
 [[r["estimación"], n(r["n"],0), pct(r["margen MAS (pp)"],2), pct(r["margen con deff (pp)"],2), ("sí" if r["cumple 3,5 % (MAS)"] else "no") + " / " + ("sí" if r["cumple 3,5 % (deff)"] else "no")] for r in R["margenes"]])}

El estudio cumple el 3,5 % **sólo para las cifras nacionales de los materiales que evalúa toda la muestra** (2,0 % bajo MAS, 2,7 % con
deff). Para Cuentos lo cumple apenas bajo MAS (3,4 %) y lo incumple con deff (3,8 %). Por macrozona no lo cumple en ningún caso (4,0 %
y 5,3 %), y mucho menos para Cuentos por macrozona (6,8-7,5 %). Las bases pedían el 3,5 % «por material» a nivel nacional: se cumple
para tres de cuatro materiales y se incumple en Cuentos si se reconoce el conglomerado.

**5b. Diferencia mínima detectable** (potencia 0,80, $\\alpha$ = 0,05 bilateral, p = 0,5): $\\delta = (z_{{0{{,}}975}}+z_{{0{{,}}80}})\\sqrt{{2\\cdot 0{{,}}25\\,\\mathrm{{deff}}/n}}$.

{tabla(["Contraste", "n por grupo", "DMD bajo MAS", "DMD con deff"], [[r["contraste"], r["n por grupo"], pp(r["DMD MAS (pp)"]), pp(r["DMD con deff (pp)"])] for r in R["dmd"]])}

Frente al EMR de 10 pp declarado en 1a: para los materiales de toda la muestra el estudio podía detectar 10 pp bajo MAS (DMD 8,1 pp)
pero queda justo por encima con el deff del Cuaderno (10,8 pp); para Cuentos **no** (13,7 y 15,2 pp). Esto explica 4b: la brecha de
{pp(cb[1]['diferencia_pp'],0)} en Cuentos se detectó por ser el doble de la DMD, mientras que una brecha de 10 pp en Cuentos tendría apenas un 40-50 % de
probabilidad de detectarse. El estudio no fue capaz, en general, de detectar las diferencias que declaré relevantes entre macrozonas.

**5c. Seguimiento 2027.** Objetivo: 5 pp entre cualquier par de macrozonas, potencia 0,80, $\\alpha$ = 0,05/6 por contraste
($z$ = {n(p27['z_alfa_bonf'],3)}), p = 0,5, deff 1,5, respuesta 80 %, elegibilidad por tramo y proporciones 20/20/25/35. La restricción la
impone **Cuentos**, evaluado sólo por el tramo 36-59 meses. Por macrozona: $n_{{\\text{{ef}}}} = (z_{{\\alpha/12}}+z_{{0{{,}}80}})^2\\cdot 0{{,}}5/0{{,}}05^2$ =
**{n(p27['n_efectivo'],0)}** respondentes efectivos en ese tramo; × 1,5 = {n(p27['n_respondentes_36_59'],0)} respondentes; ÷ 0,8 = **{n(p27['n_contactar_36_59'],0)} a contactar
en el tramo 36-59 por macrozona**. Como ese tramo es el 35 % del diseño, la macrozona completa son {n(p27['total_por_zona'],0)} contactos
(gestantes {n(p27['por_tramo_por_zona']['Gestante'],0)}, 0-11 meses {n(p27['por_tramo_por_zona']['0-11 meses'],0)}, 12-35 meses {n(p27['por_tramo_por_zona']['12-35 meses'],0)},
36-59 meses {n(p27['por_tramo_por_zona']['36-59 meses'],0)}) y el **total nacional {n(p27['total_nacional'],0)} cuidadores a contactar** (unas 21 veces el estudio de 2025).
Verificación por simulación (20.000 réplicas de dos binomiales con $n_{{\\text{{ef}}}}$ = {n(p27['n_efectivo'],0)}, p = 0,50 vs. 0,55, test de Wald a $\\alpha$/6):
potencia **{n(p27['potencia_simulada']*100)} %**.

Es impracticable para un servicio público. Lo que más lo encarece es la **diferencia objetivo**: 5 pp entra al cuadrado, y pasar a
10 pp bajaría el total a {n(p27['sensibilidad_total']['delta 10 pp'],0)}; le sigue la **regla de elegibilidad** (sólo el 35 % de cada macrozona evalúa Cuentos, se
contactan 2,9 cuidadores por cada uno útil: sin esa restricción serían {n(p27['sensibilidad_total']['sin restricción de tramo (prop 1)'],0)}); Bonferroni, el deff y la
no respuesta pesan menos (sin cada uno: {n(p27['sensibilidad_total']['sin Bonferroni (alfa 0,05)'],0)}, {n(p27['sensibilidad_total']['deff 1'],0)} y
{n(p27['sensibilidad_total']['respuesta 100 %'],0)}). Con **4.000 contactados** (1.000 por macrozona, 800 respuestas, $n_{{\\text{{ef}}}}$ = {n(p27['con_4000']['n_eff_todos'],0)} para
los materiales de toda la muestra y {n(p27['con_4000']['n_eff_cuentos'],0)} para Cuentos) la diferencia detectable con la misma potencia y Bonferroni es de
**{pp(p27['con_4000']['dmd_todos_pp'],0)} entre macrozonas para Cuaderno, Caja y Maletín, y de {pp(p27['con_4000']['dmd_cuentos_pp'],0)} para Cuentos**; para detectar
5 pp la potencia sería {pct(p27['con_4000']['potencia_sim_todos_delta_obj']*100,0)} y {pct(p27['con_4000']['potencia_sim_cuentos_delta_obj']*100,0)}. Una alternativa
sensata es sobremuestrear el tramo 36-59 (en vez de replicar el 35 %) y aceptar 10 pp como objetivo.

**5d. Para una autoridad sin formación estadística.** El *margen de error* dice cuánto puede alejarse una cifra de la encuesta del valor
real por haber preguntado a una muestra y no a todos: «48 % ± 2 %» significa que el verdadero uso frecuente está, con alta confianza,
entre 46 % y 50 %. Pero comparar dos regiones es otra pregunta: cada una trae su propio margen, y la diferencia entre ambas se mide con
peor precisión que cada cifra por separado, y cada región usa sólo una cuarta parte de la muestra. La *potencia* es la
probabilidad de que el estudio detecte una diferencia que sí existe; con 600 casos por región, una brecha de 4 puntos se detectaría
menos de una de cada tres veces. Y cuando se comparan muchas regiones a la vez (seis pares por material, veinticuatro en total), alguna
diferencia parecerá «significativa» por puro azar; por eso se exige un estándar más alto a cada comparación (*error global*) que el que
bastaría para una sola (*error por estrato*). Un estudio con «error del 2 %» en la cifra nacional no puede, entonces, afirmar que dos
regiones difieren en 4 puntos.

## 6. Marco legal de los datos

**6a. Datos personales y sensibles; seudonimización y minimización.** Bajo la Ley 19.628 (art. 2, letra f) es dato personal toda
información sobre una persona natural identificada o identificable; la Ley 21.719, vigente desde el 1 de diciembre de 2026, mantiene
esa definición y amplía la de dato sensible (art. 2, letra g) a origen étnico o racial, situación socioeconómica, datos de salud y
otros. En el archivo son **datos personales** `id_cuidador` (seudónimo, pero identificador), `id_centro`, `region`, `rural`,
`sexo_cuidador`, `edad_cuidador`, `escolaridad`, `n_hijos` y las dos fechas, porque combinados permiten identificar a un cuidador en un
centro de salud concreto (cuasi-identificadores). Son **datos sensibles** `pueblo_originario` (origen étnico), `peso_nacimiento`,
`semanas_gestacion` y `edad_meses` (datos de salud del niño o niña y de la gestante), y `escolaridad` como indicador de situación
socioeconómica (21.719). `migrante` no figura literalmente en el listado, pero por su riesgo de discriminación lo trataría como sensible.
Que los datos describan a **menores de edad** añade el interés superior de la niñez (Ley 21.430, art. 7) y, en la 21.719, un estándar
reforzado de licitud y de consentimiento del representante. Antes de entregar la base a terceros: reemplazar `id_cuidador` por un código
aleatorio con tabla de correspondencia bajo custodia separada; recodificar o suprimir `id_centro`; reducir `region` a `macrozona`;
llevar las fechas a mes; agrupar `edad_cuidador`, `edad_meses` y `peso_nacimiento` en tramos y `n_hijos` a «3 o más»; entregar
`migrante` y `pueblo_originario` sólo bajo convenio con fines estadísticos; y entregar únicamente las columnas necesarias para el
análisis solicitado (minimización), con registro de accesos y prohibición contractual de reidentificar.

**6b. Solicitud de un medio por la Ley 20.285.** El principio de transparencia obliga a entregar la información que obra en poder del
servicio (arts. 5 y 10), y el informe, las bases de licitación, la metodología, el cuestionario y los tabulados agregados son
públicos sin discusión. La base completa no: el art. 21 N.º 2 permite denegar cuando la publicidad afecta derechos de terceros, en
particular la esfera de la vida privada y los datos sensibles, y el art. 21 N.º 5 remite a los secretos establecidos por leyes de quórum
calificado, entre ellos el **secreto estadístico** que la Ley 17.374 (art. 29) impone a los datos individuales recogidos por el Sistema
Estadístico Nacional, que no pueden divulgarse de forma que permita identificar a las personas. Lo que sí construiría es un **archivo de
uso público**: sin `id_cuidador` ni `id_centro`, `region` sustituida por `macrozona`, fechas a trimestre, edades y peso en tramos,
`n_hijos` con tope, supresión o agregación de las celdas que dejen menos de un umbral de casos (por ejemplo, $k \\ge 5$ en el cruce
macrozona × tramo × rural × escolaridad), eliminación de las columnas de migrante y pueblo originario o su entrega sólo agregada, y una
pequeña perturbación de los valores continuos. Así se conservan las proporciones y los intervalos del informe y se impide reconstruir
quién respondió. El medio recibiría ese archivo con la documentación de los cambios, más el derecho a pedir tabulados adicionales.

**6c. Consentimiento informado.** Sí lo requiere. Quien responde es el cuidador adulto y consiente por sí mismo sobre sus propios
datos (19.628 art. 4; 21.719 exige consentimiento libre, informado, específico e inequívoco) y, como representante, sobre los datos del
niño o niña. La Ley 21.430 obliga a decidir en función del interés superior del niño (art. 7), reconoce su autonomía progresiva y su
derecho a ser oído y a la vida privada y la protección de sus datos: en la práctica, informar en lenguaje claro qué se pregunta, para
qué, quién accederá y por cuánto tiempo, hacer explícito que negarse no afecta la entrega de los materiales ni la atención del centro, y
permitir revocar. Los niños mayores (3-5 años) no participan directamente, pero su información se trata con el mismo estándar. En cuanto a
la Ley 20.120, su objeto es la investigación científica en seres humanos en el ámbito biomédico, con intervención sobre las personas y
revisión por comités ético-científicos acreditados; una evaluación de programa social basada en una encuesta a adultos, sin intervención
ni procedimiento sobre las personas, queda a mi juicio fuera de su ámbito estricto. Aun así, la buena práctica (y la exigencia de la
Dipres para estudios con población vulnerable) es someter el protocolo y el consentimiento a un comité de ética, sobre todo porque se
recogen datos de salud de menores.
""")

texto = "\n".join(md)
Path("informe/informe.md").write_text(texto, encoding="utf-8")

CSS = """
@page { size: A4; margin: 17mm 16mm 16mm 16mm; }
body { font-family: "DejaVu Serif", Georgia, serif; font-size: 9.6pt; line-height: 1.3; color: #111; }
h1 { font-size: 15pt; margin: 0 0 4pt 0; } h2 { font-size: 12pt; margin: 11pt 0 4pt 0; border-bottom: 1px solid #999; }
p { margin: 3pt 0 5pt 0; text-align: left; }
table { border-collapse: collapse; font-size: 7.8pt; margin: 4pt auto 6pt auto; font-family: "DejaVu Sans", Arial, sans-serif; }
th, td { border: 1px solid #bbb; padding: 1.5pt 4pt; vertical-align: top; } th { background: #eee; }
img { display: block; margin: 4pt auto 2pt auto; max-width: 100%; }
p:has(> img) { page-break-inside: avoid; margin: 4pt 0; }
img.fig-s { max-width: 60%; } img.fig-m { max-width: 76%; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 8pt; }
"""
html = markdown.markdown(texto, extensions=["tables", "attr_list"])
# el markdown deja la figura dentro de <p>; mover la clase al párrafo para controlar el ancho
# fórmulas LaTeX: se renderizan con MathJax al imprimir
pagina = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Tarea 1 INF396</title><style>{CSS}</style>
<script>window.MathJax = {{ tex: {{ inlineMath: [['$', '$']] }}, startup: {{ typeset: true }} }};</script>
<script id="MathJax-script" src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
</head><body>{html}</body></html>"""
Path("informe/informe.html").write_text(pagina, encoding="utf-8")

chrome = shutil.which("google-chrome") or shutil.which("chromium")
if chrome:
    subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=15000", "--no-pdf-header-footer",
                    "--print-to-pdf=tarea1_fernandez_joaquin.pdf", str(Path("informe/informe.html").resolve())], check=True, capture_output=True)
    from pypdf import PdfReader
    print("PDF escrito: tarea1_fernandez_joaquin.pdf,", len(PdfReader("tarea1_fernandez_joaquin.pdf").pages), "páginas")
else:
    print("sin Chrome: queda informe/informe.html", file=sys.stderr)

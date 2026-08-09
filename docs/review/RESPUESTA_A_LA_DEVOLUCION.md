# Respuesta a la evaluación biológica de MLOsMetaDB

**Fecha:** 2026-08-09 · **Responde a:** `docs/review/devolucion/BIOLOGY_EVALUATION.md`
**Estado del mapeo:** v4 → **v5** · **Rama:** `fix/biology-audit-stage1`

Gracias por la devolución. Se aplicó una primera etapa que cubre los 18 errores
de equivalencia y los defectos de esquema que no dependen de criterio
biológico. Este documento dice qué se aplicó, dónde nos apartamos de la
recomendación y por qué, qué cifras del informe conviene corregir, y qué
necesitamos de ustedes para seguir.

Todo lo aplicado está verificado contra la base regenerada; los conteos de
cierre están en §5.

---

## 1. Antes que nada: dos hallazgos ya estaban resueltos

La evaluación corrió sobre una copia de `mlosmetadb.db` de 54.786 filas, o sea
anterior al fix de doble ingesta de PhaSepDB (aplicado el 2026-08-08, después
de que saliera el dossier y antes de que llegara la devolución). Eso afecta a
los dos hallazgos que el informe marca como críticos:

| Hallazgo | Estado real al recibir la devolución |
|---|---|
| **INT-01** — PhaSepDB ingerido dos veces bajo `PhaseDB`/`PhasePDB` | Ya resuelto. Un solo tag `PhaSepDB`. |
| **INT-10** — filas una por PMID, no una por aserción | Ya resuelto. Las 35.971 filas tienen clave `(uniprot_id, source_db, source_mlo, source_role)` única: filas totales = claves distintas. |

Verificación directa del segundo, que era el que el informe consideraba mayor
que la duplicación de tags:

```
total rows                          35971
distinct (prot, src, mlo, role)     35971
FUS/P35637 en stress_granule            5      (el informe reportaba 119)
```

Su descomposición predecía **35.925 aserciones reales** tras colapsar PMIDs,
tags y sinónimos. La base tenía 35.971. La diferencia es de sinónimos de nombre
fuente que no colapsamos, y coincide con el orden de magnitud que estimaron.

**No** está hecha la segunda mitad de la acción 1: mover los PMIDs a una tabla
de evidencia con clave foránea. Hoy siguen como lista separada por `;` en
`mlo_annotations.evidence`. La normalización a una fila por aserción, que era
lo que distorsionaba las magnitudes relativas entre MLOs, sí está.

---

## 2. Cifras del informe que conviene corregir

Medidas sobre la base actual. Las que cuentan **proteínas** dieron casi siempre
bien —la duplicación no las afectaba, como ustedes mismos anticiparon— y las
que cuentan **aserciones** estaban infladas.

| Cifra | Informe | Real | Comentario |
|---|---:|---:|---|
| `NotInformed`, proteínas | 1.217 | **930** | Inflada por la duplicación |
| `NotInformed`, sin ninguna otra anotación | 505 | **457** | |
| `in_vitro_droplet`, proteínas | 426 | **442** | |
| `in_vitro_droplet`, sin MLO in vivo | 142 | **146** | |
| Reguladores DrLLPS, aserciones | 1.389 | **1.389** | Exacto |
| Reguladores DrLLPS, proteínas invisibles | 502 | **502** | Exacto |
| Canónicos con `Categoria` en conflicto | 24 | **23** | Ver abajo |

Sobre el último: INT-07 dice «24 canónicos, el dossier reporta 23,
`exosomal_condensate` no está listado». Al enumerarlos sobre el archivo enviado
salen **23 en total, con `exosomal_condensate` entre ellos**
(Extracelular / Citoplasmático). Parece un doble conteo de ese caso. El
diagnóstico de fondo —categoría decidida por orden de lectura, no por curador—
es correcto y era exactamente así.

Dos hallazgos que **confirmamos tal cual** y siguen sin resolver: `refractile_body`
está etiquetado Procariota y su única proteína es de *Eimeria tenella*
(apicomplejo), y `rho_body` está etiquetado Procariota sin ninguna anotación con
organismo resoluble.

---

## 3. Estado de las 22 acciones

| # | Acción | Estado |
|---|---|---|
| 1 | Normalizar filas; PMIDs a tabla de evidencia | **Parcial** — la normalización ya estaba (§1); la tabla de evidencia no |
| 2 | Colapsar `PhaseDB`/`PhasePDB` | **Ya estaba** (§1) |
| 3 | Separar `Centrosome/Spindle pole body` por organismo | **Aplicado** |
| 4 | Separar `Presynaptic clusters and postsynaptic densities` | **Aplicado con modificación** (§4.1) |
| 5 | Crear `xy_body`; corregir `sex_body` | **Aplicado con modificación** (§4.2) |
| 6 | Reemplazar `Categoria` por los cinco ejes | **Pendiente** |
| 7 | Unificar `Citoplasma` / `Citoplasmático` | **Aplicado** |
| 8 | Agregar `evidence_type` | **Pendiente** |
| 9 | Reemplazar la cadena `'NULL'` en `evidence` | **Aplicado** — 13.847 filas → 0 |
| 10 | Eliminar `NotInformed` como canónico | **Pendiente** |
| 11 | Eliminar `in_vitro_droplet` como canónico | **Pendiente** |
| 12 | Indicar por MLO si hay proteoma de clientes | **Pendiente** |
| 13 | Documentar que el rol de DrLLPS es de alcance proteína | **Pendiente** |
| 14 | Reinstaurar Regulator | **Pendiente** |
| 15 | Corregir los errores de equivalencia restantes | **Aplicado** — los 18, uno con modificación (§4.3) |
| 16 | Adjudicar los 64 casos «review» | **Pendiente** — necesitamos su ayuda (§6) |
| 17 | Derivar el eje taxonómico; `refractile_body`, `rho_body` | **Pendiente** |
| 18 | Definir el vocabulario de sufijos estructurales | **Pendiente** |
| 19 | Arreglar la fila CSV mal escapada | **Aplicado** |
| 20 | Documentar las tres vías de exclusión como un mecanismo | **Pendiente** |
| 21 | Resolver `cytoplasmic_protein_granule` / `cytoplasmic_rnp_granule` | **Parcial** — se corrigió el split por capitalización; el límite entre ambos canónicos sigue sin redefinirse |
| 22 | Actualizar `mapping_version` | **Aplicado** — sellada explícitamente, con aserción en el loader |

Además, dos defectos que el informe señala y que ahora el pipeline **rechaza
activamente** en vez de resolver en silencio: una `Categoria` en conflicto
aborta la carga, y un término de vocabulario sin ninguna anotación se poda en
cada regeneración (esto último elimina `adhesin_nanodomain`, `npr1_condensate` y
`rosenthal_fiber`, INT-05).

---

## 4. Dónde nos apartamos de la recomendación

### 4.1 `Presynaptic clusters and postsynaptic densities`: canónico propio, no split

La acción 4 pide separar la etiqueta en sus dos compartimientos. No lo hicimos
así, por esto: son **1.366 proteínas humanas, exactamente una fila por
proteína**, y CD-CODE ya tiene `Presynaptic clusters` y `Postsynaptic density`
como entradas separadas. Esta es una tercera entrada que abarca ambos lados.

Separarla obliga a elegir entre dos afirmaciones que el dato no respalda:
duplicar cada proteína en ambos canónicos afirma que las 1.366 están en los dos
lados de la sinapsis, y repartirlas requiere un criterio que la fuente no
provee. La fuente anota a resolución de sinapsis, así que creamos
**`synaptic_compartment`** a esa misma resolución. Es la regla de «la cobertura
limita la granularidad» que ustedes destacan como acertada, aplicada acá.

Consideramos también descartarla como fracción bioquímica —su tamaño y forma
son los de un screen proteómico de fracción sináptica, y ustedes destacan el
descarte de `synaptosome` por esa misma razón—. No lo hicimos porque no tenemos
el paper de origen. **Si tienen forma de identificar el estudio, esa decisión se
reabre**: si es una preparación de sinaptosomas, el descarte es la respuesta
correcta y `synaptic_compartment` sobra.

### 4.2 `XY body` y `sex body`: son la misma estructura, no dos

La acción 5 pide crear `xy_body`, corregir la definición de `sex_body` y decidir
si se crea `barr_body`. Al mirar las proteínas de `sex body` —Rnf212, proteína
de recombinación meiótica— concluimos que **esa etiqueta también es el cuerpo
sexual meiótico**, y que lo único equivocado era su justificación, que describía
el cuerpo de Barr.

«XY body» y «sex body» son sinónimos en la literatura. Ambos van a `xy_body`
(categoría Germinal) y el canónico `sex_body` desaparece. **No se creó
`barr_body`**: ninguna fuente lo anota, así que crearlo violaría la regla de
cobertura.

Su diagnóstico —«tres estructuras repartidas entre dos canónicos, ninguno
correcto»— era acertado; discrepamos en que fueran tres estructuras con datos.
Son dos con datos (cuerpo sexual meiótico y heterocromatina) más una que solo
existía en un texto de justificación.

### 4.3 `Large dense-core vesicles`: se conserva la asignación, se corrige el texto

Es el único de los 18 errores que no aplicamos como reasignación o descarte.
Su propio razonamiento dice que «el condensado es el núcleo denso
intravesicular», y eso es exactamente `chromogranin_condensate`. Descartar la
fila habría eliminado **SEMG2 (semenogelina-2) del dataset por completo** —era
su única anotación— y roto un invariante que el proyecto sostiene: toda proteína
tiene al menos una anotación.

Corregimos la justificación para que no equipare la vesícula con el condensado,
y conservamos la asignación. La semenogelina es una proteína de gránulo secretor
que separa de fase, así que su pertenencia al núcleo denso es defendible aunque
la etiqueta fuente nombre el continente.

`Golgi ribbon` sí se descartó, por el mismo criterio con el que ya se
descartaron sinaptosoma y matriz extracelular. Ahí no había costo: su proteína
tiene otras anotaciones.

### 4.4 Una imprecisión que introdujimos a conciencia

El split por organismo de `Centrosome/Spindle pole body` manda las filas
fúngicas a `spindle_pole_body` y **todo lo demás a `centrosome`**, incluidas 12
filas de *Arabidopsis*. Las plantas son acentrosómicas, así que esas 12 quedan
mal. Su regla cubre fúngico vs. metazoo y no aborda plantas; inventar un tercer
destino habría ido más allá del hallazgo. Está documentado como imprecisión
conocida en `BIOLOGY.md`. **Si tienen una recomendación para MTOCs vegetales, la
tomamos.**

---

## 5. Conteos de cierre

Verificados sobre la base regenerada. 67 tests de pipeline y 94 de API en verde.

| | Antes | Después |
|---|---:|---:|
| Anotaciones | 35.971 | **35.970** |
| Proteínas | 15.879 | **15.879** |
| Términos canónicos servidos | 167 | **177** |
| Valores de categoría | 22 | **21** |
| `evidence` con la cadena `'NULL'` | 13.847 | **0** |
| Canónicos con categoría arbitraria | 23 | **0** |

Reasignaciones con mayor movimiento:

| Canónico | Antes | Después |
|---|---:|---:|
| `spindle_pole_body` | 910 | **135** |
| `centrosome` | 1.015 | **1.790** |
| `presynaptic_active_zone` | 1.394 | **28** |
| `synaptic_compartment` (nuevo) | — | **1.366** |
| `heterochromatin` | 65 | **55** |
| `inclusion_body` | 95 | **80** |
| `viral_factory` | 35 | **50** |
| `xy_body` (nuevo) | — | **12** |

Canónicos nuevos: `synaptic_compartment`, `xy_body`, `tifasome`,
`proteasome_storage_granule`, `alpha_synuclein_condensate`, `z_disc_condensate`,
`plectin_condensate`, `chaperone_condensate`, `abc_transporter_condensate`,
`bacterial_polarity_condensate`, `cell_polarity_condensate`, `fusion_focus`.
Disueltos: `sex_body`, `polarity_condensate`.

El detalle por decisión, con justificación, está en
`database/mappings/_archive/mlo_mapping_decisions.md` §11.

---

## 6. Qué necesitamos de ustedes

En orden de utilidad para la próxima etapa.

1. **Los 64 casos «review» de `equivalence_verdicts.csv`.** Es el pendiente más
   grande y el que más depende de criterio biológico. Su propia limitación
   declarada es que requieren leer la publicación original. ¿Pueden priorizarlos
   por impacto —proteínas afectadas— para que ataquemos primero los que mueven
   volumen, en vez de ir por orden alfabético?

2. **El estudio detrás de `Presynaptic clusters and postsynaptic densities`.**
   Ver §4.1. Si es una preparación de sinaptosomas, `synaptic_compartment` no
   debería existir y esas 1.366 proteínas deberían descartarse.

3. **`evidence_type`** (acción 8). Aceptamos el diagnóstico: un «driver» de
   PhasePro y uno de PhaSepDB no son la misma afirmación, y el 58,6% de acuerdo
   entre ambos lo muestra. Antes de implementarlo: ¿los tres valores
   (`in_vitro_llps`, `cellular_requirement`, `curator_assignment`) se asignan
   por recurso, o hay filas dentro de un mismo recurso que merecen valores
   distintos? Su tabla de §4.1 sugiere que es por recurso, lo cual lo vuelve
   mecánico.

4. **Reguladores** (acción 14). Nos inclinamos a servirlos como tercer valor de
   rol antes que como flag, porque recupera 502 proteínas hoy invisibles. ¿Ven
   riesgo de que un usuario lea «regulator» como evidencia de pertenencia al
   condensado? Es la razón por la que se los había excluido.

5. **El esquema de cinco ejes** (acción 6). Es el cambio más caro: toca DB, API
   y frontend. Su `category_scheme_proposed.csv` deja 113 de 170 términos sin
   `functional_process` asignado, y el vocabulario ahora tiene 177 términos.
   ¿Consideran que el eje `functional_process` es necesario para que el esquema
   funcione, o los otros cuatro ya resuelven el problema de fondo —que una
   consulta «MLOs nucleares» omita términos etiquetados por taxón o tipo
   celular—? Si alcanza con cuatro, la migración es bastante más barata.

6. **MTOCs vegetales.** Ver §4.4.

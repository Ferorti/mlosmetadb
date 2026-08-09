# Evaluación biológica de MLOsMetaDB

Revisión independiente del vocabulario controlado, el modelo de roles y el esquema de
categorías de MLOsMetaDB, contra el dossier de curación y contra la base servida
(`mlosmetadb.db`, 54.786 filas de anotación, 170 términos canónicos,
841 filas de mapeo).

Todo lo que sigue está verificado sobre los datos. Cuando un hallazgo es una opinión de
criterio y no un defecto medible, está marcado como tal.

---

## Resumen ejecutivo

El vocabulario está bien construido en su mayor parte: de las 242
equivalencias revisadas, **160 son correctas**. Los problemas serios no están
repartidos por todo el vocabulario sino concentrados en cuatro lugares, y tres de ellos son
defectos de ingesta que ninguna cantidad de curación biológica puede compensar.

**Lo que bloquea la publicación:**

1. **Las filas de anotación no son afirmaciones biológicas, son publicaciones.** Cada
   fila corresponde a un PMID de soporte, no a un par proteína–MLO. Esto contradice la
   regla de normalización que el propio dossier enuncia, e implica que la columna
   «annotations» mide atención de la literatura, no cobertura de anotación.
2. **Dos etiquetas compuestas sin explotar arruinan dos términos.**
   `Centrosome/Spindle pole body` mete 872 proteínas mayoritariamente de metazoos en un
   término específico de hongos; `Presynaptic clusters and postsynaptic densities` asigna
   1.366 proteínas al lado presináptico y descarta silenciosamente el postsináptico.
   Entre las dos son el 95% de las proteínas afectadas por errores de equivalencia.
3. **El eje `client`/`driver` no es comparable entre recursos.** Un «driver» de PhasePro
   significa «esta proteína purificada se separa de fase in vitro»; uno de PhaSepDB
   significa «se reporta como necesaria para formar el condensado en células». Además el
   42.2% de las aserciones no tiene rol, y la ausencia está determinada
   enteramente por el recurso.
4. **La columna `Categoria` mezcla cinco ejes semánticos incompatibles.** 56
   de 170 términos están clasificados por algo que no es localización — tipo
   celular, dominio taxonómico, proceso, condición patológica o tipo de evidencia.

**Lo que está bien y conviene defender explícitamente:** la regla de granularidad limitada
por cobertura, la preservación de procedencia mediante `dataset_active`, los 12 descartes
de términos GO genéricos, y la decisión de mantener separados los condensados de estrés
de cloroplasto respecto de los citoplasmáticos.

---

## 1. Integridad de los datos

### 1.1 La inflación de filas y su descomposición

El dossier identifica la doble ingesta de PhaSepDB (tags `PhaseDB` y `PhasePDB`) como su
defecto principal. Es real, pero no es el mayor. Descomponiendo las 54.786 filas crudas:

| paso | filas eliminadas | filas restantes |
|---|---|---|
| crudo | — | 54.786 |
| colapso de filas por PMID | 9.220 | 45.566 |
| colapso del tag PhaSepDB duplicado | 9.522 | 36.044 |
| colapso de nombres fuente sinónimos | 119 | **35.925 aserciones reales** |

La explosión por PMID (9.220 filas) es comparable a la duplicación de tags
(9.522) y el dossier no la menciona. El mecanismo se verificó directamente: en
el 95,2% de las 45.566 claves `(uniprot_id, source_db, source_mlo)`, el número de filas es
exactamente el número de PMIDs distintos, y solo 2.171 claves muestran redundancia real
(más filas que publicaciones). FUS (P35637) aparece con 119 filas de
`stress_granule` en PhasePDB, idénticas salvo por la publicación citada.

**Consecuencia biológica.** Cualquier lectura del tipo «el nucléolo tiene más anotaciones que
el cuerpo de Cajal» está midiendo cuántos papers se escribieron, no cuántas proteínas se
anotaron. La corrección no es cosmética: cambia el ranking de varios términos.

![Deduplicación](art_3f339e26-9114-4aaa-a983-a6f38682b5e8)

### 1.2 Otros defectos verificados

Los diez hallazgos completos están en `data_integrity_findings.csv`. Los que tienen
consecuencia biológica:

- **`evidence` contiene la cadena literal `'NULL'`** en lugar de NULL de SQL. Cualquier
  consulta que filtre por «evidencia disponible» cuenta esas filas como respaldadas.
- **`mapping_version` en `mlo_vocabulary` está desactualizada** respecto de los términos que
  la tabla efectivamente contiene.
- **Tres entradas del vocabulario no tienen ninguna anotación.**
- **Una fila del CSV de mapeo está mal escapada** (coma sin comillas en la justificación de
  `axonal TIAR-2 granules`), lo que rompe el parseo del archivo.

---

## 2. Pregunta A — ¿son biológicamente correctas las equivalencias?

**Respuesta corta: sí en su mayoría, con 18 errores concretos y 64 casos que requieren
decisión de curador.**

Se revisaron 242 pares nombre fuente → canónico
(los 169 que son variantes ortográficas del canónico se excluyeron por triviales).
Veredictos en `equivalence_verdicts.csv`.

| veredicto | pares | proteínas afectadas |
|---|---|---|
| correcto | 160 | — |
| a revisar | 64 | — |
| **error** | **18** | **2.300** |

### 2.1 Los dos errores que dominan: etiquetas compuestas

**`Centrosome/Spindle pole body` → `spindle_pole_body`** (872 proteínas). DrLLPS usa esta
etiqueta compuesta para ambas estructuras. El 73% de las proteínas son humanas o de ratón,
organismos donde no existe cuerpo polar del huso — es el equivalente fúngico del centrosoma.
Asignar el conjunto entero al término fúngico hace desaparecer el proteoma del centrosoma
de metazoos dentro de un término que no le corresponde, y lleva `spindle_pole_body` al
puesto 11 del inventario. **Acción: separar por organismo.**

**`Presynaptic clusters and postsynaptic densities` → `presynaptic_active_zone`**
(1.366 proteínas). Etiqueta compuesta de CDCODE que nombra dos compartimientos en lados
opuestos de la sinapsis. Todo va al término presináptico; la mitad postsináptica se pierde
sin registro. **Acción: separar antes de mapear.**

Ambos casos son exactamente lo que la regla de explosión de compuestos debía capturar; el
patrón `X/Y` y el patrón `X and Y` no fueron cubiertos.

### 2.2 El error de curación con mayor consecuencia conceptual: `XY body`

`XY body` está fusionado a `heterochromatin`. Sus 10 proteínas (Topbp1, Mdc1, Brca1, más
subunidades ribosomales) son la maquinaria de respuesta a daño reclutada en el silenciamiento
meiótico del cromosoma sexual (MSCI) — **cero solapamiento** con las 41 proteínas de
heterocromatina anotadas por el mismo recurso (PhaSepDB); las 10 de `XY body` son todas de
*Mus musculus*. Es una fusión
sin ninguna base compositiva.

Peor: el vocabulario **ya contiene** un canónico `sex_body`, al que la justificación del
mapeo de `XY body` remite explícitamente («cf. sex body»), pero ese canónico recibe otra cosa
— 2 proteínas (Rnf212, C3orf62) y una justificación que describe el **cuerpo de Barr**
(cromosoma X inactivo). Son tres estructuras distintas repartidas entre dos canónicos,
ninguno de los cuales es correcto.

**Acción:** crear `xy_body` para la estructura meiótica, corregir la definición de `sex_body`,
y decidir si se crea `barr_body`.

### 2.3 Otros errores verificados

| nombre fuente | canónico actual | problema |
|---|---|---|
| `inclusion body-associated granule (IBAG)` | `inclusion_body` | Subcompartimiento de inclusiones de VRS: es una factoría viral, no un agregado patológico |
| `P6 inclusion body` | `inclusion_body` | Factoría de replicación del virus del mosaico de la coliflor en células vegetales |
| `TIFA-TRAF6 Condensate` | `inflammasome` | Los TIFAsomas activan NF-κB sin sensor NLR, sin mota de ASC y sin caspasa-1 |
| `Proteasome Storage Granule` | `proteasome_foci` | Estructura citoplasmática de quiescencia en levadura; el canónico es Nuclear |
| `Golgi ribbon` | `golgin_condensate` | Organización de organela con membrana, fuera de la definición de MLO |
| `Large dense-core vesicles` | `chromogranin_condensate` | Vesícula con membrana; el condensado es su contenido, no la vesícula |
| `FATZ-1 condensate` | `postsynaptic_density` | MYOZ1 es proteína del disco Z sarcomérico, no de la densidad postsináptica |
| `ABC transporter condensate` | `bacterial_rnp_body` | Ensamblaje de transporte de membrana asignado a gránulos de RNP bacterianos |
| `α-synuclein condensates` | `synapsin_condensate` | Condensados distintos que coexisten en el presináptico |
| `HSP` / `Plectin` / `SSB condensate` | `signaling_condensate` | Chaperonas, citoesqueleto y reparación de ADN clasificados como señalización |
| `Cytoplasmic protein granule` | `cytoplasmic_rnp_granule` | La misma etiqueta con otra capitalización va a `cytoplasmic_protein_granule` |

Ese último es un fallo de normalización, no de criterio: **el mismo nombre fuente se reparte
entre dos canónicos según su capitalización.**

### 2.4 Fusiones anchas: agregación de clase, no sinonimia

`transcriptional_condensate` absorbe 20 nombres fuente, entre ellos condensados específicos
de factor (BRD4, cBAF, EWS-FLI1, c-Maf, MEF2D, TFAP2β). Estos comparten función pero no
composición, y el solapamiento de proteínas entre ellos es bajo por una razón legítima.

Esto es **defendible bajo la regla de granularidad del proyecto** — ninguna fuente anota el
término genérico a resolución de factor. Pero el esquema debería declararlo: son
agregaciones funcionales, no conjuntos de sinónimos, y presentarlas como equivalencias
induce a error. Lo mismo aplica a `cytoplasmic_rnp_granule` (12 nombres), `viral_factory` (13)
y `signaling_condensate` (12).

![Coherencia de fusiones](art_a50fc467-091f-47db-a25f-d4fee5013326)

### 2.5 Sobre el test cuantitativo de fusiones

Se midió el solapamiento de conjuntos de proteínas entre nombres fuente fusionados en un
mismo canónico. **El test tiene poco poder sobre estos datos y ese es un resultado en sí
mismo:** de 825 pares, 365 no comparten organismo y 238 más no comparten
recurso. En esos casos el solapamiento cero es artefacto de cobertura disjunta, no evidencia
de mala curación. Solo **22 pares** superan los tres filtros (mismo recurso,
organismo compartido, ≥5 proteínas cada uno).

No conviene usar solapamiento de proteínas como criterio de validación de fusiones en este
dataset. La detección del error de `XY body` fue posible precisamente porque era uno de los
22 casos evaluables.

---

## 3. Pregunta B — ¿es coherente el esquema de categorías?

**Respuesta corta: no. La columna `Categoria` mezcla cinco ejes semánticos incompatibles, y
los 24 conflictos reportados son síntoma de eso, no la enfermedad.**

De los 22 valores de categoría:

| eje semántico | términos | valores |
|---|---|---|
| localización subcelular | 114 | Nuclear, Citoplasmático, Citoplasma, Membrana, Mitocondrial, Plastídico, Extracelular, Secretor |
| tipo celular | 22 | Germinal, Neuronal |
| dominio taxonómico | 19 | Procariota, Vegetal, Viral |
| asociación estructural | 6 | Citoesqueleto |
| proceso biológico | 2 | Autofagia, Mitótico |
| condición | 2 | Patológico |
| tipo de evidencia | 1 | In vitro |
| híbridos explícitos | 3 | Viral/Nuclear, Nuclear/Mitótico, Nuclear/Citoplasmático |

**El problema no es estético.** Una consulta «todos los MLO nucleares» omite silenciosamente
los 22 términos etiquetados por tipo celular y los 19 por taxón, la mayoría de los cuales
**sí tienen** una localización definida. `p_granule` es germinal *y* citoplasmático *y* de
metabolismo de RNA; el esquema obliga a elegir uno.

**`Citoplasma` y `Citoplasmático` son la misma categoría con dos grafías** (5 y 39 términos).
Seis canónicos reciben ambas. Unificarlas resuelve 6 de los 24 conflictos reportados sin
ninguna decisión biológica.

### 3.1 Esquema propuesto: cinco ejes ortogonales

| eje | cardinalidad | contenido |
|---|---|---|
| `compartment_class` | único | Solo espacial: nucleoplasm, cytosol, membrane_associated, mitochondrial, plastid, extracellular, cell_free |
| `taxonomic_scope` | múltiple | bacteria, archaea, fungi, plants_algae, metazoa, viruses, protists — **derivado de los organismos anotados**, no asignado por curador |
| `cell_type_context` | múltiple, nullable | germline, neuron, immune_cell, muscle, embryo |
| `functional_process` | múltiple, nullable | rna_metabolism, transcription, stress_response, dna_repair, signal_transduction, protein_quality_control, cell_division, cell_polarity, host_pathogen, metabolism, adhesion |
| `physiological_state` | único | physiological, pathological, engineered |

El esquema está aplicado a los 170 canónicos en `category_scheme_proposed.csv`, y
la traducción desde las categorías actuales en `category_axis_remap.csv`. **Resuelve 18 de
los 24 conflictos por construcción**; los 6 restantes son decisiones genuinas de curación.

### 3.2 El eje taxonómico está mal asignado

Derivar `taxonomic_scope` de los organismos anotados en vez de asignarlo a mano corrige dos
errores y recupera cinco términos mal ubicados:

- `refractile_body` está etiquetado **Procariota** pero su única proteína es de
  *Eimeria tenella*, un protista apicomplejo.
- `rho_body` está etiquetado **Procariota** sin ninguna anotación con organismo resoluble.
- `aggresome` (100% *E. coli* en los datos), `sirna_body`, `nuclear_dicing_body`,
  `antiviral_condensate` y `plant_signaling_condensate` (100% plantas) llevan categorías de
  localización en vez de taxonómicas.

![Esquema de categorías](art_56a4b003-74d4-4ac7-951a-f607cf787759)

---

## 4. Pregunta C — ¿es defendible el modelo driver/cliente?

**Respuesta corta: el modelo es razonable pero la implementación actual no es defendible,
porque la columna `unified_role` mezcla tres tipos de afirmación distintos.**

### 4.1 Cada recurso mide una cosa diferente

| recurso | aporta | qué significa su etiqueta |
|---|---|---|
| PhaSepDB | client + driver | reportado como necesario para formar el condensado en células |
| DrLLPS | Client→client, Scaffold→driver | asignación de curador |
| LLPSDB | **solo** driver | la proteína purificada se separa de fase in vitro |
| PhasePro | **solo** driver | ídem |
| CDCODE | **nada** | no tiene concepto de rol |

CDCODE aporta el 38.3% de las aserciones y ningún rol. En total el
**42.2% de las aserciones no tiene rol**, y la falta está determinada
enteramente por el recurso, no por incertidumbre biológica.

La consecuencia se ve en el acuerdo entre recursos: PhaSepDB vs DrLLPS coinciden en el
**90.9%** de 1.608 aserciones compartidas, pero PhaSepDB vs PhasePro
solo en el **58.6%** de 70, con 29 reversiones cliente↔driver. Ese
41% de desacuerdo no es ruido de curación: es la consecuencia predecible de comparar «se
separa de fase in vitro» con «es necesaria en células». Muchas proteínas hacen lo primero y
son clientes en lo segundo.

### 4.2 El rol se asigna a la proteína, no al par proteína–compartimiento

En DrLLPS, **las 1.055 proteínas anotadas en más de un MLO llevan rol idéntico en todos**
(cero excepciones), con un promedio de 2,4 MLO por proteína y hasta 8. En PhaSepDB solo el
26,2% de las proteínas multi-MLO varía su rol.

Esto significa que el modelo afirma que ser driver es una propiedad de la proteína, no del
par proteína–compartimiento. **Biológicamente es incorrecto:** FUS dirige la formación de
gránulos de estrés y es cliente del nucléolo. La base actualmente no puede expresar esa
diferencia.

### 4.3 `driver_share` mide disponibilidad de datos, no biología

Cuatro términos con n≥20 tienen `driver_share = 1.00`: `heterochromatin`, `inclusion_body`,
`transcriptional_condensate` y `NotInformed`. **Ninguno tiene un recurso que aporte proteoma
de clientes.** En el otro extremo, `nucleolus` tiene 2,1% de drivers porque DrLLPS y PhaSepDB
aportan 5.463 aserciones de cliente.

Leer estas fracciones como «el nucléolo es mayormente clientes y la heterocromatina es toda
drivers» invierte causa y efecto: la fracción mide si alguien hizo un estudio proteómico de
ese compartimiento.

![Modelo de roles](art_d4ffe608-c608-49df-9c7d-ee85224af3e1)

### 4.4 Recomendación

Mantener `unified_role` pero **agregar una columna `evidence_type` obligatoria** con tres
valores: `in_vitro_llps`, `cellular_requirement`, `curator_assignment`. Documentar que el rol
de DrLLPS es de alcance proteína. No publicar `driver_share` sin un indicador de si el MLO
tiene fuente de proteoma de clientes.

### 4.5 La exclusión de Regulator tiene un costo medible

1.389 aserciones de tipo Regulator (DrLLPS) están marcadas `dataset_active=0`. De las
proteínas involucradas, **502 desaparecen por completo del dataset servido**
porque no tienen ninguna otra anotación, concentradas en `p_body`, `stress_granule` y
`p_granule`.

Los reguladores — quinasas, chaperonas, helicasas que modulan el ensamblaje — son una clase
biológicamente informativa. Excluirlos sesga el dataset hacia componentes estructurales y
elimina justamente las enzimas que controlan el ensamblaje. La procedencia se preserva
(las filas siguen ahí), pero la decisión merece revisarse: servir Regulator como tercer valor
de rol es preferible a excluirlo.

---

## 5. Pregunta D — cobertura y nomenclatura

### 5.1 Perfil de soporte del vocabulario

**71 de los 170 términos canónicos se apoyan en 3 proteínas o
menos** (39 en una sola, 3 sin ninguna anotación). Esto no es un defecto en sí — refleja el
estado real de la literatura — pero conviene exponerlo: un usuario que consulta
`mesh_condensate` debería ver que hay 3 proteínas detrás, no una entrada de vocabulario con
el mismo peso visual que `nucleolus`.

Al deduplicar, cuatro entradas del top-45 publicado caen entre 25 y 74 posiciones:
`tdp43_nuclear_condensate` pasa del puesto 45 al 119 (2 proteínas reales) y
`mesh_condensate` del 36 al 109 (3 proteínas).

![Perfil de soporte](art_fcb52460-359f-4d5f-9235-775b4c64ff43)

### 5.2 Huecos de cobertura

`coverage_gaps.csv` lista 12 términos ausentes. Lo notable: **la mayoría son creables con
datos que ya están en la base**, así que la regla de granularidad no los bloquea.

| término faltante | prioridad | evidencia disponible |
|---|---|---|
| XY body (cuerpo sexual meiótico) | alta | 10 proteínas ya en la base, bajo `heterochromatin` |
| Barr body | alta | el concepto está en la justificación de `sex_body`, sin canónico propio |
| TIFAsoma | media | 7 proteínas mal ubicadas en `inflammasome` |
| Gránulo de almacenamiento de proteasoma | media | 5 proteínas mal ubicadas |
| Cuerpo amiloide (A-body) | media | nombre fuente `A-bodies` presente |
| Condensado sarcomérico / disco Z | media | 1 proteína mal ubicada |
| Purinosoma | media | ninguna fuente lo anota — la regla de cobertura lo bloquea legítimamente |

### 5.3 Nomenclatura

`naming_review.csv` documenta 12 problemas. El más sistemático: **nueve sufijos estructurales
sin semántica definida** — `condensate` (44), `body` (42), `granule` (19), `compartment` (6),
`complex` (5), `foci` (5), `speckle` (3), `puncta` (2), `droplet` (2). `foci` y `puncta` son
descripciones de microscopía; `complex` implica estequiometría (y esos términos suelen
pertenecer a DISCARD); `droplet` implica liquidez in vitro.

Otros: cinco términos en plural contra 165 en singular; 13 términos nombrados por una sola
proteína, que confunden «un condensado que contiene X» con «el compartimiento que X define»;
`NotInformed` en CamelCase dentro de un vocabulario snake_case.

### 5.4 Descartes y valores especiales

Los 12 descartes de términos GO genéricos (`protein-containing complex`,
`intracellular non-membrane-bounded organelle`, `ribonucleoprotein complex`, microtúbulos,
matriz extracelular, sinaptosoma) son **correctos y bien fundamentados**. `synaptosome` en
particular merece destacarse: es un artefacto de fraccionamiento bioquímico, no un
compartimiento in vivo, y es un contaminante frecuente de datasets proteómicos de MLO.

Problemas encontrados (`discard_review.csv`):

- **`NotInformed` es un marcador de dato faltante servido como si fuera un compartimiento.**
  Ocupa el puesto 6 del inventario con 1.217 proteínas en 108 organismos;
  505 de esas proteínas **no tienen ninguna otra anotación**, o sea que
  existen en la base únicamente bajo una etiqueta que no es un compartimiento.
- **`in_vitro_droplet` es un tipo de evidencia, no un compartimiento.** 426
  proteínas, de las cuales 142 no tienen ningún MLO in vivo, y el 99% lleva
  rol driver. Es, en los hechos, una lista de propensión a LLPS in vitro.
- **Hay tres vías de exclusión no documentadas como tales:** `DISCARD` (15 entradas),
  `synthetic_condensate` (386 construcciones de ingeniería) y un canónico literalmente
  llamado `NULL` (3 entradas). Deberían ser un solo mecanismo con campo de motivo.
- `TRIM45 bodies` está descartado pese a ser un cuerpo nuclear genuino, y su fila conserva
  `Categoria='Nuclear'`, contradiciendo su propio descarte.
- `synaptosome, neuron projection` se descarta como una sola etiqueta compuesta, con
  `Categoria` igual a la cadena `'NULL'`.

---

## 6. Matriz de acciones

Prioridad 1–12 bloquean publicación; 13–22 son mejoras. Detalle completo en
`action_matrix.csv`.

| # | área | acción |
|---|---|---|
| 1 | ingesta | Normalizar a una fila por (proteína, recurso, MLO, rol); mover PMIDs a tabla de evidencia |
| 2 | ingesta | Colapsar los tags `PhaseDB`/`PhasePDB` a un solo recurso PhaSepDB |
| 3 | vocabulario | Separar `Centrosome/Spindle pole body` por organismo |
| 4 | vocabulario | Separar `Presynaptic clusters and postsynaptic densities` |
| 5 | vocabulario | Crear `xy_body`; corregir la definición de `sex_body` |
| 6 | esquema | Reemplazar `Categoria` por los cinco ejes ortogonales |
| 7 | esquema | Unificar `Citoplasma` y `Citoplasmático` |
| 8 | esquema | Agregar `evidence_type` a cada anotación |
| 9 | datos | Reemplazar la cadena `'NULL'` en `evidence` por NULL de SQL |
| 10 | vocabulario | Eliminar `NotInformed` como canónico |
| 11 | documentación | Indicar por MLO si existe fuente de proteoma de clientes |
| 12 | documentación | Documentar que el rol de DrLLPS es de alcance proteína |
| 13–22 | varios | Reinstaurar Regulator, corregir los 16 errores restantes, adjudicar los 64 casos a revisar, derivar el eje taxonómico, definir sufijos, arreglar el CSV mal escapado |

---

## 7. Limitaciones de esta evaluación

- Los veredictos de equivalencia son juicio biológico sobre la etiqueta fuente y las
  proteínas anotadas, **sin consultar la publicación original**. Los 64 casos
  marcados «review» necesitan que un curador vea el paper.
- El test de solapamiento de proteínas tiene poco poder aquí (22 de
  825 pares evaluables); su ausencia de señal no valida las fusiones.
- La asignación de `functional_process` en el esquema propuesto es un primer pase por
  término, no una curación exhaustiva: 113 de 170 términos quedaron sin proceso
  asignado.
- No se evaluó alineación con ontologías externas (GO, ChEBI), fuera de alcance por decisión
  del dossier.
- Todo el análisis corre sobre una copia local de `mlosmetadb.db`; si la base cambió desde la
  copia, los conteos deben recalcularse.

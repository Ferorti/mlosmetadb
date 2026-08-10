# Segunda devolución: verificación de v5 y respuestas a las consultas abiertas

**Fecha:** 2026-08-10 · **Responde a:** `docs/review/RESPUESTA_A_LA_DEVOLUCION.md`
**Base verificada:** `database/mlosmetadb.db` en el commit `16378be` · **Mapeo:** v5

Se verificaron los conteos de cierre contra la base regenerada, se revisaron las
cuatro decisiones donde el equipo se apartó de la recomendación, y se responden
las seis consultas de §6. Todas las cifras de este documento salen de esa base.

---

## 1. Verificación de los conteos de cierre

Confirmado sobre la base regenerada:

| | Declarado | Verificado |
|---|---:|---:|
| Anotaciones | 35.970 | **35.970** |
| Claves distintas `(uniprot_id, source_db, source_mlo, source_role)` | — | **35.970** |
| Proteínas | 15.879 | **15.879** |
| Términos canónicos | 177 | **177** |
| Valores de categoría | 21 | **21** |
| `evidence` con la cadena `'NULL'` | 0 | **0** |

Filas totales = claves distintas. **INT-01 e INT-10 están cerrados.** Las ocho
reasignaciones de §5 verifican exactamente.

Una precisión sobre esa tabla: los ocho valores son **filas de anotación**, no
proteínas distintas. `centrosome` tiene 1.790 filas pero
999 proteínas; `heterochromatin` 55 filas y
42 proteínas. El informe original contaba proteínas, así que
conviene rotular la columna para que un lector no lea 1.790 como
proteínas.

Sobre INT-07: la observación es correcta, fue doble conteo nuestro. Son 23 con
`exosomal_condensate` incluido, no 24.

---

## 2. Las cuatro decisiones donde se apartaron

### 2.1 `synaptic_compartment` — reversión recomendada

§4.1 pide el estudio de origen para decidir. No hace falta: el dato lo resuelve.

De las 1.366 proteínas de `synaptic_compartment`, **1.360
(99.6%) ya están anotadas como `postsynaptic_density` en el mismo
recurso**. Sólo 6 son exclusivas, y una de ellas (TMEM11) es
mitocondrial.

Segunda señal: las 1.366 filas tienen `evidence` en nulo, mientras la
entrada de PSD de CD-CODE lleva PMID 23071613.

El razonamiento de §4.1 —no inventar un reparto que la fuente no provee— es
correcto. Lo que cambia el diagnóstico es que no hay nada que repartir: el
contenido ya está servido bajo `postsynaptic_density`. La etiqueta compuesta no
es una tercera entrada a resolución de sinapsis; es una reexportación redundante
de la entrada de PSD, sin procedencia.

**Recomendación:** retirar `synaptic_compartment` y tratar el nombre fuente como
sinónimo de `postsynaptic_density`. Revisar por separado si las
6 exclusivas tienen otra vía de anotación.

### 2.2 `xy_body` / `sex_body` — aceptado

La lectura del equipo es mejor que la nuestra. Rnf212 es maquinaria de
recombinación meiótica, «XY body» y «sex body» son sinónimos en la literatura, y
el cuerpo de Barr sólo existía en un texto de justificación, no en datos. No
eran tres estructuras con datos: eran dos. No crear `barr_body` es lo correcto
bajo la regla de cobertura.

### 2.3 `Large dense-core vesicles` — aceptado

Conservar la asignación para no perder SEMG2 es la decisión correcta. El
invariante de que toda proteína tenga al menos una anotación pesa más que la
pulcritud de esa etiqueta, y el núcleo denso intravesicular es efectivamente el
condensado.

### 2.4 MTOCs vegetales — resoluble ahora, no dejar como imprecisión

Las 12 filas de *Arabidopsis* enviadas a `centrosome` son TUBG1, GCP3,
GCP4, NEDD1, TON1A, TPX2, EB1A, EB1C, KIN14D, AAA1 (katanina) y GIP1. Eso es el
complejo γ-TuRC más la maquinaria TON1/TRM: el sistema de nucleación
acentrosómica de plantas, con γ-tubulina dispersa en envoltura nuclear y
corteza, sin centríolos. No es centrosoma en ningún sentido.

La lista de genes es diagnóstica y no requiere consultar la publicación.

**Recomendación:** crear `plant_mtoc` (o `acentrosomal_mtoc`) y mover las
12 filas.

Nota favorable: `spindle_pole_body` quedó con 135 filas, todas de
*S. cerevisiae* y *S. pombe*. El split fúngico funcionó limpio.

---

## 3. Respuestas a §6

### 3.1 Los 64 casos «review», priorizados

62 de los 64 siguen vivos en v5 —`Sh3gl2` y `Spindle pole` ya se
resolvieron— y suman 790 proteínas. Están muy concentrados: **un
solo caso, `Mitochondrial cloud`, son 598 de esas 790
(75.7%)**.

`review_cases_prioritized.csv` los ordena por volumen y por dominancia sobre el
término destino, porque un caso de 4 proteínas que es el 50% de su canónico
importa más que uno de 20 que es el 2%.

Además se adjudicaron los nueve de mayor impacto —86.2% de las
proteínas afectadas— desde las listas de genes, sin leer publicaciones
(`review_cases_adjudicated.csv`):

| nombre fuente | canónico actual | proteínas | fracción del destino | adjudicación |
|---|---|---:|---:|---|
| Mitochondrial cloud | `balbiani_body` | 598 | 0.67 | correct |
| Receptor cluster | `signaling_cluster` | 24 | 0.63 | split_needed |
| Leucocyte nuclear body | `nuclear_body` | 21 | 0.09 | correct_but_overgeneral |
| Germ granule | `p_granule` | 14 | 0.02 | correct |
| Peri-nucleolar condensate | `perinucleolar_compartment` | 6 | 0.75 | review_still_needed |
| PCBP2 condensates | `signaling_condensate` | 5 | 0.33 | error |
| SARS-CoV-2 condensate | `sars_cov2_n_condensate` | 4 | 0.40 | pending |
| Row 1-specific tip complex condensates | `ankle_link_condensate` | 4 | 0.50 | pending |
| SCOTIN condensate | `eres_condensate` | 3 | 0.30 | pending |
| Euchromatin | `chromatin_compartment` | 2 | 0.40 | pending |
| eukaryotic topoisomerase ii | `chromatin_compartment` | 2 | 0.40 | pending |
| euchromatin | `chromatin_compartment` | 2 | 0.40 | pending |
| Enzyme_shell proteins condensates | `carboxysome` | 2 | 0.40 | pending |
| RISC complex | `mirisc` | 2 | 1.00 | discard_candidate |
| Nuclear poly(A) domains | `maternal_mrna_condensate` | 1 | 0.50 | pending |
| YBX1 condensate | `exosomal_condensate` | 1 | 0.50 | pending |
| Fus1 condensate | `fusion_focus` | 1 | 1.00 | pending |

Los razonamientos:

- **`Mitochondrial cloud` → correcto.** En ovocito de *Xenopus* la nube
  mitocondrial es el cuerpo de Balbiani. 594 de 598 proteínas son
  *X. laevis*. Cerrar.
- **`Germ granule` → correcto.** osk, vas, tej, spn-E, me31B, tdrd6: plasma
  germinal canónico. Gránulo germinal y gránulo P son la misma estructura entre
  especies.
- **`+TIP body` → correcto.** KAR9/BIM1/BIK1 en *S. cerevisiae* y
  mal3/tea2/tip1 en *S. pombe* son los complejos de rastreo de extremo más.
- **`PCBP2 condensates` → error.** DCP1A, DDX6 y TIA1 son componentes de cuerpo
  P y gránulo de estrés. Reasignar a `cytoplasmic_rnp_granule` o `p_body`, no
  `signaling_condensate`.
- **`Receptor cluster` → split o descarte.** Mezcla sinapsis inmune (LAT, NCK1,
  SOS1, WASL), SNAREs de exocitosis (Snap25, Stx1a) y señalización antiviral
  innata (MAVS, IRF3). No es un compartimiento.
- **`ORC1 bodies` → probablemente mal.** SUV39H1, EZH2, CBX5 y DNMT1 son
  silenciamiento y heterocromatina; sólo ORC1 encaja en
  `replication_compartment`.
- **`Peri-nucleolar condensate` → probablemente mal.** HSP104 y SIS1 en levadura
  marcan el compartimiento yuxtanuclear de control de calidad (JUNQ/INQ), no el
  compartimiento perinucleolar de mamífero, que es una estructura de
  procesamiento de RNA rica en PTB.
- **`RISC complex` → descarte.** Nombre de complejo macromolecular, misma clase
  que la holoenzima de Pol II ya marcada para descarte.
- **`Leucocyte nuclear body` → correcto pero pierde información.** BRD4, MED1,
  ESR1, PGR, DAXX, SPOP son componentes genéricos de cuerpo nuclear. El mapeo a
  `nuclear_body` está bien; «leucocito» es contexto de tipo celular y el esquema
  de ejes lo recuperaría.

### 3.2 El estudio sináptico

Ver §2.1. La pregunta se responde sin la publicación.

### 3.3 `evidence_type` es mecánico, pero necesita cinco valores

Se verificó que cada par `(source_db, source_role)` es homogéneo: ocho
combinaciones, ninguna ambigua, ninguna sin mapear. La asignación es por
recurso, como anticipaban.

Hacen falta **cinco** valores, no tres, porque PhaSepDB emite dos afirmaciones
distintas según el rol:

| source_db | source_role | evidence_type |
|---|---|---|
| LLPSDB | driver | `in_vitro_llps` |
| PhasePro | driver | `in_vitro_llps` |
| PhaSepDB | client | `cellular_localisation` |
| PhaSepDB | driver | `cellular_requirement` |
| DrLLPS | Scaffold | `curator_assignment` |
| DrLLPS | Client | `curator_assignment` |
| DrLLPS | Regulator | `curator_assignment` |
| CDCODE | NotInformed | `membership_only` |

`membership_only` importa más de lo que parece: hace explícito que el
42.3% de filas sin rol (15.233) no es dato faltante sino
el alcance declarado de CD-CODE. Con esa columna, la ausencia de rol deja de ser
un agujero y pasa a ser información.

Tabla completa en `evidence_type_mapping.csv`, con el fundamento de cada
asignación.

### 3.4 Reguladores: sí, como tercer valor de rol

El riesgo que plantean —que un usuario lea «regulator» como evidencia de
pertenencia— es real, pero la solución no es ocultar 502 proteínas.

Verificado: las 1.389 filas de Regulator cubren 977
proteínas, de las cuales **502 no tienen ninguna otra anotación con
rol**. Esas 502 tienen 607 anotaciones en
19 MLOs, concentradas en `p_body` (429) y `stress_granule`
(418).

Con `evidence_type = curator_assignment` más una definición explícita de que el
regulador *influye sobre* el condensado sin necesariamente residir en él, la
afirmación queda acotada. La malinterpretación se previene con una columna que
de todos modos van a agregar; la pérdida de cobertura no se recupera de ninguna
forma.

### 3.5 Cuatro ejes alcanzan

Se verificó qué términos quedarían sin clasificar si se omite
`functional_process`: **sólo tres** — `liquid_dyrk3_speckle`, `midbody_granule`
y `fip200_puncta`.

Los 55 términos hoy clasificados por algo que no es localización
se resuelven con los otros cuatro ejes: Germinal (16) y Neuronal (10) son tipo
celular; Procariota (14), Vegetal (3) y Viral (5) son taxón; Patológico e
In vitro son estado fisiológico.

**Recomendación:** implementar cuatro ejes. `functional_process` puede sumarse
después como columna opcional si aparece demanda. No bloquea el problema de
fondo, que es que una consulta espacial omita 55 de 177
términos.

### 3.6 MTOCs vegetales

`plant_mtoc`. Ver §2.4.

---

## 4. Prioridad sugerida para la etapa 2

En orden, considerando que el scope del proyecto es el mapeo entre bases y no la
curación de evidencia primaria:

1. Retirar `synaptic_compartment` (§2.1) — 1.366 filas redundantes.
2. Crear `plant_mtoc` y mover las 12 filas de *Arabidopsis* (§2.4).
3. Agregar `evidence_type` con los cinco valores (§3.3) — mecánico, sin criterio
   biológico.
4. Reinstaurar Regulator como tercer valor de rol (§3.4) — recupera
   502 proteínas.
5. Cerrar los seis casos «review» ya adjudicados como correctos o error (§3.1).
6. Migrar a cuatro ejes de categoría (§3.5) — el más caro, y el único que toca
   API y frontend.

Los tres casos marcados `review_still_needed` o `split_needed` sí requieren ir a
la fuente; son 35 proteínas en total.

---

## 5. Limitaciones de esta verificación

- Todo se midió sobre una copia de `database/mlosmetadb.db` del commit
  `16378be`. Si la base se regeneró después, los conteos deben rehacerse.
- Las nueve adjudicaciones de §3.1 son juicio biológico sobre listas de genes y
  organismos, no lectura de las publicaciones originales. Las tres marcadas
  `review_still_needed` o `split_needed` requieren la fuente.
- Los 53 casos «review» restantes
  (109 proteínas) siguen sin
  adjudicar; están priorizados pero no resueltos.

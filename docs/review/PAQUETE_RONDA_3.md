# Paquete para la ronda 3 — MLOsMetaDB

**Fecha:** 2026-08-10 · **Mapeo:** v6 · **Commit:** `dfc00f2`
**Responde a:** `docs/review/ultima/SEGUNDA_DEVOLUCION.md`

---

## 0. Lo primero: contra qué medir

**Antes de calcular una sola cifra, leé `tests/dataset_baseline.json` y usá su
bloque `_meta`.** Contiene:

```json
"_meta": { "generated_on_commit": "dfc00f2", "generated_at": "2026-08-10" }
```

Ese archivo es la huella de la base servida: conteos por tabla, por `source_db`,
por `unified_role`, por `dataset_active`, por `evidence_type`, el histograma de
`source_db_count`, los MLOs distintos en uso y el testigo de FUS (P35637).

**Lo que necesitamos de ustedes:** que su documento de vuelta **declare el
commit contra el que midió**. Si sacan una copia local de `mlosmetadb.db` —como
hicieron en las dos rondas anteriores, y está bien que lo hagan— díganlo y
digan de cuándo es.

Por qué importa, sin reproche: en la ronda 1 midieron sobre 54.786 filas cuando
la base viva tenía 35.971, porque nada en el paquete que les mandamos declaraba
de qué momento partía. La mitad de sus cifras absolutas nacieron infladas por
eso, incluidos los dos hallazgos que graduaron como críticos y que ya estaban
resueltos. Con `_meta` presente, eso se detecta comparando dos valores.

Conteos de referencia al día de hoy:

| | |
|---|---:|
| `mlo_annotations` | 35.968 |
| `proteins` | 15.879 |
| `mlo_vocabulary` | 177 |
| Valores de categoría | 21 |
| Filas sin `unified_role` | 15.233 (42,4%) |
| Filas con `dataset_active = 0` | 1.389 |

---

## 1. Qué cambió desde su segunda devolución

Se aplicó todo lo que no dependía de criterio biológico nuevo. Detalle por
decisión en `database/mappings/_archive/mlo_mapping_decisions.md` §12.

| Cambio | Efecto |
|---|---|
| `synaptic_compartment` retirado, la etiqueta pasa a sinónimo de `postsynaptic_density` | `postsynaptic_density` 4.478 → 5.844 |
| `plant_mtoc` creado con las 12 filas de *Arabidopsis* | `centrosome` 1.790 → 1.778 |
| `evidence_type` agregado, cinco valores | 35.968 filas, cero NULL |
| `PCBP2 condensates` → `cytoplasmic_rnp_granule` | `signaling_condensate` 15 → 10 |
| `RISC complex` → DISCARD | `mirisc` conserva 8 filas y sus 2 proteínas |

Los cuatro casos que cerraron como correctos (`Mitochondrial cloud`,
`Germ granule`, `+TIP body`, `Leucocyte nuclear body`) no requirieron cambio y
quedaron registrados como tales.

### 1.1 Tres cifras de su informe que no se sostienen

Registradas en el libro con la medición que las corrige, para que puedan
ajustarlas de su lado:

| Su afirmación | Medido en la base viva |
|---|---|
| El solapamiento sináptico es intra-recurso: CD-CODE reexporta su propia entrada de PSD | 1.353 de 1.360 vienen de **DrLLPS**; solo 3 de CD-CODE. Es coincidencia **entre** recursos independientes, que es mejor evidencia que la duplicación interna que suponían |
| Las filas de PSD de CD-CODE llevan PMID 23071613 | **Ninguna** fila de CD-CODE lleva PMID en esta base (0 de 13.844), por diseño del export |
| Reguladores: `p_body` 429, `stress_granule` 418 | 253 y 164. Las suyas suman más que su propio total de 607; parecen contadas sobre las 977 proteínas reguladoras y no sobre las 502 invisibles |

Ninguna de las tres cambia sus conclusiones. La primera incluso las refuerza.

### 1.2 Una omisión que conviene que sepan

Su segunda devolución describe `RNA polymerase II, holoenzyme` como "ya marcada
para descarte" al justificar el descarte de `RISC complex`. **Nunca recibió
veredicto:** INT-09 de la ronda 1 solo pedía mandarla a la revisión de descarte,
y no aparece ni en `discard_review.csv` ni en `equivalence_verdicts.csv`. Sigue
sin adjudicar, en `transcriptional_condensate` con 2 filas (`R1-INT-09`).

---

## 2. El inventario: qué sigue abierto

**Novedad de esta ronda.** El estado de cada hallazgo ya no vive en prosa: está
en `docs/review/findings.csv`, 62 filas, una por ítem que requiere o recibió una
decisión nuestra. Cada fila apunta a la fila de origen en **sus** archivos y
agrega solo lo que ustedes no pueden saber: qué verificamos, con qué consulta,
qué decidimos y en qué commit quedó.

Para verlo:

```bash
python3 scripts/review_ledger.py --check
```

Estados: `abierto` (no lo miramos), `verificado` (lo medimos, es cierto, no
actuamos), `refutado` (lo medimos y no se sostiene), `aplicado`, `rechazado`,
`necesita_fuente`, `superado`, `cerrado`.

**26 ítems pendientes.** Los que más nos importan, en orden:

### 2.1 Cinco hallazgos suyos que se nos habían escapado

No estaban en ninguna lista nuestra hasta esta ronda. Su matriz de acciones
referencia 13 de sus 24 findings numerados, y asumimos que los subsumía a todos.
No era así. Uno de estos lo graduaron **critical**:

| id | Su finding | Estado nuestro |
|---|---|---|
| `R1-ROL-02` | 42% de aserciones sin rol, ausencia determinada por el recurso | **verificado** — 15.233 de 35.968 = 42,4%: CDCODE 13.844 más 1.389 Regulator. `evidence_type` hace explícita la causa, pero eso registra y no reporta |
| `R1-INT-02` | Roles contradictorios dentro de PhaSepDB, piden regla de precedencia | **rechazado** — 214 tripletas / 182 proteínas confirmadas. Se conservan las dos a propósito: driver y componente son experimentos distintos |
| `R1-ROL-05` | El acuerdo de roles se rompe contra fuentes in vitro; piden tabla de QC | **verificado** — el desacuerdo del 58,6% motivó `evidence_type`, pero se definió desde la tabla `(source_db, source_role)` y no desde el conjunto de desacuerdos |
| `R1-ROL-07` | 18% de drivers viene de recursos que solo dicen driver | **verificado** — 577 de 3.068 = 18,8% (LLPSDB 380, PhasePro 197). `evidence_type = in_vitro_llps` ya los marca |
| `R1-INT-04` | PMIDs de fila heredados; marcar canónicos de un solo PMID | **verificado** — la mitad documental está hecha, la marca en la UI no |

### 2.2 Las dos piezas caras

- **`R1-ACT-14` — reinstaurar Regulator.** Aceptamos su argumento. 1.389 filas,
  977 proteínas, **502 invisibles** que aportan 607 anotaciones en 19 MLOs
  (`p_body` 253, `stress_granule` 164, `p_granule` 107). Cambia lo que sirve el
  sitio, así que va con la migración de API.
- **`R1-ACT-06` / `R2-DEC-axes` — migración de categorías.** Tomamos su
  respuesta de que **cuatro ejes alcanzan**. No verificamos la afirmación de que
  omitir `functional_process` deja sin clasificar solo tres términos.

### 2.3 Lo que necesita la publicación original

Tres casos, 35 proteínas: `R2-ADJ-receptor-cluster` (24), `R2-ADJ-perinucleolar`
(6), `R2-ADJ-orc1`. Más `R2-ADJ-batch`: los 53 sin adjudicar, 109 proteínas.

### 2.4 Afirmaciones suyas que aceptamos sin verificar

Están en `abierto` y no en `verificado`, que es lo honesto. Si tienen la
evidencia a mano, nos ahorran el trabajo:

`R2-ADJ-mitochondrial-cloud` (594 de 598 proteínas serían *X. laevis*, y es el
caso de mayor volumen: 598 de las 790 en revisión), `R2-ADJ-germ-granule`,
`R2-ADJ-tip-body`, `R2-ADJ-leucocyte`, y la afirmación de los cuatro ejes.

---

## 3. Qué les pedimos concretamente

1. **Declaren el commit contra el que miden.** Ver §0.
2. **Prioricen `R2-ADJ-batch`** (53 casos) por proteínas afectadas, no
   alfabéticamente, como hicieron con los nueve anteriores.
3. **Adjudiquen `R1-INT-09`** (`RNA polymerase II, holoenzyme`), que quedó sin
   veredicto en las dos rondas.
4. **Confirmen o corrijan** las cifras de §1.1.
5. Para la migración de cuatro ejes: ¿el eje `taxonomic_scope` derivado de los
   organismos anotados resuelve también `R1-ACT-17` (`refractile_body` está en
   Procariota con una sola proteína de *Eimeria tenella*; `rho_body` está en
   Procariota sin organismo resoluble)? Si sí, son una sola tarea y no dos.

---

## 4. Qué hay en el paquete

| Archivo | Para qué |
|---|---|
| `tests/dataset_baseline.json` | La huella. Empezar por acá |
| `docs/review/findings.csv` | El inventario, 62 filas |
| `scripts/review_ledger.py` | `--check` lo valida y lista los pendientes |
| `database/mappings/_archive/mlo_mapping_decisions.md` §11 y §12 | El razonamiento largo detrás de cada decisión |
| `docs/review/RESPUESTA_A_LA_DEVOLUCION.md` | Nuestra respuesta a la ronda 1, para contexto |

Los archivos de ustedes (`devolucion/`, `ultima/`) están donde los dejaron; el
libro los referencia por `archivo:clave` en vez de copiarlos, así que si
reenvían una versión corregida de cualquiera de ellos, el libro sigue apuntando
al lugar correcto.

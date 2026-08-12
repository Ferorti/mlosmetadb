# MLO Mapping Decisions — MLOsMetaDB v2

**Fecha:** 2026-03-31  
**Archivo de mapping:** `mlo_mapping_complete.csv`  
**Fuentes cubiertas:** PhaseDB, DrLLPS, PhasePro, LLPSDB, CDCODE  

---

## 1. Estructura del archivo de mapping

El archivo `mlo_mapping_complete.csv` tiene cuatro columnas:

| Columna | Descripción |
|---|---|
| `Nombre Original` | Nombre exacto del MLO tal como aparece en la base de datos fuente |
| `Nombre Sugerido` | Nombre canónico unificado en snake_case para MLOsMetaDB |
| `Categoria` | Clasificación biológica del MLO (localización o contexto) |
| `Justificacion Biologica` | Razón del mapeo, con PMID cuando corresponde |

El mapping opera sobre el campo `source_mlo` producido por cada parser. Se aplica en el paso de integración (`integrate.py`) para poblar el campo `unified_mlo` de la tabla final.

---

## 2. Criterios generales de mapeo

### 2.1 Cuándo unificar nombres distintos a un mismo canónico

Se unifica cuando dos o más nombres de fuentes distintas refieren al mismo compartimento biológico con suficiente evidencia de equivalencia composicional y funcional. Los criterios aplicados, en orden de peso:

1. **Identidad composicional documentada**: mismos componentes estructurales marcadores (ej. coilina para Cajal body).
2. **Equivalencia funcional en el mismo organismo**: mismo proceso biológico, misma localización subcelular.
3. **Sinonimia explícita en literatura primaria**: el paper original define el término como sinónimo.
4. **Variantes tipográficas o de capitalización**: diferencias de formato sin cambio semántico.

No se unifica cuando los nombres refieren a estructuras con composición o función diferenciable, aunque sean adyacentes o relacionadas.

### 2.2 Cuándo mantener MLOs separados

Se mantienen separados cuando:
- La literatura distingue composición o función, aunque los MLOs sean espacialmente adyacentes.
- El orgánulo tiene una función específica no capturada por el canónico más general.
- El término proviene de un organismo o compartimento que no tiene equivalente directo en el contexto del canónico.

### 2.3 Cuándo descartar

Se descarta (`DISCARD`) cuando:
- El término es un término GO genérico de localización subcelular, no un MLO (ej. `cytoplasmic microtubule`, `ribonucleoprotein complex`).
- El término está marcado como obsoleto en la fuente.
- El término describe una estructura con membrana o una maquinaria molecular (complejo proteico), no un condensado.

### 2.4 Nomenclatura canónica

Los nombres canónicos (`Nombre Sugerido`) siguen estas reglas:
- snake_case, todo en minúsculas.
- Sin artículos ni preposiciones.
- Suficientemente específicos como para ser unívocos dentro del vocabulario de MLOsMetaDB.
- No son una ontología formal; son un vocabulario controlado interno.

---

## 3. Decisiones específicas de agrupamiento

### 3.1 Centrosoma y estructuras mitóticas asociadas

`Centrosome`, `Spindle pole body`, `Centrosome/Spindle pole body`, `Pericentriolar matrix`, `pericentriolar material`, `Pericentriolar compartment` → **`centrosome`**

El PCM (pericentriolar material) es el componente condensado funcional del centrosoma, no un MLO independiente. Los datos de LLPS del PCM (SPD-5 en C. elegans, pericentrina en humano) describen el mecanismo de ensamblaje del centrosoma, no una estructura separada. El spindle pole body fúngico es el ortólogo funcional del centrosoma animal.

**`Spindle apparatus`** y **`spindle matrix`** → **`spindle_apparatus`** (separado del centrosoma)

La matriz del huso es una estructura proteinácea distinta que embebe los microtúbulos del huso de polo a polo de forma microtúbulo-independiente. Proteínas como BuGZ forman condensados independientes del PCM. Colapsar spindle apparatus con centrosome perdería esta distinción.

### 3.2 Sponge body

**`Sponge body`** → **`sponge_body`** (separado de `p_body`)

Decisión corregida respecto a la primera versión del mapping, donde se había propuesto `p_body`. Los sponge bodies de Drosophila comparten componentes con P-bodies pero tienen composición diferencial entre nurse cells y oocito, contienen estructuras de RE embebidas, y su función primaria es el transporte de ARNm materno, no la degradación. La literatura los trata como granulos distintos con morfología ultraestructural diferenciable.

### 3.3 Axonal TIAR-2 granules

**`axonal TIAR-2 granules`** → **`stress_granule`**

TIAR-2 es el homólogo de TIA-1 en C. elegans y está documentado como marcador de stress granules en la literatura. Los gránulos axonales de TIAR-2 co-localizan con marcadores canónicos de SG y responden a los mismos estímulos. Aunque tienen una función específica en inhibición de regeneración axonal, su identidad como stress granule está establecida en la fuente original (PMID: 31378567).

### 3.4 Nuage, chromatoid body y estructuras germinales relacionadas

**`Chromatoid body`** → **`nuage`**

El chromatoid body es el gran gránulo único de nuage en espermátidas post-meióticas. Es una variante morfológica del nuage masculino, con la misma función en el pathway de piRNA y los mismos componentes marcadores (MVH, TDRD1, TDRD6).

**`IMC (intermitochondrial cement)`** → **`nuage`**

El cemento intermitocondrial es el equivalente del nuage en espermatocitos mamíferos, ubicado entre las mitocondrias del puente intercelular. Morfológica y molecularmente equivalente al nuage perinuclear.

**`P granule`**, **`P-granule`**, **`PGL granules`** → **`p_granule`**

Los gránulos PGL son los componentes scaffolding de los P granules de C. elegans (PGL-1 y PGL-3). No son un MLO separado sino la nomenclatura de los drivers del P granule.

**`Germ granule`** (CDCODE) → **`p_granule`**

En los contextos de CDCODE donde aparece "Germ granule" (zebrafish, Drosophila, humano), el término refiere a equivalentes de P granules según el organismo. Se unifica bajo `p_granule` como término germinal canónico más establecido.

**`Founder granule`** → **`germ_plasm`**

Los gránulos fundadores en embriones de Drosophila son el precursor del germ plasm en el polo posterior. Son el equivalente temporal del germ plasm antes de la formación de los células polares.

**`SIMR foci`** → **`mutator_foci`**

Los focos SIMR-1 en C. elegans son adyacentes a los mutator foci y participan en el mismo pathway de piRNA (procesamiento de piRNA secundario). La literatura los describe como funcionalmente acoplados aunque molecularmente distinguibles. Se agrupan por afinidad funcional, documentando la simplificación.

**`pi-body`** → **`pi_body`** (separado de `p_body` y `p_granule`)

El pi-body contiene el módulo PIWIL2-TDRD1 y es específico del pathway de piRNA primario en gonocitos. Es una estructura perinuclear distinta de P granules y P-bodies, con función y composición diferenciada.

### 3.5 Polycomb bodies

**`PcG body`**, **`PcG chromatin condensates`**, **`Polycomb body`** → **`polycomb_body`**

Todos refieren a los condensados nucleares formados por el complejo PRC1 (especialmente CBX2) en sitios de represión de genes de desarrollo. La terminología varía entre bases de datos pero la identidad biológica es la misma.

**`PcG protein complex`** → **`DISCARD`**

El complejo proteico PRC1/PRC2 es la maquinaria molecular, no el MLO. El MLO es el polycomb body que ese complejo forma.

### 3.6 Nucleolo y subestructuras

**`granular component`** y **`dense fibrillar component`** → **`nucleolus`**

Son subestructuras del nucleolo (GC y DFC respectivamente). Se colapsan porque ninguna base de datos fuente de MLOsMetaDB anota proteínas específicamente "en el GC" o "en el DFC" de forma sistemática — la anotación es siempre al nivel de nucleolo completo. Si en el futuro alguna fuente hace anotaciones a nivel de subestructura, este mapeo debería revisarse.

**`rDNA locus`** (CDCODE) → **`nucleolus`**

El locus de rDNA es el sitio genómico donde se ensambla el nucleolo. CDCODE lo anota como condensado separado, pero biológicamente es el sitio de nucleación del nucleolo, no una estructura independiente.

### 3.7 Heterocromatina y cromatina

**`Heterochromatin`** → **`heterochromatin`**  
**`Euchromatin`** → **`chromatin_compartment`**  
**`Chromatin`** (DrLLPS) → **`chromatin_compartment`**

La eucromatina y la heterocromatina son las dos fases de la cromatina. Se mantiene `heterochromatin` como entrada separada porque tiene una identidad condensado bien definida (HP1α como driver, PMID: 28636597). La eucromatina y el término genérico "Chromatin" de DrLLPS se agrupan en `chromatin_compartment` como término más general.

**`sex body`** → **`heterochromatin`**

El cuerpo de Barr (sex body) es el cromosoma X inactivo condensado, que es heterocromatina facultativa. Su identidad como condensado de HP1 y marcas represivas lo equipara a heterocromatina.

### 3.8 Estructuras de señalización

**`TCR signalosome`** y **`LAT signalosome`** → **`t_cell_signalosome`**

Son componentes del mismo condensado de señalización en la sinapsis inmunológica de células T. LAT es el andamiaje del signalosoma del TCR.

**`Receptor cluster`** y **`membrane cluster`** → **`signaling_cluster`**

Términos genéricos para agrupamientos de receptores en membrana. Se mantiene como categoría catch-all para condensados de membrana sin identidad más específica.

**`Hippo signalosome`** y **`TAZ Condensate`** → entradas separadas (`hippo_condensate`)

El signalosoma de Hippo es citoplasmático (YAP/TAZ inactivo), mientras que el condensado de TAZ es nuclear (YAP/TAZ activo como co-activador transcripcional). Aunque son el mismo pathway, operan en compartimentos distintos con composiciones diferentes. Se unifican bajo `hippo_condensate` dado que ambos son anotados en CDCODE sin suficiente granularidad como para justificar dos entradas.

**`Beta-Catenin Destruction Complex`**, **`DVL2 condensates`**, **`Dishevelled condensate`**, **`LEF1/Beta-catenin condensate`** → **`wnt_signaling_condensate`**

Todos son condensados de la vía Wnt en distintos estados (complejo de destrucción citoplasmático, Dishevelled activado, efector nuclear). Se agrupan como categoría funcional de la vía Wnt. Si en el futuro se requiere granularidad, pueden separarse.

### 3.9 Estructuras virales

**`viroplasm`** y **`viroplasm viral factory`** → **`viroplasm`**  
**`cytoplasmic viral factory`** → **`viral_factory`**  
**`Viral factory`**, **`Viral Factory`**, **`cytoplasmic Virion Assembly Compartments (cVACs)`**, **`LANA body`**, **`HIV core condensate`**, **`RdRp condensates`** → **`viral_factory`**

El viroplasma tiene una identidad específica (rotavirus, reovirus) documentada por composición proteica. La `viral_factory` es un término más general para fábricas virales sin identidad específica asignada. Se mantienen separados.

**`viral replication compartment (VRC)`**, **`Pre-replication compartment (PRC)`**, **`Virus-induced replication (VIR) condensate`**, **`ORC1 bodies`** → **`replication_compartment`**

Todos son compartimentos intracelulares de replicación viral con propiedades de condensado, distintos de la fábrica viral completa (que incluye ensamblaje).

**`SARS-CoV-2 condensate`** y **`FXR-driven SARS-CoV-2 condensate`** → **`sars_cov2_n_condensate`**

Se agrupa con el condensado del nucleocápside de SARS-CoV-2, que es el condensado viral más caracterizado de esa especie.

### 3.10 Estructuras de autofagia

**`ATG condensate`** y **`ATG4B condensate`** → **`pre_autophagosomal_structure`**

Los condensados de proteínas ATG son los PAS (pre-autophagosomal structures) en levaduras. ATG4B en mamíferos participa en la formación de autofagosomas en sitios similares. Se agrupan con el PAS como el equivalente funcional ya definido en el mapping.

### 3.11 MARDO y estructuras de oocito

**`MARDO`** → **`balbiani_body`**

MARDO (Mitochondria-Associated RNP Domain in Oocytes) es el equivalente del cuerpo de Balbiani en oocitos de mamífero (descrito en ratón y humano). Comparte los criterios definitorios del Balbiani body: agregado perinuclear en oocitos tempranos, enriquecido en mitocondrias y material granulofibrilar.

### 3.12 Estructuras procariotas y plastídicas

Se mantienen como entradas separadas con categoría `Procariota` o `Plastídico`:
- `bacterial_rnp_body` (BR-bodies bacterianos)
- `carboxysome` y `Enzyme_shell proteins condensates`
- `degradosome`
- `ftsz_droplet` y variantes
- `parabs_condensate`
- `polyp_granule`
- `polarity_condensate` (PopZ, PodJ en bacterias)
- `chloroplast_stress_granule` y `plant_photobody`
- `plant_signaling_condensate` (OsJAZ2, OsSRO1c, PARCL, RH20)

MLOsMetaDB es multiorganismo, por lo que estas estructuras se incluyen con su categoría documentada.

### 3.13 Condensados sintéticos de CDCODE

Todos los `Synthetic Condensate 000001` a `Synthetic Condensate 000386` → **`synthetic_condensate`**

Son condensados construidos artificialmente para estudiar propiedades biofísicas de LLPS. No corresponden a ningún MLO biológico natural. Se mapean a una categoría única para que puedan filtrarse en análisis downstream si se desea excluirlos.

---

## 4. Términos descartados (DISCARD)

Los siguientes términos de las bases de datos fuente no son MLOs y se descartan en la integración:

| Término | Razón |
|---|---|
| `cytoplasmic microtubule` | Término GO de estructura del citoesqueleto |
| `ribonucleoprotein complex` | Término GO genérico de complejo RNP |
| `intracellular non-membrane-bounded organelle` | Término GO estructural genérico |
| `protein-containing complex` | Término GO genérico |
| `protein complex involved in cell-cell adhesion` | Término GO genérico |
| `extracellular matrix` | Estructura con membrana funcional; no MLO |
| `collagen-containing extracellular matrix` | Idem anterior |
| `obsolete cytoskeletal part` | Término GO obsoleto |
| `PcG protein complex` | Maquinaria molecular, no el MLO |
| `neuron projection` | Término GO de morfología neuronal |
| `synaptosome, neuron projection` | Idem anterior |
| `Microtubule` | Estructura del citoesqueleto |
| `Others` (DrLLPS) | Proteínas sin MLO asignado en DrLLPS; entrada vacía |
| `_` | Placeholder en PhaseDB |

---

## 5. Casos con ambigüedad no resuelta

Los siguientes mapeos implican simplificaciones que deberían revisarse si en el futuro se requiere mayor granularidad:

**`IMP1 RNP granule` / `IMP1 ribonucleoprotein granule`** → `neuronal_granule`  
La literatura los describe como distintos de SGs y P-bodies pero similares a gránulos neuronales. La composición se solapa con neuronal granule (IMP, ribosomas, Staufen) pero también hay diferencias. Es un agrupamiento pragmático.

**`SIMR foci`** → `mutator_foci`  
Los focos SIMR-1 y los mutator foci son adyacentes y funcionalmente acoplados en piRNA, pero molecularmente distinguibles. La evidencia actual no justifica entradas separadas en una base integrada, pero la simplificación es documentada.

**`Hippo signalosome`** y **`TAZ Condensate`** → `hippo_condensate`  
Son estados distintos (citoplasmático activo vs nuclear) del mismo pathway. Si CDCODE agrega granularidad en versiones futuras, puede justificarse separación.

**`sex body`** → `heterochromatin`  
El cuerpo de Barr tiene propiedades de condensado documentadas pero también es una estructura cromosómica con identidad citológica propia. El agrupamiento bajo `heterochromatin` es funcional pero puede perderse la especificidad.

---

## 6. Cobertura del mapping por fuente

| Fuente | Entradas cubiertas | Observaciones |
|---|---|---|
| PhaseDB | Todas | Headers confirmados; `mlo_entries` sin header usa posiciones |
| DrLLPS | Todas | `Droplet` → `in_vitro_droplet`; `Others` → DISCARD |
| PhasePro | Todas | Sin header; posición col[14] para MLO confirmada |
| LLPSDB | Todas | `in_vitro_droplet` fijo; sin campo MLO en la fuente |
| CDCODE | 766 entradas | 386 sintéticos → `synthetic_condensate`; 64 ya cubiertos por mapping original; 120 nuevos MLOs biológicos |

---

## 7. Valores especiales en unified_mlo

| Valor | Significado |
|---|---|
| `in_vitro_droplet` | LLPS determinado solo in vitro; sin MLO celular asignado (DrLLPS `Droplet`, toda LLPSDB) |
| `synthetic_condensate` | Condensado sintético de CDCODE; no biológico |
| `NULL` (en source_role) | Rol no informado en la fuente (toda CDCODE, NotInformed en PhaseDB pre-v2) |

---

## 8. Actualizaciones futuras

Para mantener la reproducibilidad del mapping en versiones futuras:

1. Cualquier nombre de MLO nuevo en las fuentes que no esté en `mlo_mapping_complete.csv` debe agregarse antes de correr `integrate.py`, o el integrador lo dejará como `unmapped` con advertencia.
2. Los condensados sintéticos de CDCODE tienen numeración secuencial; si CDCODE agrega nuevos, seguirán el patrón `Synthetic Condensate 000NNN` y se mapearán automáticamente si el parser de CDCODE los detecta como tipo `synthetic`.
3. El vocabulario canónico (`Nombre Sugerido`) no es una ontología formal. No debe modificarse sin actualizar también la documentación de este archivo para mantener trazabilidad.


## 9. Revisiones v3 — correcciones basadas en definiciones de CDCODE

**Fecha:** 2026-04-29  
**Archivo actualizado:** `mlo_mapping_v2.csv` (= mapping v3)  
**Motivo:** La incorporación de las definiciones textuales de CDCODE 
(`condensates_202603181647.csv`) permitió revisar asignaciones que se 
habían hecho sin acceso a esa información. Se identificaron 21 
reclasificaciones y 2 eliminaciones de duplicados conflictivos.

---

### 9.1 Conflictos de duplicado eliminados

Dos nombres de fuente aparecían dos veces con canonicals distintos:

- `cytoplasmic protein granule`: mapeaba a `cytoplasmic_protein_granule` 
  y a `cytoplasmic_rnp_granule`. Se elimina la entrada hacia 
  `cytoplasmic_rnp_granule`; se mantiene `cytoplasmic_protein_granule` 
  como término catch-all genérico.
- `galectin complex`: mapeaba a `galectin_lattice` y a 
  `galectin_condensate`. Se elimina la entrada hacia `galectin_condensate`; 
  galectin complex y galectin lattice refieren al mismo objeto biológico.

---

### 9.2 Reclasificaciones de `stress_granule`

Cinco entradas de CDCODE estaban asignadas a `stress_granule` sin 
definición disponible al momento del mapping original. Con las 
definiciones de CDCODE:

- **`SCOTIN condensate`** → `eres_condensate`  
  SCOTIN/SHISA-5 forma condensados en la membrana del RE que secuestran 
  Sec31/13 e impiden el tráfico ER-Golgi. No es un stress granule.

- **`YBX1 condensate`** → `exosomal_condensate`  
  YBX1 forma condensados que reclutan miRNAs (miR-223) hacia exosomas 
  secretados. La función primaria es en biogénesis de exosomas, no en 
  respuesta al estrés.

- **`RPSA-VIM-ENO Condensate`** → `viral_factory`  
  Condensado de RPSA/vimentina/enolasa amplificado por enolasa de 
  *Streptococcus suis* en contexto infeccioso. Es un condensado de 
  fábrica infecciosa, no un stress granule.

- **`HSP condensate`** → `signaling_condensate`  
  HSP48 en *Dictyostelium discoideum* forma condensados estabilizados por 
  polifosfato durante el desarrollo. No corresponde a un stress granule 
  canónico sino a un condensado de chaperones de desarrollo.

- **`PCBP2 condensates`** → `signaling_condensate`  
  PCBP2 secuestra proteínas de unión mitocondrial y controla el decay de 
  BACE1 mRNA; función en señalización mitocondrial, no en respuesta al 
  estrés.

---

### 9.3 Reclasificaciones de `transcriptional_condensate`

Cuatro entradas colapsadas en `transcriptional_condensate` tienen 
identidades más específicas según sus definiciones:

- **`TAZ Condensate`** → `hippo_condensate`  
  TAZ es el efector nuclear de la vía Hippo. Sus condensados reclutan 
  co-activadores transcripcionales (TEAD4, BRD4, CycT1), pero la 
  identidad primaria de TAZ es como efector de Hippo, no como componente 
  de la maquinaria transcripcional genérica.

- **`Nur77 condensate`** → `signaling_condensate`  
  Nur77 forma condensados en mitocondrias ubiquitinadas promoviendo 
  apoptosis. Es un condensado citoplasmático de señalización 
  pro-apoptótica, no transcripcional.

- **`METTL14 condensate`** → `nuclear_speckle`  
  METTL14 modifica m6A de ARNm en condensados nucleares. Función en 
  procesamiento post-transcripcional de ARN mensajero, más cercana a 
  nuclear speckles que a condensados transcripcionales.

- **`eukaryotic topoisomerase ii`** → `chromatin_compartment`  
  Topo II eucariota forma condensados sobre el supercoiling cromosómico a 
  concentraciones fisiológicas. Es un componente de la organización de 
  cromatina, no específicamente transcripcional.

---

### 9.4 Reclasificaciones de `nuclear_body`

Cuatro entradas asignadas al catch-all `nuclear_body` tienen identidades 
definidas según CDCODE:

- **`NP bodies`** → `norad_pum_body`  
  NP bodies son condensados de Pumilio inhibido por el lncRNA NORAD que 
  previenen mitosis aberrante. Son el equivalente del `norad_pum_body` ya 
  definido como canonical.

- **`TRIM45 bodies`** → `DISCARD`  
  La definición de CDCODE es únicamente "Cytoplasmic Puncta". Evidencia 
  insuficiente para clasificar como MLO. Adicionalmente la localización 
  citoplasmática es inconsistente con el canonical `nuclear_body` 
  previamente asignado.

- **`AFAP1-AS1 condensates`** → `nuclear_speckle`  
  AFAP1-AS1 regula splicing alternativo reclutando factores de splicing. 
  Composición y función más cercana a nuclear speckle que a un nuclear 
  body genérico.

- **`nYAC`** → `transcriptional_condensate`  
  nYAC son condensados nucleares de YTHDC1 y m6A que mantienen células 
  AML en estado indiferenciado regulando la transcripción. Son condensados 
  transcripcionales/epigenéticos con función definida, no nuclear bodies 
  genéricos.

---

### 9.5 Reclasificaciones de `signaling_condensate`

Dos entradas tienen identidad más específica como moduladores de la vía 
Hippo:

- **`DDR1 condensate`** → `hippo_condensate`  
  DDR1 en células musculares lisas vasculares contrarresta 
  específicamente la vía YAP-Hippo inducida por rigidez y colágeno.

- **`NEDD4 condensates`** → `hippo_condensate`  
  NEDD4 compartimentaliza YAP1 y su quinasa NLK, controlando la 
  fosforilación de YAP1 en Ser128. Es un modulador directo de la vía 
  Hippo.

---

### 9.6 Reclasificaciones de `aggresome`

Dos entradas asignadas a `aggresome` tienen mecanismos distintos:

- **`BAG2`** → `proteasome_foci`  
  BAG2 condensates facilitan la degradación por proteasoma 20S 
  independiente de ubiquitina bajo estrés hiperosmótico. El mecanismo y 
  la función son más cercanos a `proteasome_foci` que a un aggresome.

- **`Plectin condensates`** → `signaling_condensate`  
  Plectina via su IDR promueve diferenciación osteoblástica secuestrando 
  Anxa2 por phase separation. Es un condensado de señalización de 
  diferenciación celular, no un depósito de proteínas mal plegadas.

---

### 9.7 Otras correcciones

- **`Mimi granules`** → `neuronal_granule` (era `p_granule`)  
  Gránulos Mimi en *Drosophila* contienen ARNm y proteínas de procesos 
  sinápticos. Su pérdida produce deterioro de señalización por 
  neuropéptidos y neurodegeneración. Son gránulos neuronales, no 
  germinales.

- **`Nuclear poly(A) domains`** → `maternal_mrna_condensate` (era 
  `nuclear_speckle`)  
  Los NPADs son condensados de ARNm recién transcrito en oocitos en 
  desarrollo, ligados a infertilidad femenina y fallo ovárico prematuro. 
  No son nuclear speckles sino hubs de transcritos maternos.

- **`SSB condensate`** → `signaling_condensate` (era `dna_damage_foci`)  
  SSB bacteriano (procariota) almacena proteínas de reparación de DNA y 
  se disuelve bajo estrés genómico para movilizarlas rápidamente. Es un 
  depósito regulatorio procariota, no un foco de daño al DNA eucariota.

- **`synaptosome`** → `DISCARD` (era `neuron projection` con espacio 
  inicial — entrada malformada)  
  El sinaptosome es una estructura con membrana plasmática; no es un MLO. 
  La entrada tenía además un canonical con espacio inicial que violaba el 
  formato snake_case.



## 10. Revisiones v4 — correcciones por revisión externa (mapping v3 mlo_unified_definitions_phasepro_phasepdb_cdcode_v3)

**Fecha:** 2026-04-29  
**Archivo actualizado:** `mlo_mapping_v3.csv`  
**Motivo:** Revisión externa identificó 10 posibles correcciones. Se 
evaluaron con criterio biológico y de cobertura del dataset. Se aplicaron 
6; se rechazaron 4 por no tener soporte en las fuentes actuales o por 
implicar granularidad excesiva para una base integrada.

---

### 10.1 Correcciones aplicadas

**`Spindle pole body` / `Centrosome/Spindle pole body` / `Spindle pole`
→ `spindle_pole_body`**  
El SPB fúngico está embebido permanentemente en la membrana nuclear 
(mitosis cerrada) y es estructuralmente no homólogo al centrosoma 
metazoo. Equivalencia funcional como MTOC no justifica unificación dada 
la diferencia arquitectural, composición proteica y mecanismo de 
duplicación. Se crea el canonical `spindle_pole_body` separado de 
`centrosome`.

**`Chromatoid body` → `chromatoid_body`** (separado de `nuage`)  
El cuerpo cromatoide es post-meiótico, aparece en espermátidas y se 
asocia al aparato de Golgi. El IMC (inter-mitocondrial cement) es 
meiótico, perinuclear, y asociado a mitocondrias. Son estadios y 
estructuras distintos. El IMC se mantiene en `nuage` por ser la forma 
meiótica del nuage masculino; el chromatoid body recibe canonical propio.

**`Beta-Catenin Destruction Complex` / `Destruction complex condensate`
→ `wnt_destruction_complex`** (separado de `wnt_signaling_condensate`)  
El complejo de destrucción es citoplasmático, estado Wnt-OFF, nucleado 
en el centrosoma. El signalosoma de Wnt (DVL, LEF1/β-catenina) es 
membrana/nuclear, estado Wnt-ON. Son condensados físicamente distintos, 
espacialmente separados, con composiciones y funciones opuestas. DVL2 y 
Dishevelled se mantienen en `wnt_signaling_condensate`.

**`MARDO` → `mardo`** (separado de `balbiani_body`)  
El cuerpo de Balbiani en oocitos tempranos tiene propiedades 
amiloides/sólidas (PMID:27135929). El MARDO es un hidrogel de etapa 
tardía en oocitos de mamífero con composición molecular propia. Son 
biofísicamente distintos y corresponden a estadios diferentes de la 
oogénesis.

**`SIMR foci` → `simr_foci`** (separado de `mutator_foci`)  
Los focos SIMR-1 en *C. elegans* median la transición entre piRNA 
primario (pi-bodies) y secundario (mutator foci), con componentes propios 
(SIMR-1, ENRI-1). Son molecularmente separables de los mutator foci 
aunque adyacentes. La simplificación anterior estaba admitida como 
pendiente en el decisions.md.

**`sex body` → `sex_body`** (separado de `heterochromatin`)  
El cuerpo de Barr (cromosoma X inactivo) tiene organización en capas y 
dinámica molecular específica (XIST, SHARP, HDAC3) que lo distingue de 
la heterocromatina constitutiva HP1α-driven. Son tipos de heterocromatina 
funcionalmente distintos: facultativa (Xi) vs constitutiva (centromérica).

**`axonal TIAR-2 granules` → `axonal_tiar2_granule`**  
La homología con TIA-1 no implica identidad de compartimento. Los
gránulos axonales de TIAR-2 se forman post-lesión, se localizan en el
axón distal, y funcionan como inhibidores de regeneración del cono
axonal — no como respuesta protectora de ARNm. Estímulo, localización y
función son suficientemente distintos del stress granule canónico para
justificar canonical propio. Aceptado en segunda revisión tras argumento
de que confundir homología proteica con identidad de compartimento es un
error categorial. [PMID:31378567]

---

### 10.2 Correcciones rechazadas

**`granular component` → `nucleolar_subcompartment`**  
Biológicamente correcto — el GC tiene subfases inmiscibles y una cuarta 
capa de anclaje a cromatina. Rechazado porque ninguna fuente del dataset 
(PhaseDB, DrLLPS, PhasePro, CDCODE) anota proteínas a nivel de 
subestructura nucleolar de forma sistemática. Crear el canonical sin 
cobertura de datos genera una entrada vacía. Revisable si una fuente 
futura hace esa distinción.


**`PcG body` → `prc1_condensate` / `prc2_condensate`**  
PRC1 y PRC2 forman condensados con mecanismos distintos, pero ninguna 
fuente del dataset distingue sistemáticamente entre condensados de PRC1 
y PRC2 en sus anotaciones. Crear dos canonicals sin cobertura de datos 
es equivalente al caso del GC nucleolar. Las entradas de PhaseDB, DrLLPS 
y CDCODE refieren al cuerpo de Polycomb visible por microscopía, que es 
predominantemente PRC1. Se mantiene `polycomb_body`.

**`YBX1 condensate` → `ybx1_sorting_condensate`**  
La especialización funcional de YBX1 como plataforma de sorting de 
miRNAs es real, pero `exosomal_condensate` captura esa especificidad 
suficientemente para una base integrada. Crear un canonical 
proteína-específico (`ybx1_sorting_condensate`) implicaría el mismo 
principio para decenas de proteínas con funciones especializadas en 
exosomas. Rechazado por granularidad excesiva para el nivel de resolución 
de MLOsMetaDB.

### 10.3 Nota sobre IMC

La revisión externa propuso separar `IMC (intermitochondrial cement)` de
`nuage` argumentando discontinuidad temporal (meiótico vs post-meiótico).
Se rechaza la separación del IMC porque el término nuage refiere
morfológicamente al material granulofibrilar perinuclear electrón-denso
en células germinales, y el IMC cumple esa definición en espermatocitos.
Lo que era incorrecto era colapsar el **cuerpo cromatoide** con el IMC
bajo `nuage` — eso ya fue corregido separando `chromatoid_body`. El IMC
→ `nuage` se mantiene.
---

## 11. Revisión v5 — auditoría biológica externa (2026-08-08)

Devolución completa en `docs/review/devolucion/`. La auditoría corrió sobre una
copia previa al fix de doble ingesta de PhaSepDB, así que sus dos acciones
bloqueantes de ingesta (colapsar los tags `PhaseDB`/`PhasePDB` y normalizar las
filas por PMID) ya estaban resueltas al recibirla; se verificó contra la base
actual antes de descartarlas.

Se revisaron 242 equivalencias: 160 correctas, 64 pendientes de curador, 18
errores. Esta revisión aplica los 18 errores y las correcciones de esquema que
no dependen de criterio biológico. Los 64 casos "a revisar" quedan abiertos —
necesitan que un curador lea la publicación original.

### 11.1 Etiquetas compuestas sin explotar

La regla de explosión de compuestos cubría el separador `;` pero no los
patrones `X/Y` ni `X and Y`. Dos etiquetas se colaron, y entre las dos
concentran el 95% de las proteínas afectadas por errores de equivalencia.

**`Centrosome/Spindle pole body` → `centrosome`** (default) **+
`spindle_pole_body`** (filas fúngicas).
DrLLPS usa una sola etiqueta para ambas estructuras. De las 910 filas, 775 son
de organismos sin cuerpo polar del huso (humano 533, ratón 130, *Drosophila*
66, *C. elegans* 32) y solo 135 son fúngicas (*S. cerevisiae* 87, *S. pombe*
48). Mandarlas todas al término fúngico hacía desaparecer el proteoma del
centrosoma de metazoos y llevaba `spindle_pole_body` al puesto 11 del
inventario.

`mlo_mapping.csv` no puede expresar una etiqueta cuyo significado depende del
organismo, así que se agrega **`database/mappings/mlo_organism_scoped.csv`**:
el mapeo principal fija el default y ese archivo redirige las filas que
matchean un organismo. `source_mlo` nunca se reescribe — la DB conserva la
etiqueta que usó la fuente.

*Imprecisión conocida:* las 12 filas de *Arabidopsis* caen en el default
`centrosome` y las plantas son acentrosómicas. La regla de la auditoría solo
cubre fúngico vs. metazoo, e inventar un tercer destino iría más allá del
hallazgo.

**`Presynaptic clusters and postsynaptic densities` → `synaptic_compartment`**
(canónico nuevo). Etiqueta de CD-CODE que nombra los dos lados de la sinapsis:
1.366 proteínas humanas, una por fila. Todo iba a `presynaptic_active_zone` y
la mitad postsináptica se perdía sin registro. Se descartaron duplicar cada
proteína en ambos canónicos (afirma más de lo que dice la fuente) y descartar
el conjunto como fracción bioquímica. La fuente anota a resolución de sinapsis
y no distingue lados: el canónico refleja esa resolución, que es la misma regla
de "la cobertura limita la granularidad" aplicada en §10.

### 11.2 XY body / sex body: dos nombres de una estructura, tres descripciones

`XY body` estaba fusionado a `heterochromatin` sin compartir **ninguna**
proteína con él en el mismo recurso y organismo: sus 10 proteínas (Topbp1,
Mdc1, Brca1) son maquinaria de respuesta a daño reclutada en el silenciamiento
meiótico del cromosoma sexual. Su justificación remitía a `sex body`, que
existía como canónico pero cuya justificación describía el **cuerpo de Barr**.

Al revisar las proteínas de `sex body` (Rnf212, recombinación meiótica) queda
claro que esa etiqueta también es el cuerpo sexual meiótico, y que el error
estaba en su texto. `XY body` y `sex body` son sinónimos en la literatura:
ambos van a **`xy_body`** (Germinal) y `sex_body` desaparece.

**No se crea `barr_body`**: ninguna fuente lo anota, y la regla de cobertura
aplica igual que en §10.

### 11.3 `polarity_condensate`: tres sistemas biológicos, cero composición común

El dossier ya pedía veredicto sobre este canónico y la auditoría lo confirma
como fusión indebida: agrupaba por la palabra "polaridad", no por composición.
Se abre en tres:

| Nombres fuente | → canónico | Categoría |
|---|---|---|
| `PodJ condensates`, `PopZ condensate` (*Caulobacter*) | `bacterial_polarity_condensate` | Procariota |
| `Fus1 condensate` (*S. pombe*) | `fusion_focus` | Citoesqueleto |
| `Par complex`, `Numb/Pon condensate`, `basal Numb-Pon crescent in dividing neuroblasts` | `cell_polarity_condensate` | Neuronal |

### 11.4 Resto de los errores de equivalencia

| Nombre fuente | Antes | Ahora | Razón |
|---|---|---|---|
| `inclusion body-associated granule (IBAG)` | `inclusion_body` | `viral_factory` | Subcompartimiento de inclusiones de replicación del VRS (M2-1 + eIF4F), no un agregado patológico |
| `P6 inclusion body` | `inclusion_body` | `viral_factory` | Factoría del virus del mosaico de la coliflor en células vegetales |
| `TIFA-TRAF6 Condensate` | `inflammasome` | `tifasome` | ALPK1-TIFA-TRAF6 activa NF-κB sin sensor NLR, sin mota de ASC y sin caspasa-1 |
| `Proteasome Storage Granule` | `proteasome_foci` | `proteasome_storage_granule` | Estructura citoplasmática de quiescencia en levadura; el canónico agrupaba cuerpos proteasomales nucleares |
| `SSB condensate` | `signaling_condensate` | `dna_damage_foci` | Replicación y reparación de ADN, no señalización (revierte la reclasificación de v3) |
| `DDR1 condensate` | `hippo_condensate` | `signaling_cluster` | Receptor tirosina quinasa de colágeno, no vía Hippo |
| `FATZ-1 condensate` | `postsynaptic_density` | `z_disc_condensate` | MYOZ1 es del disco Z sarcomérico; probable match por similitud de nombre |
| `α-synuclein condensates`, `α-synnuclein condensates` | `synapsin_condensate` | `alpha_synuclein_condensate` | Ensamblajes distintos que coexisten en el presináptico; incluye normalizar la variante mal escrita |
| `Plectin condensates` | `signaling_condensate` | `plectin_condensate` | Entrecruzamiento de filamentos intermedios, citoesquelético |
| `HSP condensate` | `signaling_condensate` | `chaperone_condensate` | Chaperonas de desarrollo en *Dictyostelium* |
| `ABC transporter condensate` | `bacterial_rnp_body` | `abc_transporter_condensate` | Transporte de membrana en *Mycobacterium*; los BR-bodies son gránulos de RNP nucleados por RNasa E |
| `Cytoplasmic protein granule` | `cytoplasmic_rnp_granule` | `cytoplasmic_protein_granule` | La misma etiqueta se repartía entre dos canónicos según su capitalización |
| `Golgi ribbon` | `golgin_condensate` | `DISCARD` | Disposición de organela con membrana, fuera de la definición de MLO |

**`Large dense-core vesicles` se mantiene en `chromogranin_condensate`.** La
auditoría lo marca error porque la etiqueta nombra la vesícula con membrana y
no el condensado. Pero su propio razonamiento es que el condensado *es* el
núcleo denso intravesicular, y eso es exactamente `chromogranin_condensate`.
Descartarlo habría eliminado SEMG2 del dataset por completo (era su única
anotación) y roto el invariante de que toda proteína tiene al menos una
anotación. Se corrige la justificación para que no equipare continente y
contenido, y se conserva la asignación.

### 11.5 Categorías: de arbitrarias a curadas

23 canónicos tenían `Categoria` en conflicto entre sus filas fuente, y el
loader resolvía por orden de lectura del archivo (`INSERT OR IGNORE`), o sea
que la categoría almacenada era arbitraria. Seis de esos conflictos no eran
biología: **`Citoplasma` y `Citoplasmático` eran la misma categoría con dos
grafías** y se unificaron.

Los 17 restantes recibieron una categoría curada, con este criterio en orden:

1. Si el término es exclusivo de un dominio taxonómico o de un tipo celular,
   gana esa etiqueta — es como el esquema ya trata Viral, Vegetal, Procariota,
   Germinal y Neuronal.
2. Si no, gana el compartimiento, usando `compartment_class` de
   `docs/review/devolucion/category_scheme_proposed.csv` como referencia.
3. Ante empate, la mayoría de las filas fuente.

Dos merecen nota: **`plant_photobody` pasó de Plastídico a Vegetal** porque los
fotocuerpos de phyB son nucleares y no plastídicos (ninguna de las dos opciones
del archivo era correcta, Vegetal es la menos incorrecta bajo un eje único), y
**`maternal_mrna_condensate` pasó de Nuclear a Germinal** por tratarse de hubs
de transcriptos maternos en ovocitos.

El loader ahora **falla** ante una `Categoria` en conflicto en vez de elegir en
silencio.

### 11.6 Lo que esta revisión NO hace

> El inventario completo y su estado vive en `docs/review/findings.csv`
> (`python3 scripts/review_ledger.py --check`). Esta sección explica el
> razonamiento; el libro lleva la cuenta.

- El reemplazo de `Categoria` por los cinco ejes ortogonales que propone la
  auditoría (`category_scheme_proposed.csv`). Cambia el esquema de la DB, la
  API y el frontend (`R1-ACT-06`).
- Agregar `evidence_type` a cada anotación para distinguir "separa de fase in
  vitro" de "es necesaria en células".
  - **Resuelto en v6** (`R1-ACT-08`, commit `45102ca`): ver §12.4.
- Eliminar `NotInformed` e `in_vitro_droplet` del vocabulario de organelas
  (`R1-ACT-10`, `R1-ACT-11`).
- Reinstaurar los reguladores de DrLLPS como tercer valor de rol (hoy 1.389
  aserciones con `dataset_active=0`, de las cuales 502 proteínas no aparecen
  por ningún otro lado) (`R1-ACT-14`).
- Los 64 casos "a revisar" de `equivalence_verdicts.csv` (`R1-ACT-16`).
  - **Parcialmente resuelto en v6** (`R1-ACT-16`): de los 64, 9 fueron
    adjudicados en la segunda ronda —2 aplicados (`R2-ADJ-pcbp2`,
    `R2-ADJ-risc`), 4 cerrados como correctos por la devolución pero sin
    verificar de nuestro lado (`R2-ADJ-mitochondrial-cloud`,
    `R2-ADJ-germ-granule`, `R2-ADJ-tip-body`, `R2-ADJ-leucocyte`) y 3 que
    requieren la publicación (`R2-ADJ-perinucleolar`, `R2-ADJ-orc1`,
    `R2-ADJ-receptor-cluster`)—; los 53 restantes siguen abiertos en
    `R2-ADJ-batch`. Ver §12.3.
- Mover los PMIDs de `evidence` a una tabla de evidencia con clave foránea,
  la mitad de la acción 1 que sigue pendiente (`R1-ACT-01b`).
- Indicar por MLO si algún recurso aporta proteoma masivo de clientes, para
  no publicar `driver_share` sin esa advertencia (`R1-ACT-12`).
- Derivar `taxonomic_scope` de los organismos anotados y corregir
  `refractile_body` y `rho_body`: confirmado que `refractile_body` está en
  Procariota con una sola proteína, de *Eimeria tenella* (apicomplejo), y que
  `rho_body` está en Procariota sin ningún organismo resoluble (`R1-ACT-17`).
- Definir el vocabulario de sufijos estructurales y aplicarlo
  consistentemente (`R1-ACT-18`).
- Documentar las tres vías de exclusión (`DISCARD`, `synthetic_condensate`,
  `NULL`) como un mecanismo único con motivo (`R1-ACT-20`).
- Redefinir el límite biológico entre `cytoplasmic_protein_granule` y
  `cytoplasmic_rnp_granule` (`R1-ACT-21b`).
- Adjudicar `RNA polymerase II, holoenzyme` (2 filas en
  `transcriptional_condensate`, que tiene 220 en total): INT-09 solo pedía
  mandarla a la revisión de descarte y nunca recibió veredicto; ver §12.3
  (`R1-INT-09`).
- Marcar en la UI los canónicos de baja evidencia, los que dependen de un
  solo PMID (5.244 filas llevan más de un PMID, 131 canónicos tienen alguna
  evidencia). La mitad documental ya está hecha —SCHEMA.md y BIOLOGY.md dicen
  que `evidence` es procedencia de fila, no prueba del par proteína-MLO—; la
  marca en la UI es trabajo de frontend (`R1-INT-04`).
- Reportar cobertura de rol por MLO junto a cualquier estadística de rol, y
  nunca calcular fracción de drivers sobre filas de recursos sin rol: el
  42,4% de las aserciones (15.233 de 35.968) no tiene rol y la ausencia está
  determinada enteramente por el recurso (CDCODE más los Regulator de
  DrLLPS). `evidence_type` ya hace explícita la causa (`membership_only`),
  pero eso registra y no reporta (`R1-ROL-02`).
- Publicar como tabla de QC el conjunto de desacuerdos de rol entre recursos:
  el desacuerdo PhaSepDB vs. PhasePro (58,6%) fue el que motivó
  `evidence_type` y quedó citado en SCHEMA.md, pero `evidence_type` se
  definió desde la tabla `(source_db, source_role)` y no desde el conjunto de
  desacuerdos mismo (`R1-ROL-05`).
- Ponderar o marcar, al calcular enriquecimiento de drivers, las aserciones
  que vienen de recursos que solo dicen driver: 577 de 3.068 (18,8%, LLPSDB
  380 + PhasePro 197). `evidence_type = in_vitro_llps` ya identifica
  exactamente esos dos recursos; ponderarlos es decisión de quien calcule el
  enriquecimiento (`R1-ROL-07`).

**Registrado y rechazado.** La auditoría pide una regla de precedencia
explícita para las 214 tripletas (proteína, MLO) —sobre 182 proteínas
distintas— que en PhaSepDB reciben `driver` y `client` a la vez desde sus dos
exports. Se rechaza a propósito: PhaSepDB publica un dataset curado de
drivers y otro de componentes por separado, y ser driver es un experimento
distinto de ser detectado dentro del condensado. Las dos anotaciones se
conservan con sus PMIDs y el rol es parte de la clave de deduplicación (ver
"Driver vs. Component" en `BIOLOGY.md`); `R1-INT-02`.

---

## 12. Revisión v6 — segunda devolución de la auditoría (2026-08-10)

Documento en `docs/review/ultima/`. Verifica los conteos de cierre de v5,
revisa las cuatro decisiones donde nos apartamos de la recomendación, y responde
las seis consultas de `docs/review/RESPUESTA_A_LA_DEVOLUCION.md` §6.

De las cuatro decisiones de v5: **dos aceptadas** (`xy_body`/`sex_body` y
`Large dense-core vesicles`, en ambos casos indicando que nuestra lectura era
mejor que la suya), **una revertida** (`synaptic_compartment`) y **una
corregida** (MTOCs vegetales).

### 12.1 `synaptic_compartment` se retira

v5 le había dado canónico propio a `Presynaptic clusters and postsynaptic
densities` para no inventar un reparto que la fuente no provee. El dato lo
resuelve sin necesidad de la publicación, que era lo que habíamos pedido:

| | proteínas |
|---|---:|
| Total en `synaptic_compartment` | 1.366 |
| También en `postsynaptic_density` (cualquier recurso) | 1.360 |
| — de las cuales por **DrLLPS** | **1.353** |
| — por CD-CODE | 3 |
| También en `presynaptic_active_zone` | 3 |
| Exclusivas | 6 |

**Dos precisiones sobre el argumento de la devolución.** Dice que el
solapamiento es «en el mismo recurso» y que se trata de una reexportación
redundante de la entrada de PSD de CD-CODE: no es así, 1.353 de las 1.360 vienen
de DrLLPS y solo 3 de CD-CODE. Y dice que las filas de `synaptic_compartment`
tienen `evidence` nula «mientras la entrada de PSD de CD-CODE lleva PMID
23071613»: **ninguna fila de CD-CODE lleva PMID en esta base**, por diseño del
export (0 de 13.844). Ese PMID debe estar en los metadatos del condensado en
CD-CODE, no en la anotación.

La conclusión igual se sostiene, y con mejor fundamento del que ellos creían
tener: la coincidencia es **entre recursos independientes**, que es evidencia
real, y no duplicación intra-recurso, que sería un artefacto de ingesta. Que
1.353 proteínas estén anotadas como PSD por DrLLPS y solo 3 como presinápticas
identifica el conjunto como el proteoma de la PSD. La etiqueta pasa a ser
sinónimo de `postsynaptic_density`.

Pendiente menor: las 6 proteínas exclusivas (O43236, P17152, Q14DG7, Q5VSY0,
Q6P995, Q9NQR7) merecen revisión aparte; la devolución señala que una de ellas
es mitocondrial.

### 12.2 `plant_mtoc`

Las 12 filas de *Arabidopsis* que el split por organismo de v5 había dejado caer
en `centrosome` —documentado entonces como imprecisión conocida— son TUBG1,
GCP3, GCP4, NEDD1, GIP1 (complejo γ-TuRC), TON1A, TPX2, EB1A, EB1C, KIN14D, AAA1
(maquinaria TON1/TRM) y TUBA1. Nucleación acentrosómica de microtúbulos, con
γ-tubulina dispersa en envoltura nuclear y corteza, sin centríolos. Las plantas
no tienen centrosoma ni cuerpo polar del huso, así que ninguno de los dos
destinos del split les correspondía. La lista de genes es diagnóstica y no
requiere la publicación.

Nuevo canónico `plant_mtoc`, categoría Vegetal, declarado en
`mlo_organism_scoped.csv`. **Es el primer canónico que no existe en
`mlo_mapping.csv`**, porque ningún nombre fuente apunta a él sin condición de
organismo: `build_db.py` ahora lee ambos archivos al armar el vocabulario.

### 12.3 Casos «review» cerrados

De los 64 originales, 62 siguen vivos en v5 y suman 790 proteínas, con
`Mitochondrial cloud` concentrando 598 de ellas. Nueve fueron adjudicados desde
las listas de genes, sin leer publicaciones.

**Cerrados como correctos, sin cambio:**

- `Mitochondrial cloud` → `balbiani_body`. En ovocito de *Xenopus* la nube
  mitocondrial *es* el cuerpo de Balbiani; 594 de 598 proteínas son *X. laevis*.
- `Germ granule` → `p_granule`. osk, vas, tej, spn-E, me31B, tdrd6 son plasma
  germinal canónico. Esto cierra el merge que el dossier había marcado como «el
  que más nos gustaría que cuestionaran».
- `+TIP body` → `spindle_apparatus`. KAR9/BIM1/BIK1 y mal3/tea2/tip1 son los
  complejos de rastreo de extremo más; defendible aunque grueso.
- `Leucocyte nuclear body` → `nuclear_body`, correcto pero pierde información:
  «leucocito» es contexto de tipo celular, que el esquema de ejes recuperaría.

**Aplicados:**

- `PCBP2 condensates` sale de `signaling_condensate` a `cytoplasmic_rnp_granule`.
  DCP1A y DDX6 son maquinaria de decapping y cuerpo P, TIA1 es marcador de
  gránulo de estrés. Se elige el término general y no `p_body` porque el conjunto
  mezcla ambas cosas.
- `RISC complex` a `DISCARD`, por nombre de complejo macromolecular. Verificado
  sin pérdida: `mirisc` conserva sus 8 filas restantes y sus mismas 2 proteínas
  (AGO2, TNRC6B) por la etiqueta `miRISC`.

**No aplicado, contra lo que la devolución supone:** `RNA polymerase II,
holoenzyme` (2 filas en `transcriptional_condensate`). La devolución la describe
como «ya marcada para descarte» al justificar el descarte de `RISC complex`,
pero **nunca recibió veredicto**: INT-09 de la primera ronda solo pedía mandarla
a la revisión de descarte, y no aparece ni en `discard_review.csv` ni en
`equivalence_verdicts.csv`. Queda pendiente de adjudicación explícita.

**Pendientes que requieren la fuente** (35 proteínas en total), registrados sin
tocar los datos:

| nombre fuente | canónico actual | proteínas | diagnóstico |
|---|---|---:|---|
| `Receptor cluster` | `signaling_cluster` | 24 | Mezcla sinapsis inmune (LAT, NCK1, SOS1, WASL), SNAREs de exocitosis (Snap25, Stx1a) y señalización antiviral (MAVS, IRF3). No es un compartimiento: split o descarte |
| `Peri-nucleolar condensate` | `perinucleolar_compartment` | 6 | HSP104 y SIS1 marcan el compartimiento yuxtanuclear de control de calidad (JUNQ/INQ) en levadura, no el compartimiento perinucleolar de mamífero, que es rico en PTB |
| `ORC1 bodies` | `replication_compartment` | — | SUV39H1, EZH2, CBX5, DNMT1 son silenciamiento y heterocromatina; solo ORC1 encaja en replicación |

Los 53 casos restantes (109 proteínas) siguen priorizados y sin adjudicar en
`docs/review/ultima/review_cases_prioritized.csv`.

### 12.4 `evidence_type`: cinco valores, no tres

Acepta nuestra pregunta de §6.3 —la asignación es por recurso— y corrige el
número de valores hacia arriba, porque PhaSepDB emite dos afirmaciones distintas
según el rol. Las ocho combinaciones `(source_db, source_role)` se verificaron
exhaustivas contra `database/interim/*.tsv`.

| `source_db` | `source_role` | `evidence_type` | filas |
|---|---|---|---:|
| LLPSDB | driver | `in_vitro_llps` | 380 |
| PhasePro | driver | `in_vitro_llps` | 197 |
| PhaSepDB | client | `cellular_localisation` | 8.537 |
| PhaSepDB | driver | `cellular_requirement` | 2.138 |
| DrLLPS | Scaffold / Client / Regulator | `curator_assignment` | 10.872 |
| CDCODE | NotInformed | `membership_only` | 13.844 |

El valor que cambia cómo se lee la base es `membership_only`: hace explícito que
las 13.844 filas sin rol son el **alcance declarado de CD-CODE**, no un agujero
de nuestra ingesta. Y `curator_assignment` carga la advertencia de que el rol de
DrLLPS es de alcance proteína: la misma etiqueta se propaga a todos los MLOs de
esa proteína, así que no es una afirmación por compartimiento.

Implementado en `compute_evidence_type()` en `integrate.py`, al lado de
`compute_role_and_active()`, con la misma forma de tabla fija. Dos tests nuevos
en `test_dataset_invariants.py` afirman que no hay NULL y que no aparece ningún
valor fuera de los cinco.

### 12.5 Lo que esta revisión NO hace

> El inventario completo y su estado vive en `docs/review/findings.csv`
> (`python3 scripts/review_ledger.py --check`). Esta sección explica el
> razonamiento; el libro lleva la cuenta.

- **Reinstaurar los reguladores de DrLLPS como tercer valor de rol.** La
  devolución lo recomienda y acepta el riesgo que planteamos, argumentando que
  `evidence_type = curator_assignment` más una definición explícita acota la
  afirmación. Verificado: 1.389 filas, 977 proteínas, de las cuales 502 no
  tienen ninguna otra anotación; esas 502 aportan 607 anotaciones en 19 MLOs,
  concentradas en `p_body` (253), `stress_granule` (164) y `p_granule` (107).
  *La devolución reporta 429 y 418 para los dos primeros, cifras que suman más
  que el total de 607; parecen contadas sobre las 977 y no sobre las 502.*
  Pendiente porque cambia lo que el sitio sirve y toca la API.
- **La migración a cuatro ejes de categoría.** La devolución responde nuestra
  §6.5: omitir `functional_process` deja sin clasificar solo tres términos
  (`liquid_dyrk3_speckle`, `midbody_granule`, `fip200_puncta`), así que cuatro
  ejes alcanzan y la migración es más barata de lo previsto. Sigue siendo la
  pieza que toca DB, API y frontend a la vez (`R2-DEC-axes`).
- **Sacar `NotInformed` e `in_vitro_droplet` del vocabulario de organelas.**
- **Los 53 casos «review» sin adjudicar** (`R2-ADJ-batch`) **y los 3 que
  requieren la fuente** (`R2-ADJ-perinucleolar`, `R2-ADJ-orc1`,
  `R2-ADJ-receptor-cluster`) (§12.3).
- Verificar de nuestro lado los cuatro casos «review» que la devolución cerró
  como correctos sin que pasáramos por la publicación: `Mitochondrial cloud`
  → `balbiani_body`, el de mayor volumen con 598 de las 790 proteínas en
  revisión (`R2-ADJ-mitochondrial-cloud`); `Germ granule` → `p_granule`, que
  cierra el merge que el dossier señalaba como el que más quería que
  cuestionáramos (`R2-ADJ-germ-granule`); `+TIP body` → `spindle_apparatus`,
  defendible aunque grueso (`R2-ADJ-tip-body`); y `Leucocyte nuclear body` →
  `nuclear_body`, que pierde el calificador de tipo celular que el eje
  `cell_type_context` recuperaría (`R2-ADJ-leucocyte`). Los cuatro están
  descritos en §12.3.
- Revisar aparte las 6 proteínas que quedaron en `postsynaptic_density` solo
  por la etiqueta compuesta de CD-CODE que remapeó el retiro de
  `synaptic_compartment` (O43236, P17152, Q14DG7, Q5VSY0, Q6P995, Q9NQR7);
  ningún otro recurso las corrobora, a diferencia de las otras 1.360, y la
  devolución señala que P17152/TMEM11 es mitocondrial (§12.1)
  (`R2-OWN-psd-orphans`).

---

## 13. Revisión v7 — reguladores servidos y categoría en cuatro ejes (2026-08-12)

Las dos acciones que la ronda 2 dejó pendientes por «tocan la API» (§12.5), hechas
juntas porque comparten ese pase. Tercera devolución en
`docs/review/ronda3/TERCERA_DEVOLUCION.md`; el estado de cada hallazgo, en
`docs/review/findings.csv`.

### 13.1 Los reguladores de DrLLPS entran al dataset servido

`compute_role_and_active()` devolvía `(None, 0)` para `DrLLPS` + `Regulator`.
Ahora devuelve `(None, 1)`: las filas se sirven y se cuentan.

**Por qué se revierte la exclusión.** El costo medido no era ocultar 1.389
anotaciones sino borrar proteínas enteras: **501 de las 977 proteínas con fila de
regulador no tenían ninguna otra fila**, así que no aparecían en la base servida
en absoluto. Excluir una afirmación débil es defendible; hacer desaparecer la
proteína que la sostiene no lo es, porque la ausencia no se distingue de «esta
proteína no está en ninguna fuente».

**Corrección de cifra respecto de la ronda 3.** Su medición y el libro decían
**502**; contra la base viva son **501**, y la lectura alternativa («proteínas sin
ninguna fila con rol») es **540** y no 541. La diferencia es la fusión de
accesiones de `R3-INT-sin-organismo`, aplicada entre las dos mediciones: una de
esas proteínas quedó fusionada con una sucesora que sí tiene filas activas. Se
fija en el libro la lectura de las **501** (`R3-ROL-regulador-definicion`), que es
la que mide qué se recupera; las 39 restantes de la otra lectura están servidas y
sin rol, que es el problema distinto que ya describe `R1-ROL-02`.

**`unified_role` sigue en NULL.** No se agrega `'regulator'` como tercer valor
almacenado: regulador no es un veredicto driver/client, y meterlo en esa columna
obligaría a toda consulta de rol a saber que uno de sus tres valores significa
otra cosa. Lo que identifica la fila es la combinación
`evidence_type = 'curator_assignment'` + `source_role = 'Regulator'`, expuesta
como `policy.regulator_annotation_clause()`. La clave es el **tipo de
afirmación** y no el recurso: si otra fuente empieza a emitir llamados de
regulador, entra sin editar nada.

**Efecto sobre lo servido**, verificado contra la base regenerada:

| | antes | después |
|---|---:|---:|
| anotaciones servidas (`dataset_active = 1`) | 34.343 | **35.732** |
| proteínas con al menos una anotación servida | 15.193 | **15.694** |
| filas con `dataset_active = 0` | 1.389 | **0** |
| `unified_role` (driver / client / NULL) | 3.068 / 17.544 / 15.120 | **sin cambio** |
| `protein_summary.source_db_count = 0` | 501 | **0** |

La última fila es la misma medición desde otro ángulo: el bucket de proteínas con
cero recursos en el dataset servido desaparece porque ya no existe la proteína
servida sin ninguna fila.

**Un tercer bucket en la API, y solo en un endpoint.** El `CASE` de
`get_mlo_stats()` mandaba a `component` todo lo que no fuera driver, así que las
1.389 filas se contaban como componentes del orgánulo — exactamente lo que la
fuente no afirma. Ahora tiene tres ramas: `driver`, `regulator`, `component`.
`/stats` y las facetas de `/proteins` quedan como estaban por decisión explícita:
en `/stats` los reguladores caen en `unknown` junto a las filas sin rol de
CD-CODE, y en las facetas de `/proteins` cuentan como `component` porque esa
faceta se deriva de `protein_summary.has_driver`. Los tres vocabularios de
`by_role` ya eran distintos entre sí y siguen documentados en `api/CLAUDE.md`;
unificarlos es otra tarea, no un efecto colateral de esta.

**`dataset_active` se queda sin ninguna fila en 0.** La columna y
`policy.active_annotation_clause()` no se retiran: la regla que codifican sigue
vigente (una exclusión deliberada, argumentada, con fila en el libro), y hoy
simplemente no hay ninguna. El test que afirmaba «las únicas filas excluidas son
DrLLPS Regulator» pasaba a ser cierto por vacuidad, así que se reescribió como
igualdad contra el total servido.

### 13.2 `category` se reemplaza por cuatro ejes

`mlo_vocabulary.category` desaparece. En su lugar, cuatro columnas más dos de
procedencia, cargadas desde el archivo de curación nuevo
**`database/mappings/mlo_axes.csv`** (177 filas, una por canónico):

| columna | cubre | valores |
|---|---:|---|
| `spatial_location` | 177/177 | `cytoplasm` 87, `nucleus` 51, `plasma_membrane` 18, `cytoskeleton` 11, `extracellular` 3, `mitochondrion` 2, `plastid` 2, y uno cada uno de `nucleus_and_cytoplasm`, `in_vitro`, `unspecified` |
| `taxonomic_scope` | 176/177 | `Metazoa` 116, `Fungi` 16, `Bacteria` 13, `Viridiplantae` 9, `Protista` 3, `Virus` 2, más las etiquetas `pan_*` 17; NULL solo en `rho_body` |
| `physiological_state` | 177/177 | `constitutive` 153, `stress_induced` 10, `infection` 7, `pathological` 6, `in_vitro` 1 |
| `cell_type_context` | 34/177 | `germline` 16, `neuron` 9, y 9 tipos con uno cada uno; NULL en los otros 143 **por diseño** |
| `spatial_location_evidence` | 177/177 | `from_category` 121, `hand_assigned` 56 |
| `taxonomic_support_n` | 177/177 | proteínas con organismo conocido detrás del eje taxonómico; 63 términos tienen ≤2 y 42 tienen 1 |

La clasificación es la de `docs/review/ronda3/axes_classification.csv`, adoptada
como punto de partida según `R2-DEC-axes`. Tres cosas cambian al pasarla al
archivo de curación, y ninguna es cosmética:

1. **Se agrega `spatial_location_evidence`.** La auditoría derivó 121 valores de
   la categoría v6 (donde ya era una localización) y **asignó 56 a mano** desde la
   biología del orgánulo, pidiendo explícitamente que los revisemos. Guardar
   cuál es cuál convierte ese pedido en algo consultable, en vez de una
   advertencia en prosa que nadie cruza contra la tabla. Los 56 quedan abiertos
   en el libro (`R3-OWN-spatial-56`).
2. **`taxonomic_scope = 'sin_dato'` pasa a NULL.** Es un hueco real —la única
   proteína de `rho_body`, R7KIR7, está borrada en UniProt— y no un valor curado.
   `cell_type_context` vacío también es NULL, pero por el motivo opuesto: el eje
   no aplica. Las dos ausencias son NULL en la DB y la diferencia queda
   documentada, no codificada.
3. **`spatial_location = 'unspecified'` NO pasa a NULL.** Es la única fila con ese
   valor (`NotInformed`) y ahí sí es una afirmación curada: el término nombra una
   localización ausente. La distinción importa porque
   `policy.EXCLUDED_MLO_SPATIAL_LOCATIONS` la usa para sacar `NotInformed` de la
   grilla de `/mlos` —el mismo alcance estrecho que tenía con
   `category='Unspecified'`— y un término cuyo eje nunca se determinó no debe
   desaparecer de la grilla por un hueco de curación.

**Qué gana el esquema, más allá de tener cuatro columnas.** La categoría vivía en
`mlo_mapping.csv`, que está indexado por **etiqueta fuente**: un canónico con
cinco nombres fuente tenía cinco categorías posibles y podían contradecirse, que
es el defecto que §11.5 arregló a mano y que el loader vigilaba con un chequeo de
conflictos. `mlo_axes.csv` está indexado por **canónico**, así que la
contradicción no es expresable: dos filas para el mismo término son un error
fatal del loader. El chequeo de conflictos se retira porque su objeto desapareció.

Las columnas `Categoria`/`categoria` **siguen en los archivos de mapeo y ya no se
leen**: son la procedencia de 121 de los 177 valores espaciales. Repoblar
`mlo_vocabulary` desde ellas sería reintroducir la representación que esta
migración termina.

**Dos refusals nuevos en el loader**, en el mismo espíritu que los tres de §11:

- Un término clasificado en `mlo_axes.csv` que ningún archivo de mapeo produce es
  fatal: significa que el archivo de ejes quedó viejo.
- Un término **servido** sin `spatial_location`, `spatial_location_evidence` o
  `physiological_state` es fatal (`assert_axes_complete()`, después de la poda).
  Declarar un canónico sin fila de ejes no lo es: los tres que hoy no llegan a
  ninguna anotación (`adhesin_nanodomain`, `npr1_condensate`, `rosenthal_fiber`)
  se podan en el mismo run y nunca se sirven.

**Lo que el eje taxonómico dice y lo que no.** Está derivado de los organismos de
las proteínas anotadas, así que es una afirmación sobre **este dataset** y no
sobre el orgánulo. El caso que lo muestra sin ambigüedad es `aggresome`, que sale
`Bacteria` porque sus 6 proteínas anotadas son todas de *E. coli*, aunque el
agresoma de la literatura es una estructura de mamífero dependiente de
microtúbulos. La derivación es correcta y la lectura ingenua no: por eso
`taxonomic_support_n` se sirve al lado y no aparte, como pidió la ronda 3.

De arrastre, el eje derivado cierra dos de los tres casos de `R1-ACT-17` sin que
nadie emita un juicio: `refractile_body` deja de estar en `Procariota` (su única
proteína es de *Eimeria tenella*, un apicomplejo → `Protista`) y `twn_body` deja
de estar en `Vegetal` (sus tres proteínas —NRBP1, TSC22D2, WNK1— son humanas →
`Metazoa`). El tercero, `rho_body`, no se automatiza y queda abierto
(`R3-OWN-rho-body`): hay que recurar R7KIR7 a mano o retirar el término.

**Contrato de la API.** `category` sale de las respuestas y `?category=` deja de
existir; entran los cuatro campos en `/mlo/{id}`, `/mlos`, `/search` y las
anotaciones de `/protein/{id}`, más `spatial_location_evidence` y
`taxonomic_support_n` en los dos primeros. `/mlos` acepta un filtro por eje, y
los ejes conjugan: `?spatial_location=nucleus&physiological_state=stress_induced`
devuelve 5 términos, que es la pregunta que una columna única no podía hacer. No
se mapea `?category=` a nada: sus valores mezclaban lugares (`Nuclear`) con
linajes (`Procariota`), tipos celulares (`Neuronal`) y procesos (`Autofagia`), y
cada uno de esos vive ahora en un eje distinto. El frontend se reconstruye contra
el contrato nuevo; `MlosPage.vue` y `MloBadges.vue` son los dos archivos que leen
`mlo.category`.

### 13.3 Lo que esta revisión NO hace

> El inventario completo y su estado vive en `docs/review/findings.csv`
> (`python3 scripts/review_ledger.py --check`). Esta sección explica el
> razonamiento; el libro lleva la cuenta.

- **Revisar los 56 valores espaciales asignados a mano** (`R3-OWN-spatial-56`).
  Se adoptan y se marcan; no se auditan uno por uno.
- **Recurar o retirar `rho_body`** (`R3-OWN-rho-body`), lo único de `R1-ACT-17`
  que no cierra la derivación.
- **Unificar los tres vocabularios de `by_role`.** Solo `/mlo/{id}` distingue
  reguladores; `/stats` y las facetas de `/proteins` no.
- **`functional_process` como quinto eje.** La ronda 3 avisa que
  `mast_cell_granule` (533 filas) recupera el tipo celular vía
  `cell_type_context` pero pierde el proceso secretor, y que `fip200_puncta`,
  `midbody_granule` y `liquid_dyrk3_speckle` no los captura ningún eje. Con
  cuatro ejes eso sigue perdido.
- **Sacar `NotInformed` e `in_vitro_droplet` del vocabulario** (`R1-ACT-10`,
  `R1-ACT-11`). `NotInformed` sigue siendo un término del vocabulario, ahora con
  `spatial_location = 'unspecified'`, oculto solo de la grilla de `/mlos`.
- Todo lo que §12.5 dejaba pendiente y esta revisión no toca: los 53 casos del
  lote, los 3 que requieren la fuente, `microtubule_plus_end`, las 3 filas de
  *Danio*, la tabla de evidencia con clave foránea y las 6 proteínas huérfanas de
  `postsynaptic_density`.

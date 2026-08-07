# Bases de Datos Utilizadas

Este documento resume las bases de datos externas utilizadas por el servidor web, incluyendo una breve descripción y la cita formal de cada una.

Fuente: contenido provisto por el usuario durante el brainstorming de
[2026-08-06-about-page-design.md](2026-08-06-about-page-design.md) — copiar
verbatim al componente de Data Origin, no parafrasear.

---

## Bases de Datos de LLPS (Liquid-Liquid Phase Separation)

### PhaSePDB

PhaSePDB es una base de datos curada manualmente que reúne proteínas asociadas a la separación de fases líquido-líquido (LLPS), el proceso que subyace a la formación de orgánulos sin membrana encargados de concentrar proteínas y ácidos nucleicos. Reúne miles de proteínas no redundantes localizadas en distintos orgánulos, recopiladas a partir de la literatura publicada y de otras bases de datos, y para cada una ofrece un resumen funcional, las referencias bibliográficas correspondientes y las características de secuencia relacionadas con el comportamiento de LLPS; estas mismas características de secuencia se ponen a disposición también para otras proteínas humanas candidatas. A través de una interfaz en línea que permite explorar, buscar y descargar la información, PhaSePDB se propone como un recurso centralizado que facilita el estudio de la separación de fases.

**Cita:**
You K, Huang Q, Yu C, Shen B, Sevilla C, Shi M, Hermjakob H, Chen Y, Li T. PhaSepDB: a database of liquid–liquid phase separation related proteins. *Nucleic Acids Research*. 2020;48(D1):D354–D359. https://doi.org/10.1093/nar/gkz847

---

### DrLLPS

DrLLPS es una base de datos integrativa dedicada a las proteínas involucradas en la separación de fases líquido-líquido, un mecanismo ubicuo para la organización espaciotemporal de reacciones bioquímicas mediante la formación de orgánulos sin membrana en células eucariotas. A partir de la literatura, sus autores recopilaron manualmente proteínas "scaffold" (impulsoras de LLPS), proteínas reguladoras que modulan el proceso y proteínas cliente potencialmente prescindibles para la formación de estos orgánulos, clasificándolas en decenas de condensados biomoleculares distintos; además, buscaron ortólogos potenciales de estas proteínas en más de 160 especies eucariotas. Para ocho organismos modelo, DrLLPS anota en detalle cada proteína asociada a LLPS integrando información proveniente de más de un centenar de recursos externos, cubriendo aspectos como regiones desordenadas, dominios, modificaciones postraduccionales, variantes genéticas, interacciones moleculares, localización subcelular y estructuras 3D, entre otros.

**Cita:**
Ning W, Guo Y, Lin S, Mei B, Wu Y, Jiang P, Tan X, Zhang W, Chen G, Peng D, Chu L, Xue Y. DrLLPS: a data resource of liquid–liquid phase separation in eukaryotes. *Nucleic Acids Research*. 2020;48(D1):D288–D295. https://doi.org/10.1093/nar/gkz1027

---

### LLPSDB

LLPSDB es una base de datos de acceso web que ofrece una colección curada de proteínas involucradas en la separación de fases líquido-líquido observada *in vitro*, junto con las condiciones experimentales específicas bajo las cuales dicho comportamiento fue reportado en la literatura publicada. Incluye cientos de entradas correspondientes a proteínas independientes y miles de condiciones experimentales concretas, y para cada caso reúne información biomolecular (secuencia proteica, modificaciones, ácidos nucleicos asociados, etc.), información específica del comportamiento de fase (condiciones experimentales, descripción del comportamiento observado) y anotaciones adicionales. Sus autores la presentan como la primera base de datos diseñada específicamente para proteínas relacionadas con LLPS, orientada a facilitar el estudio de la relación entre secuencia proteica y comportamiento de fase, así como el desarrollo de métodos predictivos.

**Cita:**
Li Q, Peng X, Li Y, Tang W, Zhu J, Huang J, Qi Y, Zhang Z. LLPSDB: a database of proteins undergoing liquid–liquid phase separation in vitro. *Nucleic Acids Research*. 2020;48(D1):D320–D327. https://doi.org/10.1093/nar/gkz778

---

### PhasePro

PhaSePro es una base de datos curada manualmente, de acceso abierto, dedicada a proteínas y regiones proteicas que actúan como impulsoras de la separación de fases líquido-líquido validadas experimentalmente, un proceso central en la formación de orgánulos sin membrana que participan en procesos celulares específicos como la biogénesis de ribosomas o la degradación de ARN. Sus autores señalan que, si bien numerosos estudios experimentales reportan nuevos casos de LLPS, la identificación computacional de proteínas impulsoras del proceso va rezagada, en parte por la ausencia de una base de datos dedicada; PhaSePro busca cubrir este vacío ofreciendo, además de la información curada, vocabularios controlados específicos para LLPS que estandarizan la forma en que se describen estos sistemas, accesibles mediante una interfaz web.

**Cita:**
Mészáros B, Erdős G, Szabó B, Schád É, Tantos Á, Abukhairan R, Horváth T, Murvai N, Kovács OP, Kovács M, Tosatto SCE, Tompa P, Dosztányi Z, Pancsa R. PhaSePro: the database of proteins driving liquid–liquid phase separation. *Nucleic Acids Research*. 2020;48(D1):D360–D367. https://doi.org/10.1093/nar/gkz848

---

### CD-CODE

CD-CODE (Crowdsourcing Condensate Database and Encyclopedia) es una plataforma editable por la comunidad, desarrollada para integrar el conocimiento científico interdisciplinario sobre la función y composición de los condensados biomoleculares, cuyo descubrimiento transformó la comprensión de la compartimentalización intracelular de moléculas. Incluye una base de datos de condensados biomoleculares basada en la literatura, una enciclopedia de términos científicos relevantes del campo y una aplicación web de crowdsourcing que permite a la comunidad contribuir y actualizar la información. Según sus autores, la plataforma busca acelerar el descubrimiento y la validación de condensados biomoleculares, así como facilitar los esfuerzos por comprender su papel en la enfermedad y su potencial como blancos terapéuticos.

**Cita:**
Rostam N, Ghosh S, Chow CFW, Hadarovich A, Landerer C, Ghosh R, Moon H, Hersemann L, Mitrea DM, Klein IA, Hyman AA, Toth-Petroczy A. CD-CODE: crowdsourcing condensate database and encyclopedia. *Nature Methods*. 2023;20(5):673–676. https://doi.org/10.1038/s41592-023-01831-0

---

## Bases de Datos Generales

### UniProt

UniProt es la base de datos central de conocimiento sobre proteínas, que proporciona información curada y de alta calidad sobre secuencias, funciones, estructura y anotaciones biológicas de proteínas de todos los organismos.

**Cita:**
The UniProt Consortium. UniProt: the Universal Protein Knowledgebase in 2025. *Nucleic Acids Research*. 2025;53(D1):D609–D617. https://doi.org/10.1093/nar/gkae1010

---

### InterPro

InterPro es un recurso que clasifica las proteínas en familias y predice la presencia de dominios y sitios funcionales importantes integrando múltiples bases de datos de firmas de secuencia.

**Cita:**
Blum M, Andreeva A, Florentino LC, Chuguransky SR, Grego T, Hobbs E, Pinto BL, Orr A, Paysan-Lafosse T, Ponamareva I, Salazar GA, Bordin N, Bork P, Bridge A, Colwell L, Gough J, Haft DH, Letunic I, Llinares-López F, Marchler-Bauer A, Meng-Papaxanthos L, Mi H, Natale DA, Orengo CA, Pandurangan AP, Piovesan D, Rivoire C, Sigrist CJA, Thanki N, Thibaud-Nissen F, Thomas PD, Tosatto SCE, Wu CH, Bateman A. InterPro: the protein sequence classification resource in 2025. *Nucleic Acids Research*. 2025;53(D1):D444–D456. https://doi.org/10.1093/nar/gkae1082

---

### MobiDB

MobiDB es una base de datos que anota y agrega evidencia sobre el desorden intrínseco y la movilidad conformacional de las proteínas, combinando datos experimentales, curados manualmente y predichos computacionalmente.

**Cita:**
Piovesan D, Del Conte A, Clementel D, Monzon AM, Bevilacqua M, Aspromonte MC, Iserte JA, Orti FE, Marino-Buslje C, Tosatto SCE. MobiDB: 10 years of intrinsically disordered proteins. *Nucleic Acids Research*. 2023;51(D1):D438–D444. https://doi.org/10.1093/nar/gkac1065

---

### BioGRID

BioGRID es un recurso biomédico integral que cataloga interacciones proteína-proteína, genéticas y químicas curadas manualmente a partir de la literatura publicada en múltiples organismos.

**Cita:**
Oughtred R, Rust J, Chang C, Breitkreutz BJ, Stark C, Willems A, Boucher L, Leung G, Kolas N, Zhang F, Dolma S, Coulombe-Huntington J, Chatr-aryamontri A, Dolinski K, Tyers M. The BioGRID database: A comprehensive biomedical resource of curated protein, genetic, and chemical interactions. *Protein Science*. 2021;30(1):187–200. https://doi.org/10.1002/pro.3978

---

### OMA (Orthologous MAtrix)

OMA es un recurso que infiere relaciones de ortología a gran escala entre genes de genomas completos, permitiendo identificar genes/proteínas equivalentes entre especies para estudios de genómica comparativa y evolución.

**Cita:**
Altenhoff AM, Warwick Vesztrocy A, Bernard C, Train CM, Nicheperovich A, Prieto Baños S, Julca I, Moi D, Nevers Y, Majidian S, Dessimoz C, Glover NM. OMA orthology in 2024: improved prokaryote coverage, ancestral and extant GO enrichment, a revamped synteny viewer and more in the OMA Ecosystem. *Nucleic Acids Research*. 2024;52(D1):D513–D521. https://doi.org/10.1093/nar/gkad1020

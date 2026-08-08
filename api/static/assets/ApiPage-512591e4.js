import{o as s,b as a,d as t,t as r,F as i,i as l,I as u}from"./index-afa98e65.js";const h={class:"max-w-6xl mx-auto px-6 py-8"},g={class:"mb-8"},x={class:"overflow-x-auto border border-gray-200 rounded-lg"},_={class:"w-full text-sm"},b={class:"px-4 py-2 font-mono text-[#185FA5]"},f={class:"px-4 py-2 font-mono text-gray-800"},y={class:"px-4 py-2 text-gray-600"},v={class:"mb-8"},E={class:"overflow-x-auto border border-gray-200 rounded-lg mt-3"},P={class:"w-full text-sm"},w={class:"px-4 py-2 text-gray-600"},A={class:"px-4 py-2 font-mono text-gray-800"},F={class:"px-4 py-2 font-mono text-[#185FA5]"},T={class:"flex gap-3"},O=["href"],k=["href"],d="https://mlos.leloir.org.ar/api",L=`{
  "uniprot_id": "A1ZBW4",
  "gene_name": "HnRNP-K",
  "protein_name": null,
  "organism": "Drosophila melanogaster",
  "taxon_id": 7227,
  "sequence_length": 315,
  "disorder_mobidb_lite_dc": 0.502,
  "disorder_alphafold_dc": null,
  "mlo_annotations": [
    {
      "unified_mlo": "in_vitro_droplet",
      "category": "In vitro",
      "source_db": "LLPSDB",
      "source_mlo": "in vitro droplet",
      "unified_role": "driver",
      "evidence_pmids": ["32302572"]
    }
  ],
  "sequence_features": {
    "idrs": [
      { "start": 1, "end": 69, "score": null, "source": "MobiDB-lite" }
      // ... more IDR regions
    ],
    "domains": [
      { "start": 245, "end": 308, "label": "KH domain", "accession": "PF00013", "database": "pfam" }
    ],
    "lcds": [ /* ... */ ],
    "morfs": [],
    "plddt_regions": []
  },
  "ppi": {
    "total_partners": 0,
    "partners_in_mlosmetadb": 0,
    "interactions": null
  }
}`,M=`{ "error": "protein_not_found", "message": "No protein with UniProt ID 'Q92520'" }`,R={__name:"ApiPage",setup(S){const n="/v2/api/",p=[{method:"GET",path:"/protein/{uniprot_id}",purpose:"Full protein record: metadata, MLO annotations, sequence features, PPI summary"},{method:"GET",path:"/protein/{uniprot_id}/ppi",purpose:"Full PPI partner list for one protein, with optional role/mlo filters and inter-partner edges"},{method:"GET",path:"/protein/{uniprot_id}/orthologs",purpose:"OMA-derived orthologs across the 9 target organisms"},{method:"GET",path:"/proteins",purpose:"Paginated protein list with filters (organism, taxon_id, mlo, role, source_db, uniprot_id) + facets"},{method:"GET",path:"/proteins/export",purpose:"Unpaginated bulk export (TSV or JSON, capped at 50,000 rows) with organism/taxon_id/mlo/role/multi-value source_db filters and fields=basic|full column selection"},{method:"GET",path:"/mlo/{unified_mlo}",purpose:"One MLO's definitions (per source), aggregate stats, and paginated protein list"},{method:"GET",path:"/mlos",purpose:"Full canonical MLO vocabulary (no pagination)"},{method:"GET",path:"/search",purpose:"Basic search over gene names / UniProt IDs / protein names / MLO names"},{method:"GET",path:"/search/advanced",purpose:"Multi-filter search (gene, organism, taxon, mlo, role, source_db, sequence-feature filters)"},{method:"GET",path:"/stats",purpose:"Global counts — proteins, mlo_annotations, sequence_features, ppi"},{method:"GET",path:"/organisms/search",purpose:"Organism-name autocomplete (min 3 chars)"},{method:"POST",path:"/proteins/citations",purpose:"Given a list of UniProt IDs, return which source databases contributed annotations for them"}],m=[{situation:"Protein not in proteins",http:404,error:"protein_not_found"},{situation:"MLO not in mlo_vocabulary",http:404,error:"mlo_not_found"},{situation:"Invalid query parameter (bad sort_by, bad sort_order, etc.)",http:422,error:"invalid_parameter"},{situation:"q shorter than the endpoint's minimum length",http:422,error:"invalid_parameter"},{situation:"No filters given to /search/advanced",http:422,error:"no_filters_provided"},{situation:"mode=exact requested but FTS5 unavailable",http:501,error:"fts5_unavailable"},{situation:"Any database error",http:500,error:"database_error"}],c=`curl "${d}/protein/A1ZBW4"`;return(B,e)=>(s(),a("div",h,[e[7]||(e[7]=t("div",{class:"mb-6"},[t("h1",{class:"text-2xl font-semibold text-gray-800"},"API"),t("p",{class:"text-sm text-gray-600 mt-1"}," MLOsMetaDB's REST API is public and read-only — no API key required, no rate limit enforced today. ")],-1)),t("section",{class:"mb-8"},[e[0]||(e[0]=t("h2",{class:"text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2"},"Base URL",-1)),t("code",{class:"block bg-gray-900 text-gray-100 text-sm rounded px-4 py-2 font-mono"},r(d))]),t("section",g,[e[2]||(e[2]=t("h2",{class:"text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2"},"Endpoints",-1)),t("div",x,[t("table",_,[e[1]||(e[1]=t("thead",{class:"bg-gray-50 text-left text-gray-600"},[t("tr",null,[t("th",{class:"px-4 py-2 font-medium"},"Method"),t("th",{class:"px-4 py-2 font-medium"},"Path"),t("th",{class:"px-4 py-2 font-medium"},"Purpose")])],-1)),t("tbody",null,[(s(),a(i,null,l(p,o=>t("tr",{key:o.path,class:"border-t border-gray-100"},[t("td",b,r(o.method),1),t("td",f,r(o.path),1),t("td",y,r(o.purpose),1)])),64))])])])]),t("section",{class:"mb-8"},[e[3]||(e[3]=t("h2",{class:"text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2"},"Example",-1)),t("pre",{class:"bg-gray-900 text-gray-100 text-sm rounded px-4 py-3 overflow-x-auto"},[t("code",null,r(c))]),t("pre",{class:"bg-gray-50 border border-gray-200 text-gray-800 text-xs rounded px-4 py-3 overflow-x-auto mt-2"},[t("code",null,r(L))])]),t("section",v,[e[5]||(e[5]=t("h2",{class:"text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2"},"Error format",-1)),e[6]||(e[6]=t("p",{class:"text-sm text-gray-600 mb-2"}," Every error response, regardless of endpoint, has this shape: ",-1)),t("pre",{class:"bg-gray-50 border border-gray-200 text-gray-800 text-xs rounded px-4 py-3 overflow-x-auto"},[t("code",null,r(M))]),t("div",E,[t("table",P,[e[4]||(e[4]=t("thead",{class:"bg-gray-50 text-left text-gray-600"},[t("tr",null,[t("th",{class:"px-4 py-2 font-medium"},"Situation"),t("th",{class:"px-4 py-2 font-medium"},"HTTP"),t("th",{class:"px-4 py-2 font-medium"},"error")])],-1)),t("tbody",null,[(s(),a(i,null,l(m,o=>t("tr",{key:o.error+o.http,class:"border-t border-gray-100"},[t("td",w,r(o.situation),1),t("td",A,r(o.http),1),t("td",F,r(o.error),1)])),64))])])])]),e[8]||(e[8]=u('<section class="mb-8"><h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Citation</h2><p class="text-sm text-gray-600"> If you use this data in derived work, please cite: </p><p class="text-sm text-gray-800 mt-1"> Orti F, Fernández ML, Marino-Buslje C. <em>Protein Science.</em> 2024;33(1):e4858. <a href="https://doi.org/10.1002/pro.4858" class="text-[#185FA5] hover:underline" target="_blank" rel="noopener"> https://doi.org/10.1002/pro.4858 </a></p></section>',1)),t("section",T,[t("a",{href:`${n}docs`,target:"_blank",rel:"noopener",class:"inline-flex items-center px-4 py-2 rounded bg-[#185FA5] text-white text-sm font-medium hover:bg-[#0F4A87] transition-colors"}," Interactive docs (Swagger) → ",8,O),t("a",{href:`${n}redoc`,target:"_blank",rel:"noopener",class:"inline-flex items-center px-4 py-2 rounded border border-[#185FA5] text-[#185FA5] text-sm font-medium hover:bg-[#EBF3FB] transition-colors"}," Reference docs (ReDoc) → ",8,k)])]))}};export{R as default};

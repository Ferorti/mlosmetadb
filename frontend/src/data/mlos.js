/**
 * Offline fallback for the home grid, used only when GET /mlos fails
 * (MloBadges.vue's catch). Two things about it are load-bearing:
 *
 * - The **shape** has to match what the API returns, or the fallback renders
 *   blanks where the live path renders badges. It carried `category` until
 *   2026-08-12; the four axes replaced it (R1-ACT-06), and the two spatial
 *   fields are what the grid actually reads.
 * - The **numbers** are real, measured against database/mlosmetadb.db on
 *   2026-08-12 (drivers counted over dataset_active=1 rows, as the API does).
 *   The previous values were invented placeholders and drifted badly — this list
 *   claimed 1,842 proteins for stress_granule against a real 2,836 — which is
 *   worse than an obvious skeleton, because a plausible wrong number does not
 *   look like a failure. Refresh them alongside tests/dataset_baseline.json.
 *
 * `germ_granule` is gone from the list: it is not a canonical term any more
 * (the biological audit merged it into p_granule, R2-ADJ-germ-granule).
 */
export const PLACEHOLDER_MLOS = [
  { unified_mlo: 'nucleolus',            spatial_location: 'nucleus',         spatial_location_evidence: 'from_category', protein_count: 4892, driver_count: 134 },
  { unified_mlo: 'postsynaptic_density', spatial_location: 'plasma_membrane', spatial_location_evidence: 'hand_assigned', protein_count: 2960, driver_count: 41  },
  { unified_mlo: 'stress_granule',       spatial_location: 'cytoplasm',       spatial_location_evidence: 'from_category', protein_count: 2836, driver_count: 209 },
  { unified_mlo: 'p_body',               spatial_location: 'cytoplasm',       spatial_location_evidence: 'from_category', protein_count: 1507, driver_count: 90  },
  { unified_mlo: 'centrosome',           spatial_location: 'cytoskeleton',    spatial_location_evidence: 'from_category', protein_count: 998,  driver_count: 38  },
  { unified_mlo: 'nuclear_speckle',      spatial_location: 'nucleus',         spatial_location_evidence: 'from_category', protein_count: 710,  driver_count: 76  },
  { unified_mlo: 'in_vitro_droplet',     spatial_location: 'in_vitro',        spatial_location_evidence: 'hand_assigned', protein_count: 442,  driver_count: 422 },
  { unified_mlo: 'paraspeckle',          spatial_location: 'nucleus',         spatial_location_evidence: 'from_category', protein_count: 273,  driver_count: 16  },
  { unified_mlo: 'cajal_body',           spatial_location: 'nucleus',         spatial_location_evidence: 'from_category', protein_count: 255,  driver_count: 16  },
  { unified_mlo: 'nuclear_body',         spatial_location: 'nucleus',         spatial_location_evidence: 'from_category', protein_count: 242,  driver_count: 58  },
  { unified_mlo: 'neuronal_granule',     spatial_location: 'cytoplasm',       spatial_location_evidence: 'hand_assigned', protein_count: 118,  driver_count: 15  },
  { unified_mlo: 'polycomb_body',        spatial_location: 'nucleus',         spatial_location_evidence: 'from_category', protein_count: 44,   driver_count: 7   },
]

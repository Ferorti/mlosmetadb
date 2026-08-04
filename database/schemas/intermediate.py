"""
Canonical intermediate schema for MLOsMetaDB parser outputs.
Every parser must produce a DataFrame conforming to this schema.
"""

from dataclasses import dataclass
from typing import Optional

# Column names — order matters for TSV output
COLUMNS = [
    "uniprot_id",
    "source_db",
    "source_mlo",
    "source_role",
    "evidence",
    "organism",
]

# Sentinel value for missing optional fields
NULL = "NULL"

# Valid source_db values
SOURCE_DBS = [
    "PhaseDB",
    "PhasePDB",
    "DrLLPS",
    "LLPSDB",
    "PhasePro",
    "CDCODE",
]


@dataclass
class IntermediateRecord:
    uniprot_id: str          # required
    source_db: str           # required, one of SOURCE_DBS
    source_mlo: str          # required
    source_role: str         # raw value from source, or NULL
    evidence: str            # PMIDs semicolon-separated, or NULL
    organism: str            # species name, or NULL

    def validate(self) -> list[str]:
        """Return list of validation errors, empty if valid."""
        errors = []
        if not self.uniprot_id or not self.uniprot_id.strip():
            errors.append("missing uniprot_id")
        if not self.source_mlo or not self.source_mlo.strip():
            errors.append("missing source_mlo")
        if self.source_db not in SOURCE_DBS:
            errors.append(f"unknown source_db: {self.source_db}")
        return errors

"""Shared paths, class names, colours and the clinical-data loader."""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CT_DIR = ROOT / "data" / "ct"
SPLIT_CSV = ROOT / "data" / "splits.csv"
FIG = ROOT / "figures"
RESULTS = ROOT / "results"

CLASSES = ["Aspergillus", "Non-Aspergillus Fungi", "Non-Fungi"]
SHORT = {"Aspergillus": "Aspergillus", "Non-Aspergillus Fungi": "Non-Asp. fungi", "Non-Fungi": "Non-fungal"}
# validated with dataviz validate_palette.js (light mode, all checks pass)
COLORS = {"Aspergillus": "#2E5C9A", "Non-Aspergillus Fungi": "#0F9AA5", "Non-Fungi": "#C46A0A"}

NUMERIC = ["Age", "Lymphocyte Count", "D-Dimer"]
BINARY = ["Solid Tumor", "Diabetes", "Renal dysfunction", "Immunosuppressants", "AIDS",
          "(1,3)-β-D-Glucan (G)", "Aspergillus Antigen (GM)"]
CATEGORICAL = ["Gender"]
FEATURES = NUMERIC + BINARY + CATEGORICAL


def load_clinical() -> pd.DataFrame:
    """Raw CSV -> cleaned frame indexed by case ID, plus a `group` column.

    Cleaning: strip header/value whitespace, '/' -> NaN, drop the constant
    `Pathogen Identification` column. `group` links consecutive rows whose
    clinical record is identical (suspected repeat scans of one patient), so
    the split never separates them.
    """
    df = pd.read_csv(RAW / "OMIX014539-08.csv", encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    df["Gender"] = df["Gender"].str.strip()
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c].replace("/", np.nan))
    assert df["Pathogen Identification"].nunique() == 1
    df = df.drop(columns="Pathogen Identification").rename(columns={"ID Number": "case_id"})
    df = df.sort_values("case_id").reset_index(drop=True)

    key = df[["Diagnosis_Class"] + FEATURES].astype(str)
    df["group"] = (key != key.shift()).any(axis=1).cumsum() - 1
    df["label"] = df["Diagnosis_Class"].map(CLASSES.index)
    return df.set_index("case_id")

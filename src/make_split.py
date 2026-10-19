"""Group-aware, class-stratified 70/15/15 split (seed 42) -> data/splits.csv."""
import pandas as pd
from sklearn.model_selection import train_test_split

from common import SPLIT_CSV, load_clinical

SEED = 42

df = load_clinical()
groups = df.groupby("group")["label"].first()  # every group has one class

train_g, rest_g = train_test_split(groups.index, test_size=0.30, stratify=groups, random_state=SEED)
val_g, test_g = train_test_split(rest_g, test_size=0.50, stratify=groups[rest_g], random_state=SEED)

split_of = {**{g: "train" for g in train_g}, **{g: "val" for g in val_g}, **{g: "test" for g in test_g}}
df["split"] = df["group"].map(split_of)
df[["Diagnosis_Class", "label", "group", "split"]].to_csv(SPLIT_CSV)

assert df.groupby("group")["split"].nunique().max() == 1  # no group crosses splits
print(pd.crosstab(df["split"], df["Diagnosis_Class"], margins=True))
print("groups per split:", df.groupby("split")["group"].nunique().to_dict())

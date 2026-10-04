"""Crop-box size per case -> results/crop_qa.csv (a lung crop much smaller than the body = failed mask)."""
from concurrent.futures import ProcessPoolExecutor

import pandas as pd

from common import CT_DIR, RESULTS
from ct_preprocess import process


def job(path):
    _, d = process(path, return_debug=True)
    return int(path.name[4:7]), d["box"][2], int(d["mask"].sum())


if __name__ == "__main__":
    with ProcessPoolExecutor(8) as ex:
        rows = list(ex.map(job, sorted(CT_DIR.glob("*.nii.gz"))))
    df = pd.DataFrame(rows, columns=["case_id", "crop_side", "lung_voxels"]).set_index("case_id")
    df.to_csv(RESULTS / "crop_qa.csv")
    print(df.describe().round(0))
    print(df.sort_values("crop_side").head(15))

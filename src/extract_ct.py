"""Unzip the three CT archives into data/ct/ (flat) and record each volume's geometry.

Output: results/ct_geometry.csv (case_id, shape, voxel spacing, orientation)
"""
import zipfile

import nibabel as nib
import pandas as pd

from common import CT_DIR, RAW, RESULTS

CT_DIR.mkdir(parents=True, exist_ok=True)
for fid in ("03", "04", "05"):
    with zipfile.ZipFile(RAW / f"OMIX014539-{fid}.zip") as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            out = CT_DIR / info.filename.split("/")[-1]
            if not out.exists() or out.stat().st_size != info.file_size:
                out.write_bytes(z.read(info))  # z.read checks the CRC, so a corrupt member raises here
    print(fid, "extracted")

rows = []
for f in sorted(CT_DIR.glob("Case*.nii.gz")):
    img = nib.load(str(f))  # header only, no voxel read
    sx, sy, sz = (float(v) for v in img.header.get_zooms()[:3])
    rows.append({"case_id": int(f.name[4:7]), "nx": img.shape[0], "ny": img.shape[1], "nz": img.shape[2],
                 "sx": sx, "sy": sy, "sz": sz, "axcodes": "".join(nib.aff2axcodes(img.affine))})
geo = pd.DataFrame(rows).set_index("case_id")
geo.to_csv(RESULTS / "ct_geometry.csv")
print(len(geo), "volumes")
print(geo[["nx", "ny", "nz", "sx", "sz"]].describe().round(2))
print(geo["axcodes"].value_counts())
print(geo["sz"].round(2).value_counts().head(8))

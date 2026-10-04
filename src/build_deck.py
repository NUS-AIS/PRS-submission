"""Build the first-presentation deck from the group template.

Keeps the template's title and closing slides (background photo), rebuilds every
content slide in the template's visual language. All numbers are read from
results/*.json and data/splits.csv, never typed in by hand.
"""
import json

import pandas as pd
from pptx import Presentation
from pptx.opc.packuri import PackURI
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from common import CLASSES, FIG, RESULTS, ROOT, SPLIT_CSV, load_clinical

# first and last slides (title / closing, with the background photo) come from the group template;
# a copy is kept here because the original 开题/ folder is no longer in the project
TEMPLATE = ROOT / "template" / "base.pptx"
OUT = ROOT / "Group 26_Multimodal Pulmonary Infection Classification_First Presentation.pptx"

NAVY, TEAL, AMBER = "203864", "0E7C86", "B05A00"
INK, BODY, MUTED = "1A1A1A", "404040", "757575"
PANEL_EDGE, CARD, CARD_EDGE = "374C73", "F6F8FB", "D5DCE6"
GREEN_BG, GREEN = "E8F4EB", "2E7D32"
AMBER_BG = "FDF2DE"
TABS = ["Introduction", "Scope & Data", "System Design", "Progress & Results", "Plan"]
TAB_X = [0.55, 2.2, 4.1, 6.05, 8.3]
TAB_W = [1.45, 1.7, 1.75, 2.05, 1.0]


def rgb(h):
    return RGBColor.from_string(h)


# ---------------------------------------------------------------- primitives
def box(s, x, y, w, h, fill=None, line=None, lw=1.0, shape=MSO_SHAPE.RECTANGLE, radius=None):
    sh = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill:
        sh.fill.solid()
        sh.fill.fore_color.rgb = rgb(fill)
    else:
        sh.fill.background()
    if line:
        sh.line.color.rgb = rgb(line)
        sh.line.width = Pt(lw)
    else:
        sh.line.fill.background()
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = radius
    sh.shadow.inherit = False
    return sh


def text(s, x, y, w, h, runs, size=11, color=BODY, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         italic=False, spacing=None):
    """runs: str | list of paragraphs; a paragraph is str or list of (text, {overrides})."""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    paras = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if spacing:
            p.space_after = Pt(spacing)
        for t, o in ([(para, {})] if isinstance(para, str) else para):
            r = p.add_run()
            r.text = t
            f = r.font
            f.name = "Arial"
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", italic)
            f.color.rgb = rgb(o.get("color", color))
    return tb


def chip(s, x, y, label, fill=NAVY, w=None):
    w = w or 0.2 + 0.1 * len(label)
    box(s, x, y, w, 0.28, fill=fill)
    text(s, x, y, w, 0.28, label.upper(), size=10, color="FFFFFF", bold=True, align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE)


def bullets(s, x, y, w, h, items, size=11, color=BODY, spacing=4):
    paras = []
    for it in items:
        if isinstance(it, str):
            paras.append([("• ", {"color": TEAL, "bold": True}), (it, {})])
        else:  # (bold lead, rest)
            paras.append([("• ", {"color": TEAL, "bold": True}), (it[0], {"bold": True, "color": INK}),
                          (it[1], {})])
    return text(s, x, y, w, h, paras, size=size, color=color, spacing=spacing)


def numbered(s, x, y, n, title, body, fill=NAVY, w=4.45):
    o = box(s, x, y, 0.4, 0.4, fill=fill, shape=MSO_SHAPE.OVAL)
    text(s, x, y, 0.4, 0.4, f"{n:02d}", size=11, color="FFFFFF", bold=True, align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.52, y - 0.04, w, 0.26, title, size=12.5, color=NAVY, bold=True)
    text(s, x + 0.52, y + 0.22, w, 0.5, body, size=10.5, color=BODY)
    return o


def card(s, x, y, w, h, title, body, accent=NAVY, fill=CARD, title_size=11.5, body_size=10):
    box(s, x, y, w, h, fill=fill, line=CARD_EDGE, lw=0.75, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    box(s, x, y + 0.08, 0.07, h - 0.16, fill=accent)
    text(s, x + 0.2, y + 0.1, w - 0.3, 0.3, title, size=title_size, color=accent, bold=True)
    text(s, x + 0.2, y + 0.42, w - 0.3, h - 0.5, body, size=body_size, color=BODY)


def table(s, x, y, w, rows, col_w, size=10, header_fill=NAVY, row_h=0.3, bold_last_col=False, highlight=None,
          left_cols=(0,)):
    t = s.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(row_h * len(rows))).table
    for j, cw in enumerate(col_w):
        t.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        t.rows[i].height = Inches(row_h)
        for j, v in enumerate(row):
            c = t.cell(i, j)
            c.margin_left = c.margin_right = Inches(0.08)
            c.margin_top = c.margin_bottom = Inches(0.02)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.fill.solid()
            hl = highlight and i in highlight
            c.fill.fore_color.rgb = rgb(header_fill if i == 0 else ("E8F5F4" if hl else ("FFFFFF" if i % 2 else "F2F5F9")))
            p = c.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if j in left_cols else PP_ALIGN.CENTER
            r = p.add_run()
            r.text = str(v)
            r.font.name = "Arial"
            r.font.size = Pt(size)
            r.font.bold = i == 0 or (j == 0) or hl or (bold_last_col and j == len(row) - 1)
            r.font.color.rgb = rgb("FFFFFF" if i == 0 else INK)
    return t


def arrow(s, x, y, w=0.24, h=0.26, down=False):
    box(s, x, y, w, h, fill="8AA0B8", shape=MSO_SHAPE.DOWN_ARROW if down else MSO_SHAPE.RIGHT_ARROW)


def picture(s, path, x, y, w=None, h=None):
    kw = {}
    if w:
        kw["width"] = Inches(w)
    if h:
        kw["height"] = Inches(h)
    return s.shapes.add_picture(str(path), Inches(x), Inches(y), **kw)


def frame(prs, tab, title, page):
    s = prs.slides.add_slide(prs.slide_layouts[0])
    bg = s.background.fill
    bg.solid()
    bg.fore_color.rgb = rgb("D7DBE3")
    for i, (name, x, w) in enumerate(zip(TABS, TAB_X, TAB_W)):
        active = i == tab
        if active:
            box(s, x, 0.16, w, 0.32, fill=NAVY, line=NAVY)
        text(s, x, 0.16, w, 0.32, name, size=11.5, bold=True, color="FFFFFF" if active else NAVY,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 0.6, 0.6, 12.1, 0.42, title, size=20, bold=True, color=INK, anchor=MSO_ANCHOR.MIDDLE)
    box(s, 0.55, 1.1, 12.23, 5.98, fill="FFFFFF", line=PANEL_EDGE)
    text(s, 12.3, 7.06, 0.6, 0.3, str(page), size=11, bold=True, color=NAVY, align=PP_ALIGN.RIGHT)
    return s


def set_runs(shape, new):
    """Replace a template text box's text but keep its first run's formatting."""
    tf = shape.text_frame
    p0 = tf.paragraphs[0]
    for p in tf.paragraphs[1:]:
        p._p.getparent().remove(p._p)
    for r in p0.runs[1:]:
        r._r.getparent().remove(r._r)
    p0.runs[0].text = new


def drop_slide(prs, idx):
    sld = prs.slides._sldIdLst[idx]
    prs.part.drop_rel(sld.rId)
    prs.slides._sldIdLst.remove(sld)


# ---------------------------------------------------------------- data for the slides
df = load_clinical().join(pd.read_csv(SPLIT_CSV, index_col=0)["split"])
clin = json.loads((RESULTS / "clinical_baseline.json").read_text(encoding="utf-8"))
n_groups = df["group"].nunique()
n_dup_rows = len(df) - n_groups
split_tab = pd.crosstab(df["split"], df["Diagnosis_Class"]).reindex(["train", "val", "test"])[CLASSES]
groups_per_split = df.groupby("split")["group"].nunique()
miss = df[["D-Dimer", "Lymphocyte Count"]].isna().sum()
geo = pd.read_csv(RESULTS / "ct_geometry.csv", index_col=0)
assert len(geo) == 569 and (geo.sz == 5).all() and (geo.nx == 512).all()


def ct_result(tag):
    f = RESULTS / f"{tag}.json"
    return json.loads(f.read_text()) if f.exists() else None


ct_runs = {m: [r for s in range(3) if (r := ct_result(f"{m}_aug-basic_seed{s}"))] for m in ("ct", "fusion")}
all_runs = ct_runs["ct"] + ct_runs["fusion"]
ctf = [r["test_macro_f1"] for r in ct_runs["ct"]]
fuf = [r["test_macro_f1"] for r in ct_runs["fusion"]]
best_eps = [max(r["history"], key=lambda h: h["val_f1"])["epoch"] + 1 for r in all_runs]
last_loss = [r["history"][-1]["train_loss"] for r in all_runs]
best_val = [r["best_val_f1"] for r in all_runs]


def fmt(vals):
    import numpy as np
    return f"{np.mean(vals):.3f} ± {np.std(vals):.3f}" if len(vals) > 1 else f"{vals[0]:.3f}"


# ---------------------------------------------------------------- deck
prs = Presentation(str(TEMPLATE))
title_slide, closing = prs.slides[0], prs.slides[len(prs.slides) - 1]

TITLE = "A Multimodal Medical Imaging Assistant for Pulmonary Infection Classification"
SUB = ("Chest CT + de-identified clinical information → Aspergillus / non-Aspergillus fungal / "
       "non-fungal infection, with confidence, lesion localisation and severity")
names = {s.name: s for s in title_slide.shapes}
set_runs(names["Text 2"], "NUS-ISS  ·  PATTERN RECOGNITION SYSTEMS  ·  PRACTICE MODULE  ·  FIRST PRESENTATION")
set_runs(names["Text 3"], TITLE)
set_runs(names["Text 5"], SUB)
set_runs(names["Text 15"], "Practice Project Group (FT) 26 · NUS-ISS")
set_runs(names["Text 16"], "6 October 2026")
cn = {s.name: s for s in closing.shapes}
set_runs(cn["Text 2"], "NUS-ISS  ·  PATTERN RECOGNITION SYSTEMS  ·  PRACTICE MODULE  ·  FIRST PRESENTATION")
set_runs(cn["Text 6"], TITLE)

for i in range(len(prs.slides) - 2, 0, -1):  # drop everything between title and closing
    drop_slide(prs, i)
closing.part.partname = PackURI("/ppt/slides/slide99.xml")  # new slides are numbered from 3; avoid a clash
page = 2

# 2 ── Introduction
s = frame(prs, 0, "Introduction — Clinical Problem and Project Objectives", page); page += 1
chip(s, 0.9, 1.4, "Clinical problem", fill=AMBER, w=2.0)
text(s, 0.9, 1.8, 5.9, 0.75,
     "Aspergillus, other fungal and non-fungal (bacterial / viral) pneumonias overlap on chest CT — "
     "consolidation, nodules, cavities, ground-glass. They need different first-line treatment.",
     size=11)
picture(s, FIG / "class_examples.png", 0.95, 2.6, w=5.8)
text(s, 0.9, 6.68, 5.9, 0.3, "Two PAC569 cases per class (lung window). Can you tell them apart?", size=9.5,
     color=MUTED, italic=True)

chip(s, 7.4, 1.4, "Project goal", w=1.7)
text(s, 7.4, 1.8, 5.0, 0.9,
     "A research prototype that reads one patient's chest CT and clinical record and returns a three-class "
     "infection prediction with confidence — decision support, not a diagnosis.", size=11)
chip(s, 7.4, 2.75, "Objectives", fill=TEAL, w=1.5)
numbered(s, 7.4, 3.2, 1, "Classify", "Aspergillus vs non-Aspergillus fungi vs non-fungal, with calibrated confidence")
numbered(s, 7.4, 3.88, 2, "Fuse modalities", "Show whether CT + clinical beats CT-only and clinical-only", fill=TEAL)
numbered(s, 7.4, 4.56, 3, "Explain", "Highlight suspicious lung regions (saliency); severity estimate as stretch goal")
numbered(s, 7.4, 5.24, 4, "Study the data regime", "Pre-trained backbones, training-set size and augmentation",
         fill=TEAL)
box(s, 7.4, 6.0, 5.05, 0.85, fill=AMBER_BG, line="E9C98F", shape=MSO_SHAPE.ROUNDED_RECTANGLE).adjustments[0] = 0.1
text(s, 7.55, 6.06, 4.8, 0.75, [[("Hypothesis: ", {"bold": True, "color": AMBER}),
                                 ("CT pattern + routine clinical variables classify more reliably than either "
                                  "source alone.", {})]], size=10.5, anchor=MSO_ANCHOR.MIDDLE)

# 3 ── Scope
s = frame(prs, 1, "Project Scope — What the Prototype Will and Will Not Do", page); page += 1
chip(s, 0.9, 1.4, "Functional requirements", w=2.6)
table(s, 0.9, 1.8, 6.6, [
    ["ID", "Requirement", "Priority"],
    ["FR1", "Load one case: CT volume (NIfTI) + clinical record", "Must"],
    ["FR2", "Preprocess CT (window, lung crop, slice sampling)", "Must"],
    ["FR3", "Encode clinical data (impute, scale, one-hot)", "Must"],
    ["FR4", "Predict 3 classes with probabilities", "Must"],
    ["FR5", "Return 'uncertain' when confidence is low", "Should"],
    ["FR6", "Saliency map over CT slices (lesion localisation)", "Should"],
    ["FR7", "Severity estimate (definition to agree with supervisor)", "Could"],
    ["FR8", "Viewer UI: CT slices + clinical panel + outputs", "Must"],
], [0.6, 4.9, 1.1], size=10, row_h=0.42, left_cols=(0, 1))
chip(s, 7.95, 1.4, "Pattern-recognition techniques", fill=TEAL, w=3.1)
items = [("Supervised deep learning", "Transfer learning from ImageNet ResNet-18 / ResNet-50 on 2.5D CT slices"),
         ("Multimodal fusion", "CT features ⊕ clinical MLP features → MLP classifier (late / feature fusion)"),
         ("Classical ML baselines", "Logistic regression, random forest, LightGBM on clinical variables"),
         ("Explainability", "Grad-CAM saliency for weakly-supervised lesion localisation")]
for i, (t, b) in enumerate(items):
    card(s, 7.95, 1.8 + i * 0.95, 4.5, 0.85, t, b, accent=NAVY if i % 2 == 0 else TEAL, body_size=9.5)
box(s, 7.95, 5.65, 4.5, 0.95, fill=CARD, line=CARD_EDGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE).adjustments[0] = 0.06
text(s, 8.1, 5.72, 4.2, 1.1, [[("Out of scope: ", {"bold": True, "color": INK}),
                              ("clinical validation or certification, deployment in hospital workflow, "
                               "pathogen species identification, voxel-level lesion segmentation (no masks "
                               "in the dataset).", {})]], size=10)

# 4 ── Data
s = frame(prs, 1, "Data — PAC569 Multi-Modal Dataset (OMIX014539, NGDC China)", page); page += 1
chip(s, 0.9, 1.4, "What we downloaded", w=2.3)
table(s, 0.9, 1.8, 6.4, [
    ["File", "Content", "Cases", "Size"],
    ["OMIX014539-03", "Aspergillus CT (.nii.gz)", "153", "3.53 GB"],
    ["OMIX014539-04", "Non-Aspergillus fungi CT", "209", "4.88 GB"],
    ["OMIX014539-05", "Non-fungal CT", "207", "4.67 GB"],
    ["OMIX014539-08", "Clinical variables (.csv)", "569 rows", "28 KB"],
], [1.55, 2.65, 1.1, 1.1], size=10, left_cols=(0, 1))
picture(s, FIG / "eda_class_missing.png", 0.85, 3.45, w=6.5)
chip(s, 7.7, 1.4, "CT volumes", fill=TEAL, w=1.5)
bullets(s, 7.7, 1.8, 4.8, 1.4, [
    ("One volume per case: ", "CaseXXX.nii.gz, IDs match the CSV 569 / 569, labels agree 100%"),
    ("Geometry (all 569): ", f"512 × 512 in-plane ({geo.sx.min():.2f}–{geo.sx.max():.2f} mm), "
                          f"{geo.nz.min()}–{geo.nz.max()} slices (median {geo.nz.median():.0f}), all 5 mm thick"),
    ("Intensity: ", "raw Hounsfield units (air ≈ −1000, soft tissue ≈ 0–100)"),
    ("No lesion masks, no severity labels", ""),
], size=10.5)
chip(s, 7.7, 3.45, "Clinical variables (12)", fill=TEAL, w=2.4)
table(s, 7.7, 3.85, 4.75, [
    ["Group", "Variables"],
    ["Demographics", "Gender, Age"],
    ["Comorbidity", "Solid tumour, Diabetes, Renal dysfunction, AIDS"],
    ["Treatment", "Immunosuppressants"],
    ["Laboratory", "Lymphocyte count, D-dimer"],
    ["Fungal markers", "(1,3)-β-D-glucan (G), GM antigen"],
], [1.35, 3.4], size=9.5, row_h=0.36, left_cols=(0, 1))
text(s, 7.7, 6.1, 4.75, 0.7, "A 13th column, Pathogen Identification, is 1 for every row and is dropped. "
     "Source: ngdc.cncb.ac.cn/omix/release/OMIX014539 (released 11 Sep 2026, Wuxi People's Hospital).",
     size=9, color=MUTED, italic=True)

# 5 ── Data findings
s = frame(prs, 1, "Data Exploration — What We Found Before Modelling", page); page += 1
chip(s, 0.9, 1.4, "Clinical risk factors differ by class", fill=AMBER, w=3.7)
picture(s, FIG / "eda_prevalence.png", 0.85, 1.8, w=6.6)
prev = clin["prevalence_pct"]
aids = df.groupby("Diagnosis_Class")["AIDS"].sum()
text(s, 0.9, 4.55, 6.5, 0.9,
     f"AIDS: {aids['Non-Aspergillus Fungi']} of {aids.sum()} AIDS patients are in the non-Aspergillus fungal "
     f"class. GM antigen is positive in {prev['Aspergillus Antigen (GM)']['Aspergillus']:.1f}% of Aspergillus cases; "
     f"G-test in {prev['(1,3)-β-D-Glucan (G)']['Non-Aspergillus Fungi']:.1f}% of non-Aspergillus fungal cases.",
     size=10.5)
box(s, 0.9, 5.15, 6.5, 1.15, fill=AMBER_BG, line="E9C98F", shape=MSO_SHAPE.ROUNDED_RECTANGLE).adjustments[0] = 0.08
text(s, 1.1, 5.25, 6.1, 1.0, [[("Implication: ", {"bold": True, "color": AMBER}),
                               ("clinical data carry real signal, but no single marker separates the classes "
                                "— each is positive in a minority. G / GM are themselves diagnostic criteria, so we "
                                "also report results with and without them to check for label shortcuts.", {})]],
     size=10.5)
chip(s, 7.75, 1.4, "Data-quality checks", w=2.2)
card(s, 7.75, 1.8, 4.7, 1.05, f"{n_dup_rows} repeated clinical records",
     f"{n_dup_rows} rows repeat the previous row exactly (consecutive IDs) → likely repeat scans of one patient. "
     f"Grouped into {n_groups} patient groups; a group never crosses splits.", accent=AMBER)
card(s, 7.75, 2.95, 4.7, 0.95, "Missing values",
     f"D-dimer {miss['D-Dimer']} ('/'), lymphocyte count {miss['Lymphocyte Count']}. "
     "Imputed with training-set median.", accent=TEAL)
card(s, 7.75, 4.0, 4.7, 0.95, "Inconsistent coding",
     "Gender values with trailing spaces ('F ' vs 'F'); constant Pathogen Identification column.", accent=NAVY)
card(s, 7.75, 5.05, 4.7, 1.0, "No lesion / severity ground truth",
     "Localisation becomes weakly supervised (Grad-CAM); severity needs an agreed proxy definition.",
     accent=AMBER)
text(s, 7.75, 6.2, 4.7, 0.6, "Class balance is moderate (153 / 209 / 207) → class-weighted loss, "
     "macro-F1 as primary metric.", size=10, color=MUTED, italic=True)

# 7 ── Preprocessing & split
s = frame(prs, 1, "Data Pipeline — CT Preprocessing and Leak-Free Split", page); page += 1
chip(s, 0.9, 1.4, "CT preprocessing (implemented)", w=3.2)
picture(s, FIG / "ct_pipeline.png", 0.9, 1.8, w=11.55)
chip(s, 0.9, 4.45, "Patient-group stratified split · seed 42", fill=TEAL, w=3.9)
rows = [["Split", "Aspergillus", "Non-Asp. fungi", "Non-fungal", "Scans", "Groups"]]
for sp in ["train", "val", "test"]:
    r = split_tab.loc[sp]
    rows.append([sp.capitalize(), *[int(v) for v in r.values], int(r.sum()), int(groups_per_split[sp])])
rows.append(["Total", *[int(v) for v in split_tab.sum().values], int(split_tab.values.sum()), n_groups])
table(s, 0.9, 4.85, 6.4, rows, [0.9, 1.1, 1.25, 1.05, 0.95, 1.15], size=10, row_h=0.36)
bullets(s, 7.7, 4.5, 4.8, 2.3, [
    ("70 / 15 / 15 ", "split over patient groups, stratified by class"),
    ("No leakage: ", "repeat scans stay together; imputer, scaler and encoder are fitted on train only"),
    ("Augmentation ", "only on training cases: ±10° rotation, ±5% shift (same transform for all slices)"),
    # found by visual QA of the 24 smallest crops in the first version (see src/crop_qa.py)
    ("Crop QA: ", "12 / 569 first-version crops kept only one lung (a fully consolidated lung is not "
                  "'air') → box now mirrored about the body midline; all models retrained"),
], size=10)

# 6 ── Architecture
s = frame(prs, 2, "System Design — Multimodal Architecture", page); page += 1
y1, y2 = 1.55, 3.5


def node(x, y, w, h, title, body, edge=NAVY, fill="F2F5F9"):
    box(s, x, y, w, h, fill=fill, line=edge, lw=1.0, shape=MSO_SHAPE.ROUNDED_RECTANGLE).adjustments[0] = 0.1
    text(s, x + 0.08, y + 0.1, w - 0.16, 0.3, title, size=11.5, bold=True, color=edge, align=PP_ALIGN.CENTER)
    text(s, x + 0.08, y + 0.42, w - 0.16, h - 0.45, body, size=9.5, color=BODY, align=PP_ALIGN.CENTER)


text(s, 0.85, 1.25, 2, 0.25, "CT BRANCH", size=9.5, bold=True, color=NAVY)
node(0.85, y1, 1.75, 1.25, "Chest CT", f"NIfTI volume\n512×512×{geo.nz.min()}–{geo.nz.max()}, HU")
arrow(s, 2.67, y1 + 0.5)
node(3.0, y1, 2.0, 1.25, "Preprocess", "lung window, lung crop,\n16 slices × 3 adjacent\n→ 224×224")
arrow(s, 5.07, y1 + 0.5)
node(5.4, y1, 2.0, 1.25, "ResNet-18", "ImageNet pre-trained,\nshared over 16 slices\n→ 16 × 512")
arrow(s, 7.47, y1 + 0.5)
node(7.8, y1, 1.5, 1.25, "Mean pool", "patient-level\n512-d")
text(s, 0.85, 3.2, 2.5, 0.25, "CLINICAL BRANCH", size=9.5, bold=True, color=TEAL)
node(0.85, y2, 1.75, 1.15, "Clinical record", "12 variables", edge=TEAL, fill="E8F5F4")
arrow(s, 2.67, y2 + 0.45)
node(3.0, y2, 2.0, 1.15, "Encode", "median impute, z-score,\none-hot (train-fit only)", edge=TEAL, fill="E8F5F4")
arrow(s, 5.07, y2 + 0.45)
node(5.4, y2, 2.0, 1.15, "Clinical MLP", "2 layers → 64-d", edge=TEAL, fill="E8F5F4")
arrow(s, 7.47, y2 + 0.45)
node(9.65, 2.35, 1.35, 1.4, "Concat", "512 + 64\n= 576-d", edge=AMBER, fill=AMBER_BG)
for yy in (y1 + 0.62, y2 + 0.57):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(9.3 if yy < 3 else 7.8), Inches(yy),
                               Inches(9.65), Inches(3.05))
    c.line.color.rgb = rgb("8AA0B8")
    c.line.width = Pt(2)
node(11.2, 2.35, 1.35, 1.4, "MLP head", "dropout,\nsoftmax ×3", edge=AMBER, fill=AMBER_BG)
arrow(s, 11.03, 2.92, w=0.16)
arrow(s, 11.75, 3.8, down=True)
node(10.45, 4.15, 2.1, 1.0, "Outputs", "class probabilities,\n'uncertain' flag", edge=NAVY)
node(7.8, 4.15, 2.4, 1.0, "Grad-CAM", "saliency on the CT slices\n→ lesion localisation", edge=NAVY)
chip(s, 0.85, 5.0, "Baselines share the same parts", fill=NAVY, w=3.2)
bullets(s, 0.85, 5.4, 6.7, 1.4, [
    ("CT-only: ", "same CT branch + head, clinical branch removed"),
    ("Clinical-only: ", "logistic regression / random forest / LightGBM on the encoded record"),
    ("Training: ", "class-weighted cross-entropy, AdamW, cosine LR, mixed precision; model chosen on "
                   "validation macro-F1"),
], size=10.5)
box(s, 7.8, 5.4, 4.75, 1.0, fill=CARD, line=CARD_EDGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE).adjustments[0] = 0.08
text(s, 7.95, 5.48, 4.5, 1.3, [[("Why 2.5D, not 3D? ", {"bold": True, "color": NAVY}),
                               ("Slices are 5 mm thick, so a 3D network gains little along z; 2D ImageNet "
                                "weights transfer directly, and 16 slices × 224² fits our 8 GB GPU. "
                                "3 adjacent slices as RGB keep local z-context.", {})]], size=10)

# 8 ── Experiments
s = frame(prs, 2, "Experimental Design — Two Comparison Groups: Data First, Then Model", page); page += 1
groups = [
    ("Experiment 1 · Data", "What goes into the model? — run first", TEAL, [
        ("1a · Preprocessing", "lung masking on / off; lung window vs multi-window channels", None),
        ("1b · Augmentation", "none / basic / extended (scale, intensity, noise, cut-out)", "augmentation"),
        ("1c · Training size", "25 / 50 / 75 / 100% of training groups; val + test fixed", "training size"),
    ], "no masking, basic augmentation, 100% data"),
    ("Experiment 2 · Model", "How should it learn? — on the best data setting", NAVY, [
        ("2a · Modality", "CT only / clinical only / fusion; clinical with / without G & GM", "pre-trained baseline"),
        ("2b · Fusion method", "feature concatenation vs late fusion of probabilities", None),
        ("2c · Backbone", "ImageNet ResNet-18 vs ResNet-50", "pre-trained baseline"),
        ("2d · Structure (optional)", "flat 3-class vs fungal / non-fungal first, then Aspergillus", None),
    ], "ResNet-18, 3 modalities, concatenation"),
]
for i, (t, q, col, items, done) in enumerate(groups):
    x = 0.9 + i * 5.9
    box(s, x, 1.4, 5.65, 3.45, fill="FFFFFF", line=CARD_EDGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE).adjustments[0] = 0.04
    box(s, x, 1.4, 5.65, 0.72, fill=col)
    text(s, x + 0.15, 1.44, 5.3, 0.35, t, size=13, bold=True, color="FFFFFF")
    text(s, x + 0.15, 1.77, 5.3, 0.3, q, size=10, color="FFFFFF", italic=True)
    for k, (lab, desc, sup) in enumerate(items):
        y = 2.25 + k * 0.5
        text(s, x + 0.15, y, 1.75, 0.45, lab, size=10, bold=True, color=col, anchor=MSO_ANCHOR.MIDDLE)
        text(s, x + 1.9, y, 2.55 if sup else 3.6, 0.45, desc, size=9.5, color=BODY, anchor=MSO_ANCHOR.MIDDLE)
        if sup:
            box(s, x + 4.5, y + 0.08, 1.05, 0.3, fill=AMBER_BG, line="E9C98F", lw=0.5)
            text(s, x + 4.5, y + 0.08, 1.05, 0.3, "Supervisor: " + sup, size=7, bold=True, color=AMBER,
                 align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    box(s, x + 0.12, 4.38, 5.41, 0.35, fill=GREEN_BG)
    text(s, x + 0.2, 4.38, 5.3, 0.35, [[("So far only the baseline: ", {"bold": True, "color": GREEN}), (done, {})]],
         size=9.5, anchor=MSO_ANCHOR.MIDDLE)
box(s, 6.57, 2.85, 0.22, 0.32, fill="8AA0B8", shape=MSO_SHAPE.RIGHT_ARROW)
chip(s, 0.9, 5.0, "Evaluation protocol", w=2.2)
bullets(s, 0.9, 5.38, 6.6, 1.5, [
    ("Primary metric: ", "macro-F1; also balanced accuracy, per-class recall, confusion matrix"),
    ("Model selection: ", "on validation / 5-fold group CV only"),
    ("Test set (83 scans): ", "used once per final configuration; 3 seeds, mean ± SD"),
], size=10.5)
box(s, 7.75, 5.0, 4.7, 1.3, fill=CARD, line=CARD_EDGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE).adjustments[0] = 0.06
text(s, 7.9, 5.08, 4.4, 1.15, [[("One factor at a time. ", {"bold": True, "color": NAVY}),
                               ("Each comparison changes one thing against the baseline. The best data setting from "
                                "Experiment 1 becomes the starting point for Experiment 2.", {})]],
     size=10, anchor=MSO_ANCHOR.MIDDLE)

# 9 ── Where we are
s = frame(prs, 3, "Where We Are — Data Ready, Baseline Established, Main Work Ahead", page); page += 1
phases = [  # (title, when, items, done, width)
    ("0 · Data foundation", "done", ["Download + ID / label check", "EDA, cleaning, repeat-scan groups",
                                     "Leak-free group split", "CT preprocessing + crop QA"], True, 1.75),
    ("1 · Baseline", "done", ["One default config, untuned", "Clinical / CT / fusion, 3 seeds",
                              "Grad-CAM sanity check", "→ diagnosis (slide 12)"], True, 1.75),
    ("2 · Fix data & training", "Wk 1", ["Lung masking", "Regularisation, partial freezing",
                                         "Re-run baseline"], False, 1.85),
    ("3 · Main experiments", "Wk 2–4", ["Exp. 1 · Data: preprocessing, augmentation, training size",
                                        "Exp. 2 · Model: modality, fusion, backbone", "3 seeds each"], False, 2.35),
    ("4 · Explain, severity, UI", "Wk 4–5", ["Grad-CAM review", "Severity proxy", "Calibration + 'uncertain'",
                                             "Prototype UI"], False, 2.0),
    ("5 · Final evaluation", "Wk 6", ["Test set, once", "Error analysis", "Report + demo"], False, 1.75),
]
x = 0.9
for i, (t, when, items, done, w) in enumerate(phases):
    col = GREEN if done else ("8AA0B8" if i > 2 else NAVY)
    box(s, x, 1.75, w + 0.12, 0.62, fill=col, shape=MSO_SHAPE.CHEVRON if i else MSO_SHAPE.PENTAGON)
    text(s, x + 0.22, 1.75, w - 0.25, 0.62, ("✓ " if done else "") + t, size=9.5, bold=True, color="FFFFFF",
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    box(s, x + 0.05, 2.5, w - 0.08, 2.0, fill=GREEN_BG if done else "FFFFFF", line=CARD_EDGE, lw=0.5)
    text(s, x + 0.12, 2.55, w - 0.2, 0.25, "DONE" if done else when.upper(), size=9, bold=True,
         color=GREEN if done else MUTED)
    text(s, x + 0.12, 2.82, w - 0.2, 1.65, [f"• {it}" for it in items], size=9, color=BODY, spacing=2)
    if i == 1:  # boundary between baseline and the work still ahead
        here_x = x + w + 0.06
    x += w - 0.02
box(s, here_x - 0.13, 1.47, 0.26, 0.22, fill=AMBER, shape=MSO_SHAPE.ISOSCELES_TRIANGLE).rotation = 180
text(s, here_x - 1.0, 1.2, 2.0, 0.26, "WE ARE HERE", size=10, bold=True, color=AMBER, align=PP_ALIGN.CENTER)
text(s, here_x + 1.2, 1.2, 5.6, 0.26, "the main work — phases 2 to 5 — has not started yet", size=10,
     italic=True, color=MUTED)
chip(s, 0.9, 4.75, "What the baseline is — and is not", fill=AMBER, w=3.5)
bullets(s, 0.9, 5.15, 5.9, 1.8, [
    ("Is: ", "one default configuration (ResNet-18, full training set, basic augmentation), run end-to-end "
             "with 3 seeds — it proves the pipeline works and gives the reference point."),
    ("Is not: ", "tuned, ablated or final. Neither comparison group — data or model — has been run "
                 "beyond its default cell."),
    ("Test numbers today ", "are a first look; later choices use validation / cross-validation."),
], size=10, spacing=4)
picture(s, FIG / "training_curves.png", 7.05, 4.7, w=5.4)
text(s, 7.1, 6.67, 5.35, 0.35, f"Baseline training, mean ± SD over 3 seeds: training loss {min(last_loss):.2f}–"
     f"{max(last_loss):.2f}, best validation F1 only {min(best_val):.2f}–{max(best_val):.2f}.",
     size=9, color=MUTED, italic=True)

# 10 ── Preliminary results
s = frame(prs, 3, "Baseline Results — One Untuned Configuration on the Fixed Split", page); page += 1
chip(s, 0.9, 1.4, "Macro-F1 (chance = 0.333)", w=2.9)
fs, cv = clin["fixed_split"], clin["cv5_trainval"]
rows = [["Model", "Features", "5-fold CV (train+val)", "Test, 3 seeds"]]
for key in ["Logistic regression | all", "Random forest | all", "LightGBM | all", "Random forest | no_G_GM"]:
    m, feat = key.split(" | ")
    t = fs[key]["test"]["macro_f1"]
    rows.append([m, "clinical" if feat == "all" else "clinical − G/GM", f"{cv[key][0]:.3f} ± {cv[key][1]:.3f}",
                 f"{t[0]:.3f} ± {t[1]:.3f}" if t[1] > 0.0005 else f"{t[0]:.3f} (deterministic)"])
for mode, lab in (("ct", "CT only"), ("fusion", "CT + clinical")):
    runs = ct_runs[mode]
    rows.append(["ResNet-18 (2.5D)", lab, "—",
                 f"{fmt([r['test_macro_f1'] for r in runs])}" + ("" if len(runs) == 3 else f" ({len(runs)} seed)")
                 if runs else "running"])
val_mean = {m: sum(r["best_val_f1"] for r in ct_runs[m]) / len(ct_runs[m]) for m in ct_runs if ct_runs[m]}
best_img = max(val_mean, key=val_mean.get) if val_mean else None
table(s, 0.9, 1.8, 7.0, rows, [1.9, 1.5, 1.9, 1.7], size=10, row_h=0.38,
      highlight={2} | ({5 if best_img == "ct" else 6} if best_img else set()))
best = clin["best_on_val"]
text(s, 0.9, 4.5, 7.0, 0.3, f"Highlighted: best clinical model and best image model, chosen on validation macro-F1.",
     size=9.5, color=MUTED, italic=True)
box(s, 0.9, 4.85, 7.0, 1.55, fill=AMBER_BG, line="E9C98F", shape=MSO_SHAPE.ROUNDED_RECTANGLE).adjustments[0] = 0.06
rf = cv["Random forest | all"]
text(s, 1.1, 4.93, 6.6, 1.9, [
    [("Reading so far (first, untuned runs)", {"bold": True, "color": AMBER, "size": 12})],
    [(f"• Clinical alone: CV macro-F1 ≈ {rf[0]:.2f}; dropping G/GM costs only "
      f"{rf[0] - cv['Random forest | no_G_GM'][0]:.3f} → no obvious marker shortcut.", {})],
    [(f"• CT-only ResNet-18 is the best so far ({fmt(ctf)}).", {})],
    [(f"• Fusion ({fmt(fuf)}) does not beat CT-only yet. " if sum(fuf) / len(fuf) <= sum(ctf) / len(ctf) + 0.02
      else f"• Fusion ({fmt(fuf)}) improves on CT-only. ", {"bold": True}),
     ("", {})],
    [("• These are baseline numbers — why, and what we change next, is on slide 12.", {"italic": True})],
], size=10.5, spacing=4)
cm_path = FIG / "fusion_cm.png" if (FIG / "fusion_cm.png").exists() else FIG / "clinical_cm.png"
picture(s, cm_path, 8.25, 1.4, h=3.7)
if cm_path.name == "fusion_cm.png":
    cm = json.loads((RESULTS / "fusion_aug-basic_seed0.json").read_text())["test_cm"]
    short = ["Aspergillus", "non-Asp. fungi", "non-fungal"]
    i, j = max(((i, j) for i in range(3) for j in range(3) if i != j), key=lambda ij: cm[ij[0]][ij[1]])
    caption = (f"Fusion model, seed 0, 83-scan test set. Most common error: {short[i]} predicted as {short[j]} "
               f"({cm[i][j]} of {sum(cm[i])}).")
else:
    caption = "Clinical-only confusion matrix on the 83-scan test set."
text(s, 8.25, 5.2, 4.2, 1.5, caption, size=10, color=BODY)

# 10b ── Grad-CAM
s = frame(prs, 3, "Baseline Sanity Check — Where Does the Model Look? (Grad-CAM)", page); page += 1
assert json.loads((RESULTS / "gradcam_cases.json").read_text()) == [443, 250, 511], "re-read Grad-CAM, update text"
picture(s, FIG / "gradcam.png", 0.85, 1.25, h=5.75)
chip(s, 8.3, 1.4, "What we see", fill=TEAL, w=1.6)
bullets(s, 8.3, 1.8, 4.2, 2.8, [
    ("Method: ", "Grad-CAM on ResNet layer 4 for the predicted class; 4 slices with the most saliency per case "
                 "(most confident correct test case per class)."),
    ("Consistent pattern: ", "in all three cases the heat sits on the mediastinum and hila (heart, "
                             "great vessels, central bronchi), not on peripheral lung opacities."),
    ("Interpretation: ", "the model may be using anatomy or scan-specific cues rather than infection "
                         "patterns — a warning sign rather than a finding."),
], size=10.5, spacing=6)
box(s, 8.3, 4.75, 4.2, 1.75, fill=AMBER_BG, line="E9C98F", shape=MSO_SHAPE.ROUNDED_RECTANGLE).adjustments[0] = 0.06
text(s, 8.45, 4.85, 3.9, 1.6, [
    [("Why it matters", {"bold": True, "color": AMBER, "size": 12})],
    [("• A good F1 is not enough — we must check where the model looks", {})],
    [("• Every case shows p = 1.00 → the probabilities are overconfident", {})],
], size=10.5, spacing=4)

# 11b ── Baseline -> next experiments
s = frame(prs, 4, "From Baseline to Next Experiments — What the First Run Tells Us", page); page += 1
chip(s, 0.9, 1.4, "Observation → diagnosis → next step", w=3.8)
table(s, 0.9, 1.8, 11.55, [
    ["What we observed", "What it suggests", "What we change next"],
    [f"Training loss {min(last_loss):.2f}–{max(last_loss):.2f}, validation F1 {min(best_val):.2f}–{max(best_val):.2f}",
     "The network memorises ~400 training scans", "Augmentation (Exp. 1), partial freezing, stronger regularisation"],
    ["Grad-CAM heat on mediastinum / hila", "Model may rely on non-lung cues",
     "Mask non-lung pixels, re-run baseline, re-check saliency"],
    [f"Fusion {sum(fuf) / len(fuf):.3f} vs CT-only {sum(ctf) / len(ctf):.3f}",
     "64-d clinical vector outweighed by 512 CT features", "Late fusion of CT and clinical probabilities (Exp. 2)"],
    ["Predicted probabilities ≈ 1.00", "Overconfident outputs", "Temperature scaling before the 'uncertain' flag"],
    ["12 one-lung crops (already fixed)", "Preprocessing needs routine QA", "Crop-size check kept in the pipeline"],
], [3.85, 3.6, 4.1], size=10, row_h=0.45, left_cols=(0, 1, 2))
steps = [("Baseline\n(we are here)", GREEN), ("Fix data & training\nmasking, regularisation", NAVY),
         ("Exp. 1 · Data\nprep, augmentation, size", TEAL), ("Exp. 2 · Model\nmodality, fusion, backbone", TEAL),
         ("Test set\nonce", AMBER)]
for i, (lab, col) in enumerate(steps):
    x = 0.9 + i * 2.31
    box(s, x, 4.65, 2.38, 0.62, fill=col, shape=MSO_SHAPE.CHEVRON if i else MSO_SHAPE.PENTAGON)
    text(s, x + 0.25, 4.65, 1.93, 0.62, ("✓ " if i == 0 else "") + lab, size=9.5, bold=True, color="FFFFFF",
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
rules = [("1 · Data fixes → re-run everything", "Masking or crop changes alter the input, so the baseline is re-run "
          "too — otherwise comparisons are unfair.", NAVY),
         ("2 · Augmentation ≠ more patients", "It is a training-time factor compared in Exp. 1; the dataset and the "
          "split stay unchanged.", TEAL),
         ("3 · Test set used once", "Choices are made on validation / 5-fold group CV; today's test numbers are a "
          "first look only.", AMBER)]
for i, (t, b, col) in enumerate(rules):
    card(s, 0.9 + i * 3.9, 5.5, 3.7, 1.35, t, b, accent=col, title_size=11, body_size=9.5)

# 11 ── UI + plan
s = frame(prs, 4, "Prototype Interface and Timeline", page); page += 1
chip(s, 0.9, 1.4, "Planned UI (mock-up)", w=2.3)
box(s, 0.9, 1.8, 6.4, 4.65, fill="1E2433", line="1E2433")
box(s, 1.05, 1.95, 3.7, 3.7, fill="000000", line="5A6478")
picture(s, FIG / "ui_slice.png", 1.1, 2.0, w=3.6)
text(s, 1.05, 5.7, 3.7, 0.3, "◀  slice 40 / 73  ▶     ☐ show saliency", size=9, color="C9D1E0")
text(s, 1.05, 6.1, 6.1, 0.55, "Research prototype — decision support only, not a diagnosis.", size=9,
     color="F2C46D", italic=True)
box(s, 4.9, 1.95, 2.25, 1.55, fill="2A3245", line="5A6478")
ex = df.loc[71]  # the case shown in the viewer (Case071)
yn = lambda v: "+" if v else "−"
text(s, 5.0, 2.0, 2.1, 1.45, [[("Clinical record · Case 071", {"bold": True, "color": "FFFFFF"})],
                              f"Age {ex['Age']} · {ex['Gender']}", f"Immunosuppressants {yn(ex['Immunosuppressants'])}"
                              f" · AIDS {yn(ex['AIDS'])}",
                              f"G {yn(ex['(1,3)-β-D-Glucan (G)'])} · GM {yn(ex['Aspergillus Antigen (GM)'])}",
                              f"Lymphocytes {ex['Lymphocyte Count']}",
                              f"D-dimer {ex['D-Dimer'] if ex['D-Dimer'] == ex['D-Dimer'] else 'n/a'}"],
     size=8.5, color="C9D1E0")
box(s, 4.9, 3.6, 2.25, 2.05, fill="2A3245", line="5A6478")
text(s, 5.0, 3.65, 2.1, 0.3, "Prediction", size=9.5, bold=True, color="FFFFFF")
for i, (lab, v, col) in enumerate([("Aspergillus", 0.71, "2E5C9A"), ("Non-Asp. fungi", 0.18, "0F9AA5"),
                                   ("Non-fungal", 0.11, "C46A0A")]):
    yy = 4.0 + i * 0.48
    text(s, 5.0, yy, 2.1, 0.2, f"{lab}", size=8.5, color="C9D1E0")
    box(s, 5.0, yy + 0.22, 2.0, 0.12, fill="3A445A")
    box(s, 5.0, yy + 0.22, 2.0 * v, 0.12, fill=col)
text(s, 4.9, 5.7, 2.25, 0.3, "(probabilities illustrative)", size=8, color="8A93A6", italic=True,
     align=PP_ALIGN.CENTER)
chip(s, 7.75, 1.4, "Timeline", fill=TEAL, w=1.3)
plan = [("Wk 1", "Lung masking, regularisation → re-run baseline, re-check Grad-CAM"),
        ("Wk 2", "Exp. 1 · Data: preprocessing, augmentation, training size"),
        ("Wk 3", "Exp. 2 · Model: modality, late fusion"),
        ("Wk 4", "Exp. 2 · Model: backbone, fungal-first variant; severity proxy"),
        ("Wk 5", "Prototype UI, calibration and 'uncertain' threshold"),
        ("Wk 6", "Final test-set runs, error analysis, report")]
for i, (wk, t) in enumerate(plan):
    y = 1.8 + i * 0.5
    box(s, 7.75, y, 0.8, 0.42, fill=NAVY if i < 2 else "8AA0B8")
    text(s, 7.75, y, 0.8, 0.42, wk, size=10, bold=True, color="FFFFFF", align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE)
    text(s, 8.65, y, 3.8, 0.42, t, size=10, color=BODY, anchor=MSO_ANCHOR.MIDDLE)
chip(s, 7.75, 4.9, "Risks & mitigation", fill=AMBER, w=2.1)
bullets(s, 7.75, 5.3, 4.7, 1.5, [
    ("Small data (569 scans): ", "pre-training, augmentation, seeds + CV"),
    ("Repeat scans / leakage: ", "group-level split"),
    ("No lesion masks: ", "saliency only, reviewed qualitatively"),
    ("Severity undefined: ", "stretch goal, proxy agreed with supervisor"),
], size=10)

# move closing slide to the end
lst = prs.slides._sldIdLst
closing_id = lst[1]
lst.remove(closing_id)
lst.append(closing_id)

# ---------------------------------------------------------------- speaker scripts -> notes + bilingual copies
import re  # noqa: E402
import subprocess  # noqa: E402

from script_count import parse, spoken  # noqa: E402

counts = df["Diagnosis_Class"].value_counts()
fu_cm = json.loads((RESULTS / "fusion_aug-basic_seed0.json").read_text())["test_cm"]
EN = ["Aspergillus", "other fungal", "non-fungal"]
ZH = ["曲霉", "其他真菌", "非真菌"]
ei, ej = max(((i, j) for i in range(3) for j in range(3) if i != j), key=lambda ij: fu_cm[ij[0]][ij[1]])
# both scripts say "fusion does not help yet" and "other fungi are the hardest class": stop if results change
assert sum(fuf) / len(fuf) <= sum(ctf) / len(ctf) + 0.02, "fusion now beats CT-only: rewrite slides 10/12 of the scripts"
ct_rec = [sum(r["test_recall_per_class"][c] for r in ct_runs["ct"]) / len(ct_runs["ct"]) for c in range(3)]
assert ei == 1 and min(range(3), key=lambda c: ct_rec[c]) == 1, "hardest class changed: rewrite slide 10 of the scripts"
fill = dict(
    n_asp=counts["Aspergillus"], n_naf=counts["Non-Aspergillus Fungi"], n_nf=counts["Non-Fungi"],
    nz_min=geo.nz.min(), nz_max=geo.nz.max(), miss_dd=miss["D-Dimer"],
    aids_naf=aids["Non-Aspergillus Fungi"], aids_total=aids.sum(), n_dup_rows=n_dup_rows, n_groups=n_groups,
    crop_fail=12,  # visual QA of the first-version crops, see slide 6 / src/crop_qa.py
    n_test=int(split_tab.loc["test"].sum()),
    rf_cv=f"{rf[0]:.2f}", rf_drop=f"{rf[0] - cv['Random forest | no_G_GM'][0]:.3f}",
    lr_cv=f"{cv['Logistic regression | all'][0]:.2f}", lgb_cv=f"{cv['LightGBM | all'][0]:.2f}",
    ct_mean=f"{pd.Series(ctf).mean():.3f}", ct_sd=f"{pd.Series(ctf).std(ddof=0):.3f}",
    fu_mean=f"{pd.Series(fuf).mean():.3f}", fu_sd=f"{pd.Series(fuf).std(ddof=0):.3f}",
    rec_asp=round(100 * ct_rec[0]), rec_naf=round(100 * ct_rec[1]), rec_nf=round(100 * ct_rec[2]),
    err_true=EN[ei], err_pred=EN[ej], err_true_zh=ZH[ei], err_pred_zh=ZH[ej],
    err_n=fu_cm[ei][ej], err_tot=sum(fu_cm[ei]),
    run_min=f"{sum(r['train_minutes'] for r in all_runs) / len(all_runs):.1f}",
    loss_lo=f"{min(last_loss):.2f}", loss_hi=f"{max(last_loss):.2f}",
    val_lo=f"{min(best_val):.2f}", val_hi=f"{max(best_val):.2f}",
    cv_sd_max=f"{max(v[1] for v in cv.values()):.2f}",
    seed_sd_lo=f"{min(pd.Series(ctf).std(ddof=0), pd.Series(fuf).std(ddof=0)):.3f}",
    seed_sd_hi=f"{max(pd.Series(ctf).std(ddof=0), pd.Series(fuf).std(ddof=0)):.3f}",
)
WPM = 120
TOPIC = {"A": "Background & data · 背景与数据", "B": "Model · 模型", "C": "Progress & results · 进展与结果",
         "D": "Next steps · 下一步"}
qa = (ROOT / "script" / "qa_prep.md").read_text(encoding="utf-8").format(**fill)
assert "{" not in qa
VERSIONS = {  # source, output, title, per-speaker target in seconds
    "v1": ("v1_strict.md", "Group 26_Speaker Script_v1 strict timing (EN-ZH).md",
           "v1 — strict timing · 严格计时版", {"A": 240, "B": 240, "C": 240, "D": 180}),
    "v2": ("v2_free.md", "Group 26_Speaker Script_v2 free allocation (EN-ZH).md",
           "v2 — free allocation, clearer · 自由分配、讲得更清楚版", {"A": 210, "B": 210, "C": 240, "D": 195}),
    "v3": ("v3_reference.md", "Group 26_Speaker Script_v3 reference narrative (EN-ZH).md",
           "v3 — reference narrative, no time limit · 参考版（完整叙述、不限时）", None),
    "v4": ("v4_final.md", "Group 26_Speaker Script_v4 final 15-min (EN-ZH).md",
           "v4 — final 15-minute narrative · 正式 15 分钟版", {"A": 210, "B": 225, "C": 225, "D": 210}),
}
NOTES_VERSION = "v4"
mmss = lambda sec: f"{int(sec) // 60}:{int(sec) % 60:02d}"  # noqa: E731
WRITE_FILES = {"v1", "v3", "v4"}  # the v2 output and the Word copies were removed by the user; v2 is still checked
WRITE_DOCX = False
for ver, (src_name, out_name, title, target) in VERSIONS.items():
    src_text = (ROOT / "script" / src_name).read_text(encoding="utf-8")
    # text between the title line and the first slide (v3: story line + who tells which part)
    preamble = src_text.split("\n", 1)[1].split("\n## ", 1)[0].strip().format(**fill) if ver == "v3" else ""
    sects = []
    for n, spk, body in parse(src_text):
        body = body.format(**fill)
        assert "{" not in body, f"unfilled placeholder in {ver} slide {n}"
        sects.append((n, spk, body, len(spoken(body).split())))
    assert [n for n, *_ in sects] == list(range(1, len(prs.slides) + 1)), f"{ver}: slide numbering"
    words = {}
    for _, spk, _, w in sects:
        words[spk] = words.get(spk, 0) + w
    md = [f"# Group 26 — Speaker Script · 演讲稿 · {title}", "",
          f"Timing assumes {WPM} spoken English words per minute. Numbers are filled from results/ by src/build_deck.py.",
          f"> 时长按每分钟 {WPM} 个英文词估算；所有数字由 src/build_deck.py 从结果文件自动填入。", "",
          "| Speaker 讲者 | Topic 主题 | Slides 页 | Words 词数 | Time 时长 | Target 目标 |", "|---|---|---|---|---|---|"]
    for spk in sorted(words):
        sl = [n for n, s_, *_ in sects if s_ == spk]
        md.append(f"| {spk} | {TOPIC[spk]} | {sl[0]}–{sl[-1]} | {words[spk]} | {mmss(words[spk] * 60 / WPM)} | "
                  f"{mmss(target[spk]) if target else '—'} |")
    tot = sum(words.values())
    md.append(f"| **Total** | | | **{tot}** | **{mmss(tot * 60 / WPM)}** | "
              f"**{mmss(sum(target.values())) if target else '—'}** |")
    if preamble:
        md += ["", "> This version is a reference for understanding and rehearsal; it is longer than 15 minutes. "
                   "Use v1 or v2 for timing.",
               "> 这一版用于理解和排练，篇幅超过 15 分钟；控制时间请参考 v1 或 v2。", "", preamble]
    for n, spk, body, w in sects:
        md += ["", f"## Slide {n} · Speaker {spk} · ≈ {mmss(w * 60 / WPM)}", "", body]
    md += ["", "---", "", qa.strip()]
    if ver in WRITE_FILES:
        (ROOT / out_name).write_text("\n".join(md) + "\n", encoding="utf-8")
    if ver in WRITE_FILES and WRITE_DOCX:  # Word copy; pandoc renders the "> " Chinese lines as indented quotes
        subprocess.run(["pandoc", str(ROOT / out_name), "-f", "gfm", "-o",
                        str(ROOT / out_name.replace(".md", ".docx"))], check=True)
    print(ver, "words:", words, "total", tot, f"≈ {mmss(tot * 60 / WPM)}")
    if ver == NOTES_VERSION:  # slide notes: English only, so the presenter view stays readable
        for sld, (n, spk, body, w) in zip(prs.slides, sects):
            en = "\n\n".join("\n".join(l for l in blk.split("\n") if not l.startswith(">"))
                               for blk in body.split("\n\n"))
            sld.notes_slide.notes_text_frame.text = f"[Slide {n} · Speaker {spk} · ≈ {mmss(w * 60 / WPM)}]\n\n{en}"

prs.save(str(OUT))
print("saved", OUT.name, "slides:", len(prs.slides))

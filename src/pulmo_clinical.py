"""Clinical preprocessing for fusion inference, fitted on training rows exactly as in training.

validate_clinical checks every field and reports all problems at once; clinical_summary records what the
model actually received. Missing numbers use the training-split median. Binary fields and sex have no
"unknown" encoding in training, so they are required and never silently filled in.
"""
from functools import lru_cache
import hashlib
import math
import numbers

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from common import SPLIT_CSV, NUMERIC, BINARY, CATEGORICAL, load_clinical

FIELDS = NUMERIC + BINARY + CATEGORICAL
SEXES = ('M', 'F')
AGE_MAX = 120
# The dataset gives no units; values must use the same units as the original table.
UNITS = {'Age': 'years', 'Lymphocyte Count': 'not stated in the dataset; check the original source',
         'D-Dimer': 'not stated in the dataset; check the original source'}


class ClinicalError(ValueError):
    """Invalid clinical input; field_errors maps each offending field to a displayable message."""

    def __init__(self, field_errors):
        self.field_errors = field_errors
        super().__init__(' '.join(field_errors.values()))


@lru_cache(maxsize=1)
def clinical_setup():
    df = load_clinical().join(pd.read_csv(SPLIT_CSV, index_col=0)['split'])
    pre = ColumnTransformer([
        ('num', make_pipeline(SimpleImputer(strategy='median'), StandardScaler()), NUMERIC),
        ('bin', 'passthrough', BINARY),
        ('cat', OneHotEncoder(handle_unknown='ignore'), CATEGORICAL),
    ])
    pre.fit(df.loc[df.split == 'train', FIELDS])
    return df, pre


def clinical_width():
    df, pre = clinical_setup()
    return pre.transform(df.iloc[:1][FIELDS]).shape[1]


@lru_cache(maxsize=1)
def training_reference():
    """Imputation values and provenance of the fitted preprocessing (training rows only)."""
    df, pre = clinical_setup()
    medians = pre.named_transformers_['num'].named_steps['simpleimputer'].statistics_
    # Hash with normalised line endings so Windows and Linux checkouts agree.
    split_hash = hashlib.sha256(SPLIT_CSV.read_bytes().replace(b'\r\n', b'\n')).hexdigest()[:12]
    return dict(medians={k: float(v) for k, v in zip(NUMERIC, medians)}, train_rows=int((df.split == 'train').sum()),
                split_file=SPLIT_CSV.name, split_sha256=split_hash,
                imputation='median of the training split', scaling='standardised with training-split mean and SD',
                encoding=dict(binary='0 = no, 1 = yes', sex='M / F as coded in the dataset'))


def _blank(val):
    return val is None or (isinstance(val, str) and not val.strip()) or (isinstance(val, float) and math.isnan(val))


def _number(name, val):
    if _blank(val):
        return np.nan, None
    if isinstance(val, (bool, np.bool_)) or not isinstance(val, (numbers.Real, str)):
        return None, f'{name} must be a number or left blank.'
    try:
        x = float(val)
    except ValueError:
        return None, f'{name} must be a number or left blank.'
    if not math.isfinite(x) or x < 0:
        return None, f'{name} must be a non-negative number or left blank.'
    if name == 'Age' and x > AGE_MAX:
        return None, f'Age must be between 0 and {AGE_MAX}.'
    return x, None


def validate_clinical(values):
    """Return the model-ready row; raise ClinicalError listing every invalid field."""
    if not isinstance(values, dict):
        raise ClinicalError({'clinical': 'Clinical inputs must be an object of field values.'})
    row, errors = {}, {}
    for name in NUMERIC:
        row[name], error = _number(name, values.get(name))
        if error:
            errors[name] = error
    for name in BINARY:
        val = values.get(name)
        if _blank(val):
            errors[name] = f'Please specify {name}. This model has no unknown encoding for binary fields.'
        elif isinstance(val, (bool, np.bool_, str)) or val not in (0, 1):
            errors[name] = f'{name} must be 0 (no) or 1 (yes).'
        else:
            row[name] = int(val)
    sex = values.get('Gender')
    if sex not in SEXES:
        errors['Gender'] = 'Please specify sex as encoded by the training dataset (M/F).'
    row['Gender'] = sex
    if errors:
        raise ClinicalError(errors)
    return row


def clinical_vector(values):
    row = validate_clinical(values)
    _, pre = clinical_setup()
    return pre.transform(pd.DataFrame([row])[FIELDS]).astype(np.float32)


def clinical_summary(values):
    """What the fusion model actually used: each field's submitted value, used value and its source."""
    row, ref = validate_clinical(values), training_reference()
    fields = []
    for name in FIELDS:
        missing = name in NUMERIC and np.isnan(row[name])
        fields.append(dict(field=name, kind='numeric' if name in NUMERIC else 'binary' if name in BINARY else 'categorical',
                           submitted=None if missing else row[name], used=ref['medians'][name] if missing else row[name],
                           source='training median' if missing else 'user input', unit=UNITS.get(name)))
    ignored = sorted(k for k in values if k not in FIELDS)
    return dict(used=True, fields=fields, imputed=[f['field'] for f in fields if f['source'] != 'user input'],
                ignored_fields=ignored, preprocessing={k: ref[k] for k in ref if k != 'medians'})

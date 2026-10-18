"""Clinical preprocessing for fusion inference, fitted on training rows exactly as in training."""
from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from common import SPLIT_CSV, NUMERIC, BINARY, CATEGORICAL, load_clinical

FIELDS = NUMERIC + BINARY + CATEGORICAL


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


def clinical_vector(values):
    row = {}
    for name in NUMERIC:
        val = values.get(name)
        row[name] = np.nan if val is None or val == '' else float(val)
        if not np.isnan(row[name]) and (not np.isfinite(row[name]) or row[name] < 0):
            raise ValueError(f'{name} must be a non-negative number or left blank.')
    if not np.isnan(row['Age']) and row['Age'] > 120:
        raise ValueError('Age must be between 0 and 120.')
    for name in BINARY:
        if values.get(name) not in (0, 1):
            raise ValueError(f'Please specify {name}. This model has no unknown encoding for binary fields.')
        row[name] = int(values[name])
    if values.get('Gender') not in ('M', 'F'):
        raise ValueError('Please specify sex as encoded by the training dataset (M/F).')
    row['Gender'] = values['Gender']
    _, pre = clinical_setup()
    return pre.transform(pd.DataFrame([row])[FIELDS]).astype(np.float32)

"""Type inference, safe coercion and the sklearn preprocessing pipeline."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def infer_feature_types(X: pd.DataFrame) -> dict[str, str]:
    types = {}
    for col in X.columns:
        s = X[col]
        numeric = pd.api.types.is_bool_dtype(s) or pd.api.types.is_numeric_dtype(s)
        types[col] = "numeric" if numeric else "categorical"
    return types


def _clean_category(value):
    if isinstance(value, (list, dict, tuple, set)):
        return str(value)
    if value is None or pd.isna(value):
        return np.nan
    text = str(value).strip()
    return text if text else np.nan


def coerce_frame(X: pd.DataFrame, types: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Coerce columns to their trained type.

    Returns (clean_frame, bad_mask). bad_mask[col] is True where a value was present
    but could not be interpreted (e.g. "abc" in a numeric column, or +/-inf).
    """
    clean, bad = {}, {}
    for col, kind in types.items():
        raw = X[col]
        if kind == "numeric":
            num = pd.to_numeric(raw, errors="coerce").astype(float)
            num = num.replace([np.inf, -np.inf], np.nan)
            bad[col] = (raw.notna() & num.isna()).to_numpy()
            clean[col] = num
        else:
            cleaned = pd.Series([_clean_category(v) for v in raw], index=raw.index, dtype=object)
            bad[col] = np.zeros(len(raw), dtype=bool)
            clean[col] = cleaned
    cols = list(types)
    return pd.DataFrame(clean, index=X.index)[cols], pd.DataFrame(bad, index=X.index)[cols]


def build_preprocessor(types: dict[str, str]) -> ColumnTransformer:
    numeric = [c for c, t in types.items() if t == "numeric"]
    categorical = [c for c, t in types.items() if t == "categorical"]
    parts = []
    if numeric:
        parts.append(("numeric", Pipeline([
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scaler", StandardScaler()),
        ]), numeric))
    if categorical:
        parts.append(("categorical", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent", keep_empty_features=True)),
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), categorical))
    if not parts:
        raise ValueError("No usable features.")
    return ColumnTransformer(parts, remainder="drop", verbose_feature_names_out=False)

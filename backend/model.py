"""
model.py – Crypto Volatility ML pipeline
Loads dataset from mainfile.zip, preprocesses, trains a Random Forest,
and exposes a predict() function used by the Flask API.
"""

import os
import zipfile
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIP_PATH = os.path.join(BASE_DIR, "mainfile.zip")
EXTRACT_PATH = os.path.join(BASE_DIR, "data_extracted")

FEATURES = ["open", "high", "low", "close", "volume", "marketcap"]
TARGET = "volatility_14d"

# ── Module-level singletons ────────────────────────────────────────────────────
_model: RandomForestRegressor | None = None
_scaler: StandardScaler | None = None
_df_raw: pd.DataFrame | None = None          # cleaned, unscaled master frame
_crypto_list: list[str] = []


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_csv() -> pd.DataFrame:
    """Extract dataset.csv from mainfile.zip and return raw DataFrame."""
    os.makedirs(EXTRACT_PATH, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        # find the csv inside the zip (any name)
        csv_name = next(n for n in z.namelist() if n.endswith(".csv"))
        z.extract(csv_name, EXTRACT_PATH)
    csv_path = os.path.join(EXTRACT_PATH, csv_name)
    return pd.read_csv(csv_path)


def _preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """Reproduce the notebook preprocessing steps."""
    # Standardise column names
    df.columns = df.columns.str.lower().str.replace(" ", "_")

    # Rename symbol column if needed
    if "symbol" not in df.columns:
        if "crypto_name" in df.columns:
            df.rename(columns={"crypto_name": "symbol"}, inplace=True)
        elif "unnamed:_0" in df.columns:
            df.rename(columns={"unnamed:_0": "symbol"}, inplace=True)

    # Rename marketcap variants
    if "marketcap" not in df.columns and "market_cap" in df.columns:
        df.rename(columns={"market_cap": "marketcap"}, inplace=True)

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"])

    # Missing / invalid values
    df.ffill(inplace=True)
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.dropna(inplace=True)
    df.drop_duplicates(inplace=True)

    # Feature engineering
    df["daily_return"] = df.groupby("symbol")["close"].pct_change()
    df["volatility_14d"] = (
        df.groupby("symbol")["daily_return"]
        .rolling(14)
        .std()
        .reset_index(level=0, drop=True)
    )
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.dropna(inplace=True)

    return df


def _train(df: pd.DataFrame):
    """Scale features and train the Random Forest model."""
    global _model, _scaler

    scaler = StandardScaler()
    X = scaler.fit_transform(df[FEATURES])
    y = df[TARGET].values

    model = RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1)
    model.fit(X, y)

    _model = model
    _scaler = scaler


# ── Public API ─────────────────────────────────────────────────────────────────

def load_and_train() -> pd.DataFrame:
    """
    Full pipeline: extract → preprocess → train.
    Returns the cleaned, unscaled DataFrame for database seeding.
    """
    global _df_raw, _crypto_list

    raw = _extract_csv()
    df = _preprocess(raw)
    _df_raw = df.copy()
    _crypto_list = sorted(df["symbol"].unique().tolist())
    _train(df)
    print(f"[model] Trained on {len(df):,} rows | {len(_crypto_list)} cryptos")
    return df


def get_crypto_list() -> list[str]:
    return _crypto_list


def predict(open_: float, high: float, low: float, close: float,
            volume: float, marketcap: float) -> float:
    """Predict 14-day rolling volatility for given OHLCV + marketcap values."""
    if _model is None or _scaler is None:
        raise RuntimeError("Model not trained yet. Call load_and_train() first.")
    X = np.array([[open_, high, low, close, volume, marketcap]])
    X_scaled = _scaler.transform(X)
    return float(_model.predict(X_scaled)[0])


def get_coin_history(symbol: str, n: int = 90) -> list[dict]:
    """
    Return last n rows for a given symbol with date, close price,
    and computed volatility.
    """
    if _df_raw is None:
        raise RuntimeError("Data not loaded yet.")
    sub = _df_raw[_df_raw["symbol"] == symbol].tail(n)
    result = []
    for _, row in sub.iterrows():
        result.append({
            "date": str(row["date"])[:10],
            "open": round(float(row["open"]), 6),
            "high": round(float(row["high"]), 6),
            "low": round(float(row["low"]), 6),
            "close": round(float(row["close"]), 6),
            "volume": round(float(row["volume"]), 2),
            "marketcap": round(float(row["marketcap"]), 2),
            "volatility_14d": round(float(row["volatility_14d"]), 6),
        })
    return result


def get_market_summary() -> dict:
    """
    Returns top-5 most volatile and top-5 least volatile coins
    based on average 14-day volatility across all history.
    """
    if _df_raw is None:
        raise RuntimeError("Data not loaded yet.")
    agg = (
        _df_raw.groupby("symbol")["volatility_14d"]
        .mean()
        .reset_index()
        .rename(columns={"volatility_14d": "avg_volatility"})
        .sort_values("avg_volatility", ascending=False)
    )
    top_volatile = agg.head(5).to_dict(orient="records")
    least_volatile = agg.tail(5).to_dict(orient="records")

    return {
        "total_cryptos": len(_crypto_list),
        "top_volatile": [
            {"symbol": r["symbol"], "avg_volatility": round(r["avg_volatility"], 6)}
            for r in top_volatile
        ],
        "least_volatile": [
            {"symbol": r["symbol"], "avg_volatility": round(r["avg_volatility"], 6)}
            for r in least_volatile
        ],
        "market_avg_volatility": round(float(agg["avg_volatility"].mean()), 6),
    }

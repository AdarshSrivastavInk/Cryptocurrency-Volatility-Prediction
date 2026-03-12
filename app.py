"""
app.py – Flask REST API for the Crypto Volatility Prediction platform.

Endpoints:
  GET  /                          → serves frontend/index.html
  GET  /api/cryptos               → list of all available symbols
  GET  /api/volatility/<symbol>   → last 90 rows (price + volatility) for a coin
  GET  /api/summary               → market dashboard stats
  POST /api/predict               → custom OHLCV prediction
  GET  /api/history               → paginated prediction logs

Run:
  python app.py
"""

import os
import sys
from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS

from database import db, CryptoRecord, PredictionLog
import model as ml

# ── App Setup ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")
DB_PATH = os.path.join(BASE_DIR, "crypto_volatility.db")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

CORS(app)
db.init_app(app)


# ── DB Seeding ─────────────────────────────────────────────────────────────────

def seed_database(df):
    """Bulk-insert processed rows into SQLite if the table is empty."""
    with app.app_context():
        if CryptoRecord.query.count() > 0:
            print("[db] Database already seeded – skipping.")
            return

        print("[db] Seeding database …")
        batch = []
        for _, row in df.iterrows():
            batch.append(CryptoRecord(
                symbol=str(row["symbol"]),
                date=str(row["date"])[:10],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                marketcap=float(row["marketcap"]),
                daily_return=float(row.get("daily_return", 0) or 0),
                volatility_14d=float(row.get("volatility_14d", 0) or 0),
            ))
            if len(batch) >= 2000:
                db.session.bulk_save_objects(batch)
                db.session.commit()
                batch = []

        if batch:
            db.session.bulk_save_objects(batch)
            db.session.commit()

        print(f"[db] Seeded {CryptoRecord.query.count():,} rows.")


# ── Serve Frontend ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


# ── API ────────────────────────────────────────────────────────────────────────

@app.route("/api/cryptos", methods=["GET"])
def get_cryptos():
    """Return sorted list of all crypto symbols + basic stats."""
    symbols = ml.get_crypto_list()
    result = []
    for sym in symbols:
        rows = CryptoRecord.query.filter_by(symbol=sym).order_by(
            CryptoRecord.date.desc()
        ).first()
        result.append({
            "symbol": sym,
            "latest_close": round(rows.close, 4) if rows else None,
            "latest_volatility": round(rows.volatility_14d, 6) if rows else None,
            "latest_date": rows.date if rows else None,
        })
    return jsonify({"count": len(result), "cryptos": result})


@app.route("/api/volatility/<symbol>", methods=["GET"])
def get_volatility(symbol: str):
    """Return last n rows (default 90) of price + volatility for a symbol."""
    n = min(int(request.args.get("n", 90)), 365)
    records = (
        CryptoRecord.query
        .filter_by(symbol=symbol)
        .order_by(CryptoRecord.date.asc())
        .all()
    )
    if not records:
        abort(404, description=f"Symbol '{symbol}' not found.")
    records = records[-n:]
    return jsonify({
        "symbol": symbol,
        "count": len(records),
        "data": [r.to_dict() for r in records],
    })


@app.route("/api/summary", methods=["GET"])
def get_summary():
    """Return market dashboard stats (top volatile, least volatile, avg)."""
    summary = ml.get_market_summary()
    return jsonify(summary)


@app.route("/api/predict", methods=["POST"])
def predict():
    """
    Predict 14-day volatility for user-supplied OHLCV values.
    Body (JSON): { open, high, low, close, volume, marketcap }
    """
    data = request.get_json(force=True)
    required = ["open", "high", "low", "close", "volume", "marketcap"]
    missing = [k for k in required if k not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    try:
        open_ = float(data["open"])
        high = float(data["high"])
        low = float(data["low"])
        close = float(data["close"])
        volume = float(data["volume"])
        marketcap = float(data["marketcap"])
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400

    volatility = ml.predict(open_, high, low, close, volume, marketcap)

    # Persist to log
    log = PredictionLog(
        open=open_, high=high, low=low, close=close,
        volume=volume, marketcap=marketcap,
        predicted_volatility=volatility,
    )
    db.session.add(log)
    db.session.commit()

    # Interpret result
    level = "High" if volatility > 0.08 else ("Moderate" if volatility > 0.03 else "Low")
    return jsonify({
        "predicted_volatility": round(volatility, 6),
        "volatility_level": level,
        "interpretation": (
            f"The model predicts a 14-day rolling volatility of "
            f"{round(volatility * 100, 3)}%, which is classified as {level}."
        ),
    })


@app.route("/api/history", methods=["GET"])
def prediction_history():
    """Return the last 20 manual predictions."""
    logs = PredictionLog.query.order_by(PredictionLog.timestamp.desc()).limit(20).all()
    return jsonify({"predictions": [l.to_dict() for l in logs]})


# ── Startup ────────────────────────────────────────────────────────────────────

def startup():
    with app.app_context():
        db.create_all()

    print("[app] Loading dataset and training model …")
    try:
        df = ml.load_and_train()
        seed_database(df)
    except FileNotFoundError:
        print("[app] WARNING: mainfile.zip not found. API will run with limited functionality.")

    app.run(debug=False, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    startup()

"""
database.py – SQLite models using Flask-SQLAlchemy.
The CryptoRecord table stores raw OHLCV + computed volatility for every
symbol/date row so the API can serve data without re-running pandas every time.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class CryptoRecord(db.Model):
    __tablename__ = "crypto_records"

    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(64), nullable=False, index=True)
    date = db.Column(db.String(10), nullable=False, index=True)  # "YYYY-MM-DD"
    open = db.Column(db.Float)
    high = db.Column(db.Float)
    low = db.Column(db.Float)
    close = db.Column(db.Float)
    volume = db.Column(db.Float)
    marketcap = db.Column(db.Float)
    daily_return = db.Column(db.Float)
    volatility_14d = db.Column(db.Float)

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "date": self.date,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "marketcap": self.marketcap,
            "daily_return": self.daily_return,
            "volatility_14d": self.volatility_14d,
        }


class PredictionLog(db.Model):
    """Logs every user-submitted prediction for audit/analytics."""
    __tablename__ = "prediction_logs"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())
    open = db.Column(db.Float)
    high = db.Column(db.Float)
    low = db.Column(db.Float)
    close = db.Column(db.Float)
    volume = db.Column(db.Float)
    marketcap = db.Column(db.Float)
    predicted_volatility = db.Column(db.Float)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": str(self.timestamp),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "marketcap": self.marketcap,
            "predicted_volatility": self.predicted_volatility,
        }

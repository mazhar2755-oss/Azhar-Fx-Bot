import os
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pyquotex.stable_api import Quotex

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")

client = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)

def calculate_signal(candles, sentiment):
    if not candles or len(candles) < 30:
        return {"direction": "WAIT", "strength": 0}

    df = pd.DataFrame(list(candles.values())).sort_values("time")
    df["ema9"] = df["close"].ewm(span=9, adjust=False).mean()
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    last = df.iloc[-1]
    buy_pct = sentiment.get("sentiment", {}).get("buy", 50)

    if last["ema9"] > last["ema21"] and last["rsi"] > 50:
        strength = min(95, int(60 + (last["rsi"] - 50) + (buy_pct - 50)))
        return {"direction": "CALL", "strength": max(55, strength)}

    if last["ema9"] < last["ema21"] and last["rsi"] < 50:
        strength = min(95, int(60 + (50 - last["rsi"]) + (50 - buy_pct)))
        return {"direction": "PUT", "strength": max(55, strength)}

    return {"direction": "WAIT", "strength": 0}

@app.on_event("startup")
async def startup():
    await client.connect()
    print("Quotex connected")

@app.get("/signal")
async def get_signal(asset: str, period: int = 60):
    try:
        candles = await client.get_realtime_candles(asset, period)
        sentiment = await client.get_realtime_sentiment(asset)
        return calculate_signal(candles, sentiment)
    except Exception as e:
        return {"direction": "ERROR", "strength": 0, "message": str(e)}

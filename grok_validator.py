from fastapi import FastAPI, Request
import finnhub
import httpx
import uvicorn
import os
from datetime import datetime

app = FastAPI()

FINNHUB_KEY = os.getenv("FINNHUB_KEY")
XAI_KEY     = os.getenv("XAI_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "")

finnhub_client = finnhub.Client(api_key=FINNHUB_KEY)
xai_headers = {"Authorization": f"Bearer {XAI_KEY}"}

def send_to_discord(message: str):
    if DISCORD_WEBHOOK:
        httpx.post(DISCORD_WEBHOOK, json={"content": message})

@app.post("/webhook")
async def tradingview_webhook(request: Request):
    payload = await request.json()
    symbol  = payload.get("symbol", "SPX")
    reason  = payload.get("reason", "No reason")
    now = datetime.now().strftime("%H:%M:%S")

    quote   = finnhub_client.quote(symbol)
    candles = finnhub_client.stock_candles(symbol, '1', int(datetime.now().timestamp())-3600, int(datetime.now().timestamp()))

    grok_prompt = f"""
    [INSTANT VALIDATION - Day-trade style]
    Symbol: {symbol} | Price: {quote['c']}
    Today range: {min(candles['l'])} – {max(candles['h'])}
    Last 30-min range: {min(candles['l'][-30:])} – {max(candles['h'][-30:])}
    Alert reason: {reason}
    Reply exactly:
    GREEN LIGHT – [1 short reason]
    or
    RED LIGHT – [1 short reason]
    """

    resp = httpx.post("https://api.x.ai/v1/chat/completions",
        headers=xai_headers,
        json={"model": "grok-2-128k", "messages": [{"role": "user", "content": grok_prompt}], "temperature": 0.1, "max_tokens": 100},
        timeout=12)

    decision = resp.json()["choices"][0]["message"]["content"].strip()
    msg = f"**{now} | {symbol}** → {decision}"
    print(msg)
    send_to_discord(msg)

    return {"decision": decision}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

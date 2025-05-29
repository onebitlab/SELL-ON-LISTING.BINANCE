# 🚀 Binance Sell on Listing Script

This Python script automatically places a **limit sell order** immediately after a new token is listed on Binance, at a configurable price below the market. It is optimized for **speed**, **precision**, and **safety** during high-volatility listing events.

> ⚡️ Built using **asynchronous programming (`async/await`)** for maximum responsiveness with the Binance API.

---

## ✅ Features

- ⏰ Starts checking the listing **10 seconds before** your specified launch time.
- 🕒 Synchronizes local time with **Binance server time** to avoid clock drift.
- 🔄 Continuously checks for trading pair availability via **Binance REST API**.
- 💰 Automatically places a **limit sell order** at a price below market (offset configurable).
- 🔍 If the order isn’t filled within a timeout (default: 30 seconds), it is cancelled.

---

## ⚙️ Configuration

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `config.py` file in the root directory with your preferences:

```python
# config.py

api_key = 'your_binance_api_key'
api_secret = 'your_binance_api_secret'

# Trading configuration
pair = "ALTUSDT"                     # Example: 'SOMETOKENUSDT'
coins_for_sale = "100"              # Amount of tokens to sell
price_offset_percent = "1.0"        # Percent below market price (e.g., 1.0 means 1% below)

# Timing
order_timeout_seconds = 30          # Cancel order after this many seconds if not filled
pair_check_interval_seconds = 0.5   # Interval (in sec) between symbol availability checks
launch_time = "2025-05-29 12:00:00" # Exact time trading is expected to start (UTC)
```

> ✅ Make sure your API key has **trading permissions enabled**.

---

## ▶️ Usage

Simply run:

```bash
python main.py
```

---

## 🛠 Notes

- Time format for `launch_time` must be `"YYYY-MM-DD HH:MM:SS"` in **UTC**.
- If you launch the bot after the listing time has passed, it will immediately begin checking for the pair.

---

## 📄 License

MIT License — free to use, modify, and distribute.

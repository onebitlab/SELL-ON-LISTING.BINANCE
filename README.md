# 🚀 Binance sell on listing script

This Python script monitors a new token listing on Binance and automatically places a limit sell order **at a configurable price below the market price**. Ideal for quickly selling newly listed tokens at a favorable price.

> ⚡️ Built using **asynchronous programming (async/await)** to achieve **maximum speed** and minimal latency during listing events.

---

## ✅ Features

- The script waits until the specified trading pair is listed on BINANCE (via REST API).
- It retrieves your token balance and current market price.
- It applies a configurable percentage offset (e.g. -1%) to determine the target price.
- It places a **limit sell order** BELOW current price using async API calls.
- If the order isn't filled within the timeout (default: 30 seconds), it is cancelled.

---

## ⚙️ Configuration

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a file named `config.py` in the project root:

```python
# config.py
api_key = 'your_binance_api_key'
api_secret = 'your_binance_api_secret'
pair = "ALTUSDT"
coins_for_sale = "100"
price_offset_percent = "1.0"
order_timeout_seconds = 30            # Timeout before canceling limit order (in seconds)
pair_check_interval_seconds = 0.5     # Interval to check if pair is listed (in seconds)
```

Make sure your API key has **trading permissions enabled**.

---

## ▶️ Usage

Run the script:

```bash
python main.py
```

## 📄 License

MIT License. Free to use and modify.
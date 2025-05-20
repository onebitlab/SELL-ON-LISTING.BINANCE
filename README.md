# 🚀 Binance sell on listing Bot

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
```

Make sure your API key has **trading permissions enabled**.

---

## ▶️ Usage

Run the script:

```bash
python main.py
```

You’ll be prompted to enter:

- **Trading pair** (e.g. `ALTUSDT`)
- **Amount of tokens** to sell (e.g. `12.5`)
- **Price offset** percentage (e.g. `1` for 1% below current price)


## 📄 License

MIT License. Free to use and modify.
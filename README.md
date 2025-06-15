# 🚀 Binance Sell on Listing Bot

This Python script automatically places a limit sell order immediately after a new token is listed on Binance, at a configurable price below the market. It's built for speed, precision, and safety during high-volatility listing events.

---

## ⚡️ Features

- **Async/await**: Built using asynchronous programming for maximum responsiveness with the Binance API.
- **Time synchronization**: Syncs local time with Binance server time to avoid clock drift.
- **Automatic start**: Begins checking for the trading pair 10 seconds before your specified launch time.
- **Continuous monitoring**: Polls the Binance REST API for the appearance of the trading pair.
- **Smart price and quantity calculation**: Applies Binance's `PRICE_FILTER` and `LOT_SIZE` to ensure your order meets exchange requirements.
- **Robust retry mechanism**: Retries fetching the current price to handle temporary network issues.
- **Automatic cancellation**: If the order isn't filled within a timeout (default: 30 seconds), it is cancelled.
- **Graceful shutdown**: Handles Ctrl-C (KeyboardInterrupt) and closes all Binance connections properly.
- **Tabular order output**: Uses [tabulate](https://pypi.org/project/tabulate/) for clear, structured order logs.

---

## ⚙️ Configuration

1. **Install dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

2. **Create a `config.py` file in the root directory:**
    ```python
    # config.py

    api_key = 'your_binance_api_key'
    api_secret = 'your_binance_api_secret'

    # Trading configuration
    pair = "ALTUSDT"                    # Example: 'SOMETOKENUSDT'
    coins_for_sale = "100"              # Amount of tokens to sell
    price_offset_percent = "1.0"        # Percent below market price (e.g., 1.0 means 1% below)

    # Timing
    order_timeout_seconds = 30          # Cancel order after this many seconds if not filled
    pair_check_interval_seconds = 0.5   # Interval (in sec) between trade pair availability checks
    launch_time_str = "2025-05-29 12:00:00" # Exact time trading is expected to start (UTC)
    ```

---

## ⚠️ Important: API Key Permissions

Make sure your Binance API key has **"Enable Spot & Margin Trading"** permission enabled.  
If you encounter an "Invalid API-key, IP, or permissions for action" error, check your API key, secret, and any IP restrictions on your Binance account.

---

## ▶️ Usage

Simply run:

```sh
python main.py
```

---

## 🛠 Notes

- The time format for `launch_time_str` must be `"YYYY-MM-DD HH:MM:SS"` in UTC.
- If you launch the bot after the listing time has passed, it will immediately begin checking for the pair.
- The script uses modern Python asyncio practices.
- Order details are displayed in a readable table format.

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

## 🛑 Disclaimer

Cryptocurrency trading carries significant risks and may result in the loss of capital. Use this bot at your own risk. The author is not responsible for any financial losses caused by the use of this program. Always understand the risks associated with automated trading and API interaction.

---
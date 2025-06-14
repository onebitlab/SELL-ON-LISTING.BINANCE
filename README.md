🚀 Binance Sell on Listing Bot
This Python script automatically places a limit sell order immediately after a new token is listed on Binance, at a configurable price below the market. It's built for speed, precision, and safety during high-volatility listing events.

⚡️ Built using asynchronous programming (async/await) for maximum responsiveness with the Binance API, ensuring graceful handling of operations.

✅ Features

🕒 Synchronizes local time with Binance server time to avoid clock drift, using modern datetime practices to avoid deprecation warnings.

⏰ Starts checking the listing 10 seconds before your specified launch time.

🔄 Continuously checks for trading pair availability via Binance REST API.

💰 Automatically places a limit sell order at a price below market (offset configurable).

📐 Applies Binance's PRICE_FILTER and LOT_SIZE precision to ensure your target price and quantity meet exchange requirements.

🔄 Includes a robust retry mechanism for fetching current prices, making the bot more resilient to temporary network issues.

🔍 If the order isn't filled within a timeout (default: 30 seconds), it is cancelled.

graceful Ctrl-C (KeyboardInterrupt) handling, ensuring all open Binance connections are properly closed even if the script is interrupted.

⚙️ Configuration
First, install dependencies:

pip install -r requirements.txt

Create a config.py file in the root directory with your preferences:

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

⚠️ Important: API Key Permissions
Make sure your Binance API key has "Enable Spot & Margin Trading" permission enabled. If you encounter an Invalid API-key, IP, or permissions for action error, this is usually the cause. Also, verify your API key and secret are exactly correct and check for any IP restrictions on your Binance account.

▶️ Usage
Simply run:

python main.py

🛠 Notes
Time format for launch_time_str must be "YYYY-MM-DD HH:MM:SS" in UTC.

If you launch the bot after the listing time has passed, it will immediately begin checking for the pair.

The script now uses modern Python asyncio practices, resolving previous deprecation warnings.

📄 License
MIT License — free to use, modify, and distribute.
api_key = 'your_binance_api_key'
api_secret = 'your_binance_api_secret'

# Trading configuration
pair = "ALTUSDT"                    # Example: 'SOMETOKENUSDT'
coins_for_sale = "100"              # Amount of tokens to sell
price_offset_percent = "1.0"        # Percent below market price (e.g., 1.0 means 1% below)

# Timing
order_timeout_seconds = 30          # Cancel order after this many seconds if not filled
pair_check_interval_seconds = 0.5   # Interval (in sec) between strade pair availability checks
launch_time_str = "2025-05-29 12:00:00" # Exact time trading is expected to start (UTC)
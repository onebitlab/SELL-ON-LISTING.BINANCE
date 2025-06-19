# config.py

# BINANCE API Credentials
api_key = 'YOUR_BINANCE_API_KEY'        # Your Binance API Key
api_secret = 'YOUR_BINANCE_SECRET_KEY'  # Your Binance Secret Key

# Trading configuration
pair = 'ALT/USDT'                       # Trading pair, e.g.: 'ALT/USDT'
tokens_for_sale = '100'                 # Amount of tokens to sell
price_offset = '1.0'                    # Percentage below market price (e.g., '1.0' means 1% below)

# Timing
launch_time = '2025-05-29 12:00:00'     # Exact trading start time (UTC) in 'YYYY-MM-DD HH:MM:SS' format
pre_launch_pooling = 10                 # Interval (in seconds) before launch_time to start checking for the pair listing
pair_check_interval = 0.5               # Interval (in seconds) between trade pair availability checks
price_check_interval = 1.0              # Interval (in seconds) between price retrieval attempts upon error
order_timeout = 30                      # Cancel order after this many seconds if not filled
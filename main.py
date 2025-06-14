import asyncio
import os
import sys
import signal # Import signal module for Ctrl-C handling
from datetime import datetime, timedelta, timezone # Import timezone
from decimal import Decimal, ROUND_DOWN
import pytz
from binance import AsyncClient
from binance.exceptions import BinanceAPIException, BinanceRequestException
from config import ( # Ensure config.py is accessible and contains all necessary variables
    api_key,
    api_secret,
    pair as cfg_pair,
    coins_for_sale as cfg_coins,
    price_offset_percent as cfg_offset,
    order_timeout_seconds as cfg_timeout,
    pair_check_interval_seconds as cfg_pair_check_interval,
    launch_time_str
)
from colorama import init, Fore, Style
from tabulate import tabulate

# Initialize colorama for colored console output
init(autoreset=True)

# --- GLOBAL SETTINGS (FROM config.py) ---
# Convert config values to required types and formats
pair = cfg_pair.strip().upper() # Trading pair (e.g., "BTCUSDT")
coins_for_sale = Decimal(cfg_coins) # Quantity of coins to sell
price_offset_percent = Decimal(cfg_offset) # Price offset percentage from current price
order_timeout_seconds = int(cfg_timeout) # Order timeout
pair_check_interval = float(cfg_pair_check_interval) # Interval for checking pair listing
# Launch time, converted to UTC with timezone information
launch_time_utc = datetime.strptime(launch_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.UTC)
# --- END GLOBAL SETTINGS ---

# Global variable for the Binance client instance,
# allowing connection closure upon program termination
client_instance = None

# --- LOGGING FUNCTIONS ---
def log_info(message):
    """Prints an informational message."""
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} {message}")

def log_success(message):
    """Prints a success message."""
    print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {message}")

def log_warning(message):
    """Prints a warning message."""
    print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {message}")

def log_error(message):
    """Prints an error message."""
    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {message}")

def print_order_details(order):
    """
    Prints order details in a formatted table.
    Accepts an order information dictionary.
    """
    order_table = [
        ["Symbol", order['symbol']],
        ["Order ID", order['orderId']],
        ["Status", order['status']],
        ["Type", order['type']],
        ["Side", order['side']],
        ["Quantity", order['origQty']],
        ["Price", order['price']],
        ["Filled Qty", order['executedQty']],
        ["Total USDT", order['cummulativeQuoteQty']],
        ["Time in Force", order['timeInForce']],
    ]
    print("-" * 37)
    print(tabulate(order_table, tablefmt="fancy_grid")) # Use fancy_grid for a nice table
    fills = order.get('fills', []) # Get fill details if available
    if fills:
        print("\nFills:")
        fills_table = [
            [f['price'], f['qty'], f['commission'], f['commissionAsset']]
            for f in fills
        ]
        print(tabulate(
            fills_table,
            headers=["Price", "Qty", "Commission", "Asset"],
            tablefmt="github" # Table format for fills
        ))
    print("-" * 37)

# --- ASYNCHRONOUS FUNCTIONS ---
async def wait_until_launch(client):
    """
    Waits until the launch time.
    Periodically checks Binance server time.
    """
    try:
        binance_time = await client.get_server_time()
        # Deprecation fix: Use datetime.fromtimestamp with tz=pytz.UTC or datetime.timezone.utc
        server_now = datetime.fromtimestamp(binance_time["serverTime"] / 1000, tz=pytz.UTC)
        wait_until = launch_time_utc - timedelta(seconds=10)

        if server_now >= wait_until:
            log_info("Launch time already reached or close. Skipping wait.")
            return

        while server_now < wait_until:
            remaining = wait_until - server_now
            # Ensure remaining time is positive to avoid formatting errors
            if remaining.total_seconds() < 0:
                log_info("Launch time already passed while waiting. Proceeding.")
                break

            # Format remaining time
            total_seconds = int(remaining.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Waiting for launch: "
                  f"{str(hours).zfill(2)}:{str(minutes).zfill(2)}:{str(seconds).zfill(2)}", end="\r")
            await asyncio.sleep(1) # Wait 1 second
            binance_time = await client.get_server_time()
            # Deprecation fix: Use datetime.fromtimestamp with tz=pytz.UTC or datetime.timezone.utc
            server_now = datetime.fromtimestamp(binance_time["serverTime"] / 1000, tz=pytz.UTC)

        print() # New line after countdown finishes
        log_info("10 seconds left until launch time. Starting to check listing...")
    except asyncio.CancelledError:
        log_warning("Waiting for launch time was cancelled.")
        raise # Re-raise the exception for proper task cancellation handling
    except Exception as e:
        log_error(f"Error while waiting for launch time: {e}")
        raise # Re-raise the error so it can be caught in main


async def wait_for_pair_listing(client, symbol):
    """
    Waits for the trading pair to be listed on Binance.
    Periodically checks exchange information.
    """
    log_info(f"Waiting for pair {symbol} to be listed (every {pair_check_interval}s)...")
    while True:
        try:
            info = await client.get_exchange_info()
            listed_symbols = [s['symbol'] for s in info['symbols']]
            if symbol in listed_symbols:
                log_success(f"Pair {symbol} found on Binance!")
                return info
            else:
                await asyncio.sleep(pair_check_interval)
        except asyncio.CancelledError:
            log_warning("Waiting for pair listing was cancelled.")
            raise # Re-raise the exception
        except Exception as e:
            log_error(f"Error querying exchange info: {e}. Retrying in {pair_check_interval}s...")
            await asyncio.sleep(pair_check_interval)


async def get_current_price(client, symbol, retries=5, delay=1):
    """
    Retrieves the current price of the trading pair with retries.
    """
    for i in range(retries):
        try:
            ticker = await client.get_symbol_ticker(symbol=symbol)
            return Decimal(ticker['price'])
        except asyncio.CancelledError:
            raise # Re-raise the exception
        except Exception as e:
            log_error(f"Error getting current price (attempt {i+1}/{retries}): {e}")
            if i < retries - 1:
                await asyncio.sleep(delay)
    log_error("Failed to retrieve current price after multiple attempts.")
    return Decimal('0')


async def wait_for_order_fill_or_timeout(client, symbol, order_id, timeout):
    """
    Waits for an order to be filled or for a timeout to occur.
    If timeout is reached, the order is cancelled.
    """
    log_info(f"Waiting for order {order_id} to fill or timeout in {timeout} seconds...")
    start = asyncio.get_event_loop().time() # Start time of waiting
    while True:
        try:
            order = await client.get_order(symbol=symbol, orderId=order_id)
            if order['status'] == 'FILLED':
                log_success(f"Order {order_id} filled successfully.")
                print_order_details(order)
                return
            elif order['status'] in ['CANCELED', 'REJECTED', 'EXPIRED']:
                log_warning(f"Order {order_id} ended with status: {order['status']}")
                return
            elif asyncio.get_event_loop().time() - start > timeout:
                log_info(f"Timeout reached. Cancelling order {order_id}...")
                try:
                    await client.cancel_order(symbol=symbol, orderId=order_id)
                    log_info(f"Order {order_id} cancelled due to timeout.")
                except BinanceAPIException as e:
                    # Code -2011 means the order was not found or already closed
                    if e.code == -2011:
                        log_warning(f"Order {order_id} no longer exists during cancellation attempt.")
                    else:
                        log_error(f"Error cancelling order {order_id}: {e}")
                return
            await asyncio.sleep(0.5) # Check status every 0.5 seconds
        except asyncio.CancelledError:
            log_warning(f"Waiting for order {order_id} fill/timeout was cancelled.")
            # Attempt to cancel the order if the task was cancelled
            try:
                await client.cancel_order(symbol=symbol, orderId=order_id)
                log_info(f"Order {order_id} cancelled due to task cancellation.")
            except Exception as e:
                log_warning(f"Could not cancel order {order_id} on task cancellation: {e}")
            raise # Re-raise the exception
        except Exception as e:
            log_warning(f"Error checking order status for {order_id}: {e}")
            await asyncio.sleep(0.5)


async def get_price_filter_precision(symbol_info):
    """
    Extracts price precision (number of decimal places) from symbol filters.
    """
    for f in symbol_info['filters']:
        if f['filterType'] == 'PRICE_FILTER':
            tick_size = Decimal(f['tickSize'])
            precision = abs(tick_size.normalize().as_tuple().exponent)
            return precision
    return 6 # Return default value if filter not found

async def get_lot_size_precision(symbol_info):
    """
    Extracts quantity precision (lot step size) from symbol filters.
    """
    for f in symbol_info['filters']:
        if f['filterType'] == 'LOT_SIZE':
            step_size = Decimal(f['stepSize'])
            precision = abs(step_size.normalize().as_tuple().exponent)
            return precision
    return 6 # Return default value if filter not found

# --- MAIN PROGRAM LOGIC ---
async def main():
    """
    Main asynchronous function controlling the bot's logic.
    """
    global client_instance # Use global variable for client
    client_instance = await AsyncClient.create(api_key, api_secret)
    try:
        # 1. Wait for launch time
        await wait_until_launch(client_instance)

        # 2. Wait for trading pair listing
        exchange_info = await wait_for_pair_listing(client_instance, pair)

        # 3. Get current price
        current_price = await get_current_price(client_instance, pair)
        if current_price == Decimal('0'):
            log_error("Failed to get initial price. Exiting.")
            return # Exit if price could not be retrieved

        # 4. Calculate target sell price
        offset = current_price * price_offset_percent / Decimal('100')
        target_price = current_price - offset

        quantity = coins_for_sale

        # 5. Apply price and quantity precision based on Binance filters
        symbol_found = False
        for s in exchange_info['symbols']:
            if s['symbol'] == pair:
                # Price precision
                price_precision = await get_price_filter_precision(s)
                target_price = target_price.quantize(Decimal(f'1e-{price_precision}'), rounding=ROUND_DOWN)

                # Quantity precision
                quantity_precision = await get_lot_size_precision(s)
                quantity = quantity.quantize(Decimal(f'1e-{quantity_precision}'), rounding=ROUND_DOWN)
                symbol_found = True
                break
        
        if not symbol_found:
            log_error(f"Symbol information for {pair} not found in exchange_info. Cannot apply filters.")
            return

        log_info(f"Placing limit sell order for {quantity} {pair} at {target_price} USDT (market: {current_price})...")

        # 6. Attempt to place order with retries
        retries = 3
        for attempt in range(1, retries + 1):
            try:
                log_info(f"Placing order (attempt {attempt}/{retries})...")
                order = await client_instance.order_limit_sell(
                    symbol=pair,
                    quantity=float(quantity), # Binance API often requires float
                    price=str(target_price)   # Price must be a string
                )
                log_success("Order placed successfully!")
                # 7. Wait for order fill or timeout
                await wait_for_order_fill_or_timeout(client_instance, pair, order['orderId'], order_timeout_seconds)
                break # Exit retry loop after successful placement
            except BinanceAPIException as e:
                log_error(f"API error when placing order: {e.status_code} {e.code} {e.message}")
                if attempt == retries:
                    log_error("All order placement attempts failed. Exiting.")
                    return
                await asyncio.sleep(0.5) # Small delay before next attempt
            except BinanceRequestException as e:
                log_error(f"Request error when placing order: {e}")
                if attempt == retries:
                    log_error("All order placement attempts failed due to request errors. Exiting.")
                    return
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                log_warning("Order placement was cancelled.")
                raise # Re-raise the exception

    except asyncio.CancelledError:
        log_warning("Main task was cancelled.")
    except Exception as e:
        log_error(f"General error in main function: {e}")
    finally:
        # Guaranteed closure of Binance client connection
        if client_instance:
            log_info("Closing Binance client connection.")
            await client_instance.close_connection()

# --- PROGRAM ENTRY POINT ---
if __name__ == "__main__":
    # KeyboardInterrupt (Ctrl-C) handling for asynchronous programs
    try:
        # The recommended way to run an async main function is with asyncio.run().
        # It handles loop creation, management, and clean shutdown including KeyboardInterrupt.
        asyncio.run(main())

    except KeyboardInterrupt:
        log_warning("Program interrupted by user (Ctrl-C). Shutting down.")
    except Exception as e:
        log_error(f"An unexpected error occurred in the main execution block: {e}")
    finally:
        # Guaranteed connection closure if it was opened but not closed in main()
        # This part still needs to use asyncio.run() because it's in a sync context
        # outside the main asyncio loop that asyncio.run(main()) managed.
        if client_instance: # Removed .is_closed() as it's not a valid attribute
            log_info("Guaranteed closure of Binance connection (in main execution block finally).")
            try:
                # Use asyncio.run to execute an async function in a sync context
                asyncio.run(client_instance.close_connection())
            except Exception as e:
                log_warning(f"Error during guaranteed connection closure: {e}")
        log_info("Program terminated.")

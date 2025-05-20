import asyncio
import json
import aiohttp
import os
import sys
from decimal import Decimal, ROUND_DOWN
from binance import AsyncClient
from binance.exceptions import BinanceAPIException, BinanceRequestException
from config import api_key, api_secret
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

# --- USER INPUT ---
pair = input("Enter trading pair (e.g., ZKUSDT): ").strip().upper()
coins_for_sale = Decimal(input("Enter number of tokens to sell: "))
price_offset_percent = Decimal(input("Enter price offset percentage (e.g., 1.0): "))
order_timeout_seconds = 30  # Cancel order if not filled within this time
# --- END ---

def log_info(message):
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} {message}")

def log_success(message):
    print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {message}")

def log_warning(message):
    print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {message}")

def log_error(message):
    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {message}")

async def wait_for_pair_listing(client, symbol):
    log_info(f"Waiting for listing of pair {symbol} via REST API...")
    while True:
        try:
            info = await client.get_exchange_info()
            listed_symbols = [s['symbol'] for s in info['symbols']]
            if symbol in listed_symbols:
                log_success(f"Pair {symbol} found on Binance!")
                return info  # Return full exchangeInfo for later use
            else:
                await asyncio.sleep(1)
        except Exception as e:
            log_error(f"Error querying /exchangeInfo: {e}, retrying in 1 sec...")
            await asyncio.sleep(1)

async def get_current_price(client, symbol):
    try:
        ticker = await client.get_symbol_ticker(symbol=symbol)
        return Decimal(ticker['price'])
    except Exception as e:
        log_error(f"Error getting current price: {e}")
        return Decimal('0')

async def check_balance(client, symbol):
    base_asset = symbol.replace('USDT', '')
    account = await client.get_account()
    for b in account['balances']:
        if b['asset'] == base_asset:
            return Decimal(b['free'])
    return Decimal('0')

async def wait_for_order_fill_or_timeout(client, symbol, order_id, timeout):
    log_info(f"Waiting for order {order_id} to fill or timeout in {timeout} sec...")
    start = asyncio.get_event_loop().time()
    while True:
        try:
            order = await client.get_order(symbol=symbol, orderId=order_id)
            if order['status'] == 'FILLED':
                log_success(f"Order {order_id} filled! Sale completed.")
                return
            elif order['status'] in ['CANCELED', 'REJECTED', 'EXPIRED']:
                log_warning(f"Order {order_id} ended with status: {order['status']}")
                return
            elif asyncio.get_event_loop().time() - start > timeout:
                log_info(f"Timeout reached. Cancelling order {order_id}...")
                await client.cancel_order(symbol=symbol, orderId=order_id)
                return
            await asyncio.sleep(1)
        except Exception as e:
            log_warning(f"Error checking order status: {e}")
            await asyncio.sleep(1)

async def get_price_filter_precision(symbol_info):
    for f in symbol_info['filters']:
        if f['filterType'] == 'PRICE_FILTER':
            tick_size = Decimal(f['tickSize'])
            precision = abs(tick_size.normalize().as_tuple().exponent)
            return precision
    return 6  # fallback

async def main():
    client = await AsyncClient.create(api_key, api_secret)
    try:
        exchange_info = await wait_for_pair_listing(client, pair)

        current_price_task = get_current_price(client, pair)
        balance_task = check_balance(client, pair)

        current_price, balance = await asyncio.gather(
            current_price_task, balance_task
        )

        if current_price == 0:
            log_warning("Could not retrieve current price. Restarting script...")
            os.execv(sys.executable, [sys.executable] + sys.argv)

        if balance < Decimal('0.00000001'):
            log_warning(f"No available {pair.replace('USDT', '')} for sale. Balance: {balance}")
            return

        offset = (current_price * price_offset_percent / Decimal('100'))
        target_price = current_price - offset

        # Round price to allowed precision from PRICE_FILTER
        for s in exchange_info['symbols']:
            if s['symbol'] == pair:
                price_precision = await get_price_filter_precision(s)
                target_price = target_price.quantize(Decimal(f'1e-{price_precision}'), rounding=ROUND_DOWN)
                break

        quantity = min(balance, coins_for_sale)

        log_info(f"Placing order at {target_price} USDT (current: {current_price})...")

        order = None
        retries = 3
        for attempt in range(1, retries + 1):
            try:
                log_info(f"Attempting to place order {attempt}/{retries}...")
                order = await client.order_limit_sell(
                    symbol=pair,
                    quantity=float(quantity),
                    price=str(target_price)
                )
                log_success(f"Order placed: {order}")
                break
            except BinanceAPIException as e:
                log_error(f"Order placement error: {e.status_code} {e.code} {e.message}")
                if attempt == retries:
                    log_error("All order attempts failed. Exiting.")
                    return
                await asyncio.sleep(1)

        if order:
            await wait_for_order_fill_or_timeout(client, pair, order['orderId'], order_timeout_seconds)

    except BinanceAPIException as e:
        log_error(f"Binance API error: {e.status_code} {e.code} {e.message}")
    except BinanceRequestException as e:
        log_error(f"Binance API request error: {e}")
    except Exception as e:
        log_error(f"General error: {e}")
    finally:
        await client.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
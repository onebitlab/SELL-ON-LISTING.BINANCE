import asyncio
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
import pytz
from binance import AsyncClient
from binance.exceptions import BinanceAPIException, BinanceRequestException
from config import (
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

# Initialize colorama
init(autoreset=True)

# --- CONFIG INPUT ---
pair = cfg_pair.strip().upper()
coins_for_sale = Decimal(cfg_coins)
price_offset_percent = Decimal(cfg_offset)
order_timeout_seconds = int(cfg_timeout)
pair_check_interval = float(cfg_pair_check_interval)
launch_time_utc = datetime.strptime(launch_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.UTC)
# --- END CONFIG ---


def log_info(message):
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} {message}")

def log_success(message):
    print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {message}")

def log_warning(message):
    print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {message}")

def log_error(message):
    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {message}")

def print_order_details(order):
    print("-" * 37)
    print(f"Symbol       : {order['symbol']}")
    print(f"Order ID     : {order['orderId']}")
    print(f"Status       : {order['status']}")
    print(f"Type         : {order['type']}")
    print(f"Side         : {order['side']}")
    print(f"Quantity     : {order['origQty']}")
    print(f"Price        : {order['price']}")
    print(f"Filled Qty   : {order['executedQty']}")
    print(f"Total USDT   : {order['cummulativeQuoteQty']}")
    print(f"Time in Force: {order['timeInForce']}")
    print()
    print("Fills:")
    for fill in order.get('fills', []):
        print(f"  - Price: {fill['price']}, Qty: {fill['qty']}, Commission: {fill['commission']} {fill['commissionAsset']}")
    print("-" * 37)


async def wait_until_launch(client):
    binance_time = await client.get_server_time()
    server_now = datetime.utcfromtimestamp(binance_time["serverTime"] / 1000).replace(tzinfo=pytz.UTC)
    wait_until = launch_time_utc - timedelta(seconds=10)

    if server_now >= wait_until:
        log_info("Launch time already reached or close. Skipping wait.")
        return

    while server_now < wait_until:
        remaining = wait_until - server_now
        h, m, s = str(remaining).split(":")
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Waiting for launch: {h.zfill(2)}:{m}:{s.split('.')[0]}", end="\r")
        await asyncio.sleep(1)
        binance_time = await client.get_server_time()
        server_now = datetime.utcfromtimestamp(binance_time["serverTime"] / 1000).replace(tzinfo=pytz.UTC)

    print()
    log_info("10 seconds left until launch time. Starting to check listing...")


async def wait_for_pair_listing(client, symbol):
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
        except Exception as e:
            log_error(f"Error querying exchange info: {e}. Retrying in {pair_check_interval}s...")
            await asyncio.sleep(pair_check_interval)


async def get_current_price(client, symbol):
    try:
        ticker = await client.get_symbol_ticker(symbol=symbol)
        return Decimal(ticker['price'])
    except Exception as e:
        log_error(f"Error getting current price: {e}")
        return Decimal('0')


async def wait_for_order_fill_or_timeout(client, symbol, order_id, timeout):
    log_info(f"Waiting for order {order_id} to fill or timeout in {timeout} seconds...")
    start = asyncio.get_event_loop().time()
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
                await client.cancel_order(symbol=symbol, orderId=order_id)
                return
            await asyncio.sleep(0.5)
        except Exception as e:
            log_warning(f"Error checking order status: {e}")
            await asyncio.sleep(0.5)


async def get_price_filter_precision(symbol_info):
    for f in symbol_info['filters']:
        if f['filterType'] == 'PRICE_FILTER':
            tick_size = Decimal(f['tickSize'])
            precision = abs(tick_size.normalize().as_tuple().exponent)
            return precision
    return 6


async def main():
    client = await AsyncClient.create(api_key, api_secret)
    try:
        await wait_until_launch(client)
        exchange_info = await wait_for_pair_listing(client, pair)
        current_price = await get_current_price(client, pair)

        if current_price == 0:
            log_warning("Could not retrieve price. Restarting script...")
            os.execv(sys.executable, [sys.executable] + sys.argv)

        offset = current_price * price_offset_percent / Decimal('100')
        target_price = current_price - offset

        for s in exchange_info['symbols']:
            if s['symbol'] == pair:
                price_precision = await get_price_filter_precision(s)
                target_price = target_price.quantize(Decimal(f'1e-{price_precision}'), rounding=ROUND_DOWN)
                break

        quantity = coins_for_sale
        log_info(f"Placing limit sell order at {target_price} USDT (market: {current_price})...")

        retries = 3
        for attempt in range(1, retries + 1):
            try:
                log_info(f"Placing order (attempt {attempt}/{retries})...")
                order = await client.order_limit_sell(
                    symbol=pair,
                    quantity=float(quantity),
                    price=str(target_price)
                )
                log_success("Order placed successfully!")
                await wait_for_order_fill_or_timeout(client, pair, order['orderId'], order_timeout_seconds)
                break
            except BinanceAPIException as e:
                log_error(f"API error: {e.status_code} {e.code} {e.message}")
                if attempt == retries:
                    log_error("All order attempts failed. Exiting.")
                    return
                await asyncio.sleep(0.5)

    except Exception as e:
        log_error(f"General error: {e}")
    finally:
        await client.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
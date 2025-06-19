import asyncio
import os
import sys
import signal
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
import pytz
from binance import AsyncClient
from binance.exceptions import BinanceAPIException, BinanceRequestException
from config import (
    api_key,
    api_secret,
    pair as cfg_pair,
    tokens_for_sale as cfg_tokens,
    price_offset as cfg_offset,
    order_timeout as cfg_timeout,
    pair_check_interval as cfg_pair_check_interval,
    launch_time as cfg_launch_time,
    pre_launch_pooling as cfg_pre_launch_pooling,
    price_check_interval as cfg_price_check_interval
)
from colorama import init, Fore, Style
from tabulate import tabulate

init(autoreset=True)

pair = cfg_pair.replace('/', '').strip().upper()
tokens_for_sale = Decimal(cfg_tokens)
price_offset = Decimal(cfg_offset)
order_timeout = int(cfg_timeout)
pair_check_interval = float(cfg_pair_check_interval)
pre_launch_pooling = int(cfg_pre_launch_pooling)
price_check_interval = float(cfg_price_check_interval)
launch_time_utc = datetime.strptime(cfg_launch_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.UTC)

client_instance = None

def log_info(message):
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} {message}")

def log_success(message):
    print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {message}")

def log_warning(message):
    print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {message}")

def log_error(message):
    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {message}")

def print_order_details(order):
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
    print(tabulate(order_table, tablefmt="fancy_grid"))
    fills = order.get('fills', [])
    if fills:
        print("\nFills:")
        fills_table = [
            [f['price'], f['qty'], f['commission'], f['commissionAsset']]
            for f in fills
        ]
        print(tabulate(
            fills_table,
            headers=["Price", "Qty", "Commission", "Asset"],
            tablefmt="github"
        ))
    print("-" * 37)

async def pre_launch_checks(client: AsyncClient) -> bool:
    """
    Performs pre-launch checks, specifically verifying API key validity.
    Does NOT check balance as new coins might not show up before listing.
    """
    log_info("Performing pre-launch API key checks...")
    try:
        # A lightweight call to verify API key validity without affecting balances or orders
        await client.get_account_status()
        log_success("API keys are valid and have necessary permissions.")
        return True
    except BinanceAPIException as e:
        log_error(f"API error during pre-launch API key check: {e.status_code} {e.code} {e.message}")
        log_error("Please check your API key, secret, and permissions (e.g., 'Enable Spot & Margin Trading').")
        return False
    except BinanceRequestException as e:
        log_error(f"Request error during pre-launch API key check: {e}. Check internet connection or API endpoint.")
        return False
    except Exception as e:
        log_error(f"An unexpected error occurred during pre-launch checks: {e}")
        return False

async def wait_until_launch(client):
    try:
        binance_time = await client.get_server_time()
        server_now = datetime.fromtimestamp(binance_time["serverTime"] / 1000, tz=pytz.UTC)
        wait_until = launch_time_utc - timedelta(seconds=pre_launch_pooling)

        if server_now >= wait_until:
            log_info(f"Launch time already reached or close (within {pre_launch_pooling}s). Skipping wait.")
            return

        while server_now < wait_until:
            remaining = wait_until - server_now
            if remaining.total_seconds() < 0:
                log_info("Launch time already passed while waiting. Proceeding.")
                break

            total_seconds = int(remaining.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Waiting for launch: "
                  f"{str(hours).zfill(2)}:{str(minutes).zfill(2)}:{str(seconds).zfill(2)}", end="\r")
            await asyncio.sleep(1)
            binance_time = await client.get_server_time()
            server_now = datetime.fromtimestamp(binance_time["serverTime"] / 1000, tz=pytz.UTC)

        print()
        log_info(f"{pre_launch_pooling} seconds left until launch time. Starting to check listing...")
    except asyncio.CancelledError:
        log_warning("Waiting for launch time was cancelled.")
        raise
    except Exception as e:
        log_error(f"Error while waiting for launch time: {e}")
        raise


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
        except asyncio.CancelledError:
            log_warning("Waiting for pair listing was cancelled.")
            raise
        except Exception as e:
            log_error(f"Error querying exchange info: {e}. Retrying in {pair_check_interval}s...")
            await asyncio.sleep(pair_check_interval)


async def get_current_price(client, symbol):
    while True:
        try:
            ticker = await client.get_symbol_ticker(symbol=symbol)
            return Decimal(ticker['price'])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log_error(f"Error getting current price: {e}. Retrying in {price_check_interval} seconds...")
            await asyncio.sleep(price_check_interval)


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
                try:
                    await client.cancel_order(symbol=symbol, orderId=order_id)
                    log_info(f"Order {order_id} cancelled due to timeout.")
                except BinanceAPIException as e:
                    if e.code == -2011:
                        log_warning(f"Order {order_id} no longer exists during cancellation attempt.")
                    else:
                        log_error(f"Error cancelling order {order_id}: {e}")
                return
            await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            log_warning(f"Waiting for order {order_id} fill/timeout was cancelled.")
            try:
                await client.cancel_order(symbol=symbol, orderId=order_id)
                log_info(f"Order {order_id} cancelled due to task cancellation.")
            except Exception as e:
                log_warning(f"Could not cancel order {order_id} on task cancellation: {e}")
            raise
        except Exception as e:
            log_warning(f"Error checking order status for {order_id}: {e}")
            await asyncio.sleep(0.5)


async def get_price_filter_precision(symbol_info):
    for f in symbol_info['filters']:
        if f['filterType'] == 'PRICE_FILTER':
            tick_size = Decimal(f['tickSize'])
            precision = abs(tick_size.normalize().as_tuple().exponent)
            return precision
    return 6

async def get_lot_size_precision(symbol_info):
    for f in symbol_info['filters']:
        if f['filterType'] == 'LOT_SIZE':
            step_size = Decimal(f['stepSize'])
            precision = abs(step_size.normalize().as_tuple().exponent)
            return precision
    return 6

async def main():
    global client_instance
    client_instance = await AsyncClient.create(api_key, api_secret)
    try:
        # Perform API key pre-checks
        if not await pre_launch_checks(client_instance):
            log_error("API key pre-checks failed. Exiting.")
            return

        await wait_until_launch(client_instance)

        exchange_info = await wait_for_pair_listing(client_instance, pair)

        current_price = await get_current_price(client_instance, pair)

        offset = current_price * price_offset / Decimal('100')
        target_price = current_price - offset

        quantity = tokens_for_sale

        symbol_found = False
        for s in exchange_info['symbols']:
            if s['symbol'] == pair:
                price_precision = await get_price_filter_precision(s)
                target_price = target_price.quantize(Decimal(f'1e-{price_precision}'), rounding=ROUND_DOWN)

                quantity_precision = await get_lot_size_precision(s)
                quantity = quantity.quantize(Decimal(f'1e-{quantity_precision}'), rounding=ROUND_DOWN)
                symbol_found = True
                break
        
        if not symbol_found:
            log_error(f"Symbol information for {pair} not found in exchange_info. Cannot apply filters.")
            return

        log_info(f"Placing limit sell order for {quantity} {pair} at {target_price} USDT (market: {current_price})...")

        retries = 3
        for attempt in range(1, retries + 1):
            try:
                log_info(f"Placing order (attempt {attempt}/{retries})...")
                order = await client_instance.order_limit_sell(
                    symbol=pair,
                    quantity=float(quantity),
                    price=str(target_price)
                )
                log_success("Order placed successfully!")
                await wait_for_order_fill_or_timeout(client_instance, pair, order['orderId'], order_timeout)
                break
            except BinanceAPIException as e:
                log_error(f"API error when placing order: {e.status_code} {e.code} {e.message}")
                if attempt == retries:
                    log_error("All order placement attempts failed. Exiting.")
                    return
                await asyncio.sleep(0.5)
            except BinanceRequestException as e:
                log_error(f"Request error when placing order: {e}")
                if attempt == retries:
                    log_error("All order placement attempts failed due to request errors. Exiting.")
                    return
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                log_warning("Order placement was cancelled.")
                raise

    except asyncio.CancelledError:
        log_warning("Main task was cancelled.")
    except Exception as e:
        log_error(f"General error in main function: {e}")
    finally:
        if client_instance:
            log_info("Closing Binance client connection.")
            await client_instance.close_connection()

if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        log_warning("Program interrupted by user (Ctrl-C). Shutting down.")
    except Exception as e:
        log_error(f"An unexpected error occurred in the main execution block: {e}")
    finally:
        if client_instance:
            log_info("Guaranteed closure of Binance connection (in main execution block finally).")
            try:
                asyncio.run(client_instance.close_connection())
            except Exception as e:
                log_warning(f"Error during guaranteed connection closure: {e}")
        log_info("Program terminated.")

""" Commands:

itt - Short info about currency. For example: /itt BTC
"""
import requests
from textwrap import dedent
from datetime import datetime, timedelta


from telegram import ParseMode

from django.core.cache import cache

from settings import CRYPTOPANIC_API_TOKEN 
from settings import USDT_COINS, BTC_COINS, CACHE_MIDDLEWARE_SECONDS

from apps.indicator.models import Price, Volume, Sma, Rsi

ALL_COINS = USDT_COINS + list(set(BTC_COINS)-set(USDT_COINS)) # remove dublicates and combine, USDT_COINS first
#ALL_COINS = set(USDT_COINS + BTC_COINS) # it will sort coins alphabetically


## helpers

def percents(new_value, old_value):
    return (100*(new_value - old_value)/old_value)

def diff_symbol(diff): # ↑ increase, ↓ decrease
    if diff > 0:
        d_sym = "↑"
    elif diff < 0:
        d_sym = "↓"
    else:
        d_sym = ""
    return d_sym

def fiat_from_satoshi(satoshis):
    return float(satoshis * float(10**-8))

def format_timestamp(timestamp):
    return timestamp.strftime('%Y-%m-%d %H:%M:%S')

def sentiment_from_cryptopanic(currency):
    # to speedup this plz warmup cache for all currencies or most popular ones
    CRYPTOPANIC_API_URL = "https://cryptopanic.com/api/posts/?auth_token={}&filter=trending&currencies={}".format(
        CRYPTOPANIC_API_TOKEN, currency)
    try:
        data = requests.get(CRYPTOPANIC_API_URL).json()
        last_result = data['results'][0]
        title = last_result['title']
        link = last_result['url']
    except:
        title, link = '', ''
    return (title, link)


def currency_info(currency):
    cache_key = "itt_bot_ci_" + currency
    reply_text = cache.get(cache_key)
    if not reply_text: # no cache for reply_text
        if currency in USDT_COINS:
            counter_currency = Price.USDT
            counter_currency_txt = 'USDT'
        else:
            counter_currency = Price.BTC
            counter_currency_txt = 'BTC'

        # Price
        price_new_object = Price.objects.filter(
            transaction_currency=currency, counter_currency=counter_currency
            ).order_by('-timestamp').first()

        price_24h_old_object = Price.objects.filter(
            transaction_currency=currency, counter_currency=counter_currency,
            timestamp__lte=price_new_object.timestamp - timedelta(minutes=1440)
            ).order_by('-timestamp').first()
        
        percents_price_diff_24h = percents(price_new_object.price, price_24h_old_object.price)

        currency_format = "{:.8f}" if fiat_from_satoshi(price_new_object.price) < 1 else "{:.2f}"

        price_block_text = "*{}*/{} *${} {}*\n24h change {}".format(
            currency, counter_currency_txt, currency_format.format(fiat_from_satoshi(price_new_object.price)), \
            diff_symbol(percents_price_diff_24h), '{:+.2f}%'.format(percents_price_diff_24h))

        # Volume
        volume_object = Volume.objects.filter(
            transaction_currency=currency, counter_currency=counter_currency,
            ).order_by('-timestamp').first()
        volume_block_text = "\nvolume ${:.2f}".format(volume_object.volume)

        # Signals
        try:
            latest_sma_200_object = Sma.objects.filter(
                transaction_currency=currency, counter_currency=counter_currency,
                sma_period=200
                ).order_by('-timestamp').first()
            sma_text = "\n{}: Sma200".format(format_timestamp(latest_sma_200_object.timestamp))
        except:
            sma_text = ''

        try:
            latest_rsi_object = Rsi.objects.filter(
                transaction_currency=currency, counter_currency=counter_currency
                ).exclude(relative_strength='Nan').order_by('-timestamp').first()
            rsi_text = "\n{}: RSI {:.2f}".format(format_timestamp(latest_rsi_object.timestamp), latest_rsi_object.relative_strength)
        except:
            rsi_text = ''
        
        if '' not in (sma_text, rsi_text):
            signals_block_text = '\n\nLatest signals:' + sma_text + rsi_text
        else:
            signals_block_text = ''

        # Sentiments from cryptopanic
        (title, url) = sentiment_from_cryptopanic(currency)
        if '' not in (title, url):
            cryptopanic_sentiment_block_text = "\n\n\"{}\"\n[Read on CryptoPanic]({})".format(title, url)
        else:
            cryptopanic_sentiment_block_text = ""

        reply_text = price_block_text + volume_block_text + signals_block_text + cryptopanic_sentiment_block_text # + "\nSource: Poloniex"

        cache.set(cache_key, reply_text, timeout=CACHE_MIDDLEWARE_SECONDS)  # cache for 60 min

    return reply_text

## user commands
def itt(bot, update, args):
    try:
        currency = args[0].upper()
    except:
        update.message.reply_text("Please add currency abbreviation to command. For example: `/itt BTC`", ParseMode.MARKDOWN)
        return

    if currency in ALL_COINS:
        reply_text = currency_info(currency)
    else:
        reply_text = "Sorry, I know nothing about this currency `{}`.\nPlease use one of this:\n\n{}.".format(args[0].upper(), ", ".join(ALL_COINS))

    update.message.reply_text(reply_text, ParseMode.MARKDOWN, disable_web_page_preview=True)

import json
import logging
import schedule
import time

from django.core.management.base import BaseCommand
from requests import get, RequestException

from apps.channel.models import ExchangeData
from apps.channel.models.exchange_data import POLONIEX
from apps.indicator.models import Price, Volume
from apps.indicator.models.price import get_currency_value_from_string
from apps.indicator.models.price_resampl import get_first_resampled_time

from settings import time_speed  # 1 / 10
from settings import USDT_COINS, BTC_COINS
from settings import PERIODS_LIST, SHORT, MEDIUM, LONG

from taskapp.helpers import _pull_poloniex_data, _compute_and_save_indicators

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Polls data from Poloniex on a regular interval"

    # Currently we use this command for debug only

    def handle(self, *args, **options):
        logger.info("Getting ready to trawl Poloniex...")

        schedule.every().minute.do(_pull_poloniex_data)

        # @Alex
        # run resampling for all periods and calculate indicator values
        '''
        for horizont_period in PERIODS_LIST:
            hours = (horizont_period / 60) / time_speed  # convert to hours
            schedule.every(hours).hours.at("00:00").do(
                _compute_and_save_indicators,
                {'period': horizont_period}
            )
        '''

        for horizont_period in PERIODS_LIST:
            hours = (horizont_period / 60) / time_speed  # convert to hours

            if horizont_period in [SHORT, MEDIUM]:
                schedule.every(hours).hours.at("00:00").do(
                    _compute_and_save_indicators,
                    {'period': horizont_period}
                )

            # if long period start exacly at the beginning of a day
            if horizont_period == LONG:
                schedule.every().day.at("00:00").do(
                    _compute_and_save_indicators,
                    {'period': horizont_period}
                )

        keep_going = True
        while keep_going:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.debug(str(e))
                logger.info("Poloniex Trawl shut down.")
                keep_going = False

## This code was moved to the taskapp.helpers
#
# def _pull_poloniex_data():
#     try:
#         logger.info("pulling Poloniex data...")
#         req = get('https://poloniex.com/public?command=returnTicker')

#         data = req.json()
#         timestamp = time.time()

#         poloniex_data_point = ExchangeData.objects.create(
#             source=POLONIEX,
#             data=json.dumps(data),
#             timestamp=timestamp
#         )
#         logger.info("Saving Poloniex price, volume data...")
#         _save_prices_and_volumes(data, timestamp)


#     except RequestException:
#         return 'Error to collect data from Poloniex'


# def _save_prices_and_volumes(data, timestamp):
#     for currency_pair in data:
#         try:
#             counter_currency_string = currency_pair.split('_')[0]
#             counter_currency = get_currency_value_from_string(counter_currency_string)
#             assert counter_currency >= 0
#             transaction_currency_string = currency_pair.split('_')[1]
#             assert len(transaction_currency_string) > 1 and len(transaction_currency_string) <= 6

#             Price.objects.create(
#                 source=POLONIEX,
#                 transaction_currency=transaction_currency_string,
#                 counter_currency=counter_currency,
#                 price=int(float(data[currency_pair]['last']) * 10 ** 8),
#                 timestamp=timestamp
#             )

#             Volume.objects.create(
#                 source=POLONIEX,
#                 transaction_currency=transaction_currency_string,
#                 counter_currency=counter_currency,
#                 volume=float(data[currency_pair]['baseVolume']),
#                 timestamp=timestamp
#             )
#         except Exception as e:
#             logger.debug(str(e))

#     logger.debug("Saved Poloniex price and volume data")


# def _compute_and_save_indicators(resample_period_par):

#     timestamp = time.time() // (1 * 60) * (1 * 60)   # rounded to a minute
#     resample_period = resample_period_par['period']

#     logger.info(" ################# Resampling with Period: " + str(resample_period) + " #######################")

#     pairs_to_iterate = [(itm,Price.USDT) for itm in USDT_COINS] + [(itm,Price.BTC) for itm in BTC_COINS]

#     for transaction_currency, counter_currency in pairs_to_iterate:
#         logger.info('   ======== '+str(resample_period)+ ': checking COIN: ' + str(transaction_currency) + ' with BASE_COIN: ' + str(counter_currency))
#         _calculate_one_par(timestamp, resample_period, transaction_currency, counter_currency)





# # move a calculation of one coin pair to a separate routine for future parallel execution (requested by @Alexander)
# def _calculate_one_par(timestamp, resample_period, transaction_currency, counter_currency ):
#     from apps.indicator.models.price_resampl import PriceResampl
#     from apps.indicator.models.sma import Sma
#     from apps.indicator.models.rsi import Rsi
#     from apps.indicator.models.events_elementary import EventsElementary
#     from apps.indicator.models.events_logical import EventsLogical

#     # create a dictionary of parameters to improve readability
#     indicator_params_dict = {
#         'timestamp': timestamp,
#         'source': POLONIEX,
#         'transaction_currency': transaction_currency,
#         'counter_currency': counter_currency,
#         'resample_period': resample_period
#     }

#     ################# BACK CALCULATION (need only once when run first time)
#     BACK_REC = 210   # how many records to calculate back in time
#     BACK_TIME = timestamp - BACK_REC * resample_period * 60  # same in sec

#     last_time_computed = get_first_resampled_time(POLONIEX, transaction_currency, counter_currency, resample_period)
#     records_to_compute = int((last_time_computed-BACK_TIME)/(resample_period * 60))

#     if records_to_compute >= 0:
#         logger.info("  ... calculate resampl back in time, needed records: " + str(records_to_compute))
#         for idx in range(1, records_to_compute):
#             time_point_back = last_time_computed - idx * (resample_period * 60)
#             # round down to the closest hour
#             indicator_params_dict['timestamp'] = time_point_back // (60 * 60) * (60 * 60)

#             try:
#                 resample_object = PriceResampl.objects.create(**indicator_params_dict)
#                 status = resample_object.compute()
#                 if status or (idx == records_to_compute-1) : # leave the last empty record
#                     resample_object.save()
#                 else:
#                     resample_object.delete()  # delete record if no price was added
#             except Exception as e:
#                 logger.error(" -> Back RESAMPLE EXCEPTION: " + str(e))

#         logger.debug("... resample back  - DONE.")
#     else:
#         logger.debug("   ... No back calculation needed")

#     # set time back to a current time
#     indicator_params_dict['timestamp'] = timestamp
#     ################# Can be commented after first time run


#     # calculate and save resampling price
#     # todo - prevent adding an empty record if no value was computed (static method below)
#     try:
#         resample_object = PriceResampl.objects.create(**indicator_params_dict)
#         resample_object.compute()
#         resample_object.save()
#     except Exception as e:
#         logger.error(" -> RESAMPLE EXCEPTION: " + str(e))

#     # calculate and save simple indicators
#     indicators_list = [Sma, Rsi]
#     for ind in indicators_list:
#         try:
#             ind.compute_all(ind, **indicator_params_dict)
#         except Exception as e:
#             logger.error(str(ind) + " Indicator Exception: " + str(e))


#     # check for events and save if any
#     events_list = [EventsElementary, EventsLogical]
#     for event in events_list:
#         try:
#             event.check_events(event, **indicator_params_dict)
#         except Exception as e:
#             logger.error("Event Exception: " + str(e))

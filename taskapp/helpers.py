import json
import logging
import time

from requests import get, RequestException

from apps.channel.models import ExchangeData
from apps.indicator.models import Price, Volume
from apps.indicator.models.price import get_currency_value_from_string
from apps.indicator.models.price_resampl import get_first_resampled_time

from apps.indicator.models.price_resampl import PriceResampl
from apps.indicator.models.sma import Sma
from apps.indicator.models.rsi import Rsi
from apps.indicator.models.ann_future_price_classification import AnnPriceClassification
from apps.indicator.models.events_elementary import EventsElementary
from apps.indicator.models.events_logical import EventsLogical

from apps.ai.models.nn_model import get_ann_model_object

from settings import SHORT, MEDIUM, LONG, RUN_ANN
from settings import SOURCE_CHOICES, EXCHANGE_MARKETS



logger = logging.getLogger(__name__)

def get_exchanges():
    "Return list of exchange codes for signal calculations"
    return [code for code, name in SOURCE_CHOICES if name in EXCHANGE_MARKETS]


def get_currency_pairs(source, period_in_seconds):
    """
    Return: [('BTC', 0), ('PINK', 0), ('ETH', 0),....]
    """
    get_from_time = time.time() - period_in_seconds
    price_objects = Price.objects.values('transaction_currency', 'counter_currency').filter(source=source).filter(timestamp__gte=get_from_time).distinct()
    return [(item['transaction_currency'], item['counter_currency']) for item in price_objects]

def get_source_name(source_code):
    "return poloniex for code=0"
    return next((source_text for code, source_text in SOURCE_CHOICES if code==source_code), None)

def _pull_poloniex_data(source):
    logger.info("pulling Poloniex data...")
    req = get('https://poloniex.com/public?command=returnTicker')

    data = req.json()
    timestamp = time.time()

    poloniex_data_point = ExchangeData.objects.create(
        source=source,
        data=json.dumps(data),
        timestamp=timestamp
    )
    logger.info("Saving Poloniex price, volume data...")
    _save_prices_and_volumes(data, timestamp, source)

def _save_prices_and_volumes(data, timestamp, source):
    for currency_pair in data:
        try:
            counter_currency_string = currency_pair.split('_')[0]
            counter_currency = get_currency_value_from_string(counter_currency_string)
            assert counter_currency >= 0
            transaction_currency_string = currency_pair.split('_')[1]
            assert len(transaction_currency_string) > 1 and len(transaction_currency_string) <= 6

            Price.objects.create(
                source=source,
                transaction_currency=transaction_currency_string,
                counter_currency=counter_currency,
                price=int(float(data[currency_pair]['last']) * 10 ** 8),
                timestamp=timestamp
            )

            Volume.objects.create(
                source=source,
                transaction_currency=transaction_currency_string,
                counter_currency=counter_currency,
                volume=float(data[currency_pair]['baseVolume']),
                timestamp=timestamp
            )
        except Exception as e:
            logger.debug(str(e))

    logger.debug("Saved Poloniex price and volume data")

# def get_exchanges():
#     """
#     Return list of exchange codes for signal calculations
#     """
#     return [code for code, name in SOURCE_CHOICES if name in EXCHANGE_MARKETS]





def _compute_and_save_indicators(source, resample_period):

    timestamp = time.time() // (1 * 60) * (1 * 60)   # rounded to a minute

    logger.info("################# Resampling with Period: " + str(resample_period) + ", Source:" + str(source) + " #######################")



    if RUN_ANN:
        # choose the pre-trained ANN model depending on period, here are the same
        period2model = {
            SHORT : 'lstm_model_2_2.h5',
            MEDIUM: 'lstm_model_2_2.h5',
            LONG  : 'lstm_model_2_2.h5'
        }
        # load model from S3 and database
        ann_model_object = get_ann_model_object(period2model[resample_period])

    #TODO: get pairs from def(SOURCE)
    #pairs_to_iterate = [(itm,Price.USDT) for itm in USDT_COINS] + [(itm,Price.BTC) for itm in BTC_COINS]
    pairs_to_iterate = get_currency_pairs(source=source, period_in_seconds=resample_period*60*2)
    #logger.debug("## Pairs to iterate: " + str(pairs_to_iterate))

    for transaction_currency, counter_currency in pairs_to_iterate:
        logger.info('   ======== EXCHANGE: ' + str(source) + '| period: ' + str(resample_period)+ '| checking COIN: ' + str(transaction_currency) + ' with BASE_COIN: ' + str(counter_currency))

        # create a dictionary of parameters to improve readability
        indicator_params_dict = {
            'timestamp': timestamp,
            'source': source,
            'transaction_currency': transaction_currency,
            'counter_currency': counter_currency,
            'resample_period': resample_period
        }


        ################# BACK CALCULATION (need only once when run first time)
        BACK_REC = 5   # how many records to calculate back in time
        BACK_TIME = timestamp - BACK_REC * resample_period * 60  # same in sec

        last_time_computed = get_first_resampled_time(source, transaction_currency, counter_currency, resample_period)
        records_to_compute = int((last_time_computed-BACK_TIME)/(resample_period * 60))

        if records_to_compute >= 0:
            logger.info("  ... calculate resampl back in time, needed records: " + str(records_to_compute))
            for idx in range(1, records_to_compute):
                time_point_back = last_time_computed - idx * (resample_period * 60)
                # round down to the closest hour
                indicator_params_dict['timestamp'] = time_point_back // (60 * 60) * (60 * 60)

                try:
                    resample_object = PriceResampl.objects.create(**indicator_params_dict)
                    status = resample_object.compute()
                    if status or (idx == records_to_compute-1) : # leave the last empty record
                        resample_object.save()
                    else:
                        resample_object.delete()  # delete record if no price was added
                except Exception as e:
                    logger.error(" -> Back RESAMPLE EXCEPTION: " + str(e))

            logger.debug("... resample back  - DONE.")
        else:
            logger.debug("   ... No back calculation needed")

        # set time back to a current time
        indicator_params_dict['timestamp'] = timestamp
        ################# Can be commented after first time run


        # calculate and save resampling price
        # todo - prevent adding an empty record if no value was computed (static method below)
        try:
            resample_object = PriceResampl.objects.create(**indicator_params_dict)
            resample_object.compute()
            resample_object.save()
            logger.debug("  ... Resampled completed,  ELAPSED Time: " + str(time.time() - timestamp))
        except Exception as e:
            logger.error(" -> RESAMPLE EXCEPTION: " + str(e))


        # calculate and save simple indicators
        indicators_list = [Sma, Rsi]
        for ind in indicators_list:
            try:
                ind.compute_all(ind, **indicator_params_dict)
                logger.debug("  ... Regular indicators completed,  ELAPSED Time: " + str(time.time() - timestamp))
            except Exception as e:
                logger.error(str(ind) + " Indicator Exception: " + str(e))


        # calculate ANN indicator(s)
        # TODO: now run only for a short period, since it is not really tuned for other periods
        if (RUN_ANN) and (resample_period==SHORT):
            # TODO: just form X_predicted here and then run prediction outside the loop !
            try:
                if ann_model_object:
                    AnnPriceClassification.compute_all(AnnPriceClassification, ann_model_object, **indicator_params_dict)
                    logger.info("  ... ANN indicators completed,  ELAPSED Time: " + str(time.time() - timestamp))
                else:
                    logger.error(" No ANN model, calculation does not make sence")
            except Exception as e:
                logger.error("ANN Indicator Exception (ANN has not been calculated): " + str(e))



        ##############################
        # check for events and save if any
        events_list = [EventsElementary, EventsLogical]
        for event in events_list:
            try:
                event.check_events(event, **indicator_params_dict)
                logger.debug("  ... Events completed,  ELAPSED Time: " + str(time.time() - timestamp))
            except Exception as e:
                logger.error(" Event Exception: " + str(e))

    if RUN_ANN:
        # clean session to prevent memory leak
        logger.debug("   ... Cleaning Keras session...")
        from keras import backend as K
        K.clear_session()
        # TODO check if I can do a batch Keras prediction for all currencies at once
        # NOTE: you can form an X vector inside this cycle and then run prediction!!!
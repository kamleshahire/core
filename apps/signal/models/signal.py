import copy
import json
import logging

import boto
from boto.sqs.message import Message
from datetime import datetime, timedelta

from django.db.models.signals import post_save, pre_save

from apps.common.behaviors import Timestampable
from apps.indicator.models import Price
from settings import QUEUE_NAME, AWS_OPTIONS, BETA_QUEUE_NAME, TEST_QUEUE_NAME
from django.db import models
from unixtimestampfield.fields import UnixTimeStampField
from apps.channel.models.exchange_data import SOURCE_CHOICES, POLONIEX
from apps.user.models.user import RISK_CHOICES, HORIZON_CHOICES

logger = logging.getLogger(__name__)


(TELEGRAM, WEB) = list(range(2))
UI_CHOICES = (
    (TELEGRAM, 'telegram bot'),
    (WEB, 'web app'),
)


class Signal(Timestampable, models.Model):

    UI = models.SmallIntegerField(choices=UI_CHOICES, null=False, default=TELEGRAM)
    subscribers_only = models.BooleanField(default=True)
    text = models.TextField(default="")

    source = models.SmallIntegerField(choices=SOURCE_CHOICES, null=False, default=POLONIEX)
    transaction_currency = models.CharField(max_length=6, null=False, blank=False)

    signal = models.CharField(max_length=15, null=True)
    trend = models.CharField(max_length=15, null=True)

    risk = models.SmallIntegerField(choices=RISK_CHOICES, null=True)
    horizon = models.SmallIntegerField(choices=HORIZON_CHOICES, null=True)
    strength_value = models.IntegerField(null=True)
    strength_max = models.IntegerField(null=True)

    counter_currency = models.SmallIntegerField(choices=Price.COUNTER_CURRENCY_CHOICES, null=False, default=Price.BTC)
    price = models.BigIntegerField(null=False)
    price_change = models.FloatField(null=True)  # in percents, thatis why Float

    rsi_value = models.FloatField(null=True)

    volume_btc = models.FloatField(null=True)  # BTC volume
    volume_btc_change = models.FloatField(null=True)
    volume_usdt = models.FloatField(null=True)  # USD value
    volume_usdt_change = models.FloatField(null=True)

    timestamp = UnixTimeStampField(null=False)
    sent_at = UnixTimeStampField(use_numeric=True)

    _price_ts = None

    def get_price_ts(self):
        '''
        Caches from DB the min nessesary amount of records
        :return: pd.Series of last ~200 time points
        '''

        # todo: it does not work correctly, there is no currency if we call static method
        if self._price_ts is None:
            back_in_time_records = list(Price.objects.filter(
                source=POLONIEX,
                transaction_currency=self.transaction_currency,
                counter_currency=self.counter_currency,
                timestamp__gte = datetime.now() - timedelta(minutes=(self.period * max([self.sma_high_period, self.ema_high_period])))
            ).values('price'))

            if not back_in_time_records:
                return None

            # convert price into a time Series (pandas)
            self._resampled_price_ts = pd.Series([rec['closing_price'] for rec in back_in_time_records])
            # TALIB: price_ts_nd = np.array([ rec['mean_price_satoshis'] for rec in raw_data])

        return self._resampled_price_ts

    # MODEL PROPERTIES


    # MODEL FUNCTIONS

    def get_price(self):
        if self.price and self.price_change:
            return self.price

        price_object = Price.objects.filter(transaction_currency=self.transaction_currency,
                                            source=self.source,
                                            counter_currency = self.counter_currency,
                                            timestamp__lte=self.timestamp
                                            ).order_by('-timestamp').first()
        if price_object:
            self.price = price_object.price
            self.price_change = price_object.price_change
        return self.price


    def as_dict(self):
        data_dict = copy.deepcopy(self.__dict__)
        if "_state" in data_dict:
            del data_dict["_state"]
        for key, value in data_dict.items():
            data_dict[key] = str(value) # cast all as strings
        data_dict.update({
            "UI": self.get_UI_display(),
            "source": self.get_source_display(),
            "risk": self.get_risk_display(),
            "horizon": self.get_horizon_display(),
            "created_at": str(self.created_at),
            "modified_at": str(self.modified_at),
            "timestamp": str(self.timestamp),
            "sent_at": str(self.sent_at),
        })
        return data_dict

    def _send(self):
        # populate all required values

        try:
            if not all([self.price, self.price_change]):
                self.price = self.get_price()

            if not all([self.volume_btc, self.volume_btc_change,
                        self.volume_usdt, self.volume_usdt_change]):
                pass #todo write and call volume getter function

        except Exception as e:
            logging.debug("Problem finding price, volume: " + str(e))


        # todo: call send in a post_save signal?? is there any reason to delay or schedule a signal?

        message = Message()
        message.set_body(json.dumps(self.as_dict()))

        sqs_connection = boto.sqs.connect_to_region("us-east-1",
                            aws_access_key_id=AWS_OPTIONS['AWS_ACCESS_KEY_ID'],
                            aws_secret_access_key=AWS_OPTIONS['AWS_SECRET_ACCESS_KEY'])

        if QUEUE_NAME:
            logging.debug("emitted to QUEUE_NAME queue :" + QUEUE_NAME)
            production_queue = sqs_connection.get_queue(QUEUE_NAME)
            production_queue.write(message)

        if BETA_QUEUE_NAME:
            logging.debug("emitted to BETA_QUEUE_NAME queue :" + BETA_QUEUE_NAME)
            test_queue = sqs_connection.get_queue(BETA_QUEUE_NAME)
            test_queue.write(message)

        if TEST_QUEUE_NAME:
            logging.debug("emitted to TEST_QUEUE_NAME queue :" + TEST_QUEUE_NAME)
            test_queue = sqs_connection.get_queue(TEST_QUEUE_NAME)
            test_queue.write(message)

        logger.info("EMITTED SIGNAL: " + str(self.as_dict()))
        self.sent_at = datetime.now()  # to prevent emitting the same signal twice
        return

    def print(self):
        logger.info("PRINTING SIGNAL DATA: " + str(self.as_dict()))


from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(pre_save, sender=Signal, dispatch_uid="check_has_price")
def check_has_price(sender, instance, **kwargs):
    price = instance.get_price()
    try:
        assert price #see now we have it :)
    except Exception as e:
        logging.debug(str(e))


@receiver(post_save, sender=Signal, dispatch_uid="send_signal")
def send_signal(sender, instance, **kwargs):
    logging.debug("signal saved, checking if signal has been sent yet")
    if not instance.sent_at:   # to prevent emitting the same signal twice
        try:
            logging.debug("signal not sent yet, sending now...")
            instance._send()
            assert instance.sent_at
            instance.save()
            logging.debug("signal sent and timstamp saved")
        except Exception as e:
            logging.error(str(e))

# todo: Tom's attention -
# at a time of calling this static method (from trawl_poloniex) I need transaction_currency and counter_currency already set
# and I am not happy with sending it as porameters
# How can I set in django a parent class SignalParent so I can create it and fill currencies pror to calling check_ichimoku
# without creating a signal in DB?
# then I can call SignalParent.check_signal and that method will create a DB record if neccesary
# may be any other more elegant ideas?

@staticmethod
def check_ichimoku(transaction_currency, counter_currency):
    logging.debug("    Ichimoky checking started")


    # I need


    # get price information back in time for neccesary steps
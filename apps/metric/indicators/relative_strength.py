import logging
from apps.metric.models.relative_strength import RelativeStrengthAnal
import numpy as np

logger = logging.getLogger(__name__)


def RelativeStrength(period_records):
    '''
    Relative Strength calculation.
    The RSI is calculated a a property, we only save RS
    (RSI is a momentum oscillator that measures the speed and change of price movements.)
    :return:
    '''

    # get Series of last 200 time points
    # period= 15,60,360, this ts is already reflects one of those before we call it

    rs_indicator_object = RelativeStrengthAnal.objects.create()

    price_ts = rs_indicator_object.get_price_ts()

    if price_ts is not None:
        # difference btw start and close of the day, remove the first NA
        delta = price_ts.diff()
        delta = delta[1:]

        up, down = delta.copy(), delta.copy()
        up[up < 0] = 0
        down[down > 0] = 0

        # Calculate the 14 period back EWMA for each up/down trends
        # QUESTION: shall this 14 perid depends on period 15,60, 360?

        roll_up = up.ewm(com = 14, min_periods=3).mean()
        roll_down = np.abs(down.ewm(com = 14, min_periods=3).mean())

        rs_ts = roll_up / roll_down

        rs_indicator_object.relative_strength = float(rs_ts.tail(1))  # get the last element for the last time point
    else:
        logger.debug('Not enough closing prices for RS calculation')


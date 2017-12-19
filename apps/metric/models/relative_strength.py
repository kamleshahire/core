import logging
from datetime import timedelta, datetime

import numpy as np
import pandas as pd
from django.db import models

from apps.metric.models.abstract_indicator import AbstractIndicator
from apps.metric.models.price import Price
from apps.signal.models import Signal
from apps.user.models.user import get_horizon_value_from_string
from settings import HORIZONS_TIME2NAMES  # mapping from bin size to a name short/medium
from settings import PERIODS_LIST
from settings import SHORT, MEDIUM, LONG

from settings import time_speed  # speed of the resampling, 10 for fast debug, 1 for prod

logger = logging.getLogger(__name__)


class RelativeStrengthAnal(AbstractIndicator):
    # source inherited from AbstractIndicator
    # transaction_currency inherited from AbstractIndicator
    # timestamp inherited from AbstractIndicator

    period = models.PositiveSmallIntegerField(null=False, default=PERIODS_LIST[0])  # minutes (eg. 15)

    relative_strength = models.FloatField(null=True) # relative strength
    # RSI = relative strength index, see property


    # MODEL PROPERTIES

    @property
    # rsi = 100 - 100 / (1 + rUp / rDown)
    def relative_strength_index(self): # relative strength index
        if self.relative_strength is not None:
            return 100.0 - (100.0 / (1.0 + self.relative_strength))





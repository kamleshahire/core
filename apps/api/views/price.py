from rest_framework.generics import ListAPIView

from apps.api.serializers import PriceSerializer
from apps.api.permissions import RestAPIPermission
from apps.api.paginations import StandardResultsSetPagination, OneRecordPagination

from apps.api.helpers import filter_queryset_by_timestamp, queryset_for_list_without_resample_period

from apps.indicator.models import Price



class ListPrices(ListAPIView):
    """Return list of prices from Price model. Thise are raw, non resampled prices from exchange tickers.

    /api/v2/prices/

    URL query parameters

    For filtering

        transaction_currency: -- string 'BTC', 'ETH' etc
        counter_currency -- number 0=BTC, 1=ETH, 2=USDT, 3=XMR
        source -- number 0=poloniex, 1=bittrex, 2=binance
        startdate -- from this date (inclusive). Example 2018-02-12T09:09:15
        enddate -- to this date (inclusive)

    For pagination
        cursor - indicator that the client may use to page through the result set
        page_size -- a numeric value indicating the page size

    Examples
        /api/v2/prices/?startdate=2018-01-26T10:24:37&enddate=2018-01-26T10:59:02
        /api/v2/prices/?transaction_currency=ETH&counter_currency=0
    """

    permission_classes = (RestAPIPermission, )
    pagination_class = StandardResultsSetPagination
    serializer_class = PriceSerializer

    filter_fields = ('source', 'transaction_currency', 'counter_currency')

    model = serializer_class.Meta.model
    
    def get_queryset(self):
        queryset = filter_queryset_by_timestamp(self, self.model.objects)
        return queryset


class ListPrice(ListAPIView):
    """Return list of prices from Price model for {transaction_currency} with default counter_currency. 
    Default counter_currency is BTC. For BTC itself, counter_currency is USDT.
    
    /api/v2/prices/{transaction_currency}

    URL query parameters

    For filtering

        counter_currency -- number 0=BTC, 1=ETH, 2=USDT, 3=XMR. Default 0=BTC, for BTC 2=USDT
        source -- number 0=poloniex, 1=bittrex, 2=binance.
        startdate -- show inclusive from date. For example 2018-02-12T09:09:15
        enddate -- until this date inclusive in same format

    For pagination
        cursor - indicator that the client may use to page through the result set
        page_size -- a numeric value indicating the page size

    Examples
        /api/v2/prices/ETH # ETH in BTC
        /api/v2/prices/ETH?counter_currency=2 # ETH in USDT
    """

    permission_classes = (RestAPIPermission, )
    serializer_class = PriceSerializer
    pagination_class = OneRecordPagination

    filter_fields = ('source', 'counter_currency')

    model = serializer_class.Meta.model

    def get_queryset(self):
        queryset = queryset_for_list_without_resample_period(self)
        return queryset

[![Waffle.io - Columns and their card count](https://badge.waffle.io/IntelligentTrading/core.svg?columns=all)](https://waffle.io/IntelligentTrading/core)

# ITT Data-Sources


## API

### Price

Get the current trading price for any token

GET `/price`
PARAMS `transaction_currency = <ticker>`

eg. `/price?transaction_currency=BTC`

JSON RESPONSE

`{
    'source': "Poloniex",
    'transaction_currency': <str, transaction_currency_ticker>,
    'price_satoshis': <int, price_in_satoshis>,
    'price_usdt': <float, price in USD> (only for BTC ticker),
    'price_satoshis_change': <float, 15_min_price_change_ratio>,
    'timestamp': <str, timestamp>,
}`

eg.
`{
   "source": "Poloniex",
   "transaction_currency": "OMG",
   "price_sotoshis": 281123, (equivelent to 0.00218123)
   "price_usdt": null,
   "price_satoshis_change": 0.0242342, (equivelent to 2.4% increase)
   "timestamp": "2017-10-18 04:18:51.269170"
 }`

token ticker is <8 chars should be all caps


### Volume

Get the current trading volume for any token

GET `/volume`
PARAMS `transaction_currency = <token ticker>`

eg. `/volume?transaction_currency=BTC`

token ticker is <8 chars should be all caps

JSON RESPONSE

`{"volume": <float, BTC>, 'timestamp': timestamp}`

eg.
`{"volume": 63.3236288, "timestamp": "2017-10-18 03:41:17.902490"}`

### User

Save user settings

POST `/user`

PARAMS 

| required | key | value |
|---|---|---|
| yes | chat_id | string |
| no | is_subscribed | string ['True', 'False'] |
| no | token | string ['2EF92A', '🐼'] |
| no | is_muted | string ['True', 'False'] |
| no | risk | string ['low', 'medium', 'high'] |
| no | horizon | string ['short', 'medium', 'long'] |

RESPONSE

`200` `{"is_subscribed": false, "is_muted": true, "risk": "medium", "horizon": "long"}`

or `500` `{'error': 'error message'}`

### Users

Get list of chat ids for all the users with a common set of settings

GET `/user`

PARAMS 

/api/users&is_ITT_team=true

`beta_token_valid=true`

`is_ITT_team=true`

`risk=<risk setting>' '['low', 'medium', 'high']`

`horizon=<horizon setting>' '['short', 'medium', 'long']`

eg. `/users?beta_token_valid=true,risk=low&horizon=long` for only beta subscribers with these risk and horizon setttings

eg. `/users?is_ITT_team=true` for only ITT team members

eg. '/users' for all subscribers regardless of risk, horizon settings and 

JSON RESPONSE

`{"chat_ids": ["id1", "id2", ...]}`



## Environment Setup

1. Install Prerequisites
 - python3.5 
 - pip 
 - [virtualenv](https://virtualenv.pypa.io/en/stable/installation/) 
 - [virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/en/latest/install.html)
 - run commands to create virtual env
    ```
    $ mkvirtualenv --python=/usr/local/bin/python3 ITT`
    $ workon ITT
    ```
 
2. Clone and setup Django env
 - clone https://github.com/IntelligentTrading/data-sources.git
 - `$ cd data-sources`
 - `$ pip install -r requirements.txt`

3. Local Env Settings
 - make a copy of `settings/local_settings_template.py` and save as `settings/local_settings.py`
 - add private keys and passwords as needed

3. Connect to Database
 - install PostgreSQL server and create local database
 - run `$ python manage.py migrate` to setup schemas in local database
 - AND/OR
 - connect to read-only Amazon Aurora DB
 - set database connection settings in your `settings/local_settings.py`
 
4. Run Local Server
 - `$ python manage.py runserver`
 - open [http://localhost:8000/](http://localhost:8000/)
 - view logs and debug as needed

5. Run Worker Services
 - `$ python manage.py trawl_poloniex`
 - ...
 
6. Query DB in Shell
 - `$ python manage.py shell`
 
    ```
    > from apps.indicator.models import Price
    > eth_price = Price.objects.filter(currency="ETH").order_by('-timestamp').first()
    > print(eth_price.satoshis)
    ```
 

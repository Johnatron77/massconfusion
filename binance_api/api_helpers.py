import environ

env = environ.Env()
environ.Env.read_env()

BINANCE_KEY = env('BINANCE_KEY')
BINANCE_SECRET = env('BINANCE_SECRET')

symbol='BTCUSDT'

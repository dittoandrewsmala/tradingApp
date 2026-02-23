import config
from logger import Logger
logger = Logger()
class RiskManager:

    def __init__(self):
        self.entry = None
        self.trail = None

    def qty(self):
        risk_amt = config.CAPITAL * config.RISK_PERCENT
        return int(risk_amt / config.STOP_LOSS)

    def new_trade(self, price):
        self.entry = price
        self.trail = price - config.STOP_LOSS

    def should_exit(self, ltp):

        if ltp <= self.trail:
            return True

        if ltp >= self.entry + config.TARGET:
            return True

        if ltp > self.entry:
            new_trail = ltp - config.TRAIL
            if new_trail > self.trail:
                self.trail = new_trail

        return False

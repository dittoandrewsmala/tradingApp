import config

class Logger:

    def __init__(self):
        pass

    def printD(self, value):
        if config.trade_log == "D":
            print(value)
    
    def printR(self, value):
            print(value)
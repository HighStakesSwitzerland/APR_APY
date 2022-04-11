#!/usr/bin/python3

from threading import Thread
from time import sleep
from requests import get
import uvicorn
from fastapi import FastAPI
from re import findall


class GetAprApy(Thread):
    def __init__(self):
        super().__init__()

        self.base_url = "http://localhost:1317"
        self.inflation_url = "/cosmos/mint/v1beta1/inflation"
        self.bonded_token_url = "/cosmos/staking/v1beta1/pool"
        self.supply_url = "/cosmos/bank/v1beta1/supply"
        self.token = 'udaric' #change that to the appropriate token name

        self.apr = 0
        self.apy = 0

        self.app = FastAPI()
        self.app.type = "00"

        @self.app.get("/APR")
        def return_apr():
            return round(self.apr*100, 3)

        @self.app.get("/APY")
        def return_apy():
            return self.apy

    def run(self):

        while True:
            #we need to retrieve the metrics (supply, inflation, and number of bonded tokens) to calculate the APY & APY.

            # My deepest apologies for probably the worst piece of code ever written.
            try:
                supply = get(self.base_url+self.supply_url).json()
                supply = int(findall('\d+', str([i for i in supply['supply'] if self.token in i['denom']][0]))[0])

                inflation = get(self.base_url+self.inflation_url).text
                inflation = float(findall('\d+.\d+', inflation)[0])*100

                bonded_tokens = get(self.base_url+self.bonded_token_url).text
                bonded_tokens = int(findall('(?<="bonded_tokens": ")\d+', bonded_tokens)[0])
                #awful.

                #onto the calculation itself.
                self.apr = self.APR(supply,inflation,bonded_tokens)
                self.apy = self.APY(self.apr)

            except Exception as e:
                print(e)

            sleep(86400) #sleep 24h, yes. Idiotic I know.

    def APR(self,supply,inflation,bonded_tokens):

        return ((0.01*supply*inflation)/bonded_tokens) #we'll need to multiply that by 100 when returning the value

    def APY(self, apr):

        return round((1 + (apr/365))**365 - 1, 3) #with a daily compounding

getAprApy = GetAprApy()
app = getAprApy.app
getAprApy.daemon = True
getAprApy.start()


uvicorn.run(app, host='0.0.0.0', port=5006)
#!/usr/bin/python3
from datetime import datetime
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
        self.params_url = "/cosmos/distribution/v1beta1/params"
        self.blocks_url = "/cosmos/base/tendermint/v1beta1/blocks/"
        self.token = 'udaric' #change that to the appropriate token name
        self.commission = 0.05 # the validator commission, let's say 5%.

        self.apr = 0
        self.apy = 0

        self.app = FastAPI()
        self.app.type = "00"

        @self.app.get("/APR")
        def return_apr():
            return round(self.apr,3) #*100, 3)

        @self.app.get("/APY")
        def return_apy():
            return self.apy

    def run(self):

        while True:
            #we need to retrieve the metrics (supply, inflation, number of bonded tokens and more) to calculate the APR & APY.

            # My deepest apologies for probably the worst piece of code ever written.
            try:
                supply = get(self.base_url+self.supply_url).json()
                supply = int(findall('\d+', str([i for i in supply['supply'] if self.token in i['denom']][0]))[0])

                inflation = get(self.base_url+self.inflation_url).text
                inflation = float(findall('\d+.\d+', inflation)[0])*100

                bonded_tokens = get(self.base_url+self.bonded_token_url).text
                bonded_tokens = int(findall('(?<="bonded_tokens": ")\d+', bonded_tokens)[0])

                tax = get(self.base_url+self.params_url).json()
                tax = float(tax['params']['community_tax'])
                #awful.

                #the theoretical APR
                nominal_apr = self.nominal_APR(supply,inflation,bonded_tokens,tax)
                #theoretical number of blocks/year
                theoretical_provision = self.theoretical_provision(supply,inflation)
                #let's estimate the actual provision
                actual_provision = self.actual_provision()

                #we have enough data to calculate the actual APR.

                #onto the calculation itself.
                self.apr = self.actual_APR(nominal_apr,theoretical_provision,actual_provision)
                self.apy = self.APY(self.apr)

            except Exception as e:
                print(e)

            sleep(86400) #sleep 24h, yes. Idiotic I know.

    def theoretical_provision(self,supply,inflation):
        return int(str(supply * (inflation / 100))[:6])
        # It returns a long float and we need to take only its first 6 digits.
        # So convert to string, extract the first 6 chars, then back to int. Not sure it can be done more elegantly.

    def actual_provision(self):
        #check the average block time over the last 1000 blocks and derive the yearly number of blocks.
        latest_block = get(self.base_url + self.blocks_url + 'latest').json()
        latest_block_height = int(latest_block['block']['header']['height'])
        latest_block_time = datetime.strptime(latest_block['block']['header']['time'][:-4:] + 'Z',
                                              '%Y-%m-%dT%H:%M:%S.%fZ')
        # now, the timestamp of the earlier block (latest-1000)
        previous_block_1000_time = datetime.strptime(
            get(self.base_url + self.blocks_url + str(latest_block_height - 1000)).json()
            ['block']['header']['time'][:-4:] + 'Z', '%Y-%m-%dT%H:%M:%S.%fZ')

        average_block_time = (latest_block_time.timestamp() - previous_block_1000_time.timestamp()) / 1000

        # now, there are 31,536,000 seconds in a year --365 days, not taking into account leap years because come on.
        # this allows to get the exact (although somewhat approximate...) provision.

        return 31_536_000/average_block_time

    def nominal_APR(self,supply,inflation,bonded_tokens,tax):

        return (inflation * (1 - tax)) / (bonded_tokens / supply)

    def actual_APR(self,nominal_apr,theoretical_provision,actual_provision):

        #return (nominal_apr*(actual_provision/theoretical_provision))*(1-self.commission)
        #The above version is not working. Actual and theoretical provisions are significantly different, and affect the result too much.
        #There must be an error in the upstream formula.
        return nominal_apr * (1 - self.commission)

    def APY(self, apr):
        #need to divide the APR by 100 here.
        return round(((1 + (apr/(100*365)))**365 - 1)*100, 3) #with a daily compounding

getAprApy = GetAprApy()
app = getAprApy.app
getAprApy.daemon = True
getAprApy.start()


uvicorn.run(app, host='0.0.0.0', port=5006)
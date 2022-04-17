#!/usr/bin/python3
from datetime import datetime
from threading import Thread
from time import sleep
from requests import get
import uvicorn
from fastapi import FastAPI
from re import findall
from argparse import ArgumentParser
from psutil import process_iter

class GetAprApy(Thread):
    def __init__(self, data, app=None):
        super().__init__()

        try:
            self.VALIDATOR = data[0]
            self.PORT = data[1]
            self.TOKEN = data[2]
            self.COMMISSION = float(data[3])
        except:
            print("\nGarbage was supplied. Please run with for example (with a 5% commission):\n\npython3 apr_apy.py -i desmos 1317 udsm 0.05\n")
            for proc in process_iter():
                if "apr_apy.py" in proc.cmdline():
                    proc.kill()
#            exit(1)

        self.base_url = f"http://localhost:{self.PORT}" #default is 1317 for the node API
        self.inflation_url = "/cosmos/mint/v1beta1/inflation"
        self.bonded_token_url = "/cosmos/staking/v1beta1/pool"
        self.supply_url = "/cosmos/bank/v1beta1/supply"
        self.distribution_params_url = "/cosmos/distribution/v1beta1/params"
        self.mint_params_url = "/cosmos/mint/v1beta1/params"
        self.blocks_url = "/cosmos/base/tendermint/v1beta1/blocks/"
        # self.token = 'udaric' #change that to the appropriate token name
        # self.commission = 0.05 # the validator commission, let's say 5%.

        self.apr = 0
        self.apy = 0

        ###setup FastAPI
        if app is None:
            self.app = FastAPI()
            self.app.type = "00"
        else:
            self.app = app

        @self.app.get(f"/{self.VALIDATOR}")
        def return_apr_apy():
            return {'apr': round(self.apr,3), 'apy': self.apy}


    def run(self):

        while True:
            #we need to retrieve the metrics (supply, inflation, number of bonded tokens and more) to calculate the APR & APY.

            # My deepest apologies for probably the worst piece of code ever written.
            try:
                supply = get(self.base_url+self.supply_url).json()
                supply = int(findall('\d+', str([i for i in supply['supply'] if self.TOKEN in i['denom']][0]))[0])

                inflation = get(self.base_url+self.inflation_url).text
                inflation = float(findall('\d+.\d+', inflation)[0])*100

                bonded_tokens = get(self.base_url+self.bonded_token_url).text
                bonded_tokens = int(findall('(?<="bonded_tokens": ")\d+', bonded_tokens)[0])

                tax = get(self.base_url+self.distribution_params_url).json()
                tax = float(tax['params']['community_tax'])
                #awful.

                #the theoretical APR
                nominal_apr = self.nominal_APR(supply,inflation,bonded_tokens,tax)
                #theoretical number of blocks/year
                theoretical_provision = self.theoretical_provision()
                #let's estimate the actual provision
                actual_provision = self.actual_provision()

                #we have enough data to calculate the actual APR.

                #onto the calculation itself.
                self.apr = self.actual_APR(nominal_apr,theoretical_provision,actual_provision)
                self.apy = self.APY(self.apr)

            except Exception as e:
                print(e)

            sleep(86400) #sleep 24h, yes. Idiotic I know.

    def theoretical_provision(self):
        provision = get(self.base_url+self.mint_params_url).json()
        return int(provision['params']['blocks_per_year'])

    def actual_provision(self):
        #check the average block time over the last 10k blocks and derive the yearly number of blocks.
        latest_block = get(self.base_url + self.blocks_url + 'latest').json()
        latest_block_height = int(latest_block['block']['header']['height'])
        latest_block_time = datetime.strptime(latest_block['block']['header']['time'][:-4:] + 'Z',
                                              '%Y-%m-%dT%H:%M:%S.%fZ')
        # now, the timestamp of the earlier block (latest-1000)
        previous_block_1000_time = datetime.strptime(
            get(self.base_url + self.blocks_url + str(latest_block_height - 10000)).json()
            ['block']['header']['time'][:-4:] + 'Z', '%Y-%m-%dT%H:%M:%S.%fZ')

        average_block_time = (latest_block_time.timestamp() - previous_block_1000_time.timestamp()) / 10000

        # now, there are 31,536,000 seconds in a year --365 days, not taking into account leap years because come on.
        # this allows to get the exact (although somewhat approximate...) provision.

        return 31_536_000/average_block_time

    def nominal_APR(self,supply,inflation,bonded_tokens,tax):

        return (inflation * (1 - tax)) / (bonded_tokens / supply)

    def actual_APR(self,nominal_apr,theoretical_provision,actual_provision):

        # print("actual_APR", nominal_apr*(actual_provision/theoretical_provision)*(1-self.COMMISSION))
        # print("theorical_APR", nominal_apr * (1 - self.COMMISSION))
        #return the adjusted apr based on the actual number of blocks per year.
        return (nominal_apr*(actual_provision/theoretical_provision))*(1-self.COMMISSION)


    def APY(self, apr):
        #need to divide the APR by 100 here.
        return round(((1 + (apr/(100*365)))**365 - 1)*100, 3) #with a daily compounding


parser = ArgumentParser()
parser.add_argument('-i', nargs='+', action='append', help='Usage: python3 apr_apy.py -i validator1 port1 token1 commission1 -i validator2 port2 token2 commission2 etc.')
args = parser.parse_args()

app = None

for i in args.i:
    getAprApy = GetAprApy(i, app)
    getAprApy.daemon = True
    if app is None:
        app = getAprApy.app
    getAprApy.start()


uvicorn.run(app, host='0.0.0.0', port=5006)
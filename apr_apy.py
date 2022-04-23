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
            self.COMMISSION = float(data[2])

            self.base_url = f"http://localhost:{self.PORT}"  # default is 1317 for the node API

            if 'iris' in self.VALIDATOR: #need a specific config
                self.mint_params_url = "/irishub/mint/params"
                self.inflation_url = "/irishub/mint/params"
            else:
                self.inflation_url = "/cosmos/mint/v1beta1/inflation"
                self.mint_params_url = "/cosmos/mint/v1beta1/params"

            self.bonded_token_url = "/cosmos/staking/v1beta1/pool"
            self.supply_url = "/cosmos/bank/v1beta1/supply?pagination.key=" #some chains have multiple pages here
            self.distribution_params_url = "/cosmos/distribution/v1beta1/params"
            self.blocks_url = "/cosmos/base/tendermint/v1beta1/blocks/"

            #let's also retrieve the token name directly from the api
            self.TOKEN = get(self.base_url+self.mint_params_url).json()['params']['mint_denom']

        except:
            print("\nGarbage was supplied. Please run with for example (with a 5% commission):\n\npython3 apr_apy.py -i desmos 1317 0.05\n")
            for proc in process_iter():
                if "apr_apy.py" in proc.cmdline():
                    proc.kill()

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

        #first let's retrieve the token name

        while True:
            #we need to retrieve the metrics (supply, inflation, number of bonded tokens and more) to calculate the APR & APY.

            # My deepest apologies for probably the worst piece of code ever written.
            try:
                key = ''
                supply = 0
                while True:
                    data = get(self.base_url+self.supply_url+key).json()
                    key = data['pagination']['next_key']
                    try:
                        supply = int(findall('\d+', str([i for i in data['supply'] if self.TOKEN in i['denom']][0]))[0])
                        break
                    except:
                        pass
                    if not key:
                        break

                inflation = get(self.base_url+self.inflation_url).text
                inflation = float(findall('\d+.\d+', inflation)[0])*100

                print(inflation)

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

                print(self.apr,self.apy)

            except Exception as e:
                print(e)

            sleep(86400) #sleep 24h, yes. Idiotic I know.

    def theoretical_provision(self):
        try:  # this does not work for Iris for example
            provision = get(self.base_url + self.mint_params_url).json()
            return int(provision['params']['blocks_per_year'])
        except:
            return 6311520  # seems to be the default for most chains.

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
parser.add_argument('-i', nargs='+', action='append', help='Usage: python3 apr_apy.py -i validator1 port1 commission1 -i validator2 port2 commission2 etc.')
args = parser.parse_args()
print(args)
app = None

for i in args.i:
    getAprApy = GetAprApy(i, app)
    getAprApy.daemon = True
    if app is None:
        app = getAprApy.app
    getAprApy.start()


uvicorn.run(app, host='0.0.0.0', port=5006)
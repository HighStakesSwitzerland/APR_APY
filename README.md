# APR_APY

Retrieve the APR and APY (for daily compounding) for a Cosmos-based blockchain through an API (default is port 5006)

The node API server must be enabled on the node (port 1317 by default).

Usage: <code>python3 apr_apy -i validator1 port1 commission1 -i validator2 port2 commission2 etc.<code>

The program serves an API at localhost:5006/{validator_name}. Values are updated every 24h.

The calculated APR takes into account the actual number of blocks per year (estimated based on the average time of the latest 10k blocks).
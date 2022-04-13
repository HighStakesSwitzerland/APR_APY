# APR_APY

Retrieve the APR and APY (for daily compounding) for a Cosmos-based blockchain through an API (default is port 5006)

The token name must be updated (default is 'udaric'), and the API server must be enabled on the node (port 1317)

At this time it does not take into account the number of blocks per year, which seems to affect the APR. Will implement that later.


<b>UPDATE</b>
 
- Modified the algorithm for taking into account the community tax (however, on Big Dipper it seems to not be the case. If set manually to 0 in the code,<br>
the APR matches exactly the one that is displayed. But with the tax that is retrieved (0.2 /20%), it's, well, 20% lower).
- Same applies with the validator commission: to match the displayed value it should be set to 0.
- Tried to apply the calculation to get the ratio between the expected annual provision vs the actual provision (in terms of number of blocks per year), <br>
but either the math is wrong, or the actual block number is too far away from the expected one and it makes the APR drop.
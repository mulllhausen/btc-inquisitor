#!/usr/bin/env python2.7

# this script is intended to replace bitcoin-cli's getrawtransaction with the 1
# flag set, since getrawtransaction misses some elements such as the txin funds

import os, sys

# when executing this script directly include the parent dir in the path
if (
	(__name__ == "__main__") and
	(__package__ is None)
):
	os.sys.path.append(
		os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	)
import btc_grunt, json

if len(sys.argv) < 2:
	raise ValueError(
		"\n\nUsage: ./get_tx.py <the tx hash in hex>\n"
		"eg: ./get_tx.py 514c46f0b61714092f15c8dfcb576c9f79b3f959989b98de3944b1"
		"9d98832b58\n\n"
	)
txhash_hex = sys.argv[1]

btc_grunt.connect_to_rpc()
tx_bin = btc_grunt.get_transaction(txhash_hex, "bytes")

# don't set to 0 or we will not get the previous tx out data
tx_num = 1 
# set the block height arbitrarily - it is not used in the transaction
block_height = 1
explain_errors = False
tx_dict = btc_grunt.human_readable_tx(tx_bin, tx_num, block_height)
print os.linesep.join(l.rstrip() for l in json.dumps(
	tx_dict, sort_keys = True, indent = 4
).splitlines())

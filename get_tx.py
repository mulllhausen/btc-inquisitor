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

# note that this bitcoin-rpc dict is in a different format to the btc_grunt tx
# dicts
tx_rpc_dict = btc_grunt.get_transaction(txhash_hex, "json")

# the blockhash that the tx appears in
blockhash = tx_rpc_dict["blockhash"]

block_rpc_dict = btc_grunt.get_block(blockhash, "json")
block_height = block_rpc_dict["height"]
tx_num = block_rpc_dict["tx"].index(txhash_hex)
tx_bin = btc_grunt.hex2bin(tx_rpc_dict["hex"])
tx_dict = btc_grunt.human_readable_tx(tx_bin, tx_num, block_height)
explain_errors = False
print "\nblock height: %d\nblock hash: %s\ntx num: %d\ntx: %s" % (
	block_height, blockhash, tx_num,
	os.linesep.join(l.rstrip() for l in json.dumps(
		tx_dict, sort_keys = True, indent = 4
	).splitlines())
)

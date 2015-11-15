#!/usr/bin/env python2.7

# this script is intended to replace bitcoin-cli's getrawtransaction with the 1
# flag set, since getrawtransaction misses some elements such as the txin funds

import os, sys, btc_grunt, json

if len(sys.argv) < 2:
	raise ValueError(
		"\n\nUsage: ./get_tx.py <the tx hash in hex>\n"
		"eg: ./get_tx.py 514c46f0b61714092f15c8dfcb576c9f79b3f959989b98de3944b1"
		"9d98832b58\n\n"
	)
txhash_hex = sys.argv[1]

if len(txhash_hex) != 64:
	raise ValueError(
		"\n\ninput tx hash should be 64 hex characters. %s is %d characters\n\n"
		% (txhash_hex, len(txhash_hex))
	)
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
print "\nblock height: %d\n" \
"block hash: %s\n" \
"tx num: %d\n" \
"tx: %s" % (
	block_height, blockhash, tx_num,
	os.linesep.join(l.rstrip() for l in json.dumps(
		tx_dict, sort_keys = True, indent = 4
	).splitlines())
)

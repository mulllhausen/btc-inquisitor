#!/usr/bin/env python2.7
"""
this script is intended to replace bitcoin-cli's getrawtransaction with the 1
flag set, since getrawtransaction misses some elements such as the txin funds.
it also returns data about where the transaction is within the blockchain.
"""
import sys, btc_grunt, json

if len(sys.argv) < 2:
	raise ValueError(
		"\n\nUsage: ./get_tx.py <the tx hash in hex>\n"
		"eg: ./get_tx.py 514c46f0b61714092f15c8dfcb576c9f79b3f959989b98de3944b1"
		"9d98832b58\n\n"
	)
txhash_hex = sys.argv[1]
is_valid_hash = btc_grunt.valid_hash(txhash_hex, explain = True)
if is_valid_hash is not True:
	raise ValueError("\n\ninvalid input tx hash. %s\n\n" % is_valid_hash)

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
"tx: %s" \
% (block_height, blockhash, tx_num, btc_grunt.pretty_json(tx_dict))

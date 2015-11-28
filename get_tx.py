#!/usr/bin/env python2.7
"""
this script is intended to replace bitcoin-cli's getrawtransaction with the 1
flag set, since getrawtransaction misses some elements such as the txin funds.
it also returns data about where the transaction is within the blockchain.
"""
import sys, btc_grunt, json

if len(sys.argv) < 2:
	raise ValueError(
		"\n\nUsage: ./get_tx.py <the tx hash in hex | blockheight-txnum>\n"
		"eg: ./get_tx.py 514c46f0b61714092f15c8dfcb576c9f79b3f959989b98de3944b1"
		"9d98832b58\n"
		"or ./get_tx.py 257727-130\n\n"
	)
# what is the format of the input argument
input_arg_format = ""
if "-" in sys.argv[1]:
	input_arg_format = "blockheight-txnum"
	try:
		(block_height, tx_num) = sys.argv[1].split("-")
	except Exception as e:
		raise ValueError(
			"\n\ninvalid input blockheight-txnum format. %s\n\n."
			% e.message
		)
	try:
		block_height = int(block_height)
	except:
		# exception will be raised if non-base-10 characters exist in string
		raise ValueError(
			"\n\ninvalid input block height %s. it is not an integer.\n\n"
			% block_height
		)
	try:
		tx_num = int(tx_num)
	except:
		raise ValueError(
			"\n\ninvalid input tx number %s. it is not an integer.\n\n"
			% tx_num
		)
else:
	input_arg_format = "txhash"
	txhash_hex = sys.argv[1]
	is_valid_hash = btc_grunt.valid_hash(txhash_hex, explain = True)
	if is_valid_hash is not True:
		raise ValueError("\n\ninvalid input tx hash. %s\n\n." % is_valid_hash)

btc_grunt.connect_to_rpc()

if input_arg_format == "blockheight-txnum":
	# the program always requires the txhash, regardless of input format
	block_rpc_dict = btc_grunt.get_block(block_height, "json")
	block_hash = block_rpc_dict["hash"]
	try:
		txhash_hex = block_rpc_dict["tx"][tx_num]
	except IndexError:
		raise IndexError(
			"\n\ntx number %d does not exist in block %d\n\n"
			% (tx_num, block_height)
		)

# note that this bitcoin-rpc dict is in a different format to the btc_grunt tx
# dicts
tx_rpc_dict = btc_grunt.get_transaction(txhash_hex, "json")

if input_arg_format == "txhash":
	# the blockhash that the tx appears in
	block_hash = tx_rpc_dict["blockhash"]

	block_rpc_dict = btc_grunt.get_block(block_hash, "json")
	block_height = block_rpc_dict["height"]
	tx_num = block_rpc_dict["tx"].index(txhash_hex)

tx_bin = btc_grunt.hex2bin(tx_rpc_dict["hex"])
tx_dict = btc_grunt.human_readable_tx(tx_bin, tx_num, block_height)
print "\nblock height: %d\n" \
"block hash: %s\n" \
"tx num: %d\n" \
"tx: %s" \
% (block_height, block_hash, tx_num, btc_grunt.pretty_json(tx_dict))

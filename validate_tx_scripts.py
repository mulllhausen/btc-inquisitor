#!/usr/bin/env python2.7

import os, sys, btc_grunt, json

if len(sys.argv) < 2:
	raise ValueError(
		"\n\nUsage: ./validate_tx_scripts.py <the tx hash in hex>\n"
		"eg: ./validate_tx_scripts.py 514c46f0b61714092f15c8dfcb576c9f79b3f9599"
		"89b98de3944b19d98832b58\n\n"
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
tx_bin = btc_grunt.hex2bin(tx_rpc_dict["hex"])
blockhash = tx_rpc_dict["blockhash"]
block_rpc_dict = btc_grunt.get_block(blockhash, "json")
block_height = block_rpc_dict["height"]
tx_num = block_rpc_dict["tx"].index(txhash_hex)
if tx_num == 0:
	# no scripts to verify for a coinbase tx
	exit()
(tx, _) = btc_grunt.tx_bin2dict(
	tx_bin, 0, btc_grunt.all_tx_info, tx_num, block_height
)
blocktime = tx_rpc_dict["blocktime"]
block_version = tx_rpc_dict["version"]
bugs_and_all = True

# the previous tx number is not relevant since it is only used for txin data,
# and we only care about txout data from the previous tx
fake_prev_tx_num = 0

# the prev block height is not relevant since it is only used to calculate the
# mining reward
fake_prev_block_height = 0

# loop through all txins
for on_txin_num in range(len(tx_rpc_dict["vin"])):
	prev_txhash_hex = tx_rpc_dict["vin"][on_txin_num]["txid"]
	prev_tx_rpc_dict = btc_grunt.get_transaction(prev_txhash_hex, "json")
	prev_tx_bin = btc_grunt.hex2bin(prev_tx_rpc_dict["hex"])
	(prev_tx, _) = btc_grunt.tx_bin2dict(
		prev_tx_bin, 0, ["tx_hash", "txout_script_list", "txout_script_format"],
		fake_prev_tx_num, fake_prev_block_height
	)
	res = btc_grunt.verify_script(
		blocktime, tx, on_txin_num, prev_tx, block_version, bugs_and_all,
		explain = True
	)
	if res["status"] is not True:
		del res["pubkeys"]
		del res["signatures"]
		del res["sig_pubkey_statuses"]
		print "\ntxin %d validation fail:\n%s" % (
			on_txin_num, os.linesep.join(l.rstrip() for l in json.dumps(
				res, sort_keys = True, indent = 4
			).splitlines())
		)

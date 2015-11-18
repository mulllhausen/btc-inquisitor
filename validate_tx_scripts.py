#!/usr/bin/env python2.7

import os, sys, btc_grunt, json

if len(sys.argv) < 2:
	raise ValueError(
		"\n\nUsage: ./validate_tx_scripts.py <the tx hash in hex> <verbose>\n"
		"eg: ./validate_tx_scripts.py 514c46f0b61714092f15c8dfcb576c9f79b3f9599"
		"89b98de3944b19d98832b58 1\n\n"
	)
txhash_hex = sys.argv[1]

if len(txhash_hex) != 64:
	raise ValueError(
		"\n\ninput tx hash should be 64 hex characters. %s is %d characters\n\n"
		% (txhash_hex, len(txhash_hex))
	)
always_display_results = True if (len(sys.argv) > 2) else False

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
	if (
		always_display_results or
		(res["status"] is not True)
	):
		res["pubkeys"] = [btc_grunt.bin2hex(p) for p in res["pubkeys"]]
		res["signatures"] = [btc_grunt.bin2hex(s) for s in res["signatures"]]
		sig_pubkey_statuses_hex = {} # init
		for (bin_sig, pubkey_dict) in res["sig_pubkey_statuses"].items():
			hex_sig = btc_grunt.bin2hex(bin_sig)
			sig_pubkey_statuses_hex[hex_sig] = {} # init
			for (bin_pubkey, status) in pubkey_dict.items():
				hex_pubkey = btc_grunt.bin2hex(bin_pubkey)
				sig_pubkey_statuses_hex[hex_sig][hex_pubkey] = status

		del res["sig_pubkey_statuses"]
		res["sig_pubkey_statuses"] = sig_pubkey_statuses_hex

		print "\ntxin %d validation %s:\n%s\n" % (
			on_txin_num, "fail" if (res["status"] is not True) else "pass",
			os.linesep.join(l.rstrip() for l in json.dumps(
				res, sort_keys = True, indent = 4
			).splitlines())
		)

#!/usr/bin/env python2.7
"""
validate all txin scripts in the supplied txhash against their previous txout
scripts
"""
import sys, btc_grunt, json

if len(sys.argv) < 2:
	raise ValueError(
		"\n\nUsage: ./validate_tx_scripts.py <the tx hash in hex |"
		" blockheight-txnum> <verbose>\n"
		"eg: ./validate_tx_scripts.py 514c46f0b61714092f15c8dfcb576c9f79b3f9599"
		"89b98de3944b19d98832b58 1\n\n"
		"or ./validate_tx_scripts.py 257727-130 yes\n\n"
	)
# what is the format of the first input argument
input_arg1_format = ""
if "-" in sys.argv[1]:
	input_arg1_format = "blockheight-txnum"
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
	input_arg1_format = "txhash"
	txhash_hex = sys.argv[1]
	is_valid_hash = btc_grunt.valid_hash(txhash_hex, explain = True)
	if is_valid_hash is not True:
		raise ValueError("\n\ninvalid input tx hash. %s\n\n." % is_valid_hash)

btc_grunt.connect_to_rpc()

always_display_results = (
	(len(sys.argv) > 2) and (
		(
			isinstance(sys.argv[2], (int, long)) and
			(int(sys.argv[2]) > 0)
		) or (
			isinstance(sys.argv[2], basestring) and
			sys.argv[2].lower() not in ["false", "null", "no", "off"]
		)
	)
)

btc_grunt.connect_to_rpc()

if input_arg1_format == "blockheight-txnum":
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

if input_arg1_format == "txhash":
	# the blockhash that the tx appears in
	block_hash = tx_rpc_dict["blockhash"]

	block_rpc_dict = btc_grunt.get_block(block_hash, "json")
	block_height = block_rpc_dict["height"]
	tx_num = block_rpc_dict["tx"].index(txhash_hex)

tx_bin = btc_grunt.hex2bin(tx_rpc_dict["hex"])

if always_display_results:
	print "\n" \
	"txhash: %s\n" \
	"tx number: %d\n" \
	"block: %d" \
	% (txhash_hex, tx_num, block_height)

if tx_num == 0:
	if always_display_results:
		print "this is a coinbase tx - no scripts to verify"
	exit()

# get the current tx as a dict (btc_grunt.all_tx_info includes all previous tx
# info that this tx spends)
(tx, _) = btc_grunt.tx_bin2dict(
	tx_bin, 0, btc_grunt.all_tx_info, tx_num, block_height, ["rpc"]
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

	# "prev_tx" data is stored using the previous block hash and previous tx
	# number in that block because it used to be possible to have the same
	# txhash in many different blocks. but since the hash is the same, the data
	# is also the same, so any will do. pop the first one for convenience.
	prev_tx0 = tx["input"][on_txin_num]["prev_txs"].values()[0]

	res = btc_grunt.verify_script(
		blocktime, tx, on_txin_num, prev_tx0, block_version, bugs_and_all,
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
			btc_grunt.pretty_json(res)
		)
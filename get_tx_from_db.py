#!/usr/bin/env python2.7
"""
this script is very similar to ./get_tx.py. the purpose of this apparent
duplication is that this script does not require bitcoin-cli to function - it
just requires a database populated with the bitcoin blockchain as per schema.sql
"""
import sys
import btc_grunt
import mysql_grunt
import queries

if len(sys.argv) < 2:
	raise ValueError(
		"\n\nUsage: ./get_tx_from_db.py <the tx hash in hex | "
        "blockheight-txnum>\n"
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

# get the block data
if input_arg_format == "blockheight-txnum":
    data = (block_height, tx_num)
elif input_arg_format == "txhash":
    data = tx_hash_hex

block_data = mysql_grunt.quick_fetch(queries.block(input_arg_format, data))[0]

# get all the tx data in a single query
# todo - break into 2 seperate queries for speed?

tx_data = mysql_grunt.quick_fetch(queries.get_tx(block_data["tx_hash_hex"]))

tx_dict = {
    "change": block_data["tx_change"],
    "funds_balance_validation_status": block_data["tx_funds_balance_validation_status"],
    "hash": block_data["tx_hash_hex"],
    "lock_time": block_data["tx_lock_time"],
    "lock_time_validation_status": block_data["tx_lock_time_validation_status"],
    "num_inputs": block_data["num_txins"],
    "num_outputs": block_data["num_txouts"],
    "size": block_data["tx_size"],
    "version": block_data["tx_version"],
    "input": {},
    "output": {}
}
count_txins = 0
count_txouts = 0

for (i, row) in enumerate(tx_data):
    if (row["type"] == "txin"):
        count_txins += 1
        tx_dict["input"][i] = {
            "checksig_validation_status": row["txin_checksig_validation_status"],
            "funds": row["txin_funds"],
            "hash": row["prev_txout_hash_hex"],
            "hash_validation_status": row["txin_hash_validation_status"],
            "index": row["prev_txout_num"],
            "index_validation_status": row["txin_index_validation_status"],
            "mature_coinbase_spend_validation_status": \
            row["txin_mature_coinbase_spend_validation_status"],
            "parsed_script": btc_grunt.script_list2human_str(
                btc_grunt.script_bin2list(
                    btc_grunt.hex2bin(row["txin_script_hex"])
                )
            ),
            "prev_txout": {
                "parsed_script": btc_grunt.script_list2human_str(
                    btc_grunt.script_bin2list(
                        btc_grunt.hex2bin(row["prev_txout_script_hex"])
                    )
                ),
                "script": row["prev_txout_script_hex"],
                "script_format": row["prev_txout_script_format"],
                "script_length": len(row["prev_txout_script_hex"]) / 2,
                "standard_script_address": row["prev_txout_address"],
                "standard_script_alternate_address": \
                row["prev_txout_alternate_address"]
            },
            "script": row["txin_script_hex"],
            "script_format": row["txin_script_format"],
            "script_length": len(row["txin_script_hex"]) / 2,
            "sequence_num": row["txin_sequence_num"],
            "single_spend_validation_status": \
            row["txin_single_spend_validation_status"],
            "spend_from_non_orphan_validation_status": \
            row["txin_spend_from_non_orphan_validation_status"]
        }
    if (row["type"] == "txout"):
        count_txouts += 1
        tx_dict["output"][i] = {
            "funds": row["txout_funds"],
            "parsed_script": btc_grunt.script_list2human_str(
                btc_grunt.script_bin2list(
                    btc_grunt.hex2bin(row["txout_script_hex"])
                )
            ),
            "script": row["txout_script_hex"],
            "script_format": row["txout_script_format"],
            "script_length": len(row["txout_script_hex"]) / 2,
            "standard_script_address": row["txout_address"],
            "standard_script_alternate_address": row["txout_alternate_address"],
            "standard_script_address_checksum_validation_status": \
            row["standard_script_address_checksum_validation_status"],
            "standard_script_pubkey": row["txout_pubkey_hex"]
        }

tx_dict["txins_exist_validation_status"] = (count_txins == block_data["num_txins"])
tx_dict["txouts_exist_validation_status"] = (count_txouts == block_data["num_txouts"])

print "\nblock height: %d\n" \
"block hash: %s\n" \
"tx num: %d\n" \
"tx: %s" \
% (
    block_data["block_height"], block_data["block_hash_hex"],
    block_data["tx_num"], btc_grunt.pretty_json(tx_dict)
)

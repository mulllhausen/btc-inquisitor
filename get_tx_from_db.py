#!/usr/bin/env python2.7
"""
this script is very similar to ./get_tx.py. the purpose of this apparent
duplication is that this script does not require bitcoin-cli to function - it
just requires a database populated with the bitcoin blockchain as per schema.sql
"""
import sys
import btc_grunt
import get_tx
import queries

def validate_script_usage():
    if len(sys.argv) < 2:
        raise ValueError(
            "\n\nUsage: ./get_tx_from_db.py <the tx hash in hex | "
            "blockheight-txnum>\n"
            "eg: ./get_tx_from_db.py 514c46f0b61714092f15c8dfcb576c9f79b3f95998"
            "9b98de3944b19d98832b58\n"
            "or ./get_tx_from_db.py 257727-130\n\n"
        )

def get_data_from_db(input_arg_format, data, in_hex = True):

    block_data = queries.get_tx_header(input_arg_format, data)

    block_data["block_hash"] = btc_grunt.bin2hex(block_data["block_hash"]) if \
    in_hex else block_data["block_hash"]

    tx_hash_hex = btc_grunt.bin2hex(block_data["tx_hash"])
    block_data["tx_hash"] = tx_hash_hex if in_hex else block_data["tx_hash"]

    # get all the tx data in a single query
    # todo - break into 2 seperate queries for speed?
    tx_data = queries.get_txins_and_txouts(tx_hash_hex)

    tx_dict = {
        "change": block_data["tx_change"],
        "funds_balance_validation_status": \
        block_data["tx_funds_balance_validation_status"],

        "hash": block_data["tx_hash"],
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
            prev_txout = {
                "hash": btc_grunt.bin2hex(row["prev_txout_hash"]) if in_hex \
                else row["prev_txout_hash"],
            }
            if block_data["tx_num"] > 0:
                prev_txout["output"] = {
                    row["prev_txout_num"]: {
                        "parsed_script": btc_grunt.script_list2human_str(
                            btc_grunt.script_bin2list(row["prev_txout_script"])
                        ),
                        "script": btc_grunt.bin2hex(row["prev_txout_script"]) \
                        if in_hex else row["prev_txout_script"],

                        "script_format": row["prev_txout_script_format"],
                        "script_length": len(row["prev_txout_script"]),
                        "standard_script_address": row["prev_txout_address"],
                        "standard_script_alternate_address": \
                        row["prev_txout_alternate_address"]
                    }
                }

            if not in_hex:
                prev_txout["output"][row["prev_txout_num"]]["script_list"] = \
                btc_grunt.script_bin2list(row["prev_txout_script"])

            tx_dict["input"][row["txin_num"]] = {
                "checksig_validation_status": \
                row["txin_checksig_validation_status"],

                "funds": row["txin_funds"],

                "hash": btc_grunt.bin2hex(row["prev_txout_hash"]) if in_hex \
                else row["prev_txout_hash"],

                "hash_validation_status": row["txin_hash_validation_status"],
                "index": row["prev_txout_num"],
                "index_validation_status": row["txin_index_validation_status"],

                "mature_coinbase_spend_validation_status": \
                row["txin_mature_coinbase_spend_validation_status"],

                "parsed_script": btc_grunt.script_list2human_str(
                    btc_grunt.script_bin2list(row["txin_script"])
                ),
                "prev_txs": {0: prev_txout},
                "script": btc_grunt.bin2hex(row["txin_script"]) if in_hex else \
                row["txin_script"],

                "script_format": row["txin_script_format"],
                "script_length": len(row["txin_script"]),

                "sequence_num": row["txin_sequence_num"],
                "single_spend_validation_status": \

                row["txin_single_spend_validation_status"],
                "spend_from_non_orphan_validation_status": \

                row["txin_spend_from_non_orphan_validation_status"]
            }
            if not in_hex:
                tx_dict["input"][row["txin_num"]]["script_list"] = \
                btc_grunt.script_bin2list(row["txin_script"])

        if (row["type"] == "txout"):
            count_txouts += 1
            tx_dict["output"][row["txout_num"]] = {
                "funds": row["txout_funds"],
                "parsed_script": btc_grunt.script_list2human_str(
                    btc_grunt.script_bin2list(row["txout_script"])
                ),
                "script": btc_grunt.bin2hex(row["txout_script"]) if in_hex \
                else row["txout_script"],

                "script_format": row["txout_script_format"],
                "script_length": len(row["txout_script"]),
                "standard_script_address": row["txout_address"],

                "standard_script_alternate_address": \
                row["txout_alternate_address"],

                "standard_script_address_checksum_validation_status": \
                row["standard_script_address_checksum_validation_status"],

                "standard_script_pubkey": \
                btc_grunt.bin2hex(row["txout_pubkey"]) if in_hex else \
                row["txout_pubkey"]
            }

    tx_dict["txins_exist_validation_status"] = \
    (count_txins == block_data["num_txins"])

    tx_dict["txouts_exist_validation_status"] = \
    (count_txouts == block_data["num_txouts"])

    return (tx_dict, block_data)

if __name__ == '__main__':

    validate_script_usage()
    (input_arg_format, data) = get_tx.get_stdin_params()
    in_hex = True
    (tx_dict, block_data) = get_data_from_db(input_arg_format, data, in_hex)

    print "\nblock height: %d\n" \
    "block hash: %s\n" \
    "tx num: %d\n" \
    "tx: %s" \
    % (
        block_data["block_height"], block_data["block_hash"],
        block_data["tx_num"], btc_grunt.pretty_json(tx_dict)
    )

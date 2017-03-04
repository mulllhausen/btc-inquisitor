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

def process_tx_header_from_db(tx_db_data, human_readable = True):
    tx_dict = {
        "block_height": tx_db_data["block_height"],

        "block_hash": btc_grunt.bin2hex(tx_db_data["block_hash"]) if \
        human_readable else tx_db_data["block_hash"],

        "hash": btc_grunt.hex2bin(tx_db_data["tx_hash_hex"]),
        "change": tx_db_data["tx_change"],

        "funds_balance_validation_status": \
        btc_grunt.bin2bool(tx_db_data["tx_funds_balance_validation_status"]),

        "lock_time": tx_db_data["tx_lock_time"],

        "lock_time_validation_status": \
        btc_grunt.bin2bool(tx_db_data["tx_lock_time_validation_status"]),

        "num_inputs": tx_db_data["num_txins"],
        "num_outputs": tx_db_data["num_txouts"],
        "size": tx_db_data["tx_size"],
        "version": tx_db_data["tx_version"],
        "tx_num": tx_db_data["tx_num"],
        "input": {},
        "output": {}
    }
    if human_readable:
        tx_dict = btc_grunt.human_readable_tx(tx_dict, 0, 0, 0, 0, None)

    return tx_dict

def process_tx_body_from_db(tx_dict, human_readable = True):

    if (btc_grunt.valid_hex_hash(tx_dict["hash"])):
        tx_hash_hex = tx_dict["hash"]
    else:
        tx_hash_hex = btc_grunt.bin2hex(tx_dict["hash"])

    txin_txout_data = queries.get_txins_and_txouts(tx_hash_hex)
    count_txins = 0
    count_txouts = 0

    for (i, row) in enumerate(txin_txout_data):
        if (row["type"] == "txin"):
            count_txins += 1
            prev_txout = {}
            if tx_dict["tx_num"] > 0:
                prev_txout_script = btc_grunt.hex2bin(
                    row["prev_txout_script_hex"]
                )
                prev_txout0 = {
                    "script": prev_txout_script,
                    "script_format": row["prev_txout_script_format"],
                    "script_length": len(prev_txout_script),
                    "standard_script_pubkey": row["prev_txout_pubkey"],
                    "standard_script_address": row["prev_txout_address"],
                    "standard_script_alternate_address": \
                    row["prev_txout_alternate_address"]
                }
                prev_txout0["script_list"] = btc_grunt.script_bin2list(
                    prev_txout_script
                )
                if human_readable:
                    prev_txout0["parsed_script"] = \
                    btc_grunt.script_list2human_str(prev_txout0["script_list"])

                prev_txout["output"] = { row["prev_txout_num"]: prev_txout0 }

            txin_script = btc_grunt.hex2bin(row["txin_script_hex"])
            txin = {
                "checksig_validation_status": \
                btc_grunt.bin2bool(row["txin_checksig_validation_status"]),

                "funds": row["txin_funds"],
                "hash": btc_grunt.hex2bin(row["prev_txout_hash_hex"]),
                "hash_validation_status": btc_grunt.bin2bool(
                    row["txin_hash_validation_status"]
                ),
                "index": row["prev_txout_num"],
                "index_validation_status": btc_grunt.bin2bool(
                    row["txin_index_validation_status"]
                ),
                "mature_coinbase_spend_validation_status": \
                btc_grunt.bin2bool(
                    row["txin_mature_coinbase_spend_validation_status"]
                ),
                "script": txin_script,
                "script_format": row["txin_script_format"],
                "script_length": len(txin_script),
                "sequence_num": row["txin_sequence_num"],

                "single_spend_validation_status": \
                btc_grunt.bin2bool(row["txin_single_spend_validation_status"]),

                "spend_from_non_orphan_validation_status": \
                btc_grunt.bin2bool(
                    row["txin_spend_from_non_orphan_validation_status"]
                )
            }
            if tx_dict["tx_num"] > 0:
                txin["prev_txs"] = { 0: prev_txout }

            txin["script_list"] = btc_grunt.script_bin2list(txin_script)
            if human_readable:
                txin["parsed_script"] = \
                btc_grunt.script_list2human_str(txin["script_list"])

            tx_dict["input"][row["txin_num"]] = txin

        if (row["type"] == "txout"):
            count_txouts += 1
            txout_script = btc_grunt.hex2bin(row["txout_script_hex"])
            txout = {
                "funds": row["txout_funds"],
                "script": txout_script,
                "script_format": row["txout_script_format"],
                "script_length": len(txout_script),
                "standard_script_address": row["txout_address"],

                "standard_script_alternate_address": \
                row["txout_alternate_address"],

                "standard_script_address_checksum_validation_status": \
                btc_grunt.bin2bool(
                    row["standard_script_address_checksum_validation_status"]
                )
            }
            if row["txout_pubkey_hex"] is None:
                txout["standard_script_pubkey"] = None
            else:
                txout["standard_script_pubkey"] = \
                btc_grunt.hex2bin(row["txout_pubkey_hex"])

            txout["script_list"] = btc_grunt.script_bin2list(txout_script)
            if human_readable:
                txout["parsed_script"] = \
                btc_grunt.script_list2human_str(txout["script_list"])

            tx_dict["output"][row["txout_num"]] = txout

    tx_dict["txins_exist_validation_status"] = \
    (count_txins == tx_dict["num_inputs"])

    tx_dict["txouts_exist_validation_status"] = \
    (count_txouts == tx_dict["num_outputs"])

    if human_readable:
        tx_dict = btc_grunt.human_readable_tx(tx_dict, 0, 0, 0, 0, None)

    return tx_dict

if __name__ == '__main__':

    validate_script_usage()
    (input_arg_format, data) = get_tx.get_stdin_params()
    tx_db_data = queries.get_tx_header(input_arg_format, data)
    tx_dict = process_tx_header_from_db(tx_db_data, human_readable = False)
    tx_dict = process_tx_body_from_db(tx_dict, human_readable = True)

    block_height = tx_dict["block_height"]
    del tx_dict["block_height"]

    block_hash = btc_grunt.bin2hex(tx_dict["block_hash"])
    del tx_dict["block_hash"]

    tx_num = tx_dict["tx_num"]
    del tx_dict["tx_num"]

    print "\nblock height: %d\n" \
    "block hash: %s\n" \
    "tx num: %d\n" \
    "tx: %s" \
    % (block_height, block_hash, tx_num, btc_grunt.pretty_json(tx_dict))

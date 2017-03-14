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

def process_tx_header_from_db(tx_db_data, required_info, human_readable = True):
    tx_dict = {} # init
    if "block_height" in required_info:
        tx_dict["block_height"] = tx_db_data["block_height"]

    if "tx_change" in required_info:
        tx_dict["change"] = tx_db_data["tx_change"]

    if "tx_funds_balance_validation_status" in required_info:
        tx_dict["funds_balance_validation_status"] = \
        btc_grunt.bin2bool(tx_db_data["tx_funds_balance_validation_status"])

    if "tx_lock_time" in required_info:
        tx_dict["lock_time"] = tx_db_data["tx_lock_time"]

    if "tx_lock_time_validation_status" in required_info:
        tx_dict["lock_time_validation_status"] = \
        btc_grunt.bin2bool(tx_db_data["tx_lock_time_validation_status"])

    if "num_txins" in required_info:
        tx_dict["num_inputs"] = tx_db_data["num_txins"]

    if "num_txouts" in required_info:
        tx_dict["num_outputs"] = tx_db_data["num_txouts"]

    if "tx_size" in required_info:
        tx_dict["size"] = tx_db_data["tx_size"]

    if "tx_version" in required_info:
        tx_dict["version"] = tx_db_data["tx_version"]

    if "tx_num" in required_info:
        tx_dict["tx_num"] = tx_db_data["tx_num"]

    if any(x in btc_grunt.all_txin_info for x in required_info):
        tx_dict["input"] = {}

    if any(x in btc_grunt.all_txout_info for x in required_info):
        tx_dict["output"] = {}
 
    if human_readable:
        if "tx_hash" in required_info:
            tx_dict["hash"] = tx_db_data["tx_hash_hex"]

        if "block_hash" in required_info:
            tx_dict["block_hash"] = tx_db_data["block_hash_hex"]
    else:
        if "tx_hash" in required_info:
            tx_dict["hash"] = btc_grunt.hex2bin(tx_db_data["tx_hash_hex"])

        if "block_hash" in required_info:
            tx_dict["block_hash"] = btc_grunt.hex2bin(
                tx_db_data["block_hash_hex"]
            )

    if human_readable:
        tx_dict = btc_grunt.human_readable_tx(tx_dict, 0, 0, 0, 0, None)

    return tx_dict

def process_tx_body_from_db(
    tx_db_data, required_info, tx_num, human_readable = True
):
    tx_dict = {}
    count_txins = 0
    count_txouts = 0

    for (i, row) in enumerate(tx_db_data):
        txin = {}
        if (row["type"] == "txin"):
            count_txins += 1

            txin_script = btc_grunt.hex2bin(row["txin_script_hex"])
            if "txin_checksig_validation_status" in required_info:
                txin["checksig_validation_status"] = \
                btc_grunt.bin2bool(row["txin_checksig_validation_status"])

            if "txin_funds" in required_info:
                txin["funds"] = row["txin_funds"]

            if "txin_hash" in required_info:
                txin["hash"] = btc_grunt.hex2bin(row["prev_txout_hash_hex"])

            if "txin_hash_validation_status" in required_info:
                txin["hash_validation_status"] = btc_grunt.bin2bool(
                    row["txin_hash_validation_status"]
                )

            if "txin_index" in required_info:
                txin["index"] = row["prev_txout_num"]

            if "txin_index_validation_status" in required_info:
                txin["index_validation_status"] = btc_grunt.bin2bool(
                    row["txin_index_validation_status"]
                )

            if "txin_mature_coinbase_spend_validation_status" in required_info:
                txin["mature_coinbase_spend_validation_status"] = \
                btc_grunt.bin2bool(
                    row["txin_mature_coinbase_spend_validation_status"]
                )

            if "txin_script" in required_info:
                txin["script"] = txin_script

            if "txin_script_format" in required_info:
                txin["script_format"] = row["txin_script_format"]

            if "txin_script_length" in required_info:
                txin["script_length"] = len(txin_script)

            if "txin_sequence_num" in required_info:
                txin["sequence_num"] = row["txin_sequence_num"]

            if "txin_single_spend_validation_status" in required_info:
                txin["single_spend_validation_status"] = \
                btc_grunt.bin2bool(row["txin_single_spend_validation_status"])

            if "txin_spend_from_non_orphan_validation_status" in required_info:
                txin["spend_from_non_orphan_validation_status"] = \
                btc_grunt.bin2bool(
                    row["txin_spend_from_non_orphan_validation_status"]
                )
            if tx_num > 0:
                txin["prev_txs"] = {
                    0: {
                        "output": {
                            row["prev_txout_num"]: get_prev_txout(
                                tx_db_data, required_info, tx_num
                            )
                        }
                    }
                }

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

    def get_prev_txout(tx_db_data, required_info, tx_num):
        prev_txout0 = {}
        if (
            ("prev_txout_script" in required_info) or
            ("prev_txout_script_format" in required_info) or
            ("prev_txout_script_length" in required_info) or
        ):
            prev_txout_script = btc_grunt.hex2bin(
                row["prev_txout_script_hex"]
            )

        if "prev_txout_script" in required_info:
            prev_txout0["script"] = prev_txout_script

        if "prev_txout_script_format" in required_info:
            prev_txout0["script_format"] = row["prev_txout_script_format"]

        if "prev_txout_script_length" in required_info:
            prev_txout0["script_length"] = len(prev_txout_script)

        if "prev_txout_standard_script_pubkey" in required_info:
            prev_txout0["standard_script_pubkey"] = row["prev_txout_pubkey"]

        if "prev_txout_standard_script_address" in required_info:
            prev_txout0["standard_script_address"] = row["prev_txout_address"]

        if "prev_txout_standard_script_alternate_address" in required_info:
            prev_txout0["standard_script_alternate_address"] = \
            row["prev_txout_alternate_address"]

        if "prev_txout_script_list" in required_info:
            prev_txout0["script_list"] = btc_grunt.script_bin2list(
                prev_txout_script
            )
        if human_readable and ("parsed_script" in required_info):
            prev_txout0["parsed_script"] = \
            btc_grunt.script_list2human_str(prev_txout0["script_list"])

        return prev_txout0

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

#!/usr/bin/env python2.7
"""
this script is very similar to ./get_block.py. the purpose of this apparent
duplication is that this script does not require bitcoin-cli to function - it
just requires a database populated with the bitcoin blockchain as per schema.sql
"""
import os
import sys
import btc_grunt
import get_block
import get_tx_from_db
import queries
import lang_grunt
import copy

data_formats = ["hex", "full-json", "header-json"]

def stdin_params2where(block_id):
    if (btc_grunt.valid_hex_hash(block_id)):
        where = {"block_hash": block_id}
    else:
        where = {"block_height": {"start": block_id, "end": block_id}}
    return where

def process_block_from_db(
    block_db_data, required_info, human_readable = True
):
    # required_info_ gets modified, required_info remains unchanged
    required_info_ = copy.deepcopy(required_info)
    if (
        (("target" in required_info_) or ("difficulty" in required_info_)) and
        ("bits" not in required_info_)
    ):
        required_info_.append("bits")

    block_dict = {} # init
    if "block_height" in required_info:
        block_dict["block_height"] =  block_db_data[0]["block_height"]

    if "block_hash" in required_info:
        block_hash_hex = block_db_data[0]["block_hash_hex"]
        if human_readable:
            block_dict["block_hash"] = block_hash_hex
        else:
            block_dict["block_hash"] = btc_grunt.hex2bin(block_hash_hex)

    if "prev_block_hash" in required_info:
        if human_readable:
            block_dict["prev_block_hash"] = \
            block_db_data[0]["prev_block_hash_hex"]
        else:
            block_dict["prev_block_hash"] = btc_grunt.hex2bin(
                block_db_data[0]["prev_block_hash_hex"]
            )

    if (
        ("bits" in required_info) or
        ("target" in required_info) or
        ("difficulty" in required_info)
    ):
        bits = btc_grunt.hex2bin(block_db_data[0]["bits_hex"])

        if "bits" in required_info:
            if human_readable:
                block_dict["bits"] = block_db_data[0]["bits_hex"]
            else:
                block_dict["bits"] = bits

        if "target" in required_info:
            block_dict["target"] = btc_grunt.int2hex(
                btc_grunt.bits2target_int(bits)
            )

        if "difficulty" in required_info:
            block_dict["difficulty"] = btc_grunt.bits2difficulty(bits)

    if "timestamp" in required_info:
        block_dict["timestamp"] = block_db_data[0]["block_time"]

    if "merkle_root" in required_info:
        if human_readable:
            block_dict["merkle_root"] = block_db_data[0]["merkle_root_hex"]
        else:
            block_dict["merkle_root"] = btc_grunt.hex2bin(
                block_db_data[0]["merkle_root_hex"]
            )

    if "nonce" in required_info:
        block_dict["nonce"] = block_db_data[0]["nonce"]

    if "orphan_status" in required_info:
        block_dict["orphan_status"] = btc_grunt.bin2bool(
            block_db_data[0]["block_orphan_status"]
        )

    if "bits_validation_status" in required_info:
        block_dict["bits_validation_status"] = btc_grunt.bin2bool(
            block_db_data[0]["bits_validation_status"]
        )

    if "difficulty_validation_status" in required_info:
        block_dict["difficulty_validation_status"] = btc_grunt.bin2bool(
            block_db_data[0]["difficulty_validation_status"]
        )

    if "block_hash_validation_status" in required_info:
        block_dict["block_hash_validation_status"] = btc_grunt.bin2bool(
            block_db_data[0]["block_hash_validation_status"]
        )

    if "merkle_root_validation_status" in required_info:
        block_dict["merkle_root_validation_status"] = btc_grunt.bin2bool(
            block_db_data[0]["merkle_root_validation_status"]
        )

    if "block_hash_validation_status" in required_info:
        block_dict["block_hash_validation_status"] = btc_grunt.bin2bool(
            block_db_data[0]["block_hash_validation_status"]
        )

    if "block_size" in required_info:
        block_dict["block_size"] = block_db_data[0]["block_size"],

    if "block_size_validation_status" in required_info:
        block_dict["block_size_validation_status"] = btc_grunt.bin2bool(
            block_db_data[0]["block_size_validation_status"]
        )

    if "version" in required_info:
        block_dict["version"] = block_db_data[0]["block_version"],

    required_info_ = list(
        set(required_info_) - \
        set(btc_grunt.all_block_header_and_validation_info)
    )

    if not len(required_info_):
        return block_dict

    block_dict["tx"] = {}

    if "num_txs" in required_info:
        block_dict["num_txs"] = block_db_data[0]["num_txs"]

    # next get the transactions
    for tx_row in block_db_data:
        tx_num = tx_row["tx_num"]
        # todo - extract rows for each tx from block_db_data and pass to process_tx_from_db
        tx_dict = get_tx_from_db.process_tx_from_db(
            block_db_data[tx_num], required_info, human_readable
        )
        tx_dict["timestamp"] = block_db_data[0]["block_time"]
        del tx_dict["block_hash"]
        del tx_dict["block_height"]
        del tx_dict["tx_num"]
        block_dict["tx"][tx_num] = tx_dict

    return block_dict

if __name__ == '__main__':

    get_block.validate_script_usage(
        get_block.get_usage_str(os.path.basename(__file__), data_formats)
    )
    required_info = btc_grunt.all_block_and_validation_info

    (block_id, data_format) = get_block.get_stdin_params()
    where = stdin_params2where(block_id)
    block_db_data = queries.get_blockchain_data(where, required_info)
    block_dict = process_block_from_db(
        block_db_data, required_info, human_readable = True
    )
    if input_arg_format == "hex":
        print block_dict
    else:
        print btc_grunt.pretty_json(block_dict, multiline = True)

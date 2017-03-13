#!/usr/bin/env python2.7
"""
this script is very similar to ./get_block.py. the purpose of this apparent
duplication is that this script does not require bitcoin-cli to function - it
just requires a database populated with the bitcoin blockchain as per schema.sql
"""
import sys
import btc_grunt
import get_block
import get_tx_from_db
import queries
import lang_grunt
import copy

data_types = ["hex", "full-json", "header-json"]
def validate_script_usage():
    if (
        (len(sys.argv) < 3) or
        (sys.argv[2] not in data_types)
    ):
        raise ValueError(
            "\n\nUsage: ./get_block_from_db.py <the block hash in hex | "
            "blockheight> <data type>\n"
            "where <data format> can be %s\n"
            "eg: ./get_block_from_db.py 000000000019d6689c085ae165831e934ff763a"
            "e46a2a6c172b3f1b60a8ce26f hex\n"
            "or ./get_block_from_db.py 257727 full-json\n\n"
            % lang_grunt.list2human_str(data_types, "or")
        )

def convert_stdin_params_to_where(block_id):
    if (btc_grunt.valid_hex_hash(block_id)):
        where = {"block_hash": block_id}
    else:
        where = {"block_height": {"start": block_id, "end": block_id}}
    return where

def process_block_header_from_db(
    where, data_format, required_info, human_readable = True
):
    # required_info_ gets modified, required_info remains unchanged
    required_info_ = copy.deepcopy(required_info)
    if (
        (("target" in required_info_) or ("difficulty" in required_info_)) and
        ("bits" not in required_info_)
    ):
        required_info_.append("bits")

    block_data_rows = queries.get_blockchain_data(where, required_info_)
 
    block_dict = {} # init

    if "block_height" in required_info:
        block_dict["block_height"] =  block_data_rows[0]["block_height"]

    if "block_hash" in required_info:
        block_hash_hex = block_data_rows[0]["block_hash_hex"]
        if human_readable:
            block_dict["block_hash"] = block_hash_hex
        else:
            block_dict["block_hash"] = btc_grunt.hex2bin(block_hash_hex)

    if "prev_block_hash" in required_info:
        if human_readable:
            block_dict["prev_block_hash"] = \
            block_data_rows[0]["prev_block_hash_hex"]
        else:
            block_dict["prev_block_hash"] = btc_grunt.hex2bin(
                block_data_rows[0]["prev_block_hash_hex"]
            )

    if (
        ("bits" in required_info)
        ("target" in required_info) or
        ("difficulty" in required_info) or
    ):
        bits = btc_grunt.hex2bin(block_data_rows[0]["bits_hex"])

        if "bits" in required_info:
            if human_readable:
                block_dict["bits"] = block_data_rows[0]["bits_hex"]
            else:
                block_dict["bits"] = bits

        if "target" in required_info:
            block_dict["target"] = btc_grunt.int2hex(
                btc_grunt.bits2target_int(bits)
            )

        if "difficulty" in required_info:
            block_dict["difficulty"] = btc_grunt.bits2difficulty(bits)

    if "timestamp" in required_info:
        block_dict["timestamp"] = block_data_rows[0]["block_time"]

    if "merkle_root" in required_info:
        if human_readable:
            block_dict["merkle_root"] = block_data_rows[0]["merkle_root_hex"]
        else:
            block_dict["merkle_root"] = btc_grunt.hex2bin(
                block_data_rows[0]["merkle_root_hex"]
            )

    if "nonce" in required_info:
        block_dict["nonce"] = block_data_rows[0]["nonce"]

    if "orphan_status" in required_info:
        block_dict["orphan_status"] = btc_grunt.bin2bool(
            block_data_rows[0]["block_orphan_status"]
        )

    if "bits_validation_status" in required_info:
        block_dict["bits_validation_status"] = btc_grunt.bin2bool(
            block_data_rows[0]["bits_validation_status"]
        )

    if "difficulty_validation_status" in required_info:
        block_dict["difficulty_validation_status"] = btc_grunt.bin2bool(
            block_data_rows[0]["difficulty_validation_status"]
        )

    if "block_hash_validation_status" in required_info:
        block_dict["block_hash_validation_status"] = btc_grunt.bin2bool(
            block_data_rows[0]["block_hash_validation_status"]
        )

    if "merkle_root_validation_status" in required_info:
        block_dict["merkle_root_validation_status"] = btc_grunt.bin2bool(
            block_data_rows[0]["merkle_root_validation_status"]
        )

    if "block_hash_validation_status" in required_info:
        block_dict["block_hash_validation_status"] = btc_grunt.bin2bool(
            block_data_rows[0]["block_hash_validation_status"]
        )

    if "block_size" in required_info:
        block_dict["block_size"] = block_data_rows[0]["block_size"],

    if "block_size_validation_status" in required_info:
        block_dict["block_size_validation_status"] = btc_grunt.bin2bool(
            block_data_rows[0]["block_size_validation_status"]
        )

    if "version" in required_info:
        block_dict["version"] = block_data_rows[0]["block_version"],

    required_info_ = list(
        set(required_info_) - \
        set(btc_grunt.all_block_header_and_validation_info)
    )

    if not len(required_info_):
        return block_dict

    block_dict["tx"] = {}

    if "num_txs" in required_info:
        block_dict["num_txs"] = block_data_rows[0]["num_txs"]

    # next get the transactions
    for tx_row in block_data_rows:
        tx_num = tx_row["tx_num"]
        tx_dict = get_tx_from_db.process_tx_header_from_db(
            block_data_rows[tx_num], required_info, human_readable = False
        )
        tx_dict = get_tx_from_db.process_tx_body_from_db(
            tx_dict, required_info, human_readable
        )
        tx_dict["timestamp"] = block_data_rows[0]["block_time"]
        del tx_dict["block_hash"]
        del tx_dict["block_height"]
        del tx_dict["tx_num"]
        block_dict["tx"][tx_num] = tx_dict

    return block_dict

if __name__ == '__main__':

    validate_script_usage()
    (block_id, data_format) = get_block.get_stdin_params()
    where = convert_stdin_params_to_where(block_id)
    block_data = process_block_header_from_db(
        where, data_format, btc_grunt.all_block_and_validation_info
    )
    if input_arg_format == "hex":
        print block_data
    else:
        print btc_grunt.pretty_json(block_data, multiline = True)

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

def process_block_header_from_db(input_arg_format, data, human_readable = True):

    block_hash = block_height = None
    if (btc_grunt.valid_hex_hash(data)):
        input_arg_format = "blockhash"
        block_hash = data
    else:
        input_arg_format = "blockheight"
        block_height = data

    # first get the block header
    block_data_rows = queries.get_tx_header(input_arg_format, data)
    bits = btc_grunt.hex2bin(block_data_rows[0]["bits_hex"])
    num_txs = block_data_rows[0]["num_txs"]
    block_dict = {
        "block_hash": btc_grunt.hex2bin(block_data_rows[0]["block_hash_hex"]),
        "orphan_status": btc_grunt.bin2bool(
            block_data_rows[0]["block_orphan_status"],
        ),
        "block_height": block_data_rows[0]["block_height"],
        "timestamp": block_data_rows[0]["block_time"],
        "bits_validation_status": btc_grunt.bin2bool(
            block_data_rows[0]["bits_validation_status"]
        ),
        "difficulty_validation_status": btc_grunt.bin2bool(
            block_data_rows[0]["difficulty_validation_status"],
        ),
        "block_hash_validation_status": btc_grunt.bin2bool(
            block_data_rows[0]["block_hash_validation_status"],
        ),
        "nonce": block_data_rows[0]["nonce"],
        "num_txs": num_txs,
        "merkle_root_validation_status": btc_grunt.bin2bool(
            block_data_rows[0]["merkle_root_validation_status"],
        ),
        "block_hash_validation_status": btc_grunt.bin2bool(
            block_data_rows[0]["block_hash_validation_status"],
        ),
        "block_size": block_data_rows[0]["block_size"],
        "block_size_validation_status": btc_grunt.bin2bool(
            block_data_rows[0]["block_size_validation_status"]
        ),
        "version": block_data_rows[0]["block_version"],
        "tx": {}
    }
    if human_readable:
        block_dict["block_hash"] = block_data_rows[0]["block_hash_hex"]

        block_dict["prev_block_hash"] = \
        block_data_rows[0]["prev_block_hash_hex"]

        block_dict["merkle_root"] = block_data_rows[0]["merkle_root_hex"]
        block_dict["bits"] = block_data_rows[0]["bits_hex"]
    else:
        block_dict["prev_block_hash"] = btc_grunt.hex2bin(
            block_data_rows[0]["prev_block_hash_hex"]
        )
        block_dict["merkle_root"] = btc_grunt.hex2bin(
            block_data_rows[0]["merkle_root_hex"]
        )
        block_dict["bits"] = bits

    block_dict["target"] = btc_grunt.int2hex(btc_grunt.bits2target_int(bits))
    block_dict["difficulty"] = btc_grunt.bits2difficulty(bits)

    # next get the transactions
    for tx_row in block_data_rows:
        tx_num = tx_row["tx_num"]
        tx_dict = get_tx_from_db.process_tx_header_from_db(
            block_data_rows[tx_num], human_readable = False
        )
        tx_dict = get_tx_from_db.process_tx_body_from_db(
            tx_dict, human_readable = True
        )
        tx_dict["timestamp"] = block_data_rows[0]["block_time"]
        del tx_dict["block_hash"]
        del tx_dict["block_height"]
        del tx_dict["tx_num"]
        block_dict["tx"][tx_num] = tx_dict

    return block_dict

if __name__ == '__main__':

    validate_script_usage()
    (block_id, input_arg_format) = get_block.get_stdin_params()
    block_data = process_block_header_from_db(input_arg_format, block_id)

    if input_arg_format == "hex":
        print block_data
    else:
        print btc_grunt.pretty_json(block_data, multiline = True)

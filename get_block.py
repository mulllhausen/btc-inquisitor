#!/usr/bin/env python2.7
"""
this script is intended to replace bitcoin-cli's getblock with the true flag
set, since getblock misses some elements such as the txin funds.
"""
import sys
import btc_grunt

data_types = ["hex", "bitcoin-cli", "full-json", "header-json"]
def validate_script_usage():
    if (
        (len(sys.argv) < 3) or
        (sys.argv[2] not in data_types)
    ):
        raise ValueError(
            "\n\nUsage: ./get_block.py <the block hash in hex | blockheight> "
            "<data type>\n"
            "where <data format> is can be hex, bitcoin-cli, full-json, or "
            "header-json\n"
            "eg: ./get_block.py 000000000019d6689c085ae165831e934ff763ae46a2a6c"
            "172b3f1b60a8ce26f hex\n"
            "or ./get_block.py 257727 bitcoin-cli\n\n"
        )

# what is the format of the input argument
def get_stdin_params():
    return (sys.argv[1], sys.argv[2])

def get_block_data_from_rpc(block_id, data_format):
    btc_grunt.connect_to_rpc()

    if data_format == "hex":
        return btc_grunt.get_block(block_id, "hex")

    # we need to know the block height for the mining reward
    if (btc_grunt.valid_hash(block_id)):
        block_data_rpc = btc_grunt.get_block(block_id, "json")
        block_height = block_data_rpc["block_height"]
    else:
        block_height = block_id

    block_height = int(block_height)

    if data_format == "bitcoin-cli":
        try:
            return block_data_rpc
        except NameError:
            return btc_grunt.get_block(block_id, "json")

    block_bytes = btc_grunt.get_block(block_id, "bytes")
    if data_type == "full-json":
        info = btc_grunt.all_block_and_validation_info
    elif data_type == "header-json":
        info = btc_grunt.block_header_info

    explain_fail = True
    return btc_grunt.human_readable_block(btc_grunt.block_bin2dict(
        block_bytes, block_height, info, explain_fail
    ))

if __name__ == '__main__':

    validate_script_usage()
    (block_id, data_type) = get_stdin_params()
    block_data = get_block_data_from_rpc(block_id, data_type)

    if data_type == "hex":
        print block_data
    else:
        print btc_grunt.pretty_json(block_data, multiline = True)

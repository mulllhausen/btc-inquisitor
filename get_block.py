#!/usr/bin/env python2.7
"""
this script is intended to replace bitcoin-cli's getblock with the true flag
set, since getblock misses some elements such as the txin funds.
"""
import os
import sys
import btc_grunt
import lang_grunt

data_formats = ["hex", "bitcoin-cli", "full-json", "header-json"]
def get_usage_str(scriptname, data_formats):
    return "Usage: ./%s <the block hash in hex | blockheight> <data type>\n" \
    "where <data format> can be %s\n" \
    "eg: ./%s 000000000019d6689c085ae165831e934ff763ae46a2a6c" \
    "172b3f1b60a8ce26f hex\n" \
    "or ./%s 257727 bitcoin-cli\n\n" % (
        scriptname, lang_grunt.list2human_str(data_formats, "or"), scriptname,
        scriptname
    )

def validate_script_usage(usage):
    if (
        (len(sys.argv) < 3) or
        (sys.argv[2] not in data_formats)
    ):
        raise ValueError("\n\n" + usage)

    if btc_grunt.valid_hex_hash(sys.argv[1], explain = False):
        return
 
    try:
        int(sys.argv[1])
        return
    except:
        pass

    raise ValueError(
        "\n\nthe first argument was neither a block hash nor a block height"
        "\n\n" + usage
    )

# what is the format of the input argument
def get_stdin_params():
    if btc_grunt.valid_hex_hash(sys.argv[1], explain = False):
        block_id = sys.argv[1]
    else:
        block_id = int(sys.argv[1])
    return (block_id, sys.argv[2])

def get_block_data_from_rpc(block_id, data_format, human_readable = True):
    btc_grunt.connect_to_rpc()

    if data_format == "hex":
        return btc_grunt.get_block(block_id, "hex")

    # we need to know the block height for the mining reward
    if (btc_grunt.valid_hex_hash(block_id)):
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
    if data_format == "full-json":
        info = btc_grunt.all_block_and_validation_info
    elif data_format == "header-json":
        info = btc_grunt.block_header_info

    explain_fail = True
    return btc_grunt.block_bin2dict(
        block_bytes, block_height, info, ["rpc"], explain_fail
    )

if __name__ == '__main__':

    validate_script_usage(
        get_usage_str(os.path.basename(__file__), data_formats)
    )
    (block_id, data_format) = get_stdin_params()
    human_readable = True
    block_data = get_block_data_from_rpc(block_id, data_format, human_readable)

    if data_format == "hex":
        print block_data
    elif data_format == "bitcoin-cli":
        print btc_grunt.pretty_json(block_data)
    elif (
        (data_format == "full-json") or
        (data_format == "header-json")
    ):
        print btc_grunt.pretty_json(
            btc_grunt.human_readable_block(block_data, None), multiline = True
        )

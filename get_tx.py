#!/usr/bin/env python2.7
"""
this script is intended to replace bitcoin-cli's getrawtransaction with the 1
flag set, since getrawtransaction misses some elements such as the txin funds.
this script also returns data about where the transaction is within the
blockchain.
"""
import sys
import btc_grunt
import copy

def validate_script_usage():
    if len(sys.argv) < 2:
        raise ValueError(
            "\n\nUsage: ./get_tx.py <the tx hash in hex | blockheight-txnum>\n"
            "eg: ./get_tx.py 514c46f0b61714092f15c8dfcb576c9f79b3f959989b98de39"
            "44b19d98832b58\n"
            "or ./get_tx.py 257727-130\n\n"
        )

# what is the format of the input argument
def get_stdin_params():
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
            raise ValueError(
                "\n\ninvalid input tx hash. %s\n\n." % is_valid_hash
            )

    # get the block data
    if input_arg_format == "blockheight-txnum":
        data = (block_height, tx_num)
    elif input_arg_format == "txhash":
        data = txhash_hex

    return (input_arg_format, data)

def get_tx_data_from_rpc(input_arg_format, data):
    btc_grunt.connect_to_rpc()

    if input_arg_format == "blockheight-txnum":
        # the program always requires the txhash, regardless of input format
        (block_height, tx_num) = data
        block_rpc_dict = btc_grunt.get_block(block_height, "json")
        try:
            txhash_hex = block_rpc_dict["tx"][tx_num]
        except IndexError:
            raise IndexError(
                "\n\ntx number %d does not exist in block %d\n\n"
                % (tx_num, block_height)
            )
    elif input_arg_format == "txhash":
        txhash_hex = data

    # note that this bitcoin-rpc dict is in a different format to the btc_grunt
    # tx dicts
    tx_rpc_dict = btc_grunt.get_transaction(txhash_hex, "json")

    if input_arg_format == "txhash":
        tx_hash_hex = data
        block_rpc_dict = btc_grunt.get_block(tx_rpc_dict["blockhash"], "json")
        block_height = block_rpc_dict["height"]
        tx_num = block_rpc_dict["tx"].index(txhash_hex)

    tx_bin = btc_grunt.hex2bin(tx_rpc_dict["hex"])
    required_info = copy.deepcopy(btc_grunt.all_tx_and_validation_info)
    (tx_dict, _) = btc_grunt.tx_bin2dict(
        tx_bin, 0, required_info, tx_num, block_height, ["rpc"]
    )

    return (tx_dict, tx_num, block_rpc_dict, tx_rpc_dict)

if __name__ == '__main__':

    validate_script_usage()
    (input_arg_format, data) = get_stdin_params()

    (tx_dict, tx_num, block_rpc_dict, tx_rpc_dict) = get_tx_data_from_rpc(
        input_arg_format, data
    )
    human_tx_dict = btc_grunt.human_readable_tx(
        tx_dict["bytes"], tx_num, block_rpc_dict["height"],
        block_rpc_dict["time"], block_rpc_dict["version"], ["rpc"]
    )
    print "\nblock height: %d\n" \
    "block hash: %s\n" \
    "tx num: %d\n" \
    "tx: %s" \
    % (
        block_rpc_dict["height"], block_rpc_dict["hash"], tx_num,
        btc_grunt.pretty_json(human_tx_dict)
    )

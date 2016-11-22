#!/usr/bin/env python2.7

"""
parse the specified block range and save it to the mysql db. parsing (not to be
confused with processing) involves extracting the readily available information
from the blocks. see process_blocks_in_db.py for an explanation of how parsing
differs from processing.

use this script like so:

./parse_blocks_to_db.py startblock endblock

or import this script and use it in python like so:

import parse_blocks_to_db
parse_blocks_to_db.parse_range(startblock, endblock)
"""

import sys
import os
import btc_grunt
import queries
import mysql_grunt
import progress_meter
import filesystem_grunt

def validate_script_usage():
    usage = "\n\nUsage: ./parse_blocks_to_db.py startblock endblock\n"
    "eg: ./parse_blocks_to_db.py 1 10"

    if len(sys.argv) < 2:
        raise ValueError(usage)

    try:
        block_height_start = int(sys.argv[1])
        block_height_end = int(sys.argv[2])
    except:
        raise ValueError(usage)

def get_stdin_params():
    block_height_start = int(sys.argv[1])
    block_height_end = int(sys.argv[2])
    return (block_height_start, block_height_end)

block_header_info = [
    "block_height",
    "block_hash",
    "previous_block_hash",
    "version",
    "merkle_root",
    "timestamp",
    "bits",
    "nonce",
    "block_size",
    "num_txs"
]
tx_info = [
    "tx_version",
    "num_tx_inputs",
    "num_tx_outputs",
    "tx_lock_time",
    "tx_hash",
    "tx_size"
    #"tx_change" # don't get this here since it requires the previou tx
]
txin_info = [
    #"txin_funds", # don't get this here since it requires the previous tx
    "txin_hash",
    "txin_index",
    "txin_script_length",
    "txin_script",
    "txin_script_format",
    "txin_sequence_num"
    #"txin_coinbase_change_funds" # don't get this here since it requires the previou tx
]
txout_info = [
    "txout_funds",
    "txout_script_length",
    "txout_script",
    "txout_script_format",
    "txout_standard_script_pubkey",
    "txout_standard_script_address"
]
required_info = block_header_info + tx_info + txin_info + txout_info

def parse_range(block_height_start, block_height_end):
    for block_height in xrange(block_height_start, block_height_end):
        progress_meter.render(
            100 * (block_height - block_height_start) / \
            float(block_height_end - block_height_start),
            "parsing block %d (final: %d)" % (block_height, block_height_end)
        )
        try:
            parse_and_write_block_to_db(block_height)
        except Exception as e:
            print "\n\n---------------------\n\n"
            filesystem_grunt.update_errorlog(e, prepend_datetime = True)
            raise

    progress_meter.render(
        100, "finished parsing from block %d to %d\n" % (
            block_height_start, block_height_end
        )
    )

def parse_and_write_block_to_db(block_height):
    block_bytes = btc_grunt.get_block(block_height, "bytes")
    parsed_block = btc_grunt.block_bin2dict(
        block_bytes, block_height, required_info, explain_errors = False
    )
    # write header to db
    queries.insert_block_header(
        parsed_block["block_height"],
        btc_grunt.bin2hex(parsed_block["block_hash"]),
        btc_grunt.bin2hex(parsed_block["previous_block_hash"]),
        parsed_block["version"],
        btc_grunt.bin2hex(parsed_block["merkle_root"]),
        parsed_block["timestamp"],
        btc_grunt.bin2hex(parsed_block["bits"]),
        parsed_block["nonce"],
        parsed_block["size"],
        parsed_block["num_txs"]
    )

    for (tx_num, parsed_tx) in parsed_block["tx"].items():
        # get the coinbase txin funds, leave all other funds as None for now
        if tx_num == 0:
            txin_funds = btc_grunt.mining_reward(block_height)
        else:
            txin_funds = None

        # this value must be calculated during processing
        parsed_tx["change"] = None

        # write tx data to db
        queries.insert_tx_header(
            parsed_block["block_height"],
            btc_grunt.bin2hex(parsed_block["block_hash"]),
            tx_num,
            btc_grunt.bin2hex(parsed_tx["hash"]),
            parsed_tx["version"],
            parsed_tx["num_inputs"],
            parsed_tx["num_outputs"],
            parsed_tx["lock_time"],
            parsed_tx["size"],
            parsed_tx["change"]
        )

        for (txin_num, txin) in parsed_tx["input"].items():
            txin_script_format = "coinbase" if (txin_num == 0) else \
            txin["script_format"]

            # this value must be calculated during processing
            coinbase_change_funds = None

            # write txin data to db
            queries.insert_txin(
                parsed_block["block_height"],
                btc_grunt.bin2hex(parsed_tx["hash"]),
                txin_num,
                btc_grunt.bin2hex(txin["hash"]),
                txin["index"],
                txin["script_length"],
                btc_grunt.bin2hex(txin["script"]),
                txin_script_format,
                txin["sequence_num"],
                txin_funds, # coinbase funds or null
                coinbase_change_funds
            )

        for (txout_num, txout) in parsed_tx["output"].items():
            pubkey = txout["standard_script_pubkey"]
            if pubkey is not None:
                pubkey = btc_grunt.bin2hex(pubkey)

            # write txout data to db
            queries.insert_txout(
                parsed_block["block_height"],
                btc_grunt.bin2hex(parsed_tx["hash"]),
                txout_num,
                txout["funds"],
                txout["script_length"],
                btc_grunt.bin2hex(txout["script"]),
                txout["script_format"],
                pubkey,
                txout["standard_script_address"]
            )

if __name__ == '__main__':

    validate_script_usage()
    (block_height_start, block_height_end) = get_stdin_params()

    btc_grunt.connect_to_rpc()
    parse_range(block_height_start, block_height_end)
    mysql_grunt.disconnect()

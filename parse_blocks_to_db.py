#!/usr/bin/env python2.7

"""
parse the specified block range and save it to the mysql db. parsing (not to be
confused with processing) involves extracting the readily available information
from the blocks. see process_blocks_to_db.py for an explanation of how parsing
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
import mysql_grunt
import progress_meter
import filesystem_grunt

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
    "tx_size",
    "tx_change"
]
txin_info = [
    "txin_funds",
    "txin_hash",
    "txin_index",
    "txin_script_length",
    "txin_script",
    "txin_script_format",
    "txin_sequence_num",
    "txin_coinbase_change_funds"
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
clean_query = True

def parse_range(block_height_start, block_height_end):
    for block_height in xrange(block_height_start, block_height_end):
        progress_meter.render(
            100 * block_height / float(block_height_end),
            "parsing block %d (final: %d)" % (block_height, block_height_end)
        )
        try:
            parse_and_write_block_to_db(block_height)
        except Exception as e:
            print "\n\n---------------------\n\n"
            filesystem_grunt.update_errorlog(e, prepend_datetime = True)
            raise

    progress_meter.render(100, "parsed final block: %d\n" % block_height_end)

def parse_and_write_block_to_db(block_height):
    block_bytes = btc_grunt.get_block(block_height, "bytes")
    parsed_block = btc_grunt.block_bin2dict(
        block_bytes, block_height, required_info, explain_errors = False
    )
    # write header to db
    mysql_grunt.cursor.execute("""
        insert into blockchain_headers set
        block_height = %s,
        block_hash = unhex(%s),
        previous_block_hash = unhex(%s),
        version = %s,
        merkle_root = unhex(%s),
        timestamp = %s,
        bits = unhex(%s),
        nonce = %s,
        block_size = %s,
        num_txs = %s
    """, (
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
    ))

    for (tx_num, parsed_tx) in parsed_block["tx"].items():
        # write tx data to db
        mysql_grunt.cursor.execute("""
            insert into blockchain_txs set
            block_height = %s,
            block_hash = unhex(%s),
            tx_num = %s,
            tx_hash = unhex(%s),
            tx_version = %s,
            num_txins = %s,
            num_txouts = %s,
            tx_lock_time = %s,
            tx_size = %s,
            tx_change = %s
        """, (
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
        ))

        for (txin_num, txin) in parsed_tx["input"].items():
            txin_script_format = "coinbase" if (txin_num == 0) else \
            txin["txin_script_format"]

            coinbase_change_funds = txin["coinbase_change_funds"] if \
            ("coinbase_change_funds" in txin) else None

            # write txin data to db
            mysql_grunt.cursor.execute("""
                insert into blockchain_txins set
                block_height = %s,
                tx_hash = unhex(%s),
                txin_num = %s,
                prev_txout_hash = unhex(%s),
                prev_txout_num = %s,
                script_length = %s,
                script = unhex(%s),
                script_format = %s,
                txin_sequence_num = %s,
                funds = %s,
                txin_coinbase_change_funds = %s
            """, (
                parsed_block["block_height"],
                btc_grunt.bin2hex(parsed_tx["hash"]),
                txin_num,
                btc_grunt.bin2hex(txin["hash"]),
                txin["index"],
                txin["script_length"],
                btc_grunt.bin2hex(txin["script"]),
                txin_script_format,
                txin["sequence_num"],
                txin["funds"], # coinbase funds or null
                coinbase_change_funds
            ))

        for (txout_num, txout) in parsed_tx["output"].items():
            pubkey = txout["standard_script_pubkey"]
            if pubkey is not None:
                pubkey = btc_grunt.bin2hex(pubkey)

            # write txout data to db
            mysql_grunt.cursor.execute("""
                insert into blockchain_txouts set
                block_height = %s,
                tx_hash = unhex(%s),
                txout_num = %s,
                funds = %s,
                script_length = %s,
                script = unhex(%s),
                script_format = %s,
                pubkey = unhex(%s),
                address = %s
            """, (
                parsed_block["block_height"],
                btc_grunt.bin2hex(parsed_tx["hash"]),
                txout_num,
                txout["funds"],
                txout["script_length"],
                btc_grunt.bin2hex(txout["script"]),
                txout["script_format"],
                pubkey,
                txout["standard_script_address"]
            ))

if (
    (os.path.basename(__file__) == "parse_blocks_to_db.py") and
    (len(sys.argv) > 1)
):
    # the user is calling this script from the command line
    try:
        block_height_start = int(sys.argv[1])
        block_height_end = int(sys.argv[2])
    except:
        raise IOError("usage: ./parse_blocks_to_db.py startblock endblock")

    btc_grunt.connect_to_rpc()
    parse_range(block_height_start, block_height_end)

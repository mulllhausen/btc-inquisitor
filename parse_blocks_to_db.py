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
import btc_grunt
import mysql_grunt
import progress_meter

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
	"txin_sequence_num"
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
            "parsing block %d of %d" % (block_height, block_height_end)
        )
        parse_block(block_height)

def parse_block(block_height):
    block_bytes = btc_grunt.get_block(block_height, "bytes")
    parsed_block = btc_grunt.block_bin2dict(
        block_bytes, block_height, required_info, explain_errors = False
    )
    # write header to db
    mysql_grunt.execute("""
        insert into blockchain_headers set
        block_height = %d,
        block_hash = unhex('%s'),
        previous_block_hash = unhex('%s'),
        version = %d,
        merkle_root = unhex('%s'),
        timestamp = %d,
        bits = unhex('%s'),
        nonce = %d,
        block_size = %d,
        num_txs = %d
    """ % (parsed_block[field] for field in block_header_info),
    clean_query)

    for (tx_num, parsed_tx) in parsed_block["tx"].items():
        # write tx data to db
        mysql_grunt.execute("""
            insert into blockchain_txs set
            block_hash = unhex('%s'),
            tx_num = %d,
            tx_hash = unhex('%s'),
            tx_version = %d,
            num_txins = %d,
            num_txouts = %d,
            tx_lock_time = %d,
            tx_size = %d,
            tx_change = %d
        """ % (
            parsed_block["parsed_hash"],
            tx_num,
            parsed_tx["hash"],
            parsed_tx["version"],
            parsed_tx["num_inputs"],
            parsed_tx["num_outputs"],
            parsed_tx["lock_time"],
            parsed_tx["size"],
            parsed_tx["change"]
        ), clean_query)

        for (txin_num, txin) in parsed_tx["input"].items():
            # write txin data to db
            mysql_grunt.execute("""
                insert into blockchain_txins set
                tx_hash = unhex('%s'),
                txin_num = %d,
                prev_txout_hash = unhex('%s')
                prev_txout_num = %d,
                script_length = %d,
                script = unhex('%s'),
                script_format = '%s',
                txin_sequence_num = %d,
                funds = %d
            """ % (
                parsed_tx["hash"],
                txin_num,
                txin["hash"],
                txin["index"],
                txin["script_length"],
                txin["script"],
                txin["script_format"],
                txin["sequence_num"],
                txin["funds"] # coinbase funds or null
            ), clean_query)

        for (txout_num, txout) in parsed_tx["output"].items():
            # write txout data to db
            mysql_grunt.execute("""
                insert into blockchain_txouts set
                tx_hash = unhex('%s'),
                txout_num = %d,
                funds = %d,
                script_length = %d,
                script = unhex('%s'),
                script_format = '%s',
                pubkey = unhex('%s'),
                address = '%s'
            """ % (
                parsed_tx["hash"],
                txout_num,
                txout["funds"],
                txout["script_length"],
                txout["script"],
                txout["script_format"],
                txout["standard_script_pubkey"],
                txout["standard_script_address"]
            ), clean_query)

if (sys.argv[0] == "parse_blocks_to_db.py" and len(sys.argv) > 1):
    # the user is calling this script from the command line
    try:
        block_height_start = int(sys.argv[1])
        block_height_end = int(sys.argv[2])
    except:
        raise IOError("usage: ./parse_blocks_to_db.py startblock endblock")

    btc_grunt.connect_to_rpc()
    parse_range(block_height_start, block_height_end)

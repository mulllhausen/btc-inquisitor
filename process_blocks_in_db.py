#!/usr/bin/env python2.7

"""
process the specified block range in the mysql db. processing (not to be
confused with parsing) involves updating the following existing block data in
the db:

- update the txin funds value for any blocks in the range
- update the tx change funds value for each tx in a block in the range
- update the txin coinbase change funds for any blocks in the range
-
-
-
-

use this script like so:

./process_blocks_in_db.py startblock endblock

or import this script and use it in python like so:

import process_blocks_in_db
process_blocks_in_db.process_range(startblock, endblock)
"""

import sys
import os
import btc_grunt
import mysql_grunt

def process_range(block_height_start, block_height_end):

    print "updating all txin funds between block %d and %d..." % \
    (block_height_start, block_height_end)

    mysql_grunt.cursor.execute("""
        update blockchain_txins txin
        inner join blockchain_txouts txout on (
            txin.prev_txout_hash = txout.tx_hash
            and txin.prev_txout_num = txout.txout_num
        )
        set txin.funds = txout.funds
        where txin.funds is null
        and txin.block_height >= %s
        and txin.block_height < %s
    """, (block_height_start, block_height_end))
    print "done. %d rows updated\n" % mysql_grunt.cursor.rowcount

    print "updating the change funds for each tx between block %d and %d..." \
    % (block_height_start, block_height_end)

    mysql_grunt.cursor.execute("""
        update blockchain_txs tx
        inner join (
            select sum(funds) as txins_total, tx_hash
            from blockchain_txins
            group by tx_hash
        ) txin on tx.tx_hash = txin.tx_hash
        inner join (
            select sum(funds) as txouts_total, tx_hash
            from blockchain_txouts
            group by tx_hash
        ) txout on tx.tx_hash = txout.tx_hash
        set tx.tx_change = (txin.txins_total - txout.txouts_total)
        where tx.tx_change is null
        and tx.block_height >= %s
        and tx.block_height < %s
    """, (block_height_start, block_height_end))
    print "done. %d rows updated\n" % mysql_grunt.cursor.rowcount

if (
    (os.path.basename(__file__) == "process_blocks_in_db.py") and
    (len(sys.argv) > 2)
):
    # the user is calling this script from the command line
    try:
        block_height_start = int(sys.argv[1])
        block_height_end = int(sys.argv[2])
    except:
        raise IOError("usage: ./process_blocks_in_db.py startblock endblock")

    process_range(block_height_start, block_height_end)
    mysql_grunt.disconnect()

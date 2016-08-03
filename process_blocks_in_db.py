#!/usr/bin/env python2.7

"""
process the specified block range in the mysql db. processing (not to be
confused with parsing) involves updating the following existing block data in
the db:

- update the txin funds value for any blocks in the range
- update the tx change funds value for each tx in a block in the range
- update the txin coinbase change funds for any blocks in the range
- extract the pubkeys from non-standard scripts
- extract the addresses from pubkeys
- copy the addresses from the txouts to the txins spending them
- update
- update
- validate the merkle root for each block
- validate the coinbase txin hash
- validate the coinbase txin index
- validate
- validate

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
import progress_meter

def process_range(block_height_start, block_height_end):

    print "updating all txin funds between block %d and %d by copying over" \
    " the funds being spent from the previous txouts..." % \
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

    # note that txin.tx_change_calculated and txout.tx_change_calculated are
    # used to speed up the query
    print "updating the change funds for each tx between block %d and %d..." \
    % (block_height_start, block_height_end)
    mysql_grunt.cursor.execute("""
        update blockchain_txs tx
        inner join (
            select sum(funds) as txins_total, tx_hash
            from blockchain_txins
            where tx_change_calculated = false
            and block_height >= %s
            and block_height < %s
            group by tx_hash
        ) txin on tx.tx_hash = txin.tx_hash
        inner join (
            select sum(funds) as txouts_total, tx_hash
            from blockchain_txouts
            where tx_change_calculated = false
            and block_height >= %s
            and block_height < %s
            group by tx_hash
        ) txout on tx.tx_hash = txout.tx_hash
        set tx.tx_change = (txin.txins_total - txout.txouts_total)
        where tx.tx_change is null
        and tx.tx_num != 0
        and tx.block_height >= %s
        and tx.block_height < %s
    """, (block_height_start, block_height_end) * 3)
    print "done. %d rows updated\n" % mysql_grunt.cursor.rowcount

    print "marking off the txins that have been used to calculate the change" \
    " funds for each tx between block %d and %d..." \
    % (block_height_start, block_height_end)
    mysql_grunt.cursor.execute("""
        update blockchain_txins
        set tx_change_calculated = true
        where block_height >= %s
        and block_height < %s
    """, (block_height_start, block_height_end))
    print "done. %d rows updated\n" % mysql_grunt.cursor.rowcount

    print "marking off the txouts that have been used to calculate the change" \
    " funds for each tx between block %d and %d..." \
    % (block_height_start, block_height_end)
    mysql_grunt.cursor.execute("""
        update blockchain_txouts
        set tx_change_calculated = true
        where block_height >= %s
        and block_height < %s
    """, (block_height_start, block_height_end))
    print "done. %d rows updated\n" % mysql_grunt.cursor.rowcount

    print "updating the coinbase change funds for each coinbase txin between" \
    " block %d and %d..." \
    % (block_height_start, block_height_end)
    mysql_grunt.cursor.execute("""
        update blockchain_txins txin
        inner join (
            select sum(tx_totals.tx_change) as total_change, tx0.tx_hash
            from blockchain_txs tx_totals
            inner join blockchain_txs tx0 on (
                tx0.block_hash = tx_totals.block_hash
                and tx0.tx_num = 0
            )
            where tx_totals.tx_num != 0
            and tx_totals.block_height >= %s
            and tx_totals.block_height < %s
            group by tx_totals.block_hash
        ) block on block.tx_hash = txin.tx_hash
        set txin.txin_coinbase_change_funds = block.total_change
        where txin.txin_num = 0
        and txin.txin_coinbase_change_funds is null
    """, (block_height_start, block_height_end))
    print "done. %d rows updated\n" % mysql_grunt.cursor.rowcount

    # the following code can only be tested once a non-standard txout script is
    # found:
    # the logic here mimics validate_tx_scripts.py and update_addresses_db.py
    #print "extracting the valid pubkeys for each txin and txout script pair" \
    #" where the txin belongs to a block between %d and %d..." \
    #% (block_height_start, block_height_end)
    #all_rows = mysql_grunt.quick_fetch("""
    #    select
    #    block.timestamp,
    #    block.version,
    #    block.block_height,
    #    block.
    #    from blockchain_txins txin
    #    inner join blockchain_txouts txout on (
    #        txin.prev_txout_hash = txout.tx_hash
    #        and txin.prev_txout_num = txout.txout_num
    #    )
    #    inner join blockchain_txs tx on txin.tx_hash = tx.tx_hash
    #    inner join blockchain_headers block on tx.block_hash = block.block_hash
    #    where txout.pubkey is null
    #    and txout.address is null
    #    and txout.alternate_address is null
    #    and txin.non_standard_pubkey_extraction_attempted = false
    #    and tx.tx_num != 0
    #    and block_height >= %s
    #    and block_height < %s
    #""", (block_height_start, block_height_end))
    #num_txins = mysql_grunt.cursor.rowcount
    #print "found %d txins which require pubkey extraction" % num_txins

    #rows_updated = 0 # init
    #skip_checksig = False
    #bugs_and_all = True
    #explain = True
    #for (i, row) in enumerate(all_rows):
    #    block_time = row["blocktime"]
    #    block_version = row["version"]
    #    tx =
    #    prev_tx0 = 
    #    script_eval_data = verify_script(
    #        block_time, tx, txin_num, prev_tx0, block_version, skip_checksig,
    #        bugs_and_all, explain
    #    )

    #    for on_txin_num in range(len(tx_rpc_dict["vin"])):

    #    pubkey_hex = row["pubkey_hex"]
    #    (uncompressed_address, compressed_address) = btc_grunt.pubkey2addresses(
    #        btc_grunt.hex2bin(pubkey_hex)
    #    )
    #    # if there is only one valid pubkey then update the row
    #    mysql_grunt.cursor.execute("""
    #        update blockchain_txouts
    #        set address = %s,
    #        alternate_address = %s
    #        where pubkey = unhex(%s)
    #    """, (uncompressed_address, compressed_address, pubkey_hex))
    #    rows_updated += mysql_grunt.cursor.rowcount
    #    progress_meter.render(
    #        100 * i / float(num_pubkeys),
    #        "updated addresses for %d unique pubkeys (of %d pubkeys)" \
    #        % (i, num_pubkeys)
    #    )

    #progress_meter.render(100, "updated pubkeys for %d txins\n" % num_txins)
    #print "done. %d rows updated\n" % mysql_grunt.cursor.rowcount

    print "updating the address and alternate address for txout pubkeys" \
    " between block %d and %d..." % (block_height_start, block_height_end)
    all_rows = mysql_grunt.quick_fetch("""
        select hex(pubkey) as pubkey_hex
        from blockchain_txouts
        where (
            address is null
            or alternate_address is null
        )
        and block_height >= %s
        and block_height < %s
        and pubkey is not null
        group by pubkey
    """, (block_height_start, block_height_end))
    num_pubkeys = mysql_grunt.cursor.rowcount
    print "found %d unique pubkeys without addresses" % num_pubkeys

    rows_updated = 0 # init
    for (i, row) in enumerate(all_rows):
        pubkey_hex = row["pubkey_hex"]
        (uncompressed_address, compressed_address) = btc_grunt.pubkey2addresses(
            btc_grunt.hex2bin(pubkey_hex)
        )
        mysql_grunt.cursor.execute("""
            update blockchain_txouts
            set address = %s,
            alternate_address = %s
            where pubkey = unhex(%s)
        """, (uncompressed_address, compressed_address, pubkey_hex))
        rows_updated += mysql_grunt.cursor.rowcount
        progress_meter.render(
            100 * i / float(num_pubkeys),
            "updated addresses for %d unique pubkeys (of %d pubkeys)" \
            % (i, num_pubkeys)
        )

    progress_meter.render(
        100, "updated addresses for %d unique pubkeys\n" % num_pubkeys
    )
    print "done. %d rows updated (some pubkeys may exist in multiple rows)\n" \
    % rows_updated

    print "updating all txin addresses between block %d and %d by copying" \
    " over the addresses from the previous txouts..." \
    % (block_height_start, block_height_end)
    mysql_grunt.cursor.execute("""
        update blockchain_txins txin
        inner join blockchain_txouts txout on (
            txin.prev_txout_hash = txout.tx_hash
            and txin.prev_txout_num = txout.txout_num
        )
        set txin.address = txout.address,
        txin.alternate_address = txout.alternate_address
        where (
            txin.address is null
            or txin.alternate_address is null
        )
        and txin.block_height >= %s
        and txin.block_height < %s
    """, (block_height_start, block_height_end))
    print "done. %d rows updated\n" % mysql_grunt.cursor.rowcount

def query_get_tx(tx_hash = None):
    query = """
        select
        'txin' as 'type',
        txin_num,
        address as 'txin_address',
        funds as 'txin_funds',
        '' as 'txout_num',
        '' as 'txout_address',
        '' as 'txout_funds'
        from blockchain_txins
        where
        tx_hash = unhex('%s')

        union all

        select
        'txout' as 'type',
        '' as 'txin_num',
        '' as 'txin_address',
        '' as 'txin_funds',
        txout_num as 'txout_num',
        address as 'txout_address',
        funds as 'txout_funds'
        from blockchain_txouts
        where
        tx_hash = unhex('%s')
    """
    if tx_hash is not None:
        query = query % tx_hash

    return query

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

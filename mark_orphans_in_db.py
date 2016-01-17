#!/usr/bin/env python2.7

"""
mark all orphans in the map_addresses_to_txs table by setting orphan_block = 1
and unmark any previous orphans in the map_addresses_to_txs table by setting
orphan_block = 0.

do this by starting at the very last known good block (use bitcoin-cli for this)
and working back using the previous block hash value from bitcoin-cli. for each
block, mark the tx-hashes in the db that are given by bitcoin-cli as non-orphans
and mark any that are not given by bitcoin-cli as orphans.

work back a maximum of 1000 blocks from the best chain tip (about 7 days).
"""

import MySQLdb
import btc_grunt
import mysql_grunt

btc_grunt.connect_to_rpc()
chaintip_hash_hex = btc_grunt.get_best_block_hash()

with open("mysql_connection.json") as mysql_params_file:
    mysql_params = json.load(mysql_params_file)

mysql_db = MySQLdb.connect(**mysql_params)
mysql_db.autocommit(True)
cursor = mysql_db.cursor(MySQLdb.cursors.DictCursor)

def main(blockhash_hex):

    # go back this many blocks from the top:
    total = 1000

    for i in xrange(1, total + 1):
        # get all hashes for this blockheight
        block_rpc_dict = btc_grunt.get_block(blockhash_hex, "json")
        blockheight = block_rpc_dict["height"]
        maybe_print("%d/%d block %d" % (i, total, blockheight))

        # mark orphans
        cmd1 = """
        update map_addresses_to_txs
        set orphan_block = 1
        where blockheight = %d and unhex(txhash) not in ('%s')
        """ % (blockheight, "','".join(block_rpc_dict["tx"]))
        cmd1 = mysql_grunt.clean_query(cmd1)

        cursor.execute(cmd1)
        if cursor.rowcount > 0:
            maybe_print("found orphans at blockheight %d" % blockheight)

        # unmark ex-orphans
        cmd2 = """
        update map_addresses_to_txs
        set orphan_block = 0
        where blockheight = %d and unhex(txhash) in ('%s')
        """ % (blockheight, "','".join(block_rpc_dict["tx"]))
        cmd2 = mysql_grunt.clean_query(cmd2)

        cursor.execute(cmd2)
        if cursor.rowcount > 0:
            maybe_print(
                "ex-orphans at blockheight %d moved to main chain" % blockheight
            )

        # setup for next loop
        blockhash_hex = block_rpc_dict["previousblockhash"]

def maybe_print(txt):
    # comment the next line out if silence is required
    print txt

main(chaintip_hash_hex)
mysql_db.close()

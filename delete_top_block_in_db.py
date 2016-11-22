#!/usr/bin/env python2.7

import mysql_grunt
import queries

# get the highest block height from each table, and select the lowest of these

top_block = queries.get_top_block_by_block_header()

tmp_top_block = queries.get_top_block_by_tx_header()
if tmp_top_block < top_block:
    top_block = tmp_top_block

tmp_top_block = queries.get_top_block_by_txout()
if tmp_top_block < top_block:
    top_block = tmp_top_block

tmp_top_block = queries.get_top_block_by_txin()
if tmp_top_block < top_block:
    top_block = tmp_top_block

# delete everything above the top block in the db in all tables. do one
# statement per execute command. multiple statements causes weird errors.
queries.delete_block_range(top_block, 1000000000)

print "\ndeleted top block %d\n" % top_block

mysql_grunt.disconnect()

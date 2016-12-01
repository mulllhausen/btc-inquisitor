#!/usr/bin/env python2.7

import mysql_grunt
import queries

print """
top block by block header: %d
top block by tx header   : %d
top block by txout       : %d
top block by txin        : %d
""" % (
    queries.get_top_block_by_block_header(),
    queries.get_top_block_by_tx_header(),
    queries.get_top_block_by_txout(),
    queries.get_top_block_by_txin()
)

mysql_grunt.disconnect()

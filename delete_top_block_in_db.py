#!/usr/bin/env python2.7

import mysql_grunt

top_block = mysql_grunt.quick_fetch("""
    select block_height
    from blockchain_headers
    order by block_height desc
    limit 0,1
""")[0]["block_height"]

# do one statement per execute command. multiple statements causes weird errors
mysql_grunt.cursor.execute("""
    delete from blockchain_headers where block_height = %s;
""", top_block)

mysql_grunt.cursor.execute("""
    delete from blockchain_txs where block_height = %s;
""", top_block)

mysql_grunt.cursor.execute("""
    delete from blockchain_txins where block_height = %s;
""", top_block)

mysql_grunt.cursor.execute("""
    delete from blockchain_txouts where block_height = %s;
""", top_block)

print "\ndeleted top block %d\n" % top_block

mysql_grunt.disconnect()

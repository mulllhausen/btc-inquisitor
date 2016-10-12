#!/usr/bin/env python2.7

import sys
import mysql_grunt

if len(sys.argv) < 2:
    raise ArgumentError("usage: ./delete_block_in_db.py <blocknum>")

try:
    block_to_delete = int(sys.argv[1])
except:
    raise ValueError("you must supply the block to delete as a number")

any_deleted = False

# do one statement per execute command. multiple statements causes weird errors
mysql_grunt.cursor.execute("""
    delete from blockchain_headers where block_height = %s
""", block_to_delete)

if mysql_grunt.cursor.rowcount > 0:
    any_deleted = True

mysql_grunt.cursor.execute("""
    delete from blockchain_txs where block_height = %s
""", block_to_delete)

if mysql_grunt.cursor.rowcount > 0:
    any_deleted = True

mysql_grunt.cursor.execute("""
    delete from blockchain_txins where block_height = %s
""", block_to_delete)

if mysql_grunt.cursor.rowcount > 0:
    any_deleted = True

mysql_grunt.cursor.execute("""
    delete from blockchain_txouts where block_height = %s
""", block_to_delete)

if mysql_grunt.cursor.rowcount > 0:
    any_deleted = True

if any_deleted:
    print "\ndeleted block %d\n" % block_to_delete
else:
    print "\nno traces of block %d existed in the db. nothing deleted.\n" \
    % block_to_delete

mysql_grunt.disconnect()

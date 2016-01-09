#!/usr/bin/env python2.7
"""
get the times when the balance changed. returns a json array in the following
format: [
    [unixtime0, 12345],
    [unixtime1, -12345],
    [unixtime2, 555000],
    [unixtime3, -444000]
]
the units are satoshis and merely indicate the change in balance (not the
absolute balance).
"""
import sys
import btc_grunt
import json
import MySQLdb

# TODO - also accept pubkey instead of address as input
if len(sys.argv) < 2:
    raise ValueError(
        "\n\nUsage: ./get_balance_over_time.py <the address>\n"
        "eg: ./get_balance_over_time.py 1GkktBuJ6Pr51WEJe5ZzyNvMYaMDFjwyDk\n\n"
	)
address = sys.argv[1]
with open("mysql_connection.json") as mysql_params_file:
    mysql_params = json.load(mysql_params_file)

mysql_db = MySQLdb.connect(**mysql_params)
mysql_db.autocommit(True)
cursor = mysql_db.cursor() # removed MySQLdb.cursors.DictCursor)

# first get alternate addresses if available, grouping is to reduce the result
# set down to that which is unique
cursor.execute(
    "select address, alternate_address"
    " from map_addresses_to_txs"
    " where address = '%s' or alternate_address = '%s'"
    " group by address, alternate_address"
    % (address, address)
)
data = cursor.fetchall()
for (i, record) in enumerate(data):
    if (
        #(record["address"] != "") and
        (record[0] != "") and
        #(record["address"] != address)
        (record[0] != address)
    ):
        #alternate_address = record["address"]
        alternate_address = record[0]

    if (
        #(record["alternate_address"] != "") and
        (record[1] != "") and
        #(record["alternate_address"] != address)
        (record[1] != address)
    ):
        #alternate_address = record["alternate_address"]
        alternate_address = record[1]

# next get all transactions for these addresses
cursor.execute(
    "select blockheight, hex(txhash), txin_num, txout_num"
    " from map_addresses_to_txs"
    " where address = '%s' or alternate_address = '%s' or address = '%s' or"
    " alternate_address = '%s'"
    " order by blockheight asc"
    % (address, address, alternate_address, alternate_address)
)
data = list(cursor.fetchall())

# convert the data from [[blockheight, txhash, txin_num, txout_num], [...]]
# to {"blockheight-txhash": [txin_num, txout_num], "blockheight-txhash": [...]}
# this way when we use the rpc client to get the txhash we can avoid getting the
# same txhash multiple times via rpc (slow)

btc_grunt.connect_to_rpc()
res = []
for record in data:
	# the blockhash that the tx appears in
    block_hash = tx_rpc_dict["blockhash"]

    block_rpc_dict = btc_grunt.get_block(block_hash, "json")
    block_height = block_rpc_dict["height"]
    tx_num = block_rpc_dict["tx"].index(txhash_hex)
    tx_rpc_dict = btc_grunt.get_transaction(record["txhash"], "json")
    tx_bin = btc_grunt.hex2bin(tx_rpc_dict["hex"])
    tx_dict = btc_grunt.human_readable_tx(
        tx_bin, tx_num, block_height, block_rpc_dict["time"],
        block_rpc_dict["version"]
    )
    res.append([block_rpc_dict["time"], ])

if not txhash_data:
	exit()
print btc_grunt.pretty_json(txhash_data)

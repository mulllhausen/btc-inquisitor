#!/usr/bin/env python2.7
"""
get the times when the balance changed. returns a json array in the following
format: [
    [time0, 12345],
    [time1, -12345],
    [time2, 555000],
    [time3, -444000]
]
the units are satoshis and merely indicate the change in balance (not the
absolute balance).
"""
import sys
import btc_grunt
import lang_grunt
import json
import MySQLdb
import datetime

# TODO - also accept pubkey instead of address as input
if len(sys.argv) < 3:
    raise ValueError(
        "\n\nUsage: ./get_balance_over_time.py <the address>"
        " [unixtime|datetime]\n"
        "eg: ./get_balance_over_time.py 12cbQLTFMXRnSzktFkuoG3eHoMeFtpTu3S"
        " datetime\n\n"

	)
address = sys.argv[1]
time_format = sys.argv[2]
allowed_time_formats = ["datetime", "unixtime"]
if time_format not in allowed_time_formats:
    raise ValueError(
        "unrecognized 'time' parameter: %s\n"
        "allowed values are %s"
        % (time_format, lang_grunt.list2human_str(allowed_time_formats, "or"))
    )

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
    " order by blockheight asc, txout_num asc"
    % (address, address, alternate_address, alternate_address)
)
data = list(cursor.fetchall())

btc_grunt.connect_to_rpc()

# this dict that will hold the result to be processed and displayed to the user
# in the format {time: {txhash: balance}
balance_history = {}

# we store these dicts in case we can re-use them (eg if there are multiple txs
# from the same block, or multiple txins or txouts from the same tx)
block_rpc_dicts = {}
tx_rpc_dicts = {}
tx_dicts = {}

for record in data:
    block_height = record[0]
    txhash_hex = record[1].lower()
    txin_num = record[2]
    txout_num = record[3]

    # only get the tx rpc dict if we have not previously got it
    if txhash_hex not in tx_rpc_dicts:
        tx_rpc_dicts[txhash_hex] = btc_grunt.get_transaction(txhash_hex, "json")
    tx_rpc_dict = tx_rpc_dicts[txhash_hex]

    block_hash = tx_rpc_dict["blockhash"]

    # only get the block rpc dict if we have not previously got it
    if block_hash not in block_rpc_dicts: 
        block_rpc_dicts[block_hash] = btc_grunt.get_block(block_hash, "json")
    block_rpc_dict = block_rpc_dicts[block_hash]

    tx_num = block_rpc_dict["tx"].index(txhash_hex)
    tx_bin = btc_grunt.hex2bin(tx_rpc_dict["hex"])

    if txhash_hex not in tx_dicts:
        (tx_dicts[txhash_hex], _) = btc_grunt.tx_bin2dict(
            tx_bin, 0, ["txin_funds", "txout_funds"], tx_num, block_height,
            ["rpc"], explain_errors = True
        )
    tx_dict = tx_dicts[txhash_hex]

    if (
        (txin_num is None) and
        (txout_num is not None)
    ):
        # the address is in the txout - ie funds have been sent to the address
        balance_diff = tx_dict["output"][txout_num]["funds"]
    elif (
        (txout_num is None) and
        (txin_num is not None)
    ):
        # the address is in the txin - ie funds have been sent by the address
        balance_diff = -tx_dict["input"][txin_num]["funds"]

    if time_format == "unixtime":
        time = block_rpc_dict["time"]
    elif time_format == "datetime":
        time = datetime.datetime.utcfromtimestamp(block_rpc_dict["time"]).\
        strftime("%Y-%m-%d %H:%M:%S")

    if time not in balance_history:
        balance_history[time] = {} # init
    if txhash_hex not in balance_history[time]:
        balance_history[time][txhash_hex] = balance_diff
    else:
        balance_history[time][txhash_hex] += balance_diff

balance_list = []
for time in sorted(balance_history):
    for (txhash_hex, balance) in balance_history[time].items():
        balance_list.append([time, balance])

print btc_grunt.pretty_json(balance_list)

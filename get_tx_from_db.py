#!/usr/bin/env python2.7
"""
this script is very similar to ./get_tx.py. the purpose of this apparent
duplication is that this script does not require bitcoin-cli to function - it
just requires a database populated with the bitcoin blockchain as per schema.sql
"""
import sys
import btc_grunt
import mysql_grunt

if len(sys.argv) < 2:
	raise ValueError(
		"\n\nUsage: ./get_tx_from_db.py <the tx hash in hex | "
        "blockheight-txnum>\n"
		"eg: ./get_tx.py 514c46f0b61714092f15c8dfcb576c9f79b3f959989b98de3944b1"
		"9d98832b58\n"
		"or ./get_tx.py 257727-130\n\n"
	)
# what is the format of the input argument
input_arg_format = ""
if "-" in sys.argv[1]:
	input_arg_format = "blockheight-txnum"
	try:
		(block_height, tx_num) = sys.argv[1].split("-")
	except Exception as e:
		raise ValueError(
			"\n\ninvalid input blockheight-txnum format. %s\n\n."
			% e.message
		)
	try:
		block_height = int(block_height)
	except:
		# exception will be raised if non-base-10 characters exist in string
		raise ValueError(
			"\n\ninvalid input block height %s. it is not an integer.\n\n"
			% block_height
		)
	try:
		tx_num = int(tx_num)
	except:
		raise ValueError(
			"\n\ninvalid input tx number %s. it is not an integer.\n\n"
			% tx_num
		)
else:
	input_arg_format = "txhash"
	txhash_hex = sys.argv[1]
	is_valid_hash = btc_grunt.valid_hash(txhash_hex, explain = True)
	if is_valid_hash is not True:
		raise ValueError("\n\ninvalid input tx hash. %s\n\n." % is_valid_hash)

# get the block data
select_start = """select
block_height,
hex(block_hash) as block_hash_hex,
tx_num,
hex(tx_hash) as tx_hash_hex,
tx_change,
tx_funds_balance_validation_status,
num_txins,
num_txouts,
tx_lock_time,
tx_lock_time_validation_status,
tx_size,
tx_version
from blockchain_txs
where"""

if input_arg_format == "blockheight-txnum":
    query = """%s
    block_height = %d and
    tx_num = %d
    """ % (select_start, block_height, tx_num)
elif input_arg_format == "txhash":
    query = """%s
    tx_hash = unhex(%s)
    """ % (select_start, tx_hash_hex)

block_data = mysql_grunt.quick_fetch(query)[0]

# get all the tx data in a single query

tx_data = mysql_grunt.quick_fetch("""
select
'txin' as 'type',
txin.txin_num as 'txin_num',
txin.address as 'txin_address',
txin.alternate_address as 'txin_alternate_address',
txin.funds as 'txin_funds',
txin.prev_txout_hash as 'prev_txout_hash',
txin.prev_txout_num as 'prev_txout_num',
txin.txin_hash_validation_status as 'txin_hash_validation_status',
txin.txin_index_validation_status as 'txin_index_validation_status',
txin.txin_mature_coinbase_spend_validation_status as 'txin_mature_coinbase_spend_validation_status',
hex(txin.script) as 'txin_script_hex',
txin.script_format as 'txin_script_format',
hex(prev_txout.script) as 'prev_txout_script_hex',
prev_txout.script_format as 'prev_txout_script_format',
txin.txin_sequence_num as 'txin_sequence_num',
txin.txin_single_spend_validation_status as 'txin_single_spend_validation_status',
txin.txin_spend_from_non_orphan_validation_status as 'txin_spend_from_non_orphan_validation_status',
txin.txin_checksig_validation_status as 'txin_checksig_validation_status',
'' as 'txout_num',
'' as 'txout_address',
'' as 'txout_funds',
'' as 'txout_alternate_address',
'' as 'txout_pubkey',
'' as 'txout_pubkey_to_address_validation_status',
'' as 'txout_script',
'' as 'txout_script_format',
'' as 'txout_script_length',
'' as 'txout_shared_funds',
'' as 'standard_script_address_checksum_validation_status',
'' as 'txout_change_calculated'
from blockchain_txins txin
left join blockchain_txouts prev_txout on (
    txin.prev_txout_hash = prev_txout.tx_hash and 
    txin.prev_txout_num = prev_txout.txout_num
)
where
txin.tx_hash = unhex(%s)

union all

select
'txout' as 'type',
'' as 'txin_num',
'' as 'txin_address',
'' as 'txin_alternate_address',
'' as 'txin_funds',
'' as 'prev_txout_hash',
'' as 'prev_txout_num',
'' as 'txin_hash_validation_status',
'' as 'txin_index_validation_status',
'' as 'txin_mature_coinbase_spend_validation_status',
'' as 'txin_script_hex',
'' as 'txin_script_format',
'' as 'prev_txout_script_hex',
'' as 'prev_txout_script_format',
'' as 'txin_sequence_num',
'' as 'txin_single_spend_validation_status',
'' as 'txin_spend_from_non_orphan_validation_status',
'' as 'txin_checksig_validation_status',
txout.txout_num as 'txout_num',
txout.address as 'txout_address',
txout.funds as 'txout_funds',
txout.alternate_address as 'txout_alternate_address',
hex(txout.pubkey) as 'txout_pubkey',
txout.pubkey_to_address_validation_status as 'txout_pubkey_to_address_validation_status',
hex(txout.script) as 'txout_script',
txout.script_format as 'txout_script_format',
txout.script_length as 'txout_script_length',
txout.shared_funds as 'txout_shared_funds',
txout.standard_script_address_checksum_validation_status as 'standard_script_address_checksum_validation_status',
txout.tx_change_calculated as 'txout_change_calculated'
from blockchain_txouts txout
where
txout.tx_hash = unhex(%s)
""", (block_data["tx_hash_hex"], block_data["tx_hash_hex"]))

tx_dict = {"input": {}, "output": {}}
for (i, row) in enumerate(tx_data):
    if (row["type"] == "txin"):
        pass
    if (row["type"] == "txout"):
        pass

print "\nblock height: %d\n" \
"block hash: %s\n" \
"tx num: %d\n" \
"tx: %s" \
% (
    block_data["block_height"], block_data["block_hash_hex"],
    block_data["tx_num"], btc_grunt.pretty_json(tx_dict)
)

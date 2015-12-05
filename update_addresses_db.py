#!/usr/bin/env python2.7

"""
this script gets addresses from the blockchain and stores then against the tx
hash in a mysql db. using this db table you can easily look up all txs for an
address. storing information in a database is far better than relying on
bitcoin-cli's listtransactions. theoretically listtransactions should be able to
do the same thing as this database, but it currently has a bug which prevents it
from working for watch-only addresses
(https://bitcointalk.org/index.php?topic=1258904.0). and even once this bug is
fixed, it takes ~40 minutes to add a watch-only address (as of nov 2015). a busy
website/app will want to add a new address more than once per second, so a ~40
minute wait would be useless for this purpose.

public keys are points on the secp256k1 elliptic curve. the same pubkey can be
represented in uncompressed or compressed format. the uncompressed pubkey
basically involves concatenating the x and y coordinates, whereas the compressed
pubkey just involves the x coordinate and a sign bit (the y coordinate can be
derived from the x coordinate if we know whether the point we are after lies
above or below the x-axis).

bitcoin addresses are derived by hashing the pubkey. there is one address for
the compressed pubkey and one address for the uncompressed pubkey. but both of
these addresses and pubkeys refer to the same point on the elliptic curve.

to spend a txout the pubkey must be supplied (generally in a txin script but in
earlier blocks it was in the txout script). therefore the pubkey is always known
by the time an address is spent, but it is not always known (to us) when a user
sends funds to an address.

as it scans the blockchain, this script encounters pubkeys. it the derives both
the compressed and uncompressed addresses from the pubkey and stores them both
against that txhash and txin/txout number. but when the script encounters an
address without a pubkey (ie in a standard txout) then only that known address
is stored. without the pubkey there is no way of knowing whether the address is
compressed or uncompressed.

some bitcoin addresses are in p2sh (pay to script-hash) format. this form of
address is a hash of an entire script (as opposed to a hash of a single pubkey).
the script-hash can contain many pubkeys and other script elements. when someone
sends funds to a p2sh address we don't know the pubkey(s) contained within it,
but once the p2sh is spent then the pubkeys are revealed. at that point we
discover which address(es) the funds were really sent to. however there is no
easy way of linking the p2sh address in the txout to the txin addresses that
actually spent the funds. therefore to make this link, update_addresses_db.py
copies the addresses derived from the pubkeys that actually validate to the
txout in the db. this is a special case only used for p2sh txs.

finally, multisignature addresses may involve multiple pubkeys. these may not
always be available in the txout script, but they are always revealed in the
txin script. we store the pubkeys that actually get used and set the
shared_funds flag in the db to indicate that the funds are shared between
multiple addresses (to avoid inflation). 

useful features of this database:

- you can search for an address (search in both the `address` and
`alternate_address` fields) and find the corresponding compressed/uncompressed
address. with this alternate address you can then see all transfers of funds
to/from a single pubkey.

- you can find the pubkey corrsponding to an address (if it has been revealed on
the blockchain already). do this by finding a row where both `address` and
`alternate_address` are not null. this indicates that the pubkey was known in
that tx, so you can feed `txhash` into ./get_tx.py and pull out the pubkey from
the corresponding `txin_num` or `txout_num`.

- you can find the balance for a pubkey by first converting it to both the
compressed and uncompressed addresses, then selecting all rows from the database
that have these addresses. remember to search for the compressed and
uncompressed addresses in both `address` and `alternate_address`.

- search for non-standard txin/txout scripts. do this by searching where
`address` and `alternate_address` are null.

- search for multisig transactions. do this by searching on the shared_funds
field.

- find the addresses that actually received funds within a p2sh address
"""

import MySQLdb, btc_grunt, json

with open("mysql_connection.json") as mysql_params_file:
	mysql_params = json.load(mysql_params_file)

mysql_db = MySQLdb.connect(**mysql_params)
mysql_db.autocommit(True)
cursor = mysql_db.cursor()

cursor.execute("select max(blockheight) from transaction_addresses_and_scripts")
if cursor.rowcount > 0:
	block_height_start = cursor.fetchone()[0] + 1
else:
	block_height_start = 0

btc_grunt.connect_to_rpc()
required_info = [
	"txin_pubkeys", "txin_script", "txin_script_format", "txout_addresses",
	"txout_pubkeys", "txout_script", "txout_script_format", "txin_hash",
	"txin_index"
]
thought - include db fields for txout pubkeys vs txin pubkeys
# loop through all transactions in block and add them to the db.
#
# this is more complicated than it sounds. get the addresses and or pubkeys in
# the following order:
# 1. from standard txout scripts
# 2. from standard txin scripts that spend standard txout scripts that have
# already been validated by btc-inquisitor.py
# 3. non-standard txin scripts
# 
# (3) often requires us to perform a checksig operation on the script to extract
# the pubkey(s). this is slow, but fortunately not extremely common (most
# checksigs are within standard scripts).
#
for block_height in range(block_height_start, block_height_start + 10):
	block_rpc_dict = btc_grunt.get_block(block_height, "json")
	for (tx_num, txhash_hex) in enumerate(block_rpc_dict["tx"]):
		tx = btc_grunt.get_transaction(txhash_hex, "bytes")
		(parsed_tx, _) = btc_grunt.tx_bin2dict(
			tx, 0, required_info, tx_num, block_height, ["rpc"]
		)
		# start with txout data
		for (txout_num, txout) in parsed_tx["outputs"].items():
			txin_num = None
			# if there are any pubkeys then get the corresponding addresses and
			# write these to the db
			if txout["pubkeys"] is not None:
				for pubkey in txout["pubkeys"]:
					address = btc_grunt.pubkey2address(pubkey)
					insert_record(
						block_height, txhash_hex, txin_num, txout_num, address,
						pubkey, shared_funds
					)
				
			for address in 
			# for non-standard scripts, still write a row to the table but do not
			# populate pubkey or address
		


		# ignore the coinbase txins
		if tx_num == 0:
			continue

		for (txin_num, txin) in parsed_tx["inputs"].items():
			# are the funds split between more than one address?
			shared_funds = (len(txin["addresses"]) > 0)

			for address in txin["addresses"]:
				# don't use 0 here since txouts start counting from 0
				txout_num = None
				insert_record(
					block_height, txhash_hex, txin_num, txout_num, address,
					pubkey, shared_funds
				)
				update_record(
					block_height, txhash_hex, txin_num, txout_num, address,
					pubkey, shared_funds
					
				)
				
				cmd = "insert into transaction_addresses_and_scripts set" \
				" blockheight = %d, txhash = '%s', txin_num = %s," \
				" txout_num = %s, address = %s, pubkey = %s" \
				% (block_height, txhashi_hex, txin_num, txout_num, address, pubkey)
		# always write the txout data to the db

txhash = "ffff"
txin_num = 0
txout_num = "null"
address = '"1abc"'
pubkey = "null"
cursor.execute(command)
mysql_db.close()

#!/usr/bin/env python2.7

"""
update_addresses_db.py gets addresses from the blockchain and stores then
against the tx hash in a mysql db. using this db table you can easily look up
all txs for an address. storing information in a database is far better than
relying on bitcoin-cli's listtransactions. theoretically listtransactions should
be able to do the same thing as this database, but it currently has a bug which
prevents it from working for watch-only addresses
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

as it scans the blockchain, update_addresses_db.py encounters pubkeys. it the
derives both the compressed and uncompressed addresses from the pubkey and
stores them both against that txhash and txin/txout number. but when
update_addresses_db.py encounters an address without a pubkey (ie in a standard
txout) then only that known address is stored. without the pubkey there is no
way of knowing whether the address is compressed or uncompressed.

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

useful features of the database:

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

- search for non-standard txout scripts. do this by searching where `address`
and `alternate_address` are null, and where txin_num is null and txout_num is
not null.

- search for txin scripts which have no pubkeys. do this by searching where
`address` and `alternate_address` are null, and where txout_num is null and
txin_num is not null.

- search for multisig transactions. do this by searching on the shared_funds
field.

- find the addresses that actually received funds within a p2sh address.
"""

import MySQLdb, btc_grunt, copy, json, bitcoin as pybitcointools

with open("mysql_connection.json") as mysql_params_file:
	mysql_params = json.load(mysql_params_file)

mysql_db = MySQLdb.connect(**mysql_params)
mysql_db.autocommit(True)
cursor = mysql_db.cursor(MySQLdb.cursors.DictCursor)

cursor.execute(
	"select max(blockheight) as max_blockheight from map_addresses_to_txs"
)
max_blockheight = cursor.fetchone()["max_blockheight"]

# erase the top block if it exists (just in case it was incomplete, its easier
# to delete and rebuild than check if its complete)
if max_blockheight is not None:
	cursor.execute(
		"delete from map_addresses_to_txs where blockheight = %d"
		% max_blockheight
	)
block_height_start = (0 if max_blockheight is None else max_blockheight)

# the latest block that has been validated by btc-inquisitor
latest_validated_block_height = btc_grunt.saved_validation_data[1]

btc_grunt.connect_to_rpc()
required_txin_info = [
	"txin_hash",
	"txin_index",
	"txin_script",
	"txin_script_list",
	"txin_script_format",
	"txin_sig_pubkey_validation_status"
]
required_txout_info = [
	"txout_script",
	"txout_script_format",
	"txout_standard_script_pubkey",
	"txout_standard_script_address"
]
def main():
	"""
	loop through all transactions in the block and add them to the db.

	this is more complicated than it sounds. get the addresses and or pubkeys in
	the following order:
	1. addresses (inc p2sh) or pubkeys from standard txout scripts
	2. non-standard txout scripts (1 empty row per script)
	3. from standard txin scripts that spend standard txout scripts that have
	already been validated by btc-inquisitor.py
	4. non-standard txin scripts

	(4) often requires us to perform a checksig operation on the script to
	extract the pubkey(s). this is slow, but fortunately not extremely common
	(most checksigs are within standard scripts).
	"""
	for block_height in range(
		block_height_start, latest_validated_block_height
	):
		block_rpc_dict = btc_grunt.get_block(block_height, "json")
		for (tx_num, txhash_hex) in enumerate(block_rpc_dict["tx"]):
			tx = btc_grunt.get_transaction(txhash_hex, "bytes")

			if tx_num == 0:
				# do not fetch txin info for coinbase txs
				required_info = required_txout_info
			else:
				required_info = required_txin_info + required_txout_info

			(parsed_tx, _) = btc_grunt.tx_bin2dict(
				tx, 0, required_info, tx_num, block_height, ["rpc"]
			)
			# 1
			for (txout_num, txout) in parsed_tx["output"].items():
				txin_num = None
				# if there is a pubkey then get the corresponding addresses and
				# write these to the db
				if txout["standard_script_pubkey"] is not None:
					# standard scripts have 1 pubkey. shared_funds requires > 1
					shared_funds = False
					(uncompressed_address, compressed_address) = \
					btc_grunt.pubkey2addresses(txout["standard_script_pubkey"])
					insert_record(
						block_height, txhash_hex, txin_num, txout_num,
						uncompressed_address, compressed_address,
						txout["script_format"], shared_funds
					)
				elif txout["standard_script_address"] is not None:
					# standard scripts have 1 address. shared_funds requires > 1
					shared_funds = False
					insert_record(
						block_height, txhash_hex, txin_num, txout_num,
						txout["standard_script_address"], None,
						txout["script_format"], shared_funds
					)
				# 2. for non-standard scripts, still write a row to the table
				# but do not populate the addresses yet. this row will be
				# overwritten later if the txout ever gets spent
				elif txout["script_format"] == "non-standard":
					shared_funds = None # unknown at this stage
					insert_record(
						block_height, txhash_hex, txin_num, txout_num, None,
						None, None, shared_funds
					)
			
			# ignore the coinbase txins
			if tx_num == 0:
				continue

			# 3. this block has already been validated (guaranteed by the block
			# range) so we know that all standard txin scripts that spend
			# standard txout scripts pass checksig validation.
			for (txin_num, txin) in parsed_tx["input"].items():

				# sigpubkey format: OP_PUSHDATA0(73) <signature>
				# OP_PUSHDATA0(33/65) <pubkey>
				if txin["script_format"] == "sigpubkey":
					# sigpubkeys spend hash160 txouts (OP_DUP OP_HASH160
					# OP_PUSHDATA0(20) <hash160> OP_EQUALVERIFY OP_CHECKSIG) so
					# if the prev txout format is hash160 then insert the
					# addresses, otherwise get mysql to raise an error.
					prev_txhash_hex = btc_grunt.bin2hex(txin["hash"])
					prev_txout_num = txin["index"]
					if prev_txout_records_exist(
						prev_txhash_hex, prev_txout_num, "hash160"
					):
						shared_funds = False
						pubkey = txin["script_list"][3]
						(uncompressed_address, compressed_address) = \
						btc_grunt.pubkey2addresses(pubkey)
						txout_num = None
						insert_record(
							block_height, txhash_hex, txin_num, txout_num,
							uncompressed_address, compressed_address, None,
							shared_funds
						)
						continue # on to next txin
					else:
						# the prev txout was not in the hash160 standard format.
						# now we must validate both scripts and extract the
						# pubkeys that do validate
						pubkeys = validate()

				# scriptsig format: OP_PUSHDATA <signature>
				if txin["script_format"] == "scriptsig":
					# scriptsigs spend pubkeys (OP_PUSHDATA0(33/65) <pubkey>
					# OP_CHECKSIG) so if the prev txout format is pubkey then
					# copy these addresses over to this txin. otherwise we will
					# need to validate the scripts to get the pubkeys
					prev_txhash_hex = btc_grunt.bin2hex(txin["hash"])
					prev_txout_num = txin["index"]
					if prev_txout_records_exist(
						prev_txhash_hex, prev_txout_num, "pubkey"
					):
						copy_txout_addresses_to_txin(
							prev_txhash_hex, prev_txout_num, block_height,
							txhash_hex, txin_num
						)
						continue # on to next txin
					else:
						pubkeys = validate()

				# if we get here then we have not been able to get the pubkeys
				# from the txin script. so validate the txin and txout scripts
				# to get the pubkeys. if there is only one checksig then we will
				# skip it for speed, since btc-inquisitor has previously
				# validated this block
				pubkeys = validate()

def validate():
	"""
	get the prev txout script and validate it against the input txin script.
	return only the pubkeys that validate.
	"""
	raise Exception("validate() has not yet been defined")

# mysql functions

field_data = {
	# fieldname: [default value, quote, unhex]
	"blockheight":         [None,   False, False],
	"txhash":              [None,   False, True ],
	"txin_num":            ["null", False, False],
	"txout_num":           ["null", False, False],
	"address":             ["''",   True,  False],
	"alternate_address":   ["''",   True,  False],
	"txout_script_format": ["null", True,  False],
	"shared_funds":        ["null", False, False]
}
fieldlist = [
	"blockheight", "txhash", "txin_num", "txout_num", "address",
	"alternate_address", "txout_script_format","shared_funds"
]
fields_str = ", ".join(fieldlist)
def insert_record(
	blockheight, txhash, txin_num, txout_num, address, alternate_address,
	txout_script_format, shared_funds
):
	"""simple insert - not a unique record insert"""
	fields_dict = prepare_fields(locals())
	cmd = "insert into map_addresses_to_txs (%s) values (%s)" % (
		fields_str, get_values_str(fields_dict)
	)
	cursor.execute(cmd)

def prev_txout_records_exist(
	prev_txhash_hex, prev_txout_num, prev_txout_script_format
):
	"""does a previous txout in the specified format exist?"""
	cmd = """
	select * from map_addresses_to_txs
	where
	txhash = unhex('%s') and
	txout_num = %d and
	txout_script_format = '%s'
	""" % (prev_txhash_hex, prev_txout_num, prev_txout_script_format)

	cmd = clean_query(cmd)
	cursor.execute(cmd)
	return (cursor.rowcount > 0)

def copy_txout_addresses_to_txin(
	prev_txhash_hex, prev_txout_num, current_blockheight, current_txhash,
	txin_num
):
	# TODO - test if this will copy more than 1 record over. and do we want this?
	cmd = """
	insert into map_addresses_to_txs (%s)
	select %d, unhex('%s'), %d, null, address, alternate_address, null,
	shared_funds
	from map_addresses_to_txs
	where txhash = unhex('%s') and txout_num = %d
	""" % (
		fields_str, current_blockheight, current_txhash, txin_num,
		prev_txhash_hex, prev_txout_num
	)
	cmd = clean_query(cmd)
	cursor.execute(cmd)

def get_values_str(fields_dict):
	"""return a string of field values for use in insert values ()"""
	values_list = []
	# use the same order as fieldlist
	for field in fieldlist:
		values_list.append(fields_dict[field])

	return ", ".join(values_list)

def prepare_fields(_fields_dict):
	"""
	- translate fields with value None to their default
	- quote the necessary fields
	- convert all values to strings
	"""
	fields_dict = copy.deepcopy(_fields_dict)
	for (k, v) in fields_dict.items():

		# special case - save "non-standard" as null
		if (
			(k == "txout_script_format") and
			(v == "non-standard")
		):
			fields_dict[k] = "null"

		# special case - save "non-standard" as null
		elif k == "shared_funds":
			fields_dict[k] = 1 if v else 0

		# replace None with the default
		elif v is None:
			fields_dict[k] = field_data[k][0]

		# quote the field?
		elif field_data[k][1]:
			fields_dict[k] = "'%s'" % v

		# unhex the field?
		elif field_data[k][2]:
			fields_dict[k] = "unhex('%s')" % v

		fields_dict[k] = str(fields_dict[k])

	return fields_dict

def clean_query(cmd):
	return cmd.replace("\n", " ").replace("\t", "").strip()

# use main() so that functions defined lower down can be called earlier
main() 
mysql_db.close()

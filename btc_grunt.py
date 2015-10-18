"""
module containing some general bitcoin-related functions. whenever the word
"orphan" is used in this file it refers to orphan-block, not orphan-transaction.
orphan transactions do not exist in the blockfiles that this module processes.
"""

# TODO - switch from strings to bytearray() for speed (stackoverflow.com/q/16678363/339874)
# TODO - add . to the end of each csv line - this is a way to tell whether the
# whole line has been written or whether a ctrl+c has halted it and the line
# should be discarded
# TODO - scan for compressed/uncompressed addresses when scanning by public key or private key

# TODO - now that the block is grabbed by height, validate the block hash against
# the hash table
# TODO - use signrawtransaction to validate signatures (en.bitcoin.it/wiki/Raw_Transactions#JSON-RPC_API)
# TODO - figure out what to do if we found ourselves on a fork - particularly wrt doublespends
# TODO - validate the tx locktime/blockheight

import pprint
import copy
import binascii
import hashlib
import re
import ast
import glob
import os
import shutil
import errno
import progress_meter
import psutil
import inspect
import json
import dicttoxml
import xml.dom.minidom
import csv
import collections
import time

# install bitcoinrpc like so:
# git clone https://github.com/jgarzik/python-bitcoinrpc.git
# cd python-bitcoinrpc
# change first line of setup.py to:
#!/usr/bin/env python2.7
# chmod 755 setup.py
# sudo ./setup.py install
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException

# pybitcointools is absolutely essential - some versions of openssl will fail
# the signature validations in unit_tests/script_tests.py. this is because some
# versions of openssl require correct der encoding - see here
# http://bitcoin.stackexchange.com/q/37469/2116 - rather than trying to enforce
# a particular version of openssl (messy) i just chose an ecdsa library that
# will consistently validate bitcoin signatures. it is quite a bit slower
# unfortunately.
import bitcoin as pybitcointools

# module to do language-related stuff for this project
import lang_grunt

# module to process the user-specified btc-inquisitor options
import options_grunt

# module globals:

# rpc details. do not set here - these are updated from config.json
rpc_connection_string = None

# the rpc connection object. initialized from the config file
rpc = None

# if the result set grows beyond this then dump the saved blocks to screen
max_saved_blocks = 50

# for validation
max_block_size = 1024 * 1024 

# update these, if necessary, using the user-specified options and function
# get_range_options()
block_range_filter_lower = None
block_range_filter_upper = None

coinbase_maturity = 100 # blocks
satoshis_per_btc = 100000000
coinbase_index = 0xffffffff
int_max = 0x7fffffff
initial_bits = "1d00ffff" # gets converted to bin in sanitize_globals() asap
max_script_size = 10000 # bytes (bitcoin/src/script/interpreter.cpp)
max_script_element_size = 520 # bytes (bitcoin/src/script/script.h)
max_op_count = 200 # nOpCount in bitcoin/src/script/interpreter.cpp
locktime_threshold = 500000000 # tue nov 5 00:53:20 1985 
max_sequence_num = 0xffffffff

# address symbols. from https://en.bitcoin.it/wiki/List_of_address_prefixes
version_symbol = {
	"pub_key_hash": {"magic": 0, "prefix": "1"},
	"script_hash": {"magic": 5, "prefix": "3"},
	"compact_pub_key": {"magic": 21, "prefix": "4"},
	"namecoin_pub_key_hash": {"magic": 52, "prefix": "M"},
	"private_key": {"magic": 128, "prefix": "5"},
	"testnet_pub_key_hash": {"magic": 111, "prefix": "n"},
	"testnet_script_hash": {"magic": 196, "prefix": "2"}
}
base_dir = None # init
tx_metadata_dir = None # init
# TODO - mark all validation data as True for blocks we have already passed

# format is hash, height, prev hash
saved_validation_file = "@@base_dir@@/latest-validated-block.txt"
saved_validation_data = None # gets initialized asap in the following code.

# block hashes of known orphans (one per line in hex)
known_orphans_file = "@@base_dir@@/known-orphans.txt"
saved_known_orphans = None # gets initialized asap in the following code.

aux_blockchain_data = None # gets initialized asap in the following code
tx_metadata_keynames = [
	# the end of the tx hash as a hex string (the start is in the file name)
	"tx_hash",

	# last 2 bytes of the block hash - tx num. this is necessary so we can
	# distinguish between transactions with identical hashes.
	"blockhashend_txnum",

	"blockfile_num", # int (deprecated - set to empty string)
	"block_start_pos", # int (deprecated - set to empty string)
	"tx_start_pos", # int (deprecated - set to empty string)
	"tx_size", # int (deprecated - set to empty string)
	"block_height", # int (deprecated - set to empty string)
	"is_coinbase", # 1 = True, None = False
	"is_orphan", # 1 = True, None = False (deprecated - set to empty string)
	"spending_txs_list" # "[spendee_hash-spendee_index, ...]"
]
block_header_info = [
	"orphan_status",
	"block_height",
	"block_hash",
	"format_version",
	"previous_block_hash",
	"merkle_root",
	"timestamp",
	"bits",
	"target",
	"difficulty",
	"nonce",
	"block_size",
	#"block_bytes"
]
block_header_validation_info = [
	# do the transaction hashes form the merkle root specified in the header?
	"merkle_root_validation_status",

	# do the previous bits and time to mine 2016 blocks produce these bits?
	"bits_validation_status",

	# is the difficulty > 1?
	"difficulty_validation_status",

	# is the block hash below the target?
	"block_hash_validation_status",

	# is the block size less than the permitted maximum?
	"block_size_validation_status"
]
all_txin_info = [
	"prev_txs_metadata",
	"prev_txs",
	"txin_funds",
	"txin_coinbase_change_funds",
	"txin_hash",
	"txin_index",
	"txin_script_length",
	"txin_script",
	"txin_script_list",
	"txin_parsed_script",
	"txin_addresses",
	"txin_sequence_num"
]
all_txout_info = [
	"txout_funds",
	"txout_script_length",
	"txout_script",
	"txout_script_list",
	"txout_addresses",
	"txout_parsed_script"
]
remaining_tx_info = [
	#"tx_pos_in_block",
	"num_txs",
	"tx_version",
	"num_tx_inputs",
	"num_tx_outputs",
	"tx_lock_time",
	"tx_timestamp",
	"tx_hash",
	"tx_bytes",
	"tx_size"
]
all_tx_validation_info = [
	"tx_lock_time_validation_status",
	"txin_coinbase_hash_validation_status",
	"txin_hash_validation_status",
	"txin_coinbase_index_validation_status",
	"txin_index_validation_status",
	"txin_single_spend_validation_status",
	"txin_spend_from_non_orphan_validation_status",
	"txin_script_format_validation_status", # TODO - implement this - checks for pushdata
	"txout_address_checksums",
	"txin_checksig_validation_status",
	"txin_mature_coinbase_spend_validation_status",
	"txout_script_format_validation_status",
	"txins_exist_validation_status",
	"txouts_exist_validation_status",
	"tx_funds_balance_validation_status"
]
# info without validation
all_tx_info = all_txin_info + all_txout_info + remaining_tx_info
all_block_info = block_header_info + all_tx_info

# info with validation
all_tx_and_validation_info = all_tx_info + all_tx_validation_info

all_block_header_and_validation_info = block_header_info + \
block_header_validation_info

all_block_and_validation_info = all_block_header_and_validation_info + \
all_tx_and_validation_info

# validation info only
all_validation_info = block_header_validation_info + all_tx_validation_info

config_file = "config.json"
def import_config():
	"""
	this function is run automatically whenever this module is imported - see
	the final lines in this file
	"""
	global base_dir, tx_metadata_dir, rpc_connection_string

	if not os.path.isfile(config_file):
		# the config file is not mandatory since there are uses of this script
		# which do not involve reading the blockchain or writing outputs to file
		return	

	try:
		with open(config_file, "r") as f:
			config_json = f.read()
	except:
		raise IOError("config file %s is inaccessible" % config_file)

	try:
		config_dict = json.loads(config_json)
	except Exception, error_string:
		raise IOError(
			"config file %s contains malformed json, which could not be parsed:"
			" %s.%serror details: %s"
			% (config_file, config_json, os.linesep, error_string)
		)
	if "base_dir" in config_dict:
		base_dir = os.path.join(os.path.expanduser(config_dict["base_dir"]), "")

	if "rpc_user" in config_dict:
		rpc_user = config_dict["rpc_user"]

	if "rpc_password" in config_dict:
		rpc_password = config_dict["rpc_password"]

	if "rpc_host" in config_dict:
		rpc_host = config_dict["rpc_host"]

	if "rpc_port" in config_dict:
		rpc_port = config_dict["rpc_port"]

	rpc_connection_string = "http://%s:%s@%s:%d" % (
		rpc_user, rpc_password, rpc_host, rpc_port
	)
	if "tx_metadata_dir" in config_dict:
		tx_metadata_dir = os.path.join(
			substitute_base_dir(
				os.path.expanduser(config_dict["tx_metadata_dir"])
			), ""
		)

def substitute_base_dir(path):
	"""string substitution: @@base_dir@@ -> base_dir"""
	global base_dir
	if "@@base_dir@@" in path:
		try:
			path = path.replace("@@base_dir@@", base_dir)
		except:
			raise Exception(
				"failed to add base directory %s to tx metadata directory %s"
				% (base_dir, path)
			)
	# normpath converts // to / but also removes any trailing slashes
	return os.path.normpath(path)

def sanitize_globals():
	"""
	this function is run automatically whenever this module is imported - see
	the final lines in this file
	"""
	global base_dir, tx_metadata_dir, blank_hash, initial_bits, \
	saved_validation_data, saved_validation_file, aux_blockchain_data, \
	known_orphans_file, saved_known_orphans

	if base_dir is not None:
		if not os.path.isdir(base_dir):
			raise IOError("cannot access base directory %s" % base_dir)

	if tx_metadata_dir is not None:
		if not os.path.isdir(tx_metadata_dir):
			raise IOError(
				"cannot access the transaction metadata directory %s"
				% tx_metadata_dir
			)
	blank_hash = hex2bin("0" * 64)
	initial_bits = hex2bin(initial_bits)
	saved_validation_file = substitute_base_dir(saved_validation_file)
	saved_validation_data = get_saved_validation_data()
	#aux_blockchain_data = get_aux_blockchain_data()
	known_orphans_file = substitute_base_dir(known_orphans_file)
	saved_known_orphans = get_saved_known_orphans()

def enforce_sanitization(inputs_have_been_sanitized):
	previous_function = inspect.stack()[1][3] # [0][3] would be this func name
	if not inputs_have_been_sanitized:
		raise Exception(
			"you must sanitize the input options with function"
			" sanitize_options_or_die() before passing them to function %s()."
			% previous_function
		)

def ensure_correct_bitcoind_version():
	"""make sure all the bitcoind methods used in this program are available"""
	version = get_info()["version"]
	if version < 70000:
		raise ValueError(
			"you are running bitcoind version %s. however this script requires"
			" at least version 0.7. please upgrade bitcoind"
			% bitcoind_version2human_str(version)
		)

def init_base_dir():
	"""
	if the base dir does not exist then attempt to create it. also create the
	necessary subdirectories and their readme files for this script. die if this
	fails.
	"""
	if not os.path.exists(base_dir):
		os.makedirs(base_dir)

	if not os.path.exists(tx_metadata_dir):
		os.makedirs(tx_metadata_dir)

	readme_file = os.path.join(base_dir, "README")
	try:
		if not os.path.exists(readme_file):
			with open(readme_file, "w") as f:
				f.write(
					"this directory contains the following metadata for the"
					" btc-inquisitor script:%s- tx_metadata dir - data to"
					" locate transactions in the blockchain. the directory"
					" makes up the hash of each transaction and the text file"
					" located within the final dir contains the blockfile"
					" number, the position of the start of the block (including"
					" magic network id), the position of the start of the"
					" transaction within this block, the size of the"
					" transaction, the height of the block this transaction is"
					" in, the orphan status of the block, the transaction"
					" outputs that have been spent and the hashes indexes of"
					" the transactions that have spent these hashes. for"
					" example, file ~/.bit-inquisitor/tx_metadata/ab/cd/ef.txt"
					" corresponds to transaction with hash abcdef (obviously"
					" not a real hash). and if it has content"
					" 7,1000,180,200,60000,orphan,[0123-0,4567-5,] then this"
					" transaction exists in blockfile blk00007.dat, 1000 bytes"
					" into the file, the transaction starts 180 bytes into this"
					" block and has a length of 200 bytes. the block that the"
					" transaction exists in has height 60,000 (where 0 is the"
					" genesis block), it is an orphan transaction. the first"
					" output of this transaction has already been spent by"
					" index 0 of a transaction starting with hash 0123, and the"
					" second output of this transaction has already been spent"
					" by index 5 of a transaction starting with hash 4567. the"
					" third output has not yet been spent.%sthe transaction"
					" metadata in these files is used to perform checksigs in"
					" the blockchain for validations, and the spending data is"
					" used to check for doublespends. the block height is used"
					" to ensure that a coinbase transaction has reached"
					" maturity before being spent."
					% ((os.linesep * 2), os.linesep)
				)
	except:
		raise IOError("failed to create readme file")

def init_orphan_list():
	"""
	we only know if a block is an orphan by waiting coinbase_maturity blocks
	then looking back and identifying blocks which are not on the main-chain.
	so save all blocks then analyse previous coinbase_maturity blocks every
	coinbase_maturity blocks and update the list of orphan hashes
	"""
	orphans = [] # list of hashes
	return orphans

def validate_blockchain(options, sanitized = False):
	"""
	validate the blockchain beginning at the genesis block. this function is
	called whenever the user invokes the -v/--validate flag.

	validation creates a (huge) database of spent txs on disk and checks block
	heights against block hashes in bitcoind.

	no data is returned as part of this function - exit silently upon success
	and raise an error upon fail.

	the user will almost certainly want to use the progress meter flag
	-p/--progress in conjunction with validation as it will take a very long
	time (weeks) to validate the blockchain from start to finish.

	a dict of block heights and hashes (hash_table) is built up and used to
	detect orphans in this function. any transactions for these orphan blocks
	are marked as "is_orphan" in the previous tx data in the parsed block.
	attempting to spend a transaction from these orphan blocks results in a
	failed validation and function enforce_valid_block() will raise an exception
	"""
	# mimic the behaviour of the original bitcoin source code when performing
	# validations. this means validating certain buggy transactions without
	# dying. search 'bugs_and_all' in this file to see where this is necessary.
	bugs_and_all = True

	# make sure the user input data has been sanitized
	enforce_sanitization(sanitized)

	# initialize the hash table from where we left off validating last time.
	# {current hash: [current block height, previous hash], ...}
	hash_table = init_hash_table()

	# get the block height to start validating from. begin 1 after the latest
	# block in the hash table, since all hash table blocks have already been
	# validated.
	block_height = truncate_hash_table(hash_table, 1).values()[0][0] + 1

	# get the very latest block height in the blockchain
	latest_block = get_info()["blocks"]

	# init the bits for the previous (already validated) block
	if block_height == 0:
		block_1_ago = {"bits": None, "timestamp": None}
	else:
		temp = get_block(block_height - 1, "json")
		block_1_ago = {"bits": hex2bin(temp["bits"]), "timestamp": temp["time"]}

	def prog(action):
		"""quick function to update progress meter"""
		if options.progress:
			progress_meter.render(
				100 * block_height / float(latest_block),
				"%s block %d of %d" % (action, block_height, latest_block)
			)
	while True:
		# if we have already validated the whole user-defined range then exit
		# here note that block_height is the latest validated block height
		if block_height >= block_range_filter_upper:
			# TODO - test this
			return True

		# get the block from bitcoind
		prog("fetching")
		block_bytes = get_block(block_height, "bytes")

		# parse the block and initialize the validation elements to None
		prog("parsing")
		parsed_block = block_bin2dict(
			block_bytes, block_height, all_block_and_validation_info,
			options.explain
		)
		# die if this block has no ancestor in the hash table
		enforce_ancestor(hash_table, parsed_block["previous_block_hash"])

		save_tx_metadata(parsed_block)

		# update the hash table (contains orphan and main-chain blocks)
		hash_table[parsed_block["block_hash"]] = [
			parsed_block["block_height"], parsed_block["previous_block_hash"]
		]
		# if there are any orphans in the hash table then save them to disk and
		# also to the saved_known_orphans var
		save_new_orphans(hash_table, parsed_block["block_hash"])

		# truncate the hash table so as not to use up too much ram
		if len(hash_table) > (2 * coinbase_maturity):
			hash_table = truncate_hash_table(hash_table, coinbase_maturity)

		# update the validation elements of the parsed block
		prog("validating")
		parsed_block = validate_block(
			parsed_block, block_1_ago, bugs_and_all, options.explain
		)
		# die if the block failed validation
		enforce_valid_block(parsed_block, options)

		# mark off all the txs that this validated block spends
		prog("spending txs from")
		mark_spent_txs(parsed_block)

		# if this block height has not been saved before, or if it has been
		# saved but has now changed, then back it up to disk. it is important to
		# leave this until after validation, otherwise an invalid block height
		# will be written to disk as if it were valid. we back-up to disk in
		# case an error is encountered later (which would prevent this backup
		# from occuring and then we would need to start parsing from the
		# beginning again)
		save_latest_validated_block(
			bin2hex(parsed_block["block_hash"]), parsed_block["block_height"],
			bin2hex(parsed_block["previous_block_hash"])
		)
		# update vars for the next loop...
		# update the bits data for the next loop
		(block_1_ago["bits"], block_1_ago["timestamp"]) = (
			parsed_block["bits"], parsed_block["timestamp"]
		)
		# get the very latest block height in the blockchain to keep the
		# progress meter accurate
		latest_block = get_info()["blocks"]
		block_height += 1

	# terminate the progress meter if we are using one
	if options.progress:
		progress_meter.done()

	# TODO - necessary?
	save_new_orphans(hash_table, parsed_block["block_hash"])

def extract_data(options, sanitized = False):
	"""
	extract data from the blockchain. no validation is performed in this
	function, however btc-inquisitor.py will not call this function unless the
	range of blocks specified by the user has already been validated (dates are
	matched to block heights using bitcoind, then these heights are compared to
	the latest-validation data).
	"""
	pass

def main_loop(options, sanitized = False):
	"""
	get full blocks which contain the specified addresses, transaction hashes or
	block hashes, or validate the blockchain.
	"""
	# mimic the behaviour of the original bitcoin source code when performing
	# validations and extracting addresses. this means validating certain buggy
	# transactions without dying. search 'bugs_and_all' in this file to see
	# where this is necessary.
	bugs_and_all = True

	# make sure the user input data has been sanitized
	enforce_sanitization(sanitized)

	# only needed so that python does not create this as a different local var
	global aux_blockchain_data

	# TODO - determine if this is needed
	# if this is the first pass of the blockchain then we will be looking
	# coinbase_maturity blocks beyond the user-specified range so as to check
	# for orphans. once his has been done, it does not need doing again
	# seek_orphans = True if (pass_num == 1) else False

	filtered_blocks = {} # init. this is the only returned var
	orphans = init_orphan_list() # list of hashes
	exit_now = False # init
	# initialize the hash table (gives the previous block hash, from which we
	# derive the current height), get a list of blockfile numbers to loop
	# through, and the start position within the first file.
	(
		hash_table, block_file_nums, earliest_start_pos, full_blockchain_bytes,
		progress_bytes, block_height
	) = init_some_loop_vars(options, aux_blockchain_data)

	# initialize the progress meter to a percentage of all blockchain files. do
	# not specify the block height, as it is not known since we have not yet
	# parsed any blocks from the blockchain.
	if options.progress:
		progress_meter.render(
			100 * progress_bytes / float(full_blockchain_bytes),
			"block %s" % block_height
		)
	for block_file_num in block_file_nums:
		block_filename = blockfile_num2name(block_file_num)
		active_file_size = os.path.getsize(block_filename)

		if earliest_start_pos is None:
			bytes_into_file = 0 # reset
		else:
			bytes_into_file = earliest_start_pos
			earliest_start_pos = None # reset for next loop

		bytes_into_section = 0 # reset
		active_blockchain = "" # init
		fetch_more_blocks = True # TODO - test and clarify doco for this var
		file_handle = open(block_filename, "rb")

		# loop within the same block file
		while True:
			# either extract block data or move on to the next blockchain file
			(fetch_more_blocks, active_blockchain, bytes_into_section) = \
			maybe_fetch_more_blocks(
				file_handle, fetch_more_blocks, active_blockchain,
				bytes_into_section, bytes_into_file, active_blockchain_num_bytes
			)
			# if we have already extracted all blocks from this file
			if not len(active_blockchain):
				break # move on to next file

			# if this block is incomplete
			if incomplete_block(
				active_blockchain, num_block_bytes, bytes_into_section
			):
				fetch_more_blocks = True
				continue # get the next block in this file

			# block as bytes
			block = active_blockchain[bytes_into_section + 8: \
			bytes_into_section + num_block_bytes + 8]

			# update position counters
			block_pos = bytes_into_file 
			bytes_into_section += num_block_bytes + 8
			bytes_into_file += num_block_bytes + 8

			# if we have already saved the txhash locations in this block then
			# get as little block data as possible, otherwise parse all data and
			# save it to disk. also get the block height within this function.
			# note that txin addresses are never validated at this point, and
			# multisig addresses are set to None (they must be updated later if
			# required)
			parsed_block = minimal_block_parse_maybe_save_txs(
				block, latest_validated_block_data,
				block_file_num, block_pos, hash_table, options
			)
			# update the block height - needed only for error notifications
			block_height = parsed_block["block_height"]

			# if we are using a progress meter then update it
			progress_bytes = maybe_update_progress_meter(
				options, num_block_bytes, progress_bytes,
				parsed_block["block_height"], full_blockchain_bytes
			)
			# update the hash table (contains orphan and main-chain blocks)
			hash_table[parsed_block["block_hash"]] = [
				parsed_block["block_height"],
				parsed_block["previous_block_hash"]
			]
			# maybe mark off orphans in the parsed blocks and truncate hash
			# table, but only if the hash table is twice the allowed length
			(filtered_blocks, hash_table, aux_blockchain_data) = manage_orphans(
				filtered_blocks, hash_table, parsed_block, aux_blockchain_data,
				2
			)
			# convert hash or limit ranges to blocknum ranges
			# this has changed - options = options_grunt.get_range_options(options, parsed_block)

			# get the aux blockchain data for the current block so that we can
			# validate the bits data. if this block height has not been saved
			# before (ie it is not an index in the aux_blockchain_data dict), or
			# if it has been saved but has now changed, then update the dict but
			# do not back it up to disk just yet - it is important to leave the
			# disk-save until after validation - otherwise an invalid block
			# height will be written to disk as if it were valid.
			(should_save_aux_blockchain_data, aux_blockchain_data) = \
			maybe_update_aux_blockchain_data(parsed_block, aux_blockchain_data)

			# if the block requires validation and we have not yet validated it
			# then do so now (we must validate all blocks from the start, but
			# only if they have not been validated before).
			if should_validate_block(
				options, parsed_block, latest_validated_block_data
			):
				parsed_block = validate_block(
					parsed_block, aux_blockchain_data, bugs_and_all, options
				)
			# if we did not need to validate the block we may still need to get
			# non-standard (eg multisig) addresses by validating scripts
			elif should_get_non_standard_script_addresses(
				options, parsed_block
			):
				parsed_block = parse_non_standard_script_addresses(
					parsed_block, bugs_and_all, options
				)
			# if this block height has not been saved before, or if it has been
			# saved but has now changed, then back it up to disk. it is
			# important to leave this until after validation, otherwise an
			# invalid block height will be written to disk as if it were valid.
			# we back-up to disk in case an error is encountered later (which
			# would prevent this backup from occuring and then we would need to
			# start parsing from the beginning again)
			if should_save_aux_blockchain_data:
				save_aux_blockchain_data(aux_blockchain_data)

			in_range = False # init

			# return if we are beyond the specified range + coinbase_maturity
			if after_range(parsed_block["block_height"], True):
				exit_now = True # since "break 2" is not possible in python
				break

			# skip the block if we are past the user specified range. note that
			# the only reason to be here is to see if any of the blocks in the
			# range are orphans
			if after_range(parsed_block["block_height"]):
				continue

			# skip the block if we are not yet in range
			if before_range(parsed_block["block_height"]):
				continue

			# be explicit. simplifies processing in the following functions
			in_range = True

			# so far we have not parsed any tx data. if the options specify this
			# block (eg an address that is in this block, or a tx hash that is
			# in this block) then get all tx data. do this after the range
			# checks since there is no need to look for relevant addresses or
			# txhashes outside the range
			# TODO - prevent this from overwriting validation data. is this
			# stage even necessary?
			parsed_block = manage_update_relevant_block(
				options, in_range, parsed_block
			)
			# if the options do not specify this block then quickly move on to
			# the next one
			if parsed_block is None:
				continue

			# if a user-specified address is found in a txout, then save the
			# hash of this whole transaction and save the index where the
			# address is found in the format {hash: [index, index]}. this data
			# will then be used later to search for txins that reference these
			# txouts. this is the only way to find a txin address
			options.TXINHASHES = address2txin_data(options, parsed_block)

			# if the options specify that this block is to be displayed to the
			# user then either do so immediately, or save so that we can do so
			# later
			filtered_blocks = print_or_return_blocks(
				filtered_blocks, parsed_block, options, max_saved_blocks
			)
		file_handle.close()
		if exit_now:
			break

	# terminate the progress meter if we are using one
	maybe_finalize_progress_meter(
		options, progress_meter, parsed_block["block_height"]
	)
	# mark off any known orphans. the above loop does this too, but only checks
	# every 2 * coinbase_maturity (for efficiency). if we do not do this here
	# then we might miss orphans within the last [coinbase_maturity,
	# 2 * coinbase_maturity] blocks
	(filtered_blocks, hash_table, aux_blockchain_data) = manage_orphans(
		filtered_blocks, hash_table, parsed_block, aux_blockchain_data, 1
	)
	# save the latest validated block
	if options.validate:
		save_latest_validated_block(parsed_block)

	return filtered_blocks

def init_hash_table(block_data = None):
	"""
	construct the hash table that is needed to begin validating the blockchain
	from the position specified by the user. the hash table must begin 1 block
	before the range we begin parsing at and is in the format:

	{current hash: [current block height, previous hash], ...}

	if block_data is not specified then init the hash table from file. if it is
	specified then also update the hash table from this block data.
	"""
	hash_table = {blank_hash: [-1, blank_hash]} # init
	if saved_validation_data is not None:
		(
			saved_validated_block_hash, saved_validated_block_height,
			saved_previous_validated_block_hash
		) = saved_validation_data

		hash_table[saved_validated_block_hash] = [
			saved_validated_block_height, saved_previous_validated_block_hash
		]
	if block_data is not None:
		hash_table[block_data["block_hash"]] = [
			block_data["block_height"], block_data["previous_block_hash"]
		]
	return hash_table

def backup_hash_table(hash_table, latest_block_hash):
	"""
	save the last entry of the hash table to disk. the "block height" in the
	hash table is the latest validated block.

	no need to check if this block is an orphan (this will be inevitable
	sometimes anyway). if we end up saving an orphan then we will just go back
	coinbase_maturity blocks to restart the hash table from there.
	"""
	try:
		with open(hash_table_file, "w") as f:
			f.write(
				"%s,%s,%s." % (
					latest_block_hash, hash_table[latest_block_hash][0],
					hash_table[latest_block_hash][1]
				)
			)
	except:
		raise IOError(
			"failed to save the hash table to file %s" % hash_table_file
		)

def init_some_loop_vars(options, aux_blockchain_data):
	"""
	get the data that is needed to begin parsing the blockchain from the
	position specified by the user. we will also construct the hash table - this
	must begin 1 block before the range we begin parsing at. the hash table is
	in the format

	{current hash: [current block height, previous hash], ...}

	however, we only need to populate it with the previous hash and previous
	block height.

	aux_blockchain_data is in the format:
	{block-height: {block-hash0: {
		"filenum": 0, "start_pos": 999, "size": 285, "timestamp": x, "bits": x,
		"is_orphan": True
	}}}
	"timestamp" and "bits" are only defined every 2016 blocks or 2016 - 1, but
	"filenum", "start_pos", "size" and "orphan" are always defined.

	if the aux_blockchain_data does not go upto the start of the user-specified
	range, then begin at the closest possible block below.
	"""

	hash_table = {blank_hash: [-1, blank_hash]} # init
	block_file_nums = [
		blockfile_name2num(block_file_name) for block_file_name in \
		sorted(glob.glob(os.path.join(blockchain_dir, blockname_ls)))
	]
	closest_start_pos = None # init
	# get the total size of the blockchain
	bytes_past = 0 # init
	closest_block_height = 0 # init

	# if the user has specified a range that starts from block 0, or a range
	# that is less than both the first 2-weekly milestone block (block 2015) and
	# less than the first aux_blockchain_data_backup_freq block then the closest
	# block is block 0, so exit here
	if (
		(options.STARTBLOCKNUM in [None, 0]) or (
			(options.STARTBLOCKNUM < aux_blockchain_data_backup_freq) and
			(options.STARTBLOCKNUM < 2015)
		)
	):
		return (
			hash_table, block_file_nums, closest_start_pos,
			full_blockchain_bytes, bytes_past, closest_block_height
		)
	# find the single closest block height from the block heights file
	try:
		for closest_block_height in sorted(aux_blockchain_data, reverse = True):
			if (closest_block_height < options.STARTBLOCKNUM):
				break
	except IndexError:
		# if the block heights file has no relevant data then just return
		# block 0 (blank hash) and the default other values
		return (
			hash_table, block_file_nums, closest_start_pos,
			full_blockchain_bytes, bytes_past, closest_block_height
		)
	# get all block hashes for this closest backed-up block
	for block_hash in aux_blockchain_data[closest_block_height]:
		hash_table[block_hash] = [closest_block_height, blank_hash]

	# find the closest backed-up blockfile number
	closest_blockfile_num = min(
		d["filenum"] for d in aux_blockchain_data[closest_block_height].values()
	)
	# find the closest backed-up start position. we start parsing the
	# blockchain one block after the closest_block_height. thus we know the
	# previous block hash's height.
	closest_start_pos = min(
		8 + d["start_pos"] + d["size"] for d in \
		aux_blockchain_data[closest_block_height].values() \
		if (d["filenum"] == closest_blockfile_num)
	)
	return (
		hash_table, block_file_nums, closest_start_pos, full_blockchain_bytes,
		bytes_past, closest_block_height
	)

"""
def extract_tx(options, txhash, tx_metadata):
	" ""given tx position data, fetch the tx data from the blockchain files"" "

	with open(blockfile_num2name(tx_metadata["blockfile_num"]), "rb") as f:
		f.seek(tx_metadata["block_start_pos"], 0)

		# 8 = 4 bytes for the magic network id + 4 bytes for the block size
		num_bytes = 8 + tx_metadata["tx_start_pos"] + tx_metadata["tx_size"]

		partial_block_bytes = f.read(num_bytes)

	tx_bytes = partial_block_bytes[8 + tx_metadata["tx_start_pos"]:]
	return tx_bytes
"""
"""
def maybe_update_progress_meter(
	options, num_block_bytes, progress_bytes, block_height,
	full_blockchain_bytes
):
	"" "
	if a progress meter is specified then update it with the number of bytes
	through the entire blockchain
	"" "
	if options.progress:
		progress_bytes += num_block_bytes + 8
		progress_meter.render(
			100 * progress_bytes / float(full_blockchain_bytes),
			"block %s" % block_height
		)
	return progress_bytes
"""

def maybe_finalize_progress_meter(options, progress_meter, block_height):
	"""if a progress meter is specified then set it to 100%"""

def print_or_return_blocks(
	filtered_blocks, parsed_block, options, max_saved_blocks
):
	"""
	if the filtered_blocks dict is bigger than max_saved_blocks then output the
	data now. this must be done otherwise we will run out of memory.

	if the filtered_blocks dict is not bigger than max_saved_blocks then just
	append the latest block to the filtered_blocks dict and return the whole
	dict.

	if the user has not specified any output data (probably just doing a
	validation) then don't update the filtered_blocks dict.
	"""
	if options.OUTPUT_TYPE is None:
		return filtered_blocks

	filtered_blocks[parsed_block["block_hash"]] = parsed_block

	# if there is too much data to save in memory then print it now
	if len(filtered_blocks) > max_saved_blocks:
		# first filter out the data that has been specified by the options
		data = final_results_filter(filtered_blocks, options)
		print get_formatted_data(options, data)

		# clear filtered_blocks to prevent memory from growing
		filtered_blocks = {}
		return filtered_blocks

	# if there is not too much data to save in memory then just return it
	return filtered_blocks

"""
def extract_txs(binary_blocks, options):
	"" "
	return only the relevant transactions. no progress meter here as this stage
	should be very quick even for thousands of transactions
	"" "

	filtered_txs = []
	for (block_height, block) in binary_blocks.items():

		if isinstance(block, dict):
			parsed_block = block
		else:
			parsed_block = block_bin2dict(
				block, ["tx_hash", "tx_bytes", "txin_address", "txout_address"]
			)

		for tx_num in sorted(parsed_block["tx"]):

			break_now = False # reset
			if (
				(options.TXHASHES is not None) and
				parsed_block["tx"][tx_num]["hash"] in options.TXHASHES
			):
				filtered_txs.append(parsed_block["tx"][tx_num])
				continue # on to next tx

			if parsed_block["tx"][tx_num]["input"] is not None:
				for input_num in parsed_block["tx"][tx_num]["input"]:
					if (
						(parsed_block["tx"][tx_num]["input"][input_num] \
						["address"] is not None) and
						(options.ADDRESSES is not None) and
						(parsed_block["tx"][tx_num]["input"][input_num] \
						["address"] in options.ADDRESSES)
					):
						filtered_txs.append(parsed_block["tx"][tx_num])
						break_now = True
						break # to next txin

				if break_now:
					continue # to next tx_num

			if parsed_block["tx"][tx_num]["output"] is not None:
				for output_num in parsed_block["tx"][tx_num]["output"]:
					if (
						(parsed_block["tx"][tx_num]["output"][output_num] \
						["address"] is not None) and
						(options.ADDRESSES is not None) and
						(parsed_block["tx"][tx_num]["output"][output_num] \
						["address"] in options.ADDRESSES)
					):
						filtered_txs.append(parsed_block["tx"][tx_num])
						break_now = True
						break # to next txout

				if break_now:
					continue # to next tx_num

	return filtered_txs
"""

def save_latest_validated_block(
	latest_validated_block_hash, latest_validated_block_height,
	previous_validated_block_hash
):
	"""
	save to disk the latest block that has been validated. overwrite file if it
	exists. the file format is:
	latest validated block hash, latest validated block height, previously
	validated hash
	"""
	# do not overwrite a later value with an earlier value
	if saved_validation_data is not None:
		(
			saved_validated_block_hash, saved_validated_block_height,
			saved_previous_validated_block_hash
		) = saved_validation_data # global

		if latest_validated_block_height <= saved_validated_block_height:
			return

	# from here on we know that the latest validated block is beyond where we
	# were upto before.

	# backup the file in case the write fails (copy2 preserves file metadata)
	shutil.copy2(
		saved_validation_file, "%s.backup.%s" % (
			saved_validation_file, time.strftime("%Y-%m-%d-%H-%M-%S")
		)
	)
	# the old validation point is now safely backed-up :)

	# now update the latest-saved-tx file
	with open(saved_validation_file, "w") as f:
		f.write(
			"%s,%d,%s." % (
				latest_validated_block_hash, latest_validated_block_height,
				previous_validated_block_hash
			)
		)

def get_aux_blockchain_data():
	"""
	retrieve the aux blockchain data from disk. this data is useful as it means
	we don't have to parse the blockchain from the start each time.

	this data is used to reconstruct the hash table from which the block height
	is determined, and also to reconstruct the bits (difficulty) data for
	validation.

	aux_blockchain_data is in the format:
	{block-height: {block-hash0: {
		"filenum": 0, "start_pos": 999, "size": 285, "timestamp": x, "bits": x,
		"is_orphan": True
	}}}
	"timestamp" and "bits" are only defined every 2016 blocks or 2016 - 1, but
	"filenum", "start_pos", "size" and "is_orphan" are always defined.
	"""
	data = {}
	try:
		with open(os.path.join(base_dir, "aux-blockchain-data.csv"), "r") as f:
			handle = csv.reader(f, delimiter = ",")
			for line in handle:
				block_height = int(line[0])
				if block_height not in data:
					data[block_height] = {}

				block_hash = hex2bin(line[1])
				if block_hash not in data[block_height]:
					data[block_height][block_hash] = {}

				data[block_height][block_hash] = {
					"filenum": int(line[2]),
					"start_pos": int(line[3]),
					"size": int(line[4]) if len(line[4]) else None,
					"timestamp": int(line[5]) if len(line[5]) else None,
					"bits": hex2bin(line[6]) if len(line[6]) else None,
					"is_orphan": True if len(line[7]) else None
				}
			# file gets automatically closed
	except:
		# the file cannot be opened - it probably doesn't exist yet
		pass

	return data

def save_aux_blockchain_data(aux_blockchain_data):
	"""
	save the block height data to disk. overwrite existing file if it exists.

	aux_blockchain_data is in the format:
	{block-height: {block-hash0: {
		"filenum": 0, "start_pos": 999, "size": 285, "timestamp": x, "bits": x,
		"is_orphan": True
	}}}
	"timestamp" and "bits" are only defined every 2016 blocks or 2016 - 1, but
	"filenum", "start_pos", "size" and "is_orphan" are always defined.
	"""
	with open(os.path.join(base_dir, "aux-blockchain-data.csv"), "w") as f:
		for block_height in sorted(aux_blockchain_data):
			for (block_hash, d) in aux_blockchain_data[block_height].items():
				size = "" if (d["size"] is None) else d["size"]
				timestamp = "" if (d["timestamp"] is None) else d["timestamp"]
				bits = "" if (d["bits"] is None) else bin2hex(d["bits"])
				is_orphan = "" if (d["is_orphan"] is None) else 1
				f.write(
					"%s,%s,%s,%s,%s,%s,%s,%s%s" % (
						block_height, bin2hex(block_hash), d["filenum"],
						d["start_pos"], size, timestamp, bits, is_orphan,
						os.linesep
					)
				)

def get_saved_validation_data():
	"""
	retrieve the saved validation data. this enables us to avoid re-validating
	blocks that have already been validated in the past. the file format is:
	saved validated hash,corresponding height,previous validated hash.

	note the full-stop at the end - this is vital as it ensures that the entire
	file has been written correctly in the past, and not terminated half way
	through a write.
	"""
	try:
		with open(saved_validation_file, "r") as f:
			file_data = f.read().strip()

		file_exists = True
	except:
		# the file cannot be opened
		file_exists = False
		saved_validation_data = None

	if file_exists:
		if file_data[-1] != ".":
			raise IOError(
				"the validation data was not previously backed up to disk"
				" correctly. it should end with a full stop, however one was"
				" not found. this implies that the file-write was interrupted."
				" please attempt manual reconstruction of the file."
			)
		else:
			file_data = file_data[: -1]
			saved_validation_data = file_data.split(",")
			saved_validation_data[0] = hex2bin(saved_validation_data[0])
			saved_validation_data[1] = int(saved_validation_data[1])
			saved_validation_data[2] = hex2bin(saved_validation_data[2])

	return saved_validation_data

def save_validation_data():
	# TODO
	pass

def get_saved_known_orphans():
	"""
	retrieve the saved orphan data. this is necessary because validation now
	happens seperately to block retrieval, and we need to know if a block is an
	orphan when retrieving it via rpc.

	the file format is "block height, block hash" per line. note the full-stop
	on the final line - this is vital as it ensures that the entire file has
	been written correctly in the past, and not terminated half way through a
	write.
	"""
	try:
		with open(known_orphans_file, "r") as f:
			file_data = f.readlines()

		file_exists = True
	except:
		# the file cannot be opened
		file_exists = False
		saved_known_orphans = None

	if file_exists:
		if file_data[-1].strip() != ".":
			raise IOError(
				"the validation data was not previously backed up to disk"
				" correctly. it should end with a full stop, however one was"
				" not found. this implies that the file-write was interrupted."
				" please restore from one of the %s backup files."
				% known_orphans_file
			)
		else:
			file_data = file_data[: -1]
			saved_known_orphans = {} # init
			# convert the whole-file-string to a dict in two setps. firstly
			# get a list with each element being a line of the file
			list_of_csvs = [
				orphan_block_hash.strip() for orphan_block_hash in file_data
			]
			# then loop through the list of csvs and convert to a dict
			for csv_str in list_of_csvs:
				csv_list = csv_str.split(",")
				block_height = int(csv_list[0])
				block_hash = hex2bin(csv_list[1])
				if block_height not in saved_known_orphans:
					# this block height has not been saved before
					saved_known_orphans[block_height] = [block_hash]
				elif block_hash not in saved_known_orphans[block_height]:
					# this block height has been saved before but not this hash
					saved_known_orphans[block_height].append(block_hash)

	return saved_known_orphans

def save_known_orphans(orphans, backup = True):
	"""
	save the supplied dict of orphans to disk and backup the old file if
	necessary. the purpose of the backup is to enable restoring in case of a
	failed disk write. orphans is in the format {
		block height: [block hash, ...], ...
	}
	"""
	global saved_known_orphans
	# copy2 preserves file metadata
	shutil.copy2(
		known_orphans_file, "%s.backup.%s" % (
			known_orphans_file, time.strftime("%Y-%m-%d-%H-%M-%S")
		)
	)
	# the old orphans file is now safely backed-up :)

	with open(known_orphans_file, "w") as f:
		# convert the orphans var to a single string for the whole file. first
		# get a list of csv strings
		csv_list = [] # init
		for (block_height, hash_list) in orphans.items():
			for block_hash in hash_list:
				csv_list.append("%d,%s" % (block_height, bin2hex(block_hash)))

		csv_list.append(".")

		# convert the list of csv strings into a single string for the file
		f.write("\n".join(s for s in csv_list))

	# the new orphan data is saved to disk - reflect this in the global variable
	saved_known_orphans = orphans

def is_orphan(block_hash):
	for (block_height, orphan_block_hash_list) in saved_known_orphans.items():
		if block_hash in orphan_block_hash_list:
			return True
	return False

def save_tx_metadata(parsed_block):
	"""
	save all txs in this block to the filesystem. as of this block the txs are
	unspent.

	we need to backup the location data of each tx so that it can be retrieved
	from the blockchain later on. for this we need to store:

	- the last bytes of the blockhash
	- the tx number
	- the blockfile number (deprecated*)
	- the start position of the block, including magic_network_id (deprecated*)
	- the start position of the tx in the block (deprecated*)
	- the size of the tx in bytes (deprecated*)

	* these elements were previously used to extract txs from the blk[0-9]*.dat
	files, but since the transition to rpc, these elements are deprecated and so
	are set to be blank strings in the metadata files.

	the block hash and tx number are used to distinguish between duplicate txs
	with the same hash. this way we can determine if there is a doublespend.

	we also need to store the block height so that we can check whether the tx
	has reached coinbase maturity before it is spent.

	we also need to store the coinbase status of the transaction so we can
	validate that the transaction has reached maturity later on. note that while
	this information can be obtained from bitcoind we might as well get it from
	the tx_metadata files since we also need the orphan status too

	we also need to store the orphan status so that we know whether this block
	is spendable or not. it is possible that the orphan status has not been
	determined by this stage - this is not a problem as it will be updated later
	on if the block is found to be an orphan.

	finally, we need to store the spending tx hash and txin index. this will
	enable us to determine if double-spending occurs. store a list as the final
	entry of the csv file in the format: [h0-i0, h1-i1, ...], where:
	- h0 is the hash of the transaction that spends txout 0
	- i0 is the txin index of the transaction that spends txout 0
	"""
	# use only the last x bytes of the block hash to conserve disk space. this
	# still gives us 0xff^x chances of catching a duplicate tx hash - plenty
	# given how rare this is
	x = 2
	block_hashend = bin2hex(parsed_block["block_hash"][-x:])

	for (tx_num, tx) in sorted(parsed_block["tx"].items()):
		is_coinbase = 1 if (tx_num == 0) else None
		is_orphan = None if not parsed_block["is_orphan"] else 1
		# no spending txs at this stage
		spending_txs_list = [None] * len(tx["output"])
		blockhashend_txnum = "%s-%s" % (block_hashend, tx_num)
		save_data = {
			blockhashend_txnum: {
				# TODO - check if the block height and coinbase (tx num in block)
				# are returned by getrawtransaction
				# it gives the block hash and we can get the info from there (though it might be slow?)
				"block_height": parsed_block["block_height"],
				"is_coinbase": is_coinbase,
				"is_orphan": is_orphan,
				"spending_txs_list": spending_txs_list
			}
		}
		save_tx_data_to_disk(bin2hex(tx["hash"]), save_data)

def save_tx_data_to_disk(txhash, save_data):
	"""
	save a 64 character hash, eg 2ea121e32934b7348445f09f46d03dda69117f2540de164
	36835db7f032370d0 in a directory structure like base_dir/2e/a1/21.txt the
	remainder of the hash is the first column entry within the csv file:
	e32934b7348445f09f46d03dda69117f2540de16436835db7f032370d0
	this way we use up a maximum of 0xff^3 = 16,777,216 files, but probably far
	fewer. there should be plenty of inodes for this amount of files on any 1tb+
	hard drive.

	txs actually are not unique, for example, block 91842 and block 91812 both
	have the exact same coinbase tx. this occurs when two coinbase addresses are
	the same, or when two txs spend from such coinbases. for this reason the end
	of the block hash and the tx number within the block are included in the tx
	metadata. this enables us to distinguish between a doublespend and a
	blockchain reorganization.
	"""
	(f_dir, f_name, hashend) = hash2dir_and_filename_and_hashend(txhash)

	# create the dir if it does not exist
	if not os.path.exists(f_dir):
		os.makedirs(f_dir)

	# write data to the file if the file does not exist
	try:
		if not os.path.isfile(f_name):
			with open(f_name, "w") as f:
				f.write(tx_metadata_dict2csv({hashend: save_data}))
			return
	except:
		raise IOError(
			"failed to open file %s for writing unspent transaction data %s in"
			% (f_name, save_data)
		)

	# if we get here then we know the file exists. get one tx per list item
	existing_data_csv = get_tx_metadata_csv(txhash, f_dir, f_name, hashend)
	existing_data_dict = tx_metadata_csv2dict(existing_data_csv)

	save_data_new1 = copy.deepcopy(existing_data_dict) # init
	# now update only the relevant hash if it has changed
	if txhash in existing_data_dict:
		save_data_new1[txhash] = merge_tx_metadata(
			txhash, existing_data_dict[txhash], save_data
		)
	else:
		# add the new hash to the dict
		save_data_new1[txhash] = save_data

	# if there is nothing to update then exit here
	if existing_data_dict == save_data_new1:
		return

	# alter the hashes into hashends
	hashstart_len = 64 - len(hashend)
	save_data_new2 = {
		txhash[hashstart_len:]: data for (txhash, data) in \
		save_data_new1.items()
	}
	# overwrite the file
	with open(f_name, "w") as f:
		f.write(tx_metadata_dict2csv(save_data_new2))

def merge_tx_metadata(txhash, old_dict, new_dict):
	"""update the old dict with data from the new dict"""

	return_dict = {}
	for hashend_txnum in old_dict:
		return_dict[hashend_txnum] = {}
	for hashend_txnum in new_dict:
		return_dict[hashend_txnum] = {}

	for hashend_txnum in return_dict:
		try:
			old_dict_i = old_dict[hashend_txnum]
		except:
			# if the tx metadata is not defined in the old dict then it must be
			# in the new dict. update with this alone.
			return_dict[hashend_txnum] = new_dict[hashend_txnum]
			continue
		try:
			new_dict_i = new_dict[hashend_txnum]
		except:
			# if the tx metadata is not defined in the new dict then it must be
			# in the old dict. update with this alone.
			return_dict[hashend_txnum] = old_dict[hashend_txnum]
			continue

		# TODO - reconfigure the tx metadata if changes are found, instead of dying

		for (key, old_v) in old_dict_i.items():
			try:
				new_v = new_dict_i[key]
			except:
				new_v = None

			# if the old is the same as the new then stick to the default
			if old_v == new_v:
				return_dict[hashend_txnum][key] = old_v
				continue

			# if neither old nor new is set
			if (
				(old_v is None) and
				(new_v is None)
			):
				return_dict[hashend_txnum][key] = None
				continue 

			# if only old is set then use that one
			if (
				(old_v is not None) and
				(new_v is None)
			):
				return_dict[hashend_txnum][key] = old_v
				continue

			# if only new is set then use that one
			if (
				(old_v is None) and
				(new_v is not None)
			):
				return_dict[hashend_txnum][key] = new_v
				continue

			# if we get here then both old and new are set and different...

			# orphan status
			if key == "is_orphan":
				# do not update if the tx is already marked as an orphan
				if old_v is not None:
					return_dict[hashend_txnum][key] = old_v
				else:
					return_dict[hashend_txnum][key] = new_v

			# spending txs list. each element is a later tx hash and txin index
			# that is spending from the tx specified by the filename
			if key == "spending_txs_list":
				return_dict[hashend_txnum][key] = \
				merge_spending_txs_lists(txhash, old_v, new_v)

	return return_dict

def merge_spending_txs_lists(txhash, old_list, new_list):
	"""
	merge the updates into the list that aready exists. the spending_txs_list is
	of the format: [txhash0-index0, txhash1-index1, ...] where txhash0 is the
	hash of the transaction that is spending the current transaction specified
	by the filename. and index0 is the txin index of the transaction that is
	spending the current tranaction specified by the filename.

	if any different transaction tries to spend a transaction that has already
	been spent then issue a warning and do not update this element of the list.
	"""
	# assume that the old_list at least has the correct number of elements
	return_list = copy.deepcopy(old_list)

	for i in range(len(old_list)):
		# get the value of the old list element
		try:
			old_v = old_list[i]
		except:
			old_v = None

		# get the value of the new list element
		try:
			new_v = new_list[i]
		except:
			new_v = None

		# if neither old nor new is set then stick to the default
		if (
			(old_v is None) and
			(new_v is None)
		):
			return_list[i] = None
			continue 

		# if only old is set then use that one
		if (
			(old_v is not None) and
			(new_v is None)
		):
			return_list[i] = old_v
			continue

		# if only new is set then use that one
		if (
			(old_v is None) and
			(new_v is not None)
		):
			return_list[i] = new_v
			continue

		# if the old is the same as the new then stick to the default
		if old_v == new_v:
			continue

		# if we get here then both old and new are set and different...
		(old_spend_hash, old_spend_index) = old_v.split("-")
		(new_spend_hash, new_spend_index) = new_v.split("-")
		raise ValueError(
			"doublespend error. transaction with hash %s has already been spent"
			" by tx starting with hash %s and txin index %s, however tx"
			" starting with hash %s and txin index %s is attempting to spend"
			" this transaction now as well."
			% (
				txhash, old_spend_hash, old_spend_index, new_spend_hash,
				new_spend_index
			)
		)
	return return_list

def tx_metadata_dict2csv(dict_data):
	"""
	convert the tx data from the dict to a list, then convert this list to a csv
	string to be stored on disk. the tx_metadata_keynames global list gives the
	order of the csv elements.
	"""
	# the outer list contains one item per csv line
	outer_list = [] # init
	for (txhash, middle_dict_data) in dict_data.items():

		for (hashend_txnum, inner_dict_data) in middle_dict_data.items():

			inner_list = [] # init or reset
			for keyname in tx_metadata_keynames:

				if keyname == "tx_hash":
					el = txhash
				elif keyname == "blockhashend_txnum":
					el = hashend_txnum
				elif keyname in inner_dict_data:
					el = copy.deepcopy(inner_dict_data[keyname])
				else:
					el = None

				if isinstance(el, list):

					# convert any None values to an empty string
					for (j, sub_el) in enumerate(el):
						if sub_el is None:
							el[j] = ""
						else:
							# convert numbers to strings
							el[j] = "%s" % sub_el

					el = "[%s]" % ",".join(el)

				elif (
					isinstance(el, str) and
					("-" in el)
				):
					# keep as string
					pass

				else:
					if el is None:
						el = ""
					else:
						# convert numbers to strings
						el = "%s" % el

				inner_list.append(el)

			outer_list.append(",".join(inner_list))

	return "\n".join(outer_list)

def tx_metadata_csv2dict(csv_data):
	"""
	the tx data is stored as comma seperated values in the tx metadata files and
	the final element is a representation of a list. the tx_metadata_keynames
	global list shows what each element of the csv represents. the csv can have
	multiple lines because transaction hashes are not unique ids (see bip30) and
	also because all hashes starting with the same 6 characters exist in the
	same file, eg. hash 123456aa and 123456bb are in the same file.

	the last 2 bytes (4 chars) of the block hash and the txnum are included in
	each tx as a unique id. note that the block hash alone would not be a unique
	id since it is possible that the same block contains multiple transactions
	with the same hash. this would occur if two txs spend two coinbase txs in
	other blocks which have the same output script (address).
	"""
	# csv_data is a list of txs
	dict_data = {}
	tx_hash_index = tx_metadata_keynames.index("tx_hash")
	blockhashend_txnum_index = tx_metadata_keynames.index("blockhashend_txnum")
	for tx in csv_data:
		# if the final character of the tx is not a "]" then this is a malformed
		# csv file (interrupted write?)
		if tx[-1] != "]":
			raise ValueError("malformed csv file. each line must end in ']'")

		# get the csv as a list (but not including the square bracket, since it
		# might contain commas which would be interpreted as top level elements
		start_sq = tx.index("[")
		list_data = tx[: start_sq - 1].split(",")

		# add the square bracket substring back onto the end of the list
		sq = tx[start_sq:]
		list_data.append(sq)

		tx_data = {}
		for (i, el) in enumerate(list_data):
			# convert empty strings to None values
			if el == "":
				el = None

			# convert string representation of a list to a list
			elif (
				(el[0] == "[") and
				(el[-1] == "]")
			):
				el = el[1: -1].split(",")
				for (j, sub_el) in enumerate(el):
					# convert empty strings to None values
					if sub_el == "":
						el[j] = None

			# must come after the list check, since this has "-" in it too
			elif "-" in el:
				# keep as string
				pass

			elif i == tx_hash_index:
				# keep as string
				pass
			else:
				el = int(el)

			# save the tx hash and block hash end - txnum seperately for now
			if i == tx_hash_index:
				tx_hash = el
			elif i == blockhashend_txnum_index:
				blockhashend_txnum = el
			else:
				tx_data[tx_metadata_keynames[i]] = el

		if tx_hash not in dict_data:
			dict_data[tx_hash] = {} # init

		# no need to check if the blockhashend_txnum already exists since this
		# is unique
		dict_data[tx_hash][blockhashend_txnum] = tx_data

	return dict_data

def get_tx_metadata_csv(txhash, f_dir = None, f_name = None, hashend = None):
	"""
	given a tx hash (as a hex string), fetch the position data from the
	tx_metadata dirs. return csv data in a list - one line per item and each
	item is a csv string.
	"""
	if (
		(f_dir is None) or
		(f_name is None) or
		(hashend is None)
	):
		(f_dir, f_name, hashend) = hash2dir_and_filename_and_hashend(txhash)
	prepend_len = 64 - len(hashend)
	hashstart = txhash[: prepend_len]
	try:
		with open(f_name, "r") as f:
			# get each tx as a list item
			data = [] # init
			for line in f:
				# get rid of the newline if it exists and prepend the first 6
				# characters of the tx hash to create a complete hash
				data.append("%s%s" % (hashstart, line.translate(None, "\n\r")))
	except:
		# this can occur when the user spends a transaction which exists within
		# the same block - the transaction will not have been written to the
		# filesystem yet. not to worry - we just fetch the transaction from ram
		# later on (before moving on to the next block)
		data = None

	return data

def filter_tx_metadata(txs_metadata, filter_txhash):
	"""
	tx metadata contains many different tx hashes - filter out and return only
	the relevant one
	the txs_metadata input is in the following format: {
		tx_hash: {blockhashend_txnum: [tx_data]}
	}
	and the return output is {blockhashend_txnum: [tx_data]} from the above
	"""
	for (txhash, txhash_data) in txs_metadata.items():
		if txhash == filter_txhash:
			return txhash_data

	# if we get here then the specified hash has not been found
	return None

def mark_spent_txs(parsed_block):
	"""
	mark off all txs that this block spends (in the metadata csv database). note
	that we should not delete these spent txs because we will need them in
	future to identify txin addresses and also to identify double-spends.
	"""
	for (tx_num, tx) in sorted(parsed_block["tx"].items()):
		# coinbase txs don't spend previous txs
		if tx_num == 0:
			continue
		spender_txhash = tx["hash"]
		for (spender_index, spender_txin) in tx["input"].items():
			spendee_txs_metadata = spender_txin["prev_txs_metadata"]
			spendee_txhash = bin2hex(spender_txin["hash"])
			spendee_index = spender_txin["index"]
			mark_spent_tx(
				spendee_txhash, spendee_index, spender_txhash, spender_index,
				spendee_txs_metadata
			)

def mark_spent_tx(
	spendee_txhash, spendee_index, spender_txhash, spender_index,
	spendee_txs_metadata
):
	"""
	mark the spendee transaction as spent using the later (spender) tx hash and
	later txin index. it should be impossible to overwrite a transaction that
	has already been spent. but don't worry about this - the lower level
	functions will handle this.
	"""
	# coinbase txs do not spend from any previous tx in the blockchain so these
	# do not need to be marked off
	if (
		(spendee_txhash == blank_hash) and
		(spendee_index == coinbase_index)
	):
		return

	# use only the first x bytes to conserve disk space. this still gives us
	# 0xff^x chances of catching a doublespend - plenty given how rare this is
	x = 2
	spender_txhash = bin2hex(spender_txhash[: x])

	# construct the list of txs that are spending from the previous tx. this
	# list may be too small, but it doesn't matter - so long as we put the data
	# in the correct location in the list.
	spender_txs_list = [None] * (spendee_index + 1) # init
	spender_hashstart_index = "%s-%s" % (spender_txhash, spender_index)
	spender_txs_list[spendee_index] = spender_hashstart_index

	# now determine which block-hash-end txnum combo we are spending from
	# (remember txs are not unique so we need to specify the block and tx num
	# that the spendee tx hash is in). if it already exists then use that one...
	use_blockhashend_txnum = None # init
	for (blockhashend_txnum, spendee_tx_metadata) in \
	spendee_txs_metadata.items():
		if spendee_tx_metadata["spending_txs_list"][spendee_index] == \
		spender_hashstart_index:
			use_blockhashend_txnum = blockhashend_txnum

	# otherwise use the block-hash-end from the tx with the earliest blockheight
	# that has not already been spent
	if use_blockhashend_txnum is None:
		# TODO - write unit test for a duplicate tx hash being spent
		latest_block_height = None # init
		for (blockhashend_txnum, spendee_tx_metadata) in \
		spendee_txs_metadata.items():
			this_block_height = spendee_tx_metadata["block_height"]
			if (
				(
					spendee_tx_metadata["spending_txs_list"][spendee_index] \
					is None
				) and (
					(latest_block_height is None) or
					(this_block_height > latest_block_height)
				)
			):
				#earliest_block_height = this_block_height
				latest_block_height = this_block_height
				use_blockhashend_txnum = blockhashend_txnum

	save_data = {
		use_blockhashend_txnum: {"spending_txs_list": spender_txs_list}
	}
	save_tx_data_to_disk(spendee_txhash, save_data)

def hash2dir_and_filename_and_hashend(hash64 = ""):
	"""
	convert a 64 character hash, eg 2ea121e32934b7348445f09f46d03dda69117f2540de
	16436835db7f032370d0 to a directory structure like base_dir/2e/a1/21.txt
	the remainder of the hash will be stored within this file
	"""
	n = 2 # max dirname length
	hash_elements = [hash64[i: i + n] for i in range(0, 6, n)]
	#f_dir = "%s%s/" % (tx_metadata_dir, "/".join(hash_elements[: -1]))
	f_dir = os.path.join(
		os.path.join(tx_metadata_dir, *hash_elements[: -1]), ""
	)
	#f_name = "%s%s.txt" % (f_dir, hash_elements[-1])
	f_name = os.path.join(f_dir, "%s.txt" % hash_elements[-1])
	hashend = hash64[6:]
	return (f_dir, f_name, hashend)

def minimal_block_parse_maybe_save_txs(
	block_bytes, block_height, saved_validation_data, hash_table, options
):
	"""
	the aim of this function is to parse as little of the block as is necessary
	so as to eliminate computational waste. this function is called before it is
	possible to know whether the block has been specified by the user (since the
	block height is not yet known, so range checks cannot yet be performed).

	if we are not yet upto the latest saved tx then this means that all the txs
	in this block have already been saved, so there is no need to parse txs for
	this reason.

	if we are already past the latest saved tx then this means that all the txs
	in this block have not yet been saved to disk, so parse the whole block so
	that we can save the txs in it to disk in the following functions.

	if we are not yet upto the latest validated block then this means that all
	the txs in this block have already been validated, so there is no need to
	parse txs for this reason.

	if we are already past the latest validated block then this means that all
	the txs in this block have not yet been validated, so parse the whole block
	(if the user has asked to validate any blocks at all) so that we can
	validate the txs in it in the following functions.
	"""
	(
		saved_validated_hash, saved_validated_block_height,
		saved_previous_validated_hash
	) = saved_validation_data

	save_txs = True if (block_height > saved_validated_block_height) else False

	if save_txs:
		get_info = all_block_and_validation_info
	else:
		get_info = all_block_header_and_validation_info

	parsed_block = block_bin2dict(
		block_bytes, block_height, get_info, options.explain
	)
	# die if this block has no ancestor
	enforce_ancestor(hash_table, parsed_block["previous_block_hash"])

	"""
	this is already known now
	# get the block height
	parsed_block["block_height"] = \
	hash_table[parsed_block["previous_block_hash"]][0] + 1
	"""

	# now get the smallest amount of extra data necessary for saving
	# transactions to disk (no need to get missing txin addresses here as these
	# do not get saved to disk)
	if save_txs:
		# get the coinbase txin funds. this is not strictly necessary at this
		# point since it is not part of the tx data that gets saved to disk, but
		# its confusing to leave this value empty for later on, when all the
		# other tx data is available, so get it now.
		#parsed_block["tx"][0]["input"][0]["funds"] = mining_reward(
		#	parsed_block["block_height"]
		#)
		# if any prev_tx data could not be obtained from the tx_metadata dirs in
		# the filesystem it could be because this data exists within the current
		# block and has not yet been written to disk. if so then add it now.
		### with bitcoind it should always be possible to get the previous txs
		###parsed_block = add_missing_prev_txs(parsed_block, get_info)

		# initialize transaction metadata so we can see if they are spent or not
		save_tx_metadata(parsed_block)

	return parsed_block

def get_range_options(options, sanitized = False):
	"""
	if the user has specified a start block or an end block then convert these
	into start and end block heights

	these start and end blocks can be used as a filter to exclude other block
	data that may be found. the earliest start block possible is selected and
	the latest end block possible is selected.
	"""
	# make sure the user input data has been sanitized
	enforce_sanitization(sanitized)

	lower_block = None # init
	upper_block = None # init
	explain_lower = "" # init
	explain_upper = "" # init

	# convert the start block date and hash to a height and select the earliest
	if options.STARTBLOCKNUM is not None:
		if lower_block is None:
			lower_block = options.STARTBLOCKNUM
			explain_lower = "from block num %s" % options.STARTBLOCKNUM
		elif options.STARTBLOCKNUM < lower_block:
			lower_block = options.STARTBLOCKNUM
			explain_lower = "from block num %s" % options.STARTBLOCKNUM

	if options.STARTBLOCKDATE is not None:
		temp_lower_block = block_date2heights(options.STARTBLOCKDATE).keys()[0]
		if lower_block is None:
			lower_block = temp_lower_block
			explain_lower = "converted from date %s" % (options.STARTBLOCKDATE)
		elif temp_lower_block < lower_block:
			lower_block = temp_lower_block
			explain_lower = "converted from date %s" % (options.STARTBLOCKDATE)

	if options.STARTBLOCKHASH is not None:
		temp_lower_block = get_block(options.STARTBLOCKHASH, "json")["height"]
		if lower_block is None:
			lower_block = temp_lower_block
			explain_lower = "converted from hash %s" % (options.STARTBLOCKHASH)
		elif temp_lower_block < lower_block:
			lower_block = temp_lower_block
			explain_lower = "converted from hash %s" % (options.STARTBLOCKHASH)

	if lower_block is None:
		lower_block = 0

	# convert the end block date and hash to a height and select the latest
	if options.ENDBLOCKNUM is not None:
		if upper_block is None:
			upper_block = options.ENDBLOCKNUM
			explain_upper = "from block num %s" % options.ENDBLOCKNUM
		elif options.ENDBLOCKNUM < upper_block:
			upper_block = options.ENDBLOCKNUM
			explain_upper = "from block num %s" % options.ENDBLOCKNUM

	if options.ENDBLOCKDATE is not None:
		temp_upper_block = block_date2heights(options.ENDBLOCKDATE).keys()[1]
		if upper_block is None:
			upper_block = temp_upper_block
			explain_upper = "converted from date %s" % (options.STARTBLOCKDATE)
		elif temp_upper_block > upper_block:
			upper_block = temp_upper_block
			explain_upper = "converted from date %s" % (options.STARTBLOCKDATE)

	if options.ENDBLOCKHASH is not None:
		temp_upper_block = get_block(options.ENDBLOCKHASH, "json")["height"]
		if upper_block is None:
			upper_block = temp_upper_block
			explain_upper = "converted from hash %s" % (options.STARTBLOCKHASH)
		elif temp_upper_block > upper_block:
			upper_block = temp_upper_block
			explain_upper = "converted from hash %s" % (options.STARTBLOCKHASH)

	# STARTBLOCKNUM + LIMIT - 1 to ENDBLOCKNUM
	# - 1 is because the first block is inclusive
	if (
		(lower_block is not None) and
		(options.LIMIT is not None)
	):
		temp_upper_block = lower_block + options.LIMIT - 1
		explain_upper = "converted from limit %d" % (options.LIMIT)
		if upper_block is None:
			upper_block = temp_upper_block
		elif temp_upper_block > upper_block:
			upper_block = temp_upper_block

	if upper_block is None:
		upper_block = get_info()["blocks"]

	if (
		(lower_block is not None) and
		(upper_block is not None) and
		(lower_block > upper_block)
	):
		raise ValueError(
			"the specified end block (%d %s) comes before the specified start"
			" block (%d %s)"
			% (upper_block, explain_upper, lower_block, explain_lower)
		)

	return (lower_block, upper_block)

def before_range(block_height):
	"""
	check if the current block is before the range (inclusive) specified by the
	options

	note that function get_range_options() must be called before running
	this function so as to convert ranges based on hashes or limits into ranges
	based on block numbers.
	"""
	if (block_height < block_range_filter_lower):
		return True

	return False

def after_range(block_height, seek_orphans = False):
	"""
	have we gone past the user-specified block range?

	if the seek_orphans option is set then we must proceed coinbase_maturity
	blocks past the user specified range to be able to check for orphans. this
	options is only needed on the first pass of the blockchain.

	note that function get_range_options() must be called before running
	this function so as to convert ranges based on hashes or limits into ranges
	based on block numbers.
	"""
	new_upper_limit = block_range_filter_upper # init
	if seek_orphans:
		new_upper_limit += coinbase_maturity
	
	if (block_height > new_upper_limit):
		return True

	return False

def whole_block_match(options, block_hash, block_height):
	"""
	check if the user wants the whole block returned

	note that function get_range_options() must be called before running
	this function so as to convert ranges based on hashes or limits into ranges
	based on block numbers.
	"""

	# if the block is not in the user-specified range then it is not a match.
	if (
		before_range(block_height) or
		after_range(block_height)
	):
		return False

	# the user has specified this block via its hash
	if (
		(options.BLOCKHASHES is not None) and
		[required_block_hash for required_block_hash in options.BLOCKHASHES \
		if required_block_hash == block_hash]
	):
		return True

	# the user has specified this block by default
	if (
		(options.BLOCKHASHES is None) and
		(options.TXHASHES is None) and
		(options.ADDRESSES is None)
	):
		return True

	return False

def manage_update_relevant_block(options, in_range, parsed_block):
	"""
	if the options specify this block then parse the tx data (which we do not
	yet have) and return it. we have previously already gotten the block header
	and header-validation info so there is no need to parse these again.
	"""

	# if the block is not in range then exit here without adding it to the
	# filtered_blocks var. after_range() searches coinbase_maturity beyond the
	# user-specified limit to determine whether the blocks in range are orphans
	if not in_range:
		return None

	# check the block hash and whether the block has been specified by default
	if whole_block_match(
		options, parsed_block["block_hash"], parsed_block["block_height"]
	):
		return update_relevant_block(parsed_block, options)

	# check the txin hashes
	if options.TXINHASHES:
		parsed_block.update(block_bin2dict(block, ["txin_hash"], options))
		get_info.remove("txin_hash")
		# if any of the options.TXINHASHES matches a txin then this block is
		# relevant, so get the remaining data
		if txin_hashes_in_block(parsed_block, options.TXINHASHES):
			return update_relevant_block(parsed_block, options)

	# check the txout hashes (only 1 hash per tx)
	if options.TXHASHES is not None:
		parsed_block.update(block_bin2dict(block, ["tx_hash"], options))
		get_info.remove("tx_hash")
		# if any of the options.TXHASHES matches a tx hash then this block is
		# relevant, so get the remaining data
		if tx_hashes_in_block(parsed_block, options.TXHASHES):
			return update_relevant_block(parsed_block, options)

	# check the addresses
	if (
		(options.ADDRESSES is not None) and
		addresses_in_block(options.ADDRESSES, block)
	):
		return update_relevant_block(parsed_block, options)

	# if we get here then no data has been found and this block is not relevant
	return None

def update_relevant_block(parsed_block, options):

	# by this point we have already parsed the info from
	# all_block_header_and_validation_info, so we only need to get the remaining
	# transaction and transaction-validation info. we will not be calculating
	# validation statuses at this stage, but we still want to show the user the
	# things that can be validated 
	get_info = copy.deepcopy(all_tx_and_validation_info)

	parsed_block.update(block_bin2dict(
		parsed_block["bytes"], get_info, options
	))
	parsed_block["tx"][0]["input"][0]["funds"] = mining_reward(
		parsed_block["block_height"]
	)
	return parsed_block

def final_results_filter(filtered_blocks, options):
	"""
	this function is used to prepare the data to be displayed to the user. the
	blockchain is always parsed into individual blocks as elements of a dict,
	and these are input to this function. if the user has specified that they
	want something less than full blocks (eg txs or address balances) then
	return only that data that has been requested by the user.
	"""
	# the user doesn't want to see any data (they must just be validating the
	# blockchain)
	if options.OUTPUT_TYPE is None:
		return None

	# if the user wants to see full blocks then just return it as-is
	if options.OUTPUT_TYPE == "BLOCKS":
		return filtered_blocks

	# beyond this point we only need tx data
	txs = {} # use a temp dict for txs - this keeps txs unique

	# filter the required txs
	for (block_hash, parsed_block) in filtered_blocks.items():
		for tx in parsed_block.values():
			txhash = tx["hash"]

			# if the user has specified these txs via the blockhash
			if (
				(options.BLOCKHASHES is not None) and
				(block_hash in options.BLOCKHASHES)
			):
				txs[txhash] = tx

			# if the user has specified these txs via their hashes
			elif (
				(options.TXHASHES is not None) and
				(tx["hash"] in options.TXHASHES)
			):
				txs[txhash] = tx

			# if the user has specified these txs via an address
			elif options.ADDRESSES is not None:
				# check the txout addresses
				for txout in tx["output"].values():
					breakout = False
					for address in txout["addresses"]:
						if address in options.ADDRESSES:
							txs[txhash] = tx
							breakout = True
							break
					if breakout:
						break

				# check the txin addresses
				for txin in tx["input"].values():
					breakout = False
					for address in txin["addresses"]:
						if address in options.ADDRESSES:
							txs[txhash] = tx
							breakout = True
							break
					if breakout:
						break

	# now we know there are no dup txs, convert the dict to a list
	txs = [tx for tx in txs.values()]

	if not len(txs):
		return None

	# if the user wants to see transactions then extract only the relevant txs
	if options.OUTPUT_TYPE == "TXS":
		return txs

	# if the user wants to see balances then return a list of balances
	if options.OUTPUT_TYPE == "BALANCES":
		return tx_balances(txs, options.ADDRESSES)

	# thanks to options_grunt.sanitize_options_or_die() we will never get to
	# this line

def tx_hashes_in_block(block, search_txhashes):
	"""
	check if any of the txs specified by hash value exist in the block.
	search_txhashes is a list of tx hashes (not txin hashes).
	"""
	if isinstance(block, dict):
		parsed_block = block # already parsed
	else:
		parsed_block = block_bin2dict(block, ["tx_hash"])

	for tx in parsed_block["tx"].values():
		if [sh for sh in search_txhashes if sh == tx["hash"]]:
			return True

	return False

def txin_hashes_in_block(block, search_txhashes):
	"""
	check if any of the txins specified by hash value and index exist in the
	txins of this block. search_txhashes is a dict of txin-hashes and
	txin-indexes in the format {hash: [index, index, index], hash: [index]}
	"""
	if isinstance(block, dict):
		parsed_block = block # already parsed
	else:
		parsed_block = block_bin2dict(block, ["tx_hash"])

	for tx in parsed_block["tx"].values():
		for (txin_num, txin) in sorted(tx["input"]).items():
			for (search_hash, search_indexes) in search_txhashes.items():
				if (
					(search_hash == txin["hash"]) and
					[index for index in search_indexes if index == txin_num]
				):
					return True

	return False

def addresses_in_block(addresses, block):
	"""
	this function checks whether any of the specified addresses exist in the
	block. the block may contain addresses in a variety of formats which may not
	match the formats of the input argument addresses. for example the early
	coinbase addresses are in the full public key format, while the input
	argument addresses may be in base58.

	a simple string search for the address string within the block string is not
	done because there is a tiny chance of a false positive if one of the
	transaction hashes contains the same character sequence as the address.

	note that this function can return false negatives in the case where a block
	contains an unhashed public key and we only know the address (that is the
	base58 hash of the public key) to search for.
	"""
	# TODO - only check txout addresses - options.TXHASHES handles the txin
	# addresses
	parsed_block = block_bin2dict(
		block, ["txin_addresses", "txout_addresses"], options
	)
	for tx_num in parsed_block["tx"]:
		if parsed_block["tx"][tx_num]["input"] is not None:
			txin = parsed_block["tx"][tx_num]["input"]
			for input_num in txin:
				if txin[input_num]["addresses"] is not None:
					for txin_address in txin[input_num]["addresses"]:
						if txin_address in addresses:
							return True

		if parsed_block["tx"][tx_num]["output"] is not None:
			txout = parsed_block["tx"][tx_num]["output"]
			for output_num in txout:
				if txout[output_num]["addresses"] is not None:
					for txout_address in txout[output_num]["addresses"]:
						if txout_address in addresses:
							return True

def address2txin_data(options, block):
	"""
	the bitcoin protocol specifies that the decoded address in a txout is always
	the same as the decoded address in the later txin which points back to the
	original txout and txout-index. the txout address can easily be decoded in
	isolation, but the only sure way to decode the address in a txin is by
	looking at the earlier txout that it points to.

	in this function we convert user-specified addresses in txouts into
	txout hashes and txout-indexes to be searched for as txins in later blocks.

	options.TXINHASHES is in the format {hash: [index, ..., index]}. we set the
	indexes using txout indexes matching options.ADDRESSES
	"""
	if options.ADDRESSES is None:
		return options.TXINHASHES

	if isinstance(block, dict):
		parsed_block = block
	else:
		parsed_block = block_bin2dict(block, ["tx_hash", "txout_addresses"])

	for (tx_num, tx) in sorted(parsed_block["tx"].items()):
		indexes = [] # reset
		for (txout_num, txout) in sorted(tx["output"].items()):
			# if this tx has previously been saved in the options object then
			# skip to the nex tx now
			if(
				(tx["hash"] in options.TXINHASHES) and
				(txout_num in options.TXINHASHES[tx["hash"]])
			):
				continue

			# if any of this txout's addresses have been specified by the user
			# then save the index
			for txout_address in txout["addresses"]:
				if txout_address in options.ADDRESSES:
					indexes.append(txout_num)
					break
		if indexes:
			# if any indexes already exist for this hash then merge these with
			# the new indexes and make unique
			if tx["hash"] in options.TXINHASHES:
				options.TXINHASHES[tx["hash"]] = list(set(
					options.TXINHASHES[tx["hash"]] + indexes
				))
			# else save the newly aquired indexes (they are already unique)
			else:
				options.TXINHASHES[tx["hash"]] = indexes

	return options.TXINHASHES

def merge_blocks_ascending(*blocks):
	"""
	combine blocks args into a single dict in ascending block height
	"""

	# first loop through all blocks and save the hashes in order
	hash_order = {}
	for blocks_subset in blocks:
		for block_hash in blocks_subset:
			hash_order[blocks_subset[block_hash]["block_height"]] = block_hash

	# now construct the output dict in this order
	all_blocks = {}
	for block_height in hash_order:
		block_hash = hash_order[block_height]
		for blocks_subset in blocks:
			if block_hash in blocks_subset:
				all_blocks[block_hash] = blocks_subset[block_hash]
				break

	return all_blocks

def maybe_fetch_more_blocks(
	file_handle, fetch_more_blocks, active_blockchain, bytes_into_section,
	bytes_into_file, active_blockchain_num_bytes
):
	"""
	fetch more blocks if possible, otherwise skip to the next blockchain file
	"""
	if (
		(not fetch_more_blocks) and
		((len(active_blockchain) - bytes_into_section) < 8)
	):
		fetch_more_blocks = True

	if fetch_more_blocks:
		file_handle.seek(bytes_into_file, 0)

		# get a subsection of the blockchain file
		active_blockchain = file_handle.read(active_blockchain_num_bytes)
		bytes_into_section = 0 # reset everytime active_blockchain is updated

		# if there are blocks left in this file
		if len(active_blockchain):
			fetch_more_blocks = False

	return (fetch_more_blocks, active_blockchain, bytes_into_section)

def enforce_ancestor(hash_table, previous_block_hash):
	"""die if the block has no ancestor"""
	if previous_block_hash not in hash_table:
		raise Exception(
			"could not find parent for block with hash %s (parent hash: %s)."
			" Investigate."
			% (bin2hex(block_hash), bin2hex(previous_block_hash))
		)

def block_bin2dict(block, block_height, required_info_, explain_errors = False):
	"""
	extract the specified info from the block into a dictionary and return as
	soon as it is all available.

	for the validation_status info just initialize to None to acknowledge that
	they are necessary but have not been processed yet. they will be processed
	later elsewhere. this way, even if the user does not want to validate the
	blocks, there is feedback that the blocks have not been validated.
	attempting to convey the difference between 'do not verify' and 'not yet
	verified' through the required_info list input to this function would be
	messy. would omission of an element mean to set it to None? for some
	functions this would be undesirable, as we really just want to process the
	specified elements and get out asap.
	"""
	block_arr = {} # init

	# copy to avoid altering the argument outside the scope of this function
	required_info = copy.deepcopy(required_info_)

	# initialize the orphan status - not possible to determine this yet
	if "orphan_status" in required_info:
		block_arr["is_orphan"] = None
		required_info.remove("orphan_status")
		if not required_info: # no more info required
			return block_arr

	# initialize the block height
	if "block_height" in required_info:
		block_arr["block_height"] = block_height
		required_info.remove("block_height")
		if not required_info: # no more info required
			return block_arr

	# extract the block hash from the header. this is necessary
	if "block_hash" in required_info:
		block_arr["block_hash"] = calculate_block_hash(block)
		required_info.remove("block_hash")
		if not required_info: # no more info required
			return block_arr
	pos = 0

	if "format_version" in required_info:
		block_arr["format_version"] = bin2int(little_endian(
			block[pos: pos + 4]
		))
		required_info.remove("format_version")
		if not required_info: # no more info required
			return block_arr
	pos += 4

	if "previous_block_hash" in required_info:
		block_arr["previous_block_hash"] = little_endian(block[pos: pos + 32])
		required_info.remove("previous_block_hash")
		if not required_info: # no more info required
			return block_arr
	pos += 32

	if "merkle_root" in required_info:
		block_arr["merkle_root"] = little_endian(block[pos: pos + 32])
		required_info.remove("merkle_root")
		if not required_info: # no more info required
			return block_arr
	pos += 32


	if (
		("timestamp" in required_info) or
		("tx_timestamp" in required_info)
	):
		timestamp = bin2int(little_endian(block[pos: pos + 4]))
	pos += 4

	if "timestamp" in required_info:
		block_arr["timestamp"] = timestamp
		required_info.remove("timestamp")
		if not required_info: # no more info required
			return block_arr

	if (
		("bits" in required_info) or
		("target" in required_info) or
		("difficulty" in required_info)
	):
		bits = little_endian(block[pos: pos + 4])
	pos += 4

	if "bits" in required_info:
		block_arr["bits"] = bits
		required_info.remove("bits")
		if not required_info: # no more info required
			return block_arr

	if "target" in required_info:
		block_arr["target"] = int2hex(bits2target_int(bits))
		required_info.remove("target")
		if not required_info: # no more info required
			return block_arr

	if "bits_validation_status" in required_info:
		# None indicates that we have not tried to verify that the target is
		# correct given the previous target and time taken to mine the previous
		# 2016 blocks
		block_arr["bits_validation_status"] = None
		required_info.remove("bits_validation_status")
		if not required_info: # no more info required
			return block_arr

	if "difficulty" in required_info:
		block_arr["difficulty"] = bits2difficulty(bits)
		required_info.remove("difficulty")
		if not required_info: # no more info required
			return block_arr
	
	if "difficulty_validation_status" in required_info:
		# None indicates that we have not tried to verify that difficulty > 1
		block_arr["difficulty_validation_status"] = None
		required_info.remove("difficulty_validation_status")
		if not required_info: # no more info required
			return block_arr

	if "block_hash_validation_status" in required_info:
		# None indicates that we have not tried to verify the block hash
		# against the target
		block_arr["block_hash_validation_status"] = None
		required_info.remove("block_hash_validation_status")
		if not required_info: # no more info required
			return block_arr

	if "nonce" in required_info:
		block_arr["nonce"] = bin2int(little_endian(block[pos: pos + 4]))
		required_info.remove("nonce")
		if not required_info: # no more info required
			return block_arr
	pos += 4

	(num_txs, length) = decode_variable_length_int(block[pos: pos + 9])
	if "num_txs" in required_info:
		block_arr["num_txs"] = num_txs
		required_info.remove("num_txs")
		if not required_info: # no more info required
			return block_arr
	pos += length

	block_arr["tx"] = {}
	# loop through all transactions in this block
	for i in range(0, num_txs):
		block_arr["tx"][i] = {}
		(block_arr["tx"][i], length) = tx_bin2dict(
			block, pos, required_info, i, block_height, explain_errors
		)
		if "tx_timestamp" in required_info:
			block_arr["tx"][i]["timestamp"] = timestamp

		if not required_info: # no more info required
			return block_arr
		pos += length

	# if any transactions spend from other transactions within this same block
	# then we will be missing previous tx data. fetch it now
	block_arr = add_missing_prev_txs(block_arr, required_info)

	if "txin_coinbase_change_funds" in required_info:
		block_arr["tx"][0]["input"][0]["coinbase_change_funds"] = \
		calculate_tx_change(block_arr)

	if "merkle_root_validation_status" in required_info:
		# None indicates that we have not tried to verify
		block_arr["merkle_root_validation_status"] = None
		required_info.remove("merkle_root_validation_status")
		if not required_info: # no more info required
			return block_arr

	if "block_size" in required_info:
		block_arr["size"] = pos

	if "block_size_validation_status" in required_info:
		# None indicates that we have not tried to verify
		block_arr["block_size_validation_status"] = None
		required_info.remove("block_size_validation_status")
		if not required_info: # no more info required
			return block_arr

	if "block_bytes" in required_info:
		block_arr["bytes"] = block

	if len(block) != pos:
		raise Exception(
			"the full block could not be parsed. block length: %s, position: %s"
			% (len(block), pos)
		)
	# we only get here if the user has requested all the data from the block
	return block_arr

def tx_bin2dict(
	block, pos, required_info, tx_num, block_height, explain_errors = False
):
	"""
	parse the specified transaction info from the block into a dictionary and
	return as soon as it is all available.

	this function gets previous tx data that has been parsed and stored to disk,
	but it does not extract previous tx data when that data comes from a
	transaction within this very block and has not yet been stored to disk.
	since txin addresses rely on previous txs, some txin addresses will be
	unknown and we will have to derive these later.

	also, since this function is intended to parse data from the blockchain, it
	does not validate checksigs, so any txin addresses may actually be invalid.
	this does not matter because the "checksig_validation_status" status of each
	txin can be polled to see if the addresses are valid or not.

	also, since scripts are not validated in this function, multisig addresses
	cannot be determined, and are simply set to None. these must be derived
	later elsewhere.
	"""
	tx = {} # init
	init_pos = pos

	# the first transaction is always coinbase (mined)
	is_coinbase = True if (tx_num == 0) else False

	"""
	if "tx_pos_in_block" in required_info:
		# this value gets stored in the tx_metadata dirs to enable quick
		# retrieval from the blockchain files later on
		tx["pos"] = init_pos
	"""

	if "tx_version" in required_info:
		tx["version"] = bin2int(little_endian(block[pos: pos + 4]))
	pos += 4

	(num_inputs, length) = decode_variable_length_int(block[pos: pos + 9])
	if "num_tx_inputs" in required_info:
		tx["num_inputs"] = num_inputs
	pos += length

	if "txins_exist_validation_status" in required_info:
		tx["txins_exist_validation_status"] = None

	# if the user wants to retrieve the txin funds, txin addresses or previous
	# tx data and this is not a coinbase tx then we need to get the previous tx
	# as a dict using the txin hash and txin index
	# TODO - split this into either getting the previous tx, or getting the
	# previous tx metadata, as per user requirements
	if (
		(not is_coinbase) and (
			("prev_txs_metadata" in required_info) or
			("prev_txs" in required_info) or
			("txin_funds" in required_info) or
			("txin_addresses" in required_info)
		)
	):
		get_previous_tx = True
	else:
		get_previous_tx = False

	tx["input"] = {} # init
	for j in range(0, num_inputs): # loop through all inputs
		tx["input"][j] = {} # init

		if "txin_single_spend_validation_status" in required_info:
			tx["input"][j]["single_spend_validation_status"] = None

		# if coinbase
		if is_coinbase:
			if "txin_coinbase_hash_validation_status" in required_info:
				tx["input"][j]["coinbase_hash_validation_status"] = None

			if "txin_coinbase_index_validation_status" in required_info:
				tx["input"][j]["coinbase_index_validation_status"] = None

			if "txin_coinbase_change_funds" in required_info:
				tx["input"][j]["coinbase_change_funds"] = None # init

		# if not coinbase
		else:
			if "txin_hash_validation_status" in required_info:
				tx["input"][j]["hash_validation_status"] = None

			if "txin_index_validation_status" in required_info:
				tx["input"][j]["index_validation_status"] = None

		if (
			get_previous_tx or
			("txin_hash" in required_info)
		):
			txin_hash = little_endian(block[pos: pos + 32])
		pos += 32

		if "txin_hash" in required_info:
			tx["input"][j]["hash"] = txin_hash

		if (
			get_previous_tx or
			("txin_index" in required_info)
		):
			txin_index = bin2int(little_endian(block[pos: pos + 4]))
		pos += 4

		if "txin_index" in required_info:
			tx["input"][j]["index"] = txin_index

		(txin_script_length, length) = decode_variable_length_int(
			block[pos: pos + 9]
		)
		pos += length
		if "txin_script_length" in required_info:
			tx["input"][j]["script_length"] = txin_script_length

		# always get the raw txin script, only get other script-related elements
		# if we are not looking at the coinbase tx
		if (
			("txin_script" in required_info) or (
				(not is_coinbase) and (
					("txin_script_list" in required_info) or
					("txin_parsed_script" in required_info) or
					("txin_script_format_validation_status" in required_info) or
					("txin_addresses" in required_info)
				)
			)
		):
			input_script = block[pos: pos + txin_script_length]
		pos += txin_script_length

		if "txin_script" in required_info:
			tx["input"][j]["script"] = input_script

		# parsing a txin script to a list can fail for coinbase, and that's ok -
		# thanks bitminter for releasing the first unparsable txin script in
		# block 241787 i guess haha
		if (
			(not is_coinbase) and (
				("txin_script_list" in required_info) or
				("txin_parsed_script" in required_info) or
				("txin_script_format_validation_status" in required_info) or
				("txin_addresses" in required_info)
			)
		):
			# convert string of bytes to list of bytes, return False upon fail
			txin_script_list = script_bin2list(input_script, explain_errors)
			
		if (
			(not is_coinbase) and
			("txin_script_list" in required_info)
		):
			if txin_script_list is False:
				# if there is an error then set the list to None
				tx["input"][j]["script_list"] = None
			else:
				tx["input"][j]["script_list"] = txin_script_list

		if (
			(not is_coinbase) and
			("txin_parsed_script" in required_info)
		):
			if txin_script_list is False:
				# if there is an error then set the parsed script to None
				tx["input"][j]["parsed_script"] = None
			else:
				# convert list of bytes to human readable string
				tx["input"][j]["parsed_script"] = script_list2human_str(
					txin_script_list
				)
		# coinbase input scripts have no use, so do not validate them
		if (
			(not is_coinbase) and
			("txin_script_format_validation_status" in required_info)
		):
			if txin_script_list is False:
				# if we get here then there is an error. log it and proceed
				tx["input"][j]["script_format_validation_status"] = \
				script_bin2list(input_script, explain_errors)
			else:
				# set to None - there may not be an error yet, but we don't know
				# if there will be an error later
				tx["input"][j]["script_format_validation_status"] = None

		if "txin_spend_from_non_orphan_validation_status" in required_info:
			tx["input"][j]["spend_from_non_orphan_validation_status"] = None

		if "txin_checksig_validation_status" in required_info:
			# init - may be updated later on once the script has been validated
			tx["input"][j]["checksig_validation_status"] = None

		if "txin_mature_coinbase_spend_validation_status" in required_info:
			tx["input"][j]["mature_coinbase_spend_validation_status"] = None

		# if the user wants to retrieve the txin funds, txin addresses or
		# previous tx data then we need to get the previous tx as a dict using
		# the txin hash and txin index
		if get_previous_tx:
			prev_txs_metadata = None # init
			prev_txs = None # init

			# attempt to get metadata from the tx_metadata files - contains some
			# irrelevant hashes
			prev_tx_metadata_csv = get_tx_metadata_csv(bin2hex(txin_hash))

			if prev_tx_metadata_csv:
				# filter out the relevant hash if it exists, if it does not
				# exist then its either because:
				# - the tx hash is in this block, or
				# - the txhash does not exist (fraudulent tx)
				# - someone has tampered with the tx metadata file
				prev_txs_metadata = filter_tx_metadata(
					tx_metadata_csv2dict(prev_tx_metadata_csv),
					bin2hex(txin_hash)
				)
			if prev_txs_metadata is not None:
				# get each previous tx with the specified hash (there might be
				# more than one per hash as tx hashes are not unique)
				prev_txs = {}
				for (block_hashend_txnum, prev_tx_metadata) in \
				prev_txs_metadata.items():
					prev_tx = get_transaction(bin2hex(txin_hash), "json")
					prev_tx_bin = hex2bin(prev_tx["hex"])

					prev_txs_metadata[block_hashend_txnum]["is_orphan"] = \
					is_orphan(hex2bin(prev_tx["blockhash"]))

					# fake the prev tx num
					if prev_tx_metadata["is_coinbase"] is None: # not coinbase
						fake_prev_tx_num = 1
					else: # if coinbase
						fake_prev_tx_num = 0

					# the block height is only used to calculate the mining
					# reward (txin funds) - not applicable here - use any value
					fake_prev_block_height = 0

					# make sure not to include txin info otherwise we'll get all
					# the recurring txs back to the original coinbase (which is
					# often enough to reach the python recursion limit and
					# crash)
					(prev_txs[block_hashend_txnum], _) = tx_bin2dict(
						prev_tx_bin, 0, all_txout_info + ["tx_hash"],
						fake_prev_tx_num, fake_prev_block_height, explain_errors
					)
		if "prev_txs_metadata" in required_info:
			if get_previous_tx:
				tx["input"][j]["prev_txs_metadata"] = prev_txs_metadata
			else:
				tx["input"][j]["prev_txs_metadata"] = None

		if "prev_txs" in required_info:
			if get_previous_tx:
				tx["input"][j]["prev_txs"] = prev_txs
			else:
				tx["input"][j]["prev_txs"] = None

		if "txin_funds" in required_info:
			if is_coinbase:
				tx["input"][j]["funds"] = mining_reward(block_height)
			elif (
				get_previous_tx and
				(prev_txs is not None)
			):
				# both previous txs are identical (use the last loop hashend).
				# note that "txin funds" is a non-existent binary entry in this
				# tx - it must be obtained from the previous txout.
				tx["input"][j]["funds"] = prev_txs[block_hashend_txnum] \
				["output"][txin_index]["funds"]
			else:
				tx["input"][j]["funds"] = None

		if (
			(not is_coinbase) and
			("txin_addresses" in required_info)
		):
			txin_addresses = None # init
			if (
				get_previous_tx and
				(prev_txs is not None)
			):
				# some operations require the combined [txin + txout] script
				prev_txout_script_list = prev_txs[block_hashend_txnum] \
				["output"][txin_index]["script_list"]

				full_script_list = txin_script_list + prev_txout_script_list
				format_type = extract_script_format(full_script_list)

				# at this stage only get addresses for standard scripts and do
				# not validate these scripts. later on we may (depending on user
				# settings, data availability and the type of scripts) attempt
				# to get any addresses that have been set to None.
				if format_type in ["scriptsig-pubkey", "sigpubkey-hash160"]:
					# no validation requested and a standard script means
					# get the addresses and set the validation status to None
					txin_addresses = script2addresses(
						full_script_list, format_type
					)
				if txin_addresses is None:
					format_type = extract_script_format(prev_txout_script_list)
					if format_type == "p2sh-txout":
						txin_addresses = script2addresses(
							prev_txout_script_list, format_type
						)

			tx["input"][j]["addresses"] = txin_addresses

		if "txin_sequence_num" in required_info:
			tx["input"][j]["sequence_num"] = bin2int(little_endian(
				block[pos: pos + 4]
			))
		pos += 4

		if not len(tx["input"][j]):
			del tx["input"][j]

	if not len(tx["input"]):
		del tx["input"]

	(num_outputs, length) = decode_variable_length_int(block[pos: pos + 9])
	if "num_tx_outputs" in required_info:
		tx["num_outputs"] = num_outputs
	pos += length

	if "txouts_exist_validation_status" in required_info:
		tx["txouts_exist_validation_status"] = None

	tx["output"] = {} # init
	for k in range(0, num_outputs): # loop through all outputs
		tx["output"][k] = {} # init

		if "txout_funds" in required_info:
			tx["output"][k]["funds"] = bin2int(little_endian(
				block[pos: pos + 8]
			))
		pos += 8

		(txout_script_length, length) = decode_variable_length_int(
			block[pos: pos + 9]
		)
		if "txout_script_length" in required_info:
			tx["output"][k]["script_length"] = txout_script_length
		pos += length

		if (
			("txout_script" in required_info) or
			("txout_script_list" in required_info) or
			("txout_parsed_script" in required_info) or
			("txout_script_format_validation_status" in required_info) or
			("txout_addresses" in required_info)
		):
			output_script = block[pos: pos + txout_script_length]
		pos += txout_script_length	

		if "txout_script" in required_info:
			tx["output"][k]["script"] = output_script

		if (
			("txout_script_list" in required_info) or
			("txout_parsed_script" in required_info) or
			("txout_script_format_validation_status" in required_info)
		):
			# convert string of bytes to list of bytes, return False upon fail
			script_list = script_bin2list(output_script, explain_errors)
			
		if "txout_script_list" in required_info:
			if script_list is False:
				# if there is an error then set the list to None
				tx["output"][k]["script_list"] = None
			else:
				tx["output"][k]["script_list"] = script_list

		if "txout_parsed_script" in required_info:
			if script_list is False:
				# if there is an error then set the parsed script to None
				tx["output"][k]["parsed_script"] = None
			else:
				# convert list of bytes to human readable string
				tx["output"][k]["parsed_script"] = script_list2human_str(
					script_list
				)
		if "txout_script_format_validation_status" in required_info:
			if script_list is False:
				# if we get here then there is an error
				tx["output"][k]["script_format_validation_status"] = \
				script_list
			else:
				# set to None - there may not be an error yet, but we don't know
				# if there will be an error later
				tx["output"][k]["script_format_validation_status"] = None

		if "txout_addresses" in required_info:
			if script_list is False:
				# if the script elements could not be parsed then we can't get
				# the addresses
				tx["output"][k]["addresses"] = None
			else:
				# return btc addresses or None
				tx["output"][k]["addresses"] = script2addresses(script_list)

		if "txout_address_checksums" in required_info:
			if tx["output"][k]["addresses"] is not None:
				tx["output"][k]["addresses_checksum_validation_status"] = {}
				for address in tx["output"][k]["addresses"]:
					# set to None - there may not be an error yet, but we don't
					# know if there will be an error later
					tx["output"][k]["addresses_checksum_validation_status"]\
					[address] = None
			else:
				# if there are no addresses then we will add this information
				# during the validation stage. for now, just mark this element
				# as None to indicate we have not tried to verify
				tx["output"][k]["addresses_checksum_validation_status"] = None

		if not len(tx["output"][k]):
			del tx["output"][k]

	if not len(tx["output"]):
		del tx["output"]

	if "tx_funds_balance_validation_status" in required_info:
		# None indicates that we have not tried to verify
		tx["funds_balance_validation_status"] = None

	if "tx_lock_time_validation_status" in required_info:
		# None indicates that we have not tried to verify
		tx["lock_time_validation_status"] = None

	if "tx_lock_time" in required_info:
		tx["lock_time"] = bin2int(little_endian(block[pos: pos + 4]))
	pos += 4

	if ("tx_bytes" in required_info) or ("tx_hash" in required_info):
		tx_bytes = block[init_pos: pos]

	if "tx_bytes" in required_info:
		tx["bytes"] = tx_bytes

	if "tx_hash" in required_info:
		tx["hash"] = little_endian(sha256(sha256(tx_bytes)))

	if "tx_size" in required_info:
		tx["size"] = pos - init_pos

	return (tx, pos - init_pos)

def block_dict2bin(block_arr):
	"""
	take a dict of the block and convert it to a binary string. elements of
	the block header may be ommitted and this function will return as much info
	as is available. this function is used before the nonce has been mined.
	"""

	output = "" # init
	if "format_version" not in block_arr:
		return output
	output += little_endian(int2bin(block_arr["format_version"], 4))

	if "previous_block_hash" not in block_arr:
		return output
	output += little_endian(block_arr["previous_block_hash"])

	if "merkle_root" in block_arr:
		calc_merkle_root = False
		output += little_endian(block_arr["merkle_root"])
	else:
		calc_merkle_root = True
		merkle_leaves = []
		output += blank_hash # will update later on in this function

	if "timestamp" not in block_arr:
		return output
	output += little_endian(int2bin(block_arr["timestamp"], 4))

	if "bits" not in block_arr:
		return output
	output += little_endian(block_arr["bits"])

	if "nonce" not in block_arr:
		return output
	output += little_endian(int2bin(block_arr["nonce"], 4))

	if "num_txs" in block_arr:
		num_txs = block_arr["num_txs"]
	else:
		if "tx" not in block_arr:
			return output
		num_txs = len(block_arr["tx"])
	output += encode_variable_length_int(num_txs)

	for tx_num in range(0, num_txs):
		tx_bytes = tx_dict2bin(block_arr["tx"][tx_num])
		output += tx_bytes
		if calc_merkle_root:
			tx_hash = little_endian(sha256(sha256(tx_bytes)))
			merkle_leaves.append(tx_hash)
	if calc_merkle_root:
		# update the merkle root in the output now
		merkle_root = calculate_merkle_root(merkle_leaves)
		output = output[: 36] + merkle_root + output[68:]
	return output

def tx_dict2bin(tx):
	"""take a dict of the transaction and convert it into a binary string"""

	output = little_endian(int2bin(tx["version"], 4))

	if "num_inputs" in tx:
		num_inputs = tx["num_inputs"]
	else:
		num_inputs = len(tx["input"])
	output += encode_variable_length_int(num_inputs)

	for j in range(0, num_inputs): # loop through all inputs
		output += little_endian(tx["input"][j]["hash"])
		output += little_endian(int2bin(tx["input"][j]["index"], 4))

		if "script_length" in tx["input"][j]:
			script_length = tx["input"][j]["script_length"]
		else:
			script_length = len(tx["input"][j]["script"])
		output += encode_variable_length_int(script_length)

		output += tx["input"][j]["script"]
		output += little_endian(int2bin(tx["input"][j]["sequence_num"], 4))

	if "num_outputs" in tx:
		num_outputs = tx["num_outputs"]
	else:
		num_outputs = len(tx["output"])
	output += encode_variable_length_int(num_outputs)

	for k in range(0, num_outputs): # loop through all outputs
		output += little_endian(int2bin(tx["output"][k]["funds"], 8))
		if "script_length" in tx["output"][k]:
			script_length = tx["output"][k]["script_length"]
		else:
			script_length = len(tx["output"][k]["script"])
		output += encode_variable_length_int(script_length)
		output += tx["output"][k]["script"]

	output += little_endian(int2bin(tx["lock_time"], 4))

	return output

def add_missing_prev_txs(parsed_block, required_info):
	"""
	if any prev_tx data could not be obtained from the tx_metadata dirs in the
	filesystem it could be because this data exists within the current block and
	has not yet been written to disk. if so then add it now.

	for efficiency in this function we do not want to create a list of all tx
	hashes until it is absolutely necessary. otherwise we will be creating this
	list for every single block, even when it is not needed.

	my guess is that this function will be most needed after a blockchain fork
	has been resolved, since the transactions from many blocks will then have to
	be put into 1 block and some of them are likely to reference each other.
	"""
	# if there is no requirement to add the missing prev_txs then exit here
	if (
		("prev_txs_metadata" not in required_info) and
		("prev_txs" not in required_info) and
		("txin_funds" not in required_info) and
		("txin_addresses" not in required_info)
	):
		return parsed_block

	all_block_tx_data = {} # init
	block_hashend = bin2hex(parsed_block["block_hash"][-2:])
	def get_tx_hash_data(parsed_block):
		# it is possible that more than one tx with the same hash exists within
		# the block. therefore, include the txnum in the key to keep it unique
		return {
			tx["hash"]: {tx_num: {
				"is_coinbase": 1 if (tx_num == 0) else None,
				"spending_txs_list": [None] * tx["num_outputs"],
				# careful not to include the txin here otherwise we will get
				# its prev_tx and so on
				"this_txout": tx["output"]
			}} for (tx_num, tx) in parsed_block["tx"].items()
		}
	is_orphan = None # unknowable at this stage, update later as required
	for (tx_num, tx) in sorted(parsed_block["tx"].items()):
		# coinbase txs have no previous tx data
		if tx_num == 0:
			continue

		for (txin_num, txin) in tx["input"].items():
			if (
				("prev_txs_metadata" in required_info) and
				(txin["prev_txs_metadata"] is None)
			):
				# if we don't yet have all block tx data then get it now
				if not all_block_tx_data:
					all_block_tx_data = get_tx_hash_data(parsed_block)

				if txin["hash"] in all_block_tx_data:
					parsed_block["tx"][tx_num]["input"][txin_num] \
					["prev_txs_metadata"] = {} # init
					for (prev_tx_num, prev_tx_data) in \
					all_block_tx_data[txin["hash"]].items():
						block_hashend_txnum = "%s-%s" % (
							block_hashend, prev_tx_num
						)
						parsed_block["tx"][tx_num]["input"][txin_num] \
						["prev_txs_metadata"][block_hashend_txnum] = {
							# prev tx comes from the same block
							"block_height": parsed_block["block_height"],
							# data on prev tx comes from the temp dict
							"is_coinbase": prev_tx_data["is_coinbase"],
							"is_orphan": is_orphan,
							# no need to update the spending txs list here
							"spending_txs_list": prev_tx_data \
							["spending_txs_list"]
						}

			# get any more txs with the same hash from this same block
			# TODO - test and make sure we get here even if prev txs already exist
			if (
				("prev_txs" in required_info) and
				(txin["prev_txs"] is None)
			):
				# if we don't yet have all block tx data then get it now
				if not all_block_tx_data:
					all_block_tx_data = get_tx_hash_data(parsed_block)

				if txin["hash"] in all_block_tx_data:
					parsed_block["tx"][tx_num]["input"][txin_num] \
					["prev_txs"] = {} # init
					for (prev_tx_num, prev_tx_data) in \
					all_block_tx_data[txin["hash"]].items():
						hashend_txnum = "%s-%s" % (block_hashend, prev_tx_num)
						# store the same data that is stored in tx_bin2dict()
						parsed_block["tx"][tx_num]["input"][txin_num] \
						["prev_txs"][hashend_txnum] = {
							"hash": txin["hash"],
							"output": prev_tx_data["this_txout"]
						}

			if (
				("txin_funds" in required_info) and
				(txin["funds"] is None)
			):
				# if we don't yet have all block tx data then get it now
				if not all_block_tx_data:
					all_block_tx_data = get_tx_hash_data(parsed_block)

				if txin["hash"] in all_block_tx_data:
					for (prev_tx_num, prev_tx_data) in \
					all_block_tx_data[txin["hash"]].items():
						parsed_block["tx"][tx_num]["input"][txin_num] \
						["funds"] = prev_tx_data["this_txout"][txin["index"]] \
						["funds"]
						break # all tx data is identical

			if (
				("txin_addresses" in required_info) and
				(txin["addresses"] is None)
			):
				# if we don't yet have all block tx data then get it now
				if not all_block_tx_data:
					all_block_tx_data = get_tx_hash_data(parsed_block)

				if txin["hash"] in all_block_tx_data:
					for (prev_tx_num, prev_tx_data) in \
					all_block_tx_data[txin["hash"]].items():
						parsed_block["tx"][tx_num]["input"][txin_num] \
						["addresses"] = prev_tx_data["this_txout"] \
						[txin["index"]]["addresses"]
						break # all tx data is identical

	return parsed_block

def validate_block_elements_type_len(block_arr, bool_result = False):
	"""validate a block's type and length. block must be input as a dict."""
	if not bool_result:
		errors = []

	if "format_version" in block_arr:
		if not isinstance(block_arr["format_version"], (int, long)):
			if bool_result:
				return False
			errors.append(
				"Error: format_version must be an int. %s supplied."
				% type(block_arr["format_version"])
			)
	else:
		errors.append("Error: element format_version must exist in block.")

	if "previous_block_hash" in block_arr:
		if not isinstance(block_arr["previous_block_hash"], str):
			if bool_result:
				return False
			errors.append(
				"Error: previous_block_hash must be a string. %s supplied."
				% type(block_arr["previous_block_hash"])
			)
		if len(block_arr["previous_block_hash"]) != 32:
			if bool_result:
				return False
			errors.append("Error: previous_block_hash must be 32 bytes long.")
	else:
		errors.append("Error: element previous_block_hash must exist in block.")

	if "merkle_root" in block_arr:
		if not isinstance(block_arr["merkle_root"], str):
			if bool_result:
				return False
			errors.append(
				"Error: merkle_root must be a string. %s supplied."
				% type(block_arr["merkle_root"])
			)
		if len(block_arr["merkle_root"]) != 32:
			if bool_result:
				return False
			errors.append("Error: merkle_root must be 32 bytes long.")
	# else: this element is not mandatory since it can be derived from the
	# transaction hashes

	if "timestamp" in block_arr:
		if not isinstance(block_arr["timestamp"], (int, long)):
			if bool_result:
				return False
			errors.append(
				"Error: timestamp must be an int. %s supplied."
				% type(block_arr["timestamp"])
			)
	else:
		errors.append("Error: element timestamp must exist in block.")

	if "bits" in block_arr:
		if not isinstance(block_arr["bits"], str):
			if bool_result:
				return False
			errors.append(
				"Error: bits must be a string. %s supplied."
				% type(block_arr["bits"])
			)
		if len(block_arr["bits"]) != 4:
			if bool_result:
				return False
			errors.append("Error: bits must be 4 bytes long.")
	else:
		errors.append("Error: element bits must exist in block.")

	if "nonce" in block_arr:
		if not isinstance(block_arr["nonce"], (int, long)):
			if bool_result:
				return False
			errors.append(
				"Error: nonce must be an int. %s supplied."
				% type(block_arr["nonce"])
			)
	else:
		errors.append("Error: element nonce must exist in block.")

	if "num_txs" in block_arr:
		if block_arr["num_txs"] != len(block_arr["tx"]):
			if bool_result:
				return False
			errors.append(
				"Error: num_txs is different to the actual number of"
				" transactions."
			)
	# else: this element is not mandatory since it can be derived by counting
	# the transactions

	for tx_dict in block_arr["tx"].values():
		tx_errors = validate_tx_elements_type_len(tx_dict)
		if tx_errors:
			if bool_result:
				return False
			errors = list(set(errors + tx_errors)) # unique

	if (
		not errors and
		bool_result
	):
		errors = True # block is valid
	return errors

def validate_tx_elements_type_len(tx, explain = False):
	"""
	return True if all tx elements are valid (eg type and length). if any tx
	elements are not valid then either return False if the explain argument is
	not set, otherwise return a list of human readable strings with explanations
	of the failure.

	transaction must be input as a dict.
	"""
	if explain:
		errors = []

	if "version" in tx:
		if not isinstance(tx["version"], (int, long)):
			if not explain:
				return False
			errors.append(
				"Error: transaction version must be an int. %s supplied."
				% type(tx["version"])
			)
	else:
		errors.append("Error: transaction version does not exist.")

	if "num_tx_inputs" in tx:
		if tx["num_tx_inputs"] != len(tx["input"]):
			if not explain:
				return False
			errors.append(
				"Error: num_tx_inputs is different to the actual number of"
				" transaction inputs."
			)
	# else: this element is not mandatory since it can be derived by counting
	# the transaction inputs

	#for tx_input in tx["input"].values(): # loop through all inputs
	for txin in tx["input"].values(): # loop through all inputs

		if "verification_attempted" in txin:
			if not isinstance(txin["verification_attempted"], bool):
				if not explain:
					return False
				errors.append(
					"Error: input element verification_attempted must be a"
					" bool. %s supplied."
					% type(txin["verification_attempted"])
				)
		# else: this element is totally optional

		if "verification_succeeded" in txin:
			if not isinstance(txin["verification_succeeded"], bool):
				if not explain:
					return False
				errors.append(
					"Error: input element verification_succeeded must be a"
					" bool. %s supplied."
					% type(txin["verification_succeeded"])
				)
		# else: this element is totally optional

		if "funds" in txin:
			if not isinstance(txin["funds"], (int, long)):
				if not explain:
					return False
				errors.append(
					"Error: input funds must be an int. %s supplied."
					% type(txin["funds"])
				)
			elif txin["funds"] < 0:
				if not explain:
					return False
				errors.append("Error: input funds must be a positive int.")
		# else: this element is totally optional

		if "hash" in txin:
			if not isinstance(txin["hash"], str):
				if not explain:
					return False
				errors.append(
					"Error: input hash must be a string. %s supplied."
					% type(txin["hash"])
				)
			elif len(txin["hash"]) != 32:
				if not explain:
					return False
				errors.append("Error: input hash must be 32 bytes long.")
		else:
			errors.append(
				"Error: hash element must exist in transaction input."
			)

		if "index" in txin:
			if not isinstance(txin["index"], (int, long)):
				if not explain:
					return False
				errors.append(
					"Error: input index must be an int. %s supplied."
					% type(txin["index"])
				)
			elif txin["index"] < 0:
				if not explain:
					return False
				errors.append("Error: input index must be a positive int.")
		else:
			errors.append(
				"Error: index element must exist in transaction input."
			)

		if "script_length" in txin:
			script_length_ok = True
			if not isinstance(txin["script_length"], (int, long)):
				if not explain:
					return False
				errors.append(
					"Error: input script_length must be an int. %s supplied."
					% type(txin["script_length"])
				)
				script_length_ok = False
			elif txin["script_length"] < 0:
				if not explain:
					return False
				errors.append(
					"Error: input script_length must be a positive int."
				)
				script_length_ok = False
		else:
			script_length_ok = False
			# this element is not mandatory since it can be derived by counting
			# the bytes in the script element

		if "script" in txin:
			if not isinstance(txin["script"], str):
				if not explain:
					return False
				errors.append(
					"Error: input script must be a string. %s supplied."
					% type(txin["script"])
				)
			elif (
				script_length_ok and
				(len(txin["script"]) != txin["script_length"])
			):
				if not explain:
					return False
				errors.append(
					"Error: input script must be %s bytes long, but it is %s."
					% (txin["script_length"], len(txin["script"]))
				)
		else:
			errors.append(
				"Error: script element must exist in transaction input."
			)

		if "addresses" in txin:
			if not isinstance(txin["addresses"], list):
				if not explain:
					return False
				errors.append(
					"Error: input addresses must be a list. %s supplied."
					% type(txin["addresses"])
				)
			else:
				for address in txin["addresses"]:
					if len(address) != 34:
						if not explain:
							return False
						errors.append(
							"Error: all input addresses must be 34 characters"
							" long. %s is %s characters long"
							% (address, len(address))
						)
		# else: this element is totally optional

		if "sequence_num" in txin:
			if not isinstance(txin["sequence_num"], (int, long)):
				if not explain:
					return False
				errors.append(
					"Error: input sequence_num must be an int. %s supplied."
					% type(txin["sequence_num"])
				)
			elif txin["sequence_num"] < 0:
				if not explain:
					return False
				errors.append(
					"Error: input sequence_num must be a positive int."
				)
		else:
			errors.append(
				"Error: sequence_num element must exist in transaction input."
			)

	if "num_tx_outputs" in tx:
		if tx["num_tx_outputs"] != len(tx["output"]):
			if not explain:
				return False
			errors.append(
				"Error: num_tx_outputs is different to the actual number of"
				" transaction outputs."
			)
	# else: this element is not mandatory since it can be derived by counting
	# the transaction outputs

	for txout in tx["output"].values(): # loop through all outputs

		if "funds" in txout:
			if not isinstance(txout["funds"], (int, long)):
				if not explain:
					return False
				errors.append(
					"Error: output funds must be an int. %s supplied."
					% type(txout["funds"])
				)
			elif txout["funds"] < 0:
				if not explain:
					return False
				errors.append("Error: output funds must be a positive int.")
		else:
			errors.append(
				"Error: funds element must exist in transaction output."
			)

		if "script_length" in txout:
			script_length_ok = True
			if not isinstance(txout["script_length"], (int, long)):
				if not explain:
					return False
				errors.append(
					"Error: output script_length must be an int. %s supplied."
					% type(txout["script_length"])
				)
				script_length_ok = False
			elif txout["script_length"] < 0:
				if not explain:
					return False
				errors.append(
					"Error: output script_length must be a positive int."
				)
				script_length_ok = False
		else:
			script_length_ok = False
			# this element is not mandatory since it can be derived by counting
			# the bytes in the script element

		if "script" in txout:
			if not isinstance(txout["script"], str):
				if not explain:
					return False
				errors.append(
					"Error: output script must be a string. %s supplied."
					% type(txout["script"])
				)
			elif (
				script_length_ok and
				(len(txout["script"]) != txout["script_length"])
			):
				if not explain:
					return False
				errors.append(
					"Error: output script must be %s bytes long, but it is %s."
					% (txout["script_length"], len(txout["script"]))
				)
		else:
			errors.append(
				"Error: script element must exist in transaction output."
			)

		if "addresses" in txout:
			if not isinstance(txout["address"], list):
				if not explain:
					return False
				errors.append(
					"Error: output addresses must be a list. %s supplied."
					% type(txout["addresses"])
				)
			else:
				for address in txout["addresses"]:
					if len(address) != 34:
						if not explain:
							return False
						errors.append(
							"Error: all output addresses must be 34 characters"
							" long. %s is %s characters long"
							% (address, len(address))
						)
		# else: this element is totally optional

	if "lock_time" in tx:
		if not isinstance(tx["lock_time"], (int, long)):
			if not explain:
				return False
			errors.append(
				"Error: transaction lock_time must be an int. %s supplied."
				% type(tx["lock_time"])
			)
		elif tx["lock_time"] < 0:
			if not explain:
				return False
			errors.append(
				"Error: transaction lock_time must be a positive int."
			)

	if "hash" in tx:
		if not isinstance(tx["hash"], str):
			if not explain:
				return False
			errors.append(
				"Error: transaction hash must be a string. %s supplied."
				% type(tx["hash"])
			)
		elif len(tx["hash"]) != 32:
			if not explain:
				return False
			errors.append("Error: transaction hash must be a 32 bytes long.")
	# else: this element is not mandatory since it can be derived by hashing all
	# transaction bytes

	"""
	if "size" in tx:
		if not isinstance(tx["size"], (int, long)):
			if not explain:
				return False
			errors.append(
				"Error: transaction size must be an int. %s supplied."
				% type(tx["size"])
			)
		elif tx["size"] < 0:
			if not explain:
				return False
			errors.append("Error: transaction size must be a positive int.")
	# else: this element is not mandatory since it can be derived by counting
	# the bytes in the whole transaction
	"""

	if (
		explain and
		not errors
	):
		return True

	if not explain:
		return True

	return errors

def human_readable_block(block, options = None):
	"""return a human readable dict"""

	if isinstance(block, dict):
		parsed_block = copy.deepcopy(block)
	else:
		output_info = copy.deepcopy(all_block_and_validation_info)

		# the parsed script will still be returned, but these raw scripts will
		# not
		output_info.remove("txin_script")
		output_info.remove("txout_script")
		output_info.remove("tx_bytes")
		output_info.remove("txin_script_list")
		output_info.remove("txout_script_list")

		# bin encoded string to a dict (some elements still not human readable)
		parsed_block = block_bin2dict(block, output_info, options)

	# convert any remaining binary encoded elements
	parsed_block["block_hash"] = bin2hex(parsed_block["block_hash"])
	parsed_block["previous_block_hash"] = bin2hex(
		parsed_block["previous_block_hash"]
	)
	parsed_block["merkle_root"] = bin2hex(parsed_block["merkle_root"])
	parsed_block["bits"] = bin2int(parsed_block["bits"])

	if "bytes" in parsed_block:
		del parsed_block["bytes"]

	# there will always be at least one transaction per block
	for (tx_num, tx) in parsed_block["tx"].items():
		parsed_block["tx"][tx_num] = human_readable_tx(
			tx, tx_num, parsed_block["block_height"]
		)
	return parsed_block

def human_readable_tx(tx, tx_num, block_height):
	"""take the input binary tx and return a human readable dict"""

	if isinstance(tx, dict):
		parsed_tx = copy.deepcopy(tx)
	else:
		output_info = copy.deepcopy(all_tx_info)

		# return the parsed script, but not these raw scripts
		output_info.remove("txin_script")
		output_info.remove("txout_script")
		output_info.remove("tx_bytes")
		output_info.remove("txin_script_list")
		output_info.remove("txout_script_list")

		# bin encoded string to a dict (some elements still not human readable)
		(parsed_tx, _) = tx_bin2dict(tx, 0, output_info, tx_num, block_height)

	# convert any remaining binary encoded elements
	parsed_tx["hash"] = bin2hex(parsed_tx["hash"])

	if "bytes" in parsed_tx:
		del parsed_tx["bytes"]

	for (txin_num, txin) in parsed_tx["input"].items():
		parsed_tx["input"][txin_num]["hash"] = bin2hex(txin["hash"])
		if "script" in txin:
			del parsed_tx["input"][txin_num]["script"]
		if "script_list" in txin:
			del parsed_tx["input"][txin_num]["script_list"]
		if "prev_txs" in txin:
			del parsed_tx["input"][txin_num]["prev_txs"]

	for (txout_num, txout) in parsed_tx["output"].items():
		if "script" in txout:
			del parsed_tx["output"][txout_num]["script"]
		if "script_list" in txout:
			del parsed_tx["output"][txout_num]["script_list"]

	return parsed_tx

"""
def gather_transaction_data(tx):
	"" "
	fetch the following data from the blockchain that is required to construct
	this transaction:
	- the available funds
	- all previous hashes
	- all previous indexes
	- all previous output scripts
	"" "
	from_addresses = [] # init
	for input_num in tx["input"]:
		from_addresses.append(tx["input"][input_num]["address"])

	get_full_blocks(options, sanitized = False)
	
def create_transaction(prev_tx_hash, prev_txout_index, prev_tx_ecdsa_private_key, to_address, btc):
	"" "create a 1-input, 1-output transaction to broadcast to the network. untested! always compare to bitcoind equivalent before use" ""
	raw_version = struct.pack('<I', 1) # version 1 - 4 bytes (little endian)
	raw_num_inputs = encode_variable_length_int(1) # one input only
	if len(prev_tx_hash) != 64:
		lang_grunt.die('previous transaction hash should be 32 bytes')
	raw_prev_tx_hash = binascii.a2b_hex(prev_tx_hash) # previous transaction hash
	raw_prev_txout_index = struct.pack('<I', prev_txout_index)
	from_address = '' ############## use private key to get it
	temp_scriptsig = from_address
	raw_input_script_length = encode_variable_length_int(len(temp_scriptsig))
	raw_sequence_num = binascii.a2b_hex('ffffffff')
	raw_num_outputs = encode_variable_length_int(1) # one output only
	raw_satoshis = struct.pack('<Q', (btc - 0.001) * satoshi_per_btc) # 8 bytes (little endian)
	to_address_hashed = address2hash160(to_address)
	output_script = unparse_script('OP_DUP OP_HASH160 OP_PUSHDATA(xxx) ' + to_address_hashed + ' OP_EQUALVERIFY OP_CHECKSIG') # convert to hex
	raw_output_script = binascii.a2b_hex(output_script)
	raw_output_script_length = encode_variable_length_int(len(raw_output_script))
	raw_locktime = binascii.a2b_hex('00000000')
	raw_hashcode = binascii.a2b_hex('01000000') # ????
	temp_tx = raw_version + raw_num_inputs + raw_prev_tx_hash + raw_prev_txout_index + raw_input_script_length + temp_scriptsig + raw_sequence_num + raw_num_outputs + raw_satoshis + raw_output_script + raw_output_script_length + raw_locktime + raw_hashcode
	tx_hash = double_sha256(temp_tx)
	signature = der_encode(ecdsa_sign(tx_hash, prev_tx_private_key)) + '01' # TODO - der encoded
	signature_length = len(signature)
	if signature_length > 75:
		lang_grunt.die('signature cannot be longer than 75 bytes: [' + signature + ']')
	final_scriptsig = stuct.pack('B', signature_length) + signature + raw_input_script_length + from_address
	input_script_length = len(final_scriptsig) # overwrite
	if input_script_length > 75:
		lang_grunt.die('input script cannot be longer than 75 bytes: [' + final_script + ']')
	raw_input_script = struct.pack('B', input_script_length) + final_script
	signed_tx = raw_version + raw_num_inputs + raw_prev_tx_hash + raw_prev_txout_index + raw_input_script_length + final_scriptsig + raw_sequence_num + raw_num_outputs + raw_satoshis + raw_output_script + raw_output_script_length + raw_locktime
"""

def calculate_tx_change(parsed_block):
	"""
	calculate the total change from all txs in the block, excluding the coinbase
	tx. if there is only one tx (the coinbase tx) then return None. if any txin
	funds are not yet known then also return None. this can occur when a tx
	spends from the same block. in this instance this function will be called
	again later on once the data becomes available.
	"""
	change = 0 # init
	for (tx_num, tx) in sorted(parsed_block["tx"].items()):
		if tx_num == 0:
			continue

		change += sum(txin["funds"] for txin in tx["input"].values())
		change -= sum(txout["funds"] for txout in tx["output"].values())

	return change

def calculate_block_hash(block_bytes):
	"""calculate the block hash from the first 80 bytes of the block"""
	return little_endian(sha256(sha256(block_bytes[0: 80])))

def should_get_non_standard_script_addresses(options, parsed_block):
	"""
	check if we should get the non standard addresses from this block. there are
	two basic criteria:
	- options.ADDRESSES is set and,
	- this block has undefined addresses
	"""
	if options.ADDRESSES is None:
		return False

	for (tx_num, tx) in sorted(parsed_block["tx"].items()):
		# coinbase txs have no txin address
		if tx_num == 0:
			continue
		for (txin_num, txin) in tx["input"].items():
			if (
				("addresses" in txin) and
				(txin["addresses"] is None)
			):
				return True

	return False

def should_validate_block(options, parsed_block, saved_validation_data):
	"""
	check if this block should be validated. there are two basic criteria:
	- options.validate is set and,
	- this block has not yet been validated
	"""
	if options.validate is None:
		return False
	
	if latest_validated_block_data is None:
		return True

	(
		saved_validation_block_hash, latest_validated_block_pos
	) = saved_validation_data

	# if this block has not yet been validated...
	if (
		(parsed_block["block_filenum"] >= latest_validated_block_filenum) and
		(parsed_block["block_pos"] > latest_validated_block_pos)
	):
		return True

	return False

def enforce_valid_block(parsed_block, options):
	# now that all validations have been performed, die if anything failed
	invalid_block_elements = valid_block_check(parsed_block)
	if invalid_block_elements is not None:
		block_human_str = get_formatted_data(options, {
			parsed_block["block_hash"]: parsed_block
		})
		num_invalid = len(invalid_block_elements)
		# wrap each element in quotes
		invalid_block_elements = ["'%s'" % x for x in invalid_block_elements]
		raise Exception(
			"Validation error. Element%s %s in the following block %s been"
			" found to be invalid:%s%s"
			% (
				lang_grunt.plural("s", num_invalid),
				lang_grunt.list2human_str(invalid_block_elements, "and"),
				lang_grunt.plural("have", num_invalid), os.linesep,
				block_human_str
			)
		)

def validate_block(parsed_block, block_1_ago, bugs_and_all, explain = False):
	"""
	validate everything except the orphan status of the block (this way we can
	validate before waiting coinbase_maturity blocks to check the orphan status)

	the *_validation_status determines the types of validations to perform. see
	the block_header_validation_info variable at the top of this file for the
	full list of possibilities. for this reason, only parsed blocks can be
	passed to this function.

	if the explain argument is set then set the *_validation_status element
	values to human readable strings when there is a failure, otherwise to True.

	if the explain argument is not set then set the *_validation_status element
	values to False when there is a failure otherwise to True.

	if there are any undefined txin addresses then assign these in this function

	based on https://en.bitcoin.it/wiki/Protocol_rules
	"""
	# make sure the block is smaller than the permitted maximum
	if "block_size_validation_status" in parsed_block:
		parsed_block["block_size_validation_status"] = valid_block_size(
			parsed_block, explain
		)
	# make sure the transaction hashes form the merkle root when sequentially
	# hashed together
	if "merkle_root_validation_status" in parsed_block:
		parsed_block["merkle_root_validation_status"] = valid_merkle_tree(
			parsed_block, explain
		)
	# make sure the target is valid based on previous network hash performance
	if "bits_validation_status" in parsed_block:
		parsed_block["bits_validation_status"] = valid_bits(
			parsed_block, block_1_ago, explain
		)
	# make sure the block hash is below the target
	if "block_hash_validation_status" in parsed_block:
		parsed_block["block_hash_validation_status"] = valid_block_hash(
			parsed_block, explain
		)
	# make sure the difficulty is valid	
	if "difficulty_validation_status" in parsed_block:
		parsed_block["difficulty_validation_status"] = valid_difficulty(
			parsed_block, explain
		)
	# use this var to keep track of txs that have been spent within this very
	# block. we don't want to mark any txs as spent until we know that the whole
	# block is valid (ie that the funds are permitted to be spent). it is in the
	# format {spendee_hash: [spendee_index, spender_hash,  spender_index]}
	spent_txs = {}

	for (tx_num, tx) in sorted(parsed_block["tx"].items()):
		(parsed_block["tx"][tx_num], spent_txs) = validate_tx(
			tx, tx_num, spent_txs, parsed_block["block_height"],
			parsed_block["timestamp"], bugs_and_all, explain
		)
	return parsed_block

def validate_tx(
	tx, tx_num, spent_txs, block_height, block_time, bugs_and_all,
	explain = False
):
	"""
	the *_validation_status determines the types of validations to perform. see
	the all_tx_validation_info variable at the top of this file for the full
	list of possibilities. for this reason, only parsed blocks can be passed to
	this function.

	if the explain argument is set then set the *_validation_status element
	values to human readable strings when there is a failure, otherwise to True.

	if the explain argument is not set then set the *_validation_status element
	values to False when there is a failure otherwise to True.

	based on https://en.bitcoin.it/wiki/Protocol_rules
	"""
	txins_exist = False # init
	txouts_exist = False # init

	# the first transaction is always coinbase (mined)
	is_coinbase = True if (tx_num == 0) else False

	sequence_nums = [] # init
	for (txin_num, txin) in sorted(tx["input"].items()):
		txins_exist = True
		spendee_hash = txin["hash"]
		spendee_index = txin["index"]
		sequence_nums.append(txin["sequence_num"])

		if is_coinbase:
			if "coinbase_hash_validation_status" in txin:
				txin["coinbase_hash_validation_status"] = \
				valid_coinbase_hash(spendee_hash, explain)

			if "coinbase_index_validation_status" in txin:
				txin["coinbase_index_validation_status"] = \
				valid_coinbase_index(spendee_index, explain)

			# no more txin checks required for coinbase transactions
			# merge the results back into the tx return var
			tx["input"][txin_num] = txin
			continue

		# not a coinbase tx from here on...
		spendee_txs_metadata = txin["prev_txs_metadata"]
		prev_txs = txin["prev_txs"]
		hashend_txnum0 = prev_txs.keys()[0]
		prev_tx0 = prev_txs[hashend_txnum0]

		# check if each transaction (hash) being spent actually exists. use any
		# tx since they both have identical data
		status = valid_txin_hash(spendee_hash, prev_tx0, explain)
		if "hash_validation_status" in txin:
			txin["hash_validation_status"] = status
		if status is not True:
			# merge the results back into the tx return var
			tx["input"][txin_num] = txin
			continue

		# from this point onwards the tx being spent definitely exists.

		# check if the transaction (index) being spent actually exists. use any
		# tx since they both have identical data
		status = valid_txin_index(spendee_index, prev_tx0, explain)
		if "index_validation_status" in txin:
			txin["index_validation_status"] = status
		if status is not True:
			# merge the results back into the tx return var
			tx["input"][txin_num] = txin
			continue

		# check if the transaction we are spending from has already been spent
		# in an earlier block. careful here as tx hashes are not unique. only
		# fail if all hashes have been spent.
		all_spent = True # init
		for (hashend_txnum, spendee_tx_metadata) in \
		spendee_txs_metadata.items():
			# returns True if the tx has never been spent before
			status = valid_tx_spend(
				spendee_tx_metadata, spendee_hash, spendee_index, tx["hash"],
				txin_num, spent_txs, explain
			)
			if status is True:
				# if this tx has not been spent before
				all_spent = False
				break
			else:
				# if this tx has been spent before
				spent_status = status

		# use the last available status
		if all_spent:
			if "single_spend_validation_status" in txin:
				txin["single_spend_validation_status"] = spent_status
			# merge the results back into the tx return var
			tx["input"][txin_num] = txin
			continue
		else:
			if "single_spend_validation_status" in txin:
				txin["single_spend_validation_status"] = True
			
		# check if any of the txs being spent is in an orphan block. this
		# script's validation process halts if any other form of invalid block
		# is encountered, so there is no need to worry about previous double-
		# -spends on the main chain, etc.
		any_orphans = False # init
		for (hashend_txnum, spendee_tx_metadata) in \
		spendee_txs_metadata.items():
			status = valid_spend_from_non_orphan(
				spendee_tx_metadata["is_orphan"], spendee_hash, explain
			)
			if status is not True:
				any_orphans = True
				break

		if "spend_from_non_orphan_validation_status" in txin:
			txin["spend_from_non_orphan_validation_status"] = status
		if any_orphans:
			# merge the results back into the tx return var
			tx["input"][txin_num] = txin
			continue

		# check that this txin is allowed to spend the referenced prev_tx. use
		# any previous tx since they all have identical data
		try:
			script_eval_data = verify_script(
				tx, txin_num, prev_tx0, bugs_and_all, explain
			)
		except:
			raise Exception(
				"failed to validate script for txin %d in tx %d (hash %s)" \
				% (txin_num, tx_num, bin2hex(tx["hash"]))
			)
		if "checksig_validation_status" in txin:
			txin["checksig_validation_status"] = script_eval_data["status"]
		if script_eval_data["status"] is not True:
			# merge the results back into the tx return var
			tx["input"][txin_num] = txin
			continue

		# only keep valid txin addresses
		if "addresses" in txin:
			txin["addresses"] = script_dict2addresses(script_eval_data, "valid")

		# if a coinbase transaction is being spent then make sure it has already
		# reached maturity. do this for all previous txs
		any_immature = False
		for (hashend_txnum, spendee_tx_metadata) in \
		spendee_txs_metadata.items():
			status = valid_mature_coinbase_spend(
				block_height, spendee_tx_metadata, explain
			)
			if status is not True:
				any_immature = True
				break

		if "mature_coinbase_spend_validation_status" in txin:
			txin["mature_coinbase_spend_validation_status"] = status
		if any_immature:
			# merge the results back into the tx return var
			tx["input"][txin_num] = txin
			continue

		# merge the results back into the tx return var
		tx["input"][txin_num] = txin

		# format {spendee_hash: [spendee_index, spender_hash,  spender_index]}
		spent_txs[spendee_hash] = [spendee_index, tx["hash"], txin_num]

		# end of txins for-loop

	if "txins_exist_validation_status" in tx:
		tx["txins_exist_validation_status"] = valid_txins_exist(
			txins_exist, explain
		)
	# make sure the locktime is valid
	if "lock_time_validation_status" in tx:
		tx["lock_time_validation_status"] = valid_locktime(
			tx["lock_time"], block_time, block_height, sequence_num, explain
		)

	for (txout_num, txout) in sorted(tx["output"].items()):
		txouts_exist = True
		# this happens when txout script cannot be converted to a list. it
		# should not happen in the live blockchain
		if txout["script_list"] is None:
			raise Exception(
				"tx with hash %s has no output script in txout %s. txout"
				" script: %s"
				% (bin2hex(tx["hash"]), txout_num, txout["script"])
			)
		if "script_format_validation_status" in txout:
			txout["script_format_validation_status"] = valid_script_format(
				txout["script_list"], explain
			)
		# validate the output addresses in standard txs
		if "addresses_checksum_validation_status" in txout:
			if txout["addresses"] is None:
				# there are no addresses to validate, this is still valid
				txout["addresses_checksum_validation_status"] = None
			else:
				for address in txout["addresses"]:
					txout["addresses_checksum_validation_status"][address] = \
					valid_address_checksum(address, explain)

		# merge the results back into the tx return var
		tx["output"][txout_num] = txout

		# end of txouts for-loop

	if "txouts_exist_validation_status" in tx:
		tx["txouts_exist_validation_status"] = valid_txouts_exist(
			txouts_exist, explain
		)
	if "funds_balance_validation_status" in tx:
		tx["funds_balance_validation_status"] = valid_tx_balance(tx, explain)
	return (tx, spent_txs)

def valid_block_check(parsed_block):
	"""
	return None if the block is valid, otherwise return a list of validation
	errors. this function is only accurate if the parsed_block input argument
	comes from function valid_block().

	all elements which are named like '...validation_status' are either:
	- set to True if they have been checked and did pass
	- set to False if they have been checked, did not pass, and the user did not
	request an explanation
	- set to None if they have not been checked
	- set to a string if they have been checked, did not pass, and the user
	requested an explanation
	"""
	invalid_elements = []
	for (k, v) in parsed_block.items():
		if (
			("validation_status" in k) and
			(v is not True) and
			(v is not None)
		):
			invalid_elements.append(k)

		if k == "tx":
			for tx in parsed_block["tx"].values():
				for (k, v) in tx.items():
					if (
						("validation_status" in k) and
						(v is not True) and
						(v is not None)
					):
						invalid_elements.append(k)

				for txin in tx["input"].values():
					for (k, v) in txin.items():
						if (
							("validation_status" in k) and
							(v is not True) and
							(v is not None)
						):
							invalid_elements.append(k)

				for txout in tx["output"].values():
					for (k, v) in txin.items():
						if (
							("validation_status" in k) and
							(v is not True) and
							(v is not None)
						):
							invalid_elements.append(k)

	return None if not invalid_elements else list(set(invalid_elements))
			
def valid_block_size(block, explain = False):
	if isinstance(block, dict):
		parsed_block = block
	else:
		parsed_block = block_bin2dict(block, ["size"])

	if parsed_block["size"] <= max_block_size:
		return True
	else:
		if explain:
			return "block size (%s bytes) is larger than the maximum" \
			" permitted size of %s bytes." \
			% (parsed_block["size"], max_block_size)
		else:
			return False

def valid_merkle_tree(block, explain = False):
	"""
	return True if the block has a valid merkle root. if the merkle root is not
	valid then either return False if the explain argument is not set, otherwise
	return a human readable string with an explanation of the failure.
	"""
	if isinstance(block, dict):
		parsed_block = block
	else:
		parsed_block = block_bin2dict(block, ["merkle_root", "tx_hash"])

	# assume there is at least one transaction in this block
	merkle_leaves = [tx["hash"] for tx in parsed_block["tx"].values()]
	calculated_merkle_root = calculate_merkle_root(merkle_leaves)

	if calculated_merkle_root == parsed_block["merkle_root"]:
		return True
	else:
		if explain:
			return "bad merkle root. the merkle root calculated from the" \
			" transaction hashes is %s, but the block header claims the" \
			" merkle root is %s." \
			% (
				bin2hex(calculated_merkle_root),
				bin2hex(parsed_block["merkle_root"])
			)
		else:
			return False

def valid_bits(block, block_1_ago, explain = False):
	"""
	return True if the block bits matches that derived from the block height and
	previous bits data. if the block bits is not valid then either return False
	if the explain argument is not set, otherwise return a human readable string
	with an explanation of the failure.

	to calculate whether the bits is valid we need to look at the previous
	block's bits and timestamp. the current block's bits must be the same as the
	previous block's bits unless we have reached a multiple of 2016 blocks, in
	which case we must calculate the new bits (difficulty) using

	calc_new_bits(old_bits, old_bits_time, new_bits_time)
	"""
	# TODO - handle orphans in the previous blocks
	#(from the bits_data dict), which is in the following format:
	#{block-height: {block-hash0: {
	#	"filenum": 0, "start_pos": 999, "size": 285, "timestamp": x, "bits": x,
	#	"is_orphan": True
	#}}}
	#"timestamp" and "bits" are only defined every 2016 blocks or 2016 - 1, but
	#"filenum", "start_pos", "size" and "is_orphan" are always defined.

	if isinstance(block, dict):
		parsed_block = block
	else:
		parsed_block = block_bin2dict(block, ["bits"])

	block_height = parsed_block["block_height"]

	if parsed_block["block_height"] < 2016:
		if parsed_block["bits"] == initial_bits:
			return True
		else:
			if explain:
				return "the bites should be %s, however they are %s." \
				% (bin2hex(initial_bits), bin2hex(parsed_block["bits"]))
			else:
				return False

	# from here onwards we are beyond block height 2016
	if parsed_block["block_height"] % 2016:
		# block height is not on a multiple of 2016 
		if parsed_block["bits"] == block_1_ago["bits"]:
			return True
		else:
			if explain:
				return "the bits should be %s, however they are %s." \
				% (bits2hex(block_1_ago["bits"]), bin2hex(parsed_block["bits"]))
			else:
				return False
	else:
		# block height is a multiple of 2016 - recalculate
		block_2016_ago = get_block(parsed_block["block_height"] - 2016, "json")
		calculated_bits = calc_new_bits(
			hex2bin(block_2016_ago["bits"]), block_2016_ago["time"],
			block_1_ago["timestamp"]
		)
		if calculated_bits != parsed_block["bits"]:
			if explain:
				return "the bits for block with height %s and hash %s, should" \
				" be %s, however they are %s." \
				% (
					parsed_block["block_height"],
					bin2hex(parsed_block["block_hash"]),
					bin2hex(calculated_bits), bin2hex(parsed_block["bits"])
				)
			else:
				return False
	"""
	# find bits data for the block that is the floored multiple of 2016 for the
	# current height. eg:
	# - if block height is 2015 then floor == 0, not 2016
	# - if block height is 2016 then floor == 2016, not 0
	# - if block height is 2017 then floor == 2016, not 0
	two_week_floor = int(block_height / 2016) * 2016
	for x in [two_week_floor, two_week_floor - 1, two_week_floor - 2016]:
		if x not in bits_data:
			if explain:
				return "could not find bits data for block %s." % x
			else:
				return False

	# make sure there is only one block hash for the bits data 2 weeks ago, and
	# save this data for later
	only_one_block_found = None
	for bits_data_i in bits_data[two_week_floor - 2016].values():
		if only_one_block_found:
			only_one_block_found = False
			break
		if only_one_block_found is None:
			only_one_block_found = True

		old_bits_time = bits_data_i["timestamp"]
		old_bits = bits_data_i["bits"]

	if not only_one_block_found:
		if explain:
			return "there is still an orphan for the previous bits data at" \
			" block %s. hashes: %s. no blockchain fork should last 2016" \
			" blocks!" \
			% (
				two_week_floor - 2016,
				", ".join(bin2hex(x) for x in bits_data[prev_bits_block_height])
			)
		else:
			return False

	# if there is more than one block hash for the closest target then validate
	# all of these. if any targets fail then return either False, or an
	# explanation
	for (block_hash_i, bits_data_i) in bits_data[two_week_floor - 1].items():
		new_bits_time = bits_data_i["timestamp"]
		new_bits = bits_data_i["bits"]
		calculated_bits = calc_new_bits(old_bits, old_bits_time, new_bits_time)
		if calculated_bits != parsed_block["bits"]:
			if explain:
				return "the bits for block with hash %s and height %s, should" \
				" be %s, however it has been calculated as %s." \
				% (
					bin2hex(parsed_block["block_height"]), block_height,
					bin2hex(calculated_bits), bin2hex(parsed_block["bits"])
				)
			else:
				return False
	"""
	# if we get here then all "bits" were correct
	return True

def valid_difficulty(block, explain = False):
	if isinstance(block, dict):
		parsed_block = block
	else:
		parsed_block = block_bin2dict(block, ["difficulty"])

	if parsed_block["difficulty"] >= 1:
		return True
	else:
		if explain:
			return "the block difficulty is %s but should not be less than 1." \
			% difficulty
		else:
			return False

def valid_block_hash(block, explain = False):
	"""
	return True if the block hash is less than or equal to the target. if the
	block hash is greater than the target then either return False if the
	explain argument is not set, otherwise return a human readable string with
	an explanation of the failure.
	"""
	if isinstance(block, dict):
		parsed_block = block
	else:
		parsed_block = block_bin2dict(block, ["block_hash", "bits"])

	target_int = bits2target_int(parsed_block["bits"])
	block_hash_as_int = bin2int(parsed_block["block_hash"])

	# hash must be below target
	if block_hash_as_int <= target_int:
		return True
	else:
		if explain:
			return "bad block hash. the block hash %s (int: %s) should not be" \
			" greater than target %s (int: %s)." \
			% (
				bin2hex(parsed_block["block_hash"]), block_hash_as_int,
				bin2hex(parsed_block["bits"]), target_int
			)
		else:
			return False

def valid_locktime(
	tx_locktime, block_time, block_height, sequence_nums, explain = False
):
	"""
	performs the same function as isFinalTx() in the original bitcoin source.
	sequence_nums is a list of integers that should already have been validated.

	locktimes can be used to prevent miners from including a transaction in a
	block until a certain time in the future. eg if we are currently at block
	20 and a transaction with locktime 22 is broadcast, then miners cannot
	include the transaction in a block until block height 22 has passed. however
	note that the transaction can be re-broadcast with a new locktime or with
	all sequence numbers maxxed out, and this will tell the miners to ignore
	locktimes and just mine the transaction into the block straight away.
	"""
	if tx_locktime == 0:
		# the locktime is below any known block time or block height already
		return True

	# what type of locktime are we dealing with?
	if tx_locktime < locktime_threshold:
		tx_locktime_type = "block height"
		compare_to = block_height
	else:
		tx_locktime_type = "block time"
		compare_to = block_time

	# eg locktime 22 < block height 23
	if tx_locktime < compare_to:
		return True

	# from here on, the tx_locktime has failed the time or block constraints.
	# you might think that we should return false already, but there is still
	# one way for the locktime to be valid - it can be disabled by maxxing out
	# all txin sequence numbers. so if any sequence number is not maxxed out
	# then the locktime will not be disabled, and the previous validation
	# failure is carried through.
	for (seq_key, seq_num) in enumerate(sequence_nums):
		if seq_num != max_sequence_num:
			if explain:
				return "bad locktime - the current %s is %d but the locktime" \
				" is %d. And sequence number %d is not maxxed out." \
				% (tx_locktime_type, compare_to, tx_locktime, seq_key)
			else:
				return False

	# if we get here then the locktime has been disabled due to all sequence
	# numbers being maxxed out
	return True

def valid_coinbase_hash(txin_hash, explain = False):
	if txin_hash == blank_hash:
		return True
	else:
		if explain:
			return "the coinbase transaction should reference previous hash" \
			" %s but it actually references hash %s." \
			% (bin2hex(blank_hash), bin2hex(txin_hash))
		else:
			return False

def valid_coinbase_index(txin_index, explain = False):
	if txin_index == coinbase_index:
		return True
	else:
		if explain:
			return "the coinbase transaction should reference previous index" \
			" %s but it actually references index %s." \
			% (coinbase_index, txin_index)
		else:
			return False

def valid_txin_hash(txin_hash, prev_tx, explain = False):
	if prev_tx is not None:
		return True
	else:
		if explain:
			return "it is not possible to spend transaction with hash %s" \
			" since this transaction does not exist." \
			% txin_hash
		else:
			return False

def valid_txin_index(txin_index, prev_tx, explain = False):
	"""
	return True if the txin index refers to an output index that actually exists
	in the previous transaction. if the txout does not exist then either return
	False if the explain argument is not set, otherwise return a human readable
	string with an explanation of the failure.
	"""
	if isinstance(prev_tx, dict):
		parsed_prev_tx = prev_tx
	else:
		(parsed_prev_tx, _) = tx_bin2dict(prev_tx, ["num_tx_outputs"], 0, 0)

	if (
		(txin_index in parsed_prev_tx["output"]) or (
			("num_tx_outputs" in parsed_prev_tx) and
			(txin_index <= parsed_prev_tx["num_tx_outputs"])
		)
	):
		return True
	else:
		if explain:
			return "it is not possible to spend txout %s since the referenced" \
			" transaction only has %s outputs." \
			% (txin_index, parsed_prev_tx["num_tx_outputs"])
		else:
			return False

def valid_tx_spend(
	spendee_tx_metadata, spendee_hash, spendee_index, tx_hash, txin_num,
	same_block_spent_txs, explain = False
):
	"""
	return True if the tx being spent has never been spent before (including by
	transactions within this same block). if the spendee tx has been spent
	before then either return False if the explain argument is not set,
	otherwise return a human readable string with an explanation of the failure.

	note that same_block_spent_txs is a dict in the format
	{spendee_hash: [
		spendee_index, spender_hash, spender_txin_index
	]}
	"""
	try:
		# use 'try' because this value might be None, or might be malformed
		(spender_txhash, spender_txin_index) = \
		spendee_tx_metadata["spending_txs_list"][spendee_index].split("-")

		spender_txhash = hex2bin(spender_txhash)
		spender_txin_index = int(spender_txin_index)
		x = len(spender_txhash)
	except:
		(spender_txhash, spender_txin_index) = (None, None)

	error_text = "doublespend failure. previous transaction with hash %s and" \
	" index %s has already been spent by transaction starting with hash %s" \
	" and txin-index %s. it cannot be spent again by transaction with hash %s" \
	" and txin-index %s."

	# if there is previous data and it is not for this tx then we have a
	# doublespend error from a prior block
	if (
		(spender_txhash is not None) and
		(spender_txin_index is not None) and (
			(spender_txhash != tx_hash[: x]) or
			(spender_txin_index != txin_num)
		)					
	):
		if explain:
			return error_text \
			% (
				bin2hex(spendee_hash), spendee_index, bin2hex(spender_txhash),
				spender_txin_index, bin2hex(tx_hash), txin_num
			)
		else:
			return False

	# check if it is a doublespend from this same block
	if (
		(spendee_hash in same_block_spent_txs) and
		(same_block_spent_txs[spendee_hash][0] == spendee_index)
	):
		spender_txhash = same_block_spent_txs[spendee_hash][1]
		spender_txin_index = same_block_spent_txs[spendee_hash][2]
		if explain:
			return error_text \
			% (
				bin2hex(spendee_hash), spendee_index, bin2hex(spender_txhash),
				spender_txin_index, bin2hex(tx_hash), txin_num
			)
		else:
			return False

	# if we get here then there were no doublespend errors
	return True

def valid_spend_from_non_orphan(is_orphan, spendee_hash, explain = False):
	"""
	return True if the tx being spent is not in an orphan block. if the spendee
	tx is in an orphan block then either return False if the explain argument is
	not set, otherwise return a human readable string with an explanation of the
	failure.

	note that this is the only check on the validity of the previous tx that is
	necessary. the validation process in this script will halt if errors are
	encountered in a main-chain block, so there is no need to worry about this.
	"""
	if not is_orphan:
		return True
	else:
		if explain:
			return "previous transaction with hash %s occurs in an orphan" \
			" block and therefore cannot be spent." \
			% bin2hex(spendee_hash)
		else:
			return False

def valid_mature_coinbase_spend(
	block_height, spendee_tx_metadata, explain = False
):
	"""
	return True either if we are not spending a coinbase tx, or if we are
	spending a coinbase tx and it has reached maturity. if we are spending a
	coinbase tx and it has not reached maturity yet then either return False if
	the explain argument is not set, otherwise return a human readable string
	with an explanation of the failure.
	"""
	# if the spendee is not a coinbase then all is ok
	if spendee_tx_metadata["is_coinbase"] is None:
		return True

	num_confirmations = block_height - spendee_tx_metadata["block_height"]
	if num_confirmations >= coinbase_maturity:
		return True
	else:
		if explain:
			return "it is not permissible to spend coinbase funds until they" \
			" have reached maturity (ie %s confirmations). this transaction" \
			" attempts to spend coinbase funds after only %s confirmations." \
			% (coinbase_maturity, num_confirmations)
		else:
			return False

def valid_script_format(script_list, explain = False):
	if extract_script_format(script_list) is not None:
		return True
	else:
		if explain:
			return "unrecognized script format %s." \
			% script_list2human_str(script_list)
		else:
			return False

def valid_address_checksum(address, explain = False):
	"""make sure the checksum in the base58 encoded address is correct"""
	if address is None:
		if explain:
			return "cannot calculate address checksum since there is no address"
		else:
			return False

	# decode from base 58 into bytes
	address_bytes = base58decode(address)

	# the checksum is the last 4 bytes of the address
	checksum = address_bytes[-4:]

	# the remaining bytes must hash to 
	expected_checksum = sha256(sha256(address_bytes[: -4]))[: 4]

	if expected_checksum == checksum:
		return True
	else:
		if explain:
			return "address %s has checksum %s however the checksum for this" \
			" address has been calculated to be %s" \
			% (address, bin2hex(checksum), bin2hex(expected_checksum))
		else:
			return False

def valid_tx_balance(tx, explain = False):
	"""make sure the output funds are not larger than the input funds"""
	total_txout_funds = sum(txout["funds"] for txout in tx["output"].values())
	total_txin_funds = sum(txin["funds"] for txin in tx["input"].values())
	if (
		("coinbase_change_funds" in tx["input"][0]) and
		(tx["input"][0]["coinbase_change_funds"]is not None)
	):
		total_txin_funds += tx["input"][0]["coinbase_change_funds"]
		
	if total_txout_funds <= total_txin_funds:
		return True
	else:
		if explain:
			return "there are more txout funds (%s) than txin funds (%s) in" \
			" this transaction" \
			% (total_txout_funds, total_txin_funds)
		else:
			return False

def valid_txins_exist(txins_exist, explain = False):
	if txins_exist:
		return True
	else:
		if explain:
			return "invalid tx. no txins were found."
		else:
			return False

def valid_txouts_exist(txouts_exist, explain = False):
	if txouts_exist:
		return True
	else:
		if explain:
			return "invalid tx. no txouts were found."
		else:
			return False

def parse_non_standard_script_addresses(parsed_block, bugs_and_all, options):
	"""get any non-standard (eg multisig) addresses from the block"""

	for (tx_num, tx) in sorted(parsed_block["tx"].items()):
		# coinbase txs have no txin address
		if tx_num == 0:
			continue
		for (txin_num, txin) in tx["input"].items():
			if (
				("addresses" in txin) and
				(txin["addresses"] is None) and
				("checksig_validation_status" in txin) and
				(txin["checksig_validation_status"] is None)
			):
				prev_tx = txin["prev_txs"][0]
				script_eval_data = verify_script(
					tx, txin_num, prev_tx, bugs_and_all, options.explain
				)
				parsed_block["tx"][tx_num]["input"][txin_num] \
				["checksig_validation_status"] = script_eval_data["status"]

				if script_eval_data["status"] is not True:
					continue

				parsed_block["tx"][tx_num]["input"][txin_num]["addresses"] = \
				script_eval_data["addresses"]

def prelim_checksig_setup(tx, on_txin_num, prev_tx, explain = False):
	"""
	take all the necessary data to perform the checksig, and run preliminary
	tests on it. if the tests pass then return the following data necessary for
	the checksig:
	- the wiped tx
	- the script of the later txin (where the signature and sometimes the public
	key comes from)
	- the script of the earlier txout (where the public key/hash comes from)
	if they fail then return False if the explain argument is
	not set, otherwise return a human readable string with an explanation of the
	failure.

	https://en.bitcoin.it/wiki/OP_CHECKSIG
	http://bitcoin.stackexchange.com/questions/8500
	"""
	# check if this txin exists in the tranaction
	if on_txin_num not in tx["input"]:
		if explain:
			return "unable to perform a checksig on txin number %s, as it" \
			" does not exist in the transaction." \
			% on_txin_num
		else:
			return False

	# check if the prev_tx hash matches the hash for this txin
	if tx["input"][on_txin_num]["hash"] != prev_tx["hash"]:
		if explain:
			return "could not find previous transaction with hash %s to spend" \
			" from." \
			% bin2hex(tx["input"][on_txin_num]["hash"])
		else:
			return False

	# create a copy of the tx
	wiped_tx = copy.deepcopy(tx)

	# remove superfluous info if necessary
	try:
		del wiped_tx["bytes"]
	except:
		pass # no probs if this field does not exist
	try:
		del wiped_tx["hash"]
	except:
		pass # no probs if this field does not exist

	# wipe all input scripts
	for txin_num in wiped_tx["input"]:
		wiped_tx["input"][txin_num]["script"] = ""
		wiped_tx["input"][txin_num]["script_length"] = 0
		try:
			del wiped_tx["input"][txin_num]["parsed_script"]
		except:
			pass
		try:
			del wiped_tx["input"][txin_num]["script_list"]
		except:
			pass

	txin = tx["input"][on_txin_num]
	prev_index = txin["index"]
	prev_txout = prev_tx["output"][prev_index]

	return (
		wiped_tx, txin["script_list"], prev_txout["script_list"],
		prev_txout["script_format"]
	)

def valid_checksig(
	wiped_tx, on_txin_num, subscript_list, pubkey, signature, bugs_and_all,
	explain = False
):
	"""
	return True if the checksig for this txin passes. if it fails then either
	return False if the explain argument is not set, otherwise return a human
	readable string with an explanation of the failure.

	note that wiped_tx should have absolutely all input scripts set to "" and
	their lengths set to 0 as it is input to this function.

	http://bitcoin.stackexchange.com/questions/8500
	https://bitcoin.org/en/developer-guide#signature-hash-types
	"""
	# remove all OP_CODESEPARATORs from the subscript
	codeseparator_bin = opcode2bin("OP_CODESEPARATOR")
	subscript_list = [
		el for el in subscript_list if el is not codeseparator_bin
	]
	# remove OP_PUSHDATAx-signature from the subscript
	subscript = script_list2bin(subscript_list)
	pushdata_bin = pushdata_int2bin(len(signature))
	pushdata_sig_bin = "%s%s" % (pushdata_bin, signature)
	subscript = subscript.replace(pushdata_sig_bin, "")

	# add the subscript back into the relevant txin
	wiped_tx["input"][on_txin_num]["script"] = subscript
	wiped_tx["input"][on_txin_num]["script_length"] = len(subscript)

	# determine the hashtype (final byte) and remove it from the signature
	hashtype_int = bin2int(signature[-1])
	signature = signature[: -1]

	res = sighash(wiped_tx, on_txin_num, hashtype_int)
	if bugs_and_all:
		# mimic the original bitcoin functionality - bugs and all. if there was
		# an error when calculating the sighash then the default hash is used,
		# rather than terminating execution.
		tx_hash = res["value"]
	elif not res["status"]:
		# don't mimic the original bitcoin functionality. if there was an error
		# when calculating the sighash then exit here.
		if explain:
			return "error while calculating sighash for tx %s: %s" \
			% (wiped_tx, res["detail"])
		else:
			return False

	if pybitcointools.ecdsa_raw_verify(
		tx_hash, pybitcointools.der_decode_sig(bin2hex(signature)),
		bin2hex(pubkey)
	):
		return True
	else:
		if explain:
			return "checksig with signature %s and pubkey %s failed." \
			% (bin2hex(signature), bin2hex(pubkey))
		else:
			return False

def sighash(semi_wiped_tx, on_txin_num, hashtype_int):
	"""
	this function determines the correct tx hash. some txouts and/or txins are
	removed depending on the hashtypes (derived from the final byte of the
	signature). the function returns a dict of the following format: {
		"status": True = success, False = fail,
		"value": the tx hash value. use the default if status = fail,
		"detail": details of the failure, empty string if status = success
	}
	note that semi_wiped_tx should have all but the on_txin_num signature set to
	"" and all but the on_txin_num signature lengths set to 0. the on_txin_num
	signature and length should be set to the correct subscript and its length.

	this function mimics SignatureHashOld() from
	github.com/bitcoin/bitcoin/blob/master/src/test/sighash_tests.cpp
	notice that the original function does not actually throw errors - it just
	prints an error message and returns a normal hash as per
	bitcointalk.org/index.php?topic=260595.0 this functionality is optionally
	available here. you can call this function and ignore the status element in
	the return dict.

	en.bitcoin.it/wiki/OP_CHECKSIG is useful for understanding this
	function.
	"""
	default_tx_hash = hex2bin("%s1" % ("0" * 63))

	# range check
	if on_txin_num >= semi_wiped_tx["num_inputs"]:
		return {
			"status": False,
			"value": default_tx_hash,
			"detail": "txin %s is out of range since there are only %s inputs"
			" in this tx."
			% (on_txin_num, semi_wiped_tx["num_inputs"])
		}

	hashtypes = int2hashtype(hashtype_int)

	# now remove components of the txin and/or txout depending on the hashtypes
	if "SIGHASH_NONE" in hashtypes:
		# sign none of the outputs - doesn't matter where the bitcoins go
		semi_wiped_tx["num_outputs"] = 0
		del semi_wiped_tx["output"]

		# set sequence_num to 0 for all but the current txin - allows others to
		# update later on
		for txin_num in semi_wiped_tx["input"]:
			if txin_num != on_txin_num:
				semi_wiped_tx["input"][txin_num]["sequence_num"] = 0

	elif "SIGHASH_SINGLE" in hashtypes:
		# sign only the on_txin_num input and only the on_txin_num output

		# range check
		if on_txin_num >= semi_wiped_tx["num_outputs"]:
			return {
				"status": False,
				"value": default_tx_hash,
				"detail": "sighash_single. txout %s is out of range since there"
				"are only %s outputs"
				% (on_txin_num, semi_wiped_tx["num_outputs"])
			}

		# remove all but the on_txin_num output
		semi_wiped_tx["num_outputs"] = 1
		backup_txout = copy.deepcopy(semi_wiped_tx["output"][on_txin_num])
		del semi_wiped_tx["output"]
		semi_wiped_tx["output"] = {} # init
		semi_wiped_tx["output"][on_txin_num] = backup_txout

		# set sequence_num to 0 for all but the current txin - allows others to
		# update later on
		for txin_num in semi_wiped_tx["input"]:
			if txin_num != on_txin_num:
				semi_wiped_tx["input"][txin_num]["sequence_num"] = 0

	if "SIGHASH_ANYONECANPAY" in hashtypes:
		# remove all but the on_txin_num input
		semi_wiped_tx["num_inputs"] = 1
		backup_txin = copy.deepcopy(semi_wiped_tx["input"][on_txin_num])
		del semi_wiped_tx["input"]
		semi_wiped_tx["input"] = {} # init
		semi_wiped_tx["input"][0] = backup_txin

	hashtype_bin = little_endian(int2bin(hashtype_int, 4))
	txhash = sha256(sha256("%s%s" % (tx_dict2bin(semi_wiped_tx), hashtype_bin)))
	return {
		"status": True,
		"value": txhash,
		"detail": ""
	}

def check_pubkey_encoding(pubkey, explain = False):
	"""
	same as IsCompressedOrUncompressedPubKey() in the satoshi source. function
	CheckPubKeyEncoding() in the satoshi source is currently redundant.

	pubkey is bytes unmodified from the script stack.
	"""
	if len(pubkey) < 33:
		# this check is redundant (already covered by the following checks) but
		# its in the satoshi source, so copy it here
		if explain:
			return "pubkey %s is less than 33 bytes - too short even for a" \
			" compressed pubkey" % bin2hex(pubkey)
		else:
			return False

	# uncompressed pubkeys start with 04
	if bin2int(pubkey[0]) == 0x04:
		if len(pubkey) != 65:
			if explain:
				return "uncompressed pubkeys should be 65 bytes, this one" \
				" (%s) is %d" % (bin2hex(pubkey), len(pubkey))
			else:
				return False
	# compressed pubkeys start with 02 or 03
	elif (
		(bin2int(pubkey[0]) == 0x02) or
		(bin2int(pubkey[0]) == 0x03)
	):
		if len(pubkey) != 33:
			if explain:
				return "compressed pubkeys should be 33 bytes, this one (%s)" \
				"is %d" % (bin2hex(pubkey), len(pubkey))
			else:
				return False
	else:
		if explain:
			return "non-canonical pubkey %s - neither compressed nor" \
			" uncompressed" % bin2hex(pubkey)
		else:
			return False

	# if we get here then the pubkey is correct
	return True

def check_signature_encoding(signature, explain = False):
	"""
	same as CheckSignatureEncoding() in the satoshi source

	basically make sure the signature is encoded correctly. this is necessary
	because some versions of openssl will accept some signature encodings while
	other versions will not. if both these versions are allowed to operate then
	the blockchain will become unverifiable by some miners and they will fork
	the network.
	"""
	if len(signature) == 0:
		# empty signature. not strictly der encoded, but allowed to provide a
		# compact way to provide an invalid signature for use in CHECK(MULTI)SIG
		return True
	# same as IsValidSignatureEncoding() in satoshi source
	res = valid_der_signature(signature, explain)
	if res is not True:
		return res

	# is_low_der_signature() needs to know valid_der_signature()'s results
	# same as IsLowDERSignature() in satoshi source
	res = is_low_der_signature(signature, res, explain)
	if res is not True:
		return res

	# same as IsDefinedHashtypeSignature() in satoshi source
	res = is_defined_hashtype_signature(signature, explain)
	if res is not True:
		return res

	# if we get here then the signature encoding is correct
	return True

def is_defined_hashtype_signature(signature, explain = False):
	"""
	mimic IsDefinedHashtypeSignature() from /src/script/interpreter.cpp

	check that the hashtype matches the known codes and nothing else
	"""
	if len(signature) == 0:
		if explain:
			return "signature has no length"
		else:
			return False

	# hashtype codes from script/interpreter.h
	SIGHASH_ALL = 1
	SIGHASH_NONE = 2
	SIGHASH_SINGLE = 3
	SIGHASH_ANYONECANPAY = 0x80

	# first remove the SIGHASH_ANYONECANPAY bit
	hashtype = bin2int(signature[-1]) & ~SIGHASH_ANYONECANPAY
	if (
		(hashtype < SIGHASH_ALL) or
		(hashtype > SIGHASH_SINGLE)
	):
		if explain:
			return "signature hash type %s does not match SIGHASH_ALL," \
			" SIGHASH_NONE or SIGHASH_SINGLE" % bin2hex(signature[-1])
		else:
			return False

	# if we get here then the hashtype of the signature is defined
	return True

def valid_der_signature(signature, explain = False):
	"""
	mimimc IsValidSignatureEncoding() from /src/script/interpreter.cpp

	note that this function is not currently used for validation in bitcoin
	miners, so it is entirely possible that signatures exist in the blockchain
	which would fail these checks (yet still correctly validate tx hashes in
	certain versions of openssl)

	this function basically makes sure that the signature is in the format:

	- 0x30 - constant placeholder 1
	- alleged signature length - 1 byte (the length of the following bytes, not
	  including the sighash byte)
	- 0x02 - constant placeholder 2
	- length r - 1 byte
	- r
	- 0x02 - constant placeholder 3
	- length s - 1 byte
	- s
	- sighash - 1 byte

	negative r or s are encoded with 0080... ie a leading null byte and the msb
	in byte 2 set
	"""
	human_signature = bin2hex(signature)
	signature_length = len(signature)

	placeholder_1 = 0 # init
	alleged_signature_length = 0 # init
	placeholder_2 = 0 # init
	r_length = 0 # init
	r = "" # init
	placeholder_3 = 0 # init
	s_length = 0 # init
	s = "" # init
	sighash = 0 # init
	try:
		placeholder_1 = bin2int(signature[0])
		alleged_signature_length = bin2int(signature[1])
		placeholder_2 = bin2int(signature[2])
		r_length = bin2int(signature[3])
		signature = signature[4:] # chop off what we have extracted
		r = signature[: r_length]
		signature = signature[r_length:] # chop off what we have extracted
		placeholder_3 = bin2int(signature[0])
		s_length = bin2int(signature[1])
		signature = signature[2:] # chop off what we have extracted
		s = signature[: s_length]
		signature = signature[s_length:] # chop off what we have extracted
		sighash = signature[0]
	except:
		pass

	# minimum and maximum size constraints
	if signature_length < 9:
		if explain:
			return "error: signature %s is too short (min length is 9 bytes" \
			" but this is %s bytes)" \
			% (human_signature, signature_length)
		else:
			return False

	if signature_length > 73:
		if explain:
			return "error: signature %s is too long (max length is 73 bytes" \
			" but this is %s bytes)" \
			% (human_signature, signature_length)
		else:
			return False

	# a signature is of type 0x30 (compound)
	if placeholder_1 != 0x30:
		if explain:
			return "error: the first placeholder in signature %s should be %s" \
			" but it is %s" \
			% (human_signature, int2hex(0x30), int2hex(placeholder_1))
		else:
			return False

	# make sure the length covers the entire signature
	if alleged_signature_length != (signature_length - 3):
		if explain:
			return "error: signature %s claims to be %s bytes (0x%s + 3), but" \
			" it is really %s bytes" \
			% (
				human_signature, alleged_signature_length + 3,
				int2hex(alleged_signature_length), signature_length
			)
		else:
			return False

	# make sure the length of the s element is still inside the signature
	if (r_length + 5) >= signature_length:
		if explain:
			return "error: signature %s has an incorrect r-length of %s given" \
			" its actual length of %s" \
			% (human_signature, r_length, signature_length)
		else:
			return False

	# verify that the length of the signature matches the sum of the length of
	# the elements
	if (r_length + s_length + 7) != signature_length:
		if explain:
			return "error: signature %s has incorrect r-length of %s or an" \
			" incorrect s-length of %s for its actual length %s" \
			% (human_signature, r_length, s_length, signature_length)
		else:
			return False

	# check whether the r element is an integer
	if placeholder_2 != 0x02:
		if explain:
			return "error: the second placeholder in signature %s should be" \
			" %s but it is %s" \
			% (human_signature, int2hex(0x02), int2hex(placeholder_2))
		else:
			return False

	# zero-length integers are not allowed for r
	if r_length == 0:
		if explain:
			return "error: signature %s has r-length = 0" \
			% (human_signature)
		else:
			return False

	# negative numbers are not allowed for r
	if bin2int(r[0]) & 0x80:
		if explain:
			return "error: signature %s has a negative r (it starts with %s)" \
			% (human_signature, bin2hex(r[0]))
		else:
			return False

	# null bytes at the start of r are not allowed, unless r would otherwise
	# falsely be interpreted as a negative number
	if (
		(r_length > 1) and
		(bin2int(r[0]) == 0x00) and
		not (bin2int(r[1]) & 0x80)
	):
		if explain:
			return "error: signature %s has null bytes at the start of r and" \
			" r would not otherwise be falsely interpreted as negative: %s" \
			% (human_signature, bin2hex(r))
		else:
			return False

	# check whether the s element is an integer
	if placeholder_3 != 0x02:
		if explain:
			return "error: the third placeholder in signature %s should be" \
			" %s but it is %s" \
			% (human_signature, int2hex(0x02), int2hex(placeholder_3))
		else:
			return False

	# zero-length integers are not allowed for s
	if s_length == 0:
		if explain:
			return "error: signature %s has s-length = 0" \
			% (human_signature)
		else:
			return False

	# negative numbers are not allowed for s
	if bin2int(s[0]) & 0x80:
		if explain:
			return "error: signature %s has a negative s (it starts with %s)" \
			% (human_signature, bin2hex(s[0]))
		else:
			return False

	# null bytes at the start of s are not allowed, unless s would otherwise
	# falsely be interpreted as a negative number
	if (
		(s_length > 1) and
		(bin2int(s[0]) == 0x00) and
		not (bin2int(s[1]) & 0x80)
	):
		if explain:
			return "error: signature %s has null bytes at the start of s and" \
			" s would not otherwise be falsely interpreted as negative: %s" \
			% (human_signature, bin2hex(s))
		else:
			return False

	# if we get here then everything is ok with the signature
	return True

max_mod_half_order = [
	0x7f, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
	0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
	0x5d, 0x57, 0x6e, 0x73, 0x57, 0xa4, 0x50, 0x1d,
	0xdf, 0xe9, 0x2f, 0x46, 0x68, 0x1b, 0x20, 0xa0
]
def is_low_der_signature(signature, valid_der_signature, explain = False):
	"""similar to IsLowDERSignature() in script/interpreter.cpp"""
	if valid_der_signature is not True:
		if explain:
			return "signature has not passed der validation yet - %s" \
			% valid_der_signature
		else:
			return False

	# we want to get the s component of the signature
	r_length = bin2int(signature[3]) # 1 byte
	s_length = bin2int(signature[5 + r_length]) # 1 byte
	s = signature[6 + r_length: 6 + r_legnth + s_length]
	
	# convert s into an array of integers (1 per byte)
	s = bytearray(s)

	# if the s value is above the order of the curve divided by two, its
	# complement modulo the order could have been used instead, which is one
	# byte shorter when encoded correctly
	if (
		(compare_big_endian(s, [0]) > 0) and
		(compare_big_endian(s, max_mod_half_order) <= 0)
	):
		return True
	else:
		if explain:
			return "signature %s is not low-der encoded" % bin2hex(signature)
		else:
			return False

def compare_big_endian(c1, c2):
	"""
	loosely matches CompareBigEndian() from eccryptoverify.cpp

	compares two lists of integers, and returns a negative value if the first is
	less than the second, 0 if they're equal, and a positive value if the
	first is greater than the second.

	thanks to https://github.com/petertodd/python-bitcoinlib

	c1 and c2 must be of type bytearray or lists of integers
	"""
	# adjust starting positions until remaining lengths of the two arrays match
	while len(c1) > len(c2):
		if c1.pop(0) > 0:
			return 1

	while len(c2) > len(c1):
		if c2.pop(0) > 0:
			return -1

	while len(c1) > 0:
		diff = c1.pop(0) - c2.pop(0)
		if diff != 0:
			return diff

	return 0

def verify_script(
	blocktime, tx, on_txin_num, prev_tx, bugs_and_all, explain = False
):
	"""
	this function returns a dict in the format: {
		"status": True/False/"explanation of failure",
		"pubkeys": [],
		"signatures": [],
		"sig_pubkey_statuses": {sig0: {pubkey0: True, pubkey1: False}, ...}
	}
	the status element is True if the scripts pass. if the scripts fail then
	either set the status element to False if the explain argument is not set,
	otherwise set it to a human readable string with an explanation of the
	failure.

	the sig_pubkey_statuses element shows the checksig results of each
	signature-pubkey combination (there are only multiple combinations for
	multisig scripts, for standard scripts there is only 1 pubkey and 1
	signature). if the explain argument is set then the results in the
	sig_pubkey_statuses element will either be True or a human string of the
	failure. if the explain argument is not set then they are either True or
	False.
	"""
	res = { # init
		"status": True,
		"pubkeys": [],
		"signatures": [],
		"sig_pubkey_statuses": {}
	}
	tmp = prelim_checksig_setup(tx, on_txin_num, prev_tx, explain)
	if isinstance(tmp, tuple):
		(
			wiped_tx, txin_script_list, prev_txout_script_list,
			prev_txout_script_format
		) = tmp
	else:
		# if tmp is not a tuple then it must be either False or an error string
		res["status"] = tmp
		return res

	# txin script (scriptsig) must be push-only to avoid tx malleability
	push_only = is_push_only(txin_script_list)
	if not push_only:
		if explain:
			res["status"] = "scriptsig %s is not push-only. malleability is" \
			" possible for this tx." % script_list2human_str(txin_script_list)
		else:
			res["status"] = False
		return res
	
	stack = [] # init
	# first evaluate the txin script (scriptsig)
	(res, stack) = eval_script(
		res, stack, txin_script_list, wiped_tx, on_txin_num, bugs_and_all,
		explain
	)
	if res["status"] is not True:
		if explain:
			res["status"] = "txin script (scriptsig) %s" % res["status"]
			return res
		else:
			return False

	# backup the stack for use in p2sh
	stack_copy = copy.deepcopy(stack)

	# next evaluate the previous txout script (scriptpubkey)
	(res, stack) = eval_script(
		res, stack, prev_txout_script_list, wiped_tx, on_txin_num, bugs_and_all,
		explain
	)
	if res["status"] is not True:
		if explain:
			res["status"] = "txout script (scriptpubkey) %s" % res["status"]
			return res
		else:
			return False

	# after evaluating both txin and txout scripts, the stack should not be
	# empty and should not be false
	if (
		(len(stack) == 0) or
		(stack_el2bool(stack[-1]) == False)
	):
		if explain:
			res["status"] = "stack is empty or false in the end. txin script:" \
			" %s, txout script: %s" % (
				script_list2human_str(txin_script_list),
				script_list2human_str(prev_txout_script_list),
			)
		else:
			return False

	# make sure the script passed evaluation
	try:
		v1 = stack.pop()
		# if the top stack item is 0 or "" its a fail 
		if not stack_el2bool(v1):
			if explain:
				res["status"] = "script eval failed since the top stack item" \
				" (%s) at the end of all operations is zero. script: %s" \
				% (
					script_list2human_str(v1),
					script_list2human_str(script_list)
				)
			else:
				return_dict["status"] = False
			return return_dict

	except IndexError:
		if explain:
			res["status"] = "script eval failed since there are no items on" \
			" the stack at the end of all operations. script: %s" \
			% human_script
		else:
			return_dict["status"] = False
		return return_dict

	# if the txout script is p2sh and if the blocktime is later than 15 Feb 2012
	# 00:00:00 GMT (as per bip 16) then evaluate this also
	if (
		(timestamp >= 1329264000) and
		(prev_txout_script_format == "p2sh-txout")
	):
		(res, stack_copy) = eval_script(
			res, stack_copy, prev_txout_script_list, wiped_tx, on_txin_num,
			bugs_and_all, explain
		)
	if res["status"] is not True:
		return res

def eval_script(
	stack, script_list, wiped_tx, on_txin_num, tx_locktime, txin_sequence_num,
	bugs_and_all, explain = False
):
	"""
	mimics bitcoin-core's EvalScript() function as exactly as i know how.

	evaluate a script. note that while this function has been used to evaluate
	the blockchain (so far upto block 251717) it may be different to the satoshi
	source. you should not use this function for mission critical applications.

	return a dict in the format: {
		"status": True/False/"explanation of failure",
		"pubkeys": [],
		"signatures": [],
		"sig_pubkey_statuses": {sig0: {pubkey0: True, pubkey1: False}, ...}
	}
	the status element is True if the scripts pass. if the scripts fail then
	either set the status element to False if the explain argument is not set,
	otherwise set it to a human readable string with an explanation of the
	failure.

	the sig_pubkey_statuses element shows the checksig results of each
	signature-pubkey combination (there are only multiple combinations for
	multisig scripts, for standard scripts there is only 1 pubkey and 1
	signature). if the explain argument is set then the results in the
	sig_pubkey_statuses element will either be True or a human string of the
	failure. if the explain argument is not set then they are either True or
	False.
	"""
	# human script - used for errors and debugging
	human_script = script_list2human_str(script_list)

	# initialize the return dict
	return_dict = {
		"status": None,
		"pubkeys": [],
		"signatures": [],
		"sig_pubkey_statuses": {}
	}
	def set_error(status):
		if explain:
			# update a nonlocal var - only works for a dict in python 2.x. see
			# stackoverflow.com/a/3190783/339874
			# the idea here is to end up with something like "scriptsig ...
			# error: unbalanced conditional"
			return_dict["status"] = "%s error: %s" % (human_script, status)
		else:
			# False or string -> False, else True
			return_dict["status"] = False if (status is not True) else True
		return return_dict

	stack_len_error_str = "%d is not enough stack items to perform operation %s"

	# ifelse_conditions is used to store (nested) if/else statement conditions.
	# eg [True, False, True]. same as vfExec in satoshi source
	ifelse_conditions = [] # init
	set_error("unknown error") # init
	alt_stack = [] # init
	pushdata = False # init
	subscript_list = copy.copy(script_list) # init
	op_count = 0 # init
	op_16_int = bin2int(opcode2bin("OP_16")) # used frequently
	while len(script_list):
		# same as fExec in satoshi source
		ifelse_ok = False if False in [
			stack_el2bool(el) for el in ifelse_conditions
		] else True

		# pop the leftmost element off the script
		opcode_bin = script_list.pop(0)

		# get the opcode string
		opcode_str = bin2opcode(opcode_bin)
		if opcode_str is None:
			return set_error(
				"script contains unrecognized opcode %s" % bin2hex(opcode_bin)
			)
		# if more than 200 ops
		if op_count > max_op_count:
			return set_error(
				"cannot have more than %s operations in a script" % max_op_count
			)
		# increment op count. we will increment again later in OP_CHECKMULTISIG
		# too. note how the following opcodes do not count toward the opcode
		# limit:
		# 0 - OP_FALSE (an empty array of bytes is pushed onto the stack)
		# 75-78 OP_PUSHDATA
		# 79 - OP_1NEGATE (the number -1 is pushed onto the stack)
		# 80 - OP_RESERVED
		# 81 - OP_TRUE/OP_1 (the number 1 is pushed onto the stack)
		# 82-96 - OP_2-OP_16 (the number 2-16 is pushed onto the stack)
		if bin2int(opcode_bin) > op_16_int:
			op_count += 1

		# disabled opcodes
		if opcode_str in [
			"OP_CAT", "OP_SUBSTR", "OP_LEFT", "OP_RIGHT", "OP_INVERT", "OP_AND",
			"OP_OR", "OP_XOR", "OP_2MUL", "OP_2DIV", "OP_MUL", "OP_DIV",
			"OP_MOD", "OP_LSHIFT", "OP_RSHIFT"
		]:
			return set_error("opcode % is disabled" % opcode_str)

		if (
			ifelse_ok and
			(0 <= bin2int(opcode_bin) <= 78) # OP_PUSHDATA4 == 78
		):
			pushdata_val_bin = script_list.pop(0)
			if not check_minimal_push(pushdata_val_bin, opcode_str):
				return set_error(
					"opcode %s performs a non-minimal push on data %s" \
					% (opcode_str, bin2hex(pushdata_val_bin))
				)
			# beware - no length checks! these should already have been done
			# when the script was converted into a list prior to this function
			stack.append(pushdata_val_bin)
			continue
		elif ( # (fExec || (OP_IF <= opcode && opcode <= OP_ENDIF))
			ifelse_ok or
			opcode_str in [
				"OP_IF", "OP_NOTIF", "OP_VERIF", "OP_VERNOTIF", "OP_ELSE",
				"OP_ENDIF"
			]
		):
			############
			# push value
			############
			# OP_1 through OP_16
			if opcode_str in [("OP_%d" % x) for x in range(1, 17)]:
				pushnum = int(opcode_str.replace("OP_", ""))
				stack.append(stack_int2bin(pushnum))

			elif "OP_1NEGATE" == opcode_str:
				stack.append(stack_int2bin(-1))

			# push 0x01 onto the stack
			elif "OP_TRUE" == opcode_str:
				stack.append(stack_int2bin(1))

			# push an empty byte onto the stack
			if opcode_str in ["OP_FALSE", "OP_0"]:
				stack.append(stack_int2bin(0))

			############
			# control
			############
			# do nothing for OP_NOP, other OP_NOPs are handled later
			elif "OP_NOP" == opcode_str:
				pass

			# compare the transaction's locktime to the value on the top of the
			# stack. to validate successfully, both must be the same side of the
			# theshold (ie both must be interpreted as a block height, or both
			# as a timestamp), and the script will only validate if the stack
			# value is lower than the tx locktime. this is the opposite of
			# IsFinalTx(). IsFinalTx() is intended to prevent transactions with
			# locktimes in the future from being included into the blockchain,
			# whereas OP_CHECKLOCKTIMEVERIFY is intended to freeze funds so that
			# they can only be spent in the future. note that the stack value
			# used for comparison is most useful when placed in the txout script
			# of the previous transaction, and then the spender must wait for
			# the block or timestamp in order to spend the funds.
			#
			# according to IsFinalTx(), it is possible to create a transaction
			# with a locktime above the current block height or timestamp by
			# maxxing out the sequence number. submitting such a transaction
			# would be a sneaky way for the recipient to spend the funds at any
			# time. to prevent this. we fail the script validation if the
			# sequence number is maxxed out.
			# TODO - test this
			elif "OP_CHECKLOCKTIMEVERIFY" == opcode_str:
				l = len(stack)
				if l < 1:
					return set_error(stack_len_error_str % (l, opcode_str))
				script_locktime_bin = stack.pop()
				min_bytes = minimal_stack_bytes(script_locktime, 5)
				if min_bytes is not True:
					return set_error(
						"error in script locktime value - %s" % min_bytes
				)
				script_locktime = stack_bin2int(locktime_bin)
					
				if script_locktime < 0:
					return set_error(
						"invalid locktime %d in script - it should be" \
						" positive" % script_locktime
					)

				# if locktime < locktime threshold then locktime represents
				# block height, else it is just the transaction locktime.

				tx_locktime_type = "block height" if \
				(tx_locktime < locktime_threshold) else "timestamp"

				script_locktime_type = "block height" if \
				(script_locktime < locktime_threshold) else "timestamp"

				if tx_locktime_type != script_locktime_type:
					return set_error(
						"the transaction locktime (%d) is a %s, but the" \
						" script locktime (%d) is a %s" % (
							tx_locktime, tx_locktime_type, script_locktime,
							script_locktime_type
						)
					)
				# tx locktime must be passed the script locktime to validate
				if tx_locktime < script_locktime:
					return set_error(
						"tx locktime (%s %d) has not yet passed the script" \
						" locktime (%s %d)" % (
							tx_locktime_type, tx_locktime, script_locktime_type,
							script_locktime
						)
					)
				# do not let the spender bypass the locktime requirement by
				# disabling it with the sequence number
				if txin_sequence_num == max_sequence_num:
					return set_error(
						"the locktime has been disabled by the txin sequence" \
						" number. fail the OP_CHECKLOCKTIMEVERIFY check to" \
						" prevent the signer from bypassing this requirement."
					)

			# "in" covers all the remaining OP_NOPs, eg OP_NOP1
			elif "OP_NOP" in opcode_str:
				pass

			# if/notif the top stack item is set then do the following opcodes
			elif opcode_str in ["OP_IF", "OP_NOTIF"]:
				v1 = False # init
				if ifelse_ok:
					l = len(stack)
					if l < 1:
						return set_error(stack_len_error_str % (l, opcode_str))
					v1 = stack_el2bool(stack.pop())
					if "OP_NOTIF" == opcode_str:
						v1 = not v1

				ifelse_conditions.append(v1)

			elif "OP_ELSE" == opcode_str:
				if not len(ifelse_conditions):
					return set_error("OP_ELSE found without prior OP_IF")
				ifelse_conditions[-1] = not ifelse_conditions[-1]

			elif "OP_ENDIF" == opcode_str:
				if not len(ifelse_conditions):
					return set_error("OP_ENDIF found without prior OP_IF")
				ifelse_conditions.pop()

			elif "OP_VERIFY" == opcode_str:
				l = len(stack)
				if l < 1:
					return set_error(stack_len_error_str % (l, opcode_str))
				v1 = stack.pop()
				if not stack_el2bool(v1):
					return set_error(
						"OP_VERIFY failed since the top stack item (%s) is"
						" zero." % script_list2human_str(v1)
					)

			elif "OP_RETURN" == opcode_str:
				return set_error("OP_RETURN found in script")

			############
			# stack ops
			############
			elif "OP_TOALTSTACK" == opcode_str:
				l = len(stack)
				if l < 1:
					return set_error(stack_len_error_str % (l, opcode_str))
				alt_stack.append(stack.pop())

			elif "OP_FROMALTSTACK" == opcode_str:
				l = len(alt_stack)
				if l < 1:
					return set_error(
						"%d is not enough alt-stack items to perform" \
						" operation OP_FROMALTSTACK"
					)
				stack.append(alt_stack.pop())

			elif "OP_2DROP" == opcode_str:
				l = len(stack)
				if l < 2:
					return set_error(stack_len_error_str % (l, opcode_str))
				stack.pop()
				stack.pop()

			elif "OP_2DUP" == opcode_str:
				# x1 x2 -> x1 x2 x1 x2
				l = len(stack)
				if l < 2:
					return set_error(stack_len_error_str % (l, opcode_str))
				v1 = stack[-2]
				v2 = stack[-1]
				stack.append(v1)
				stack.append(v2)

			elif "OP_3DUP" == opcode_str:
				# x1 x2 x3 -> x1 x2 x3 x1 x2 x3
				l = len(stack)
				if l < 3:
					return set_error(stack_len_error_str % (l, opcode_str))
				v1 = stack[-3]
				v2 = stack[-2]
				v3 = stack[-1]
				stack.append(v1)
				stack.append(v2)
				stack.append(v3)

			elif "OP_2OVER" == opcode_str:
				# x1 x2 x3 x4 -> x1 x2 x3 x4 x1 x2
				l = len(stack)
				if l < 4:
					return set_error(stack_len_error_str % (l, opcode_str))
				v1 = stack[-4]
				v2 = stack[-3]
				stack.append(v1)
				stack.append(v2)

			elif "OP_2ROT" == opcode_str:
				# x1 x2 x3 x4 x5 x6 -> x3 x4 x5 x6 x1 x2
				l = len(stack)
				if l < 6:
					return set_error(stack_len_error_str % (l, opcode_str))
				v1 = stack.pop(-6)
				v2 = stack.pop(-5)
				stack.append(v1)
				stack.append(v2)

			elif "OP_2SWAP" == opcode_str:
				# x1 x2 x3 x4 -> x3 x4 x1 x2
				l = len(stack)
				if l < 4:
					return set_error(stack_len_error_str % (l, opcode_str))
				v1 = stack.pop(-4)
				v2 = stack.pop(-3)
				stack.append(v1)
				stack.append(v2)

			elif "OP_IFDUP" == opcode_str:
				# duplicate but only if true
				l = len(stack)
				if l < 1:
					return set_error(stack_len_error_str % (l, opcode_str))
				v1 = stack[-1]
				if stack_el2bool(v1):
					stack.append(v1)

			elif "OP_DEPTH" == opcode_str:
				# put the number of stack items onto the stack
				stack.append(stack_int2bin(len(stack)))

			elif "OP_DROP" == opcode_str:
				l = len(stack)
				if l < 1:
					return set_error(stack_len_error_str % (l, opcode_str))
				stack.pop()

			elif "OP_DUP" == opcode_str:
				# duplicate the last item in the stack
				stack.append(stack[-1])

			elif "OP_NIP" == opcode_str:
				# x1 x2 -> x2
				l = len(stack)
				if l < 2:
					return set_error(stack_len_error_str % (l, opcode_str))
				stack.pop(-2)

			elif "OP_OVER" == opcode_str:
				# x1 x2 -> x1 x2 x1
				l = len(stack)
				if l < 2:
					return set_error(stack_len_error_str % (l, opcode_str))
				v1 = stack.pop(-2)
				stack.append(v1)

			elif opcode_str in ["OP_PICK", "OP_ROLL"]:
				# OP_PICK: xn ... x2 x1 x0 n -> xn ... x2 x1 x0 xn
				# OP_ROLL: xn ... x2 x1 x0 n -> ... x2 x1 x0 xn
				l = len(stack)
				if l < 2:
					return set_error(stack_len_error_str % (l, opcode_str))
				n_bin = stack.pop()
				min_bytes = minimal_stack_bytes(n_bin)
				if min_bytes is not True:
					return set_error(
						"error in %s - %s" % (opcode_str, min_bytes)
					)
				n = stack_bin2int(n_bin)
				if (n < 0 or l <= n):
					# use >= because we count the 0
					return set_error(
						"cannot %s %d stack elements when there are %d stack" \
						" elements" % (opcode_str, n, l)
					)
				v1 = stack[-n - 1]
				if "OP_ROLL" == opcode_str:
					stack.pop(-n - 1)
				stack.append(v1)

			elif "OP_ROT" == opcode_str:
				# x1 x2 x3 -> x2 x1 x3 -> x2 x3 x1
				l = len(stack)
				if l < 3:
					return set_error(stack_len_error_str % (l, opcode_str))
				stack[-3], stack[-2] = stack[-2], stack[-3]
				stack[-2], stack[-1] = stack[-1], stack[-2]

			elif "OP_SWAP" == opcode_str:
				# x1 x2 -> x2 x1
				l = len(stack)
				if l < 2:
					return set_error(stack_len_error_str % (l, opcode_str))
				stack[-2], stack[-1] = stack[-1], stack[-2]

			elif "OP_TUCK" == opcode_str:
				# x1 x2 -> x2 x1 x2
				l = len(stack)
				if l < 2:
					return set_error(stack_len_error_str % (l, opcode_str))
				stack.insert(-2, stack[-1])

			elif "OP_SIZE" == opcode_str:
				# append the number of bytes of the top stack item to the stack
				l = len(stack)
				if l < 1:
					return set_error(stack_len_error_str % (l, opcode_str))
				stack.append(stack_int2bin(len(stack[-1])))

			############
			# bitwise logic
			############
			elif opcode_str in ["OP_EQUAL", "OP_EQUALVERIFY"]:
				l = len(stack)
				if l < 2:
					return set_error(stack_len_error_str % (l, opcode_str))
				v1 = stack.pop()
				v2 = stack.pop()
				if "OP_EQUALVERIFY" == opcode_str:
					# equalverify - push nothing upon success
					if v1 == v2:
						pass
					else:
						return set_error(
							"the final stack item %s is not equal to the"
							" penultimate stack item %s, so %s fails"
							% (bin2hex(v1), bin2hex(v2), opcode_str)
						)
				if "OP_EQUAL" == opcode_str:
					stack.append(stack_int2bin(1 if (v1 == v2) else 0))

			############
			# numeric
			############
			elif opcode_str in [
				"OP_1ADD", "OP_1SUB", "OP_NEGATE", "OP_ABS", "OP_NOT",
				"OP_0NOTEQUAL"
			]:
				l = len(stack)
				if l < 1:
					return set_error(stack_len_error_str % (l, opcode_str))

				v1 = stack.pop()
				min_bytes = minimal_stack_bytes(v1)
				if min_bytes is not True:
					return set_error(
						"error in %s - %s" % (opcode_str, min_bytes)
					)
				v1 = stack_bin2int(v1)

				if "OP_1ADD" == opcode_str:
					res = v1 + 1
				elif "OP_1SUB" == opcode_str:
					res = v1 - 1
				elif "OP_NEGATE" == opcode_str:
					res = -v1
				elif "OP_ABS" == opcode_str:
					res = abs(v1)
				elif "OP_NOT" == opcode_str:
					res = 1 if (v1 == 0) else 0
				elif "OP_0NOTEQUAL" == opcode_str:
					res = 1 if (v1 != 0) else 0

				stack.append(stack_int2bin(res))

			elif opcode_str in [
				"OP_ADD", "OP_SUB", "OP_BOOLAND", "OP_BOOLOR", "OP_MIN",
				"OP_MAX", "OP_NUMEQUALVERIFY", "OP_NUMNOTEQUAL", "OP_LESSTHAN",
				"OP_NUMEQUAL", "OP_GREATERTHAN", "OP_LESSTHANOREQUAL",
				"OP_GREATERTHANOREQUAL"
			]:
				l = len(stack)
				if l < 2:
					return set_error(stack_len_error_str % (l, opcode_str))

				v2 = stack.pop()
				min_bytes = minimal_stack_bytes(v2)
				if min_bytes is not True:
					return set_error(
						"error in %s - %s" % (opcode_str, min_bytes)
					)
				v2 = stack_bin2int(v2)

				v1 = stack.pop()
				min_bytes = minimal_stack_bytes(v1)
				if min_bytes is not True:
					return set_error(
						"error in %s - %s" % (opcode_str, min_bytes)
					)
				v1 = stack_bin2int(v1)

				if "OP_ADD" == opcode_str:
					res = v1 + v2
				elif "OP_SUB" == opcode_str:
					res = v1 - v2
				elif "OP_BOOLAND" == opcode_str:
					res = 1 if (v1 != 0 and v2 != 0) else 0
				elif "OP_BOOLOR" == opcode_str:
					res = 1 if (v1 != 0 or v2 != 0) else 0
				elif "OP_NUMEQUAL" == opcode_str:
					res = 1 if (v1 == v2) else 0
				elif "OP_NUMEQUALVERIFY" == opcode_str:
					res = 1 if (v1 == v2) else 0
				elif "OP_NUMNOTEQUAL" == opcode_str:
					res = 1 if (v1 != v2) else 0
				elif "OP_LESSTHAN" == opcode_str:
					res = 1 if (v1 < v2) else 0
				elif "OP_GREATERTHAN" == opcode_str:
					res = 1 if (v1 > v2) else 0
				elif "OP_LESSTHANOREQUAL" == opcode_str:
					res = 1 if (v1 <= v2) else 0
				elif "OP_GREATERTHANOREQUAL" == opcode_str:
					res = 1 if (v1 >= v2) else 0
				elif "OP_MIN" == opcode_str:
					res = v1 if (v1 < v2) else v2
				elif "OP_MAX" == opcode_str:
					res = v1 if (v1 > v2) else v2

				if "OP_NUMEQUALVERIFY" == opcode_str:
					if not res:
						return set_error(
							"stack integers %d and %d differ" % (v1, v2)
						)

				stack.append(stack_int2bin(res))

			elif "OP_WITHIN" == opcode_str:
				l = len(stack)
				if l < 3:
					return set_error(stack_len_error_str % (l, opcode_str))

				v3 = stack.pop()
				min_bytes = minimal_stack_bytes(v3)
				if min_bytes is not True:
					return set_error(
						"error in %s - %s" % (opcode_str, min_bytes)
					)
				v3 = stack_bin2int(v3)

				v2 = stack.pop()
				min_bytes = minimal_stack_bytes(v2)
				if min_bytes is not True:
					return set_error(
						"error in %s - %s" % (opcode_str, min_bytes)
					)
				v2 = stack_bin2int(v2)

				v1 = stack.pop()
				min_bytes = minimal_stack_bytes(v1)
				if min_bytes is not True:
					return set_error(
						"error in %s - %s" % (opcode_str, min_bytes)
					)
				v1 = stack_bin2int(v1)

				stack.append(stack_int2bin(1 if (v2 <= v1 < v3) else 0))

			elif opcode_str in [
				"OP_SHA256", "OP_HASH256", "OP_RIPEMD160", "OP_SHA1",
				"OP_HASH160"
			]:
				# pop, hash, and add the result to the top of the stack
				l = len(stack)
				if l < 1:
					return set_error(stack_len_error_str % (l, opcode_str))

				v1 = stack.pop()

				if "OP_RIPEMD160" == opcode_str:
					res = ripemd160(v1)
				elif "OP_SHA1" == opcode_str:
					res = sha1(v1)
				elif "OP_SHA256" == opcode_str:
					res = sha256(v1)
				elif "OP_HASH160" == opcode_str:
					res = ripemd160(sha256(v1))
				elif "OP_HASH256" == opcode_str:
					res = sha256(sha256(v1))
				stack.append(res)

			elif "OP_CODESEPARATOR" == opcode_str:
				# the subscript starts at the next element up to the end of the
				# current (not entire) script
				subscript_list = copy.copy(script_list)

			elif opcode_str in ["OP_CHECKSIG", "OP_CHECKSIGVERIFY"]:
				l = len(stack)
				if l < 2:
					return set_error(stack_len_error_str % (l, opcode_str))
				pubkey = stack.pop()
				return_dict["pubkeys"].append(pubkey)
				signature = stack.pop()
				return_dict["signatures"].append(signature)

				if signature not in return_dict["sig_pubkey_statuses"]:
					return_dict["sig_pubkey_statuses"][signature] = {}
				if pubkey not in return_dict["sig_pubkey_statuses"][signature]:
					return_dict["sig_pubkey_statuses"][signature][pubkey] = res
				if not check_signature_encoding(signature):
					return set_error(
						"signature %s is not encoded correctly" % signature
					)
				if not check_pubkey_encoding(pubkey):
					return set_error(
						"pubkey %s is not encoded correctly" % pubkey
					)
				res = valid_checksig(
					wiped_tx, on_txin_num, subscript_list, pubkey, signature,
					bugs_and_all, explain
				)
				if "OP_CHECKSIGVERIFY" == opcode_str:
					# do not append result to the stack, but die here on error
					if res is not True:
						return set_error("%s fail: %s" % (opcode_str, res))
				if "OP_CHECKSIGVERIFY" == opcode_str:
					# append result to the stack and don't die on error
					stack.append(stack_int2bin(0 if (res is not True) else 1))

			elif opcode_str in ["OP_CHECKMULTISIG", "OP_CHECKMULTISIGVERIFY"]:
				# get all the signatures into a list, and all the pubkeys into a
				# list. starting from the top of the stack, moving down, looks
				# like this:
				#
				# [num_pubkeys (n)]
				# [pubkey n]
				# ...
				# [pubkey 3]
				# [pubkey 2]
				# [pubkey 1]
				# [num_signatures (m)]
				# [sig m]
				# ...
				# [sig 2]
				# [sig 1]
				#
				# then validate each signature against each pubkey. each
				# signature must validate against at least one pubkey for
				# OP_CHECKMULTISIG to pass. and m <= n. the order of validation
				# is also important - if sig2 validates against pubkey2, sig1
				# can only validate against pubkey1 (not pubkeys3 or pubkey2)

				l = len(stack)
				if l < 1:
					return set_error(
						"failed to count the number of public keys in %s"
						% (opcode_str)
					)
				num_pubkeys_bin = stack.pop()
				min_bytes = minimal_stack_bytes(num_pubkeys_bin)
				if min_bytes is not True:
					return set_error(
						"error with num pubkeys in %s - %s"
						% (opcode_str, min_bytes)
					)
				num_pubkeys = stack_bin2int(num_pubkeys_bin)

				# make sure we have an allowable number of pubkeys
				if (
					(num_pubkeys < 0) or
					(num_pubkeys > 20)
				):
					return set_error(
						"%d is an unacceptable number of public keys for %s"
						% (num_pubkeys, opcode_str)
					)

				op_count += num_pubkeys
				if op_count > (max_op_count + 1):
					return set_error(
						"more than %d operations used" % max_op_count + 1
					)

				# read the pubkeys from the stack into a new list
				pubkeys = []
				try:
					for i in range(num_pubkeys):
						pubkey = stack.pop()
						pubkeys.append(pubkey)
						return_dict["pubkeys"].append(pubkey)
					# pubkeys = [pubkey3, pubkey2, pubkey1]
				except:
					return set_error(
						"failed to get %d public keys off the stack in %s"
						% (num_pubkeys, opcode_str)
					)

				l = len(stack)
				if l < 1:
					return set_error(
						"failed to count the number of signatures in %s"
						% opcode_str
					)
				num_signatures_bin = stack.pop()
				min_bytes = minimal_stack_bytes(num_signatures_bin)
				if min_bytes is not True:
					return set_error(
						"error with num signatures in %s - %s"
						% (opcode_str, min_bytes)
					)
				num_signatures = stack_bin2int(num_signatures_bin)

				if (
					(num_signatures < 0) or
					(num_signatures > num_pubkeys)
				):
					return set_error(
						"%d is an unacceptable number of signatures for %s."
						" number of public keys: %d"
						% (num_signatures, opcode_str, num_pubkeys)
					)

				# read the signatures from the stack into a new list
				signatures = []
				try:
					for i in range(num_signatures):
						signature = stack.pop()
						signatures.append(signature)
						return_dict["signatures"].append(signature)
					# signatures = [sig3, sig2, sig1]
				except:
					return set_error(
						"failed to get %d signatures off the stack in %s"
						% (num_signatures, opcode_str)
					)

				if bugs_and_all:
					# reproduce the bug that pops an extra element off the stack
					try:
						bug_byte = stack.pop()
					except:
						return set_error(
							"failed to pop the final (bug) element off the"
							" stack in %s" % opcode_str
						)
					# the byte here could be altered by a miner to alter the tx
					# hash without the private-key-holder knowing (mutability).
					# to prevent this mutability, ensure that this byte == 0
					bug_int = stack_bin2int(bug_byte)
					if bug_int != 0:
						return set_error(
							"the final (bug) element should be zero. %s found"
							% bin2hex(bug_byte)
						)

				# each pubkey can only be used once so pop them off the list:
				# pubkeys = [pubkey3, pubkey2, pubkey1] starting with pubkey3
				each_sig_passes = True
				for signature in signatures:
					if signature not in return_dict["sig_pubkey_statuses"]:
						return_dict["sig_pubkey_statuses"][signature] = {}
					sig_pass = False # init
					while len(pubkeys):
						pubkey = pubkeys.pop(0)
						res = valid_checksig(
							wiped_tx, on_txin_num, subscript_list, pubkey,
							signature, bugs_and_all, explain
						)
						return_dict["sig_pubkey_statuses"][signature] \
						[pubkey] = res
						if res is True:
							sig_pass = True
							break

					if not sig_pass:
						each_sig_passes = False
						# if one of the signatures does not pass then still
						# evaluate the rest, so as to populate return_dict

				#each_sig_passes = False # debug use only
				if "OP_CHECKMULTISIGVERIFY" == opcode_str:
					# do not append result to the stack, but die here on error
					if not each_sig_passes:
						return set_error(
							"some signatures failed %s"
							% opcode_str
						)
				if "OP_CHECKMULTISIGVERIFY" == opcode_str:
					# append result to the stack and don't die on error
					stack.append(stack_int2bin(0 if each_sig_passes else 1))

			else:
				return set_error("unrecognized opcode %s" % opcode_str)

		# still inside while loop
		if (len(stack) + len(alt_stack)) > 1000:
			return set_error(
				"stack has %d elements and alt stack has %d elements - this"
				" comes to more than 1000 elements total"
				% (len(stack), len(alt_stack))
			)

	if len(ifelse_conditions):
		return set_error("unblanaced conditional")

	# if we get here then everything is ok with the script
	return_dict["status"] = True
	return (return_dict, stack)

def stack2human_str(stack):
	if not stack:
		return "*empty*"
	else:
		return " ".join(bin2hex(el) for el in stack),

def stack_el2bool(v1):
	if (
		(v1 == "") or
		(stack_bin2int(v1) == 0)
	):
		return False
	else:
		return True

def stack_bool2el(v1):
	return stack_int2bin(1 if v1 else 0)

def stack_int2bin(stack_element_int):
	"""
	convert an element of the script stack from an integers to a byte. negative
	numbers are represented by setting the most significant bit in the most
	significant byte. if this bit is already set then another empty byte with
	this bit set is added on infront and results are converted to little endian:
	this function input -> this function output
	-0x7f -> 0xff
	0x7f -> 0x7f
	-0xff -> 0x80ff -> 0xff80
	0xff -> 0x00ff -> 0xff00 (output 0xff would be a negative number)
	"""
	neg = stack_element_int < 0
	stack_element_bin = int2bin(abs(stack_element_int))
	top_byte_int = bin2int(stack_element_bin[0])

	if top_byte_int & 0x80:
		# if the most significant bit is already set
		if neg:
			# negative numbers must now be represented by appending an 0x80 byte
			return little_endian("\x80%s" % stack_element_bin)
		else:
			# positive numbers must now be represented by appending a 0x00 byte
			return little_endian("\x00%s" % stack_element_bin)
	else:
		# if the most significant bit is not set
		if neg:
			# negative numbers must now be represented by flipping the most
			# significant bit (this can be done by adding 0x80 to it). for the
			# remaining bytes note that "abc"[7:] == ""
			return little_endian(
				"%s%s" % (int2bin(top_byte_int + 0x80), stack_element_bin[1: ])
			)
		else:
			# positive numbers here are fine as they are
			return little_endian(stack_element_bin)

def stack_bin2int(stack_element_bytes):
	"""
	equivalent to part of the CScriptNum constructor in src/script/script.h

	convert an element of the script stack from binary into an integer. the main
	purpose of this function is to handle negative integers.
	0xff -> -0x7f
	0xff80 -> 0x80ff -> -0xff
	0xff00 -> 0x00ff -> 0xff
	0xff0000 -> 0x0000ff -> 0xff
	0xff0080 -> 0x8000ff -> -0xff
	(verify this with ff80 OP_NEGATE OP_NEGATE in webbtc.com/script)
	"""
	stack_element_bytes = little_endian(stack_element_bytes)
	# if the most significant bit of the most significant byte is set then this
	# is a negative number

	top_byte_int = bin2int(stack_element_bytes[0])
	neg = top_byte_int & 0x80
	if not neg:
		return bin2int(stack_element_bytes)

	# from here on, we need to convert the bytes into a negative integer

	abs_bin = "%s%s" % (int2bin(top_byte_int & 0x7f), stack_element_bytes[1: ])
	return -bin2int(abs_bin)

def minimal_stack_bytes(stack_element_bytes, max_bytes = 4):
	"""
	equivalent to part of the CScriptNum constructor in src/script/script.h

	check that the number is encoded with the minimum possible number of bytes.

	the easiest way to do this is to simply convert to int, then back to binary
	and compare the number of bytes with the original.
	"""
	length = len(stack_element_bytes)

	if not length:
		return True

	if length > max_bytes:
		return "stack element %s has more than %d bytes" \
		% (bin2hex(stack_element_bytes), max_bytes)

	stack_element_int = stack_bin2int(stack_element_bytes)
	recalc = stack_int2bin(stack_element_int)
	if len(recalc) == length:
		return True
	else:
		return "a more minimal encoding for stack element %s (int %s) exists:" \
		" %s" \
		% (bin2hex(stack_element_bytes), stack_element_int, bin2hex(recalc))

def check_minimal_push(pushdata_val_bin, opcode_str):
	"""
	could the pushdata have been done more efficiently?
	this function is the same as CheckMinimalPush() in the satoshi source code
	"""
	pushdata_len = len(pushdata_val_bin) # used frequently
	if pushdata_len == 0:
		# could have used OP_0
		return opcode_str == "OP_0"
	elif (
		(pushdata_len == 1) and
		(bin2int(pushdata_val_bin) >= 1) and
		(bin2int(pushdata_val_bin) <= 16)
	):
		# could have used OP_1-OP_16
		return opcode_str in [("OP_%d" % x) for x in range(1, 17)]
	elif (
		(pushdata_len == 1) and
		(bin2int(pushdata_val_bin) == 0x81)
	):
		# could have used OP_1NEGATE
		return opcode_str == "OP_1NEGATE"
	elif pushdata_len <= 75:
		# could have used OP_PUSHDATA0
		return opcode_str == "OP_PUSHDATA0(%d)" % pushdata_len
	elif pushdata_len <= 255:
		# could have used OP_PUSHDATA1
		return "OP_PUSHDATA1" in opcode_str
	elif pushdata_len <= 65535:
		# could have used OP_PUSHDATA2
		return "OP_PUSHDATA2" in opcode_str

	# if we get here then the pushdata opcode is as efficient as possible
	return True

def is_push_only(script_list, explain = False):
	push_only_opcodes = [
		"OP_PUSHDATA0", "OP_PUSHDATA1", "OP_PUSHDATA2", "OP_PUSHDATA4",
		"OP_TRUE", "OP_FALSE", "OP_TRUE", "OP_1NEGATE", "OP_RESERVED"
	]
	push_only_opcodes.extend(("OP_%d" % x) for x in range(1, 17))

	for el in script_list:
		opcode_str = bin2opcode(el)
		if opcode_str not in push_only_opcodes:
			return False
	return True

def bits2target_int(bits_bytes):
	# TODO - this will take forever as the exponent gets large - modify to use
	# taylor series
	exp = bin2int(bits_bytes[: 1]) # exponent is the first byte
	mult = bin2int(bits_bytes[1:]) # multiplier is all but the first byte
	return mult * (2 ** (8 * (exp - 3)))

# difficulty_1 = bits2target_int(initial_bits)
difficulty_1 = 0x00000000ffff0000000000000000000000000000000000000000000000000000
def bits2difficulty(bits_bytes):
	return difficulty_1 / float(bits2target_int(bits_bytes))

def target_int2bits(target):
	# comprehensive explanation here: bitcoin.stackexchange.com/a/2926/2116

	# get in base 256 as a hex string
	target_hex = int2hex(target)

	bits = "00" if (hex2int(target_hex[: 2]) > 127) else ""
	bits += target_hex # append
	bits = hex2bin(bits)
	length_bin = int2bin(len(bits), 1)

	# the bits value could be zero (0x00) so make sure it is at least 3 bytes
	bits += hex2bin("0000")

	# the bits value could be bigger than 3 bytes, so cut it down to size
	bits = bits[: 3]

	return "%s%s" % (length_bin, bits)

def tx_balances(txs, addresses):
	"""
	take a list of transactions and a list of addresses and output a dict of the
	balance for each address. note that it is possible to end up with negative
	balances when the txs are from an incomplete range of the blockchain
	"""
	balances = {addr: 0 for addr in addresses} # init balances to 0
	done_txs = [] # only process each tx once

	for tx in txs: # unique

		# only process each tx once
		if tx["hash"] in done_txs:
			continue

		done_txs.append(tx["hash"])

		for txin_num in tx["input"]:

			# no address - irrelevant transaction
			if tx["input"][txin_num]["addresses"] is None:
				continue

			# do not update the balance unless the transaction is verified
			if tx["input"][txin_num]["verification_succeeded"] is not True:
				continue

			# irrelevant addresses - skip to next
			address_match = False
			for address in tx["input"][txin_num]["addresses"]:
				if address in addresses:
					address_match = True

			if not address_match:
				continue

			# print "- %s btc %s in tx %s" % (tx["input"][txin_num]["funds"], tx["input"][txin_num]["address"], bin2hex(tx["hash"])) # debug use only

			funds = tx["input"][txin_num]["funds"]
			balances[tx["input"][txin_num]["addr"]] -= funds

		for output_num in tx["output"]:

			# no address - irrelevant transaction
			if tx["output"][output_num]["address"] is None:
				continue

			# irrelevant address - skip to next
			address_match = False
			for address in tx["output"][output_num]["addresses"]:
				if address not in addresses:
					address_match = True

			if not address_match:
				continue

			# print "+ %s btc %s in tx %s" % (tx["output"][output_num]["funds"], tx["output"][output_num]["address"], bin2hex(tx["hash"])) # debug use only

			funds = tx["output"][output_num]["funds"]
			balances[tx["output"][output_num]["addr"]] += funds

	return balances

def sha1(bytes):
	"""takes binary, performs sha1 hash, returns binary"""
	# .digest() keeps the result in binary, .hexdigest() outputs as hex string
	return hashlib.sha1(bytes).digest()

def sha256(bytes):
	"""takes binary, performs sha256 hash, returns binary"""
	# .digest() keeps the result in binary, .hexdigest() outputs as hex string
	return hashlib.sha256(bytes).digest()

def ripemd160(bytes):
	"""takes binary, performs ripemd160 hash, returns binary"""
	# must use the following format, rather than hashlib.ripemd160(), since
	# ripemd160 is not native to hashlib
	res = hashlib.new("ripemd160")
	res.update(bytes)
	return res.digest()

def little_endian(bytes):
	"""
	takes binary, performs little endian (ie reverse the bytes), returns binary
	"""
	return bytes[:: -1]

def extract_scripts_from_input(input_str):
	"""take an input string and create a list of the scripts it contains"""

	# literal_eval is safer than eval - elements can only be string, numbers,
	# etc
	input_dict = ast.literal_eval(input_str)

	scripts = []
	for (tx_num, tx_data) in input_dict.items():
		coinbase = True if (tx_data["hash"] == blank_hash) else False
		scripts.append(tx_data["script"])
	return {"coinbase": coinbase, "scripts": scripts}

def script2pubkey(script):
	"""
	get the public key from the transaction input or output script. if the
	pubkey cannot be found then return None. and if the script cannot be decoded
	then return False.
	"""
	if isinstance(script, str):
		# assume script is a binary string. first try without an explanation.
		script_list = script_bin2list(script, explain = False)
		if script_list is False:
			# we get here if the script cannot be converted into a list
			return False
	elif isinstance(script, list):
		script_list = script
	else:
		return None

	script_format = extract_script_format(script_list)
	pubkey = None # init

	# OP_PUSHDATA0(33/65) <pubkey> OP_CHECKSIG
	if script_format == "pubkey":
		pubkey = script_list[1]

	# OP_PUSHDATA0(73) <signature> OP_PUSHDATA0(33/65) <pubkey>
	# or even OP_PUSHDATA1(76) <signature> OP_PUSHDATA0(33/65) <pubkey>
	elif script_format == "sigpubkey":
		pubkey = script_list[3]

	return pubkey

def script2signature(script):
	"""
	get the signature from the transaction script (ought to be the later txin).
	if the signature cannot be found then return None. and if the script cannot
	be decoded then return False.
	"""
	if isinstance(script, str):
		# assume script is a binary string
		script_list = script_bin2list(script, explain = False)
		if script_list is False:
			# we get here if the script cannot be converted into a list
			return False
	elif isinstance(script, list):
		script_list = script
	else:
		return None

	script_format = extract_script_format(script_list)

	# txin: OP_PUSHDATA0(73) <signature> OP_PUSHDATA0(33/65) <pubkey>
	if script_format in ["sigpubkey", "scriptsig"]:
		return script_list[1]

	return None

def script2addresses(script_list, format_type = None):
	"""
	extract the bitcoin addresses from the binary script (input, output, or
	both)
	"""
	if format_type is None:
		format_type = extract_script_format(script_list)

	if format_type is None:
		return None

	# OP_PUSHDATA0(33/65) <pubkey> OP_CHECKSIG
	if format_type == "pubkey":
		return [pubkey2address(script_list[1])]

	# OP_DUP OP_HASH160 OP_PUSHDATA0(20) <hash160> OP_EQUALVERIFY OP_CHECKSIG
	if format_type == "hash160":
		return [hash1602address(script_list[3], "pub_key_hash")]

	# OP_PUSHDATA0(73) <signature> OP_PUSHDATA0(33/65) <pubkey>
	if format_type == "sigpubkey":
		return [pubkey2address(script_list[3])]

	# OP_PUSHDATA <signature>
	if format_type == "scriptsig":
		# no address in a scriptsig
		return None

	# OP_PUSHDATA <signature> OP_PUSHDATA0(33/65) <pubkey> OP_CHECKSIG
	if format_type == "scriptsig-pubkey":
		return [pubkey2address(script_list[3])]

	# OP_PUSHDATA0(73) <signature> OP_PUSHDATA0(33/65) <pubkey> OP_DUP
	# OP_HASH160 OP_PUSHDATA0(20) <hash160> OP_EQUALVERIFY OP_CHECKSIG
	if format_type == "sigpubkey-hash160":
		return [pubkey2address(script_list[3])]

	# OP_HASH160 OP_PUSHDATA0(20) <redeem-script-hash> OP_EQUAL
	if format_type == "p2sh-txout":
		return [hash1602address(script_list[2], "script_hash")]

	# unrecognized standard format - script eval may get the address
	return None
	#raise ValueError("unrecognized format type %s" % format_type)

def script_dict2addresses(script_dict, desired_status):
	"""
	extract addresses from the script dict that is in the format: {
		"status": True/False/"explanation of failure",
		"pubkeys": [],
		"signatures": [],
		"sig_pubkey_statuses": {sig0: {pubkey0: True, pubkey1: False}, ...}
	}
	if the desired_status is "valid" then only return those addresses
	corresponding to sig-pubkey pairs with a status of True. if the
	desired_status is "invalid" then only return those addresses corresponding
	to sig-pubkey pairs with a status of False or "explanation of failure".
	"""
	addresses = [] # init
	for (signature, pubkeys) in script_dict["sig_pubkey_statuses"].items():
		for (pubkey, status) in pubkeys.items():
			if desired_status is "valid":
				if status is True:
					addresses.append(pubkey2address(pubkey))
			elif desired_status is "invalid":
				if status is not True:
					addresses.append(pubkey2address(pubkey))
			else:
				raise ValueError("unrecognized status: %s" % desired_status)

	return addresses

def extract_script_format(script):
	"""compare the script to some known standard format types"""
	# only two input formats recognized - list of binary strings, and binary str
	if isinstance(script, list):
		script_list = script
	else:
		script_list = script_bin2list(script, explain = False) # explode
		if script_list is False:
			# the script could not be parsed into a list
			return None

	# remove all OP_NOPs
	script_list = [
		i for i in script_list if (
			(len(i) != 1) or # if length is not 1 then it can't be op_nop
			("OP_NOP" not in bin2opcode(i)) # slower check for other opcodes
		)
	]
	# TODO - ensure all the isstandard() scripts are in here
	# evaluate all used opcodes, for speed
	OP_HASH160 = opcode2bin("OP_HASH160")
	OP_CHECKSIG = opcode2bin("OP_CHECKSIG")
	OP_DUP = opcode2bin("OP_DUP")
	OP_EQUALVERIFY = opcode2bin("OP_EQUALVERIFY")
	OP_EQUAL = opcode2bin("OP_EQUAL")
	recognized_formats = {
		"pubkey": ["OP_PUSHDATA", "pubkey", OP_CHECKSIG],
		"hash160": [
			OP_DUP, OP_HASH160, opcode2bin("OP_PUSHDATA0(20)"), "hash160",
			OP_EQUALVERIFY, OP_CHECKSIG
		],
		"scriptsig": ["OP_PUSHDATA", "signature"],
		"sigpubkey": ["OP_PUSHDATA", "signature", "OP_PUSHDATA", "pubkey"],
		"p2sh-txout": [
			OP_HASH160, opcode2bin("OP_PUSHDATA0(20)"), "redeem-script-hash",
			OP_EQUAL
		]
	}
	recognized_formats["scriptsig-pubkey"] = recognized_formats["scriptsig"] + \
	recognized_formats["pubkey"]

	recognized_formats["sigpubkey-hash160"] = \
	recognized_formats["sigpubkey"] + recognized_formats["hash160"]

	for (format_type, format_opcodes) in recognized_formats.items():
		# try next format
		if len(format_opcodes) != len(script_list):
			continue

		# we have the correct number of script elements from here on...

		last_format_el_num = len(format_opcodes) - 1
		# loop through the recognized formats until we have an exact match
		for (format_opcode_el_num, format_opcode) in enumerate(format_opcodes):
			# the actual value of the element in the script
			script_el_value = script_list[format_opcode_el_num]

			# validate the bin opcodes and their positions in the script
			if format_opcode == script_el_value:
				confirmed_format = format_type
			elif (
				(format_opcode == "OP_PUSHDATA") and
				(len(script_el_value) <= 5) and # OP_PUSHDATA max len is 5
				("OP_PUSHDATA" in bin2opcode(script_el_value))
			):
				confirmed_format = format_type
			elif (
				(format_opcode_el_num in [1, 3]) and
				(format_opcode == "pubkey") and
				(len(script_el_value) in [33, 65])
			):
				confirmed_format = format_type
			elif (
				# 3: "hash160", 7: "sigpubkey-hash160"
				(format_opcode_el_num in [3, 7]) and
				(format_opcode == "hash160") and
				(len(script_el_value) == 20)
			):
				confirmed_format = format_type
			elif (
				(format_opcode_el_num == 2) and
				(format_opcode == "redeem-script-hash") and
				(len(script_el_value) == 20)
			):
				confirmed_format = format_type
			elif (
				(format_opcode_el_num == 1) and
				(format_opcode == "signature")
			):
				confirmed_format = format_type
			else:
				confirmed_format = None # reset
				# break out of inner for-loop and try the next format type
				break

			if format_opcode_el_num == last_format_el_num: # last
				if confirmed_format is not None:
					return format_type

	# could not determine the format type :(
	return None

def script_bin2list(bytes, explain = False):
	"""
	split the script into elements of a list. input is a string of bytes, output
	is a list of bytes.
	return the list if the script is valid. if the script is not valid then
	either return False if the explain argument is not set, otherwise
	return a human readable string with an explanation of the failure.
	"""
	if len(bytes) > max_script_size:
		if explain:
			return "Error: Length %s for script %s exceeds the allowed" \
			" maximum of %s." \
			% (len(bytes), bin2hex(bytes), max_script_size)
		else:
			return False

	script_list = []
	pos = 0
	opcode_count = 0
	while len(bytes[pos:]):
		byte = bytes[pos: pos + 1]
		parsed_opcode = bin2opcode(byte)
		opcode_count += 1

		if parsed_opcode is None:
			# bad opcode - exit the loop here
			if explain:
				return "Error: Unrecognized opcode %s in script %s." \
				% (bin2hex(byte), bin2hex(bytes))
			else:
				return False

		elif "OP_PUSHDATA" in parsed_opcode:
			(pushdata_str, push_num_bytes, num_used_bytes) = \
			pushdata_bin2opcode(bytes[pos:])

			if push_num_bytes > max_script_element_size:
				if explain:
					return "Error: Cannot push %s bytes (%s) onto the stack" \
					" in script %s since this exceeds the allowed maximum %s." \
					% (
						push_num_bytes, parsed_opcode, bin2hex(bytes),
						max_script_element_size
					)
				else:
					return False

			# add the pushdata opcode (could be more than 1 byte) to the list
			script_list.append(bytes[pos: pos + num_used_bytes])
			pos += num_used_bytes
			if len(bytes[pos:]) < push_num_bytes:
				if explain:
					return "Error: Cannot push %s bytes (%s) onto the stack" \
					" in script %s since there are not enough bytes left." \
					% (push_num_bytes, parsed_opcode, bin2hex(bytes))
				else:
					return False

			script_list.append(bytes[pos: pos + push_num_bytes])
			pos += push_num_bytes
		else:
			# all other opcodes have a length of 1 byte
			script_list.append(byte)
			pos += 1

	if opcode_count > max_op_count:
		# inaccurate but good enough for a quick check (since opcodes =/= ops)
		if explain:
			return "Error: Script %s has %s opcodes, which exceeds the" \
			" allowed maximum of %s opcodes." \
			% (bin2hex(bytes), opcode_count, max_op_count)
		else:
			return False

	return script_list

def script_list2human_str(script_list_bin):
	"""
	take a list whose elements are bytes and output a human readable bitcoin
	script (ie replace opcodes and convert bin to hex for pushed data)

	no sanitization is done here.
	"""
	human_str = ""

	# set to true once the next list element is to be pushed to the stack
	push = False # init

	for bytes in script_list_bin:
		if push:
			# the previous element was OP_PUSHDATA
			human_str += bin2hex(bytes)
			push = False # reset
		else:
			parsed_opcode = bin2opcode(bytes[: 1])
			if "OP_PUSHDATA" in parsed_opcode:
				# this is the only opcode that can be more than 1 byte long
				(pushdata_str, push_num_bytes, num_used_bytes) = \
				pushdata_bin2opcode(bytes)
				human_str += pushdata_str

				# push the next element onto the stack
				push = True
			else:
				human_str += parsed_opcode

		human_str += " "

	return human_str.strip()

def human_script2bin_list(human_str):
	"""
	take a human-readable string and return a list whose elements are binary
	bytes. do not perform any validation on pushdata lengths here.
	"""
	human_list = human_str.split(" ")
	bin_list = [] # init
	push = False # init
	for human_el in human_list:
		if push:
			# the previous element was OP_PUSHDATA
			bin_list.append(hex2bin(human_el))
			push = False # reset
		else:
			bin_opcode = opcode2bin(human_el)
			if bin_opcode is False:
				# the human element could not be converted to bin (eg it could
				# be out of bounds)
				return False
			bin_list.append(bin_opcode)
			if "OP_PUSHDATA" in human_el:
				# push the next element onto the stack
				push = True

	return bin_list

def script_list2bin(script_list):
	"""take a list whose elements are bytes and return a binary string"""
	return "".join(script_list)

def int2hashtype(hashtype_int):
	"""
	decode the hash types from the binary byte (that comes from the end of the
	signature) and return as a list of strings
	https://github.com/bitcoin/bitcoin/blob/
	41e6e4caba9899ce7c165b0784461c55c867ee24/src/script/interpreter.cpp
	"""
	hashtypes = []
	if (hashtype_int & 0x1f) == 2:
		hashtypes.append("SIGHASH_NONE")
	if (hashtype_int & 0x1f) == 3:
		hashtypes.append("SIGHASH_SINGLE")
	if (hashtype_int & 0x80) == 0x80:
		hashtypes.append("SIGHASH_ANYONECANPAY")
	# if none of the other hashtypes match, then default to SIGHASH_ALL
	# as per https://bitcointalk.org/index.php?topic=120836.0
	if not hashtypes:
		hashtypes.append("SIGHASH_ALL")

	return hashtypes

def bin2opcode(code_bin):
	"""
	decode a single byte into the corresponding opcode as per
	https://en.bitcoin.it/wiki/script
	"""
	if code_bin == "":
		return "OP_FALSE"
	code = ord(code_bin[0])
	if code == 0:
		# an empty array of bytes is pushed onto the stack. (this is not a
		# no-op: an item is added to the stack)
		return "OP_FALSE"
	elif code <= 75:
		# this opcode byte is the number of bytes to be pushed onto the stack
		return "OP_PUSHDATA0"
	elif code == 76:
		# the next byte is the number of bytes to be pushed onto the stack
		return "OP_PUSHDATA1"
	elif code == 77:
		# the next two bytes are the number of bytes to be pushed onto the stack
		return "OP_PUSHDATA2"
	elif code == 78:
		# the next four bytes are the number of bytes to be pushed onto the
		# stack
		return "OP_PUSHDATA4"
	elif code == 79:
		# the number -1 is pushed onto the stack
		return "OP_1NEGATE"
	elif code == 81:
		# the number 1 is pushed onto the stack
		return "OP_TRUE"
	elif code == 82:
		# the number 2 is pushed onto the stack
		return "OP_2"
	elif code == 83:
		# the number 3 is pushed onto the stack
		return "OP_3"
	elif code == 84:
		# the number 4 is pushed onto the stack
		return "OP_4"
	elif code == 85:
		# the number 5 is pushed onto the stack
		return "OP_5"
	elif code == 86:
		# the number 6 is pushed onto the stack
		return "OP_6"
	elif code == 87:
		# the number 7 is pushed onto the stack
		return "OP_7"
	elif code == 88:
		# the number 8 is pushed onto the stack
		return "OP_8"
	elif code == 89:
		# the number 9 is pushed onto the stack
		return "OP_9"
	elif code == 90:
		# the number 10 is pushed onto the stack
		return "OP_10"
	elif code == 91:
		# the number 11 is pushed onto the stack
		return "OP_11"
	elif code == 92:
		# the number 12 is pushed onto the stack
		return "OP_12"
	elif code == 93:
		# the number 13 is pushed onto the stack
		return "OP_13"
	elif code == 94:
		# the number 14 is pushed onto the stack
		return "OP_14"
	elif code == 95:
		# the number 15 is pushed onto the stack
		return "OP_15"
	elif code == 96:
		# the number 16 is pushed onto the stack
		return "OP_16"

	# flow control
	elif code == 97:
		# does nothing
		return "OP_NOP"
	elif code == 99:
		# if the top stack value is not 0, the statements are executed. the top
		# stack value is removed.
		return "OP_IF"
	elif code == 100:
		# if the top stack value is 0, the statements are executed. the top
		# stack value is removed.
		return "OP_NOTIF"
	elif code == 103:
		# if the preceding OP_IF or OP_NOTIF or OP_ELSE was not executed then
		# these statements are and if the preceding OP_IF or OP_NOTIF or OP_ELSE
		# was executed then these statements are not.
		return "OP_ELSE"
	elif code == 104:
		# ends an if/else block. All blocks must end, or the transaction is
		# invalid. An OP_ENDIF without OP_IF earlier is also invalid.
		return "OP_ENDIF"
	elif code == 105:
		# marks transaction as invalid if top stack value is not true.
		return "OP_VERIFY"
	elif code == 106:
		# marks transaction as invalid
		return "OP_RETURN"

	# stack
	elif code == 107:
		# put the input onto the top of the alt stack. remove it from the main
		# stack
		return "OP_TOALTSTACK"
	elif code == 108:
		# put the input onto the top of the main stack. remove it from the alt
		# stack
		return "OP_FROMALTSTACK"
	elif code == 115:
		# if the top stack value is not 0, duplicate it
		return "OP_IFDUP"
	elif code == 116:
		# puts the number of stack items onto the stack
		return "OP_DEPTH"
	elif code == 117:
		# removes the top stack item
		return "OP_DROP"
	elif code == 118:
		# duplicates the top stack item
		return "OP_DUP"
	elif code == 119:
		# removes the second-to-top stack item
		return "OP_NIP"
	elif code == 120:
		# copies the second-to-top stack item to the top
		return "OP_OVER"
	elif code == 121:
		# the item n back in the stack is copied to the top
		return "OP_PICK"
	elif code == 122:
		# the item n back in the stack is moved to the top
		return "OP_ROLL"
	elif code == 123:
		# the top three items on the stack are rotated to the left
		return "OP_ROT"
	elif code == 124:
		# the top two items on the stack are swapped
		return "OP_SWAP"
	elif code == 125:
		# the item at the top of the stack is copied and inserted before the
		# second-to-top item
		return "OP_TUCK"
	elif code == 109:
		# removes the top two stack items
		return "OP_2DROP"
	elif code == 110:
		# duplicates the top two stack items
		return "OP_2DUP"
	elif code == 111:
		# duplicates the top three stack items
		return "OP_3DUP"
	elif code == 112:
		# copies the pair of items two spaces back in the stack to the front
		return "OP_2OVER"
	elif code == 113:
		# the fifth and sixth items back are moved to the top of the stack
		return "OP_2ROT"
	elif code == 114:
		# swaps the top two pairs of items
		return "OP_2SWAP"

	# splice
	elif code == 126:
		# concatenates two strings. disabled
		return "OP_CAT"
	elif code == 127:
		# returns a section of a string. disabled
		return "OP_SUBSTR"
	elif code == 128:
		# keeps only characters left of the specified point in a string.
		# disabled
		return "OP_LEFT"
	elif code == 129:
		# keeps only characters right of the specified point in a string.
		# disabled
		return "OP_RIGHT"
	elif code == 130:
		# returns the length of the input string
		return "OP_SIZE"

	# bitwise logic
	elif code == 131:
		# flips all of the bits in the input. disabled
		return "OP_INVERT"
	elif code == 132:
		# boolean and between each bit in the inputs. disabled
		return "OP_AND"
	elif code == 133:
		# boolean or between each bit in the inputs. disabled
		return "OP_OR"
	elif code == 134:
		# boolean exclusive or between each bit in the inputs. disabled
		return "OP_XOR"
	elif code == 135:
		# returns 1 if the inputs are exactly equal, 0 otherwise
		return "OP_EQUAL"
	elif code == 136:
		# same as OP_EQUAL, but runs OP_VERIFY afterward
		return "OP_EQUALVERIFY"

	# arithmetic
	elif code == 139:
		# 1 is added to the input
		return "OP_1ADD"
	elif code == 140:
		# 1 is subtracted from the input
		return "OP_1SUB"
	elif code == 141:
		# the input is multiplied by 2. disabled
		return "OP_2MUL"
	elif code == 142:
		# the input is divided by 2. disabled
		return "OP_2DIV"
	elif code == 143:
		# the sign of the input is flipped
		return "OP_NEGATE"
	elif code == 144:
		# the input is made positive
		return "OP_ABS"
	elif code == 145:
		# if the input is 0 or 1, it is flipped. Otherwise the output will be 0
		return "OP_NOT"
	elif code == 146:
		# returns 0 if the input is 0. 1 otherwise
		return "OP_0NOTEQUAL"
	elif code == 147:
		# a is added to b
		return "OP_ADD"
	elif code == 148:
		# b is subtracted from a
		return "OP_SUB"
	elif code == 149:
		# a is multiplied by b. disabled
		return "OP_MUL"
	elif code == 150:
		# a is divided by b. disabled
		return "OP_DIV"
	elif code == 151:
		# returns the remainder after dividing a by b. disabled
		return "OP_MOD"
	elif code == 152:
		# shifts a left b bits, preserving sign. disabled
		return "OP_LSHIFT"
	elif code == 153:
		# shifts a right b bits, preserving sign. disabled
		return "OP_RSHIFT"
	elif code == 154:
		# if both a and b are not 0, the output is 1. Otherwise 0
		return "OP_BOOLAND"
	elif code == 155:
		# if a or b is not 0, the output is 1. Otherwise 0
		return "OP_BOOLOR"
	elif code == 156:
		# returns 1 if the numbers are equal, 0 otherwise
		return "OP_NUMEQUAL"
	elif code == 157:
		# same as OP_NUMEQUAL, but runs OP_VERIFY afterward
		return "OP_NUMEQUALVERIFY"
	elif code == 158:
		# returns 1 if the numbers are not equal, 0 otherwise
		return "OP_NUMNOTEQUAL"
	elif code == 159:
		# returns 1 if a is less than b, 0 otherwise
		return "OP_LESSTHAN"
	elif code == 160:
		# returns 1 if a is greater than b, 0 otherwise
		return "OP_GREATERTHAN"
	elif code == 161:
		# returns 1 if a is less than or equal to b, 0 otherwise
		return "OP_LESSTHANOREQUAL"
	elif code == 162:
		# returns 1 if a is greater than or equal to b, 0 otherwise
		return "OP_GREATERTHANOREQUAL"
	elif code == 163:
		# returns the smaller of a and b
		return "OP_MIN"
	elif code == 164:
		# returns the larger of a and b
		return "OP_MAX"
	elif code == 165:
		# returns 1 if x is within the specified range (left-inclusive), else 0
		return "OP_WITHIN"

	# crypto
	elif code == 166:
		# the input is hashed using RIPEMD-160
		return "OP_RIPEMD160"
	elif code == 167:
		# the input is hashed using SHA-1
		return "OP_SHA1"
	elif code == 168:
		# the input is hashed using SHA-256
		return "OP_SHA256"
	elif code == 169:
		# the input is hashed twice: first with SHA-256 and then with RIPEMD-160
		return "OP_HASH160"
	elif code == 170:
		# the input is hashed two times with SHA-256
		return "OP_HASH256"
	elif code == 171:
		# only match signatures after the latest OP_CODESEPARATOR
		return "OP_CODESEPARATOR"
	elif code == 172:
		# hash all transaction outputs, inputs, and script. return 1 if valid
		return "OP_CHECKSIG"
	elif code == 173:
		# same as OP_CHECKSIG, but OP_VERIFY is executed afterward
		return "OP_CHECKSIGVERIFY"
	elif code == 174:
		# execute OP_CHECKSIG for each signature and public key pair
		return "OP_CHECKMULTISIG"
	elif code == 175:
		# same as OP_CHECKMULTISIG, but OP_VERIFY is executed afterward
		return "OP_CHECKMULTISIGVERIFY"

	# pseudo-words
	elif code == 253:
		# represents a public key hashed with OP_HASH160
		return "OP_PUBKEYHASH"
	elif code == 254:
		# represents a public key compatible with OP_CHECKSIG
		return "OP_PUBKEY"
	elif code == 255:
		# any opcode that is not yet assigned
		return "OP_INVALIDOPCODE"

	# reserved words
	elif code == 80:
		# transaction is invalid unless occuring in an unexecuted OP_IF branch
		return "OP_RESERVED"
	elif code == 98:
		# transaction is invalid unless occuring in an unexecuted OP_IF branch
		return "OP_VER"
	elif code == 101:
		# transaction is invalid even when occuring in an unexecuted OP_IF
		# branch
		return "OP_VERIF"
	elif code == 102:
		# transaction is invalid even when occuring in an unexecuted OP_IF
		# branch
		return "OP_VERNOTIF"
	elif code == 137:
		# transaction is invalid unless occuring in an unexecuted OP_IF branch
		return "OP_RESERVED1"
	elif code == 138:
		# transaction is invalid unless occuring in an unexecuted OP_IF branch
		return "OP_RESERVED2"
	elif code == 176:
		# the word is ignored
		return "OP_NOP1"
	elif code == 177:
		# the word is ignored
		return "OP_CHECKLOCKTIMEVERIFY"
	elif code == 178:
		# the word is ignored
		return "OP_NOP3"
	elif code == 179:
		# the word is ignored
		return "OP_NOP4"
	elif code == 180:
		# the word is ignored
		return "OP_NOP5"
	elif code == 181:
		# the word is ignored
		return "OP_NOP6"
	elif code == 182:
		# the word is ignored
		return "OP_NOP7"
	elif code == 183:
		# the word is ignored
		return "OP_NOP8"
	elif code == 184:
		# the word is ignored
		return "OP_NOP9"
	elif code == 185:
		# the word is ignored
		return "OP_NOP10"

	# byte has no corresponding opcode
	return None

def pushdata_bin2opcode(code_bin):
	"""
	a bit like a variable length integer - input bytes are converted to a human
	readable string of the format OP_PUSHDATAx(y) where x is 0, 1, 2, 4 and y is
	the number of bytes to push onto the stack. also return y seperately, and
	the number of bytes that were used up (eg OP_PUSHDATA0 uses 1 byte,
	OP_PUSHDATA1 uses 2 bytes, etc).
	"""
	pushdata = bin2opcode(code_bin[: 1])

	if "OP_PUSHDATA" not in pushdata:
		return False

	pushdata_num = int(pushdata[-1])
	push_num_bytes_start = 0 if (pushdata_num == 0) else 1
	push_num_bytes_end = pushdata_num + 1
	# this is little endian (bitcoin.stackexchange.com/questions/2285)
	push_num_bytes = bin2int(little_endian(
		code_bin[push_num_bytes_start: push_num_bytes_end]
	))
	pushdata += "(%s)" % push_num_bytes
	return (pushdata, push_num_bytes, push_num_bytes_end)

def pushdata_opcode_split(opcode):
	"""
	split a human-readable pushdata string into the pushdata number and the
	number of bytes. for example, given OP_PUSHDATA1(90), return (1, 90).

	note that this function expects an opcode in the format OP_PUSHDATAx(y)
	where x is 0, 1, 2, 4 and y is an int. this function will not correctly
	split malformed opcodes like OP_PUSHDATA12(90)(80), so make sure you
	sanitize before passing data to this function.
	"""
	if "OP_PUSHDATA" not in opcode:
		raise ValueError(
			"unrecognized opcode (%s) input to function pushdata_opcode_split()"
			% opcode
		)
	matches = re.search(r"\((\d+)\)", opcode)
	try:
		push_num_bytes = int(matches.group(1))
	except AttributeError:
		raise ValueError(
			"opcode %s does not contain the number of bytes to push onto the"
			" stack"
			% opcode
		)
	try:
		opcode_num = int(opcode[11])
	except:
		raise ValueError(
			"opcode %s is not valid - it does not fit the pattern"
			" OP_PUSHDATAx(y). x is missing - it should be 0, 1, 2 or 4"
			% opcode
		)
	return (opcode_num, push_num_bytes)

def pushdata_opcode_join(opcode_num, push_num_bytes):
	"""
	join the opcode number and the corresponding number of bytes to push into a
	human-readable string.

	no sanitization done here.
	"""
	return "OP_PUSHDATA%s(%s)" % (opcode_num, push_num_bytes)

def pushdata_int2bin(intval):
	"""take an integer and convert it to its pushdata binary value"""

	# first convert to a human-readable string
	if intval <= 75:
		pushdata_num = 0
	elif intval <= 0xff:
		pushdata_num = 1
	elif intval <= 0xffff:
		pushdata_num = 2
	elif intval <= 0xffffffff:
		pushdata_num = 4

	human_opcode = "OP_PUSHDATA%s(%s)" % (pushdata_num, intval)

	# then convert the human-readable string to binary
	return pushdata_opcode2bin(human_opcode)

def pushdata_opcode2bin(opcode, explain = False):
	"""
	convert a human-readable opcode into a binary string. for example
	OP_PUSHDATA0(50) becomes (50) = 0x32
	OP_PUSHDATA1(90) becomes (76)(90) = 0x4c5a
	OP_PUSHDATA2(0xeeee) becomes (77)(0xeeee) = 0x4deeee
	OP_PUSHDATA4(0xbbbbbbbb) becomes (78)(0xbbbbbbbb) = 0x4ebbbbbbbb

	this function checks that the number of bytes to push lies within the
	specified opcode range.
	"""
	if "OP_PUSHDATA" not in opcode:
		return False

	(pushdata_num, push_num_bytes) = pushdata_opcode_split(opcode)

	# sanitize the opcode number
	if pushdata_num not in [0, 1, 2, 4]:
		raise ValueError("unrecognized opcode OP_PUSHDATA%s" % pushdata_num)

	# sanitize the number of bytes to push
	if pushdata_num == 0:
		min_range = 1
		max_range = 75
	elif pushdata_num == 1:
		min_range = 76 # encoding lower numbers would be inefficient
		max_range = 0xff
	elif pushdata_num == 2:
		min_range = 0x100 # encoding lower numbers would be inefficient
		max_range = 0xffff
	elif pushdata_num == 4:
		min_range = 0x10000 # encoding lower numbers would be inefficient
		max_range = 0xffffffff

	if not (min_range <= push_num_bytes <= max_range):
		if explain:
			return "Error: opcode OP_PUSHDATA%s cannot push %s bytes" \
			" - permissible range is %s to %s bytes" \
			% (pushdata_num, push_num_bytes, min_range, max_range)
		else:
			return False

	if pushdata_num == 0:
		return int2bin(push_num_bytes, 1)
	elif pushdata_num == 1:
		return "%s%s" % (int2bin(76, 1), int2bin(push_num_bytes, 1))
	elif pushdata_num == 2:
		# pushdata is little endian (bitcoin.stackexchange.com/questions/2285)
		return "%s%s" \
		% (int2bin(77, 1), little_endian(int2bin(push_num_bytes, 2)))
	elif pushdata_num == 4:
		# pushdata is little endian (bitcoin.stackexchange.com/questions/2285)
		return "%s%s" \
		% (int2bin(78, 1), little_endian(int2bin(push_num_bytes, 4)))

def opcode2bin(opcode, explain = False):
	"""
	convert an opcode into its corresponding byte(s). as per
	https://en.bitcoin.it/wiki/script
	"""
	if (
		(opcode == "OP_FALSE") or
		(opcode == "OP_0")
	):
		# an empty array of bytes is pushed onto the stack
		return hex2bin(int2hex(0))
	elif "OP_PUSHDATA" in opcode:
		# the next opcode bytes is data to be pushed onto the stack
		# this is the only opcode that may return more than one byte
		return pushdata_opcode2bin(opcode, explain)
	elif opcode == "OP_1NEGATE":
		# the number -1 is pushed onto the stack
		return hex2bin(int2hex(79))
	elif (
		(opcode == "OP_TRUE") or
		(opcode == "OP_1")
	):
		# the number 1 is pushed onto the stack
		return hex2bin(int2hex(81))
	elif opcode == "OP_2":
		# the number 2 is pushed onto the stack
		return hex2bin(int2hex(82))
	elif opcode == "OP_3":
		# the number 3 is pushed onto the stack
		return hex2bin(int2hex(83))
	elif opcode == "OP_4":
		# the number 4 is pushed onto the stack
		return hex2bin(int2hex(84))
	elif opcode == "OP_5":
		# the number 5 is pushed onto the stack
		return hex2bin(int2hex(85))
	elif opcode == "OP_6":
		# the number 6 is pushed onto the stack
		return hex2bin(int2hex(86))
	elif opcode == "OP_7":
		# the number 7 is pushed onto the stack
		return hex2bin(int2hex(87))
	elif opcode == "OP_8":
		# the number 8 is pushed onto the stack
		return hex2bin(int2hex(88))
	elif opcode == "OP_9":
		# the number 9 is pushed onto the stack
		return hex2bin(int2hex(89))
	elif opcode == "OP_10":
		# the number 10 is pushed onto the stack
		return hex2bin(int2hex(90))
	elif opcode == "OP_11":
		# the number 11 is pushed onto the stack
		return hex2bin(int2hex(91))
	elif opcode == "OP_12":
		# the number 12 is pushed onto the stack
		return hex2bin(int2hex(92))
	elif opcode == "OP_13":
		# the number 13 is pushed onto the stack
		return hex2bin(int2hex(93))
	elif opcode == "OP_14":
		# the number 14 is pushed onto the stack
		return hex2bin(int2hex(94))
	elif opcode == "OP_15":
		# the number 15 is pushed onto the stack
		return hex2bin(int2hex(95))
	elif opcode == "OP_16":
		# the number 16 is pushed onto the stack
		return hex2bin(int2hex(96))

	# flow control
	elif opcode == "OP_NOP":
		# does nothing
		return hex2bin(int2hex(97))
	elif opcode == "OP_IF":
		# if top stack value != 0, statements are executed. remove top stack
		# value
		return hex2bin(int2hex(99))
	elif opcode == "OP_NOTIF":
		# if top stack value == 0, statements are executed. remove top stack
		# value
		return hex2bin(int2hex(100))
	elif opcode == "OP_ELSE":
		# if the preceding OP was not executed then these statements are. else
		# don't
		return hex2bin(int2hex(103))
	elif opcode == "OP_ENDIF":
		# ends an if/else block
		return hex2bin(int2hex(104))
	elif opcode == "OP_VERIFY":
		# top stack value is \x00 or "": mark transaction as invalid and remove,
		# false: don't
		return hex2bin(int2hex(105))
	elif opcode == "OP_RETURN":
		# marks transaction as invalid
		return hex2bin(int2hex(106))
	# stack
	elif opcode == "OP_TOALTSTACK":
		# put the input onto the top of the alt stack. remove it from the main
		# stack
		return hex2bin(int2hex(107))
	elif opcode == "OP_FROMALTSTACK":
		# put the input onto the top of the main stack. remove it from the alt
		# stack
		return hex2bin(int2hex(108))
	elif opcode == "OP_IFDUP":
		# if the top stack value is not 0, duplicate it
		return hex2bin(int2hex(115))
	elif opcode == "OP_DEPTH":
		# puts the number of stack items onto the stack
		return hex2bin(int2hex(116))
	elif opcode == "OP_DROP":
		# removes the top stack item
		return hex2bin(int2hex(117))
	elif opcode == "OP_DUP":
		# duplicates the top stack item
		return hex2bin(int2hex(118))
	elif opcode == "OP_NIP":
		# removes the second-to-top stack item
		return hex2bin(int2hex(119))
	elif opcode == "OP_OVER":
		# copies the second-to-top stack item to the top
		return hex2bin(int2hex(120))
	elif opcode == "OP_PICK":
		# the item n back in the stack is copied to the top
		return hex2bin(int2hex(121))
	elif opcode == "OP_ROLL":
		# the item n back in the stack is moved to the top
		return hex2bin(int2hex(122))
	elif opcode == "OP_ROT":
		# the top three items on the stack are rotated to the left
		return hex2bin(int2hex(123))
	elif opcode == "OP_SWAP":
		# the top two items on the stack are swapped
		return hex2bin(int2hex(124))
	elif opcode == "OP_TUCK":
		# copy item at the top of the stack and insert before the second-to-top
		# item
		return hex2bin(int2hex(125))
	elif opcode == "OP_2DROP":
		# removes the top two stack items
		return hex2bin(int2hex(109))
	elif opcode == "OP_2DUP":
		# duplicates the top two stack items
		return hex2bin(int2hex(110))
	elif opcode == "OP_3DUP":
		# duplicates the top three stack items
		return hex2bin(int2hex(111))
	elif opcode == "OP_2OVER":
		# copies the pair of items two spaces back in the stack to the front
		return hex2bin(int2hex(112))
	elif opcode == "OP_2ROT":
		# the fifth and sixth items back are moved to the top of the stack
		return hex2bin(int2hex(113))
	elif opcode == "OP_2SWAP":
		# swaps the top two pairs of items
		return hex2bin(int2hex(114))

	# splice
	elif opcode == "OP_CAT":
		# concatenates two strings. disabled
		return hex2bin(int2hex(126))
	elif opcode == "OP_SUBSTR":
		# returns a section of a string. disabled
		return hex2bin(int2hex(127))
	elif opcode == "OP_LEFT":
		# keeps only characters left of the specified point in a string.
		# disabled
		return hex2bin(int2hex(128))
	elif opcode == "OP_RIGHT":
		# keeps only characters right of the specified point in a string.
		# disabled
		return hex2bin(int2hex(129))
	elif opcode == "OP_SIZE":
		# returns the length of the input string
		return hex2bin(int2hex(130))

	# bitwise logic
	elif opcode == "OP_INVERT":
		# flips all of the bits in the input. disabled
		return hex2bin(int2hex(131))
	elif opcode == "OP_AND":
		# boolean and between each bit in the inputs. disabled
		return hex2bin(int2hex(132))
	elif opcode == "OP_OR":
		# boolean or between each bit in the inputs. disabled
		return hex2bin(int2hex(133))
	elif opcode == "OP_XOR":
		# boolean exclusive or between each bit in the inputs. disabled
		return hex2bin(int2hex(134))
	elif opcode == "OP_EQUAL":
		# returns 1 if the inputs are exactly equal, 0 otherwise
		return hex2bin(int2hex(135))
	elif opcode == "OP_EQUALVERIFY":
		# same as OP_EQUAL, but runs OP_VERIFY afterward
		return hex2bin(int2hex(136))

	# arithmetic
	elif opcode == "OP_1ADD":
		# 1 is added to the input
		return hex2bin(int2hex(139))
	elif opcode == "OP_1SUB":
		# 1 is subtracted from the input
		return hex2bin(int2hex(140))
	elif opcode == "OP_2MUL":
		# the input is multiplied by 2. disabled
		return hex2bin(int2hex(141))
	elif opcode == "OP_2DIV":
		# the input is divided by 2. disabled
		return hex2bin(int2hex(142))
	elif opcode == "OP_NEGATE":
		# the sign of the input is flipped
		return hex2bin(int2hex(143))
	elif opcode == "OP_ABS":
		# the input is made positive
		return hex2bin(int2hex(144))
	elif opcode == "OP_NOT":
		# if the input is 0 or 1, it is flipped. Otherwise the output will be 0
		return hex2bin(int2hex(145))
	elif opcode == "OP_0NOTEQUAL":
		# returns 0 if the input is 0. 1 otherwise
		return hex2bin(int2hex(146))
	elif opcode == "OP_ADD":
		# a is added to b
		return hex2bin(int2hex(147))
	elif opcode == "OP_SUB":
		# b is subtracted from a
		return hex2bin(int2hex(148))
	elif opcode == "OP_MUL":
		# a is multiplied by b. disabled
		return hex2bin(int2hex(149))
	elif opcode == "OP_DIV":
		# a is divided by b. disabled
		return hex2bin(int2hex(150))
	elif opcode == "OP_MOD":
		# returns the remainder after dividing a by b. disabled
		return hex2bin(int2hex(151))
	elif opcode == "OP_LSHIFT":
		# shifts a left b bits, preserving sign. disabled
		return hex2bin(int2hex(152))
	elif opcode == "OP_RSHIFT":
		# shifts a right b bits, preserving sign. disabled
		return hex2bin(int2hex(153))
	elif opcode == "OP_BOOLAND":
		# if both a and b are not 0, the output is 1. Otherwise 0
		return hex2bin(int2hex(154))
	elif opcode == "OP_BOOLOR":
		# if a or b is not 0, the output is 1. Otherwise 0
		return hex2bin(int2hex(155))
	elif opcode == "OP_NUMEQUAL":
		# returns 1 if the numbers are equal, 0 otherwise
		return hex2bin(int2hex(156))
	elif opcode == "OP_NUMEQUALVERIFY":
		# same as OP_NUMEQUAL, but runs OP_VERIFY afterward
		return hex2bin(int2hex(157))
	elif opcode == "OP_NUMNOTEQUAL":
		# returns 1 if the numbers are not equal, 0 otherwise
		return hex2bin(int2hex(158))
	elif opcode == "OP_LESSTHAN":
		# returns 1 if a is less than b, 0 otherwise
		return hex2bin(int2hex(159))
	elif opcode == "OP_GREATERTHAN":
		# returns 1 if a is greater than b, 0 otherwise
		return hex2bin(int2hex(160))
	elif opcode == "OP_LESSTHANOREQUAL":
		# returns 1 if a is less than or equal to b, 0 otherwise
		return hex2bin(int2hex(161))
	elif opcode == "OP_GREATERTHANOREQUAL":
		# returns 1 if a is greater than or equal to b, 0 otherwise
		return hex2bin(int2hex(162))
	elif opcode == "OP_MIN":
		# returns the smaller of a and b
		return hex2bin(int2hex(163))
	elif opcode == "OP_MAX":
		# returns the larger of a and b
		return hex2bin(int2hex(164))
	elif opcode == "OP_WITHIN":
		# returns 1 if x is within the specified range (left-inclusive), else 0
		return hex2bin(int2hex(165))

	# crypto
	elif opcode == "OP_RIPEMD160":
		# the input is hashed using RIPEMD-160
		return hex2bin(int2hex(166))
	elif opcode == "OP_SHA1":
		# the input is hashed using SHA-1
		return hex2bin(int2hex(167))
	elif opcode == "OP_SHA256":
		# the input is hashed using SHA-256
		return hex2bin(int2hex(168))
	elif opcode == "OP_HASH160":
		# the input is hashed twice: first with SHA-256 and then with RIPEMD-160
		return hex2bin(int2hex(169))
	elif opcode == "OP_HASH256":
		# the input is hashed two times with SHA-256
		return hex2bin(int2hex(170))
	elif opcode == "OP_CODESEPARATOR":
		# only match signatures after the latest OP_CODESEPARATOR
		return hex2bin(int2hex(171))
	elif opcode == "OP_CHECKSIG":
		# hash all transaction outputs, inputs, and script. return 1 if valid
		return hex2bin(int2hex(172))
	elif opcode == "OP_CHECKSIGVERIFY":
		# same as OP_CHECKSIG, but OP_VERIFY is executed afterward
		return hex2bin(int2hex(173))
	elif opcode == "OP_CHECKMULTISIG":
		# execute OP_CHECKSIG for each signature and public key pair
		return hex2bin(int2hex(174))
	elif opcode == "OP_CHECKMULTISIGVERIFY":
		# same as OP_CHECKMULTISIG, but OP_VERIFY is executed afterward
		return hex2bin(int2hex(175))

	# pseudo-words
	elif opcode == "OP_PUBKEYHASH":
		# represents a public key hashed with OP_HASH160
		return hex2bin(int2hex(253))
	elif opcode == "OP_PUBKEY":
		# represents a public key compatible with OP_CHECKSIG
		return hex2bin(int2hex(254))
	elif opcode == "OP_INVALIDOPCODE":
		# any opcode that is not yet assigned
		return hex2bin(int2hex(255))

	# reserved words
	elif opcode == "OP_RESERVED":
		# transaction is invalid unless occuring in an unexecuted OP_IF branch
		return hex2bin(int2hex(80))
	elif opcode == "OP_VER":
		# transaction is invalid unless occuring in an unexecuted OP_IF branch
		return hex2bin(int2hex(98))
	elif opcode == "OP_VERIF":
		# transaction is invalid even when occuring in an unexecuted OP_IF
		# branch
		return hex2bin(int2hex(101))
	elif opcode == "OP_VERNOTIF":
		# transaction is invalid even when occuring in an unexecuted OP_IF
		# branch
		return hex2bin(int2hex(102))
	elif opcode == "OP_RESERVED1":
		# transaction is invalid unless occuring in an unexecuted OP_IF branch
		return hex2bin(int2hex(137))
	elif opcode == "OP_RESERVED2":
		# transaction is invalid unless occuring in an unexecuted OP_IF branch
		return hex2bin(int2hex(138))
	elif opcode == "OP_NOP1":
		# the word is ignored
		return hex2bin(int2hex(176))
	elif opcode in ["OP_NOP2", "OP_CHECKLOCKTIMEVERIFY"]:
		# bip65
		return hex2bin(int2hex(177))
	elif opcode == "OP_NOP3":
		# the word is ignored
		return hex2bin(int2hex(178))
	elif opcode == "OP_NOP4":
		# the word is ignored
		return hex2bin(int2hex(179))
	elif opcode == "OP_NOP5":
		# the word is ignored
		return hex2bin(int2hex(180))
	elif opcode == "OP_NOP6":
		# the word is ignored
		return hex2bin(int2hex(181))
	elif opcode == "OP_NOP7":
		# the word is ignored
		return hex2bin(int2hex(182))
	elif opcode == "OP_NOP8":
		# the word is ignored
		return hex2bin(int2hex(183))
	elif opcode == "OP_NOP9":
		# the word is ignored
		return hex2bin(int2hex(184))
	elif opcode == "OP_NOP10":
		# the word is ignored
		return hex2bin(int2hex(185))
	else:
		if explain:
			return "opcode %s has no corresponding byte" % opcode
		else:
			return False

def calculate_merkle_root(merkle_tree_elements):
	"""recursively calculate the merkle root from the list of leaves"""

	if not merkle_tree_elements:
		raise ValueError(
			"No arguments passed to function calculate_merkle_root()"
		)
	if len(merkle_tree_elements) == 1: # just return the input
		return merkle_tree_elements[0]

	nodes = ["placeholder"] # gets overwritten
	level = 0

	# convert all leaves from little endian back to normal
	nodes[level] = [little_endian(leaf) for leaf in merkle_tree_elements]

	while True:
		num = len(nodes[level])
		nodes.append("placeholder") # initialize next level
		for (i, leaf) in enumerate(nodes[level]):
			if is_odd(i):
				continue
			dhash = leaf
			if (i + 1) == num: # we are on the last index
				concat = dhash + dhash
			else: # not on the last index
				dhash_next = nodes[level][i + 1]
				concat = dhash + dhash_next
			node_val = sha256(sha256(concat))
			if not i:
				nodes[level + 1] = [node_val]
			else:
				nodes[level + 1].append(node_val)

		if len(nodes[level + 1]) == 1:
			# this is the root - output in little endian
			return little_endian(nodes[level + 1][0])

		level = level + 1

def mine(block):
	"""
	given a block header, find a nonce value that results in the block hash
	being less than the target. using this function is an extremely inefficient
	method of mining bitcoins, but it does correctly demonstrate the mining code
	"""
	if isinstance(block, dict):
		partial_block_header_bin = block_dict2bin(block)[0:76]
		block_dict = block
	else:
		partial_block_header_bin = block[0:76]
		block_dict = block_bin2dict(block, ["timestamp"])

	nonce = 0
	while True:
		# increment the nonce until we find a value which gives a valid hash
		while nonce <= 0xffffffff: # max nonce = 4 bytes
			print "try nonce %s" % nonce
			header = partial_block_header_bin + int2bin(nonce, 4)
			if valid_block_hash(header):
				print "found nonce %s" % nonce
				return [nonce, block_dict["timestamp"]]
			nonce += 1
		# if none of the nonce values work, then incremement the timestamp and
		# try again
		block_dict["timestamp"] += 1

def mining_reward(block_height):
	"""
	determine the coinbase funds reward (in satoshis) using only the block
	height (genesis block has height 0).

	other names for "coinbase funds" are "block creation fee" and
	"mining reward"
	"""
	# TODO - handle other currencies
	return (50 * satoshis_per_btc) >> (block_height / 210000)

def calc_new_bits(old_bits, old_bits_time, new_bits_time):
	"""
	calculate the new target. we want new blocks to be mined on average every 10
	minutes.

	http://bitcoin.stackexchange.com/a/2926/2116
	"""
	two_weeks = 14 * 24 * 60 * 60 # in seconds
	half_a_week = 3.5 * 24 * 60 * 60 # in seconds
	eight_weeks = 4 * two_weeks
	time_diff = new_bits_time - old_bits_time

	# if the difference is greater than 8 weeks, set it to 8 weeks; this
	# prevents the difficulty decreasing by more than a factor of 4
	if time_diff > eight_weeks:
		time_diff = eight_weeks

	# if the difference is less than half a week, set it to half a week; this
	# prevents the difficulty increasing by more than a factor of 4
	elif time_diff < half_a_week:
		time_diff = half_a_week

	# convert the bits to a target then convert back to bits
	new_target = bits2target_int(old_bits) * time_diff / two_weeks
	max_target = (2 ** (256 - 32)) - 1
	if new_target > max_target:
		new_target = max_target

	return target_int2bits(new_target)

def connect_to_rpc():
	global rpc
	# always works, even if bitcoind is not installed!
	rpc = AuthServiceProxy(rpc_connection_string)

def get_info():
	"""get info such as the latest block and the client version"""
	return do_rpc("getinfo", None)

def get_transaction(tx_hash, result_format):
	"""get the transaction"""
	json_result = True if result_format == "json" else False
	result = do_rpc("getrawtransaction", tx_hash, json_result)
	if result_format in ["json", "hex"]:
		return result
	elif result_format == "bytes":
		return hex2bin(result)
	else:
		raise ValueError("unknown result format %s" % result_format)

def get_block(block_id, result_format):
	"""
	use rpc to get the block - bitcoind does all the hard work :)
	if block_id is an integer then get the block by height
	if block_id is a string then get the block by hash
	result_format can be bytes, hex, json in the format provided by bitcoind.
	note that bitcoind's json output is not compatible with the standard block
	dict format that this file creates, however it is mainly useful because it
	contains the block height.
	"""
	# first convert the block height to block hash if necessary
	if isinstance(block_id, (int, long)):
		block_hash = do_rpc("getblockhash", block_id)
	else:
		block_hash = block_id

	# if hash is bin then convert to hex
	if len(block_hash) == 32:
		block_hash = bin2hex(block_hash)

	json_result = True if result_format == "json" else False
	result = do_rpc("getblock", block_hash, json_result)
	if result_format in ["json", "hex"]:
		return result
	elif result_format == "bytes":
		return hex2bin(result)
	else:
		raise ValueError("unknown result format %s" % result_format)

ten_mins_in_seconds = 10 * 60
genesis_datetime = 1231006505
def block_date2heights(req_datetime):
	"""
	convert the given block date into an array of the following format: {
		block height before: block time before
		block height after: block time after
	}
	if req_datetime falls exactly on a block timestamp then set both array
	elements to the same value
	"""
	# if the specified datetime is before the first block then return the first
	# block
	if (req_datetime <= genesis_datetime):
		return {0: genesis_datetime, 1: get_block(1, "json")["time"]}

	latest_block_height = get_info()["blocks"]
	latest_datetime = get_block(latest_block_height, "json")["time"]

	# if the specified datetime is after the last block then return the latest
	# block
	if (req_datetime >= latest_datetime):
		return {
			(latest_block_height - 1): \
			get_block(latest_datetime - 1, "json")["time"],
			latest_block_height: latest_datetime
		}

	# if the specified time is somewhere in the middle then find the correct
	# block through a series of educated guesses (we know the blocks are 10
	# minutes apart on average)
	height_time_data = {0: genesis_datetime} # init
	def either_side():
		"""
		return data if we have consecutive blocks on both sides of the required
		datetime, else None
		"""
		prev_height = 0 # init
		prev_datetime = genesis_datetime
		prev_is_before = True # init
		for height in sorted(height_time_data.keys()):
			datetime = height_time_data[height]
			# consecutive with one date before and one after
			if (
				(height == prev_height + 1) and
				(datetime > req_datetime) and
				prev_is_before
			):
				return {prev_height: prev_datetime, height: datetime}

			prev_height = height
			prev_datetime = datetime
			prev_is_before = True if (datetime < req_datetime) else False

		return None

	block_height = 0 # init
	prev_datetime = genesis_datetime
	while True:
		# extrapolate the block height using the time difference and knowing
		# that each block takes 10 minutes on average to mine
		time_diff = req_datetime - prev_datetime
		approx_height_diff = time_diff / float(ten_mins_in_seconds)

		if 0 < approx_height_diff < 1:
			approx_height_diff = 1
		elif -1 < approx_height_diff < 0:
			approx_height_diff = -1

		approx_height_diff = int(approx_height_diff)
		block_height = block_height + approx_height_diff

		# if this would lead us beyond the genesis block then use the ratio to
		# interpolate the desired block height
		if block_height < 0:
			block_height = int(
				prev_block_height * (req_datetime - genesis_datetime) / \
				float(prev_datetime - genesis_datetime)
			)
			if block_height == prev_block_height:
				block_height = prev_block_height - 1
			if block_height < 0:
				block_height = 0
		elif block_height > latest_block_height:
			block_height = int(
				prev_block_height + (
					(latest_block_height - prev_block_height) * \
					(req_datetime - prev_block_height) / \
					float(latest_datetime - prev_datetime)
				)
			)
			if block_height == prev_block_height:
				block_height = prev_block_height + 1
			if block_height > latest_block_height:
				block_height = latest_block_height

		datetime = get_block(block_height, "json")["time"]

		# prevent infinitely bouncing between two points, by walking one block
		# in the right direction
		if (
			(block_height in height_time_data) and
			(prev_block_height in height_time_data)
		):
			if datetime < req_datetime:
				block_height = block_height + 1
			else:
				block_height = block_height - 1

			datetime = get_block(block_height, "json")["time"]

		height_time_data[block_height] = datetime

		if datetime == req_datetime:
			return {
				block_height: datetime,
				block_height + 1: get_block(block_height + 1, "json")["time"]
			}

		temp_data = either_side()
		if temp_data is not None:
			return temp_data

		prev_block_height = block_height
		prev_datetime = datetime

rpc_error_reasons = [
	"- the rpc connection details (username, password, host, port) may be"
	" incorrect",
	"- the bitcoind client may still be starting up",
	"- bitcoind may not be installed or not running",
	"- bitcoind may be out of date"
]
rpc_error_str = "failed to connect to bitcoind using rpc. possible reasons:\n" \
"%s\n\nlow level rpc error: %s"
def do_rpc(command, parameter, json_result = True):
	"""
	perform the rpc, catch errors and take a guess at what may have gone wrong
	"""
	try:
		if command == "getinfo":
			result = rpc.getinfo()
		elif command == "getblockhash":
			result = rpc.getblockhash(parameter)
		elif command == "getblock":
			result = rpc.getblock(parameter, json_result)
		elif command == "getrawtransaction":
			result = rpc.getrawtransaction(parameter, 1 if json_result else 0)

	except ValueError as e:
		# the rpc client throws this type of error when using the wrong port,
		# wrong username, wrong password, etc. note: no error code is available
		rpc_error_reasons[0] = "%s (most likely)" % rpc_error_reasons[0]
		raise IOError(rpc_error_str % ("\n".join(rpc_error_reasons), e.message))

	except JSONRPCException as e:
		# the rpc client throws this error when bitcoind is not ready to accept
		# queries or when we have called a non-existent bitcoind method
		if e.code == -32601:
			rpc_error_reasons[3] = "%s (most likely)" % rpc_error_reasons[3]
		else:
			rpc_error_reasons[1] = "%s (most likely)" % rpc_error_reasons[1]
		raise IOError(rpc_error_str % ("\n".join(rpc_error_reasons), e.message))

	except Exception as e:
		if e.errno == 111:
			# bitcoind is not available
			rpc_error_reasons[2] = "%s (most likely)" % rpc_error_reasons[2]
		raise IOError(rpc_error_str % ("\n".join(rpc_error_reasons), e.message))

	return result

def bitcoind_version2human_str(version, simplify = True):
	"convert bitcoind's version number to a human readable string"

	# add leading zeros to make it 8 chars long
	version_str = "%08d" % version

	if simplify:
 		# remove groups of "00" from the right hand side
		version_str = version_str.rstrip("00")

	# put a dot every 2 characters, and strip zeros between the dots
	return ".".join(
		str(int(version_str[i: i + 2])) for i in range(0, len(version_str), 2)
	)

def pubkey2address(pubkey):
	"""
	take the public key (bytes) and output a standard bitcoin address (ascii
	string), following
	https://en.bitcoin.it/wiki/Technical_background_of_Bitcoin_addresses
	pubkeys can be various lengths. most are 65 bytes, but some are 33 bytes,
	eg tx 94af4607627535f9b2968bd1fbbf67be101971d682023d6a3b64d8caeb448870 which
	spends 0.01337 btc lol
	"""
	return hash1602address(ripemd160(sha256(pubkey)), "pub_key_hash")

def address2hash160(address):
	"""
	from https://github.com/gavinandresen/bitcointools/blob/master/base58.py
	"""
	bytes = base58decode(address)
	return bytes[1: 21]

def hash1602address(hash160, format_type):
	"""
	convert the hash160 output (bytes) to the bitcoin address (ascii string)
	https://en.bitcoin.it/wiki/Technical_background_of_Bitcoin_addresses
	"""
	temp = "%s%s" % (chr(version_symbol[format_type]["magic"]), hash160)

	# leading zeros are lost when converting to decimal, so count them here so
	# we can replace them at the end
	num_leading_zeros = len(re.match("^\x00*", temp).group(0))
	replace_leading_zeros = "1" * num_leading_zeros

	checksum = sha256(sha256(temp))[: 4] # checksum is the first 4 bytes
	hex_address = bin2hex("%s%s" % (temp, checksum))
	decimal_address = int(hex_address, 16)
	return "%s%s" % (replace_leading_zeros, base58encode(decimal_address))

def encode_variable_length_int(value):
	"""encode a value as a variable length integer"""
	if value < 253: # encode as a single byte
		bytes = int2bin(value)
	elif value < 0xffff: # encode as 1 format byte and 2 value bytes
		bytes = "%s%s" % (int2bin(253), little_endian(int2bin(value, 2)))
	elif value < 0xffffffff: # encode as 1 format byte and 4 value bytes
		bytes = "%s%s" % (int2bin(254), little_endian(int2bin(value, 4)))
	elif value < 0xffffffffffffffff: # encode as 1 format byte and 8 value bytes
		bytes = "%s%s" % (int2bin(255), little_endian(int2bin(value, 8)))
	else:
		raise OverflowError(
			"value %s is too big to be encoded as a variable length integer"
			% value
		)
	return bytes

def decode_variable_length_int(input_bytes):
	"""extract the value of a variable length integer"""
	bytes_in = 0
	first_byte = bin2int(input_bytes[: 1]) # 1 byte binary to decimal int
	bytes = input_bytes[1:] # don't need the first byte anymore
	bytes_in += 1
	if first_byte < 253:
		value = first_byte # use the byte literally
	elif first_byte == 253:
		# read the next two bytes as a 16-bit number
		value = bin2int(little_endian(bytes[: 2]))
		bytes_in += 2
	elif first_byte == 254:
		# read the next four bytes as a 32-bit number
		value = bin2int(little_endian(bytes[: 4]))
		bytes_in += 4
	elif first_byte == 255:
		# read the next eight bytes as a 64-bit number
		value = bin2int(little_endian(bytes[: 8]))
		bytes_in += 8
	else:
		raise OverflowError(
			"value %s is too big to be decoded as a variable length integer"
			% bin2hex(input_bytes)
		)
	return (value, bytes_in)

"""
def maybe_update_aux_blockchain_data(parsed_block, aux_blockchain_data):
	" ""
	we save the blockfile number and position to the aux_blockchain_data dict
	every aux_blockchain_data_backup_freq blocks (with an offset of -1) - this
	allows us to skip ahead when the user specifies a block range that does not
	start from block 0.

	if this block height has not been saved before, or if it has been saved but
	has now changed, then update the dict ready to be backed up to disk after
	validation. this doesn't happen often so it will not slow us down.

	it is important to leave the disk-save until after validation - otherwise an
	invalid block height will be written to disk as if it were valid.

	aux_blockchain_data is in the format:
	{block-height: {block-hash0: {
		"filenum": 0, "start_pos": 999, "size": 285, "timestamp": x, "bits": x,
		"is_orphan": True
	}}}
	"timestamp" and "bits" are only defined every 2016 blocks or 2016 - 1, but
	"filenum", "start_pos", "size" and "is_orphan" are always defined.
	" ""
	data_updated = False # init
	block_height = parsed_block["block_height"]

	# check if this is 1 before one of the aux blockchain backup milestones
	if (
		(((block_height + 1) % aux_blockchain_data_backup_freq) == 0) or
		(block_height == 0)
	):
		freq_hit = True
	else:
		freq_hit = False

	# check if we are at the 2-week block height, or 1 block before
	if (block_height % 2016) in [0, 2015]:
		two_week_hit = True
	else:
		two_week_hit = False

	# if neither case is applicable then there is nothing to update
	if (
		(not freq_hit) and
		(not two_week_hit)
	):
		return (data_updated, aux_blockchain_data)

	block_hash = parsed_block["block_hash"]

	# from here on this is a block to backup to disk. but if it is already on	
	# disk then there is nothing to do here
	if block_height not in aux_blockchain_data:
		aux_blockchain_data[block_height] = {} # init
		data_updated = True

	if block_hash not in aux_blockchain_data[block_height]:
		aux_blockchain_data[block_height][block_hash] = {} # init
		data_updated = True

	# always backup the file number
	if (
		("filenum" not in aux_blockchain_data[block_height][block_hash]) or
		aux_blockchain_data[block_height][block_hash]["filenum"] != \
		parsed_block["block_filenum"]
	):
		aux_blockchain_data[block_height][block_hash]["filenum"] = \
		parsed_block["block_filenum"]
		data_updated = True

	# always backup the start position of the block in the file
	if (
		("start_pos" not in aux_blockchain_data[block_height][block_hash]) or
		aux_blockchain_data[block_height][block_hash]["start_pos"] != \
		parsed_block["block_pos"]
	):
		aux_blockchain_data[block_height][block_hash]["start_pos"] = \
		parsed_block["block_pos"]
		data_updated = True

	# always backup the block size
	if (
		("size" not in aux_blockchain_data[block_height][block_hash]) or
		aux_blockchain_data[block_height][block_hash]["size"] != \
		parsed_block["size"]
	):
		aux_blockchain_data[block_height][block_hash]["size"] = \
		parsed_block["size"]
		data_updated = True

	# only backup the block timestamp if this is a 2-week hit
	if (
		("timestamp" not in aux_blockchain_data[block_height][block_hash]) or
		aux_blockchain_data[block_height][block_hash]["timestamp"] != \
		parsed_block["timestamp"]
	):
		data_updated = True
		if two_week_hit:
			aux_blockchain_data[block_height][block_hash]["timestamp"] = \
			parsed_block["timestamp"]
		else:
			aux_blockchain_data[block_height][block_hash]["timestamp"] = None

	# only backup the block bits (ie difficulty) if this is a 2-week hit
	if (
		("bits" not in aux_blockchain_data[block_height][block_hash]) or
		aux_blockchain_data[block_height][block_hash]["bits"] != \
		parsed_block["bits"]
	):
		data_updated = True
		if two_week_hit:
			aux_blockchain_data[block_height][block_hash]["bits"] = \
			parsed_block["bits"]
		else:
			aux_blockchain_data[block_height][block_hash]["bits"] = None

	# backup the orphan status but only if it previously did not exist in the
	# aux_blockchain_data dict, or has changed from non-orphan to orphan in the
	# aux_blockchain_data dict. the orphan status this may not exist in the
	# parsed block yet, so be careful
	if "is_orphan" not in aux_blockchain_data[block_height][block_hash]:
		aux_blockchain_data[block_height][block_hash]["is_orphan"] = None # init
		data_updated = True # there is something to change
	try:
		old_orphan_status = \
		aux_blockchain_data[block_height][block_hash]["is_orphan"]
	except:
		old_orphan_status = None
	try:
		new_orphan_status = parsed_block["orphan_status"]
	except:
		new_orphan_status = None
	if (
		(old_orphan_status is None) and
		(old_orphan_status != new_orphan_status)
	):
		data_updated = True # there is something to change
		aux_blockchain_data[block_height][block_hash]["is_orphan"] = \
		new_orphan_status

	return (data_updated, aux_blockchain_data)

def manage_orphans(
	filtered_blocks, hash_table, parsed_block, mult
	#filtered_blocks, hash_table, parsed_block, aux_blockchain_data, mult
):
	"" "
	if the hash table grows to mult * coinbase_maturity size then:
	- detect any orphans in the hash table
	- mark off these orphans in the blockchain (filtered_blocks)
	- mark off all certified non-orphans in the blockchain
	- mark off any orphans in the aux_blockchain_data dict
	- truncate the hash table back to coinbase_maturity size again
	tune mult according to whatever is faster.
	" ""
	if len(hash_table) > int(mult * coinbase_maturity):
		# the only way to know if it is an orphan block is to wait
		# coinbase_maturity blocks after a split in the chain.
		orphans = detect_orphans(
			hash_table, parsed_block["block_hash"], coinbase_maturity
		)
		# mark off any non-orphans
		filtered_blocks = mark_non_orphans(
			filtered_blocks, orphans, parsed_block["block_height"]
		)
		# mark off any orphans in the filtered blocks and aux data
		if orphans:
			filtered_blocks = mark_orphans(filtered_blocks, orphans)
			aux_blockchain_data = mark_aux_blockchain_data_orphans(
				aux_blockchain_data, orphans
			)

		# truncate the hash table to coinbase_maturity hashes length so as not
		# to use up too much ram
		hash_table = truncate_hash_table(hash_table, coinbase_maturity)

	return (filtered_blocks, hash_table, aux_blockchain_data)
"""

def save_new_orphans(hash_table, latest_block_hash):
	"""
	if there are any new orphans in the hash table then save them to disk and
	update the saved_known_orphans global var
	hash_table format: {block hash: [block height, previous hash], ...}
	saved_known_orphans format: {block height: [block hash1, hash2, ...], ...}
	"""
	# get orphans in a list of the format [(height, hash), ...]
	orphans_list = detect_orphans(hash_table, latest_block_hash, 0)
	if orphans_list is None:
		return

	# if we get here then there are orphans. now detect if they have been saved
	# already or not
	new_orphans = copy.deepcopy(saved_known_orphans) # init
	any_new = False
	for (block_height, block_hash) in orphans_list:
		if block_height not in new_orphans:
			new_orphans[block_height] = [block_hash]
			any_new = True
		elif block_hash not in new_orphans[block_height]:
			new_orphans[block_height].append(block_hash)
			any_new = True

	if not any_new:
		return

	save_known_orphans(new_orphans)

def detect_orphans(hash_table, latest_block_hash, threshold_confirmations):
	"""
	look back through the hash_table for orphans. if any are found then	return
	them in a list of the format [(height, hash), ...]

	the threshold_confirmations argument specifies the number of confirmations
	to wait before marking a hash as an orphan.
	"""
	# remember, hash_table is in the format {hash: [block_height, prev_hash]}
	inverted_hash_table = {v[0]: k for (k, v) in hash_table.items()}
	if len(inverted_hash_table) == len(hash_table):
		# there are no orphans
		return None

	# if we get here then some orphan blocks exist. now find their hashes...
	orphans = copy.deepcopy(hash_table)
	top_block_height = hash_table[latest_block_height][0]
	previous_hash = latest_block_hash # needed to start the loop correctly
	while previous_hash in hash_table:
		this_hash = previous_hash
		this_block_height = hash_table[this_hash][0]
		if (
			(threshold_confirmations > 0) and
			((top_block_height - this_block_height) >= threshold_confirmations)
		):
			del orphans[this_hash]
		previous_hash = hash_table[this_hash][1]

	# anything not deleted from the orphans dict is now an orphan
	return [(hash_table[block_hash][0], block_hash) for block_hash in orphans]

def mark_non_orphans(filtered_blocks, orphans, block_height):
	"""
	mark off any non-orphans. these are identified by looping through all blocks
	that are over coinbase_maturity from the current block height and marking
	any blocks that are not in the orphans dict	
	"""
	threshold = block_height - coinbase_maturity
	for block_hash in filtered_blocks:

		# if the block is too new to know for sure then ignore it for now
		if filtered_blocks[block_hash]["block_height"] > threshold:
			continue

		# if the block is a known orphan then skip it
		if (
			orphans and
			(block_hash in orphans)
		):
			continue
	
		filtered_blocks[block_hash]["is_orphan"] = False

	return filtered_blocks

def mark_orphans(filtered_blocks, orphans, blockfile):
	"""mark the specified blocks as orphans"""
	for orphan_hash in orphans:
		if orphan_hash in filtered_blocks:
			filtered_blocks[orphan_hash]["is_orphan"] = True

			# mark unspent txs as orphans
			parsed_block = filtered_blocks[orphan_hash]
			save_tx_metadata(parsed_block)

	# not really necessary since dicts are immutable. still, it makes the code
	# more readable
	return filtered_blocks

def mark_aux_blockchain_data_orphans(aux_blockchain_data, orphans):
	"""
	use the orphans list to mark off unnecessary difficulty data.
	aux_blockchain_data is in the format:
	{block-height: {block-hash0: {
		"filenum": 0, "start_pos": 999, "size": 285, "timestamp": x, "bits": x,
		"is_orphan": True
	}}}
	"timestamp" and "bits" are only defined every 2016 blocks or 2016 - 1, but
	"filenum", "start_pos", "size" and "is_orphan" are always defined.
	"""
	for (block_height, d) in aux_blockchain_data.items():
		for block_hash in d:
			if block_hash not in orphans:
				continue
			aux_blockchain_data[block_height][block_hash]["is_orphan"] = True

	# not really necessary since dicts are immutable. still, it makes the code
	# more readable
	return aux_blockchain_data

def truncate_hash_table(hash_table, new_len):
	"""
	take a dict of the form {block hash: [block_num, prev block hash]} and leave
	new_len upper blocks
	"""
	# quick check - maybe the criteria is already satisfied...
	if len(hash_table) <= new_len:
		return hash_table

	local_hash_table = copy.deepcopy(hash_table)
	# remember, hash_table is in the format {hash: [block_height, prev_hash]}
	reversed_hash_table = {
		hash_data[0]: hashstring for (hashstring, hash_data) in \
		local_hash_table.items()
	}
	# only keep [new_len] on the end
	to_remove = sorted(reversed_hash_table)[: -new_len]

	for block_num in to_remove:
		block_hash = reversed_hash_table[block_num]
		del local_hash_table[block_hash]

	return local_hash_table

def filter_orphans(blocks, options):
	"""loop through the blocks and filter according to the options"""

	# no need to do anything if the user is optionally allowing orphans in the
	# result set
	if options.ORPHAN_OPTIONS == "ALLOW":
		return blocks

	# eliminate orphan blocks if requested
	if options.ORPHAN_OPTIONS == "NONE":
		# first remove the blocks already marked as orphans - this covers all
		# orphans up to coinbase_maturity blocks from the top block
		blocks = {
			block_hash: blocks[block_hash] for block_hash in blocks if \
			not blocks[block_hash]["is_orphan"]
		}

		# TODO - validate the whole blockchain to see if this ever happens
		# if not then remove these next two checks for orphans

		# keep only blocks with correct merkle root values
		blocks = {
			block_hash: blocks[block_hash] for block_hash in blocks if \
			valid_merkle_tree(blocks[block_hash])
		}

		# keep only blocks with correct nonce values
		blocks = {
			block_hash: blocks[block_hash] for block_hash in blocks if \
			valid_block_hash(blocks[block_hash])
		}

		return blocks

	# keep only orphan blocks
	if options.ORPHAN_OPTIONS == "ONLY":
		# extract the blocks already marked as non-orphans - this covers all
		# blocks up to coinbase_maturity blocks from the top block
		blocks0 = {
			block_hash: blocks[block_hash] for block_hash in blocks if \
			blocks[block_hash]["is_orphan"]
		}

		# TODO - validate the whole blockchain to see if this ever happens
		# if not then remove these next two checks for orphans

		# extract the blocks with incorrect merkle root values
		blocks1 = {
			block_hash: blocks[block_hash] for block_hash in blocks if \
			valid_merkle_tree(blocks[block_hash])
		}

		# extract the blocks with incorrect nonce values
		blocks2 = {
			block_hash: blocks[block_hash] for block_hash in blocks if \
			not valid_block_hash(blocks[block_hash])
		}

		return merge_blocks_ascending(blocks0, blocks1, blocks2)

	# sanitization ensures we never get to this line

def explode_addresses(original_addresses):
	"""
	convert addresses into as many different formats as possible. return as a
	list
	"""
	addresses = []
	for address in original_addresses:
		address_type = get_address_type(address)

		# script hash eg 3EktnHQD7RiAE6uzMj2ZifT9YgRrkSgzQX
		if "script hash" in address_type:
			addresses.append(address)
			#if is_base58(address): TODO
			#	addresses.append(base582bin(address))

		# pubkey hash eg 17VZNX1SN5NtKa8UQFxwQbFeFc3iqRYhem
		elif "pubkey hash" in address_type:
			addresses.append(address)
			#if is_base58(address): TODO
			#	addresses.append(base582bin(address))

		# public key is a 130 character hex string
		elif address_type == "public key":

			# raw public keys
			addresses.append(hex2bin(address))

			# public key hashes (condensed from public keys)
			addresses.append(pubkey2address(hex2bin(address)))

	return addresses

def get_formatted_data(options, data):
	"""
	format the input data into a string as specified by the options. sort
	ascending
	"""
	if data is None:
		return

	# the user must just be validating the blockchain
	if options.OUTPUT_TYPE is None:
		return

	if options.OUTPUT_TYPE == "BLOCKS":
		if (
			("JSON" in options.FORMAT) or
			("XML" in options.FORMAT)
		):
			# transform block indexes into the format blockheight-orphannum
			parsed_blocks = {}
			prev_block_height = 0 # init
			for block_hash in data:
				# remove any binary bytes when diaplaying json or xml
				parsed_block = human_readable_block(data[block_hash], options)
				block_height = parsed_block["block_height"]
				if parsed_block["is_orphan"]:
					# if this is not the first displayed orphan for this block
					if block_height == prev_block_height:
						orphan_num += 1
					else:
						orphan_num = 0 # init
					orphan_descr = "-orphan%s" % orphan_num
				else:
					orphan_descr = ""

				# sorting only works if we use strings, not ints
				parsed_blocks["%s%s" % (block_height, orphan_descr)] = \
				parsed_block

				# ready to check for orphans in the next block
				prev_block_height = block_height

			if options.FORMAT == "MULTILINE-JSON":
				return os.linesep.join(
					l.rstrip() for l in json.dumps(
						parsed_blocks, sort_keys = True, indent = 4
					).splitlines()
				)
				# rstrip removes the trailing space added by the json dump
			if options.FORMAT == "SINGLE-LINE-JSON":
				return json.dumps(parsed_blocks, sort_keys = True)
			if options.FORMAT == "MULTILINE-XML":
				# dicttoxml has no sorting capabilities, so convert to an orderd
				# dict first and sort this
				parsed_blocks = collections.OrderedDict(parsed_blocks)
				parsed_blocks = collections.OrderedDict(sorted(
					parsed_blocks.items()
				))
				return xml.dom.minidom.parseString(
					dicttoxml.dicttoxml(parsed_blocks)
				).toprettyxml()
			if options.FORMAT == "SINGLE-LINE-XML":
				# dicttoxml has no sorting capabilities, so convert to an orderd
				# dict first and sort this
				parsed_blocks = collections.OrderedDict(parsed_blocks)
				parsed_blocks = collections.OrderedDict(sorted(
					parsed_blocks.items()
				))
				return dicttoxml.dicttoxml(parsed_blocks)
		if options.FORMAT == "BINARY":
			return "".join(
				parsed_block["bytes"] for parsed_block in data.values()
			)
		if options.FORMAT == "HEX":
			return os.linesep.join(
				bin2hex(parsed_block["bytes"]) for parsed_block in data.values()
			)

	if options.OUTPUT_TYPE == "TXS":

		# sort the txs in order of occurence
		data.sort(key = lambda tx: tx["timestamp"])

		if options.FORMAT == "MULTILINE-JSON":
			for tx in data:
				return os.linesep.join(l.rstrip() for l in json.dumps(
					tx, sort_keys = True, indent = 4
				).splitlines())
				# rstrip removes the trailing space added by the json dump
		if options.FORMAT == "SINGLE-LINE-JSON":
			return os.linesep.join(
				json.dumps(tx, sort_keys = True) for tx in data
			)
		if options.FORMAT == "MULTILINE-XML":
			return xml.dom.minidom.parseString(dicttoxml.dicttoxml(data)). \
			toprettyxml()
		if options.FORMAT == "SINGLE-LINE-XML":
			return dicttoxml.dicttoxml(data)
		if options.FORMAT == "BINARY":
			return "".join(data)
		if options.FORMAT == "HEX":
			return os.linesep.join(bin2hex(tx["bytes"]) for tx in data)

	if options.OUTPUT_TYPE == "BALANCES":
		if options.FORMAT == "MULTILINE-JSON":
			return json.dumps(data, sort_keys = True, indent = 4)
		if options.FORMAT == "SINGLE-LINE-JSON":
			return json.dumps(data, sort_keys = True)
		if options.FORMAT == "MULTILINE-XML":
			return xml.dom.minidom.parseString(dicttoxml.dicttoxml(data)). \
			toprettyxml()
		if options.FORMAT == "SINGLE-LINE-XML":
			return dicttoxml.dicttoxml(data)

	# thanks to options_grunt.sanitize_options_or_die() we will never get to
	# this line

base58alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
def is_base58(input_str):
	"""check if the input string is base58"""
	for char in input_str:
		if char not in base58alphabet:
			return False
	return True # if we get here then it is a base58 string

def base58encode(input_num):
	"""
	encode the input integer into a base58 string. see
	https://en.bitcoin.it/wiki/Base58Check_encoding for doco. code modified from
	http://darklaunch.com/2009/08/07/base58-encode-and-decode-using-php-with-\
	example-base58-encode-base58-decode using bcmath
	"""
	base = len(base58alphabet)
	encoded = ""
	num = input_num
	try:
		while num >= base:
			mod = num % base
			encoded = base58alphabet[mod] + encoded
			num = num / base
	except TypeError:
		raise TypeError(
			"function base58encode() only accepts an integer argument"
		)
	if num:
		encoded = base58alphabet[num] + encoded
	return encoded

def base58decode(value):
	"""
	decode the value into a string of bytes in base58 from
	https://github.com/gavinandresen/bitcointools/blob/master/base58.py
	"""
	base = 58
	long_value = 0L # init

	# loop through the input value one char at a time in reverse order
	# (i starts at 0)
	for (i, char) in enumerate(value[::-1]):
		long_value += base58alphabet.find(char) * (base ** i)
	decoded = "" # init
	while long_value > 255:
		(div, mod) = divmod(long_value, 256)
		decoded = chr(mod) + decoded
		long_value = div
	decoded = chr(long_value) + decoded
	padding = 0 # init
	for char in value:
		if char == base58alphabet[0]:
			padding += 1
		else:
			break
	decoded = (chr(0) * padding) + decoded
	return decoded	

def get_address_type(address):
	"""
	https://en.bitcoin.it/wiki/List_of_address_prefixes. input is an ascii
	string
	"""
	# TODO - compressed pubkey is 33 bytes
	# (bitcoin.stackexchange.com/questions/2013)
	if len(address) == 130: # hex public key. specific currency is unknown
		return "public key"

	# bitcoin eg 17VZNX1SN5NtKa8UQFxwQbFeFc3iqRYhem
	if address[0] == "1":
		if len(address) != 34:
			raise ValueError(
				"address %s looks like a bitcoin public key hash, but does not"
				" have the necessary 34 characters"
				% address
			)
		return "bitcoin pubkey hash"

	# bitcoin eg 3EktnHQD7RiAE6uzMj2ZifT9YgRrkSgzQX
	if address[0] == "3":
		if len(address) != 34:
			raise ValueError(
				"address %s looks like a bitcoin script hash, but does not have"
				" the necessary 34 characters"
				% address
			)
		return "bitcoin script hash"

	# litecoin eg LhK2kQwiaAvhjWY799cZvMyYwnQAcxkarr
	if address[0] == "L":
		if len(address) != 34:
			raise ValueError(
				"address %s looks like a litecoin public key hash, but does not"
				" have the necessary 34 characters"
				% address
			)
		return "litecoin pubkey hash"

	# namecoin eg NATX6zEUNfxfvgVwz8qVnnw3hLhhYXhgQn
	if address[0] in ["M", "N"]:
		if len(address) != 34:
			raise ValueError(
				"address %s looks like a namecoin public key hash, but does not"
				" have the necessary 34 characters"
				% address
			)
		return "namecoin pubkey hash"

	# bitcoin testnet eg mipcBbFg9gMiCh81Kj8tqqdgoZub1ZJRfn
	if address[0] in ["m", "n"]:
		if len(address) != 34:
			raise ValueError(
				"address %s looks like a bitcoin testnet public key hash, but"
				" does not have the necessary 34 characters"
				% address
			)
		return "bitcoin-testnet pubkey hash"

	return "unknown"

def get_currency(address):
	"""
	attempt to derive the currency type from the address. this is only possible
	for base58 formats.
	"""
	address_type = get_address_type(address)
	if address_type == "public key":
		return "any"
	return address_type.split(" ")[0] # return the first word

def valid_hash(hash_str):
	"""input is a hex string"""
	if len(hash_str) != 64:
		return False
	try: # make sure the hash string has only hex characters
		int(hash_str, 16)
	except:
		return False
	return True

def int2hex(intval):
	neg = "-" if (intval < 0) else ""
	intval = abs(intval)
	hex_str = hex(intval)[2:]
	if hex_str[-1] == "L":
		hex_str = hex_str[: -1]
	if is_odd(len(hex_str)):
		hex_str = "0%s" % hex_str
	return "%s%s" % (neg, hex_str)

def hex2int(hex_str):
	return int(hex_str, 16)

def hex2bin(hex_str):
	"""convert a hex string to raw binary data"""
	return binascii.a2b_hex(hex_str)

def bin2hex(binary):
	"""
	convert raw binary data to a hex string. also accepts ascii chars (0 - 255)
	"""
	return binascii.b2a_hex(binary)

def bin2int(bytes):
	return hex2int(bin2hex(bytes))

def int2bin(val, pad_length = False):
	hexval = int2hex(val)
	if pad_length: # specified in bytes
		hexval = hexval.zfill(2 * pad_length)
	return hex2bin(hexval)

def ascii2hex(ascii_str):
	"""ascii strings are the same as binary data in python"""
	return binascii.b2a_hex(ascii_str)

def ascii2bin(ascii_str):
	#return ascii_str.encode("utf-8")
	return binascii.a2b_qp(ascii_str)

def is_odd(intval):
	return True if (intval % 2) else False

import_config() # import the config globals straight away
sanitize_globals() # run whenever the module is imported

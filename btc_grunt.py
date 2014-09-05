"""
module containing some general bitcoin-related functions. whenever the word
"orphan" is used in this file it refers to orphan-block, not orphan-transaction.
orphan transactions do not exist in the blockfiles that this script processes.
"""

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
import ecdsa_ssl
import inspect
import json
import dicttoxml
import xml.dom.minidom

# module to do language-related stuff for this project
import lang_grunt

# module to process the user-specified btc-inquisitor options
import options_grunt

# module globals:

max_block_size = 500 # 1024 * 1024 # 1MB == 1024 * 1024 bytes

# the number of bytes to process in ram at a time.
# set this to the max_block_size + 4 bytes for the magic_network_id seperator +
# 4 bytes which contain the block size 
active_blockchain_num_bytes = max_block_size + 4 + 4

# if the result set grows beyond this then dump the saved blocks to screen
max_saved_blocks = 100

magic_network_id = "f9beb4d9" # gets converted to bin in sanitize_globals() asap
coinbase_maturity = 100 # blocks
satoshis_per_btc = 100000000
base58alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
blank_hash = "0" * 64 # gets converted to bin in sanitize_globals() asap
coinbase_index = 0xffffffff
int_max = 0x7fffffff
initial_bits = "1d00ffff" # gets converted to bin in sanitize_globals() asap
# difficulty_1 = bits2target(initial_bits)
difficulty_1 = 0x00000000ffff0000000000000000000000000000000000000000000000000000
blockname_format = "blk*[0-9]*.dat"
base_dir = os.path.expanduser("~/.btc-inquisitor/")
tx_meta_dir = "%stx_metadata/" % base_dir
latest_saved_tx_data = None # gets initialized asap in the following code
latest_validated_block_data = None # gets initialized asap in the following code
tx_metadata_keynames = [
	"blockfile_num", # int
	"block_start_pos", # int
	"tx_start_pos", # int
	"tx_size", # int
	"block_height", # int
	"is_coinbase", # 1 = True, None = False
	"is_orphan", # 1 = True, None = False
	"spending_txs_list" # "[spendee_hash-spendee_index, ...]"
]
block_header_info = [
	"block_filenum",
	"block_pos",
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
	"block_bytes"
]
block_header_validation_info = [
	# do the transaction hashes form the merkle root specified in the header?
	"merkle_root_validation_status",

	# do the previous target and time to mine 2016 blocks produce this target?
	"target_validation_status",

	# is the difficulty > 1?
	"difficulty_validation_status",

	# is the block hash below the target?
	"block_hash_validation_status",

	# is the block size less than the permitted maximum?
	"block_size_validation_status",

	# are the coinbase funds correct for this block height?
	"coinbase_funds_validation_status"
]
all_txin_info = [
	"prev_tx_metadata",
	"prev_tx",
	"txin_funds",
	"txin_hash",
	"txin_index",
	"txin_script_length",
	"txin_script",
	"txin_script_list",
	"txin_parsed_script",
	"txin_address",
	"txin_sequence_num"
]
all_txout_info = [
	"txout_funds",
	"txout_script_length",
	"txout_script",
	"txout_script_list",
	"txout_address",
	"txout_parsed_script"
]
remaining_tx_info = [
	"tx_pos_in_block",
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

def sanitize_globals():
	"""
	this function is run automatically at the start - see the final line in this
	file.
	"""
	global magic_network_id, blank_hash, initial_bits, latest_saved_tx_data, \
	latest_validated_block_data

	if active_blockchain_num_bytes < 1:
		lang_grunt.die(
			"Error: Cannot process %s bytes of the blockchain - this number is"
		    " too small! Please increase the value of variable"
		    " 'active_blockchain_num_bytes' at the top of module btc_grunt.py."
		    % active_blockchain_num_bytes
		)
	# use a safety factor of 3
	if active_blockchain_num_bytes > (psutil.virtual_memory().free / 3):
		lang_grunt.die(
			"Error: Cannot process %s bytes of the blockchain - not enough ram!"
		    " Please lower the value of variable 'active_blockchain_num_bytes'"
		    " at the top of file btc_grunt.py."
			% active_blockchain_num_bytes
		)
	magic_network_id = hex2bin(magic_network_id)
	blank_hash = hex2bin(blank_hash)
	initial_bits = hex2bin(initial_bits)
	latest_saved_tx_data = get_latest_saved_tx_data()
	latest_validated_block_data = get_latest_validated_block()

def enforce_sanitization(inputs_have_been_sanitized):
	previous_function = inspect.stack()[1][3] # [0][3] would be this func name
	if not inputs_have_been_sanitized:
		lang_grunt.die(
			"Error: You must sanitize the input options with function"
			" sanitize_options_or_die() before passing them to function %s()."
			% previous_function
		)

def init_base_dir():
	"""
	if the base dir does not exist then attempt to create it. also create the
	necessary subdirectories and their readme files for this script. die if this
	fails.
	"""
	try:
		if not os.path.exists(base_dir):
			os.makedirs(base_dir)
	except:
		lang_grunt.die("failed to create directory %s" % base_dir)

	try:
		if not os.path.exists(tx_meta_dir):
			os.makedirs(tx_meta_dir)
	except:
		lang_grunt.die("failed to create directory %s" % tx_meta_dir)

	readme_file = "%sREADME" % base_dir
	try:
		if not os.path.exists(readme_file):
			with open(readme_file, "w") as f:
				f.write(
					"this directory contains the following metadata for the"
					" btc-inquisitor script:\n\n- tx_metadata dir - data to"
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
					" third output has not yet been spent.\nthe transaction"
					" metadata in these files is used to perform checksigs in"
					" the blockchain for validations, and the spending data is"
					" used to check for doublespends. the block height is used"
					" to ensure that a coinbase transaction has reached"
					" maturity before being spent."
				)
	except:
		lang_grunt.die("failed to create directory %s" % tx_meta_dir)

def init_orphan_list():
	"""
	we only know if a block is an orphan by waiting coinbase_maturity blocks
	then looking back and identifying blocks which are not on the main-chain.
	so save all blocks then analyse previous coinbase_maturity blocks every
	coinbase_maturity blocks and update the list of orphan hashes
	"""
	orphans = [] # list of hashes
	return orphans

def init_hash_table():
	"""
	the hash_table contains a list of hashes in the format

	{current hash: [current block height, previous hash], ...}

	in the case of a chain fork, two hashes can have the same height. we need to
	keep the hash table populated only coinbase_maturity blocks back from the
	current block.
	"""
	hash_table = {blank_hash: [-1, blank_hash]} # init
	return hash_table

def extract_full_blocks(options, sanitized = False):
	"""
	get full blocks which contain the specified addresses, transaction hashes or
	block hashes.
	"""
	# make sure the user input data has been sanitized
	enforce_sanitization(sanitized)

	# TODO - determine if this is needed
	# if this is the first pass of the blockchain then we will be looking
	# coinbase_maturity blocks beyond the user-specified range so as to check
	# for orphans. once his has been done, it does not need doing again
	# seek_orphans = True if (pass_num == 1) else False

	filtered_blocks = {} # init. this is the only returned var
	target_data = {} # init
	orphans = init_orphan_list() # list of hashes
	hash_table = init_hash_table()
	block_height = 0 # init
	exit_now = False # init
	(progress_bytes, full_blockchain_bytes) = maybe_init_progress_meter(options)

	"""# validation needs to store all unspent txs (slower)
	if options.validate:
		all_unspent_txs = {}
	"""
	
	for block_filename in sorted(glob.glob(
		options.BLOCKCHAINDIR + blockname_format
	)):
		active_file_size = os.path.getsize(block_filename)
		# blocks_into_file includes orphans, whereas block_height does not
		blocks_into_file = -1 # reset
		bytes_into_file = 0 # reset
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

			# die if this chunk does not begin with the magic network id
			enforce_magic_network_id(
				active_blockchain, bytes_into_section, block_filename,
				blocks_into_file, block_height
			)
			# get the number of bytes in this block
			num_block_bytes = count_block_bytes(
				active_blockchain, bytes_into_section
			)
			# die if this chunk is smaller than the current block
			enforce_min_chunk_size(
				num_block_bytes, active_blockchain_num_bytes, blocks_into_file,
				block_filename, block_height
			)
			# if this block is incomplete
			if incomplete_block(
				active_blockchain, num_block_bytes, bytes_into_section
			):
				fetch_more_blocks = True
				continue # get the next block in this file

			blocks_into_file += 1 # ie 0 = first block in file
			block_file_num = int(re.findall(r"\d+", block_filename)[0])

			# block as bytes
			block = active_blockchain[bytes_into_section + 8: \
			bytes_into_section + num_block_bytes + 8]

			# update position counters
			block_pos = bytes_into_file 
			bytes_into_section += num_block_bytes + 8
			bytes_into_file += num_block_bytes + 8

			# make sure the block is correct size
			enforce_block_size(
				block, num_block_bytes, block_filename, blocks_into_file
			)
			# if we have already saved the txhash locations in this block then
			# get as little block data as possible, otherwise parse all data and
			# save it to disk. also get the block height within this function.
			(parsed_block, hash_table) = minimal_block_parse_maybe_save_txs(
				block, latest_saved_tx_data, latest_validated_block_data,
				block_file_num, block_pos, hash_table, options
			)
			# update the block height - needed only for error notifications
			block_height = parsed_block["block_height"]
			if block_height in [187]:
				pass

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
			(filtered_blocks, hash_table, target_data) = manage_orphans(
				filtered_blocks, hash_table, parsed_block, target_data, 2
			)
			# convert hash or limit ranges to blocknum ranges
			options = options_grunt.convert_range_options(options, parsed_block)

			# update the target data every two weeks (2016 blocks) and remove
			# target data that is older that 2 weeks + 1 block
			target_data = manage_target_data(parsed_block, target_data)

			# if the block requires validation and we have not yet validated it
			# then do so now (we must validate all blocks from the start, but
			# only if they have not been validated before)
			if should_validate_block(
				options, parsed_block, latest_validated_block_data
			):
				parsed_block = validate_block(
					parsed_block, target_data, options
				)
			in_range = False # init

			# return if we are beyond the specified range + coinbase_maturity
			if after_range(options, parsed_block["block_height"], True):
				exit_now = True # since "break 2" is not possible in python
				break

			# skip the block if we are past the user specified range. note that
			# the only reason to be here is to see if any of the blocks in the
			# range are orphans
			if after_range(options, parsed_block["block_height"]):
				continue

			# skip the block if we are not yet in range
			if before_range(options, parsed_block["block_height"]):
				continue

			# be explicit. simplifies processing in the following functions
			in_range = True

			# so far we have not parsed any tx data. if the options specify this
			# block (eg an address that is in this block, or a tx hash that is
			# in this block) then get all tx data. do this after the range
			# checks since there is no need to look for relevant addresses or
			# txhashes outside the range
			parsed_block = update_relevant_block(
				options, in_range, parsed_block, block
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
	(filtered_blocks, hash_table, target_data) = manage_orphans(
		filtered_blocks, hash_table, parsed_block, target_data, 1
	)
	save_latest_tx_progress(parsed_block)

	# save the latest validated block
	if options.validate:
		save_latest_validated_block(parsed_block)

	return filtered_blocks

def extract_tx(options, txhash, tx_metadata):
	"""given tx position data, fetch the tx data from the blockchain files"""

	# we need 5 leading zeros in the blockfile number
	f = open("%sblk%05d.dat" % (
		options.BLOCKCHAINDIR, tx_metadata["blockfile_num"]
	), "rb")
	f.seek(tx_metadata["block_start_pos"], 0)

	# 8 = 4 bytes for the magic network id + 4 bytes for the block size
	num_bytes = 8 + tx_metadata["tx_start_pos"] + tx_metadata["tx_size"]

	partial_block_bytes = f.read(num_bytes)
	f.close()

	# make sure the block starts at the magic network id
	if partial_block_bytes[: 4] != magic_network_id:
		lang_grunt.die(
			"transaction %s has incorrect block position data - it does not"
			" reference the start of a block. possibly the blockchain has been"
			" updated since the tx hash data was saved?"
			% txhash
		)
	tx_bytes = partial_block_bytes[8 + tx_metadata["tx_start_pos"]: ]
	return tx_bytes

def maybe_init_progress_meter(options):
	"""
	initialise the progress meter and get the size of all the blockchain
	files combined
	"""
	if not options.progress:
		return (None, None)

	# get the size of all files - only needed for the progress meter 
	full_blockchain_bytes = get_full_blockchain_size(options.BLOCKCHAINDIR)
	progress_bytes = 0 # init
	progress_meter.render(0, "block 0") # init progress meter
	return (progress_bytes, full_blockchain_bytes)

def maybe_update_progress_meter(
	options, num_block_bytes, progress_bytes, block_height,
	full_blockchain_bytes
):
	"""
	if a progress meter is specified then update it with the number of bytes
	through the entire blockchain
	"""
	if options.progress:
		progress_bytes += num_block_bytes + 8
		progress_meter.render(
			100 * progress_bytes / float(full_blockchain_bytes),
			"block %s" % block_height
		)

	return progress_bytes

def maybe_finalize_progress_meter(options, progress_meter, block_height):
	"""if a progress meter is specified then set it to 100%"""
	if options.progress:
		progress_meter.render(100, "block %s" % block_height)
		progress_meter.done()

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
		# first filter out the data that has been specified in the options
		data = final_results_filter(filtered_blocks, options)
		print get_formatted_data(options, data)
		return None

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

def save_latest_validated_block(latest_parsed_block):
	"""
	save the latest block that has been validated to disk. overwrite existing
	file if it exists.
	"""
	latest_validated_block_file_num = latest_parsed_block["block_filenum"]
	latest_validated_block_pos = latest_parsed_block["block_pos"]
	# do not overwrite a later value with an earlier value
	if latest_validated_block_data is not None:
		(previous_validated_block_file_num, previous_validated_block_pos) = \
		latest_validated_block_data # global
		if(
			(previous_validated_block_file_num >=
			latest_validated_block_file_num) and
			(previous_validated_block_pos > latest_validated_block_pos)
		):
			return

	# from here on we know that the latest validated block is beyond where we
	# were upto before. so update the latest-saved-tx file
	with open("%slatest-validated-block.txt" % base_dir, "w") as f:
		f.write("%s,%s" % (
			latest_validated_block_file_num, latest_validated_block_pos
		))

def get_latest_validated_block():
	"""
	retrieve the latest validated block data. this is useful as it enables us to
	avoid re-validating blocks that have already been validated in the past.
	"""
	try:
		with open("%slatest-validated-block.txt" % base_dir, "r") as f:
			file_data = f.read().strip()
			# file gets automatically closed
		latest_validated_block_data = [int(x) for x in file_data.split(",")]
	except:
		# the file cannot be opened
		latest_validated_block_data = None
	return latest_validated_block_data

def save_latest_tx_progress(latest_parsed_block):
	"""
	save the latest tx hash that has been processed to disk. overwrite existing
	file if it exists.
	"""
	latest_saved_tx_blockfile_num = latest_parsed_block["block_filenum"]
	latest_saved_block_pos = latest_parsed_block["block_pos"]
	# do not overwrite a later value with an earlier value
	if latest_saved_tx_data is not None:
		(previous_saved_tx_blockfile_num, previous_saved_block_pos) = \
		latest_saved_tx_data # global
		if(
			(previous_saved_tx_blockfile_num >=
			latest_saved_tx_blockfile_num) and
			(previous_saved_block_pos > latest_saved_block_pos)
		):
			return

	# from here on we know that the latest parsed block is beyond where we were
	# upto before. so update the latest-saved-tx file
	with open("%slatest-saved-tx.txt" % base_dir, "w") as f:
		f.write("%s,%s" % (
			latest_saved_tx_blockfile_num, latest_saved_block_pos
		))

def get_latest_saved_tx_data():
	"""
	retrieve the latest saved tx hash and block height. this is useful as it
	enables us to avoid reading from disk lots of times (slow) to check if a tx
	hash has already been saved.
	"""
	try:
		with open("%slatest-saved-tx.txt" % base_dir, "r") as f:
			file_data = f.read().strip()
			# file gets automatically closed
		latest_saved_tx_data = [int(x) for x in file_data.split(",")]
	except:
		# the file cannot be opened
		latest_saved_tx_data = None
	return latest_saved_tx_data

def save_tx_metadata(options, parsed_block):
	"""
	save all txs in this block to the filesystem. as of this block the txs are
	unspent.

	we need to backup the location data of each tx so that it can be retrieved
	from the blockchain later on. for this we need to store:

	- the blockfile number
	- the start position of the block, including magic_network_id
	- the start position of the tx in the block
	- the size of the tx in bytes

	we also need to store the block height so that we can check whether the tx
	has reached coinbase maturity before it is spent.

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
	for (tx_num, tx) in parsed_block["tx"].items():
		is_coinbase = 1 if (tx_num == 0) else None
		is_orphan = None if not parsed_block["is_orphan"] else 1
		# no spending txs at this stage
		spending_txs_list = [None] * len(tx["output"])
		save_data = {
			"blockfile_num": parsed_block["block_filenum"],
			"block_start_pos": parsed_block["block_pos"],
			"tx_start_pos": tx["pos"],
			"tx_size": tx["size"],
			"block_height": parsed_block["block_height"],
			"is_coinbase": is_coinbase,
			"is_orphan": is_orphan,
			"spending_txs_list": spending_txs_list
		}
		save_tx_data_to_disk(options, bin2hex(tx["hash"]), save_data)

def save_tx_data_to_disk(options, txhash, save_data):
	"""
	save a 64 character hash, eg 2ea121e32934b7348445f09f46d03dda69117f2540de164
	36835db7f032370d0 in a directory structure like base_dir/2ea/121/e32/934/
	b73/484/45f/09f/46d/03d/da6/911/7f2/540/de1/643/683/5db/7f0/323/70d/0.txt
	this way the maximum number of files or directories per dir is 0xfff = 4095,
	which should be fine on any filesystem the user chooses to run this script
	on.

	for simplicity we assume that each unspent tx hash is unique. this is
	actually not the case, for example, block 91842 has a duplicate coinbase tx
	of the coinbase tx in block 91812. this occurs when two coinbase addresses
	are the same. as a result, we will overwrite txs with later duplicates. if
	the later duplicate is an orphan then it will be unspendable.

	TODO - bip30 may specify something else, if so then update this function
	accordingly.
	"""
	(f_dir, f_name) = hash2dir_and_filename(txhash)

	# create the dir if it does not exist
	try:
		if not os.path.exists(os.path.dirname(f_name)):
			os.makedirs(f_dir)
	except:
		lang_grunt.die("failed to create directory %s" % f_dir)

	# write data to the file if the file does not exist
	try:
		if not os.path.isfile(f_name):
			with open(f_name, "w") as f:
				f.write(tx_metadata_dict2csv(save_data))
			return
	except:
		lang_grunt.die(
			"failed to open file %s for writing unspent transaction data %s in"
			% (f_name, save_data)
		)
	# if we get here then we know the file exists
	existing_data_csv = get_tx_metadata_csv(txhash)
	existing_data_dict = tx_metadata_csv2dict(existing_data_csv)

	# if there is nothing to update then exit here
	if existing_data_dict == save_data:
		return

	# if there are updates to be made then merge them together then save to disk
	save_data = merge_tx_metadata(txhash, existing_data_dict, save_data)
	with open(f_name, "w") as f:
		f.write(tx_metadata_dict2csv(save_data))

def merge_tx_metadata(txhash, old_dict, new_dict):
	"""update the old dict with data from the new dict"""

	# assume that the old_list at least has the correct number of elements
	return_dict = copy.deepcopy(old_dict)

	# TODO - reconfigure the tx metadata if changes are found

	# if there is a change in the position of the tx in the blockchain then
	# warn the user about it
	if (
		("blockfile_num" in old_dict) and
		("blockfile_num" in new_dict) and
		(old_dict["blockfile_num"] != new_dict["blockfile_num"])
	):
		lang_grunt.die(
			"transaction with hash %s exists in two different blockfiles: "
			" filenum %s and filenum %s."
			% (txhash, old_dict["blockfile_num"], new_dict["blockfile_num"])
		)
	# from here on, if the blockfilenum exists it is the same in old and new
	if (
		("block_start_pos" in old_dict) and
		("block_start_pos" in new_dict) and
		(old_dict["block_start_pos"] != new_dict["block_start_pos"])
	):
		lang_grunt.die(
			"transaction with hash %s exists within two different blocks in the"
			" same block file: at byte %s and at byte %s."
			% (txhash, old_dict["block_start_pos"], new_dict["block_start_pos"])
		)
	# from here on, if the block start pos exists it is the same in old and new
	if (
		("tx_start_pos" in old_dict) and
		("tx_start_pos" in new_dict) and
		(old_dict["tx_start_pos"] != new_dict["tx_start_pos"])
	):
		lang_grunt.die(
			"transaction with hash %s exists in two different start positions"
			" in the same block: at byte %s and at byte %s."
			% (txhash, old_dict["tx_start_pos"], new_dict["tx_start_pos"])
		)
	# from here on, if the block start pos exists it is the same in old and new

	for (key, old_v) in old_dict.items():
		try:
			new_v = new_dict[key]
		except:
			new_v = None

		# if the old is the same as the new then stick to the default
		if old_v == new_v:
			continue

		# if neither old nor new is set
		if (
			(old_v is None) and
			(new_v is None)
		):
			return_dict[key] = None
			continue 

		# if only old is set then use that one
		if (
			(old_v is not None) and
			(new_v is None)
		):
			return_dict[key] = old_v
			continue

		# if only new is set then use that one
		if (
			(old_v is None) and
			(new_v is not None)
		):
			return_dict[key] = new_v
			continue

		# if we get here then both old and new are set and different...

		# orphan status
		if key == "is_orphan":
			# do not update if the tx is already marked as an orphan
			if old_v is not None:
				return_dict[key] = old_v
			else:
				return_dict[key] = new_v

		# spending txs list. each element is a later tx hash and txin index that
		# is spening from the tx specified by the filename
		if key == "spending_txs_list":
			return_dict["spending_txs_list"] = merge_spending_txs_lists(
				txhash, old_v, new_v
			)
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
		lang_grunt.die(
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
	list_data = [] # init
	for keyname in tx_metadata_keynames:

		if keyname in dict_data:
			el = copy.deepcopy(dict_data[keyname])
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

		else:
			if el is None:
				el = ""
			else:
				# convert numbers to strings
				el = "%s" % el

		list_data.append(el)

	return ",".join(list_data)

def tx_metadata_csv2dict(csv_data):
	"""
	the tx data is stored as comma seperated values in the tx metadata files and
	the final element is a representation of a list. the tx_metadata_keynames
	global list shows what each element of the csv represents.
	"""
	# first get the csv as a list (but not including the square bracket, since
	# it might contain commas which would be interpreted as top level elements
	start_sq = csv_data.index("[")
	list_data = csv_data[: start_sq - 1].split(",")

	# add the square bracket substring back into the list
	sq = csv_data[start_sq:]
	list_data.append(sq)

	dict_data = {}
	for (i, el) in enumerate(list_data):
		# convert empty strings to None values
		if el == "":
			el = None
		elif (
			(el[0] == "[") and
			(el[-1] == "]")
		):
			el = el[1: -1].split(",")
			for (j, sub_el) in enumerate(el):
				# convert empty strings to None values
				if sub_el == "":
					el[j] = None
		else:
			el = int(el)

		dict_data[tx_metadata_keynames[i]] = el

	return dict_data

def get_tx_metadata_csv(txhash):
	"""
	given a tx hash (as a hex string), fetch the position data from the
	tx_metadata dirs. return csv data as it is stored in the file.
	"""
	(f_dir, f_name) = hash2dir_and_filename(txhash)
	try:
		with open(f_name, "r") as f:
			data = f.read()
	except:
		lang_grunt.die(
			"failed to read from file %s. it may not exist." % f_name
		)
		data = None

	return data

def mark_spent_tx(
	options, spendee_txhash, spendee_index, spender_txhash, spender_index
):
	"""
	mark the transaction as spent using the later tx hash and later txin index.
	don't worry about overwriting a transaction that has already been spent -
	the lower level functions will handle this.
	"""
	# coinbase txs do not spend from any previous tx in the blockchain and so do
	# not need to be marked off
	if (
		(spendee_txhash == blank_hash) and \
		(spendee_index == coinbase_index)
	):
		return

	# use only the first x bytes to conserve disk space. this still gives us
	# ffff chances of catching a doublespend - plenty given how rare this is
	x = 2
	spender_txhash = bin2hex(spender_txhash[: x])

	# construct the list of txs that are spending from the previous tx. this
	# list may be too small, but it doesn't matter - so long as we put the data
	# in the correct location in the list.
	spender_txs_list = [None] * (spendee_index + 1) # init
	spender_txs_list[spendee_index] = "%s-%s" % (spender_txhash, spender_index)
	save_tx_data_to_disk(options, spendee_txhash, {
		"spending_txs_list": spender_txs_list
	})

def hash2dir_and_filename(hash64 = ""):
	"""
	convert a 64 character hash, eg 2ea121e32934b7348445f09f46d03dda69117f2540de
	16436835db7f032370d0 to a directory structure like base_dir/2e/a1/21/e3/29/
	34/b7/34/84/45/f0/9f/46/d0/3d/da/69/11/7f/25/40/de/16/43/68/35/db/7f/03/23/
	70/d0.txt
	"""
	n = 2 # max dirname length
	hash_elements = [hash64[i: i + n] for i in range(0, len(hash64), n)]
	f_name = None # init
	if hash_elements:
		f_dir = "%s%s/" % (tx_meta_dir, "/".join(hash_elements[: -1]))
		f_name = "%s%s.txt" % (f_dir, hash_elements[-1])

	return (f_dir, f_name)

def minimal_block_parse_maybe_save_txs(
	block, latest_saved_tx_data, latest_validated_block_data,
	current_block_file_num, block_pos, hash_table, options
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
	if options.validate:
		if latest_validated_block_data is not None:
			(latest_validated_blockfile_num, latest_validated_block_pos) = \
			latest_validated_block_data

			# if we have passed the latest validated block then get all block
			# info
			if (
				(current_block_file_num >= latest_validated_blockfile_num) and
				(block_pos > latest_validated_block_pos)
			):
				save_tx = True

			# otherwise only get the header
			else:
				save_tx = False

		# if there is no validated block data already then we must save all txs
		else:
			save_tx = True

	# if the user does not want to validate blocks then we don't need txs
	else:
		save_tx = False

	if not save_tx:
		if latest_saved_tx_data is not None:
			(latest_saved_tx_blockfile_num, latest_saved_block_pos) = \
			latest_saved_tx_data

			# if we have passed the latest saved tx pos then get all block info
			if (
				(current_block_file_num >= latest_saved_tx_blockfile_num) and
				(block_pos > latest_saved_block_pos)
			):
				save_tx = True

			# otherwise only get the header
			else:
				save_tx = False

		# if there is no saved tx data then we must save all txs
		else:
			save_tx = True

	if save_tx:	
		get_info = all_block_and_validation_info
	else:
		get_info = all_block_header_and_validation_info

	parsed_block = block_bin2dict(block, get_info, options)
	parsed_block["block_filenum"] = current_block_file_num
	parsed_block["block_pos"] = block_pos

	# die if this block has no ancestor
	enforce_ancestor(hash_table, parsed_block["previous_block_hash"])

	# get the block height
	parsed_block["block_height"] = \
	hash_table[parsed_block["previous_block_hash"]][0] + 1

	# get the coinbase txin funds
	if save_tx:
		parsed_block["tx"][0]["input"][0]["funds"] = mining_reward(
			parsed_block["block_height"]
		)
		save_tx_metadata(options, parsed_block)

	return (parsed_block, hash_table)

def before_range(options, block_height):
	"""
	check if the current block is before the range (inclusive) specified by the
	options

	note that function options_grunt.convert_range_options() must be called
	before running this function so as to convert ranges based on hashes or
	limits into ranges based on block numbers.
	"""
	# if the start block number has not yet been determined then we must be
	# before the range
	if options.STARTBLOCKNUM is None:
		return True

	if (
		(options.STARTBLOCKNUM is not None) and
		(block_height < options.STARTBLOCKNUM)
	):
		return True

	return False

def after_range(options, block_height, seek_orphans = False):
	"""
	have we gone past the user-specified block range?

	if the seek_orphans option is set then we must proceed coinbase_maturity
	blocks past the user specified range to be able to check for orphans. this
	options is only needed on the first pass of the blockchain.

	note that function options_grunt.convert_range_options() must be called
	before running this function so as to convert ranges based on hashes or
	limits into ranges based on block numbers.
	"""
	# if the user wants to go for all blocks then we can never be beyond range
	if (
		(options.ENDBLOCKNUM is not None) and
		(options.ENDBLOCKNUM == "end")
	):
		return False

	new_upper_limit = options.ENDBLOCKNUM # init
	if seek_orphans:
		new_upper_limit += coinbase_maturity
	
	if (
		(options.ENDBLOCKNUM is not None) and
		(options.ENDBLOCKNUM != "end") and
		(block_height > new_upper_limit)
	):
		return True

	return False

def incomplete_block(active_blockchain, num_block_bytes, bytes_into_section):
	"""check if this block is incomplete or complete"""
	if (num_block_bytes + 8) > (len(active_blockchain) - bytes_into_section):
		return True
	else: # block is complete
		return False

def whole_block_match(options, block_hash, block_height):
	"""
	check if the user wants the whole block returned

	note that function options_grunt.convert_range_options() must be called
	before running this function so as to convert ranges based on hashes or
	limits into ranges based on block numbers.
	"""

	# if the block is not in the user-specified range then it is not a match.
	if (
		before_range(options, block_height) or
		after_range(options, block_height)
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

def update_relevant_block(options, in_range, parsed_block, block):
	"""
	if the options specify this block then parse the tx data (which we do not
	yet have) and return it. we have previously already gotten the block header
	and header-validation info so there is no need to parse these again.
	"""

	# by this point we already have already parsed the info from
	# all_block_header_and_validation_info, so we only need to get the remaining
	# transaction and transaction-validation info. we will not be calculating
	# validation statuses at this stage, but we still want to show the user the
	# things that can be validated 
	get_info = copy.deepcopy(all_tx_and_validation_info)

	# if the block is not in range then exit here without adding it to the
	# filtered_blocks var. after_range() searches coinbase_maturity beyond the
	# user-specified limit to determine whether the blocks in range are orphans
	if not in_range:
		return None

	# check the block hash and whether the block has been specified by default
	if whole_block_match(
		options, parsed_block["block_hash"], parsed_block["block_height"]
	):
		parsed_block.update(block_bin2dict(block, get_info, options))
		return parsed_block

	# check the txin hashes
	if options.TXINHASHES:
		parsed_block.update(block_bin2dict(block, ["txin_hash"], options))
		get_info.remove("txin_hash")
		# if any of the options.TXINHASHES matches a txin then this block is
		# relevant, so get the remaining data
		if txin_hashes_in_block(parsed_block, options.TXINHASHES):
			parsed_block.update(block_bin2dict(block, get_info))
			return parsed_block

	# check the txout hashes (only 1 hash per tx)
	if options.TXHASHES is not None:
		parsed_block.update(block_bin2dict(block, ["tx_hash"], options))
		get_info.remove("tx_hash")
		# if any of the options.TXHASHES matches a tx hash then this block is
		# relevant, so get the remaining data
		if tx_hashes_in_block(parsed_block, options.TXHASHES):
			parsed_block.update(block_bin2dict(block, get_info, options))
			return parsed_block

	# check the addresses
	if (
		(options.ADDRESSES is not None) and
		addresses_in_block(options.ADDRESSES, block)
	):
		parsed_block.update(block_bin2dict(block, get_info, options))
		return parsed_block

	# if we get here then no data has been found and this block is not relevant
	return None

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
					if txout["address"] in options.ADDRESSES:
						txs[txhash] = tx
				# check the txin addresses
				for txin in tx["input"].values():
					if txin["address"] in options.ADDRESSES:
						txs[txhash] = tx

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
		block, ["txin_address", "txout_address"], options
	)
	for tx_num in parsed_block["tx"]:
		if parsed_block["tx"][tx_num]["input"] is not None:
			txin = parsed_block["tx"][tx_num]["input"]
			for input_num in txin:
				if (
					(txin[input_num]["address"] is not None) and
					(txin[input_num]["address"] in addresses)
				):
					return True

		if parsed_block["tx"][tx_num]["output"] is not None:
			txout = parsed_block["tx"][tx_num]["output"]
			for output_num in txout:
				if (
					(txout[output_num]["address"] is not None) and
					(txout[output_num]["address"] in addresses)
				):
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
		parsed_block = block_bin2dict(block, ["tx_hash", "txout_address"])

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

			# if this txout's address has been specified by the user then save
			# the index
			if txout["address"] in options.ADDRESSES:
				indexes.append(txout_num)
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

def update_txin_data(blocks):
	"""
	update txin addresses and funds where possible. these are derived from
	previous txouts
	"""
	aux_txout_data = {}
	""" of the format {
		txhash: {
			index: [script, address, funds],
			...,
			index: [script, address, funds]
		},
		txhash: {
			index: [script, address, funds],
			...,
			index: [script, address, funds]
		}
	}
	"""

	# loop through all blocks in the original order
	for (block_hash, parsed_block) in blocks.items():
		block_updated = False # init

		for tx_num in parsed_block["tx"]:
			tx = parsed_block["tx"][tx_num]
			txouts = tx["output"]
			txins = tx["input"]
			txhash = tx["hash"]

			# first save relevant txout data
			for index in sorted(txouts):
				if txhash not in aux_txout_data:
					aux_txout_data[txhash] = {} # init
				
				aux_txout_data[txhash][index] = [
					txouts[index]["script"],
					#txins["address"],
					txouts["address"],
					txouts[index]["funds"]
				]

			# TODO - do not allow spending from orphan blocks
			# now use earlier txout data to update txin data
			for input_num in txins:
				from_address = txins[input_num]["address"]
				if txins[input_num]["verification_attempted"] == True:
					continue

				parsed_block["tx"][tx_num]["input"][input_num] \
				["verification_attempted"] = True

				if parsed_block["tx"][tx_num]["input"][input_num] \
				["verification_succeeded"] == True:
					continue

				# at this point: from_address == None and funds == None

				prev_hash = txins[input_num]["hash"]
				prev_index = txins[input_num]["index"]
				parsed_block["tx"][tx_num]["input"][input_num] \
				["verification_succeeded"] = False

				# if this transaction is not relevant then skip it
				if (
					(prev_hash not in aux_txout_data) or
					(prev_index in aux_txout_data[prev_hash])
				):
					continue

				# if the checksig fails then the transaction is not valid
				if not checksig(
					tx, aux_txout_data[prev_hash][prev_index][0], input_num
				):
					continue

				parsed_block["tx"][tx_num]["input"][input_num] \
				["verification_succeeded"] = True

				from_address = aux_txout_data[prev_hash][prev_index][1]
				funds = aux_txout_data[prev_hash][prev_index][2]

				if from_address is not None:
					parsed_block["tx"][tx_num]["input"][input_num] \
					["address"] = from_address
					block_updated = True

				if funds is not None:
					parsed_block["tx"][tx_num]["input"][input_num] \
					["funds"] = funds
					block_updated = True

				# now that this previous tx-output has been used up, delete it
				# from the pool to avoid double spends
				del aux_txout_data[prev_hash][prev_index]

				# if all indexes for this hash have been used up then delete
				# this hash from the pool aswell
				if not aux_txout_data[prev_hash]:
					del aux_txout_data[prev_hash]

		if block_updated:
			blocks[block_hash] = parsed_block

	return blocks

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

def enforce_magic_network_id(
	active_blockchain, bytes_into_section, block_filename, blocks_into_file,
	block_height
):
	"""die if this chunk does not begin with the magic network id"""
	if (
		active_blockchain[bytes_into_section:bytes_into_section + 4] \
		!= magic_network_id
	):
		lang_grunt.die(
			"Error: block file %s appears to be malformed - block %s in this"
			" file (absolute block num %s) does not start with the magic"
			" network id."
			% (block_filename, blocks_into_file + 1, block_height)
		)

def enforce_min_chunk_size(
	num_block_bytes, active_blockchain_num_bytes, blocks_into_file,
	block_filename, block_height
):
	"""die if this chunk is smaller than the current block"""
	if (num_block_bytes + 8) > active_blockchain_num_bytes:
		lang_grunt.die(
			"Error: cannot process %s bytes of the blockchain since block %s of"
			" file %s (absolute block num %s) has %s bytes and this script"
			" needs to extract at least one full block (plus its 8 byte header)"
			" at once (which comes to %s for this block). Please increase the"
			" value of variable 'active_blockchain_num_bytes' at the top of"
			" file btc_grunt.py."
			% (active_blockchain_num_bytes, blocks_into_file + 1,
			block_filename, block_height, num_block_bytes,
			num_block_bytes + 8)
		)

def count_block_bytes(blockchain, bytes_into_section):
	"""use the blockchain to get the number of bytes in this block"""
	pos = bytes_into_section
	num_block_bytes = bin2int(little_endian(blockchain[pos + 4: pos + 8]))
	return num_block_bytes

def enforce_block_size(
	block, num_block_bytes, block_filename, blocks_into_file
):
	"""die if the block var is the wrong length"""
	if len(block) != num_block_bytes:
		lang_grunt.die(
			"Error: Block file %s appears to be malformed - block %s is"
			" incomplete."
			% (block_filename, blocks_into_file)
		)

def enforce_ancestor(hash_table, previous_block_hash):
	"""die if the block has no ancestor"""
	if previous_block_hash not in hash_table:
		lang_grunt.die(
			"Error: Could not find parent for block with hash %s (parent hash:"
			" %s). Investigate."
			% (bin2hex(block_hash), bin2hex(previous_block_hash))
		)

def encapsulate_block(block_bytes):
	"""
	take a block of bytes and return it encapsulated with magic network id and
	block length
	"""
	return magic_network_id + int2bin(len(block_bytes), 4) + block_bytes

def block_bin2dict(block, required_info_, options = None):
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

	if "block_filenum" in required_info:
		# this value gets stored in the tx_metadata dirs to enable quick
		# retrieval from the blockchain files later on. only init here - update
		# later
		block_arr["block_filenum"] = None
		required_info.remove("block_filenum")
		if not required_info: # no more info required
			return block_arr

	if "block_pos" in required_info:
		# this value gets stored in the tx_metadata dirs to enable quick
		# retrieval from the blockchain files later on. only init here - update
		# later
		block_arr["block_pos"] = None
		required_info.remove("block_pos")
		if not required_info: # no more info required
			return block_arr

	# initialize the orphan status - not possible to determine this yet
	if "orphan_status" in required_info:
		block_arr["is_orphan"] = None
		required_info.remove("orphan_status")
		if not required_info: # no more info required
			return block_arr

	# initialize the block height - not possible to determine this yet
	if "block_height" in required_info:
		block_arr["block_height"] = None
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

	# it is slightly faster not to process the target unless it is requested
	if (
		("target" in required_info) or
		("difficulty" in required_info)
	):
		target = target_bin2hex(bits) # as decimal int

	if "target" in required_info:
		block_arr["target"] = target
		required_info.remove("target")
		if not required_info: # no more info required
			return block_arr

	if "target_validation_status" in required_info:
		# 'None' indicates that we have not tried to verify that the target is
		# correct given the previous target and time taken to mine the previous
		# 2016 blocks
		block_arr["target_validation_status"] = None
		required_info.remove("target_validation_status")
		if not required_info: # no more info required
			return block_arr

	if "difficulty" in required_info:
		block_arr["difficulty"] = bits2difficulty(bits)
		required_info.remove("difficulty")
		if not required_info: # no more info required
			return block_arr
	
	if "difficulty_validation_status" in required_info:
		# 'None' indicates that we have not tried to verify that difficulty > 1
		block_arr["difficulty_validation_status"] = None
		required_info.remove("difficulty_validation_status")
		if not required_info: # no more info required
			return block_arr

	if "block_hash_validation_status" in required_info:
		# 'None' indicates that we have not tried to verify the block hash
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
			block, pos, required_info, i, options
		)
		if "tx_timestamp" in required_info:
			block_arr["tx"][i]["timestamp"] = timestamp

		if not required_info: # no more info required
			return block_arr
		pos += length

	if "merkle_root_validation_status" in required_info:
		# 'None' indicates that we have not tried to verify
		block_arr["merkle_root_validation_status"] = None
		required_info.remove("merkle_root_validation_status")
		if not required_info: # no more info required
			return block_arr

	if "coinbase_funds_validation_status" in required_info:
		# 'None' indicates that we have not tried to verify
		block_arr["coinbase_funds_validation_status"] = None
		required_info.remove("coinbase_funds_validation_status")
		if not required_info: # no more info required
			return block_arr

	if "block_size" in required_info:
		block_arr["size"] = pos

	if "block_size_validation_status" in required_info:
		# 'None' indicates that we have not tried to verify
		block_arr["block_size_validation_status"] = None
		required_info.remove("block_size_validation_status")
		if not required_info: # no more info required
			return block_arr

	if "block_bytes" in required_info:
		block_arr["bytes"] = block

	if len(block) != pos:
		lang_grunt.die(
			"the full block could not be parsed. block length: %s, position: %s"
			% (len(block), pos)
		)
	# we only get here if the user has requested all the data from the block
	return block_arr

def tx_bin2dict(block, pos, required_info, tx_num, options):
	"""
	extract the specified transaction info from the block into a dictionary and
	return as soon as it is all available
	"""
	tx = {} # init
	init_pos = pos

	# the first transaction is always coinbase (mined)
	is_coinbase = True if (tx_num == 0) else False

	if "tx_pos_in_block" in required_info:
		# this value gets stored in the tx_metadata dirs to enable quick
		# retrieval from the blockchain files later on
		tx["pos"] = init_pos

	if "tx_version" in required_info:
		tx["version"] = bin2int(little_endian(block[pos: pos + 4]))
	pos += 4

	(num_inputs, length) = decode_variable_length_int(block[pos: pos + 9])
	if "num_tx_inputs" in required_info:
		tx["num_inputs"] = num_inputs
	pos += length

	if "txins_exist_validation_status" in required_info:
		tx["txins_exist_validation_status"] = None

	# if the user wants to retrieve the txin funds, txin address or previous tx
	# data and this is not a coinbase tx then we need to get the previous tx as
	# a dict using the txin hash and txin index
	if (
		(not is_coinbase) and (
			("prev_tx_metadata" in required_info) or
			("prev_tx" in required_info) or
			("txin_funds" in required_info) or
			("txin_address" in required_info)
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
			("txin_hash" in required_info)
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

		if (
			("txin_script" in required_info) or
			("txin_script_list" in required_info) or
			("txin_parsed_script" in required_info)
		):
			input_script = block[pos: pos + txin_script_length]
		pos += txin_script_length

		if "txin_script" in required_info:
			tx["input"][j]["script"] = input_script

		if (
			("txin_parsed_script" in required_info) or
			("txin_script_list" in required_info)
		):
			# convert string of bytes to list of bytes
			script_elements = script_bin2list(input_script)
			
		if "txin_script_list" in required_info:
			tx["input"][j]["script_list"] = script_elements

		if "txin_parsed_script" in required_info:
			# convert list of bytes to human readable string
			tx["input"][j]["parsed_script"] = script_list2human_str(
				script_elements
			)
		if "txin_spend_from_non_orphan_validation_status" in required_info:
			tx["input"][j]["spend_from_non_orphan_validation_status"] = None

		if "txin_checksig_validation_status" in required_info:
			tx["input"][j]["checksig_validation_status"] = None

		if "txin_mature_coinbase_spend_validation_status" in required_info:
			tx["input"][j]["mature_coinbase_spend_validation_status"] = None

		# if the user wants to retrieve the txin funds, txin address or previous
		# tx data then we need to get the previous tx as a dict using the txin
		# hash and txin index
		if get_previous_tx:
			prev_tx_metadata_csv = get_tx_metadata_csv(bin2hex(txin_hash))
			if prev_tx_metadata_csv is None: 
				prev_tx_metadata = None
				prev_tx = None
			else:
				prev_tx_metadata = tx_metadata_csv2dict(prev_tx_metadata_csv)
				prev_tx_bin = extract_tx(options, txin_hash, prev_tx_metadata)
				(prev_tx, _) = tx_bin2dict(
					prev_tx_bin, 0, all_txout_info + ["tx_hash"], tx_num,
					options
				)
		if "prev_tx_metadata" in required_info:
			if get_previous_tx:
				tx["input"][j]["prev_tx_metadata"] = prev_tx_metadata
			else:
				tx["input"][j]["prev_tx_metadata"] = None

		if "prev_tx" in required_info:
			if get_previous_tx:
				tx["input"][j]["prev_tx"] = prev_tx
			else:
				tx["input"][j]["prev_tx"] = None

		if "txin_funds" in required_info:
			if (
				get_previous_tx and
				(prev_tx is not None)
			):
				tx["input"][j]["funds"] = prev_tx["output"][txin_index] \
				["funds"]
			else:
				tx["input"][j]["funds"] = None

		# get the txin address. note that this should not be trusted until the
		# tx has been verified
		if "txin_address" in required_info:
			if (
				get_previous_tx and
				(prev_tx is not None)
			):
				tx["input"][j]["address"] = prev_tx["output"][txin_index] \
				["address"]
			else:
				tx["input"][j]["address"] = None

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
			("txout_address" in required_info) or
			("txout_parsed_script" in required_info) or
			("txout_script_format_validation_status" in required_info)
		):
			output_script = block[pos: pos + txout_script_length]
		pos += txout_script_length	

		if "txout_script" in required_info:
			tx["output"][k]["script"] = output_script

		if (
			("txout_parsed_script" in required_info) or
			("txout_script_list" in required_info) or
			("txout_script_format_validation_status" in required_info)
		):
			# convert string of bytes to list of bytes
			script_elements = script_bin2list(output_script)

		if "txout_script_list" in required_info:
			tx["output"][k]["script_list"] = script_elements

		if "txout_parsed_script" in required_info:
			# convert list of bytes to human readable string
			tx["output"][k]["parsed_script"] = script_list2human_str(
				script_elements
			)
		if "txout_script_format_validation_status" in required_info:
			tx["output"][k]["script_format_validation_status"] = None

		if "txout_address" in required_info:
			# return btc address or None
			tx["output"][k]["address"] = script2address(output_script)

		if not len(tx["output"][k]):
			del tx["output"][k]

	if not len(tx["output"]):
		del tx["output"]

	if "tx_funds_balance_validation_status" in required_info:
		# 'None' indicates that we have not tried to verify
		tx["funds_balance_validation_status"] = None

	if "tx_lock_time_validation_status" in required_info:
		# 'None' indicates that we have not tried to verify
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

	for tx_arr in block_arr["tx"].values():
		tx_errors = validate_tx_elements_type_len(tx_arr)
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

def validate_tx_elements_type_len(tx_arr, bool_result = False):
	"""
	validate a transaction's type and length. transaction must be input as a
	dict.
	"""
	if not bool_result:
		errors = []

	if "version" in tx_arr:
		if not isinstance(tx_arr["version"], (int, long)):
			if bool_result:
				return False
			errors.append(
				"Error: transaction version must be an int. %s supplied."
				% type(tx_arr["version"])
			)
	else:
		errors.append("Error: element version must exist in transaction.")

	if "num_tx_inputs" in tx_arr:
		if tx_arr["num_tx_inputs"] != len(tx_arr["input"]):
			if bool_result:
				return False
			errors.append(
				"Error: num_tx_inputs is different to the actual number of"
				" transaction inputs."
			)
	# else: this element is not mandatory since it can be derived by counting
	# the transaction inputs

	for tx_input in tx_arr["input"].values(): # loop through all inputs

		if "verification_attempted" in tx_input:
			if not isinstance(tx_input["verification_attempted"], bool):
				if bool_result:
					return False
				errors.append(
					"Error: input element verification_attempted must be a"
					" bool. %s supplied."
					% type(tx_input["verification_attempted"])
				)
		# else: this element is totally optional

		if "verification_succeeded" in tx_input:
			if not isinstance(tx_input["verification_succeeded"], bool):
				if bool_result:
					return False
				errors.append(
					"Error: input element verification_succeeded must be a"
					" bool. %s supplied."
					% type(tx_input["verification_succeeded"])
				)
		# else: this element is totally optional

		if "funds" in tx_input:
			if not isinstance(tx_input["funds"], (int, long)):
				if bool_result:
					return False
				errors.append(
					"Error: input funds must be an int. %s supplied."
					% type(tx_input["funds"])
				)
			elif tx_input["funds"] < 0:
				if bool_result:
					return False
				errors.append("Error: input funds must be a positive int.")
		# else: this element is totally optional

		if "hash" in tx_input:
			if not isinstance(tx_input["hash"], str):
				if bool_result:
					return False
				errors.append(
					"Error: input hash must be a string. %s supplied."
					% type(tx_input["hash"])
				)
			elif len(tx_input["hash"]) != 32:
				if bool_result:
					return False
				errors.append("Error: input hash must be 32 bytes long.")
		else:
			errors.append(
				"Error: hash element must exist in transaction input."
			)

		if "index" in tx_input:
			if not isinstance(tx_input["index"], (int, long)):
				if bool_result:
					return False
				errors.append(
					"Error: input index must be an int. %s supplied."
					% type(tx_input["index"])
				)
			elif tx_input["index"] < 0:
				if bool_result:
					return False
				errors.append("Error: input index must be a positive int.")
		else:
			errors.append(
				"Error: index element must exist in transaction input."
			)

		if "script_length" in tx_input:
			script_length_ok = True
			if not isinstance(tx_input["script_length"], (int, long)):
				if bool_result:
					return False
				errors.append(
					"Error: input script_length must be an int. %s supplied."
					% type(tx_input["script_length"])
				)
				script_length_ok = False
			elif tx_input["script_length"] < 0:
				if bool_result:
					return False
				errors.append(
					"Error: input script_length must be a positive int."
				)
				script_length_ok = False
		else:
			script_length_ok = False
			# this element is not mandatory since it can be derived by counting
			# the bytes in the script element

		if "script" in tx_input:
			if not isinstance(tx_input["script"], str):
				if bool_result:
					return False
				errors.append(
					"Error: input script must be a string. %s supplied."
					% type(tx_input["script"])
				)
			elif (
				script_length_ok and
				(len(tx_input["script"]) != tx_input["script_length"])
			):
				if bool_result:
					return False
				errors.append(
					"Error: input script must be %s bytes long, but it is %s."
					% (tx_input["script_length"], len(tx_input["script"]))
				)
		else:
			errors.append(
				"Error: script element must exist in transaction input."
			)

		if "address" in tx_input:
			if not isinstance(tx_input["address"], str):
				if bool_result:
					return False
				errors.append(
					"Error: input address must be a string. %s supplied."
					% type(tx_input["address"])
				)
			elif len(tx_input["address"]) != 34:
				if bool_result:
					return False
				errors.append(
					"Error: input address must be 34 characters long."
				)
		# else: this element is totally optional

		if "sequence_num" in tx_input:
			if not isinstance(tx_input["sequence_num"], (int, long)):
				if bool_result:
					return False
				errors.append(
					"Error: input sequence_num must be an int. %s supplied."
					% type(tx_input["sequence_num"])
				)
			elif tx_input["sequence_num"] < 0:
				if bool_result:
					return False
				errors.append(
					"Error: input sequence_num must be a positive int."
				)
		else:
			errors.append(
				"Error: sequence_num element must exist in transaction input."
			)

	if "num_tx_outputs" in tx_arr:
		if tx_arr["num_tx_outputs"] != len(tx_arr["output"]):
			if bool_result:
				return False
			errors.append(
				"Error: num_tx_outputs is different to the actual number of"
				" transaction outputs."
			)
	# else: this element is not mandatory since it can be derived by counting
	# the transaction outputs

	for tx_output in tx_arr["output"].values(): # loop through all outputs

		if "funds" in tx_output:
			if not isinstance(tx_output["funds"], (int, long)):
				if bool_result:
					return False
				errors.append(
					"Error: output funds must be an int. %s supplied."
					% type(tx_output["funds"])
				)
			elif tx_output["funds"] < 0:
				if bool_result:
					return False
				errors.append("Error: output funds must be a positive int.")
		else:
			errors.append(
				"Error: funds element must exist in transaction output."
			)

		if "script_length" in tx_output:
			script_length_ok = True
			if not isinstance(tx_output["script_length"], (int, long)):
				if bool_result:
					return False
				errors.append(
					"Error: output script_length must be an int. %s supplied."
					% type(tx_output["script_length"])
				)
				script_length_ok = False
			elif tx_output["script_length"] < 0:
				if bool_result:
					return False
				errors.append(
					"Error: output script_length must be a positive int."
				)
				script_length_ok = False
		else:
			script_length_ok = False
			# this element is not mandatory since it can be derived by counting
			# the bytes in the script element

		if "script" in tx_output:
			if not isinstance(tx_output["script"], str):
				if bool_result:
					return False
				errors.append(
					"Error: output script must be a string. %s supplied."
					% type(tx_output["script"])
				)
			elif (
				script_length_ok and
				(len(tx_output["script"]) != tx_output["script_length"])
			):
				if bool_result:
					return False
				errors.append(
					"Error: output script must be %s bytes long, but it is %s."
					% (tx_output["script_length"], len(tx_output["script"]))
				)
		else:
			errors.append(
				"Error: script element must exist in transaction output."
			)

		if "address" in tx_output:
			if not isinstance(tx_output["address"], str):
				if bool_result:
					return False
				errors.append(
					"Error: output address must be a string. %s supplied."
					% type(tx_output["address"])
				)
			elif len(tx_output["address"]) != 34:
				if bool_result:
					return False
				errors.append(
					"Error: output address must be 34 characters long."
				)
		# else: this element is totally optional

	if "lock_time" in tx_arr:
		if not isinstance(tx_arr["lock_time"], (int, long)):
			if bool_result:
				return False
			errors.append(
				"Error: transaction lock_time must be an int. %s supplied."
				% type(tx_arr["lock_time"])
			)
		elif tx_arr["lock_time"] < 0:
			if bool_result:
				return False
			errors.append(
				"Error: transaction lock_time must be a positive int."
			)

	if "hash" in tx_arr:
		if not isinstance(tx_arr["hash"], str):
			if bool_result:
				return False
			errors.append(
				"Error: transaction hash must be a string. %s supplied."
				% type(tx_arr["hash"])
			)
		elif len(tx_arr["hash"]) != 32:
			if bool_result:
				return False
			errors.append("Error: transaction hash must be a 32 bytes long.")
	# else: this element is not mandatory since it can be derived by hashing all
	# transaction bytes

	if "size" in tx_arr:
		if not isinstance(tx_arr["size"], (int, long)):
			if bool_result:
				return False
			errors.append(
				"Error: transaction size must be an int. %s supplied."
				% type(tx_arr["size"])
			)
		elif tx_arr["size"] < 0:
			if bool_result:
				return False
			errors.append("Error: transaction size must be a positive int.")
	# else: this element is not mandatory since it can be derived by counting
	# the bytes in the whole transaction

	if (
		not errors and
		bool_result
	):
		errors = True # block is valid
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
		parsed_block["tx"][tx_num] = human_readable_tx(tx, tx_num)

	return parsed_block

def human_readable_tx(tx, tx_num):
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
		(parsed_tx, _) = tx_bin2dict(tx, 0, output_info, tx_num)

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
		if "prev_tx" in txin:
			del parsed_tx["input"][txin_num]["prev_tx"]

	for (txout_num, txout) in parsed_tx["output"].items():
		if "script" in txout:
			del parsed_tx["output"][txout_num]["script"]
		if "script_list" in txout:
			del parsed_tx["output"][txout_num]["script_list"]

	return parsed_tx

def gather_transaction_data(tx):
	"""
	fetch the following data from the blockchain that is required to construct
	this transaction:
	- the available funds
	- all previous hashes
	- all previous indexes
	- all previous output scripts
	"""
	from_addresses = [] # init
	for input_num in tx["input"]:
		from_addresses.append(tx["input"][input_num]["address"])

	get_full_blocks(options, sanitized = False)
	

def create_transaction(tx):
	"""
	create a transaction with as many inputs and outputs as required. no
	multisig.
	for each transaction input:
	- previous hash
	- previous index
	- script
	
	for each transaction output:
	- quantity
	- script
	"""
	

"""def create_transaction(prev_tx_hash, prev_txout_index, prev_tx_ecdsa_private_key, to_address, btc):
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

def get_missing_txin_data(block, options):
	"""
	tx inputs reference previous tx outputs. if any txin addresses are unknonwn
	or unverified (if that is requied by the options) then get the details
	necessary to go fetch them - ie the previous tx hash and index.
	block input must be a dict.
	"""
	# assume we have been given a block in dict type
	parsed_block = block
	block_height = block["block_height"]
	block_hash = block["block_hash"]

	missing_data = {} # init

	# note that the block range specified via STARTBLOCKHASH and ENDBLOCKHASH
	# must be converted to STARTBLOCKNUM and ENDBLOCKNUM using function
	# options_grunt.convert_range_options() before this point

	# if the options specify this entire block then then all txs are relevant
	if whole_block_match(options, block_hash, block_height):
		relevant_tx = True

	for tx_num in parsed_block["tx"]:
		tx = parsed_block["tx"][tx_num]

		if (
			(options.TXHASHES is not None) and
			[txhash for txhash in options.TXHASHES if txhash == tx["hash"]]
		):
			relevant_tx = True

		for input_num in tx["input"]:
			txin = tx["input"][input_num]
			prev_txout_hash = txin["hash"]

			# if we already have the input address the skip this txin
			if (
				"address" in txin and
				(txin["address"] is not None)
			):
					continue

			if "hash" in txin:
				# if this is a coinbase tx then skip this txin since we already
				# know everything there is to know about this tx
				if prev_txout_hash == blank_hash:
					continue

				missing_data[prev_txout_hash] = txin["index"]

	return missing_data

def calculate_block_hash(block_bytes):
	"""calculate the block hash from the first 80 bytes of the block"""
	return little_endian(sha256(sha256(block_bytes[0: 80])))

def should_validate_block(options, parsed_block, latest_validated_block_data):
	"""
	check if this block should be validated. there are two basic criteria:
	- options.validate is set and,
	- this block has not yet been validated
	"""
	if options.validate is None:
		return False
	
	if latest_validated_block_data is None:
		return True

	(latest_validated_block_filenum, latest_validated_block_pos) = \
	latest_validated_block_data

	# if this block has not yet been validated...
	if (
		(parsed_block["block_filenum"] >= latest_validated_block_filenum) and
		(parsed_block["block_pos"] > latest_validated_block_pos)
	):
		return True

	return False

def validate_block(parsed_block, target_data, options):
	"""
	validate everything except the orphan status of the block (this way we can
	validate before waiting coinbase_maturity blocks to check the orphan status)

	the *_validation_status determines the types of validations to perform. see
	the block_header_validation_info variable at the top of this file for the
	full list of possibilities. for this reason, only parsed blocks can be
	passed to this function.

	if the options.explain argument is set then set the *_validation_status
	element values to human readable strings when there is a failure, otherwise
	to True.

	if the options.explain argument is not set then set the *_validation_status
	element values to False when there is a failure otherwise to True.

	based on https://en.bitcoin.it/wiki/Protocol_rules
	"""
	# make sure the block is smaller than the permitted maximum
	if "block_size_validation_status" in parsed_block:
		parsed_block["block_size_validation_status"] = valid_block_size(
			parsed_block, options.explain
		)
	# make sure the transaction hashes form the merkle root when sequentially
	# hashed together
	if "merkle_root_validation_status" in parsed_block:
		parsed_block["merkle_root_validation_status"] = valid_merkle_tree(
			parsed_block, options.explain
		)
	# make sure the target is valid based on previous network hash performance
	if "target_validation_status" in parsed_block:
		parsed_block["target_validation_status"] = valid_target(
			parsed_block, target_data
		)
	# make sure the block hash is below the target
	if "block_hash_validation_status" in parsed_block:
		parsed_block["block_hash_validation_status"] = valid_block_hash(
			parsed_block, options.explain
		)
	# make sure the difficulty is valid	
	if "difficulty_validation_status" in parsed_block:
		parsed_block["difficulty_validation_status"] = valid_difficulty(
			parsed_block, options.explain
		)
	# use this var to keep track of txs that have been spent within this very
	# block. we don't want to mark any txs as spent until we know that the whole
	# block is valid (ie that the funds are permitted to be spent). it is in the
	# format {spendee_hash: [spendee_index, spender_hash,  spender_index]}
	spent_txs = {}

	for (tx_num, tx) in sorted(parsed_block["tx"].items()):
		(parsed_block["tx"][tx_num], spent_txs) = validate_tx(
			tx, tx_num, spent_txs, parsed_block["block_height"], options
		)
	if "coinbase_funds_validation_status" in parsed_block:
		parsed_block["coinbase_funds_validation_status"] = valid_coinbase_funds(
			parsed_block, options.explain
		)
	# now that all validations have been performed, die if anything failed
	invalid_block_elements = valid_block_check(parsed_block)
	if invalid_block_elements is not None:
		if options.FORMAT not in [
			"MULTILINE-JSON", "SINGLE-LINE-JSON", "MULTILINE-XML",
			"SINGLE-LINE-XML"
		]:
			options.FORMAT = "MULTILINE-JSON"

		if options.OUTPUT_TYPE is None:
			options.OUTPUT_TYPE = "BLOCKS"

		block_human_str = get_formatted_data(options, {
			parsed_block["block_hash"]: parsed_block
		})
		lang_grunt.die(
			"Validation error. Elements %s in the following block have been"
			" found to be invalid:\n%s"
			% (
				lang_grunt.list2human_str(invalid_block_elements, "or"),
				block_human_str
			)
		)
	# once we get here we know that the block is perfect, so it is safe to mark
	# off any spent transactions from the unspent txs pool. note that we should
	# not delete these spent txs because we will need them in future to
	# identify txin addresses
	for (tx_num, tx) in parsed_block["tx"].items():
		# coinbase txs don't spend previous txs
		if tx_num == 0:
			continue
		spender_txhash = tx["hash"]
		for (spender_index, spender_txin) in tx["input"].items():
			spendee_txhash = bin2hex(spender_txin["hash"])
			spendee_index = spender_txin["index"]
			mark_spent_tx(
				options, spendee_txhash, spendee_index, spender_txhash,
				spender_index
			)
	return parsed_block

def validate_tx(tx, tx_num, spent_txs, block_height, options):
	"""
	the *_validation_status determines the types of validations to perform. see
	the all_tx_validation_info variable at the top of this file for the full
	list of possibilities. for this reason, only parsed blocks can be passed to
	this function.

	if the options.explain argument is set then set the *_validation_status
	element values to human readable strings when there is a failure, otherwise
	to True.

	if the options.explain argument is not set then set the *_validation_status
	element values to False when there is a failure otherwise to True.

	based on https://en.bitcoin.it/wiki/Protocol_rules
	"""
	txins_exist = False # init
	txouts_exist = False # init

	# make sure the locktime for each transaction is valid
	if "lock_time_validation_status" in tx:
		tx["lock_time_validation_status"] = valid_lock_time(
			tx["lock_time"], options.explain
		)
	# the first transaction is always coinbase (mined)
	is_coinbase = True if (tx_num == 0) else False

	for (txin_num, txin) in sorted(tx["input"].items()):
		txins_exist = True
		spendee_hash = txin["hash"]
		spendee_index = txin["index"]

		if is_coinbase:
			if "coinbase_hash_validation_status" in txin:
				txin["coinbase_hash_validation_status"] = \
				valid_coinbase_hash(spendee_hash, options.explain)

			if "coinbase_index_validation_status" in txin:
				txin["coinbase_index_validation_status"] = \
				valid_coinbase_index(spendee_index, options.explain)

			# no more txin checks required for coinbase transactions
			# merge the results back into the tx return var
			tx["input"][txin_num] = txin
			continue

		# not a coinbase tx from here on...
		spendee_tx_metadata = txin["prev_tx_metadata"]
		prev_tx = txin["prev_tx"]

		# check if the transaction (hash) being spent actually exists
		###csv_data = get_tx_metadata_csv(bin2hex(spendee_hash))
		###status = valid_txin_hash(spendee_hash, csv_data, options.explain)
		status = valid_txin_hash(spendee_hash, prev_tx, options.explain)
		if "hash_validation_status" in txin:
			txin["hash_validation_status"] = status
		if status is not True:
			# merge the results back into the tx return var
			tx["input"][txin_num] = txin
			continue

		# from this point onwards the tx being spent definitely exists.

		#### fetch it as a dict
		###spendee_tx_metadata = tx_metadata_csv2dict(csv_data) # as dict
		###prev_tx_bin = extract_tx(options, spendee_hash, spendee_tx_metadata)
		###(prev_tx, _) = tx_bin2dict(prev_tx_bin, 0, all_txout_info, tx_num)

		# check if the transaction (index) being spent actually exists
		status = valid_txin_index(spendee_index, prev_tx, options.explain)
		if "index_validation_status" in txin:
			txin["index_validation_status"] = status
		if status is not True:
			# merge the results back into the tx return var
			tx["input"][txin_num] = txin
			continue

		# check if the transaction we are spending from has already been
		# spent in an earlier block
		status = valid_tx_spend(
			spendee_tx_metadata, spendee_hash, spendee_index, tx["hash"],
			txin_num, spent_txs, options.explain
		)
		if "single_spend_validation_status" in txin:
			txin["single_spend_validation_status"] = status
		if status is not True:
			# merge the results back into the tx return var
			tx["input"][txin_num] = txin
			continue

		# check if the tx being spent is in an orphan block. this script's
		# validation process halts if any other form of invalid block is
		# encountered, so there is no need to worry about previous double-
		# -spends on the main chain, etc.
		status = valid_spend_from_non_orphan(
			spendee_tx_metadata["is_orphan"], spendee_hash, options.explain
		)
		if "spend_from_non_orphan_validation_status" in txin:
			txin["spend_from_non_orphan_validation_status"] = status
		if status is not True:
			# merge the results back into the tx return var
			tx["input"][txin_num] = txin
			continue

		# check that this txin is allowed to spend the referenced prev_tx
		status = valid_checksig(tx, txin_num, prev_tx, options.explain)
		if "checksig_validation_status" in txin:
			txin["checksig_validation_status"] = status
		if status is not True:
			# merge the results back into the tx return var
			tx["input"][txin_num] = txin
			continue

		# if a coinbase transaction is being spent then make sure it has already
		# reached maturity
		status = valid_mature_coinbase_spend(
			block_height, spendee_tx_metadata, options.explain
		)
		if "mature_coinbase_spend_validation_status" in txin:
			txin["mature_coinbase_spend_validation_status"] = status
		if status is not True:
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
			txins_exist, options.explain
		)
	for (txout_num, txout) in sorted(tx["output"].items()):
		txouts_exist = True
		if "script_format_validation_status" in txout:
			txout["script_format_validation_status"] = valid_script_format(
				txout["script_list"], options.explain
			)
		# merge the results back into the tx return var
		tx["output"][txout_num] = txout

		# end of txouts for-loop

	if "txouts_exist_validation_status" in tx:
		tx["txouts_exist_validation_status"] = valid_txouts_exist(
			txouts_exist, options.explain
		)
	if "funds_balance_validation_status" in tx:
		tx["funds_balance_validation_status"] = valid_tx_balance(
			tx, options.explain
		)
	return (tx, spent_txs)

def valid_block_check(parsed_block):
	"""
	return True if the block is valid, else False. this function is only
	accurate if the parsed_block input argument comes from function
	valid_block().

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

	# if we get here then there were no validation failures in the block
	return None if (invalid_elements == []) else invalid_elements
			
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

def valid_target(block, target_data, explain = False):
	"""
	return True if the block target matches that derived from the block height
	and previous target data. if the block target is not valid then either
	return False if the explain argument is not set, otherwise return a human
	readable string with an explanation of the failure.

	to calculate whether the target is valid we need to look at the current
	target (from the target_data dict within element), which is in the following
	format: target_data[block_height][block_hash] = (timestamp, target)
	"""
	if isinstance(block, dict):
		parsed_block = block
	else:
		parsed_block = block_bin2dict(block, ["difficulty"])

	block_height = parsed_block["block_height"]

	if block_height < 2016:
		if parsed_block["bits"] == initial_bits:
			return True
		else:
			if explain:
				return "the target should be %s, however it is %s." \
				% (bits2target(initial_bits), parsed_block["target"])
			else:
				return False

	# from here onwards we are beyond block height 2016

	# find target data for a block that is within 2016 of the current height
	found_closest = False
	for closest_block_height in target_data:
		# if block height is 2015 then closest == 0, not 2016
		# if block height is 2016 then closest == 2016, not 0
		# if block height is 2017 then closest == 2016, not 0
		if (block_height - closest_block_height) < 2016:
			found_closest = True
			break

	if not found_closest:
		if explain:
			return "could not find any target data within 2016 blocks of %s." \
			% block_height
		else:
			return False

	prev_target_block_height = closest_block_height - 2016

	if prev_target_block_height not in target_data:
		if explain:
			return "could not find previous target data for block %s." \
			% prev_target_block_height
		else:
			return False

	# make sure there is only one block hash for the previous target data
	if len(target_data[prev_target_block_height]) > 1:
		if explain:
			return "there is still an orphan for the previous target data." \
			" hashes: %s.no blockchain fork should last 2016 blocks!" \
			% ", ".join(str(x) for x in target_data[prev_target_block_height])
		else:
			return False

	# if there is more than one block hash for the closest target then validate
	# all of these. if any targets fail then return either False, or an
	# explanation
	(old_target_time, old_target) = target_data[prev_block_height]
	for (block_hash, closest_target_data) in target_data[
		closest_target_data
	].items():
		(closest_target_time, closest_target) = closest_target_data
		calculated_target = new_target(
			old_target, old_target_time, closest_target_time
		)
		if calculated_target != parsed_block["target"]:
			if explain:
				return "the target for block with hash %s and height %s," \
				" should be %s, however it has been calculated as %s." \
				% (
					bin2hex(block_hash), block_height,
					bin2hex(calculated_target), parsed_block["target"]
				)
			else:
				return False

	# if we get here then all targets were correct
	return True

def valid_difficulty(block, explain = False):
	if isinstance(block, dict):
		parsed_block = block
	else:
		parsed_block = block_bin2dict(block, ["difficulty"])

	if parsed_block["difficulty"] >= 1:
		return True
	else:
		if options.explain:
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

	target_int = bits2target(parsed_block["bits"])
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

def manage_target_data(parsed_block, old_target_data):
	"""
	if this block is a multiple of 2016 (includes block 0) then add the
	timestamp for this block height to the target data dict and remove any
	target data that is older than the previous target. otherwise just return
	the old target data.

	when adding to the target data, both the block height and the block hash
	must be stored. this way if the block turns out to be an orphan then we can
	retrieve the non-orphan target data as required.
	"""
	block_height = parsed_block["block_height"]
	if (block_height % 2016) != 0:
		# block height is not a multiple of 2016
		return old_target_data 

	# keep only the previous target if available
	target_data = {}
	prev_target_block_height = block_height - 2016
	if prev_target_block_height in old_target_data:
		target_data[prev_target_block_height] = copy.deepcopy(
			old_target_data[prev_target_block_height]
		)
	# add the new target data to the old target data
	target_data[block_height] = {}
	target_data[block_height][parsed_block["block_hash"]] = (
		parsed_block["timestamp"], parsed_block["target"]
	)
	return target_data

def valid_lock_time(locktime, explain = False):
	if locktime <= int_max:
		return True
	else:
		if explain:
			return "bad lock time - it must be less than %s" % int_max
		else:
			return False

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
		(parsed_prev_tx, _) = tx_bin2dict(prev_tx, ["num_tx_outputs"], 0)

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

	error_text = "doublespend failure. previous transaction with hash %s and"
	" index %s has already been spent by transaction starting with hash %s and"
	" txin-index %s. it cannot be spent again by transaction with hash %s and"
	" txin-index %s."

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
				bin2hex(spendee_hash), spendee_index, spender_txhash,
				spender_txin_index, bin2hex(tx_hash), txin_num
			)
		else:
			return False

	# check if it is a doublespend from this same block
	if (
		(spendee_hash in same_block_spent_txs) and
		(same_block_spent_txs[spendee_hash][0] == spendee_index)
	):
		spender_txhash = spent_txs[spendee_hash][1]
		spender_txin_index = spent_txs[spendee_hash][2]
		if explain:
			return error_text \
			% (
				bin2hex(spendee_hash), spendee_index, spender_txhash,
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
	if is_orphan is None:
		return True
	else:
		if explain:
			return "previous transaction with hash %s occurs in an orphan" \
			" block and therefore cannot be spent." \
			% bin2hex(spendee_hash)
		else:
			return False

def valid_checksig(tx, on_txin_num, prev_tx, explain = False):
	"""
	return True if the checksig for this txin passes. if it fails then either
	return False if the explain argument is not set, otherwise return a human
	readable string with an explanation of the failure.

	https://en.bitcoin.it/wiki/OP_CHECKSIG
	http://bitcoin.stackexchange.com/questions/8500
	"""
	codeseparator_bin = opcode2bin("OP_CODESEPARATOR")

	# check if this txin exists in the tranaction
	if on_txin_num not in tx["input"]:
		if explain:
			return "unable to perform a checksig on txin number %s, as it" \
			" does not exist in the transaction." \
			% on_txin_num
		else:
			return False

	# create a copy of the tx
	wiped_tx = copy.deepcopy(tx)

	# remove superfluous info
	del wiped_tx["bytes"]
	del wiped_tx["hash"]

	# wipe all input scripts
	for txin_num in wiped_tx["input"]:
		wiped_tx["input"][txin_num]["script"] = ""
		wiped_tx["input"][txin_num]["script_length"] = 0
		del wiped_tx["input"][txin_num]["parsed_script"]
		del wiped_tx["input"][txin_num]["script_list"]

	# check if the prev_tx hash matches the hash for this txin
	if tx["input"][on_txin_num]["hash"] != prev_tx["hash"]:
		if explain:
			return "could not find previous transaction with hash %s to spend" \
			" from." \
			% bin2hex(tx["input"][on_txin_num]["hash"])
		else:
			return False

	# if we get here then all the required txout data exists for this txin
	txin = tx["input"][on_txin_num]
	prev_index = txin["index"]
	prev_txout_script_list = prev_tx["output"][prev_index]["script_list"]
	address = prev_tx["output"][prev_index]["address"]

	# extract the pubkey either from the previous txout or this txin
	pubkey = scripts2pubkey(prev_txout_script_list, txin["script_list"])
	if pubkey is None:
		if explain:
			return "could not find the public key in either the txin script" \
			" (%s) or the previous txout script (%s)." \
			% (
				txin["parsed_script"],
				prev_tx["output"][prev_index]["parsed_script"]
			)
		else:
			return False

	# check if the pubkey resolves to the address of the previous txout
	address_from_pubkey = pubkey2address(pubkey)
	if address_from_pubkey != address:
		if explain:
			return "public key %s resolves to address %s, however this txin" \
			" is attempting to spend from a txout with address %s." \
			% (bin2hex(pubkey), address_from_pubkey, address)
		else:
			return False

	# extract the signature from the txin
	signature = scripts2signature(txin["script_list"])
	if signature is None:
		if explain:
			return "could not find the signature in either the txin script" \
			" (%s) or the previous txout script (%s)." \
			% (
				txin["parsed_script"],
				prev_tx["output"][prev_index]["parsed_script"]
			)
		else:
			return False

	# make sure the hash type is 1
	hashtype = bin2int(signature[-1])
	if hashtype != 1:
		if explain:
			return "hashtype %s is not 1. found on the end of signature %s." \
			% (hashtype, bin2hex(signature))
		else:
			return False

	# TODO - support other hashtypes
	hashtype = little_endian(int2bin(1, 4))

	# chop off the last (hash type) byte from the signature
	signature = signature[: -1]

	# create an error for testing
	###signature = signature[: 4] + "z" + signature[5:]

	# create subscript list from last OP_CODESPEERATOR until the end of the
	# script. if there is no OP_CODESPEERATOR then use whole script
	if codeseparator_bin in prev_txout_script_list:
		last_codeseparator = -1 # init
		for (i, data) in enumerate(prev_txout_script_list):
			if data == codeseparator_bin:
				last_codeseparator = i
		prev_txout_subscript_list = prev_txout_script_list[
			last_codeseparator + 1:
		]
	else:
		prev_txout_subscript_list = prev_txout_script_list

	prev_txout_subscript = "".join(prev_txout_subscript_list)

	# the input script must start with OP_PUSHDATA
	if "OP_PUSHDATA" not in bin2opcode(txin["script_list"][0]):
		if explain:
			return "the transaction input script is incorrect - it does not" \
			" start with OP_PUSHDATA: %s." \
			% txin["parsed_script"]
		else:
			return False

	# add the subscript back into the txin and calculate the hash
	wiped_tx["input"][txin_num]["script"] = prev_txout_subscript
	wiped_tx["input"][txin_num]["script_length"] = len(prev_txout_subscript)
	wiped_tx_hash = sha256(sha256("%s%s" % (tx_dict2bin(wiped_tx), hashtype)))

	key = ecdsa_ssl.key()
	key.set_pubkey(pubkey)
	if key.verify(wiped_tx_hash, signature):
		return True
	else:
		if explain:
			return "checksig with signature %s and pubkey %s failed." \
			% (bin2hex(signature), bin2hex(pubkey))
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
	if num_confirmations > coinbase_maturity:
		return True
	else:
		if explain:
			return "it is not permissible to spend coinbase funds until they" \
			" have reached maturity (ie %s confirmations). this transaction" \
			" attempts to spend coinbase funds after only %s confirmations." \
			% (coinbase_maturity, num_confirmations)
		else:
			return False

def valid_coinbase_funds(parsed_block, explain = False):
	"""
	return True if the coinbase tx spends less than or equal to the permitted
	amount. if the coinbase tx spends more than the permitted amount then either
	return False if the explain argument is not set, otherwise return a human
	readable string with an explanation of the failure.

	the permitted amount is calculated as the mining reward plus the sum of all
	txout funds minus the sum of all txin funds
	"""
	for (tx_num, tx) in sorted(parsed_block["tx"].items()):
		if tx_num == 0:
			spendable = sum(txin["funds"] for txin in tx["input"].values())
			continue
		spendable += sum(txout["funds"] for txout in tx["output"].values())
		spendable -= sum(txin["funds"] for txin in tx["input"].values())

	attempted_spend = sum(
		txout["funds"] for txout in parsed_block["tx"][0]["output"].values()
	)
	if attempted_spend <= spendable:
		return True
	else:
		if explain:
			return "this block attempts to spend %s coinbase funds but only" \
			" %s are available to spend" \
			% (attempted_spend, spendable)
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

def valid_tx_balance(tx, explain = False):
	total_txout_funds = sum(txout["funds"] for txout in tx["output"].values())
	total_txin_funds = sum(txin["funds"] for txin in tx["input"].values())
	if total_txout_funds <= total_txin_funds:
		return True
	else:
		if explain:
			return "there are more txout funds (%s) than txin funds (%s) in" \
			" this transaction" \
			% (txout_funds_tx_total, txin_funds_tx_total, tx_num)
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

def target_bin2hex(bits_bytes):
	"""calculate the decimal target given the 'bits' bytes"""
	return int2hex(bits2target(bits_bytes))

def bits2target(bits_bytes):
	"""calculate the decimal target given the 'bits' bytes"""
	exp = bin2int(bits_bytes[: 1]) # exponent is the first byte
	mult = bin2int(bits_bytes[1: ]) # multiplier is all but the first byte
	return mult * (2 ** (8 * (exp - 3)))

def bits2difficulty(bits_bytes):
	"""calculate the decimal difficulty given the target int"""
	return difficulty_1 / float(bits2target(bits_bytes))

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

		for input_num in tx["input"]:

			# no address - irrelevant transaction
			if tx["input"][input_num]["address"] is None:
				continue

			# do not update the balance unless the transaction is verified
			if tx["input"][input_num]["verification_succeeded"] == False:
				continue

			# irrelevant address - skip to next
			if tx["input"][input_num]["address"] not in addresses:
				continue

			# print "- %s btc %s in tx %s" % (tx["input"][input_num]["funds"], tx["input"][input_num]["address"], bin2hex(tx["hash"])) # debug use only

			funds = tx["input"][input_num]["funds"]
			balances[tx["input"][input_num]["address"]] -= funds

		for output_num in tx["output"]:

			# no address - irrelevant transaction
			if tx["output"][output_num]["address"] is None:
				continue

			# irrelevant address - skip to next
			if tx["output"][output_num]["address"] not in addresses:
				continue

			# print "+ %s btc %s in tx %s" % (tx["output"][output_num]["funds"], tx["output"][output_num]["address"], bin2hex(tx["hash"])) # debug use only

			funds = tx["output"][output_num]["funds"]
			balances[tx["output"][output_num]["address"]] += funds

	return balances

def sha256(bytes):
	"""takes binary, performs sha256 hash, returns binary"""
	# .digest() keeps the result in binary, .hexdigest() outputs as hex string
	return hashlib.sha256(bytes).digest()	

def ripemd160(bytes):
	"""takes binary, performs ripemd160 hash, returns binary"""
	res = hashlib.new('ripemd160')
	res.update(bytes)
	return res.digest()

def little_endian(bytes):
	"""
	takes binary, performs little endian (ie reverse the bytes), returns binary
	"""
	return bytes[::-1]

def extract_scripts_from_input(input_str):
	"""take an input string and create a list of the scripts it contains"""

	# literal_eval is safer than eval - elements can only be string, numbers,
	# etc
	input_dict = ast.literal_eval(input_str)

	scripts = []
	for (tx_num, tx_data) in input_dict.items():
		coinbase = True if (tx_data['hash'] == blank_hash) else False
		scripts.append(tx_data['script'])
	return {'coinbase': coinbase, 'scripts': scripts}

def scripts2pubkey(prev_txout_script, txin_script):
	"""
	get the public key from either the previous transaction output script, or
	from the later transaction input script. if the pubkey cannot be found in
	either of these then return None.
	"""
	if isinstance(prev_txout_script, str):
		# assume script is a binary string
		prev_txout_script_list = script_bin2list(prev_txout_script)
	elif isinstance(prev_txout_script, list):
		prev_txout_script_list = prev_txout_script
	else:
		return None

	if isinstance(txin_script, str):
		# assume script is a binary string
		txin_script_list = script_bin2list(txin_script)
	elif isinstance(txin_script, list):
		txin_script_list = txin_script
	else:
		return None

	prev_txout_script_format = extract_script_format(prev_txout_script_list)
	txin_script_format = extract_script_format(txin_script_list)

	# txout: OP_PUSHDATA0(65) <pubkey> OP_CHECKSIG
	if prev_txout_script_format == "pubkey":
		# whereas later transactions were sent to the sha256 hash of a public
		# key (ie an address), early transactions were sent directly to public
		# keys. it is slightly more risky to leave public keys in plain sight
		# for too long, incase supercomputers factorize the private key and
		# steal the funds. this is not a problem for later transactions unless
		# sha256 also falls prey to pre-image extractions.
		pubkey = prev_txout_script_list[1]

	# txin: OP_PUSHDATA0(65) <pubkey> OP_CHECKSIG
	elif txin_script_format == "pubkey":
		pubkey = txin_script_list[1]

	# txin: OP_PUSHDATA0(73) <signature> OP_PUSHDATA0(65) <pubkey>
	elif txin_script_format == "sigpubkey":
		pubkey = txin_script_list[3]
	else:
		pubkey = None

	return pubkey

def scripts2signature(txin_script):
	"""
	get the signature from the later transaction input script. if the signature
	cannot be found then return None.
	"""
	if isinstance(txin_script, str):
		# assume script is a binary string
		txin_script_list = script_bin2list(txin_script)
	elif isinstance(txin_script, list):
		txin_script_list = txin_script
	else:
		return None

	txin_script_format = extract_script_format(txin_script_list)

	# txin: OP_PUSHDATA0(73) <signature> OP_PUSHDATA0(65) <pubkey>
	if txin_script_format in ["sigpubkey", "scriptsig"]:
		return txin_script_list[1]

	return None

def script2address(script):
	"""extract the bitcoin address from the binary script (input or output)"""
	format_type = extract_script_format(script)
	if not format_type:
		return None

	# OP_PUSHDATA0(65) <pubkey> OP_CHECKSIG
	if format_type == "pubkey":
		output_address = pubkey2address(script_bin2list(script)[1])

	# OP_DUP OP_HASH160 OP_PUSHDATA0(20) <hash160> OP_EQUALVERIFY OP_CHECKSIG
	elif format_type == "hash160":
		output_address = hash1602address(script_bin2list(script)[3])

	# OP_PUSHDATA0(73) <signature> OP_PUSHDATA0(65) <pubkey>
	elif format_type == "sigpubkey":
		output_address = pubkey2address(script_bin2list(script)[3])
	else:
		lang_grunt.die("unrecognized format type %s" % format_type)
	return output_address

def extract_script_format(script):
	"""carefully extract the format for the input (binary string) script"""
	recognized_formats = {
		"pubkey": [
			opcode2bin("OP_PUSHDATA0(65)"), "pubkey", opcode2bin("OP_CHECKSIG")
		],
		"hash160": [
			opcode2bin("OP_DUP"), opcode2bin("OP_HASH160"),
			opcode2bin("OP_PUSHDATA0(20)"), "hash160",
			opcode2bin("OP_EQUALVERIFY"), opcode2bin("OP_CHECKSIG")
		],
		"scriptsig": [opcode2bin("OP_PUSHDATA0(71)"), "signature"],
		"sigpubkey": [
			# TODO - should this be 71, not 73?
			opcode2bin("OP_PUSHDATA0(73)"), "signature",
			opcode2bin("OP_PUSHDATA0(65)"), "pubkey"
		]
	}
	# only two input formats recognized - list of binary strings, and binary str
	if isinstance(script, list):
		script_list = script
	else:
		script_list = script_bin2list(script) # explode

	for (format_type, format_opcodes) in recognized_formats.items():

		# try next format
		if len(format_opcodes) != len(script_list):
			continue

		for (format_opcode_el_num, format_opcode) in enumerate(format_opcodes):
			if format_opcode == script_list[format_opcode_el_num]:
				confirmed_format = format_type
			elif (
				(format_opcode_el_num in [1, 3]) and
				(format_opcode == "pubkey") and
				(len(script_list[format_opcode_el_num]) == 65)
			):
				confirmed_format = format_type
			elif (
				(format_opcode_el_num == 3) and
				(format_opcode == "hash160") and
				(len(script_list[format_opcode_el_num]) == 20)
			):
				confirmed_format = format_type
			elif (
				(format_opcode_el_num == 1) and
				(format_opcode == "signature") and
				#(len(script_list[format_opcode_el_num]) == 73)
				(len(script_list[format_opcode_el_num]) == 71)
			):
				confirmed_format = format_type
			else:
				confirmed_format = None # reset
				# break out of inner for-loop and try the next format type
				break

			if format_opcode_el_num == (len(format_opcodes) - 1): # last
				if confirmed_format is not None:
					return format_type

	# could not determine the format type :(
	return None
				
def script_list2human_str(script_elements):
	"""
	take a list of bytes and output a human readable bitcoin script (ie replace
	opcodes and convert bin to hex for pushed data)
	"""
	script_hex_str = ""

	# set to true once the next list element is to be pushed to the stack
	push = False

	for (i, data) in enumerate(script_elements):
		if push:
			script_hex_str += bin2hex(data)
			push = False # reset
		else:
			parsed_opcode = bin2opcode(data)
			script_hex_str += parsed_opcode
			if "OP_PUSHDATA" in parsed_opcode:
				script_hex_str += ("(%s)" % bin2int(data))

				# push the next element onto the stack
				push = True

		script_hex_str += " "

	return script_hex_str.strip()

def script_bin2list(bytes):
	"""
	split the script into elements of a list. input is a string of bytes, output
	is a list of bytes
	"""
	script_list = []
	pos = 0
	while len(bytes[pos:]):
		byte = bytes[pos: pos + 1]
		pos += 1
		parsed_opcode = bin2opcode(byte)
		script_list.append(byte)
		if parsed_opcode == "OP_PUSHDATA0":

			# push this many bytes onto the stack
			push_num_bytes = bin2int(byte)

			if len(bytes[pos:]) < push_num_bytes:
				lang_grunt.die(
					"Error: Cannot push %s bytes onto the stack since there are"
					" not enough characters left in the raw script."
					% push_num_bytes
				)
			script_list.append(bytes[pos: pos + push_num_bytes])
			pos += push_num_bytes

		elif parsed_opcode == "OP_PUSHDATA1":

			# push this many bytes onto the stack
			push_num_bytes = bin2int(bytes[pos: pos + 2])

			pos += 2
			if len(bytes[pos:]) < push_num_bytes:
				lang_grunt.die(
					"Error: Cannot push %s bytes onto the stack since there are"
					" not enough characters left in the raw script."
					% push_num_bytes
				)
			script_list.append(bytes[pos: pos + push_num_bytes])
			pos += push_num_bytes

		elif parsed_opcode == "OP_PUSHDATA2":

			# push this many bytes onto the stack
			push_num_bytes = bin2int(bytes[pos: pos + 4])

			pos += 4
			if len(bytes[pos:]) < push_num_bytes:
				lang_grunt.die(
					"Error: Cannot push %s bytes onto the stack since there are"
					" not enough characters left in the raw script."
					% push_num_bytes
				)
			script_list.append(bytes[pos: pos + push_num_bytes])
			pos += push_num_bytes

		elif parsed_opcode == "OP_PUSHDATA4":

			# push this many bytes onto the stack
			push_num_bytes = bin2int(bytes[pos: pos + 8])

			pos += 8
			if len(bytes[pos:]) < push_num_bytes:
				lang_grunt.die(
					"Error: Cannot push %s bytes onto the stack since there are"
					" not enough characters left in the raw script."
					% push_num_bytes
				)
			script_list.append(bytes[pos: pos + push_num_bytes])
			pos += push_num_bytes

	return script_list

def bin2opcode(code_bin):
	"""
	decode a single byte into the corresponding opcode as per
	https://en.bitcoin.it/wiki/script
	"""
	code = ord(code_bin)
	if code == 0:
		# an empty array of bytes is pushed onto the stack. (this is not a
		# no-op: an item is added to the stack)
		opcode = "OP_FALSE"
	elif code <= 75:
		# the next opcode bytes is data to be pushed onto the stack
		opcode = "OP_PUSHDATA0"
	elif code == 76:
		# the next byte contains the number of bytes to be pushed onto the stack
		opcode = "OP_PUSHDATA1"
	elif code == 77:
		# the next two bytes contain the number of bytes to be pushed onto the
		# stack
		opcode = "OP_PUSHDATA2"
	elif code == 78:
		# the next four bytes contain the number of bytes to be pushed onto the
		# stack
		opcode = "OP_PUSHDATA4"
	elif code == 79:
		# the number -1 is pushed onto the stack
		opcode = "OP_1NEGATE"
	elif code == 81:
		# the number 1 is pushed onto the stack
		opcode = "OP_TRUE"
	elif code == 82:
		# the number 2 is pushed onto the stack
		opcode = "OP_2"
	elif code == 83:
		# the number 3 is pushed onto the stack
		opcode = "OP_3"
	elif code == 84:
		# the number 4 is pushed onto the stack
		opcode = "OP_4"
	elif code == 85:
		# the number 5 is pushed onto the stack
		opcode = "OP_5"
	elif code == 86:
		# the number 6 is pushed onto the stack
		opcode = "OP_6"
	elif code == 87:
		# the number 7 is pushed onto the stack
		opcode = "OP_7"
	elif code == 88:
		# the number 8 is pushed onto the stack
		opcode = "OP_8"
	elif code == 89:
		# the number 9 is pushed onto the stack
		opcode = "OP_9"
	elif code == 90:
		# the number 10 is pushed onto the stack
		opcode = "OP_10"
	elif code == 91:
		# the number 11 is pushed onto the stack
		opcode = "OP_11"
	elif code == 92:
		# the number 12 is pushed onto the stack
		opcode = "OP_12"
	elif code == 93:
		# the number 13 is pushed onto the stack
		opcode = "OP_13"
	elif code == 94:
		# the number 14 is pushed onto the stack
		opcode = "OP_14"
	elif code == 95:
		# the number 15 is pushed onto the stack
		opcode = "OP_15"
	elif code == 96:
		# the number 16 is pushed onto the stack
		opcode = "OP_16"

	# flow control
	elif code == 97:
		# does nothing
		opcode = "OP_NOP"
	elif code == 99:
		# if the top stack value is not 0, the statements are executed. the top
		# stack value is removed.
		opcode = "OP_IF"
	elif code == 100:
		# if the top stack value is 0, the statements are executed. the top
		# stack value is removed.
		opcode = "OP_NOTIF"
	elif code == 103:
		# if the preceding OP_IF or OP_NOTIF or OP_ELSE was not executed then
		# these statements are and if the preceding OP_IF or OP_NOTIF or OP_ELSE
		# was executed then these statements are not.
		opcode = "OP_ELSE"
	elif code == 104:
		# ends an if/else block. All blocks must end, or the transaction is
		# invalid. An OP_ENDIF without OP_IF earlier is also invalid.
		opcode = "OP_ENDIF"
	elif code == 105:
		# marks transaction as invalid if top stack value is not true.
		opcode = "OP_VERIFY"
	elif code == 106:
		# marks transaction as invalid
		opcode = "OP_RETURN"

	# stack
	elif code == 107:
		# put the input onto the top of the alt stack. remove it from the main
		# stack
		opcode = "OP_TOALTSTACK"
	elif code == 108:
		# put the input onto the top of the main stack. remove it from the alt
		# stack
		opcode = "OP_FROMALTSTACK"
	elif code == 115:
		# if the top stack value is not 0, duplicate it
		opcode = "OP_IFDUP"
	elif code == 116:
		# puts the number of stack items onto the stack
		opcode = "OP_DEPTH"
	elif code == 117:
		# removes the top stack item
		opcode = "OP_DROP"
	elif code == 118:
		# duplicates the top stack item
		opcode = "OP_DUP"
	elif code == 119:
		# removes the second-to-top stack item
		opcode = "OP_NIP"
	elif code == 120:
		# copies the second-to-top stack item to the top
		opcode = "OP_OVER"
	elif code == 121:
		# the item n back in the stack is copied to the top
		opcode = "OP_PICK"
	elif code == 122:
		# the item n back in the stack is moved to the top
		opcode = "OP_ROLL"
	elif code == 123:
		# the top three items on the stack are rotated to the left
		opcode = "OP_ROT"
	elif code == 124:
		# the top two items on the stack are swapped
		opcode = "OP_SWAP"
	elif code == 125:
		# the item at the top of the stack is copied and inserted before the
		# second-to-top item
		opcode = "OP_TUCK"
	elif code == 109:
		# removes the top two stack items
		opcode = "OP_2DROP"
	elif code == 110:
		# duplicates the top two stack items
		opcode = "OP_2DUP"
	elif code == 111:
		# duplicates the top three stack items
		opcode = "OP_3DUP"
	elif code == 112:
		# copies the pair of items two spaces back in the stack to the front
		opcode = "OP_2OVER"
	elif code == 113:
		# the fifth and sixth items back are moved to the top of the stack
		opcode = "OP_2ROT"
	elif code == 114:
		# swaps the top two pairs of items
		opcode = "OP_2SWAP"

	# splice
	elif code == 126:
		# concatenates two strings. disabled
		opcode = "OP_CAT"
	elif code == 127:
		# returns a section of a string. disabled
		opcode = "OP_SUBSTR"
	elif code == 128:
		# keeps only characters left of the specified point in a string.
		# disabled
		opcode = "OP_LEFT"
	elif code == 129:
		# keeps only characters right of the specified point in a string.
		# disabled
		opcode = "OP_RIGHT"
	elif code == 130:
		# returns the length of the input string
		opcode = "OP_SIZE"

	# bitwise logic
	elif code == 131:
		# flips all of the bits in the input. disabled
		opcode = "OP_INVERT"
	elif code == 132:
		# boolean and between each bit in the inputs. disabled
		opcode = "OP_AND"
	elif code == 133:
		# boolean or between each bit in the inputs. disabled
		opcode = "OP_OR"
	elif code == 134:
		# boolean exclusive or between each bit in the inputs. disabled
		opcode = "OP_XOR"
	elif code == 135:
		# returns 1 if the inputs are exactly equal, 0 otherwise
		opcode = "OP_EQUAL"
	elif code == 136:
		# same as OP_EQUAL, but runs OP_VERIFY afterward
		opcode = "OP_EQUALVERIFY"

	# arithmetic
	elif code == 139:
		# 1 is added to the input
		opcode = "OP_1ADD"
	elif code == 140:
		# 1 is subtracted from the input
		opcode = "OP_1SUB"
	elif code == 141:
		# the input is multiplied by 2. disabled
		opcode = "OP_2MUL"
	elif code == 142:
		# the input is divided by 2. disabled
		opcode = "OP_2DIV"
	elif code == 143:
		# the sign of the input is flipped
		opcode = "OP_NEGATE"
	elif code == 144:
		# the input is made positive
		opcode = "OP_ABS"
	elif code == 145:
		# if the input is 0 or 1, it is flipped. Otherwise the output will be 0
		opcode = "OP_NOT"
	elif code == 146:
		# returns 0 if the input is 0. 1 otherwise
		opcode = "OP_0NOTEQUAL"
	elif code == 147:
		# a is added to b
		opcode = "OP_ADD"
	elif code == 148:
		# b is subtracted from a
		opcode = "OP_SUB"
	elif code == 149:
		# a is multiplied by b. disabled
		opcode = "OP_MUL"
	elif code == 150:
		# a is divided by b. disabled
		opcode = "OP_DIV"
	elif code == 151:
		# returns the remainder after dividing a by b. disabled
		opcode = "OP_MOD"
	elif code == 152:
		# shifts a left b bits, preserving sign. disabled
		opcode = "OP_LSHIFT"
	elif code == 153:
		# shifts a right b bits, preserving sign. disabled
		opcode = "OP_RSHIFT"
	elif code == 154:
		# if both a and b are not 0, the output is 1. Otherwise 0
		opcode = "OP_BOOLAND"
	elif code == 155:
		# if a or b is not 0, the output is 1. Otherwise 0
		opcode = "OP_BOOLOR"
	elif code == 156:
		# returns 1 if the numbers are equal, 0 otherwise
		opcode = "OP_NUMEQUAL"
	elif code == 157:
		# same as OP_NUMEQUAL, but runs OP_VERIFY afterward
		opcode = "OP_NUMEQUALVERIFY"
	elif code == 158:
		# returns 1 if the numbers are not equal, 0 otherwise
		opcode = "OP_NUMNOTEQUAL"
	elif code == 159:
		# returns 1 if a is less than b, 0 otherwise
		opcode = "OP_LESSTHAN"
	elif code == 160:
		# returns 1 if a is greater than b, 0 otherwise
		opcode = "OP_GREATERTHAN"
	elif code == 161:
		# returns 1 if a is less than or equal to b, 0 otherwise
		opcode = "OP_LESSTHANOREQUAL"
	elif code == 162:
		# returns 1 if a is greater than or equal to b, 0 otherwise
		opcode = "OP_GREATERTHANOREQUAL"
	elif code == 163:
		# returns the smaller of a and b
		opcode = "OP_MIN"
	elif code == 164:
		# returns the larger of a and b
		opcode = "OP_MAX"
	elif code == 165:
		# returns 1 if x is within the specified range (left-inclusive), else 0
		opcode = "OP_WITHIN"

	# crypto
	elif code == 166:
		# the input is hashed using RIPEMD-160
		opcode = "OP_RIPEMD160"
	elif code == 167:
		# the input is hashed using SHA-1
		opcode = "OP_SHA1"
	elif code == 168:
		# the input is hashed using SHA-256
		opcode = "OP_SHA256"
	elif code == 169:
		# the input is hashed twice: first with SHA-256 and then with RIPEMD-160
		opcode = "OP_HASH160"
	elif code == 170:
		# the input is hashed two times with SHA-256
		opcode = "OP_HASH256"
	elif code == 171:
		# only match signatures after the latest OP_CODESEPARATOR
		opcode = "OP_CODESEPARATOR"
	elif code == 172:
		# hash all transaction outputs, inputs, and script. return 1 if valid
		opcode = "OP_CHECKSIG"
	elif code == 173:
		# same as OP_CHECKSIG, but OP_VERIFY is executed afterward
		opcode = "OP_CHECKSIGVERIFY"
	elif code == 174:
		# execute OP_CHECKSIG for each signature and public key pair
		opcode = "OP_CHECKMULTISIG"
	elif code == 175:
		# same as OP_CHECKMULTISIG, but OP_VERIFY is executed afterward
		opcode = "OP_CHECKMULTISIGVERIFY"

	# pseudo-words
	elif code == 253:
		# represents a public key hashed with OP_HASH160
		opcode = "OP_PUBKEYHASH"
	elif code == 254:
		# represents a public key compatible with OP_CHECKSIG
		opcode = "OP_PUBKEY"
	elif code == 255:
		# any opcode that is not yet assigned
		opcode = "OP_INVALIDOPCODE"

	# reserved words
	elif code == 80:
		# transaction is invalid unless occuring in an unexecuted OP_IF branch
		opcode = "OP_RESERVED"
	elif code == 98:
		# transaction is invalid unless occuring in an unexecuted OP_IF branch
		opcode = "OP_VER"
	elif code == 101:
		# transaction is invalid even when occuring in an unexecuted OP_IF
		# branch
		opcode = "OP_VERIF"
	elif code == 102:
		# transaction is invalid even when occuring in an unexecuted OP_IF
		# branch
		opcode = "OP_VERNOTIF"
	elif code == 137:
		# transaction is invalid unless occuring in an unexecuted OP_IF branch
		opcode = "OP_RESERVED1"
	elif code == 138:
		# transaction is invalid unless occuring in an unexecuted OP_IF branch
		opcode = "OP_RESERVED2"
	elif code == 176:
		# the word is ignored
		opcode = "OP_NOP1"
	elif code == 177:
		# the word is ignored
		opcode = "OP_NOP2"
	elif code == 178:
		# the word is ignored
		opcode = "OP_NOP3"
	elif code == 179:
		# the word is ignored
		opcode = "OP_NOP4"
	elif code == 180:
		# the word is ignored
		opcode = "OP_NOP5"
	elif code == 181:
		# the word is ignored
		opcode = "OP_NOP6"
	elif code == 182:
		# the word is ignored
		opcode = "OP_NOP7"
	elif code == 183:
		# the word is ignored
		opcode = "OP_NOP8"
	elif code == 184:
		# the word is ignored
		opcode = "OP_NOP9"
	elif code == 185:
		# the word is ignored
		opcode = "OP_NOP10"
	elif code == 252:
		# include to keep the parser going, and for easy search in the db later
		opcode = "ERROR"
	else:
		lang_grunt.die("byte %s has no corresponding opcode" % code)
	return opcode

def opcode2bin(opcode):
	"""
	convert an opcode into its corresponding byte. as per
	https://en.bitcoin.it/wiki/script
	"""
	if opcode == "OP_FALSE": # an empty array of bytes is pushed onto the stack
		byteval = 0
	elif "OP_PUSHDATA0" in opcode:
		# the next opcode bytes is data to be pushed onto the stack
		matches = re.search(r"\((\d+)\)", opcode)
		try:
			byteval = int(matches.group(1))
		except AttributeError:
			lang_grunt.die(
				"opcode %s must contain the number of bytes to push onto the"
				" stack"
				% opcode
			)
	elif "OP_PUSHDATA" in opcode:
		lang_grunt.die(
			"converting opcode %s to bytes is unimplemented at this stage"
			% opcode
		) # TODO
	elif opcode == "OP_1NEGATE":
		# the number -1 is pushed onto the stack
		byteval = 79
	elif opcode == "OP_TRUE":
		# the number 1 is pushed onto the stack
		byteval = 81
	elif opcode == "OP_2":
		# the number 2 is pushed onto the stack
		byteval = 82
	elif opcode == "OP_3":
		# the number 3 is pushed onto the stack
		byteval = 83
	elif opcode == "OP_4":
		# the number 4 is pushed onto the stack
		byteval = 84
	elif opcode == "OP_5":
		# the number 5 is pushed onto the stack
		byteval = 85
	elif opcode == "OP_6":
		# the number 6 is pushed onto the stack
		byteval = 86
	elif opcode == "OP_7":
		# the number 7 is pushed onto the stack
		byteval = 87
	elif opcode == "OP_8":
		# the number 8 is pushed onto the stack
		byteval = 88
	elif opcode == "OP_9":
		# the number 9 is pushed onto the stack
		byteval = 89
	elif opcode == "OP_10":
		# the number 10 is pushed onto the stack
		byteval = 90
	elif opcode == "OP_11":
		# the number 11 is pushed onto the stack
		byteval = 91
	elif opcode == "OP_12":
		# the number 12 is pushed onto the stack
		byteval = 92
	elif opcode == "OP_13":
		# the number 13 is pushed onto the stack
		byteval = 93
	elif opcode == "OP_14":
		# the number 14 is pushed onto the stack
		byteval = 94
	elif opcode == "OP_15":
		# the number 15 is pushed onto the stack
		byteval = 95
	elif opcode == "OP_16":
		# the number 16 is pushed onto the stack
		byteval = 96

	# flow control
	elif opcode == "OP_NOP":
		# does nothing
		byteval = 97
	elif opcode == "OP_IF":
		# if top stack value != 0, statements are executed. remove top stack
		# value
		byteval = 99
	elif opcode == "OP_NOTIF":
		# if top stack value == 0, statements are executed. remove top stack
		# value
		byteval = 100
	elif opcode == "OP_ELSE":
		# if the preceding OP was not executed then these statements are. else
		# don't
		byteval = 103
	elif opcode == "OP_ENDIF":
		# ends an if/else block
		byteval = 104
	elif opcode == "OP_VERIFY":
		# top stack value != true: mark transaction as invalid and remove,
		# false: don't
		byteval = 105
	elif opcode == "OP_RETURN":
		# marks transaction as invalid
		byteval = 106
	# stack
	elif opcode == "OP_TOALTSTACK":
		# put the input onto the top of the alt stack. remove it from the main
		# stack
		byteval = 107
	elif opcode == "OP_FROMALTSTACK":
		# put the input onto the top of the main stack. remove it from the alt
		# stack
		byteval = 108
	elif opcode == "OP_IFDUP":
		# if the top stack value is not 0, duplicate it
		byteval = 115
	elif opcode == "OP_DEPTH":
		# puts the number of stack items onto the stack
		byteval = 116
	elif opcode == "OP_DROP":
		# removes the top stack item
		byteval = 117
	elif opcode == "OP_DUP":
		# duplicates the top stack item
		byteval = 118
	elif opcode == "OP_NIP":
		# removes the second-to-top stack item
		byteval = 119
	elif opcode == "OP_OVER":
		# copies the second-to-top stack item to the top
		byteval = 120
	elif opcode == "OP_PICK":
		# the item n back in the stack is copied to the top
		byteval = 121
	elif opcode == "OP_ROLL":
		# the item n back in the stack is moved to the top
		byteval = 122
	elif opcode == "OP_ROT":
		# the top three items on the stack are rotated to the left
		byteval = 123
	elif opcode == "OP_SWAP":
		# the top two items on the stack are swapped
		byteval = 124
	elif opcode == "OP_TUCK":
		# copy item at the top of the stack and insert before the second-to-top
		# item
		byteval = 125
	elif opcode == "OP_2DROP":
		# removes the top two stack items
		byteval = 109
	elif opcode == "OP_2DUP":
		# duplicates the top two stack items
		byteval = 110
	elif opcode == "OP_3DUP":
		# duplicates the top three stack items
		byteval = 111
	elif opcode == "OP_2OVER":
		# copies the pair of items two spaces back in the stack to the front
		byteval = 112
	elif opcode == "OP_2ROT":
		# the fifth and sixth items back are moved to the top of the stack
		byteval = 113
	elif opcode == "OP_2SWAP":
		# swaps the top two pairs of items
		byteval = 114

	# splice
	elif opcode == "OP_CAT":
		# concatenates two strings. disabled
		byteval = 126
	elif opcode == "OP_SUBSTR":
		# returns a section of a string. disabled
		byteval = 127
	elif opcode == "OP_LEFT":
		# keeps only characters left of the specified point in a string.
		# disabled
		byteval = 128
	elif opcode == "OP_RIGHT":
		# keeps only characters right of the specified point in a string.
		# disabled
		byteval = 129
	elif opcode == "OP_SIZE":
		# returns the length of the input string
		byteval = 130

	# bitwise logic
	elif opcode == "OP_INVERT":
		# flips all of the bits in the input. disabled
		byteval = 131
	elif opcode == "OP_AND":
		# boolean and between each bit in the inputs. disabled
		byteval = 132
	elif opcode == "OP_OR":
		# boolean or between each bit in the inputs. disabled
		byteval = 133
	elif opcode == "OP_XOR":
		# boolean exclusive or between each bit in the inputs. disabled
		byteval = 134
	elif opcode == "OP_EQUAL":
		# returns 1 if the inputs are exactly equal, 0 otherwise
		byteval = 135
	elif opcode == "OP_EQUALVERIFY":
		# same as OP_EQUAL, but runs OP_VERIFY afterward
		byteval = 136

	# arithmetic
	elif opcode == "OP_1ADD":
		# 1 is added to the input
		byteval = 139
	elif opcode == "OP_1SUB":
		# 1 is subtracted from the input
		byteval = 140
	elif opcode == "OP_2MUL":
		# the input is multiplied by 2. disabled
		byteval = 141
	elif opcode == "OP_2DIV":
		# the input is divided by 2. disabled
		byteval = 142
	elif opcode == "OP_NEGATE":
		# the sign of the input is flipped
		byteval = 143
	elif opcode == "OP_ABS":
		# the input is made positive
		byteval = 144
	elif opcode == "OP_NOT":
		# if the input is 0 or 1, it is flipped. Otherwise the output will be 0
		byteval = 145
	elif opcode == "OP_0NOTEQUAL":
		# returns 0 if the input is 0. 1 otherwise
		byteval = 146
	elif opcode == "OP_ADD":
		# a is added to b
		byteval = 147
	elif opcode == "OP_SUB":
		# b is subtracted from a
		byteval = 148
	elif opcode == "OP_MUL":
		# a is multiplied by b. disabled
		byteval = 149
	elif opcode == "OP_DIV":
		# a is divided by b. disabled
		byteval = 150
	elif opcode == "OP_MOD":
		# returns the remainder after dividing a by b. disabled
		byteval = 151
	elif opcode == "OP_LSHIFT":
		# shifts a left b bits, preserving sign. disabled
		byteval = 152
	elif opcode == "OP_RSHIFT":
		# shifts a right b bits, preserving sign. disabled
		byteval = 153
	elif opcode == "OP_BOOLAND":
		# if both a and b are not 0, the output is 1. Otherwise 0
		byteval = 154
	elif opcode == "OP_BOOLOR":
		# if a or b is not 0, the output is 1. Otherwise 0
		byteval = 155
	elif opcode == "OP_NUMEQUAL":
		# returns 1 if the numbers are equal, 0 otherwise
		byteval = 156
	elif opcode == "OP_NUMEQUALVERIFY":
		# same as OP_NUMEQUAL, but runs OP_VERIFY afterward
		byteval = 157
	elif opcode == "OP_NUMNOTEQUAL":
		# returns 1 if the numbers are not equal, 0 otherwise
		byteval = 158
	elif opcode == "OP_LESSTHAN":
		# returns 1 if a is less than b, 0 otherwise
		byteval = 159
	elif opcode == "OP_GREATERTHAN":
		# returns 1 if a is greater than b, 0 otherwise
		byteval = 160
	elif opcode == "OP_LESSTHANOREQUAL":
		# returns 1 if a is less than or equal to b, 0 otherwise
		byteval = 161
	elif opcode == "OP_GREATERTHANOREQUAL":
		# returns 1 if a is greater than or equal to b, 0 otherwise
		byteval = 162
	elif opcode == "OP_MIN":
		# returns the smaller of a and b
		byteval = 163
	elif opcode == "OP_MAX":
		# returns the larger of a and b
		byteval = 164
	elif opcode == "OP_WITHIN":
		# returns 1 if x is within the specified range (left-inclusive), else 0
		byteval = 165

	# crypto
	elif opcode == "OP_RIPEMD160":
		# the input is hashed using RIPEMD-160
		byteval = 166
	elif opcode == "OP_SHA1":
		# the input is hashed using SHA-1
		byteval = 167
	elif opcode == "OP_SHA256":
		# the input is hashed using SHA-256
		byteval = 168
	elif opcode == "OP_HASH160":
		# the input is hashed twice: first with SHA-256 and then with RIPEMD-160
		byteval = 169
	elif opcode == "OP_HASH256":
		# the input is hashed two times with SHA-256
		byteval = 170
	elif opcode == "OP_CODESEPARATOR":
		# only match signatures after the latest OP_CODESEPARATOR
		byteval = 171
	elif opcode == "OP_CHECKSIG":
		# hash all transaction outputs, inputs, and script. return 1 if valid
		byteval = 172
	elif opcode == "OP_CHECKSIGVERIFY":
		# same as OP_CHECKSIG, but OP_VERIFY is executed afterward
		byteval = 173
	elif opcode == "OP_CHECKMULTISIG":
		# execute OP_CHECKSIG for each signature and public key pair
		byteval = 174
	elif opcode == "OP_CHECKMULTISIGVERIFY":
		# same as OP_CHECKMULTISIG, but OP_VERIFY is executed afterward
		byteval = 175

	# pseudo-words
	elif opcode == "OP_PUBKEYHASH":
		# represents a public key hashed with OP_HASH160
		byteval = 253
	elif opcode == "OP_PUBKEY":
		# represents a public key compatible with OP_CHECKSIG
		byteval = 254
	elif opcode == "OP_INVALIDOPCODE":
		# any opcode that is not yet assigned
		byteval = 255

	# reserved words
	elif opcode == "OP_RESERVED":
		# transaction is invalid unless occuring in an unexecuted OP_IF branch
		byteval = 80
	elif opcode == "OP_VER":
		# transaction is invalid unless occuring in an unexecuted OP_IF branch
		byteval = 98
	elif opcode == "OP_VERIF":
		# transaction is invalid even when occuring in an unexecuted OP_IF
		# branch
		byteval = 101
	elif opcode == "OP_VERNOTIF":
		# transaction is invalid even when occuring in an unexecuted OP_IF
		# branch
		byteval = 102
	elif opcode == "OP_RESERVED1":
		# transaction is invalid unless occuring in an unexecuted OP_IF branch
		byteval = 137
	elif opcode == "OP_RESERVED2":
		# transaction is invalid unless occuring in an unexecuted OP_IF branch
		byteval = 138
	elif opcode == "OP_NOP1":
		# the word is ignored
		byteval = 176
	elif opcode == "OP_NOP2":
		# the word is ignored
		byteval = 177
	elif opcode == "OP_NOP3":
		# the word is ignored
		byteval = 178
	elif opcode == "OP_NOP4":
		# the word is ignored
		byteval = 179
	elif opcode == "OP_NOP5":
		# the word is ignored
		byteval = 180
	elif opcode == "OP_NOP6":
		# the word is ignored
		byteval = 181
	elif opcode == "OP_NOP7":
		# the word is ignored
		byteval = 182
	elif opcode == "OP_NOP8":
		# the word is ignored
		byteval = 183
	elif opcode == "OP_NOP9":
		# the word is ignored
		byteval = 184
	elif opcode == "OP_NOP10":
		# the word is ignored
		byteval = 185
	elif opcode == "ERROR":
		# include to keep the parser going, and for easy search in the db later
		byteval = 252
	else:
		lang_grunt.die("opcode %s has no corresponding byte" % opcode)
	return hex2bin(int2hex(byteval))

def calculate_merkle_root(merkle_tree_elements):
	"""recursively calculate the merkle root from the list of leaves"""

	if not merkle_tree_elements:
		lang_grunt.die(
			"Error: No arguments passed to function calculate_merkle_root()"
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
			if i % 2: # odd
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

def new_target(old_target, old_target_time, new_target_time):
	"""
	calculate the new target difficulty. we want new blocks to be mined on
	average every 10 minutes.

	http://bitcoin.stackexchange.com/a/2926/2116
	"""
	two_weeks = 14 * 24 * 60 * 60 # in seconds
	half_a_week = 3.5 * 24 * 60 * 60 # in seconds
	time_diff = new_target_time - old_target_time

	# if the difference is greater than 8 weeks, set it to 8 weeks; this
	# prevents the difficulty decreasing by more than a factor of 4
	if time_diff > two_weeks:
		time_diff = two_weeks

	# if the difference is less than half a week, set it to half a week; this
	# prevents the difficulty increasing by more than a factor of 4
	elif time_diff < half_a_week:
		time_diff = half_a_week

	new_target = old_target * time_diff / two_weeks
	max_target = (2 ** (256 - 32)) - 1
	if new_target > max_target:
		new_target = max_target

	return new_target

def pubkey2address(pubkey):
	"""
	take the public ecdsa key (bytes) and output a standard bitcoin address
	(ascii string), following
	https://en.bitcoin.it/wiki/Technical_background_of_Bitcoin_addresses
	"""
	if len(pubkey) != 65:
		lang_grunt.die(
			"the public ecdsa key must be 65 bytes long, but this one is %s"
			" bytes"
			% len(pubkey)
		)
	return hash1602address(ripemd160(sha256(pubkey)))

def address2hash160(address):
	"""
	from https://github.com/gavinandresen/bitcointools/blob/master/base58.py
	"""
	bytes = base58decode(address)
	return bytes[1:21]

def hash1602address(hash160):
	"""
	convert the hash160 output (bytes) to the bitcoin address (ascii string)
	https://en.bitcoin.it/wiki/Technical_background_of_Bitcoin_addresses
	"""
	temp = chr(0) + hash160 # 00010966776006953d5567439e5e39f86a0d273bee
	checksum = sha256(sha256(temp))[:4] # checksum is the first 4 bytes
	hex_address = bin2hex(temp + checksum) # 00010966776006953d5567439e5e39f86a0d273beed61967f6
	decimal_address = int(hex_address, 16) # 25420294593250030202636073700053352635053786165627414518

	return version_symbol('ecdsa_pub_key_hash') + \
	base58encode(decimal_address) # 16UwLL9Risc3QfPqBUvKofHmBQ7wMtjvM

def encode_variable_length_int(value):
	"""encode a value as a variable length integer"""
	if value < 253: # encode as a single byte
		bytes = int2bin(value)
	elif value < 0xffff: # encode as 1 format byte and 2 value bytes
		bytes = "%s%s" % (int2bin(253), int2bin(value))
	elif value < 0xffffffff: # encode as 1 format byte and 4 value bytes
		bytes = "%s%s" % (int2bin(254), int2bin(value))
	elif value < 0xffffffffffffffff: # encode as 1 format byte and 8 value bytes
		bytes = "%s%s" % (int2bin(255), int2bin(value))
	else:
		lang_grunt.die(
			"value %s is too big to be encoded as a variable length integer"
			% value
		)
	return bytes

def decode_variable_length_int(input_bytes):
	"""extract the value of a variable length integer"""
	# TODO test above 253. little endian?
	bytes_in = 0
	first_byte = bin2int(input_bytes[: 1]) # 1 byte binary to decimal int
	bytes = input_bytes[1:] # don't need the first byte anymore
	bytes_in += 1
	if first_byte < 253:
		value = first_byte # use the byte literally
	elif first_byte == 253:
		# read the next two bytes as a 16-bit number
		value = bin2int(bytes[: 2])
		bytes_in += 2
	elif first_byte == 254:
		# read the next four bytes as a 32-bit number
		value = bin2int(bytes[: 4])
		bytes_in += 4
	elif first_byte == 255:
		# read the next eight bytes as a 64-bit number
		value = bin2int(bytes[: 8])
		bytes_in += 8
	else:
		lang_grunt.die(
			"value %s is too big to be decoded as a variable length integer"
			% bin2hex(input_bytes)
		)
	return (value, bytes_in)

def manage_orphans(
	filtered_blocks, hash_table, parsed_block, target_data, mult
):
	"""
	if the hash table grows to mult * coinbase_maturity size then:
	- detect any orphans in the hash table
	- mark off these orphans in the blockchain (filtered_blocks)
	- mark off all certified non-orphans in the blockchain
	- remove any orphans from the target_data dict
	- truncate the hash table back to coinbase_maturity size again
	tune mult according to whatever is faster. this probably
	"""
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
		# mark off any orphans in the blockchain dict
		if orphans:
			filtered_blocks = mark_orphans(filtered_blocks, orphans)

			# remove orphans from the target data
			target_data = remove_target_orphans(target_data, orphans)

		# truncate the hash table to coinbase_maturity hashes length so as not
		# to use up too much ram
		hash_table = truncate_hash_table(hash_table, coinbase_maturity)

	return (filtered_blocks, hash_table, target_data)

def detect_orphans(hash_table, latest_block_hash, threshold_confirmations = 0):
	"""
	look back through the hash_table for orphans. if any are found then	return
	them in a list.

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
	return [block_hash for block_hash in orphans]

def mark_non_orphans(filtered_blocks, orphans, block_height):
	"""
	mark off any non-orphans. these are identified by looping through all blocks
	that are over coinbase_maturity from the current block height and marking
	any blocks that are not in the orphans dict	
	"""
	threshold = block_height - coinbase_maturity
	for block_hash in filtered_blocks:

		# if the block is too new to know for sure then ignore it for now
		if filtered_blocks[block_hash]["block_height"] >= threshold:
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
			save_tx_metadata(options, parsed_block)

	# not really necessary since dicts are immutable. still, it makes the code
	# more readable
	return filtered_blocks

def remove_target_orphans(target_data, orphans):
	"""
	use the orphans list to remove unnecessary target data. the target_data dict
	is in the following format:
	target_data[block_height][block_hash] = (timestamp, target)
	"""
	new_target_data = copy.deepcopy(target_data)
	for (block_height, target_sub_data) in target_data.items():
		for block_hash in target_sub_data:
			if block_hash in orphans:
				del new_target_data[block_height][block_hash]

	return new_target_data

def truncate_hash_table(hash_table, new_len):
	"""
	take a dict of the form {hashstring: block_num} and leave [new_len] upper
	blocks
	"""
	# remember, hash_table is in the format {hash: [block_height, prev_hash]}
	reversed_hash_table = {
		hash_data[0]: hashstring for (hashstring, hash_data) in \
		hash_table.items()
	}
	# only keep [new_len] on the end
	to_remove = sorted(reversed_hash_table)[: -new_len]

	for block_num in to_remove:
		block_hash = reversed_hash_table[block_num]
		del hash_table[block_hash]

	#hash_table = {
	#	hashstring: block_num for (block_num, hashstring) in \
	#	reversed_hash_table.items()
	#}
	return hash_table

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
				return "\n".join(
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
			return "\n".join(
				bin2hex(parsed_block["bytes"]) for parsed_block in data.values()
			)

	if options.OUTPUT_TYPE == "TXS":

		# sort the txs in order of occurence
		data.sort(key = lambda tx: tx["timestamp"])

		if options.FORMAT == "MULTILINE-JSON":
			for tx in data:
				return "\n".join(l.rstrip() for l in json.dumps(
					tx, sort_keys = True, indent = 4
				).splitlines())
				# rstrip removes the trailing space added by the json dump
		if options.FORMAT == "SINGLE-LINE-JSON":
			return "\n".join(
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
			return "\n".join(bin2hex(tx["bytes"]) for tx in data)

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
	encoded = ''
	num = input_num
	try:
		while num >= base:
			mod = num % base
			encoded = base58alphabet[mod] + encoded
			num = num / base
	except TypeError:
		lang_grunt.die(
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
	decoded = '' # init
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

def version_symbol(use, formatt = 'prefix'):
	"""
	retrieve the symbol for the given btc use case use list on page
	https://en.bitcoin.it/wiki/Base58Check_encoding and
	https://en.bitcoin.it/wiki/List_of_address_prefixes
	"""
	if use == 'ecdsa_pub_key_hash':
		symbol = {'decimal': 0, 'prefix': '1'}

	elif use == 'ecdsa_script_hash':
		symbol = {'decimal': 5, 'prefix': '3'}

	elif use == 'compact_pub_key':
		symbol = {'decimal': 21, 'prefix': '4'}

	elif use == 'namecoin_pub_key_hash':
		symbol = {'decimal': 52, 'prefix': 'M'}

	elif use == 'private_key':
		symbol = {'decimal': 128, 'prefix': '5'}

	elif use == 'testnet_pub_key_hash':
		symbol = {'decimal': 111, 'prefix': 'n'}

	elif use == 'testnet_script_hash':
		symbol = {'decimal': 196, 'prefix': '2'}

	else:
		lang_grunt.die('unrecognized bitcoin use [' + use + ']')

	if formatt not in symbol:
		lang_grunt.die('format [' + formatt + '] is not recognized')

	symbol = symbol[formatt] # return decimal or prefix
	return symbol

def get_address_type(address):
	"""
	https://en.bitcoin.it/wiki/List_of_address_prefixes. input is an ascii
	string
	"""
	if len(address) == 130: # hex public key. specific currency is unknown
		return "public key"

	# bitcoin eg 17VZNX1SN5NtKa8UQFxwQbFeFc3iqRYhem
	if address[0] == "1":
		if len(address) != 34:
			lang_grunt.die(
				"address %s looks like a bitcoin public key hash, but does not"
				" have the necessary 34 characters"
				% address
			)
		return "bitcoin pubkey hash"

	# bitcoin eg 3EktnHQD7RiAE6uzMj2ZifT9YgRrkSgzQX
	if address[0] == "3":
		if len(address) != 34:
			lang_grunt.die(
				"address %s looks like a bitcoin script hash, but does not have"
				" the necessary 34 characters"
				% address
			)
		return "bitcoin script hash"

	# litecoin eg LhK2kQwiaAvhjWY799cZvMyYwnQAcxkarr
	if address[0] == "L":
		if len(address) != 34:
			lang_grunt.die(
				"address %s looks like a litecoin public key hash, but does not"
				" have the necessary 34 characters"
				% address
			)
		return "litecoin pubkey hash"

	# namecoin eg NATX6zEUNfxfvgVwz8qVnnw3hLhhYXhgQn
	if address[0] in ["M", "N"]:
		if len(address) != 34:
			lang_grunt.die(
				"address %s looks like a namecoin public key hash, but does not"
				" have the necessary 34 characters"
				% address
			)
		return "namecoin pubkey hash"

	# bitcoin testnet eg mipcBbFg9gMiCh81Kj8tqqdgoZub1ZJRfn
	if address[0] in ["m", "n"]:
		if len(address) != 34:
			lang_grunt.die(
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

def get_full_blockchain_size(blockchain_dir): # all files
	total_size = 0 # accumulator
	for filename in sorted(glob.glob(blockchain_dir + blockname_format)):
		filesize = os.path.getsize(filename)
		total_size += os.path.getsize(filename)
	return total_size

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
	hex_str = hex(intval)[2:]
	if hex_str[-1] == "L":
		hex_str = hex_str[:-1]
	if len(hex_str) % 2:
		hex_str = "0" + hex_str
	return hex_str

def hex2int(hex_str):
	return int(hex_str, 16)

def hex2bin(hex_str):
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

sanitize_globals() # run whenever the module is imported

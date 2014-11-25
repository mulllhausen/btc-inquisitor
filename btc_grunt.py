"""
module containing some general bitcoin-related functions. whenever the word
"orphan" is used in this file it refers to orphan-block, not orphan-transaction.
orphan transactions do not exist in the blockfiles that this script processes.
"""

# TODO - switch from strings to bytearray() for speed (stackoverflow.com/q/16678363/339874)
# TODO - change lots of function arguments to named arguments for clarity
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
import csv

# module to do language-related stuff for this project
import lang_grunt

# module to process the user-specified btc-inquisitor options
import options_grunt

# module globals:

max_block_size = 5 * 1024 * 1024 # 1MB == 1024 * 1024 bytes

# the number of bytes to process in ram at a time.
# set this to the max_block_size + 4 bytes for the magic_network_id seperator +
# 4 bytes which contain the block size 
active_blockchain_num_bytes = max_block_size + 4 + 4

# if the result set grows beyond this then dump the saved blocks to screen
max_saved_blocks = 50

# backup the block height, hash, file number, byte position in the file, size of
# the block, timestamp and bits every aux_blockchain_data_backup_freq blocks.
# note that the timestamp and bits values are only backed up every two weeks
# (2016 blocks) as well as the block before two weeks. set
# aux_blockchain_data_backup_freq to somewhere around 1000 for a good trade-off
# between low disk space usage, non-frequent writes (ie fast parsing) and low
# latency data retrieval.
# TODO - set this dynamically depending on the type of parsing we are doing
aux_blockchain_data_backup_freq = 10

magic_network_id = "f9beb4d9" # gets converted to bin in sanitize_globals() asap
coinbase_maturity = 100 # blocks
satoshis_per_btc = 100000000
base58alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
blank_hash = "0" * 64 # gets converted to bin in sanitize_globals() asap
coinbase_index = 0xffffffff
int_max = 0x7fffffff
initial_bits = "1d00ffff" # gets converted to bin in sanitize_globals() asap
# difficulty_1 = bits2target_int(initial_bits)
difficulty_1 = 0x00000000ffff0000000000000000000000000000000000000000000000000000
max_script_size = 10000 # bytes (bitcoin/src/script/interpreter.cpp)
max_script_element_size = 520 # bytes (bitcoin/src/script/script.h)
max_opcode_count = 200 # nOpCount in bitcoin/src/script/interpreter.cpp
blockname_ls = "blk*[0-9]*.dat"
blockname_regex = "blk%05d.dat"
base_dir = os.path.expanduser("~/.btc-inquisitor/")
tx_meta_dir = "%stx_metadata/" % base_dir
latest_saved_tx_data = None # gets initialized asap in the following code
# TODO - mark all validation data as True for blocks we have already passed
latest_validated_block_data = None # gets initialized asap in the following code
aux_blockchain_data = None # gets initialized asap in the following code
tx_metadata_keynames = [
	"blockhashend_txnum", # last 2 bytes of the block hash - tx num
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
	"txin_script_format_validation_status",
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
	latest_validated_block_data, aux_blockchain_data

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
	aux_blockchain_data = get_aux_blockchain_data()

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

def extract_full_blocks(options, sanitized = False):
	"""
	get full blocks which contain the specified addresses, transaction hashes or
	block hashes.
	"""
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
		block_filename = blockfile_num2name(block_file_num, options)
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

			# die if this chunk does not begin with the magic network id
			enforce_magic_network_id(
				active_blockchain, bytes_into_section, block_filename,
				bytes_into_file, block_height
			)
			# get the number of bytes in this block
			num_block_bytes = count_block_bytes(
				active_blockchain, bytes_into_section
			)
			# die if this chunk is smaller than the current block
			enforce_min_chunk_size(
				num_block_bytes, active_blockchain_num_bytes, bytes_into_file,
				bytes_into_section, block_filename, block_height
			)
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

			# make sure the block is correct size
			enforce_block_size(
				block, num_block_bytes, block_filename, bytes_into_file,
				bytes_into_section
			)
			# if we have already saved the txhash locations in this block then
			# get as little block data as possible, otherwise parse all data and
			# save it to disk. also get the block height within this function.
			parsed_block = minimal_block_parse_maybe_save_txs(
				block, latest_saved_tx_data, latest_validated_block_data,
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
			# if this block height has not been saved before, or if it has been
			# saved but has now changed, then update the dict and back it up to
			# disk. this doesn't happen often so it will not slow us down
			aux_blockchain_data = manage_aux_blockchain_data(
				parsed_block, aux_blockchain_data 
			)
			# convert hash or limit ranges to blocknum ranges
			options = options_grunt.convert_range_options(options, parsed_block)

			# if the block requires validation and we have not yet validated it
			# then do so now (we must validate all blocks from the start, but
			# only if they have not been validated before)
			if should_validate_block(
				options, parsed_block, latest_validated_block_data
			):
				parsed_block = validate_block(
					parsed_block, aux_blockchain_data, options
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
	save_latest_tx_progress(parsed_block)

	# save the latest validated block
	if options.validate:
		save_latest_validated_block(parsed_block)

	return filtered_blocks

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
		sorted(glob.glob("%s%s" % (options.BLOCKCHAINDIR, blockname_ls)))
	]
	closest_start_pos = None # init
	# get the total size of the blockchain
	full_blockchain_bytes = get_blockchain_size(options.BLOCKCHAINDIR)
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
	# get the number of bytes before the start position
	past_block_file_nums = [
		filenum for filenum in block_file_nums \
		if filenum < closest_blockfile_num
	]
	preceding_blockchain_bytes = get_blockchain_size(
		options.BLOCKCHAINDIR, past_block_file_nums
	)
	bytes_past = preceding_blockchain_bytes + closest_start_pos

	block_file_nums = [
		filenum for filenum in block_file_nums \
		if filenum >= closest_blockfile_num
	]
	return (
		hash_table, block_file_nums, closest_start_pos, full_blockchain_bytes,
		bytes_past, closest_block_height
	)

def extract_tx(options, txhash, tx_metadata):
	"""given tx position data, fetch the tx data from the blockchain files"""

	f = open(blockfile_num2name(tx_metadata["blockfile_num"], options), "rb")
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
			% bin2hex(txhash)
		)
	tx_bytes = partial_block_bytes[8 + tx_metadata["tx_start_pos"]:]
	return tx_bytes

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
		with open("%saux-blockchain-data.csv" % base_dir, "r") as f:
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
	with open("%saux-blockchain-data.csv" % base_dir, "w") as f:
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

def get_latest_validated_block():
	"""
	retrieve the latest validated block data. this is useful as it enables us to
	avoid re-validating blocks that have already been validated in the past.
	"""
	# TODO - why is this always 0?
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

	- the last bytes of the blockhash
	- the tx number
	- the blockfile number
	- the start position of the block, including magic_network_id
	- the start position of the tx in the block
	- the size of the tx in bytes

	the block hash and tx number are used to distinguish between duplicate txs
	with the same hash. this way we can determine if there is a doublespend.

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
	# use only the last x bytes of the block hash to conserve disk space. this
	# still gives us ffff chances of catching a duplicate tx hash - plenty given
	# how rare this is
	x = 2
	block_hashend = bin2hex(parsed_block["block_hash"][-x:])

	for (tx_num, tx) in sorted(parsed_block["tx"].items()):
		is_coinbase = 1 if (tx_num == 0) else None
		is_orphan = None if not parsed_block["is_orphan"] else 1
		# no spending txs at this stage
		spending_txs_list = [None] * len(tx["output"])
		blockhashend_txnum = "%s-%s" % (block_hashend, tx_num)
		save_data = {} # init
		save_data[blockhashend_txnum] = {
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

def save_tx_data_to_disk(
	options, txhash, save_data, existing_data_dict = None
):
	"""
	save a 64 character hash, eg 2ea121e32934b7348445f09f46d03dda69117f2540de164
	36835db7f032370d0 in a directory structure like base_dir/2ea/121/e32/934/
	b73/484/45f/09f/46d/03d/da6/911/7f2/540/de1/643/683/5db/7f0/323/70d/0.txt
	this way the maximum number of files or directories per dir is 0xfff = 4095,
	which should be fine on any filesystem the user chooses to run this script
	on.

	txs actually are not unique, for example, block 91842 has a duplicate
	coinbase tx of the coinbase tx in block 91812. this occurs when two coinbase
	addresses are the same, or when two txs spend from such coinbases. for this
	reason the end of the block hash and the tx number within the block are
	included in the tx metadata. this enables us to distinguish between a
	doublespend and a blockchain reorganization.
	"""
	(f_dir, f_name) = hash2dir_and_filename(txhash)

	# txs are always saved to disk just after they are extracted within function
	# minimal_block_parse_maybe_save_tx(). if there is no existing_data_dict
	# then this means that the txs have not already been saved to disk
	if existing_data_dict is None:

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
		existing_data_csv = get_tx_metadata_csv(txhash) # one tx per list item
		existing_data_dict = tx_metadata_csv2dict(existing_data_csv)

	save_data_new = merge_tx_metadata(txhash, existing_data_dict, save_data)
	# if there is nothing to update then exit here
	if existing_data_dict == save_data_new:
		return

	with open(f_name, "w") as f:
		f.write(tx_metadata_dict2csv(save_data_new))

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

		# if there is a change in the position of the tx in the blockchain then
		# warn the user about it
		if (
			("blockfile_num" in old_dict_i) and
			("blockfile_num" in new_dict_i) and
			(old_dict_i["blockfile_num"] != new_dict_i["blockfile_num"])
		):
			(hashend, txnum) = hashend_txnum.split("-")
			lang_grunt.die(
				"transaction %s from block with hash ending in %s (with hash"
				" %s) exists in two different blockfiles: filenum %s and"
				" filenum %s."
				% (
					txnum, hashend, txhash, old_dict_i["blockfile_num"],
					new_dict_i["blockfile_num"]
				)
			)
		# from here on, if the blockfilenum exists it is the same in old and new
		if (
			("block_start_pos" in old_dict_i) and
			("block_start_pos" in new_dict_i) and
			(old_dict_i["block_start_pos"] != new_dict_i["block_start_pos"])
		):
			(hashend, txnum) = hashend_txnum.split("-")
			lang_grunt.die(
				"transaction %s from block with hash ending in %s (with hash"
				" %s) exists within two different blocks in block file %s: at"
				" byte %s and at byte %s."
				% (
					txnum, hashend, txhash, old_dict_i["blockfile_num"],
					old_dict_i["block_start_pos"], new_dict_i["block_start_pos"]
				)
			)
		# from here on, if the block start pos exists it is the same in old and
		# new
		if (
			("tx_start_pos" in old_dict_i) and
			("tx_start_pos" in new_dict_i) and
			(old_dict_i["tx_start_pos"] != new_dict_i["tx_start_pos"])
		):
			(hashend, txnum) = hashend_txnum.split("-")
			lang_grunt.die(
				"transaction %s from block with hash ending in %s (with hash"
				" %s) exists in two different start positions in the same"
				" block: at byte %s and at byte %s."
				% (
					txnum, hashend, txhash, old_dict_i["tx_start_pos"],
					new_dict_i["tx_start_pos"]
				)
			)
		# from here on, if the block start pos exists it is the same in old and
		# new

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

			# spending txs list. each element is a later tx hash and txin index that
			# is spening from the tx specified by the filename
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
	outer_list = []
	for (hashend_txnum, inner_dict_data) in dict_data.items():

		inner_list = [] # init
		for keyname in tx_metadata_keynames:

			if keyname == "blockhashend_txnum":
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

	return os.linesep.join(outer_list)

def tx_metadata_csv2dict(csv_data):
	"""
	the tx data is stored as comma seperated values in the tx metadata files and
	the final element is a representation of a list. the tx_metadata_keynames
	global list shows what each element of the csv represents. the csv can have
	multiple lines because transaction hashes are not unique ids (see bip30).
	the last 2 bytes (4 chars) of the block hash and the txnum are included in
	each tx as a unique id.
	"""
	# csv_data is a list of txs
	dict_data = {}
	blockhashend_txnum_pos = tx_metadata_keynames.index("blockhashend_txnum")
	for tx in csv_data:
		# first get the csv as a list (but not including the square bracket,
		# since it might contain commas which would be interpreted as top level
		# elements
		start_sq = tx.index("[")
		list_data = tx[: start_sq - 1].split(",")

		# add the square bracket substring back into the list
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

			else:
				el = int(el)

			# save the block hash end - txnum seperately for now
			if i == blockhashend_txnum_pos:
				blockhashend_txnum = el
			else:
				tx_data[tx_metadata_keynames[i]] = el

		dict_data[blockhashend_txnum] = tx_data

	return dict_data

def get_tx_metadata_csv(txhash):
	"""
	given a tx hash (as a hex string), fetch the position data from the
	tx_metadata dirs. return csv data as it is stored in the file.
	"""
	(f_dir, f_name) = hash2dir_and_filename(txhash)
	try:
		with open(f_name, "r") as f:
			# get each tx as a list item
			data = [] # init
			for line in f:
				# get rid of the newline if it exists
				data.append(line.translate(None, "\n\r"))
	except:
		# this can occur when the user spends a transaction which exists within
		# the same block - the transaction will not have been written to the
		# filesystem yet. not to worry - we just fetch the transaction from ram
		# later on (before moving on to the next block)
		data = None

	return data

def mark_spent_tx(
	options, spendee_txhash, spendee_index, spender_txhash, spender_index,
	spendee_txs_metadata
):
	"""
	mark the transaction as spent using the later tx hash and later txin index.
	don't worry about overwriting a transaction that has already been spent -
	the lower level functions will handle this.
	"""
	# coinbase txs do not spend from any previous tx in the blockchain and so do
	# not need to be marked off
	if (
		(spendee_txhash == blank_hash) and
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
	spender_hashstart_index = "%s-%s" % (spender_txhash, spender_index)
	spender_txs_list[spendee_index] = spender_hashstart_index

	# now determine which block-hash-end txnum combo we are spending from. if it
	# already exists then use that one...
	use_blockhashend_txnum = None # init
	for (blockhashend_txnum, spendee_tx_metadata) in \
	spendee_txs_metadata.items():
		if spendee_tx_metadata["spending_txs_list"][spendee_index] == \
		spender_hashstart_index:
			use_blockhashend_txnum = blockhashend_txnum

	# otherwise use the block-hash-end from the tx with the earliest blockheight
	# and has not already been spent
	if use_blockhashend_txnum is None:
		earliest_block_height = None # init
		for (blockhashend_txnum, spendee_tx_metadata) in \
		spendee_txs_metadata.items():
			this_block_height = spendee_tx_metadata["block_height"]
			if (
				(
					spendee_tx_metadata["spending_txs_list"] \
					[spendee_index] is None
				) and (
					(earliest_block_height is None) or
					(this_block_height < earliest_blockheight)
				)
			):
				earliest_blockheight = this_block_height
				use_blockhashend_txnum = blockhashend_txnum

	save_data = {}
	save_data[use_blockhashend_txnum] = {"spending_txs_list": spender_txs_list}
	save_tx_data_to_disk(
		options, spendee_txhash, save_data, spendee_txs_metadata
	)

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
			if current_block_file_num > latest_validated_blockfile_num:
				save_txs = True
			elif (
				(current_block_file_num == latest_validated_blockfile_num) and
				(block_pos > latest_validated_block_pos)
			):
				save_txs = True
			# otherwise only get the header
			else:
				save_txs = False

		# if there is no validated block data already then we must save all txs
		else:
			save_txs = True

	# if the user does not want to validate blocks then we don't need txs
	else:
		save_txs = False

	if not save_txs:
		if latest_saved_tx_data is not None:
			(latest_saved_tx_blockfile_num, latest_saved_block_pos) = \
			latest_saved_tx_data

			# if we have passed the latest saved tx pos then get all block info
			if current_block_file_num > latest_saved_tx_blockfile_num:
				save_txs = True
			elif (
				(current_block_file_num == latest_saved_tx_blockfile_num) and
				(block_pos > latest_saved_block_pos)
			):
				save_txs = True

			# otherwise only get the header
			else:
				save_txs = False

		# if there is no saved tx data then we must save all txs
		else:
			save_txs = True

	if save_txs:
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

	if save_txs:
		# get the coinbase txin funds
		parsed_block["tx"][0]["input"][0]["funds"] = mining_reward(
			parsed_block["block_height"]
		)
		# if any prev_tx data could not be obtained from the tx_metadata dirs in
		# the filesystem it could be because this data exists within the current
		# block and has not yet been written to disk. if so then add it now.
		parsed_block = add_missing_prev_txs(parsed_block, get_info)

		# save the positions of all transactions, and other tx metadata
		save_tx_metadata(options, parsed_block)

	return parsed_block

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

"""
def update_txin_data(blocks):
	""
	update txin addresses and funds where possible. these are derived from
	previous txouts
	""
	aux_txout_data = {}
	"" of the format {
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
	""

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

				# if the scripts fail then the transaction is not valid
				#if not valid_checksig(
				if not manage_script_eval(
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
"""

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
	active_blockchain, bytes_into_section, block_filename, bytes_into_file,
	block_height
):
	"""die if this chunk does not begin with the magic network id"""
	if (
		active_blockchain[bytes_into_section: bytes_into_section + 4] != \
		magic_network_id
	):
		lang_grunt.die(
			"Error: block file %s appears to be malformed - block starting at"
			" byte %s in this file (absolute block num %s) does not start with"
			" the magic network id."
			% (
				block_filename, bytes_into_file + bytes_into_section,
				block_height
			)
		)

def enforce_min_chunk_size(
	num_block_bytes, active_blockchain_num_bytes, bytes_into_file,
	bytes_into_section, block_filename, block_height
):
	"""die if this chunk is smaller than the current block"""
	if (num_block_bytes + 8) > active_blockchain_num_bytes:
		lang_grunt.die(
			"Error: cannot process %s bytes of the blockchain since block"
			" starting at byte %s in file %s (absolute block num %s) has %s"
			" bytes and this script needs to extract at least one full block"
			" (plus its 8 byte header) at once (which comes to %s for this"
			" block). Please increase the value of variable"
			" 'active_blockchain_num_bytes' at the top of file btc_grunt.py."
			% (
				active_blockchain_num_bytes, bytes_into_file + \
				bytes_into_section, block_filename, block_height,
				num_block_bytes, num_block_bytes + 8
			)
		)

def count_block_bytes(blockchain, bytes_into_section):
	"""use the blockchain to get the number of bytes in this block"""
	pos = bytes_into_section
	num_block_bytes = bin2int(little_endian(blockchain[pos + 4: pos + 8]))
	return num_block_bytes

def enforce_block_size(
	block, num_block_bytes, block_filename, bytes_into_file, bytes_into_section
):
	"""die if the block var is the wrong length"""
	if len(block) != num_block_bytes:
		lang_grunt.die(
			"Error: Block file %s appears to be malformed - block starting at"
			" byte %s is incomplete."
			% (block_filename, bytes_into_file + bytes_into_section)
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

	if "target" in required_info:
		block_arr["target"] = int2hex(bits2target_int(bits))
		required_info.remove("target")
		if not required_info: # no more info required
			return block_arr

	if "target_validation_status" in required_info:
		# None indicates that we have not tried to verify that the target is
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
			block, pos, required_info, i, options
		)
		if "tx_timestamp" in required_info:
			block_arr["tx"][i]["timestamp"] = timestamp

		if not required_info: # no more info required
			return block_arr
		pos += length

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
			("prev_txs_metadata" in required_info) or
			("prev_txs" in required_info) or
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

		if (
			("txin_script" in required_info) or
			("txin_script_list" in required_info) or
			("txin_parsed_script" in required_info) or (
				("txin_script_format_validation_status" in required_info) and
				(not is_coinbase)
			)
		):
			input_script = block[pos: pos + txin_script_length]
		pos += txin_script_length

		if "txin_script" in required_info:
			tx["input"][j]["script"] = input_script

		if (
			("txin_script_list" in required_info) or
			("txin_parsed_script" in required_info) or (
				("txin_script_format_validation_status" in required_info) and
				(not is_coinbase)
			)
		):
			# convert string of bytes to list of bytes, return False upon fail
			explain = False
			script_elements = script_bin2list(input_script, explain)
			
		if "txin_script_list" in required_info:
			if script_elements is False:
				# if there is an error then set the list to None
				tx["input"][j]["script_list"] = None
			else:
				tx["input"][j]["script_list"] = script_elements

		if "txin_parsed_script" in required_info:
			if script_elements is False:
				# if there is an error then set the parsed script to None
				tx["input"][j]["parsed_script"] = None
			else:
				# convert list of bytes to human readable string
				tx["input"][j]["parsed_script"] = script_list2human_str(
					script_elements
				)
		# coinbase input scripts have no use, so do not validate them
		if (
			("txin_script_format_validation_status" in required_info) and
			(not is_coinbase)
		):
			if script_elements is False:
				# if we get here then there is an error
				tx["input"][j]["txin_script_format_validation_status"] = \
				script_bin2list(input_script, options.explain)
			else:
				# set to None - there may not be an error yet, be we don't know
				# if there will be an error later
				tx["input"][j]["txin_script_format_validation_status"] = None

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
			# get metadata from the tx_metadata files
			prev_tx_metadata_csv = get_tx_metadata_csv(bin2hex(txin_hash))
			if prev_tx_metadata_csv is None: 
				prev_txs_metadata = None
				prev_txs = None
			else:
				prev_txs_metadata = tx_metadata_csv2dict(prev_tx_metadata_csv)
				# get each previous tx (there might be more than one per hash as
				# tx hashes are not unique)
				prev_txs = {}
				for (block_hashend_txnum, prev_tx_metadata) in \
				prev_txs_metadata.items():
					# get the tx from the specified location in the blockchain
					prev_tx_bin = extract_tx(
						options, txin_hash, prev_tx_metadata
					)
					# fake the prev tx num
					if prev_tx_metadata["is_coinbase"] is None: # not coinbase
						fake_prev_tx_num = 1
					else: # if coinbase
						fake_prev_tx_num = 0
					# make sure not to include txin info otherwise we'll get
					(prev_txs[block_hashend_txnum], _) = tx_bin2dict(
						prev_tx_bin, 0, all_txout_info + ["tx_hash"],
						fake_prev_tx_num, options
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
			if (
				get_previous_tx and
				(prev_txs is not None)
			):
				# both previous txs are identical (use the last loop hashend)
				tx["input"][j]["funds"] = prev_txs[block_hashend_txnum] \
				["output"][txin_index]["funds"]
			else:
				tx["input"][j]["funds"] = None

		# get the txin address. note that this should not be trusted until the
		# tx has been verified
		if "txin_address" in required_info:
			if (
				get_previous_tx and
				(prev_txs is not None)
			):
				# both previous txs are identical (use the last loop hashend)
				tx["input"][j]["address"] = prev_txs[block_hashend_txnum] \
				["output"][txin_index]["address"]
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
			("txout_parsed_script" in required_info) or
			("txout_script_format_validation_status" in required_info) or
			("txout_address" in required_info)
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
			explain = False
			script_elements = script_bin2list(output_script, explain)
			
		if "txout_script_list" in required_info:
			if script_elements is False:
				# if there is an error then set the list to None
				tx["output"][k]["script_list"] = None
			else:
				tx["output"][k]["script_list"] = script_elements

		if "txout_parsed_script" in required_info:
			if script_elements is False:
				# if there is an error then set the parsed script to None
				tx["output"][k]["parsed_script"] = None
			else:
				# convert list of bytes to human readable string
				tx["output"][k]["parsed_script"] = script_list2human_str(
					script_elements
				)
		if "txout_script_format_validation_status" in required_info:
			if script_elements is False:
				# if we get here then there is an error
				tx["output"][k]["txout_script_format_validation_status"] = \
				script_bin2list(output_script, options.explain)
			else:
				# set to None - there may not be an error yet, be we don't know
				# if there will be an error later
				tx["output"][k]["txout_script_format_validation_status"] = None

		if "txout_address" in required_info:
			if script_elements is False:
				# if the script elements could not be parsed then we can't get
				# the address
				tx["output"][k]["address"] = None
			else:
				# return btc address or None
				tx["output"][k]["address"] = script2address(output_script)

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
	list for every single block, when its probably only needed for 1 or 2 blocks
	in the whole blockchain!

	finally, we need to recalculate the coinbase tx change value.
	"""
	# if there is no requirement to add the missing prev_txs then exit here
	if (
		("prev_txs_metadata" not in required_info) and
		("prev_txs" not in required_info) and
		("txin_funds" not in required_info) and
		("txin_address" not in required_info)
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
				"pos": tx["pos"],
				"size": tx["size"],
				# careful not to include the txin here otherwise we will get
				# its prev_tx and so on
				"this_txout": tx["output"]
			}} for (tx_num, tx) in parsed_block["tx"].items()
		}
	is_orphan = None # unknowable at this stage, update later as required
	for (tx_num, tx) in parsed_block["tx"].items():
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
							"blockfile_num": parsed_block["block_filenum"],
							"block_start_pos": parsed_block["block_pos"],
							"block_height": parsed_block["block_height"],
							# data on prev tx comes from the temp dict
							"tx_start_pos": prev_tx_data["pos"],
							"tx_size": prev_tx_data["size"],
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
				("txin_address" in required_info) and
				(txin["address"] is None)
			):
				# if we don't yet have all block tx data then get it now
				if not all_block_tx_data:
					all_block_tx_data = get_tx_hash_data(parsed_block)

				if txin["hash"] in all_block_tx_data:
					for (prev_tx_num, prev_tx_data) in \
					all_block_tx_data[txin["hash"]].items():
						parsed_block["tx"][tx_num]["input"][txin_num] \
						["address"] = prev_tx_data["this_txout"] \
						[txin["index"]]["address"]
						break # all tx data is identical

	parsed_block["tx"][0]["input"][0]["coinbase_change_funds"] = \
	calculate_tx_change(parsed_block)

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
		if "prev_txs" in txin:
			del parsed_tx["input"][txin_num]["prev_txs"]

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

		# quicker to store this one - saves creating it twice
		txin_funds_list = [txin["funds"] for txin in tx["input"].values()]

		# if any of the funds values are not available it probably means that
		# the tx spends from another tx within the same block. exit here and
		# come back later when the funds are available.
		if None in txin_funds_list:
			return None

		change += sum(txin_funds_list)
		change -= sum(txout["funds"] for txout in tx["output"].values())

	return change

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

def validate_block(parsed_block, aux_blockchain_data, options):
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
		parsed_block["bits_validation_status"] = valid_bits(
			parsed_block, aux_blockchain_data
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
		num_invalid = len(invalid_block_elements)
		# wrap each element in quotes
		invalid_block_elements = ["'%s'" % x for x in invalid_block_elements]
		lang_grunt.die(
			"Validation error. Element%s %s in the following block %s been"
			" found to be invalid:%s%s"
			% (
				lang_grunt.plural("s", num_invalid),
				lang_grunt.list2human_str(invalid_block_elements, "and"),
				lang_grunt.plural("have", num_invalid), os.linesep,
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
			spendee_txs_metadata = spender_txin["prev_txs_metadata"]
			spendee_txhash = bin2hex(spender_txin["hash"])
			spendee_index = spender_txin["index"]
			mark_spent_tx(
				options, spendee_txhash, spendee_index, spender_txhash,
				spender_index, spendee_txs_metadata
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
		spendee_txs_metadata = txin["prev_txs_metadata"]
		prev_txs = txin["prev_txs"]
		hashend_txnum0 = prev_txs.keys()[0]
		prev_tx0 = prev_txs[hashend_txnum0]

		# check if each transaction (hash) being spent actually exists. use any
		# tx since they both have identical data
		status = valid_txin_hash(spendee_hash, prev_tx0, options.explain)
		if "hash_validation_status" in txin:
			txin["hash_validation_status"] = status
		if status is not True:
			# merge the results back into the tx return var
			tx["input"][txin_num] = txin
			continue

		# from this point onwards the tx being spent definitely exists.

		# check if the transaction (index) being spent actually exists. use any
		# tx since they both have identical data
		status = valid_txin_index(spendee_index, prev_tx0, options.explain)
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
				txin_num, spent_txs, options.explain
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
				spendee_tx_metadata["is_orphan"], spendee_hash, options.explain
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
		#status = valid_checksig(tx, txin_num, prev_tx0, options.explain)
		status = manage_script_eval(tx, txin_num, prev_tx0, options.explain)
		if "checksig_validation_status" in txin:
			txin["checksig_validation_status"] = status
		if status is not True:
			# merge the results back into the tx return var
			tx["input"][txin_num] = txin
			continue

		# if a coinbase transaction is being spent then make sure it has already
		# reached maturity. do this for all previous txs
		any_immature = False
		for (hashend_txnum, spendee_tx_metadata) in \
		spendee_txs_metadata.items():
			status = valid_mature_coinbase_spend(
				block_height, spendee_tx_metadata, options.explain
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
	return None if (invalid_elements == []) else list(set(invalid_elements))
			
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

def valid_bits(block, bits_data, explain = False):
	"""
	return True if the block bits matches that derived from the block height
	and previous bits data. if the block bits is not valid then either
	return False if the explain argument is not set, otherwise return a human
	readable string with an explanation of the failure.

	to calculate whether the bits is valid we need to look at the current bits
	(from the bits_data dict), which is in the following format:
	{block-height: {block-hash0: {
		"filenum": 0, "start_pos": 999, "size": 285, "timestamp": x, "bits": x,
		"is_orphan": True
	}}}
	"timestamp" and "bits" are only defined every 2016 blocks or 2016 - 1, but
	"filenum", "start_pos", "size" and "is_orphan" are always defined.
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
				% (bits2target_int(initial_bits), parsed_block["target"])
			else:
				return False

	# from here onwards we are beyond block height 2016

	# find bits data for the block that is the floored multiple of 2016 for the
	# current height
	# if block height is 2015 then floor == 0, not 2016
	# if block height is 2016 then floor == 2016, not 0
	# if block height is 2017 then floor == 2016, not 0
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
		calculated_bits = new_bits(old_bits, old_bits_time, new_bits_time)
		if calculated_bits != parsed_block["bits"]:
			if explain:
				return "the bits for block with hash %s and height %s, should" \
				" be %s, however it has been calculated as %s." \
				% (
					bin2hex(block_hash_i), block_height,
					bin2hex(calculated_bits), parsed_block["bits"]
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
	if is_orphan is None:
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
	try:
		wiped_tx = copy.deepcopy(tx)
	except:
		# catch and display too-deep recursion errors
		lang_grunt.die("failed to deepcopy tx %s" % tx)

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
	return (wiped_tx, txin["script_list"], prev_txout["script_list"])

def valid_checksig(
	wiped_tx, on_txin_num, subscript, pubkey, signature, explain = False
):
	"""
	return True if the checksig for this txin passes. if it fails then either
	return False if the explain argument is not set, otherwise return a human
	readable string with an explanation of the failure.

	https://en.bitcoin.it/wiki/OP_CHECKSIG
	http://bitcoin.stackexchange.com/questions/8500
	"""
	# remove the signature from the subscript
	pushsig_bin = pushdata_int2bin(len(signature))
	pushsig_sig_bin = "%s%s" % (pushsig_bin, signature)
	subscript = subscript.replace(pushsig_sig_bin, "")

	hashtype_int = bin2int(signature[-1])
	hashtype_name = int2hashtype(hashtype_int)
	if hashtype_name != "SIGHASH_ALL":
		# TODO - support other hashtypes
		if explain:
			return "hashtype %s is not yet supported. found on the end of" \
			" signature %s." \
			% (hashtype_name, bin2hex(signature))
		else:
			return False

	hashtype = little_endian(int2bin(hashtype_int, 4))

	# chop off the last (hash type) byte from the signature
	signature = signature[: -1]

	# add the subscript back into the txin and calculate the hash
	wiped_tx["input"][on_txin_num]["script"] = subscript
	wiped_tx["input"][on_txin_num]["script_length"] = len(subscript)
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

def manage_script_eval(tx, on_txin_num, prev_tx, explain = False):
	"""
	always try the checksig first, since this covers 99% of all scripts. if it
	fails then check if the scripts are in the correct format for checksig. if
	so then return the status, if not then evaluate the script. while it would
	make more sense to first check if the script is a checksig, this would be
	far slower.

	return True if the scripts pass. if it fails then either return False if the
	explain argument is not set, otherwise return a human readable string with
	an explanation of the failure.
	"""
	tmp = prelim_checksig_setup(tx, on_txin_num, prev_tx, explain)
	if isinstance(tmp, tuple):
		(wiped_tx, txin_script_list, prev_txout_script_list) = tmp
	else:
		# if tmp is not a tuple then it must be either False or an error string
		return tmp

	# TODO - evaluate txin and txout scripts independently - pass in stack
	# and return stack from each. this is how the satoshi client validates txs.
	# this way, if a checksig is encountered in the txin then we will pass in
	# the correct subscript (ie the txin script)
	return script_eval(
		wiped_tx, on_txin_num, txin_script_list, prev_txout_script_list, explain
	)

	# attempt to extract the pubkey either from the previous txout or this txin
	pubkey_from_txin = script2pubkey(txin_script_list)
	pubkey_from_txout = script2pubkey(prev_txout_script_list)

	# if the pubkey was not found then the script must be non-standard - so
	# evaluate the opcodes
	if (
		(pubkey_from_txin in [None, False]) or
		(pubkey_from_txout in [None, False])
	):
		return script_eval(
			wiped_tx, on_txin_num, txin_script_list, prev_txout_script_list,
			explain
		)
		"""
		if explain:
			return "could not find the public key in either the txin script" \
			" (%s) or the previous txout script (%s)." \
			% (
				txin["parsed_script"],
				prev_tx["output"][prev_index]["parsed_script"]
			)
		else:
			return False
		"""
	# if we get here then we have at least 1 pubkey.

	# if we have 2 pubkeys then check if they are the same
	if (
		(pubkey_from_txin is not None) and
		(pubkey_from_txout is not None) and
		(pubkey_from_txin != pubkey_from_txout)
	):
		if explain:
			return "the public key from the current txin script (%s) does not" \
			" match the public key from the previous txout script (%s)." \
			% (pubkey_from_txin, pubkey_from_txout)
		else:
			return False

	# the address has been derived from the txout, now check if the later txin
	# pubkey resolves to this address
	if pubkey_from_txin is not None:
		address_from_txin_pubkey = pubkey2address(pubkey_from_txin)
		if address_from_txin_pubkey != address_from_txout_pubkey:
			if explain:
				return "txin public key %s resolves to address %s, however" \
				" this txin is attempting to spend from a txout with address" \
				" %s." \
				% (
					bin2hex(pubkey_from_txin), address_from_txin_pubkey,
					address_from_txout_pubkey
				)
			else:
				return False

	codeseparator_bin = opcode2bin("OP_CODESEPARATOR")

	# if we get here then we have a pubkey either in the txin or the txout
	if pubkey_from_txin is not None:
		pubkey = pubkey_from_txin
	elif pubkey_from_txout is not None:
		pubkey = pubkey_from_txout

	# extract the signature from the txin
	signature = script2signature(txin["script_list"])
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

	txin_subscript = prev_txout_subscript
	checksig_status = valid_checksig(
		wiped_tx, on_txin_num, txin_subscript, pubkey, signature, explain
	)
	if checksig_status is True:
		# great :)
		return True
	else:
		# checksig failed. now see if it is because its a bad checksig, or if
		# its because the script is another format
		if (
			(
				extract_script_format(txin_script_list) in [
					"sigpubkey", "scriptsig"
				]
			)
			and (
				extract_script_format(prev_txout_script_list) in [
					"pubkey", "hash160"
				]
			)
		):
			# this was indeed a checksig script - its just a bad one
			return checksig_status
		else:
			# this was not a checksig script - evaluate it independently now...
			return script_eval(
				wiped_tx, on_txin_num, txin_script_list, prev_txout_script_list,
				explain
			)

def script_eval(
	wiped_tx, on_txin_num, txin_script_list, prev_txout_script_list,
	explain = False
):
	"""
	return True if the scripts pass. if they fail then either return False if
	the explain argument is not set, otherwise return a human readable string
	with an explanation of the failure.
	"""
	# first combine the scripts from the txin with the prev_txout
	script_list = txin_script_list + prev_txout_script_list

	# human script - used for errors and debugging
	human_script = script_list2human_str(script_list)

	def stack2human_str(stack):
		if not stack:
			return "*empty*"
		else:
			return " ".join(bin2hex(el) for el in stack),

	stack = [] #init
	pushdata = False # init
	latest_codesep = False # init
	txin_script_size = len(txin_script_list)
	subscript_list = copy.copy(txin_script_list) # init
	current_subscript = "in"
	for (el_num, opcode_bin) in enumerate(script_list):

		# update the current subscript onchange
		if (
			(el_num >= txin_script_size) and
			(current_subscript != "out")
		):
			current_subscript = "out"
			subscript_list = copy.copy(prev_txout_script_list)

		if pushdata:
			# beware - no length checks!
			stack.append(opcode_bin)
			pushdata = False # reset
			continue
		elif len(opcode_bin) <= 5: # OP_PUSHDATA4 can be 5 bytes long
			opcode_str = bin2opcode(opcode_bin)
		else:
			if explain:
				return "unexpected operation %s in script %s - neither an" \
				" opcode nor OP_PUSHDATA" \
				% (bin2hex(opcode_bin), human_script)
			else:
				return False

		# everything from here on is an opcode - put them in order of occurrence
		# for speed

		# set up to push the data in the next loop onto the stack
		if "OP_PUSHDATA" in opcode_str:
			pushdata = True
			continue

		if "OP_CHECKSIG" == opcode_str:
			pubkey = stack.pop()
			signature = stack.pop()
			subscript = script_list2bin(subscript_list)

			res = valid_checksig(
				wiped_tx, on_txin_num, subscript, pubkey, signature, explain
			)
			if res is not True:
				if explain:
					return "checksig fail in script %s with stack %s" \
					% (human_script, stack2human_str(stack))
				else:
					return False
			else:
				stack.append(int2bin(1))

			continue

		# duplicate the last item in the stack
		if "OP_DUP" == opcode_str:
			stack.append(stack[-1])
			continue

		# hash (sha256 then ripemd160) the top stack item, and add the result to
		# the top of the stack
		if "OP_HASH160" == opcode_str:
			try:
				v1 = stack.pop()
			except:
				if explain:
					return "could not perform hash160 on the stack since it" \
					" is empty. script: %s" \
					% human_script
				else:
					return False

			stack.append(ripemd160(sha256(v1)))
			continue

		if "OP_CHECKMULTISIG" == opcode_str:
			# get all the signatures into a list, and all the pubkeys into a
			# list. starting from the top of the stack, moving down, looks like
			# this:
			#
			# [num_pubkeys] [pubkeys_list] [num_signatures] [signature_list]
			#
			# then validate each signature against each pubkey. each signature
			# must validate against at least one pubkey in the list for
			# OP_CHECKMULTISIG to pass.

			subscript = script_list2bin(subscript_list)

			try:
				num_pubkeys = int(stack.pop())
			except:
				if explain:
					return "failed to count the number of public keys during" \
					" OP_CHECKMULTISIG. script: %s" \
					% human_script
				else:
					return False

			# make sure we have an allowable number of pubkeys
			if (
				(num_pubkeys < 0) or
				(num_pubkeys > 20)
			):
				if explain:
					return "%s is an unacceptable number of public keys for" \
					" OP_CHECKMULTISIG. script: %s" \
					% (num_pubkeys, human_script)
				else:
					return False

			# read the pubkeys from the stack into a new list
			pubkeys = []
			try:
				for i in range(num_pubkeys):
					pubkeys.append(stack.pop())
			except:
				if explain:
					return "failed to get %s public keys off the stack in" \
					" OP_CHECKMULTISIG. script: %s" \
					% (num_pubkeys, human_script)
				else:
					return False

			try:
				num_signatures = int(stack.pop())
			except:
				if explain:
					return "failed to count the number of signatures during" \
					" OP_CHECKMULTISIG. script: %s" \
					% human_script
				else:
					return False

			if (
				(num_signatures < 0) or
				(num_signatures > num_pubkeys)
			):
				if explain:
					return "%s is an unacceptable number of signatures for"
					" OP_CHECKMULTISIG. number of public keys: %s, script: %s" \
					% (num_signatures, num_pubkeys, human_script)
				else:
					return False

			# read the signatures from the stack into a new list
			signatures = []
			try:
				for i in range(num_signatures):
					signatures.append(stack.pop())
			except:
				if explain:
					return "failed to get %s signatures off the stack in" \
					" OP_CHECKMULTISIG. script: %s" \
					% (num_signatures, human_script)
				else:
					return False

			# now validate each signature against all pubkeys. we want to keep
			# a tally of the details of errors so we can report them all
			checksig_statuses = {
				signature: {pubkey: None for pubkey in pubkeys} for \
				signature in signatures
			}
			for signature in signatures:
				for pubkey in pubkeys:
					res = valid_checksig(
						wiped_tx, on_txin_num, subscript, pubkey, signature,
						explain
					)
					if res is True:
						# we have found one pubkey that matches this signature
						del checksig_statuses[signature]
						break # move on to the next signature
					else:
						# save to display all errors per signature (if any)
						checksig_statuses[signature][pubkey] = res

			if checksig_statuses:
				# there were errors - now return them all
				if explain:
					return "the following errors were encountered in" \
					" OP_CHECKMULTISIG: %s%s" \
					% (
						os.linesep, os.linesep.join(
							"signature %s and pubkey %s have error: %s" % \
							(sig, pubkey, err) for (sig, pubkey_data) in \
							a.items() for (pubkey, err) in pubkey_data.items()
						)
					)
				else:
					return False
			else:
				stack.append(int2bin(1))
			continue

		# if the last and the penultimate stack items are not equal then fail
		if "OP_EQUALVERIFY" == opcode_str:
			try:
				v1 = stack.pop()
				v2 = stack.pop()
				if v1 != v2:
					if explain:
						return "the final stack item %s is not equal to the" \
						" penultimate stack item %s, so OP_EQUALVERIFY fails" \
						" in script: %s" \
						% (bin2hex(v1), bin2hex(v2), human_script)
					else:
						return False
			except IndexError:
				if explain:
					return "there are not enough items on the stack (%s) to" \
					" perform OP_EQUALVERIFY. script: %s" \
					% (stack2human_str(stack), human_script)
				else:
					return False
			continue

		# do nothing for OP_NOP through OP_NOP10
		if "OP_NOP" in opcode_str:
			continue

		# push an empty byte onto the stack
		if "OP_FALSE" == opcode_str:
			stack.append(int2bin(0))
			continue
 
		# push 0x01 onto the stack
		if "OP_TRUE" == opcode_str:
			stack.append(int2bin(1))
			continue
 
		# drop the last item in the stack
		if "OP_DROP" == opcode_str:
			stack.pop()
			continue

		# use to construct subscript
		if "OP_CODESEPARATOR" == opcode_str:
			# the subscript goes from the next element up to the end of the
			# current (not entire) script
			if current_subscript == "in":
				subscript_list = txin_script_list[el_num + 1:]
			elif current_subscript == "out":
				subscript_list = txout_script_list[el_num + 1:]
			continue

		# hash (sha256 once) the top stack item, and add the result to the top
		# of the stack
		if "OP_SHA256" == opcode_str:
			stack.append(sha256(stack[-1]))
			continue

		# hash (sha256 twice) the top stack item, and add the result to the top
		# of the stack
		if "OP_HASH256" == opcode_str:
			stack.append(sha256(sha256(stack[-1])))
			continue

		# append \x01 if the two top stack items are equal, else \x00
		if "OP_EQUAL" == opcode_str:
			try:
				v1 = stack.pop()
				v2 = stack.pop()
				res = 1 if (v1 == v2) else 0
				stack.append(int2bin(res))
			except IndexError:
				if explain:
					return "there are not enough items on the stack (%s) to" \
					" perform OP_EQUAL. script: %s" \
					% (stack2human_str(stack), human_script)
				else:
					return False
			continue

		if "OP_VERIFY" == opcode_str:
			try:
				v1 = stack.pop()
				if bin2int(v1) == 0:
					if explain:
						return "OP_VERIFY failed since the top stack item" \
						" (%s) is zero. script: %s" \
						% (script_list2human_str(v1), human_script)
					else:
						return False
			except IndexError:
				if explain:
					return "OP_VERIFY failed since there are no items on the" \
					" stack. script: %s" \
					% human_script
				else:
					return False
			continue

		if explain:
			return "opcode %s is not yet supported in function script_eval()." \
			" stack: %s, script: %s" \
			% (opcode_str, stack2human_str(stack), human_script)
		else:
			return False

	try:
		v1 = stack.pop()
		if bin2int(v1) == 0: 
			if explain:
				return "script eval failed since the top stack item  (%s) at" \
				" the end of all operations is zero. script: %s" \
				% (script_list2human_str(v1), script_list2human_str(script))
			else:
				return False
	except IndexError:
		if explain:
			return "script eval failed since there are no items on the" \
			" stack at the end of all operations. script: %s" \
			% human_script
		else:
			return False

	return True

def bits2target_int(bits_bytes):
	# TODO - this will take forever as the exponent gets large - modify to use
	# taylor series
	exp = bin2int(bits_bytes[: 1]) # exponent is the first byte
	mult = bin2int(bits_bytes[1:]) # multiplier is all but the first byte
	return mult * (2 ** (8 * (exp - 3)))

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
		explain = False
		script_list = script_bin2list(script, explain)
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
		explain = False
		script_list = script_bin2list(script, explain)
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

def script2address(script):
	"""extract the bitcoin address from the binary script (input or output)"""
	format_type = extract_script_format(script)
	if not format_type:
		return None

	# OP_PUSHDATA0(33/65) <pubkey> OP_CHECKSIG
	if format_type == "pubkey":
		output_address = pubkey2address(script_bin2list(script)[1])

	# OP_DUP OP_HASH160 OP_PUSHDATA0(20) <hash160> OP_EQUALVERIFY OP_CHECKSIG
	elif format_type == "hash160":
		output_address = hash1602address(script_bin2list(script)[3])

	# OP_PUSHDATA0(73) <signature> OP_PUSHDATA0(33/65) <pubkey>
	elif format_type == "sigpubkey":
		output_address = pubkey2address(script_bin2list(script)[3])

	# OP_PUSHDATA <signature>
	elif format_type == "scriptsig":
		# no pubkey in a scriptsig
		return None

	else:
		lang_grunt.die("unrecognized format type %s" % format_type)
	return output_address

def extract_script_format(script):
	"""carefully extract the format for the input (binary string) script"""
	# only two input formats recognized - list of binary strings, and binary str
	if isinstance(script, list):
		script_list = script
	else:
		explain = False
		script_list = script_bin2list(script, explain) # explode
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
	recognized_formats = {
		"pubkey": ["OP_PUSHDATA", "pubkey", opcode2bin("OP_CHECKSIG")],
		"hash160": [
			opcode2bin("OP_DUP"), opcode2bin("OP_HASH160"),
			opcode2bin("OP_PUSHDATA0(20)"), "hash160",
			opcode2bin("OP_EQUALVERIFY"), opcode2bin("OP_CHECKSIG")
		],
		"scriptsig": ["OP_PUSHDATA", "signature"],
		"sigpubkey": ["OP_PUSHDATA", "signature", "OP_PUSHDATA", "pubkey"]
	}
	for (format_type, format_opcodes) in recognized_formats.items():
		# try next format
		if len(format_opcodes) != len(script_list):
			continue

		# correct number of script elements from here on...

		last_format_el_num = len(format_opcodes) - 1
		for (format_opcode_el_num, format_opcode) in enumerate(format_opcodes):
			# the actual value of the element in the script
			script_el_value = script_list[format_opcode_el_num]

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
				(format_opcode_el_num == 3) and
				(format_opcode == "hash160") and
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

	if opcode_count > max_opcode_count:
		if explain:
			return "Error: Script %s has %s opcodes, which exceeds the" \
			" allowed maximum of %s opcodes." \
			% (bin2hex(bytes), opcode_count, max_script_size)
		else:
			return False

	return script_list

def script_list2human_str(script_elements_bin):
	"""
	take a list whose elements are bytes and output a human readable bitcoin
	script (ie replace opcodes and convert bin to hex for pushed data)

	no sanitization is done here.
	"""
	human_str = ""

	# set to true once the next list element is to be pushed to the stack
	push = False # init

	for bytes in script_elements_bin:
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
	decode the hash type from the binary byte (that comes from the end of the
	signature)
	"""
	if hashtype_int == 1:
		return "SIGHASH_ALL"
	if hashtype_int == 2:
		return "SIGHASH_NONE"
	if hashtype_int == 3:
		return "SIGHASH_SINGLE"
	if hashtype_int == 0x80:
		return "SIGHASH_ANYONECANPAY"
	# if none of the other hashtypes match, then default to SIGHASH_ALL
	# as per https://bitcointalk.org/index.php?topic=120836.0
	return "SIGHASH_ALL"

def bin2opcode(code_bin):
	"""
	decode a single byte into the corresponding opcode as per
	https://en.bitcoin.it/wiki/script
	"""
	code = ord(code_bin)
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
		return "OP_NOP2"
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
		lang_grunt.die(
			"unrecognized opcode (%s) input to function pushdata_opcode_split()"
			% opcode
		)
	matches = re.search(r"\((\d+)\)", opcode)
	try:
		push_num_bytes = int(matches.group(1))
	except AttributeError:
		lang_grunt.die(
			"Error: opcode %s does not contain the number of bytes to push" 
			" onto the stack"
			% opcode
		)
	opcode_num = int(opcode[11])
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
		lang_grunt.die(
			"Error: unrecognized opcode OP_PUSHDATA%s" % pushdata_num
		)
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
	if opcode == "OP_FALSE": # an empty array of bytes is pushed onto the stack
		return hex2bin(int2hex(0))
	elif "OP_PUSHDATA" in opcode:
		# the next opcode bytes is data to be pushed onto the stack
		# this is the only opcode that may return more than one byte
		return pushdata_opcode2bin(opcode, explain)
	elif opcode == "OP_1NEGATE":
		# the number -1 is pushed onto the stack
		return hex2bin(int2hex(79))
	elif opcode == "OP_TRUE":
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
		# top stack value != true: mark transaction as invalid and remove,
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
	elif opcode == "OP_NOP2":
		# the word is ignored
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

def new_bits(old_bits, old_bits_time, new_bits_time):
	"""
	calculate the new target. we want new blocks to be mined on average every 10
	minutes.

	http://bitcoin.stackexchange.com/a/2926/2116
	"""
	two_weeks = 14 * 24 * 60 * 60 # in seconds
	half_a_week = 3.5 * 24 * 60 * 60 # in seconds
	time_diff = new_bits_time - old_bits_time

	# if the difference is greater than 8 weeks, set it to 8 weeks; this
	# prevents the difficulty decreasing by more than a factor of 4
	if time_diff > two_weeks:
		time_diff = two_weeks

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

def pubkey2address(pubkey):
	"""
	take the public ecdsa key (bytes) and output a standard bitcoin address
	(ascii string), following
	https://en.bitcoin.it/wiki/Technical_background_of_Bitcoin_addresses
	pubkeys can be various lengths. most are 65 bytes, but some are 33 bytes,
	eg tx 94af4607627535f9b2968bd1fbbf67be101971d682023d6a3b64d8caeb448870 which
	spends 0.01337 btc lol
	"""
	return hash1602address(ripemd160(sha256(pubkey)))

def address2hash160(address):
	"""
	from https://github.com/gavinandresen/bitcointools/blob/master/base58.py
	"""
	bytes = base58decode(address)
	return bytes[1: 21]

def hash1602address(hash160):
	"""
	convert the hash160 output (bytes) to the bitcoin address (ascii string)
	https://en.bitcoin.it/wiki/Technical_background_of_Bitcoin_addresses
	"""
	temp = chr(0) + hash160 # 00010966776006953d5567439e5e39f86a0d273bee
	checksum = sha256(sha256(temp))[: 4] # checksum is the first 4 bytes
	hex_address = bin2hex(temp + checksum) # 00010966776006953d5567439e5e39f86a0d273beed61967f6
	decimal_address = int(hex_address, 16) # 25420294593250030202636073700053352635053786165627414518

	return version_symbol("ecdsa_pub_key_hash") + \
	base58encode(decimal_address) # 16UwLL9Risc3QfPqBUvKofHmBQ7wMtjvM

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
		lang_grunt.die(
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
		lang_grunt.die(
			"value %s is too big to be decoded as a variable length integer"
			% bin2hex(input_bytes)
		)
	return (value, bytes_in)

def manage_aux_blockchain_data(parsed_block, aux_blockchain_data):
	"""
	we save the blockfile number and position to the aux_blockchain_data dict
	every aux_blockchain_data_backup_freq blocks (with an offset of -1) - this
	allows us to skip ahead when the user specifies a block range that does not
	start from block 0.

	if this block height has not been saved before, or if it has been saved but
	has now changed, then update the dict and back it up to disk. this doesn't
	happen often so it will not slow us down.

	aux_blockchain_data is in the format:
	{block-height: {block-hash0: {
		"filenum": 0, "start_pos": 999, "size": 285, "timestamp": x, "bits": x,
		"is_orphan": True
	}}}
	"timestamp" and "bits" are only defined every 2016 blocks or 2016 - 1, but
	"filenum", "start_pos", "size" and "is_orphan" are always defined.
	"""
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
		return aux_blockchain_data

	block_hash = parsed_block["block_hash"]
	save_to_disk = False # init

	# from here on this is a block to backup to disk. but if it is already on	
	# disk then there is nothing to do here
	if block_height not in aux_blockchain_data:
		aux_blockchain_data[block_height] = {} # init
		save_to_disk = True

	if block_hash not in aux_blockchain_data[block_height]:
		aux_blockchain_data[block_height][block_hash] = {} # init
		save_to_disk = True

	# always backup the file number
	if (
		("filenum" not in aux_blockchain_data[block_height][block_hash]) or
		aux_blockchain_data[block_height][block_hash]["filenum"] != \
		parsed_block["block_filenum"]
	):
		aux_blockchain_data[block_height][block_hash]["filenum"] = \
		parsed_block["block_filenum"]
		save_to_disk = True

	# always backup the start position of the block in the file
	if (
		("start_pos" not in aux_blockchain_data[block_height][block_hash]) or
		aux_blockchain_data[block_height][block_hash]["start_pos"] != \
		parsed_block["block_pos"]
	):
		aux_blockchain_data[block_height][block_hash]["start_pos"] = \
		parsed_block["block_pos"]
		save_to_disk = True

	# always backup the block size
	if (
		("size" not in aux_blockchain_data[block_height][block_hash]) or
		aux_blockchain_data[block_height][block_hash]["size"] != \
		parsed_block["size"]
	):
		aux_blockchain_data[block_height][block_hash]["size"] = \
		parsed_block["size"]
		save_to_disk = True

	# only backup the block timestamp if this is a 2-week hit
	if (
		("timestamp" not in aux_blockchain_data[block_height][block_hash]) or
		aux_blockchain_data[block_height][block_hash]["timestamp"] != \
		parsed_block["timestamp"]
	):
		save_to_disk = True
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
		save_to_disk = True
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
		save_to_disk = True # there is something to change
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
		save_to_disk = True # there is something to change
		aux_blockchain_data[block_height][block_hash]["is_orphan"] = \
		new_orphan_status

	# if there were no updates then exit here
	if not save_to_disk:
		return aux_blockchain_data

	# back-up to disk in case an error is encountered later (which would prevent
	# this backup from occuring and then we would need to start all over agin)
	save_aux_blockchain_data(aux_blockchain_data)

	return aux_blockchain_data

def manage_orphans(
	filtered_blocks, hash_table, parsed_block, aux_blockchain_data, mult
):
	"""
	if the hash table grows to mult * coinbase_maturity size then:
	- detect any orphans in the hash table
	- mark off these orphans in the blockchain (filtered_blocks)
	- mark off all certified non-orphans in the blockchain
	- mark off any orphans in the aux_blockchain_data dict
	- truncate the hash table back to coinbase_maturity size again
	tune mult according to whatever is faster.
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

def version_symbol(use, formatt = "prefix"):
	"""
	retrieve the symbol for the given btc use case use list on page
	https://en.bitcoin.it/wiki/Base58Check_encoding and
	https://en.bitcoin.it/wiki/List_of_address_prefixes
	"""
	if use == "ecdsa_pub_key_hash":
		symbol = {"decimal": 0, "prefix": "1"}

	elif use == "ecdsa_script_hash":
		symbol = {"decimal": 5, "prefix": "3"}

	elif use == "compact_pub_key":
		symbol = {"decimal": 21, "prefix": "4"}

	elif use == "namecoin_pub_key_hash":
		symbol = {"decimal": 52, "prefix": "M"}

	elif use == "private_key":
		symbol = {"decimal": 128, "prefix": "5"}

	elif use == "testnet_pub_key_hash":
		symbol = {"decimal": 111, "prefix": "n"}

	elif use == "testnet_script_hash":
		symbol = {"decimal": 196, "prefix": "2"}

	else:
		lang_grunt.die("unrecognized bitcoin use [" + use + "]")

	if formatt not in symbol:
		lang_grunt.die("format [" + formatt + "] is not recognized")

	symbol = symbol[formatt] # return decimal or prefix
	return symbol

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

def get_blockchain_size(blockchain_dir, filenums = None):
	"""
	return the combined size of the specified blockchain filenums. if none are
	specified then use all files.
	"""
	total_size = 0 # accumulator
	for filename in sorted(glob.glob("%s%s" % (blockchain_dir, blockname_ls))):
		filenum = blockfile_name2num(filename)
		if (
			(filenums is None) or
			(filenum in filenums)
		):
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
		hex_str = hex_str[: -1]
	if len(hex_str) % 2:
		hex_str = "0" + hex_str
	return hex_str

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

def blockfile_num2name(num, options):
	return "%s%s" % (options.BLOCKCHAINDIR, blockname_regex % num)

def blockfile_name2num(block_file_name):
	return int(re.findall(r"\d+", block_file_name)[0])

sanitize_globals() # run whenever the module is imported

"""module containing some general bitcoin-related functions"""

import sys
import pprint
import copy
import binascii
import hashlib
import re
import ast
import glob
import os
import errno
import progress_meter
import csv
import psutil
import ecdsa_ssl
import inspect

# module to do language-related stuff for this project
import lang_grunt

# module to process the user-specified btc-inquisitor options
import options_grunt

# module globals:

max_block_size = 300 # 1024 * 1024 # 1MB == 1024 * 1024 bytes

# the number of bytes to process in ram at a time.
# set this to the max_block_size + 4 bytes for the magic_network_id seperator +
# 4 bytes which contain the block size 
active_blockchain_num_bytes = max_block_size + 4 + 4

magic_network_id = "f9beb4d9"
coinbase_maturity = 100 # blocks
satoshis_per_btc = 100000000
base58alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
blank_hash = "0000000000000000000000000000000000000000000000000000000000000000"
coinbase_index = "ffffffff"
int_max = "7fffffff"
blockname_format = "blk*[0-9]*.dat"
#block_positions_file = os.path.expanduser("~/.btc-inquisitor/block_positions.csv")
#block_positions = []
block_header_info = [
	"block_hash",
	"format_version",
	"previous_block_hash",
	"merkle_root",
	"timestamp",
	"bits",
	"nonce",
	"block_size",
	"block_bytes"
]
all_txin_info = [
	"txin_verification_attempted",
	"txin_verification_succeeded",
	"txin_funds",
	"txin_hash",
	"txin_index",
	"txin_script_length",
	"txin_script",
	"txin_parsed_script",
	"txin_address",
	"txin_sequence_num"
]
all_txout_info = [
	"txout_funds",
	"txout_script_length",
	"txout_script",
	"txout_address",
	"txout_parsed_script"
]
remaining_tx_info = [
	"num_txs",
	"tx_version",
	"num_tx_inputs",
	"num_tx_outputs",
	"tx_lock_time",
	"tx_hash",
	"tx_bytes",
	"tx_size"
]
all_tx_info = all_txin_info + all_txout_info + remaining_tx_info
all_block_info = block_header_info + all_tx_info

all_validation_info = [
	"target_gives_ten_minute_blocks",
	"hash_lower_than_target",
	"merkle_leaves_give_root",
	""
]

def sanitize_globals():
	"""
	this function is run automatically at the start - see the final line in this
	file.
	"""

	global magic_network_id, blank_hash, coinbase_index, int_max

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
	coinbase_index = hex2int(coinbase_index)
	int_max = hex2bin(int_max)

def enforce_sanitization(inputs_have_been_sanitized):
	previous_function = inspect.stack()[1][3] # [0][3] would be this func name
	if not inputs_have_been_sanitized:
		lang_grunt.die(
			"Error: You must sanitize the input options with function"
			" sanitize_options_or_die() before passing them to function %s()."
			% previous_function
		)

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

def get_requested_blockchain_data(options, sanitized = False):
	"""
	use the options to extract data from the blockchain files. there are 3
	categories of data to return:
	- full blocks = {block_hash: {block data}, ..., block_hash: {block data}}
	- txs = [{tx data}, ..., {tx data}]
	- balances = {addr: 123.45, ..., addr: 678.9}
	"""
	# make sure the user input data has been sanitized
	enforce_sanitization(sanitized)

	# first pass of the blockchain - gets all block data in the range specified
	# by the options, except the txin addresses
	blocks = extract_full_blocks(options, sanitized)

	# if no blocks match the option specifications then we cannot get
	# transactions or balances either
	if not blocks:
		return

	# update txin addresses that can be determined from the blocks dict. this is
	# extremely unlikely to find all the txin addresses for the blocks specified
	# in the options
	if options.ADDRESSES:
		blocks = update_txin_data(blocks)

	# check if any txin-addresses are missing. if so then fetch the
	# corresponding prev-tx-hash & index
	if (
		(options.FORMAT not in ["BINARY", "HEX"]) and \
		# balance doesn't require the txin-addresses
		(options.OUTPUT_TYPE != "BALANCES")
	):
		additional_required_data = {}
		for (block_hash, block) in blocks.items():
			# returns {"txhash": index, "txhash": index, ...} or {}
			temp = get_missing_txin_data(block, options)
			if temp:
				additional_required_data.update(temp)

		# do a second pass of the blockchain to get the blocks being spent from
		# in the range specified by the options
		aux_blocks = {} # init
		if additional_required_data:
			saved_options = copy.deepcopy(options) # backup
			options.TXHASHES = [txhash for txhash in additional_required_data]

			# the first pass of the blockchain has already converted
			# options.ENDBLOCKHASH to options.ENDBLOCKNUM via function
			# options_grunt.convert_range_options() so there is no need to worry
			# about getting this wrong if options.START... and options.LIMIT are
			# temporarily removed
			options.STARTBLOCKNUM = 0
			options.STARTBLOCKHASH = None
			options.LIMIT = None

			aux_blocks = extract_full_blocks(options, sanitized, 2)
			options = saved_options # restore

		# update the txin addresses (in all original blocks only)
		if aux_blocks:
			aux_blocks = merge_blocks_ascending(aux_blocks, blocks)
			parsed_blocks = update_txin_data(aux_blocks)

			# at this point we have all data for the user-specified blocks, but
			# we probably also have irrelevant blocks which come before this
			# range. we need to eliminate the irrelevant blocks.

			filtered_blocks = {}
			# loop through all blocks and filter according the specified options
			for block_hash in parsed_blocks:
				block = parsed_blocks[block_hash]
				block_height = block["block_height"]

				# there is no need to convert hash or limit ranges to blocknum
				# ranges using function options_grunt.convert_range_options()
				# since this was already done during the first pass

				# return if we are beyond the specified range
				if after_range(options, block_height):
					break

				# skip the block if we are not yet in range
				if before_range(options, block_height):
					continue

				# if the options specify this block (eg an address that is in
				# this block) then save it
				txin_hashes = None
				(filtered_blocks, txin_hashes) = relevant_block(
					options, filtered_blocks, txin_hashes, block, block_hash,
					block_height
				)

			blocks = filtered_blocks

	# either remove all orphans, or keep only orphans, or do nothing at all
	blocks = filter_orphans(blocks, options)

	if options.OUTPUT_TYPE == "BLOCKS":
		return blocks

	# if the user did not request full blocks then they must have requested
	# either transactions or balances. only transactions are needed from here on
	txs = extract_txs(blocks, options) # as list of dicts

	if options.OUTPUT_TYPE == "TXS":
		return txs

	balances = tx_balances(txs, options.ADDRESSES)

	if options.OUTPUT_TYPE == "BALANCES":
		return balances

	# thanks to sanitization, we will never get to this line

def extract_full_blocks(options, sanitized = False, pass_num = 1):
	"""
	get full blocks which contain the specified addresses, transaction hashes or
	block hashes.
	"""
	# make sure the user input data has been sanitized
	enforce_sanitization(sanitized)

	# if this is the first pass of the blockchain then we will be looking
	# coinbase_maturity blocks beyond the user-specified range so as to check
	# for orphans. once his has been done, it does not need doing again
	seek_orphans = True if (pass_num == 1) else False

	filtered_blocks = {} # init. this is the only returned var
	orphans = init_orphan_list() # list of hashes
	hash_table = init_hash_table()
	block_height = -1 # init
	exit_now = False # init
	txin_hashes = {} # keep tabs on outgoing funds from addresses
	(progress_bytes, full_blockchain_bytes) = maybe_init_progress_meter(options)

	# validation needs to store all unspent txs (slower)
	if options.validate_blocks:
		all_unspent_txs = {}
	
	for block_filename in sorted(glob.glob(
		os.path.expanduser(options.BLOCKCHAINDIR) + blockname_format
	)):
		active_file_size = os.path.getsize(block_filename)
		# blocks_into_file includes orphans, whereas block_height does not
		blocks_into_file = -1 # reset
		bytes_into_file = 0 # reset
		bytes_into_section = 0 # reset
		active_blockchain = "" # init
		fetch_more_blocks = True # TODO - test and clarify doco for this var
		file_handle = open(block_filename)

		# loop within the same block file
		while True:
			# TODO - keep going coinbase_maturity past the final specified block
			# so as to determine whether blocks in the specified range are on
			# the main chain or not

			# either extract block data or move on to the next blockchain file
			(
				fetch_more_blocks, active_blockchain, bytes_into_section
			) = maybe_fetch_more_blocks(
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

			blocks_into_file += 1 # ie 1 = first block in file

			# block as bytes
			block = active_blockchain[bytes_into_section + 8: \
			bytes_into_section + num_block_bytes + 8]

			# update position counters
			bytes_into_section += num_block_bytes + 8
			bytes_into_file += num_block_bytes + 8

			# make sure the block is correct size
			enforce_block_size(
				block, num_block_bytes, block_filename, blocks_into_file
			)
			# get the current and previous hash
			parsed_block = block_bin2dict(
				block, ["block_hash", "previous_block_hash", "timestamp"]
			)
			block_hash = parsed_block["block_hash"]
			previous_block_hash = parsed_block["previous_block_hash"]
			block_time = parsed_block["timestamp"]

			# die if this block has no ancestor
			enforce_ancestor(hash_table, previous_block_hash)

			# update the block height
			block_height = hash_table[previous_block_hash][0] + 1

			# if we are using a progress meter then update it
			progress_bytes = maybe_update_progress_meter(
				options, num_block_bytes, progress_bytes, block_height,
				full_blockchain_bytes
			)
			# update the hash table (contains orphan and main-chain blocks)
			hash_table[block_hash] = [block_height, previous_block_hash]

			# maybe mark off orphans in the parsed blocks and truncate hash
			# table, but only if the hash table is twice the allowed length
			(filtered_blocks, hash_table) = manage_orphans(
				filtered_blocks, hash_table, block_hash, 2
			)

			# convert hash or limit ranges to blocknum ranges
			options = options_grunt.convert_range_options(
				options, block_hash, block_height, block_time
			)

			# return if we are beyond the specified range + coinbase_maturity
			if after_range(options, block_height, seek_orphans):
				exit_now = True # since "break 2" is not possible in python
				break

			# skip the block if we are past the user specified range. note that
			# the only reason to be here is to see if any of the blocks in the
			# range are orphans
			if after_range(options, block_height):
				continue

			# skip the block if we are not yet in range
			if before_range(options, block_height):
				continue

			# validate the blocks if required
			if options.validate_blocks:
				# return unspent txs, die upon error, warn as per options
				all_unspent_txs = validate_blockchain(
					block, all_unspent_txs, hash_table, options
				)

			# if the options specify this block (eg an address that is in this
			# block) then save it
			(filtered_blocks, txin_hashes) = relevant_block(
				options, filtered_blocks, txin_hashes, block, block_hash,
				block_height
			)
			# maybe save the block height. note that this cannot be used as the
			# index due to orphans
			save_block_height(filtered_blocks, block_hash, block_height)

		file_handle.close()
		if exit_now:
			maybe_finalize_progress_meter(options, progress_meter, block_height)

			(filtered_blocks, hash_table) = manage_orphans(
				filtered_blocks, hash_table, block_hash, 1
			)
			# we are beyond the specified block range - exit here
			return filtered_blocks

def maybe_init_progress_meter(options):
	"""
	initialise the progress meter and get the size of all the blockchain
	files combined
	"""
	if not options.progress:
		return (None, None)

	# get the size of all files - only needed for the progress meter 
	full_blockchain_bytes = get_full_blockchain_size(
		os.path.expanduser(options.BLOCKCHAINDIR)
	)
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

def extract_txs(binary_blocks, options):
	"""
	return only the relevant transactions. no progress meter here as this stage
	should be very quick even for thousands of transactions
	"""

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
				options.TXHASHES and \
				parsed_block["tx"][tx_num]["hash"] in options.TXHASHES
			):
				filtered_txs.append(parsed_block["tx"][tx_num])
				continue # on to next tx

			if parsed_block["tx"][tx_num]["input"] is not None:
				for input_num in parsed_block["tx"][tx_num]["input"]:
					if (
						(parsed_block["tx"][tx_num]["input"][input_num] \
						["address"] is not None) and \
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
						["address"] is not None) and \
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
def ensure_block_positions_file_exists():
	" ""make sure the block positions file exists" ""
	try:
		os.makedirs(os.path.dirname(block_positions_file))
	except (OSError, IOError) as e:
		if e.errno != errno.EEXIST: # the problem is not that the dir already exists
			die("there was an error when creating directory %s for storing the block positions in file %s - %s" % (os.path.dirname(block_positions_file), block_positions_file, e))
	# at this point, the directory exists
	try:
		open(block_positions_file, 'a').close()
	except (OSError, IOError) as e:
		lang_grunt.die("could not create the file for storing the block positions - %s" % e)

def extract_coinbase_address(block):
	" ""return the coinbase address in binary"" "
	test_length = block[214:1]
	if test_length != hex2bin("41"):
		lang_grunt.die("could not find coinbase transaction. block: %s" % bin2hex(block))
	ecdsa_pub_key = block[215:65] # coinbase should always be the first transaction
	return pubkey2btc_address(ecdsa_pub_key)

def get_known_block_positions():
	"" " return a list - [[file, position], [file, position], ...] - where list element number = block number"" "
	try:
		f = open(block_positions_file, "r")
	except (OSError, IOError) as e:
		lang_grunt.die("could not open the csv file to read the block positions - %s" % e)
	try:
		r = csv.reader(f, delimiter = ",")
		retval = [row for row in r if row]
	except Exception as e:
		lang_grunt.die("error reading csv file to get the block positions - %s" % e)
	f.close()
	return retval

def update_known_block_positions(extra_block_positions):
	"" "update the block positions file using the input argument list which is in the format [[file, position], [file, position], ...] - where list element number = block number"" "
	try:
		f = open(block_positions_file, "a")
	except (OSError, IOError) as e:
		lang_grunt.die("could not open the csv file to write the block positions - %s" % e)
	try:
		for line in extra_block_positions:
			f.write(",".join(extra_block_positions))
			block_positions.extend(extra_block_positions) # update global var
	except Exception as e:
		lang_grunt.die("error writing the block positions to the csv file - %s" % e)
	f.close()

"""

def before_range(options, block_height):
	"""
	check if the current block is before the range (inclusive) specified by the
	options

	note that function options_grunt.convert_range_options() must be called
	before running this function so as to convert ranges based on hashes or
	limits into ranges based on block numbers.
	"""
	if (
		(options.STARTBLOCKNUM) and \
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

	new_upper_limit = options.ENDBLOCKNUM
	if seek_orphans:
		new_upper_limit += coinbase_maturity
	
	if (
		(options.ENDBLOCKNUM) and \
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

"""
def get_range_data(options):
	" "" get the range data:
	''' start_data = {"file_num": xxx, "byte_num": xxx, "block_num": xxx} or {}
	''' end_data = {"file_num": xxx, "byte_num": xxx, "block_num": xxx} or {}
	" ""
	ensure_block_positions_file_exists() # dies if it does not exist and cannot be created
	block_positions_data = get_known_block_positions() # returns a list: [[file, position], [file, position], ...] where list element number = block number
	start_data = {} # need to figure out the start data based on the argument options
	if not options.STARTBLOCKNUM and not options.STARTBLOCKHASH:
		start_data["file_num"] = 0
		start_data["byte_num"] = 0
		start_data["block_num"] = 0
	if options.STARTBLOCKNUM and (options.STARTBLOCKNUM < len(block_positions_data)): # block_positions_data entry exists
		start_data["file_num"] = block_positions_data[options.STARTBLOCKNUM][0]
		start_data["byte_num"] = block_positions_data[options.STARTBLOCKNUM][1]
		start_data["block_num"] = options.STARTBLOCKNUM
	if options.STARTBLOCKHASH:
		start_data["hash"] = options.STARTBLOCKHASH # no way of knowing the start position without scanning through the blockfiles
	if options.ENDBLOCKNUM and options.LIMIT:
		lang_grunt.die("ENDBLOCKNUM and LIMIT cannot both be specified")
	end_data = {}
	if options.ENDBLOCKNUM:
		end_data["block_num"] = options.ENDBLOCKNUM
	if options.STARTBLOCKNUM and options.LIMIT:
		end_data["block_num"] = options.STARTBLOCKNUM + options.LIMIT
	if ("block_num" in end_data) and (end_data["block_num"] < len(block_positions_data)):
		end_data["file_num"] = block_positions_data[end_data["block_num"]][0]
		end_data["byte_num"] = block_positions_data[end_data["block_num"]][1]
	if options.ENDBLOCKHASH:
		end_data["hash"] = options.ENDBLOCKHASH # no way of knowing the end position without scanning through the blockfiles
	if not options.ENDBLOCKNUM and not options.ENDBLOCKHASH and not options.STARTBLOCKNUM and not options.LIMIT:
		# no range specified = use last possible block
		end_data["file_num"] = float("inf")
		end_data["byte_num"] = float("inf")
		end_data["block_num"] = float("inf")
	return (start_data, end_data)
"""

def whole_block_match(options, block_hash, block_height):
	"""
	check if the user wants the whole block returned

	note that function options_grunt.convert_range_options() must be called
	before running this function so as to convert ranges based on hashes or
	limits into ranges based on block numbers.
	"""

	# if the block is not in the user-specified range then it is not a match.
	if (
		before_range(options, block_height) or \
		after_range(options, block_height)
	):
		return False

	# the user has specified this block via its hash
	if (
		options.BLOCKHASHES and \
		[required_block_hash for required_block_hash in options.BLOCKHASHES \
		if required_block_hash == block_hash]
	):
		return True

	# the user has specified this block by default
	if (
		(not options.BLOCKHASHES) and \
		(not options.TXHASHES) and \
		(not options.ADDRESSES)
	):
		return True

	return False

def relevant_block(
	options, filtered_blocks, txin_hashes, block, block_hash, block_height
):
	"""if the options specify this block then return it"""

	# if the block is not in range then exit here without adding it to the
	# filtered_blocks var. the program searches beyond the user-specified limits
	# to determine whether the blocks in range are orphans or not
	if (
		before_range(options, block_height) or \
		after_range(options, block_height)
	):
		return (filtered_blocks, txin_hashes)

	# check the block hash
	if whole_block_match(options, block_hash, block_height):
		filtered_blocks[block_hash] = block_bin2dict(block, all_block_info)
		return (filtered_blocks, txin_hashes)

	# check the transaction hashes
	if (
		options.TXHASHES and \
		txs_in_block(block, options.TXHASHES)
	):
		filtered_blocks[block_hash] = block_bin2dict(block, all_block_info)
		return (filtered_blocks, txin_hashes)

	# check the address
	if (
		options.ADDRESSES and \
		addresses_in_block(options.ADDRESSES, block)
	):
		filtered_blocks[block_hash] = block_bin2dict(block, all_block_info)
		# get an array of all tx hashes and indexes which contain the specified
		# addresses in their txout scripts in the format {} or {hash1:[index1,
		# index2, ...], hash2:[index1, index2, ...]}
		# note that this tx hash also covers txout addresses not included in
		# options.ADDRESSES
		temp = get_recipient_txhashes(
			options.ADDRESSES, filtered_blocks[block_hash]
		)
		if temp:
			txin_hashes.update(temp)

	# if any txin hash (address receiving funds) is a match
	elif (
		txin_hashes and \
		txin_hashes_in_block(block, txin_hashes)
	):
		filtered_blocks[block_hash] = block_bin2dict(block, all_block_info)
		return (filtered_blocks, txin_hashes)

	return (filtered_blocks, txin_hashes)

def txin_hashes_in_block(block, txin_hashes):
	"""check if any of the txin hashes exist in the transaction inputs"""
	if isinstance(block, dict):
		parsed_block = block # already parsed
	else:
		parsed_block = block_bin2dict(block, ["txin_hash", "txin_index"])

	for tx_num in parsed_block["tx"]:
		if parsed_block["tx"][tx_num]["input"] is None:
			# TODO - test this
			continue
		block_input_dict = parsed_block["tx"][tx_num]["input"] # shorter
		for input_num in block_input_dict:
			if (
				(block_input_dict["hash"] in txin_hashes) and \
				(block_input_dict["index"] in \
				txin_hashes[block_input_dict[input_num]["hash"]])
			):
				return True

	return False

def txs_in_block(block, txhashes):
	"""check if any of the transactions exist in the block"""
	if isinstance(block, dict):
		parsed_block = block # already parsed
	else:
		parsed_block = block_bin2dict(block, ["tx_hash"])

	for tx_num in parsed_block["tx"]:
		txhash = parsed_block["tx"][tx_num]["hash"]
		if [required_tx_hash for required_tx_hash in txhashes \
		if required_tx_hash == txhash]:
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
	parsed_block = block_bin2dict(block, ["txin_address", "txout_address"])
	for tx_num in parsed_block["tx"]:
		if parsed_block["tx"][tx_num]["input"] is not None:
			txin = parsed_block["tx"][tx_num]["input"]
			for input_num in txin:
				if (
					(txin[input_num]["address"] is not None) and \
					(txin[input_num]["address"] in addresses)
				):
					return True

		if parsed_block["tx"][tx_num]["output"] is not None:
			txout = parsed_block["tx"][tx_num]["output"]
			for output_num in txout:
				if (
					(txout[output_num]["address"] is not None) and \
					(txout[output_num]["address"] in addresses)
				):
					return True

def get_recipient_txhashes(addresses, block):
	"""
	get an array of all tx hashes and indexes which contain the specified
	addresses in their txout scripts in the format
	{hash1:[index1, index2, ...], hash2:[index1, index2, ...], ...}
	"""
	if isinstance(block, dict):
		parsed_block = block
	else:
		parsed_block = block_bin2dict(block, ["tx_hash", "txout_address"])
	recipient_tx_hashes = {}
	for tx_num in sorted(parsed_block["tx"]):
		if parsed_block["tx"][tx_num]["output"] is not None:
			indexes = [] # reset
			for output_num in sorted(parsed_block["tx"][tx_num]["output"]):
				if (
					parsed_block["tx"][tx_num]["output"][output_num] \
					["address"] in addresses
				):
					indexes.append(output_num)
			if indexes:
				recipient_tx_hashes[parsed_block["tx"][tx_num]["hash"]] = \
				list(set(indexes)) # unique
	return recipient_tx_hashes

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
	for block_hash in blocks:
		parsed_block = blocks[block_hash]
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
					(prev_hash not in aux_txout_data) or \
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
		(not fetch_more_blocks) and \
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
			% (block_filename, blocks_into_file + 1, block_height + 1)
		)

def enforce_min_chunk_size(
	num_block_bytes, active_blockchain_num_bytes, blocks_into_file,
	block_filename, block_height
):
	"""die if this chunk is smaller than the current block"""
	if (num_block_bytes + 8) > active_blockchain_num_bytes:
		lang_grunt.die(
			"Error: cannot process %s bytes of the blockchain since block %s of"
			" file %s (absolute block num %s) has %s bytes and this program"
			" needs to extract at least one full block, plus its 8 byte header,"
			" at a time (which comes to %s for this block). Please increase the"
			" value of variable 'active_blockchain_num_bytes' at the top of"
			" file btc_grunt.py."
			% (active_blockchain_num_bytes, blocks_into_file + 1,
			block_filename, block_height + 1, num_block_bytes,
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

def save_block_height(filtered_blocks, block_hash, block_height):
	"""
	save the block height. note that the block heigh cannot be used as the index
	in the filtered_blocks array since there may be two blocks of the same
	height (ie one orphan) and so a block would get overwritten when we might
	want to keep it
	"""
	if block_hash in filtered_blocks:
		filtered_blocks[block_hash]["block_height"] = block_height

def block_bin2dict(block, required_info_):
	"""
	extract the specified info from the block into a dictionary and return as
	soon as it is all available
	"""
	block_arr = {} # init

	# copy to avoid altering the argument outside the scope of this function
	required_info = copy.deepcopy(required_info_)

	block_arr["is_orphan"] = None # init

	if "block_hash" in required_info: # extract the block hash from the header
		block_arr["block_hash"] = calculate_block_hash(block)
		required_info.remove("block_hash")
		if not required_info: # no more info required
			return block_arr
	pos = 0

	if "format_version" in required_info:
		block_arr["format_version"] = bin2int(little_endian(block[pos:pos + 4]))
		required_info.remove("format_version")
		if not required_info: # no more info required
			return block_arr
	pos += 4

	if "previous_block_hash" in required_info:
		block_arr["previous_block_hash"] = little_endian(block[pos:pos + 32])
		required_info.remove("previous_block_hash")
		if not required_info: # no more info required
			return block_arr
	pos += 32

	if "merkle_root" in required_info:
		block_arr["merkle_root"] = little_endian(block[pos:pos + 32])
		required_info.remove("merkle_root")
		if not required_info: # no more info required
			return block_arr
	pos += 32

	if "timestamp" in required_info:
		block_arr["timestamp"] = bin2int(little_endian(block[pos:pos + 4]))
		required_info.remove("timestamp")
		if not required_info: # no more info required
			return block_arr
	pos += 4

	if "bits" in required_info:
		block_arr["bits"] = little_endian(block[pos:pos + 4])
		required_info.remove("bits")
		if not required_info: # no more info required
			return block_arr
	pos += 4

	if "nonce" in required_info:
		block_arr["nonce"] = bin2int(little_endian(block[pos:pos + 4]))
		required_info.remove("nonce")
		if not required_info: # no more info required
			return block_arr
	pos += 4

	(num_txs, length) = decode_variable_length_int(block[pos:pos + 9])
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
		(block_arr["tx"][i], length) = tx_bin2dict(block, pos, required_info)

		if not required_info: # no more info required
			return block_arr
		pos += length

	if "block_size" in required_info:
		block_arr["size"] = pos

	if "block_bytes" in required_info:
		block_arr["bytes"] = block

	if len(block) != pos:
		lang_grunt.die(
			"the full block could not be parsed. block length: %s, position: %s"
			% (len(block), pos)
		)
	# we only get here if the user has requested all the data from the block
	return block_arr

def tx_bin2dict(block, pos, required_info):
	"""
	extract the specified transaction info from the block into a dictionary and
	return as soon as it is all available
	"""
	tx = {} # init
	init_pos = pos

	if "tx_version" in required_info:
		tx["version"] = bin2int(little_endian(block[pos:pos + 4]))
	pos += 4

	(num_inputs, length) = decode_variable_length_int(block[pos:pos + 9])
	if "num_tx_inputs" in required_info:
		tx["num_inputs"] = num_inputs
	pos += length

	tx["input"] = {} # init
	for j in range(0, num_inputs): # loop through all inputs
		tx["input"][j] = {} # init

		if "txin_verification_attempted" in required_info:
			# indicates whether we have tried to verify the funds and address of
			# this txin
			tx["input"][j]["verification_attempted"] = False

		if "txin_verification_succeeded" in required_info:
			# indicates whether the transaction is valid (can still be true even
			# if this is an orphan block)
			tx["input"][j]["verification_succeeded"] = False

		if "txin_funds" in required_info:
			tx["input"][j]["funds"] = None

		if "txin_hash" in required_info:
			tx["input"][j]["hash"] = little_endian(block[pos:pos + 32])
		pos += 32

		if "txin_index" in required_info:
			tx["input"][j]["index"] = bin2int(little_endian(block[pos:pos + 4]))
		pos += 4

		(txin_script_length, length) = decode_variable_length_int(
			block[pos:pos + 9]
		)
		if "txin_script_length" in required_info:
			tx["input"][j]["script_length"] = txin_script_length
		pos += length

		if (
			("txin_script" in required_info) or \
			("txin_address" in required_info) or \
			("txin_parsed_script" in required_info)
		):
			input_script = block[pos:pos + txin_script_length]
		pos += txin_script_length

		if "txin_script" in required_info:
			tx["input"][j]["script"] = input_script

		if "txin_parsed_script" in required_info:
			# convert string of bytes to list of bytes
			script_elements = script_bin2list(input_script)

			# convert list of bytes to human readable string
			tx["input"][j]["parsed_script"] = script_list2human_str(
				script_elements
			)

		# get the txin address if possible. note that this should not be trusted
		# until it has been verified against the previous txout script
		if "txin_address" in required_info:
			tx["input"][j]["address"] = script2btc_address(input_script)

		if "txin_sequence_num" in required_info:
			tx["input"][j]["sequence_num"] = bin2int(little_endian(
				block[pos:pos + 4]
			))
		pos += 4

		if not len(tx["input"][j]):
			del tx["input"][j]

	if not len(tx["input"]):
		del tx["input"]

	(num_outputs, length) = decode_variable_length_int(block[pos:pos + 9])
	if "num_tx_outputs" in required_info:
		tx["num_outputs"] = num_outputs
	pos += length

	tx["output"] = {} # init
	for k in range(0, num_outputs): # loop through all outputs
		tx["output"][k] = {} # init

		if "txout_funds" in required_info:
			tx["output"][k]["funds"] = bin2int(little_endian(
				block[pos:pos + 8]
			))
		pos += 8

		(txout_script_length, length) = decode_variable_length_int(
			block[pos:pos + 9]
		)
		if "txout_script_length" in required_info:
			tx["output"][k]["script_length"] = txout_script_length
		pos += length

		if (
			("txout_script" in required_info) or \
			("txout_address" in required_info) or \
			("txout_parsed_script" in required_info)
		):
			output_script = block[pos:pos + txout_script_length]
		pos += txout_script_length	

		if "txout_script" in required_info:
			tx["output"][k]["script"] = output_script

		if "txout_parsed_script" in required_info:
			# convert string of bytes to list of bytes
			script_elements = script_bin2list(output_script)

			# convert list of bytes to human readable string
			tx["output"][k]["parsed_script"] = script_list2human_str(
				script_elements
			)

		if "txout_address" in required_info:
			# return btc address or None
			tx["output"][k]["address"] = script2btc_address(output_script)

		if not len(tx["output"][k]):
			del tx["output"][k]

	if not len(tx["output"]):
		del tx["output"]

	if "tx_lock_time" in required_info:
		tx["lock_time"] = bin2int(little_endian(block[pos:pos + 4]))
	pos += 4

	if ("tx_bytes" in required_info) or ("tx_hash" in required_info):
		tx_bytes = block[init_pos:pos]

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

	global blank_hash

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
		output = output[:36] + merkle_root + output[68:]
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
		tx_errors = validate_transaction_elements_type_len(tx_arr)
		if tx_errors:
			if bool_result:
				return False
			errors = list(set(errors + tx_errors)) # unique

	if (
		not errors and \
		bool_result
	):
		errors = True # block is valid
	return errors

def validate_transaction_elements_type_len(tx_arr, bool_result = False):
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
				script_length_ok and \
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
				script_length_ok and \
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
		not errors and \
		bool_result
	):
		errors = True # block is valid
	return errors

"""def check_block_elements_exist(block, required_block_elements):
	" ""return true if all the elements in the input list exist in the block, else false" ""
	if isinstance(block, dict):
		parsed_block = block
	else:
		parsed_block = block_bin2dict(block, required_block_elements)
	header_elements = [el for el in required_block_elements if el in block_header_info]
	if [el for el in header_elements if el not in parsed_block]:
		return False
	tx_elements = [el for el in required_block_elements if el in all_tx_info]
	if not tx_elements: # no tx elements are required
		return True
	if ("num_txs" in required_block_elements) and ("num_txs" not in parsed_block):
		return False
	required_txin_info = [el for el in required_block_elements if el in all_txin_info]
	required_txout_info = [el for el in required_block_elements if el in all_txout_info]
	all_remaining_tx_info = remaining_tx_info[:] # TODO - replace with deepcopy
	all_remaining_tx_info.remove("num_txs")
	required_tx_info = [el for el in required_block_elements if el in remaining_tx_info]
	for tx_num in parsed_block["tx"]: # there will always be at least one transaction per block
		if required_tx_info and [el for el in required_tx_info if el not in parsed_block["tx"][tx_num]]:
			return False
		for input_num in parsed_block["tx"][tx_num]["input"]:
			if required_txin_info and [el.replace("txin_", "") for el in required_txin_info if el not in parsed_block["tx"][tx_num]["input"][input_num]]:
				return False
		for output_num in parsed_block["tx"][tx_num]["output"]:
			if required_txin_info and [el.replace("txout_", "") for el in required_txout_info if el not in parsed_block["tx"][tx_num]["output"][output_num]]:
				return False
	return True
"""

def human_readable_block(block):
	"""take the input binary block and return a human readable dict"""
	output_info = copy.deepcopy(all_block_info)

	# the parsed script will still be returned, but these raw scripts will not
	output_info.remove("txin_script")
	output_info.remove("txout_script")
	output_info.remove("tx_bytes")

	# bin encoded string to a dict (some elements still not human readable)
	parsed_block = block_bin2dict(block, output_info)

	# convert any remaining binary encoded elements
	parsed_block["block_hash"] = bin2hex(parsed_block["block_hash"])
	parsed_block["previous_block_hash"] = bin2hex(
		parsed_block["previous_block_hash"]
	)
	parsed_block["merkle_root"] = bin2hex(parsed_block["merkle_root"])
	parsed_block["bits"] = bin2int(parsed_block["bits"])

	# there will always be at least one transaction per block
	for tx_num in parsed_block["tx"]:
		tx = parsed_block["tx"][tx_num]
		parsed_block["tx"][tx_num]["hash"] = bin2hex(tx["hash"])
		for input_num in tx["input"]:
			parsed_block["tx"][tx_num]["input"][input_num]["hash"] = bin2hex(
				tx["input"][input_num]["hash"]
			)

	return parsed_block

def human_readable_tx(tx):
	"""take the input binary tx and return a human readable dict"""
	output_info = all_tx_info.deepcopy()

	# the parsed script will still be returned, but these raw scripts will not
	output_info.remove("txin_script")
	output_info.remove("txout_script")
	output_info.remove("tx_bytes")

	# bin encoded string to a dict (some elements still not human readable)
	(parsed_tx, _) = tx_bin2dict(tx, 0, output_info)

	# convert any remaining binary encoded elements
	parsed_tx["hash"] = bin2hex(parsed_tx["hash"])

	# the output is already fine, just clean up the input hash
	for input_num in parsed_tx["input"]:
		txin_i = parsed_tx["input"][input_num]
		parsed_tx["input"][input_num]["hash"] = bin2hex(txin_i["hash"])

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
	to_address_hashed = btc_address2hash160(to_address)
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
			not relevant_tx and \
			options.TXHASHES and \
			[txhash for txhash in options.TXHASHES if txhash == tx["hash"]]
		):
			relevant_tx = True

		for input_num in tx["input"]:
			txin = tx["input"][input_num]
			prev_txout_hash = txin["hash"]

			# if we already have the input address the skip this txin
			if (
				"address" in txin and \
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

def valid_block_nonce(block):
	"""
	return True if the block has a valid nonce, else False. the hash must be
	below the target (derived from the bits). block input argument must be
	 binary bytes.
	"""
	if isinstance(block, dict):
		parsed_block = block
	else:
		parsed_block = block_bin2dict(block, ["block_hash", "bits"])
	target = target_bin2int(parsed_block["bits"])

	# debug use only
	# print "target:     %s,\nblock hash: %s" % (int2hex(target),
	# bin2hex(parsed_block["block_hash"]))
	#raw_input() # pause for keypress

	if bin2int(parsed_block["block_hash"]) < target: # hash must be below target
		return True
	else:
		return False

def valid_merkle_tree(block):
	"""
	return True if the block has a valid merkle root, else False. block input
	argument must be binary bytes.
	"""
	if isinstance(block, dict):
		parsed_block = block
	else:
		parsed_block = block_bin2dict(block, ["merkle_root", "tx_hash"])
	merkle_leaves = []

	# there will always be at least one transaction per block
	for tx_num in sorted(parsed_block["tx"]):
		if parsed_block["tx"][tx_num]["hash"] is not None:
			merkle_leaves.append(parsed_block["tx"][tx_num]["hash"])

	if calculate_merkle_root(merkle_leaves) == parsed_block["merkle_root"]:
		return True
	else:
		return False

def target_bin2int(bits_bytes):
	"""calculate the decimal target given the 'bits' bytes"""
	exp = bin2int(bits_bytes[:1]) # exponent is the first byte
	mult = bin2int(bits_bytes[1:]) # multiplier is all but the first byte
	return mult * (2 ** (8 * (exp - 3)))

def calc_difficulty(bits_bytes):
	"""calculate the decimal difficulty given the 'bits' bytes"""
	# difficulty_1 = target_bin2int(hex2bin("1d00ffff"))
	difficulty_1 = 0x00000000ffff0000000000000000000000000000000000000000000000000000
	return difficulty_1 / float(target_bin2int(bits_bytes))

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

def script2btc_address(script):
	"""extract the bitcoin address from the binary script (input or output)"""
	format_type = extract_script_format(script)
	if not format_type:
		return None

	# OP_PUSHDATA0(65) <pubkey> OP_CHECKSIG
	if format_type == "pubkey":
		output_address = pubkey2btc_address(script_bin2list(script)[1])

	# OP_DUP OP_HASH160 OP_PUSHDATA0(20) <hash160> OP_EQUALVERIFY OP_CHECKSIG
	elif format_type == "hash160":
		output_address = hash1602btc_address(script_bin2list(script)[3])

	# OP_PUSHDATA0(73) <signature> OP_PUSHDATA0(65) <pubkey>
	elif format_type == "sigpubkey":
		output_address = pubkey2btc_address(script_bin2list(script)[3])
	else:
		lang_grunt.die("unrecognized format type %s" % format_type)
	return output_address

def extract_script_format(script):
	"""carefully extract the format for the input (binary string) script"""
	recognized_formats = {
		"pubkey": [
			opcode2bin("OP_PUSHDATA0(65)"),
			"pubkey",
			opcode2bin("OP_CHECKSIG")
		],
		"hash160": [
			opcode2bin("OP_DUP"),
			opcode2bin("OP_HASH160"),
			opcode2bin("OP_PUSHDATA0(20)"),
			"hash160",
			opcode2bin("OP_EQUALVERIFY"),
			opcode2bin("OP_CHECKSIG")
		],
		"sigpubkey": [
			opcode2bin("OP_PUSHDATA0(73)"),
			"signature",
			opcode2bin("OP_PUSHDATA0(65)"),
			"pubkey"
		]
	}
	script_list = script_bin2list(script) # explode

	for (format_type, format_opcodes) in recognized_formats.items():

		# try next format
		if len(format_opcodes) != len(script_list):
			continue

		for (format_opcode_el_num, format_opcode) in enumerate(format_opcodes):
			if format_opcode == script_list[format_opcode_el_num]:
				confirmed_format = format_type
			elif (
				(format_opcode_el_num in [1, 3]) and \
				(format_opcode == "pubkey") and \
				(len(script_list[format_opcode_el_num]) == 65)
			):
				confirmed_format = format_type
			elif (
				(format_opcode_el_num == 3) and \
				(format_opcode == "hash160") and \
				(len(script_list[format_opcode_el_num]) == 20)
			):
				confirmed_format = format_type
			elif (
				(format_opcode_el_num == 1) and \
				(format_opcode == "signature") and \
				(len(script_list[format_opcode_el_num]) == 73)
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

def validate_blockchain(
	block, block_height, all_unspent_txs, hash_table, target_data, options
):
	"""
	take the latest block and perform comprehensive validations on it.

	if the block is part of the main blockchain (i.e. it is not an orphan) but 
	fails to validate then die with an explantion of the error.

	if the block is an orphan and the options.explain flag is set then output
	an explanation of the error but do not die.

	"""

	bool_result = False # we want a list of text as output, not bool
	(errors, all_unspent_txs) = validate_block(
		block, all_unspent_txs, target_data, all_validation_info,
		bool_result
	)
	if not errors:
		return True # the block is valid
	
	return (
		"Errors found while validating block %s:\n%s"
		% (block_height, "\n\t- ".join(errors))
	)

def valid_block(
	block, all_unspent_txs, target_data, block_height, validate_info,
	bool_result = False
):
	"""
	validate a block without knowing whether it is an orphan or is part of the
	main blockchain.

	if the bool_result argument is set then return True for a valid block and
	False for an invalid block.

	if the bool_result argument is not set then	return a list of errors for an
	invalid block, otherwise None for a valid block.

	based on https://en.bitcoin.it/wiki/Protocol_rules
	"""

	if isinstance(block, dict):
		parsed_block = block
	else:
		parsed_block = block_bin2dict(block, all_block_info)

	if not bool_result:
		errors = []

	# make sure the block is smaller than the permitted maximum
	if parsed_block["size"] > max_block_size:
		errors.append(
			"Error: block size (%s bytes) is larger than the maximum permitted"
			"size of %s bytes."
			% (parsed_block["size"], max_block_size)
		)

	# make sure the transaction hashes form the merkle root when sequentially
	# hashed together
	merkle_leaves = [tx["hash"] for tx in parsed_block["tx"].values()]
	calculated_merkle_root = calculate_merkle_root(merkle_leaves)
	if calculated_merkle_root != parsed_block["merkle_root"]:
		if bool_result:
			return False
		errors.append(
			"Error: merkle tree validation failure. Calculated merkle root %s,"
			" but block header has merkle root %s."
			% (bin2hex(calculated_merkle_root),
			bin2hex(parsed_block["merkle_root"]))
		)

	# make sure the target is valid based on previous network hash performance
	(old_target, old_target_time) = retrieve_target_data(
		target_data, block_height
	)
	calculated_target = new_target(
		old_target, old_target_time, block["timestamp"]
	)
	if calculated_target != parsed_block["bits"]:
		if bool_result:
			return False
		errors.append(
			"Error: target validation failure. Target should be %s, however it"
			" is %s."
			% (bin2hex(calculated_target), target_bin2int(parsed_block["bits"]))
		)

	# make sure the block hash is below the target
	target = target_bin2int(parsed_block["bits"]) # as decimal int
	block_hash_as_int = bin2int(parsed_block["block_hash"])
	if block_hash_as_int > target:
		if bool_result:
			return False
		errors.append(
			"Error: block hash validation failure. Block hash %s (int: %s) is"
			" greater than the target %s (int: %s)."
			% (parsed_block["block_hash"], block_hash_as_int,
			parsed_block["bits"], target)
		)

	# make sure the difficulty is valid	
	difficulty = calc_difficulty(parsed_block["bits"])
	if difficulty < 1:
		if bool_result:
			return False
		errors.append(
			"Error: difficulty validation failure. Difficulty is %s but should"
			" not be less than 1."
			% difficulty
		)

	# use this var because we don't want to remove (ie spend) entries from
	# all_unspent_txs until we know that the whole block is valid (ie that the
	# funds are permitted to be spent), and also because making a copy of
	# all_unspent_txs would be very slow (it is an extremely large dict)
	spent_txs = {}

	# calculate coinbase funds using blockheight and each txout - txin
	permitted_coinbase_funds = 0

	for tx_num in sorted(parsed_block["tx"]):
		txins_exist = False
		txin_funds_tx_total = 0

		# make sure each transaction time is valid
		if parsed_block["tx"]["lock_time"] > bin2int(int_max):
			errors.append(
				"Error: transaction lock time must be less than %s"
				% bin2int(int_max)
			)

		# the first transaction is always coinbase (mined)
		is_coinbase = True if tx_num == 0 else False

		for txin_num in sorted(parsed_block["tx"][tx_num]["input"]):
			txins_exist = True
			prev_hash = parsed_block["tx"][tx_num]["input"][txin_num]["hash"]
			index = parsed_block["tx"][tx_num]["input"][txin_num]["index"]
			if (prev_hash in spent_txs) and (index in spent_txs[prev_hash]):
				errors.append(
					"Error: doublespend failure. Previous transaction with hash"
					" %s and index %s has already been spent within this block."
					% (bin2hex(prev_hash), index)
				)
			if is_coinbase:
				if prev_hash != blank_hash:
					errors.append(
						"Error: the coinbase transaction should reference"
						" previous hash %s but it actually references %s."
						% (bin2hex(blank_hash), bin2hex(prev_hash))
					)
				if index != coinbase_index:
					errors.append(
						"Error: the coinbase transaction should reference"
						" previous index %s but it actually references %s."
						% (coinbase_index, index)
					)
				txin_funds_tx_total += mining_reward(block_height)
				# no more checks required for coinbase transactions
				continue

			if prev_hash == blank_hash:
				errors.append(
					"Error: found a non-coinbase transaction with a blank hash"
					" - %s. This is not permitted."
					% bin2hex(blank_hash)
				)
			if index == coinbase_index:
				errors.append(
					"Error: found a non-coinbase transaction with an index of"
					"%s. This is not permitted."
					% bin2hex(coinbase_index)
				)
			if (
				(prev_hash not in all_unspent_txs) or \
				(index not in all_unspent_txs[prev_hash])
			):
				errors.append(
					"Error: doublespend failure. Previous transaction with hash"
					" %s and index %s has already been spent in a previous"
					" block."
					% (bin2hex(prev_hash), index)
				)
				# move to next txin since this one is totally invalid 
				continue

			# the previous transaction exists to be spent now
			from_script = all_unspent_txs[prev_hash][index]["script"]
			from_funds = all_unspent_txs[prev_hash][index]["funds"]
			from_address = all_unspent_txs[prev_hash][index]["address"]
			if checksig(parsed_block["tx"][tx_num], from_script, txin_num):
				txin_funds_tx_total += from_funds
				spent_txs[prev_hash] = {index: True}
			else:
				errors.append(
					"Error: checksig failure for input %s in transaction %s"
					" against transaction with hash %s and index %s."
					% (txin_num, tx_num, bin2hex(prev_hash), index)
				)
			# if a coinbase transaction is being spent then make sure it has
			# already reached maturity
			if (
				all_unspent_txs[prev_hash][index]["is_coinbase"] and \
				(block_height - all_unspent_txs[prev_hash][index] \
				["block_height"]) > coinbase_maturity
			):
				errors.append(
					"Error: it is not permissible to spend coinbase funds until"
					" they have reached maturity (ie %s confirmations). This"
					" transaction attempts to spend coinbase funds after only"
					" %s confirmations."
					% (coinbase_maturity, block_height - all_unspent_txs \
					[prev_hash][index]["block_height"])
				)
				
		if not txins_exist:
			errors.append(
				"Error: there are no txins for transaction %s (hash %s)."
				% (tx_num, bin2hex(tx_hash))
			)
		txouts_exist = False
		txout_funds_tx_total = 0
		for txout_num in parsed_block["tx"][tx_num]["output"]:
			txouts_exist = True
			txout_funds_tx_total += parsed_block["tx"][tx_num]["output"] \
				[txout_num]["funds"]
			if not extract_script_format(
				parsed_block["tx"][tx_num]["output"][txout_num]["script"]
			):
				errors.append(
					"Error: unrecognized script format %s."
					% script_list2human_str(script_bin2list(
						parsed_block["tx"][tx_num]["output"][txout_num] \
						["script"]
					))
				)

		if not txouts_exist:
			errors.append(
				"Error: there are no txouts for transaction %s (hash %s)."
				% (tx_num, bin2hex(tx_hash))
			)
		if txout_funds_tx_total > txin_funds_tx_total:
			errors.append(
				"Error: there are more txout funds (%s) than txin funds (%s) in"
				" transaction %s "
				% (txout_funds_tx_total, txin_funds_tx_total, tx_num)
			)
		if is_coinbase:
			spent_coinbase_funds = txout_funds_tx_total # save for later

		permitted_coinbase_funds += (txout_funds_tx_total - txin_funds_tx_total)

	if spent_coinbase_funds > permitted_coinbase_funds:
		errors.append(
			"Error: this block attempts to spend %s coinbase funds but only %s"
			" are available to spend"
			% (spent_coinbase_funds, permitted_coinbase_funds)
		)

	# once we get here we know that the block is perfect, so it is safe to
	# delete any spent transactions from the all_unspent_txs pool, before
	# returning it
	for tx_num in parsed_block["tx"]:
		for txin_num in parsed_block["tx"][tx_num]["input"]:
			prev_hash = parsed_block["tx"][tx_num]["input"][txin_num]["hash"]
			index = parsed_block["tx"][tx_num]["input"][txin_num]["index"]
			del all_unspent_txs[prev_hash][index]
			if not len(all_unspent_txs[prev_hash]):
				del all_unspent_txs[prev_hash]

	return (errors, all_unspent_txs)

def checksig(new_tx, prev_txout_script, validate_txin_num):
	"""take the entire chronologically later transaction and validate it against the script from the previous txout"""
	# TODO - pass in dict of prev_txout_scrpts for each new_tx input in the format {"txhash-index": script, "txhash-index": script, ...}
	# https://en.bitcoin.it/wiki/OP_CHECKSIG
	# http://bitcoin.stackexchange.com/questions/8500/
	temp = script_list2human_str(script_bin2list(prev_txout_script))
	new_txin_script_elements = script_bin2list(new_tx["input"][validate_txin_num]["script"]) # assume OP_PUSHDATA0(73) <signature>
	if extract_script_format(prev_txout_script) == "pubkey": # OP_PUSHDATA0(65) <pubkey> OP_CHECKSIG early transactions were sent directly to public keys (as opposed to the sha256 hash of the public key). it is slightly more risky to leave public keys in plain sight for too long, incase supercomputers factorize the private key and steal the funds. however later transactions onlyreveal the public key when spending funds into a new address (for which only the sha256 hash of the public key is known), which is much safer - an attacker would need to factorize the private key from the public key within a few blocks duration, then attempt to fork the chain if they wanted to steal funds this way - very computationally expensive.
		pubkey = script_bin2list(prev_txout_script)[1]
	elif extract_script_format(new_tx["input"][validate_txin_num]["script"]) == "pubkey": # OP_PUSHDATA0(65) <pubkey> OP_CHECKSIG
		pubkey = new_txin_script_elements[1]
	elif extract_script_format(new_tx["input"][validate_txin_num]["script"]) == "sigpubkey": # OP_PUSHDATA0(73) <signature> OP_PUSHDATA0(65) <pubkey>
		pubkey = new_txin_script_elements[3]
	else:
		lang_grunt.die("could not find a public key to use for the checksig")
	codeseparator_bin = opcode2bin("OP_CODESEPARATOR")
	if codeseparator_bin in prev_txout_script:
		prev_txout_script_list = script_bin2list(prev_txout_script)
		last_codeseparator = -1
		for (i, data) in enumerate(prev_txout_script_list):
			if data == codeseparator_bin:
				last_codeseparator = i
		prev_txout_subscript = "".join(prev_txout_script_list[last_codeseparator + 1:])
	else:
		prev_txout_subscript = prev_txout_script
	if "OP_PUSHDATA" not in bin2opcode(new_txin_script_elements[0]):
		lang_grunt.die("bad input script - it does not start with OP_PUSH: %s" % script_list2human_str(new_txin_script_elements))
	new_txin_signature = new_txin_script_elements[1]
	if bin2int(new_txin_signature[-1]) != 1:
		lang_grunt.die("unexpected hashtype found in the signature in the new tx input script while performing checksig")
	hashtype = little_endian(int2bin(1, 4)) # TODO - support other hashtypes
	new_txin_signature = new_txin_signature[:-1] # chop off the last (hash type) byte
	new_tx_copy = new_tx.deepcopy()
	# del new_tx_copy["bytes"], new_tx_copy["hash"] # debug only - make output more readable
	for input_num in new_tx_copy["input"]: # initially clear all input scripts
		new_tx_copy["input"][input_num]["script"] = ""
		new_tx_copy["input"][input_num]["script_length"] = 0
		# del new_tx_copy["input"][input_num]["parsed_script"] # debug only - make output more readable
	# for output_num in new_tx_copy["output"]: # debug only - make output more readable
		# del new_tx_copy["output"][output_num]["parsed_script"] # debug only - make output more readable
	new_tx_copy["input"][validate_txin_num]["script"] = prev_txout_subscript
	new_tx_copy["input"][validate_txin_num]["script_length"] = len(prev_txout_subscript)
	new_tx_hash = sha256(sha256(tx_dict2bin(new_tx_copy) + hashtype))

	key = ecdsa_ssl.key()
	key.set_pubkey(pubkey)
	return key.verify(new_tx_hash, new_txin_signature)

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
		block_dict = block_bin2dict(block)

	nonce = 0
	while True:
		# increment the nonce until we find a value which gives a valid hash
		while nonce <= 0xffffffff: # max nonce = 4 bytes
			print "try nonce %s" % nonce
			header = partial_block_header_bin + int2bin(nonce, 4)
			if valid_block_nonce(header):
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
	"""
	two_weeks = 14 * 24 * 60 * 60 # in seconds
	time_diff = new_target_time - old_target_time
	return old_target * time_diff / two_weeks

def pubkey2btc_address(pubkey):
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
	return hash1602btc_address(ripemd160(sha256(pubkey)))

def btc_address2hash160(btc_address):
	"""
	from https://github.com/gavinandresen/bitcointools/blob/master/base58.py
	"""
	bytes = base58decode(btc_address)
	return bytes[1:21]

def hash1602btc_address(hash160):
	"""
	convert the hash160 output (bytes) to the bitcoin address (ascii string)
	https://en.bitcoin.it/wiki/Technical_background_of_Bitcoin_addresses
	"""
	temp = chr(0) + hash160 # 00010966776006953d5567439e5e39f86a0d273bee
	checksum = sha256(sha256(temp))[:4] # checksum is the first 4 bytes
	hex_btc_address = bin2hex(temp + checksum) # 00010966776006953d5567439e5e39f86a0d273beed61967f6
	decimal_btc_address = int(hex_btc_address, 16) # 25420294593250030202636073700053352635053786165627414518

	return version_symbol('ecdsa_pub_key_hash') + \
	base58encode(decimal_btc_address) # 16UwLL9Risc3QfPqBUvKofHmBQ7wMtjvM

def encode_variable_length_int(value):
	"""encode a value as a variable length integer"""
	if value < 253: # encode as a single byte
		bytes = int2bin(value)
	elif value < 0xffff: # encode as 1 format byte and 2 value bytes
		bytes = int2bin(253) + int2bin(value)
	elif value < 0xffffffff: # encode as 1 format byte and 4 value bytes
		bytes = int2bin(254) + int2bin(value)
	elif value < 0xffffffffffffffff: # encode as 1 format byte and 8 value bytes
		bytes = int2bin(255) + int2bin(value)
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

def manage_orphans(filtered_blocks, hash_table, block_hash, mult):
	"""
	if the hash table grows to mult * coinbase_maturity size then:
	- detect any orphans in the hash table
	- mark off these orphans in the blockchain (filtered_blocks)
	- truncate the hash table back to coinbase_maturity size again
	tune mult according to whatever is faster. this probably
	"""
	if len(hash_table) > int(mult * coinbase_maturity):
		# the only way to know if it is an orphan block is to wait
		# coinbase_maturity blocks after a split in the chain.
		orphans = detect_orphans(hash_table, block_hash, coinbase_maturity)

		# mark off any orphans in the blockchain
		if orphans:
			filtered_blocks = mark_orphans(filtered_blocks, orphans)

		# truncate the hash table to coinbase_maturity hashes length so as not
		# to use up too much ram
		hash_table = truncate_hash_table(hash_table, coinbase_maturity)

	return (filtered_blocks, hash_table)

def detect_orphans(hash_table, latest_block_hash, threshold_confirmations = 0):
	"""
	look back through the hash_table for orphans. if any are found then	return
	them in a list.
	the threshold_confirmations argument specifies the number of confirmations
	to wait before marking a hash as an orphan.
	"""
	# remember, hash_table is in the format {hash: [block_height, prev_hash]}
	inverted_hash_table = {v[0]: k for (k,v) in hash_table.items()}
	if len(inverted_hash_table) == len(hash_table):
		# there are no orphans
		return None

	# if we get here then some orphan blocks exist. now find their hashes...
	orphans = hash_table.deepcopy()
	top_block_height = hash_table[latest_block_height][0]
	previous_hash = latest_block_hash # needed to start the loop correctly
	while previous_hash in hash_table:
		this_hash = previous_hash
		this_block_height = hash_table[this_hash][0]
		if (
			(threshold_confirmations > 0) and \
			((top_block_height - this_block_height) >= threshold_confirmations)
		):
			del orphans[this_hash]
		previous_hash = hash_table[this_hash][1]

	# anything not deleted from the orphans dict is now an orphan
	return [block_hash for block_hash in orphans]

def mark_orphans(filtered_blocks, orphans):
	"""mark the specified blocks as orphans"""
	for orphan_hash in orphans:
		if orphan_hash in filtered_blocks:
			filtered_blocks[orphan_hash]["is_orphan"] = True

	# not really necessary since dicts are immutable. still, it makes the code
	# more readable
	return filtered_blocks

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
			valid_block_nonce(blocks[block_hash])
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
			not valid_block_nonce(blocks[block_hash])
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
			addresses.append(pubkey2btc_address(hex2bin(address)))

	return addresses

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
	 http://darklaunch.com/2009/08/07/base58-encode-and-decode-using-php-with-example-base58-encode-base58-decode using bcmath
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

	if address[0] == "1": # bitcoin eg 17VZNX1SN5NtKa8UQFxwQbFeFc3iqRYhem
		if len(address) != 34:
			lang_grunt.die(
				"address %s looks like a bitcoin public key hash, but does not"
				" have the necessary 34 characters"
				% address
			)
		return "bitcoin pubkey hash"

	if address[0] == "3": # bitcoin eg 3EktnHQD7RiAE6uzMj2ZifT9YgRrkSgzQX
		if len(address) != 34:
			lang_grunt.die(
				"address %s looks like a bitcoin script hash, but does not have"
				" the necessary 34 characters"
				% address
			)
		return "bitcoin script hash"

	if address[0] == "L": # litecoin eg LhK2kQwiaAvhjWY799cZvMyYwnQAcxkarr
		if len(address) != 34:
			lang_grunt.die(
				"address %s looks like a litecoin public key hash, but does not"
				" have the necessary 34 characters"
				% address
			)
		return "litecoin pubkey hash"

	if address[0] in ["M", "N"]: # namecoin eg NATX6zEUNfxfvgVwz8qVnnw3hLhhYXhgQn
		if len(address) != 34:
			lang_grunt.die(
				"address %s looks like a namecoin public key hash, but does not"
				" have the necessary 34 characters"
				% address
			)
		return "namecoin pubkey hash"

	if address[0] in ["m", "n"]: # bitcoin testnet eg mipcBbFg9gMiCh81Kj8tqqdgoZub1ZJRfn
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
	for filename in sorted(glob.glob(blockchain_dir + 'blk[0-9]*.dat')):
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

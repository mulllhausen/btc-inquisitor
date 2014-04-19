"""module containing some general bitcoin-related functions"""

import sys, pprint, time, binascii, hashlib, re, ast, glob, os, errno, progress_meter, csv, psutil, ecdsa_ssl

n = "\n"
active_blockchain_num_bytes = 5735#1024 * 1024 # the number of bytes to process in ram at a time. never set this < 1MB (1MB == 1024 * 1024 bytes == 1048576 bytes)
magic_network_id = "f9beb4d9"
confirmations = 120 # default
satoshi = 100000000 # the number of satoshis per btc
base58alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
validate_nonce = False # turn on to make sure the nonce checks out
block_positions_file = os.path.expanduser("~/.btc-inquisitor/block_positions.csv")
block_positions = [] # init
block_header_info = ["block_hash", "format_version", "previous_block_hash", "merkle_root", "timestamp", "bits", "nonce", "block_size", "block_bytes"]
all_txin_info = ["txin_hash", "txin_index", "txin_script_length", "txin_script", "txin_parsed_script", "txin_address", "txin_sequence_num"]
all_txout_info = ["txout_btc", "txout_script_length", "txout_script", "txout_address", "txout_parsed_script"]
remaining_tx_info = ["num_txs", "tx_version", "num_tx_inputs", "num_tx_outputs", "tx_lock_time", "tx_hash", "tx_bytes", "tx_size"]
all_tx_info = all_txin_info + all_txout_info + remaining_tx_info
all_block_info = block_header_info + all_tx_info

def sanitize_globals():
	"""always run this at the start"""
	global magic_network_id

	if active_blockchain_num_bytes < 1:
		die("Error: Cannot process %s bytes of the blockchain - this number is too small! Please increase the value of variable 'active_blockchain_num_bytes' at the top of file btc_grunt.py." % active_blockchain_num_bytes)
	if active_blockchain_num_bytes > (psutil.virtual_memory().free / 3): # 3 seems like a good safety factor
		die("Error: Cannot process %s bytes of the blockchain - not enough ram! Please lower the value of variable 'active_blockchain_num_bytes' at the top of file btc_grunt.py." % active_blockchain_num_bytes)

	magic_network_id = hex2bin(magic_network_id)

def sanitize_options_or_die():
	"""sanitize the options global - may involve updating it"""

	global n, options
	n = "\n" if options.progress else ""

	if options.ADDRESSES:
		if options.ADDRESSES[-1] == ",":
			die("Error: Trailing comma found in the ADDRESSES input argument. Please ensure there are no spaces in the ADDRESSES input argument.")
		currency_types = {}
		first_currency = ""
		for address in options.ADDRESSES.split(","):
			currency_types[address] = get_currency(address)
			if currency_types[address] == "any":
				del currency_types[address]
				continue
			if not first_currency:
				first_currency = currency_types[address]
				continue
			if first_currency != currency_types[address]:
				die("Error: All supplied addresses must be of the same currency:\n%s" % pprint.pformat(currency_types, width = -1))
		options.ADDRESSES = [address for address in options.ADDRESSES.split(",")] # string to list

	if options.TXHASHES is not None:
		if options.TXHASHES[-1] == ",":
			die("Error: Trailing comma found in the TXHASHES input argument. Please ensure there are no spaces in the TXHASHES input argument.")
		for tx_hash in options.TXHASHES.split(","):
			if not valid_hash(tx_hash):
				die("Error: Supplied transaction hash %s is not in the correct format." % tx_hash)
		options.TXHASHES = [hex2bin(txhash) for txhash in options.TXHASHES.split(",")] # string to list

	if options.BLOCKHASHES is not None:
		if options.BLOCKHASHES[-1] == ",":
			die("Error: Trailing comma found in the BLOCKHASHES input argument. Please ensure there are no spaces in the BLOCKHASHES input argument.")
		for block_hash in options.BLOCKHASHES.split(","):
			if not valid_hash(block_hash):
				die("Error: Supplied block hash %s is not n the correct format." % block_hash)
		options.BLOCKHASHES = [hex2bin(blockhash) for blockhash in options.BLOCKHASHES.split(",")] # string to list

	if options.STARTBLOCKHASH is not None:
		options.STARTBLOCKHASH = hex2bin(options.STARTBLOCKHASH)

	if options.ENDBLOCKHASH is not None:
		options.ENDBLOCKHASH = hex2bin(options.ENDBLOCKHASH)

	if (options.STARTBLOCKNUM is not None) and (options.STARTBLOCKHASH is not None):
		die("Error: If option --start-blocknum (-s) is specified then option --start-blockhash cannot also be specified.")

	if (options.ENDBLOCKNUM is not None) and (options.ENDBLOCKHASH is not None):
		die("Error: If option --end-blocknum (-e) is specified then option --end-blockhash cannot also be specified.")

	if (options.LIMIT is not None) and (options.ENDBLOCKNUM is not None):
		die("Error: If option --limit (-L) is specified then option --end-blocknum (-e) cannot also be specified.")

	if (options.LIMIT is not None) and (options.ENDBLOCKHASH is not None):
		die("Error: If option --limit (-L) is specified then option --end-blockhash cannot also be specified.")

	if (options.STARTBLOCKNUM is None) and (options.STARTBLOCKHASH is None): # go from the start
		options.STARTBLOCKNUM = 0

	if (options.STARTBLOCKNUM is not None) and (options.ENDBLOCKNUM is not None) and (options.ENDBLOCKHASH < options.STARTBLOCKNUM):
		die("Error: The value of --end-blocknum (-e) cannot be less than the value of --start-blocknum (-s).")

	permitted_output_formats = ["MULTILINE-JSON", "SINGLE-LINE-JSON", "MULTILINE-XML", "SINGLE-LINE-XML", "BINARY", "HEX"]
	if options.FORMAT not in permitted_output_formats:
		die("Error: Option --output-format (-o) must be either " + ", ".join(permitted_output_formats[:-1]) + " or " + permitted_output_formats[-1] + ".")

	if options.get_balance:
		if not options.ADDRESSES:
			die("Error: If option --get-balance (-b) is selected then option --addresses (-a) is mandatory.")
		if options.get_full_blocks:
			die("Error: If option --get-balance (-b) is selected then option --get-full-blocks (-f) cannot also be selected.")
		if options.get_transactions:
			die("Error: If option --get-balance (-b) is selected then option --get-transactions (-t) cannot also be selected.")
		if options.FORMAT == "BINARY":
			die("Error: Option --get-balance (-b) cannot be selected while option --output-format (-o) is set to BINARY.")

	if options.get_full_blocks:
		if options.get_balance:
			die("Error: If option --get-full-blocks (-f) is selected then option --get-balance (-b) cannot also be selected.")
		if options.get_transactions:
			die("Error: If option --get-full-blocks (-f) is selected then option --get-transactions (-t) cannot also be selected.")

	if options.get_transactions:
		if options.get_full_blocks:
			die("Error: If option --get-transactions (-t) is selected then option --get-full-blocks (-f) cannot also be selected.")
		if options.get_balance:
			die("Error: If option --get-transactions (-t) is selected then option --get-balance (-b) cannot also be selected.")

def get_full_blocks(options, inputs_already_sanitized = False):
	"""get full blocks which contain the specified addresses, transaction hashes or block hashes."""
	# need to get the block range, either from:
	# a) options.STARTBLOCKNUM and options.LIMIT, or
	# b) options.STARTBLOCKHASH and options.LIMIT, or
	# c) options.STARTBLOCKNUM and options.ENDBLOCKNUM, or
	# d) options.STARTBLOCKHASH and options.ENDBLOCKHASH, or
	# e) all blocks

	# if the ~/.btc-inquisitor/block_positions.csv file does not exist then create it

	# method for (a), (c) and (e):
	# - if the ~/.btc-inquisitor/block_positions.csv file exists and covers the specified range then use this to extract the specified files
	# - if the ~/.btc-inquisitor/block_positions.csv file exists and does not cover the specified range then start looping through the blocks (starting at the closest position possible to the start position) and update the ~/.btc-inquisitor/block_positions.csv file as we go
	# - if the ~/.btc-inquisitor/block_positions.csv file does not exist then use the same method as for (b) and (d)

	# method for (b) and (d):
	# - get the total size of all blockchain files. use this as 100% for now
	# - start looping through the blocks within the files and hunt for the specified blockhashes. update the ~/.btc-inquisitor/block_positions.csv file as we go
	# - stop when we reach the end of the specified range
	
	### problem - we know the range does not begin until blockfile 2
	### so we skip ahead to blockfile 2, but then we do not know if the block is an
	### orphan because we do not have the hash table
	### solution - put hashes in the block_positions list? or just don't use the list? seems simpler (but maybe much slower?)
	### try not using the block positions list and see how slow it is... skipping through the blockchain from header to header
	### may still be relatively quick?
	
	### ensure_block_positions_file_exists() # dies if it does not exist and cannot be created
	### block_positions = get_known_block_positions() # update the global variable - [[file, position], [file, position], ...] - where list element number = block number
	# get the range data:
	# start_data = {"file_num": xxx, "byte_num": xxx, "block_num": xxx} or {}
	# end_data = {"file_num": xxx, "byte_num": xxx, "block_num": xxx} or {}
	### (start_data, end_data) = get_range_data(options)

	# TODO - if the user has enabled orphans then label them as 123-orphan0, 123-orphan1, etc. where 123 is the block number

	if not inputs_already_sanitized:
		die("Error: You must sanitize inputs before passing them to function get_full_blocks().")

	full_blockchain_bytes = get_full_blockchain_size(os.path.expanduser(options.BLOCKCHAINDIR)) # all files
	filtered_blocks = {} # init
	hash_table = {} # init
	hash_table[hex2bin('0000000000000000000000000000000000000000000000000000000000000000')] = -1 # init
	### start_byte = start_data["byte_num"] if "byte_num" in start_data else 0 # init
	abs_block_num = -1 # init
	in_range = False
	exit_now = False
	txin_hashes = {} # keep tabs on outgoing funds from addresses
	if options.progress:
		progress_bytes = 0 # init
		progress_meter.render(0) # init progress meter
	for block_filename in sorted(glob.glob(os.path.expanduser(options.BLOCKCHAINDIR) + 'blk[0-9]*.dat')):
		### file_num = int(re.search(r'\d+', block_filename).group(0))
		### if ("file_num" in start_data) and (file_num < start_data["file_num"]) and (block_positions[-1][0] > file_num):
		### 	continue; # completely safe to skip this blockfile
		### if os.path.isfile(os.path.expanduser(options.BLOCKCHAINDIR) + 'blk' + (file_num + 1) + '.dat'): # file exists
		### 	if (file_num + 1) in [f[0] for f in block_positions]: # if the there are any entries for the next file in the block_positions list then the current file has already been completely processed
		### 		block_positions_complete = True
		### 	else:
		### 		block_positions_complete = False
		active_file_size = os.path.getsize(block_filename)
		blocks_into_file = -1 # reset. includes orphans, whereas abs_block_num does not
		bytes_into_file = 0 # reset
		bytes_into_section = 0 # reset
		active_blockchain = "" # init
		fetch_more_blocks = True
		file_handle = open(block_filename)

		temp_counter = 0
		find_tx_hash_in_txin = {}

		while True: # loop within the same block file
			#
			# extract block data
			#
			if (not fetch_more_blocks) and ((len(active_blockchain) - bytes_into_section) < 8):
				fetch_more_blocks = True
			if fetch_more_blocks:
				file_handle.seek(bytes_into_file, 0)
				active_blockchain = file_handle.read(active_blockchain_num_bytes) # get a subsection of the blockchain file
				bytes_into_section = 0 # reset everytime active_blockchain is updated
				if not len(active_blockchain): # we have already extracted all blocks from this file
					break # move on to next file
				fetch_more_blocks = False
			if active_blockchain[bytes_into_section:bytes_into_section + 4] != magic_network_id:
				die("Error: Block file %s appears to be malformed - block %s in this file (absolute block num %s) does not start with the magic network id." % (block_filename, blocks_into_file + 1, abs_block_num + 1))
				# else - this block does not start with the magic network id, this must mean we have finished inspecting all complete blocks in this subsection - exit here
				break # go to next file
			num_block_bytes = bin2int(little_endian(active_blockchain[bytes_into_section + 4:bytes_into_section + 8])) # 4 bytes binary to decimal int
			if (num_block_bytes + 8) > active_blockchain_num_bytes:
				die("Error: Cannot process %s bytes of the blockchain since block %s of file %s (absolute block num %s) has %s bytes and this program needs to extract at least one full block, plus its 8 byte header, at a time (which comes to %s for this block). Please increase the value of variable 'active_blockchain_num_bytes' at the top of file btc_grunt.py." % (active_blockchain_num_bytes, blocks_into_file + 1, block_filename, abs_block_num + 1, num_block_bytes, num_block_bytes + 8))
			if (num_block_bytes + 8) > (len(active_blockchain) - bytes_into_section): # this block is incomplete
				fetch_more_blocks = True
				continue # get the next block
			blocks_into_file += 1 # ie 1 = first block in file
			block = active_blockchain[bytes_into_section + 8:bytes_into_section + num_block_bytes + 8] # block as bytes
			bytes_into_section += num_block_bytes + 8
			bytes_into_file += num_block_bytes + 8
			if len(block) != num_block_bytes:
				die("Error: Block file %s appears to be malformed - block %s is incomplete." % (block_filename, blocks_into_file))
			### if abs_block_num not in block_positions: # update the block positions list
			### 	update_known_block_positions([file_num, bytes_into_file]) # also updates the block_positions global var
			### if ("file_num" in start_data) and (file_num < start_data["file_num"]): # we are before the range
			### 	if block_positions_complete: # if the block_positions list is complete for this file
			### 		continue # skip to the next file
			### if ("file_num" in end_data) and (file_num > end_data['file_num']): # we have passed outside the range
			### 	return filtered_blocks # exit here
			### if ("byte_num" in start_data) and (bytes_in < start_data["byte_num"]):
			### 	blockchain.read(start_bytes) # advance to the start of the section
			parsed_block = block_bin2dict(block, ["block_hash", "previous_block_hash"])
			#parsed_block = block_bin2dict(block, all_block_info) # test
			#back_to_bytes = block_dict2bin(parsed_block)
			#if back_to_bytes != block:
			#	die("from blockchain: %s\n\nconverted back : %s" % (bin2hex(block), bin2hex(back_to_bytes)))
			#back_to_arr = block_bin2dict(back_to_bytes, all_block_info) # test
			#if back_to_arr != parsed_block:
			#	die("original parse: %s\n\nblock -> parsed -> block -> parsed: %s" % (parsed_block, back_to_arr))
			if parsed_block["previous_block_hash"] not in hash_table:
				die("Error: Could not find parent for block with hash %s (parent hash: %s). Investigate." % (parsed_block["block_hash"], parsed_block["previous_block_hash"]))
			abs_block_num = hash_table[parsed_block["previous_block_hash"]] + 1
			if options.progress:
				progress_bytes += num_block_bytes + 8 # how many bytes through the entire blockchain are we?
				progress_meter.render(100 * progress_bytes / float(full_blockchain_bytes), "block %s" % abs_block_num) # update the progress meter
			if abs_block_num == 496:
				pass # put debug breakpoint here
			hash_table[parsed_block["block_hash"]] = abs_block_num # update the hash table
			if len(hash_table) > 10000:
				# the only way to know if it is an orphan block is to wait, say, 100 blocks after a split in the chain
				hash_table = truncate_hash_table(hash_table, 500) # limit to 500, don't truncate too often
			#
			# skip the block if we are not yet in range
			#
			if options.STARTBLOCKHASH is not None:
				if parsed_block["block_hash"] == options.STARTBLOCKHASH: # just in range
					options.STARTBLOCKHASH = None
					options.STARTBLOCKNUM = abs_block_num # convert hash to a block number
					in_range = True
			if (options.STARTBLOCKNUM is not None) and (abs_block_num >= options.STARTBLOCKNUM):
				in_range = True
			if not in_range:
				if ((options.ENDBLOCKHASH is not None) and (options.ENDBLOCKHASH == parsed_block["block_hash"])) or ((options.ENDBLOCKNUM is not None) and (options.ENDBLOCKNUM == abs_block_num)):
					die("Error: The specified end block was encountered before the start block.")
			if not in_range:
				continue
			#
			# save the relevant blocks TODO - make sure good blocks are not overwritten with orphans. fix.
			#
			if options.BLOCKHASHES and [required_block_hash for required_block_hash in options.BLOCKHASHES if required_block_hash == parsed_block["block_hash"]]:
				filtered_blocks[abs_block_num] = block_bin2dict(block, all_block_info)
			if options.TXHASHES and txs_in_block(options.TXHASHES, block):
				filtered_blocks[abs_block_num] = block_bin2dict(block, all_block_info)
			if options.ADDRESSES and addresses_in_block(options.ADDRESSES, block, True): # search txout scripts only 
				filtered_blocks[abs_block_num] = block_bin2dict(block, all_block_info)
				temp = get_recipient_txhashes(options.ADDRESSES, filtered_blocks[abs_block_num]) # {hash1: [index1, index2, ...], hash2: [index1, index2,...]} or {}
				if temp: # note that this tx hash also covers txout addresses not included in options.ADDRESSES
					txin_hashes.update(temp)
			elif txin_hashes and txin_hashes_in_block(txin_hashes, block):
				filtered_blocks[abs_block_num] = block_bin2dict(block, all_block_info)
			if (not options.BLOCKHASHES) and (not options.TXHASHES) and (not options.ADDRESSES): # if no filter data is specified then return whole block
				filtered_blocks[abs_block_num] = block_bin2dict(block, all_block_info)
			#
			# return if we are beyond the specified range
			#
			if (options.ENDBLOCKNUM is not None) and (options.ENDBLOCKNUM == abs_block_num):
				exit_now = True
				break
			if (options.STARTBLOCKNUM is not None) and (options.LIMIT is not None) and ((options.STARTBLOCKNUM + options.LIMIT - 1) <= abs_block_num): # -1 is because we start counting blocks at 0
				exit_now = True
				break
			if (options.ENDBLOCKHASH is not None) and (options.ENDBLOCKHASH == parsed_block["block_hash"]):
				exit_now = True
				break
		file_handle.close()
		if exit_now:
			if options.progress:
				progress_meter.render(100)
				progress_meter.done()
			return filtered_blocks # we are beyond the specified block range - exit here

def extract_txs(binary_blocks, options):
	"""return only the relevant transactions in binary format. no progress meter here as this stage should be very quick even for thousands of transactions"""
	filtered_txs = []
	for (abs_block_num, block) in binary_blocks.items():
		if isinstance(block, dict):
			parsed_block = block
		else:
			parsed_block = block_bin2dict(block, ["tx_hash", "tx_bytes", "txin_address", "txout_address"])
		for tx_num in sorted(parsed_block["tx"]):
			if options.TXHASHES and parsed_block["tx"][tx_num]["hash"] in options.TXHASHES:
				filtered_txs.append(parsed_block["tx"][tx_num])
				continue # on to next tx
			if parsed_block["tx"][tx_num]["input"] is not None:
				for input_num in parsed_block["tx"][tx_num]["input"]:
					if (parsed_block["tx"][tx_num]["input"][input_num]["address"] is not None) and (parsed_block["tx"][tx_num]["input"][input_num]["address"] in options.ADDRESSES):
						filtered_txs.append(parsed_block["tx"][tx_num])
						break # to next tx
			if parsed_block["tx"][tx_num]["output"] is not None:
				for output_num in parsed_block["tx"][tx_num]["output"]:
					if (parsed_block["tx"][tx_num]["output"][output_num]["address"] is not None) and (parsed_block["tx"][tx_num]["output"][output_num]["address"] in options.ADDRESSES):
						filtered_txs.append(parsed_block["tx"][tx_num])
						break # to next tx
	return filtered_txs

def ensure_block_positions_file_exists():
	"""make sure the block positions file exists"""
	try:
		os.makedirs(os.path.dirname(block_positions_file))
	except (OSError, IOError) as e:
		if e.errno != errno.EEXIST: # the problem is not that the dir already exists
			die("there was an error when creating directory %s for storing the block positions in file %s - %s" % (os.path.dirname(block_positions_file), block_positions_file, e))
	# at this point, the directory exists
	try:
		open(block_positions_file, 'a').close()
	except (OSError, IOError) as e:
		die("could not create the file for storing the block positions - %s" % e)

def extract_coinbase_address(block):
	"""return the coinbase address in binary"""
	test_length = block[214:1]
	if test_length != hex2bin("41"):
		die("could not find coinbase transaction. block: %s" % bin2hex(block))
	ecdsa_pub_key = block[215:65] # coinbase should always be the first transaction
	return pubkey2btc_address(ecdsa_pub_key)

def get_known_block_positions():
	""" return a list - [[file, position], [file, position], ...] - where list element number = block number"""
	try:
		f = open(block_positions_file, "r")
	except (OSError, IOError) as e:
		die("could not open the csv file to read the block positions - %s" % e)
	try:
		r = csv.reader(f, delimiter = ",")
		retval = [row for row in r if row]
	except Exception as e:
		die("error reading csv file to get the block positions - %s" % e)
	f.close()
	return retval

def update_known_block_positions(extra_block_positions):
	"""update the block positions file using the input argument list which is in the format [[file, position], [file, position], ...] - where list element number = block number"""
	try:
		f = open(block_positions_file, "a")
	except (OSError, IOError) as e:
		die("could not open the csv file to write the block positions - %s" % e)
	try:
		for line in extra_block_positions:
			f.write(",".join(extra_block_positions))
			block_positions.extend(extra_block_positions) # update global var
	except Exception as e:
		die("error writing the block positions to the csv file - %s" % e)
	f.close()

def get_range_data(options):
	""" get the range data:
	''' start_data = {"file_num": xxx, "byte_num": xxx, "block_num": xxx} or {}
	''' end_data = {"file_num": xxx, "byte_num": xxx, "block_num": xxx} or {}
	"""
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
		die("ENDBLOCKNUM and LIMIT cannot both be specified")
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

def txin_hashes_in_block(txin_hashes, block):
	"""check if any of the txin hashes exist in the transaction inputs"""
	if isinstance(block, dict):
		parsed_block = block # already parsed
	else:
		parsed_block = block_bin2dict(block, ["txin_hash", "txin_index"])
	for tx_num in parsed_block["tx"]:
		if parsed_block["tx"][tx_num]["input"] is not None:
			for input_num in parsed_block["tx"][tx_num]["input"]:
				if (parsed_block["tx"][tx_num]["input"][input_num]["hash"] in txin_hashes) and (parsed_block["tx"][tx_num]["input"][input_num]["index"] in txin_hashes[parsed_block["tx"][tx_num]["input"][input_num]["hash"]]):
					return True
	return False

def txs_in_block(txhashes, block):
	"""check if any of the transactions exist in the block"""
	if isinstance(block, dict):
		parsed_block = block # already parsed
	else:
		parsed_block = block_bin2dict(block, ["tx_hash"])
	for tx_num in parsed_block["tx"]:
		txhash = parsed_block["tx"][tx_num]["hash"]
		if [required_tx_hash for required_tx_hash in txhashes if required_tx_hash == txhash]:
			return True
	return False

def addresses_in_block(addresses, block, rough = True):
	"""this function checks as quickly as possible whether any of the specified addresses exist in the block. the block may contain addresses in a variety of formats which may not match the formats of the input argument addresses. for example the early coinbase addresses are in the full public key format, while the input argument addresses may be in base58. if any of the input addresses can be found by a simple string search then this function imediately returns True. if the string search fails then all addresses in the block must be parsed into base58 and compared to the input addresses, which is slower :("""
	if rough: # quickly check if the addresses exist in the block in the same format
		if [address for address in addresses if address in block]:
			return True
	# if we get here then we need to parse the addresses from the block
	parsed_block = block_bin2dict(block, ["txin_address", "txout_address"])
	for tx_num in sorted(parsed_block["tx"]):
		if parsed_block["tx"][tx_num]["input"] is not None:
			for input_num in parsed_block["tx"][tx_num]["input"]:
				if (parsed_block["tx"][tx_num]["input"][input_num]["address"] is not None) and (parsed_block["tx"][tx_num]["input"][input_num]["address"] in addresses):
					return True
		if parsed_block["tx"][tx_num]["output"] is not None:
			for output_num in parsed_block["tx"][tx_num]["output"]:
				if (parsed_block["tx"][tx_num]["output"][output_num]["address"] is not None) and (parsed_block["tx"][tx_num]["output"][output_num]["address"] in addresses):
					return True

def get_recipient_txhashes(addresses, block):
	"""get an array of all tx hashes and indexes which contain the specified addresses in their txout scripts"""
	if isinstance(block, dict):
		parsed_block = block
	else:
		parsed_block = block_bin2dict(block, ["tx_hash", "txout_address"])
	recipient_tx_hashes = {} # of the format {hash1:[index1, index2, ...], hash2:[index1, index2, ...], ...}
	for tx_num in sorted(parsed_block["tx"]):
		if parsed_block["tx"][tx_num]["output"] is not None:
			indexes = [] # reset
			for output_num in sorted(parsed_block["tx"][tx_num]["output"]):
				if parsed_block["tx"][tx_num]["output"][output_num]["address"] in addresses:
					indexes.append(output_num)
			if indexes:
				recipient_tx_hashes[parsed_block["tx"][tx_num]["hash"]] = list(set(indexes)) # unique
	return recipient_tx_hashes

def update_txin_addresses(blocks, options):
	"""update the address value in transaction inputs where possible. these are derived from previous txouts"""
	txout_data = {} # {txhash: {index: [script, address]:, index: [script, address]}, txhash: {index: [script, address]}} 
	for abs_block_num in sorted(blocks):
		parsed_block = blocks[abs_block_num]
		block_updated = False
		if not isinstance(parsed_block, dict):
			die("function update_txin_addresses() only accepts pre-parsed blocks")
		for tx_num in parsed_block["tx"]:
			txhash = parsed_block["tx"][tx_num]["hash"]
			for index in sorted(parsed_block["tx"][tx_num]["output"]):
				output_script = parsed_block["tx"][tx_num]["output"][index]["script"]
				if output_script is None:
					continue
				if txhash not in txout_data:
					txout_data[txhash] = {} # init
				output_address = parsed_block["tx"][tx_num]["output"][index]["address"]
				txout_data[txhash][index] = [output_script, output_address] # update
			for input_num in parsed_block["tx"][tx_num]["input"]:
				from_address = parsed_block["tx"][tx_num]["input"][input_num]["address"]
				if parsed_block["tx"][tx_num]["input"][input_num]["verification_attempted"] == True:
					continue
				parsed_block["tx"][tx_num]["input"][input_num]["verification_attempted"] = True
				if parsed_block["tx"][tx_num]["input"][input_num]["verified"] == True:
					continue
				# from_address = None # at this point
				prev_hash = parsed_block["tx"][tx_num]["input"][input_num]["hash"]
				prev_index = parsed_block["tx"][tx_num]["input"][input_num]["index"]
				parsed_block["tx"][tx_num]["input"][input_num]["verified"] = False
				if (prev_hash in txout_data) and (prev_index in txout_data[prev_hash]):
					if checksig(parsed_block["tx"][tx_num], txout_data[prev_hash][prev_index][0], input_num):
						parsed_block["tx"][tx_num]["input"][input_num]["verified"] = True
						from_address = txout_data[prev_hash][prev_index][1]
						del txout_data[prev_hash][prev_index] # now that this previous tx-output has been used up, delete it from the pool to avoid double spends
						if not txout_data[prev_hash]:
							del txout_data[prev_hash]
				if from_address is not None:
					parsed_block["tx"][tx_num]["input"][input_num]["address"] = from_address
					block_updated = True
		if block_updated:
			blocks[abs_block_num] = parsed_block
	return blocks

def block_bin2dict(block, required_info):
	"""extract the specified info from the block into a dictionary and return as soon as it is all available"""
	block_arr = {} # init
	required_info = required_info[:] # copy to avoid altering the argument outside the scope of this function

	if "block_hash" in required_info: # extract the block's hash, from the header
		block_arr["block_hash"] = little_endian(sha256(sha256(block[0:80])))
		required_info.remove("block_hash")
		if not required_info: # no more info required
			return block_arr
	pos = 0

	if "format_version" in required_info:
		block_arr["format_version"] = bin2int(little_endian(block[pos:pos + 4])) # 4 bytes as decimal int
		required_info.remove("format_version")
		if not required_info: # no more info required
			return block_arr
	pos += 4

	if "previous_block_hash" in required_info:
		block_arr["previous_block_hash"] = little_endian(block[pos:pos + 32]) # 32 bytes (little endian)
		required_info.remove("previous_block_hash")
		if not required_info: # no more info required
			return block_arr
	pos += 32

	if "merkle_root" in required_info:
		block_arr["merkle_root"] = little_endian(block[pos:pos + 32]) # 32 bytes (little endian)
		required_info.remove("merkle_root")
		if not required_info: # no more info required
			return block_arr
	pos += 32

	if "timestamp" in required_info:
		block_arr["timestamp"] = bin2int(little_endian(block[pos:pos + 4])) # 4 bytes as decimal int
		required_info.remove("timestamp")
		if not required_info: # no more info required
			return block_arr
	pos += 4

	if "bits" in required_info:
		block_arr["bits"] = little_endian(block[pos:pos + 4]) # 4 bytes
		required_info.remove("bits")
		if not required_info: # no more info required
			return block_arr
	pos += 4

	if "nonce" in required_info:
		block_arr["nonce"] = bin2int(little_endian(block[pos:pos + 4])) # 4 bytes as decimal int
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
		die("the full block could not be parsed. block length: %s, position: %s" % (len(block), pos))
	return block_arr # we only get here if the user has requested all the data from the block

def tx_bin2dict(block, pos, required_info):
	"""extract the specified transaction info from the block into a dictionary and return as soon as it is all available"""
	tx = {} # init
	init_pos = pos

	if "tx_version" in required_info:
		tx["version"] = bin2int(little_endian(block[pos:pos + 4])) # 4 bytes as decimal int
	pos += 4

	(num_inputs, length) = decode_variable_length_int(block[pos:pos + 9])
	if "num_tx_inputs" in required_info:
		tx["num_inputs"] = num_inputs
	pos += length

	tx["input"] = {} # init
	for j in range(0, num_inputs): # loop through all inputs
		tx["input"][j] = {} # init

		tx["input"][j]["verification_attempted"] = False # have we tried to verify this transaction input?
		tx["input"][j]["verified"] = False # is the transaction input valid (can still be true even if this is an orphan block)

		if "txin_hash" in required_info:
			tx["input"][j]["hash"] = little_endian(block[pos:pos + 32]) # 32 bytes as hex
		pos += 32

		if "txin_index" in required_info:
			tx["input"][j]["index"] = bin2int(little_endian(block[pos:pos + 4])) # 4 bytes as decimal int
		pos += 4

		(txin_script_length, length) = decode_variable_length_int(block[pos:pos + 9])
		if "txin_script_length" in required_info:
			tx["input"][j]["script_length"] = txin_script_length
		pos += length

		if ("txin_script" in required_info) or ("txin_address" in required_info) or ("txin_parsed_script" in required_info):
			input_script = block[pos:pos + txin_script_length]
		pos += txin_script_length

		if "txin_script" in required_info:
			tx["input"][j]["script"] = input_script

		if "txin_parsed_script" in required_info:
			script_elements = script_bin2list(input_script) # convert string of bytes to list of bytes
			tx["input"][j]["parsed_script"] = script_list2human_str(script_elements) # convert list of bytes to human readable string

		if "txin_address" in required_info:
			tx["input"][j]["address"] = script2btc_address(input_script)

		if "txin_sequence_num" in required_info:
			tx["input"][j]["sequence_num"] = bin2int(little_endian(block[pos:pos + 4])) # 4 bytes as decimal int
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

		if "txout_btc" in required_info:
			tx["output"][k]["btc"] = bin2int(little_endian(block[pos:pos + 8])) # 8 bytes as decimal int
		pos += 8

		(txout_script_length, length) = decode_variable_length_int(block[pos:pos + 9])
		if "txout_script_length" in required_info:
			tx["output"][k]["script_length"] = txout_script_length # 8 bytes as decimal int (little endian)
		pos += length

		if ("txout_script" in required_info) or ("txout_address" in required_info) or ("txout_parsed_script" in required_info):
			output_script = block[pos:pos + txout_script_length]
		pos += txout_script_length	

		if "txout_script" in required_info:
			tx["output"][k]["script"] = output_script

		if "txout_parsed_script" in required_info:
			script_elements = script_bin2list(output_script) # convert string of bytes to list of bytes
			tx["output"][k]["parsed_script"] = script_list2human_str(script_elements) # convert list of bytes to human readable string

		if "txout_address" in required_info:
			tx["output"][k]["address"] = script2btc_address(output_script) # return btc address or None

		if not len(tx["output"][k]):
			del tx["output"][k]

	if not len(tx["output"]):
		del tx["output"]

	if "tx_lock_time" in required_info:
		tx["lock_time"] = bin2int(little_endian(block[pos:pos + 4])) # 4 bytes as decimal int
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
	"""take a dict of the block and convert it to a binary string"""
	output = little_endian(int2bin(block_arr["format_version"], 4))
	output += little_endian(block_arr["previous_block_hash"])
	output += little_endian(block_arr["merkle_root"])
	output += little_endian(int2bin(block_arr["timestamp"], 4))
	output += little_endian(block_arr["bits"])
	output += little_endian(int2bin(block_arr["nonce"], 4))
	output += encode_variable_length_int(block_arr["num_txs"])
	for tx_num in range(0, block_arr["num_txs"]):
		output += tx_dict2bin(block_arr["tx"][tx_num])
	return output

def tx_dict2bin(tx):
	"""take a dict of the transaction and convert it into a binary string"""

	output = little_endian(int2bin(tx["version"], 4)) # 4 bytes as decimal int
	output += encode_variable_length_int(tx["num_inputs"])
	for j in range(0, tx["num_inputs"]): # loop through all inputs
		output += little_endian(tx["input"][j]["hash"])
		output += little_endian(int2bin(tx["input"][j]["index"], 4)) # 4 bytes as decimal int
		output += encode_variable_length_int(tx["input"][j]["script_length"])
		output += tx["input"][j]["script"]
		output += little_endian(int2bin(tx["input"][j]["sequence_num"], 4))

	output += encode_variable_length_int(tx["num_outputs"])
	for k in range(0, tx["num_outputs"]): # loop through all outputs
		output += little_endian(int2bin(tx["output"][k]["btc"], 8)) # 8 bytes as decimal int
		output += encode_variable_length_int(tx["output"][k]["script_length"])
		output += tx["output"][k]["script"]

	output += little_endian(int2bin(tx["lock_time"], 4))
	return output

def check_block_elements_exist(block, required_block_elements):
	"""return true if all the elements in the input list exist in the block, else false"""
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
	all_remaining_tx_info = remaining_tx_info[:]
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

def array2block(block_arr):
	"""takes an array and converts it to a binary block ready for the blockchain"""
	pass # TODO

def array2tx(tx_arr):
	"""takes an array and converts it to a binary block ready for the blockchain"""
	pass # TODO

def human_readable_block(block):
	"""take the input binary block and return a human readable dict"""
	output_info = all_block_info[:]
	output_info.remove("txin_script") # note that the parsed script will still be output, just not this raw script
	output_info.remove("txout_script") # note that the parsed script will still be output, just not this raw script
	output_info.remove("tx_bytes")
	parsed_block = block_bin2dict(block, output_info) # some elements are still binary here
	parsed_block["block_hash"] = bin2hex(parsed_block["block_hash"])
	parsed_block["previous_block_hash"] = bin2hex(parsed_block["previous_block_hash"])
	parsed_block["merkle_root"] = bin2hex(parsed_block["merkle_root"])
	parsed_block["bits"] = bin2int(parsed_block["bits"])
	for tx_num in parsed_block["tx"]: # there will always be at least one transaction per block
		if parsed_block["tx"][tx_num]["hash"] is not None:
			parsed_block["tx"][tx_num]["hash"] = bin2hex(parsed_block["tx"][tx_num]["hash"])
			for input_num in parsed_block["tx"][tx_num]["input"]:
				if "hash" in parsed_block["tx"][tx_num]["input"][input_num]:
					parsed_block["tx"][tx_num]["input"][input_num]["hash"] = bin2hex(parsed_block["tx"][tx_num]["input"][input_num]["hash"])
	return parsed_block

def human_readable_tx(tx):
	"""take the input binary tx and return a human readable dict"""
	output_info = all_tx_info[:]
	output_info.remove("txin_script") # note that the parsed script will still be output, just not this raw script
	output_info.remove("txout_script") # note that the parsed script will still be output, just not this raw script
	output_info.remove("tx_bytes")
	(parsed_tx, _) = tx_bin2dict(tx, 0, output_info) # some elements are still binary here
	parsed_tx["hash"] = bin2hex(parsed_tx["hash"])
	for input_num in parsed_tx["input"]:
		if "hash" in parsed_tx["input"][input_num]:
			parsed_tx["input"][input_num]["hash"] = bin2hex(parsed_tx["input"][input_num]["hash"])
	return parsed_tx

"""def create_transaction(prev_tx_hash, prev_txout_index, prev_tx_ecdsa_private_key, to_address, btc):
	"" "create a 1-input, 1-output transaction to broadcast to the network. untested! always compare to bitcoind equivalent before use" ""
	raw_version = struct.pack('<I', 1) # version 1 - 4 bytes (little endian)
	raw_num_inputs = encode_variable_length_int(1) # one input only
	if len(prev_tx_hash) != 64:
		die('previous transaction hash should be 32 bytes')
	raw_prev_tx_hash = binascii.a2b_hex(prev_tx_hash) # previous transaction hash
	raw_prev_txout_index = struct.pack('<I', prev_txout_index)
	from_address = '' ############## use private key to get it
	temp_scriptsig = from_address
	raw_input_script_length = encode_variable_length_int(len(temp_scriptsig))
	raw_sequence_num = binascii.a2b_hex('ffffffff')
	raw_num_outputs = encode_variable_length_int(1) # one output only
	raw_satoshis = struct.pack('<Q', (btc - 0.001) * satoshi) # 8 bytes (little endian)
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
		die('signature cannot be longer than 75 bytes: [' + signature + ']')
	final_scriptsig = stuct.pack('B', signature_length) + signature + raw_input_script_length + from_address
	input_script_length = len(final_scriptsig) # overwrite
	if input_script_length > 75:
		die('input script cannot be longer than 75 bytes: [' + final_script + ']')
	raw_input_script = struct.pack('B', input_script_length) + final_script
	signed_tx = raw_version + raw_num_inputs + raw_prev_tx_hash + raw_prev_txout_index + raw_input_script_length + final_scriptsig + raw_sequence_num + raw_num_outputs + raw_satoshis + raw_output_script + raw_output_script_length + raw_locktime
"" "

def get_missing_txin_address_data(block, options):
	" ""tx inputs reference previous tx outputs. if any from-addresses are unknonwn then get the details necessary to go fetch them - ie the previous tx hash and index"" "
	required_block_elements = ["block_hash", "tx_hash", "txin_address", "txin_hash", "txin_index", "txout_address"]
	if isinstance(block, dict):
		if not check_block_elements_exist(block, required_block_elements):
			die("The necessary block elements were not all available when attempting to get the from-address transaction hashes and indexes.")
		parsed_block = block
	else:
		parsed_block = block_bin2dict(block, required_block_elements)
	missing_data = {} # init
	relevant_tx = False
	if options.BLOCKHASHES and [blockhash for blockhash in options.BLOCKHASHES if blockhash == parsed_block["block_hash"]]:
		relevant_tx = True # get missing addresses for all txs
	for tx_num in parsed_block["tx"]: # there will always be at least one transaction per block
		if not relevant_tx and options.TXHASHES and [txhash for txhash in options.TXHASHES if txhash == parsed_block["tx"][txhash]["hash"]]: # TODO - fix filter
			tx["output"][k]["address"] = script2btc_address(parsed_script) # return btc address or None
		#for output_num in parsed_block["tx"][tx_num]["input"]:
		for input_num in parsed_block["tx"][tx_num]["input"]:
			if "address" in parsed_block["tx"][tx_num]["input"][input_num]:
				if parsed_block["tx"][tx_num]["input"][input_num]["address"] is not None:
					continue # we already have the input address
			if "hash" in parsed_block["tx"][tx_num]["input"][input_num]:
				prev_txout_hash = parsed_block["tx"][tx_num]["input"][input_num]["hash"]
				if prev_txout_hash == hex2bin("0000000000000000000000000000000000000000000000000000000000000000"):
					continue # coinbase txs don't reference any previous txout
				missing_data[prev_txout_hash] = parsed_block["tx"][tx_num]["input"][input_num]["index"]
	return missing_data
"""

def valid_block_nonce(block):
	"""return True if the block has a valid nonce, else False. the hash must be below the target (derived from the bits). block input argument must be binary bytes."""
	if isinstance(block, dict):
		parsed_block = block
	else:
		parsed_block = block_bin2dict(block, ["block_hash", "bits"])
	if bin2int(parsed_block["block_hash"]) < calculate_target(parsed_block["bits"]): # hash must be below target
		return True
	else:
		return False

def valid_merkle_tree(block):
	"""return True if the block has a valid merkle root, else False. block input argument must be binary bytes."""
	if isinstance(block, dict):
		parsed_block = block
	else:
		parsed_block = block_bin2dict(block, ["merkle_root", "tx_hash"])
	merkle_leaves = []
	for tx_num in sorted(parsed_block["tx"]): # there will always be at least one transaction per block
		if parsed_block["tx"][tx_num]["hash"] is not None:
			merkle_leaves.append(parsed_block["tx"][tx_num]["hash"])
	if calculate_merkle_root(merkle_leaves) == parsed_block["merkle_root"]:
		return True
	else:
		return False

def calculate_target(bits_bytes):
	"""calculate the decimal target given the 'bits' bytes"""
	exp = bin2int(bits_bytes[:1]) # first byte
	mult = bin2int(bits_bytes[1:]) #
	return mult * (2 ** (8 * (exp - 3)))

def sha256(bytes):
	"""takes binary, performs sha256 hash, returns binary"""
	# use .digest() to keep the result in binary, and .hexdigest() to output as a hex string
	return hashlib.sha256(bytes).digest()	

def ripemd160(bytes):
	"""takes binary, performs ripemd160 hash, returns binary"""
	res = hashlib.new('ripemd160')
	res.update(bytes)
	return res.digest()

def double_sha256(bytes):
	"""calculate a sha256 hash twice. see https://en.bitcoin.it/wiki/Block_hashing_algorithm for details"""
	# use .digest() to keep the result in binary, and .hexdigest() to output as a hex string
	result = hashlib.sha256(bytes) # result as a hashlib object
	result = hashlib.sha256(result.digest()) # result as a hashlib object
	result_hex = result.digest()[::-1] # to hex (little endian)
	return result_hex

def little_endian(bytes):
	"""takes binary, performs little endian (ie reverse the bytes), returns binary"""
	return bytes[::-1]

def extract_scripts_from_input(input_str):
	"""take an input string and create a list of the scripts it contains"""
	input_dict = ast.literal_eval(input_str) # slightly safer than eval - elements can only be string, numbers, etc
	scripts = []
	for (tx_num, tx_data) in input_dict.items():
		coinbase = True if tx_data['hash'] == '0000000000000000000000000000000000000000000000000000000000000000' else False
		scripts.append(tx_data['script'])
	return {'coinbase': coinbase, 'scripts': scripts}

def script2btc_address(script):
	"""extract the bitcoin address from the binary script (input or output)"""
	format_type = extract_script_format(script)
	if not format_type:
		return None
	if format_type == "pubkey": # OP_PUSHDATA0(65) <pubkey> OP_CHECKSIG
		output_address = pubkey2btc_address(script_bin2list(script)[1])
	elif format_type == "hash160": # OP_DUP OP_HASH160 OP_PUSHDATA0(20) <hash160> OP_EQUALVERIFY OP_CHECKSIG
		output_address = hash1602btc_address(script_bin2list(script)[3])
	elif format_type == "sigpubkey": # OP_PUSHDATA0(73) <signature> OP_PUSHDATA0(65) <pubkey>
		output_address = pubkey2btc_address(script_bin2list(script)[3])
	else:
		die("unrecognised format type %s" % format_type)
	return output_address

def extract_script_format(script):
	"""carefully extract the format for the input (binary string) script"""
	recognised_formats = {
		"pubkey": [opcode2bin("OP_PUSHDATA0(65)"), "pubkey", opcode2bin("OP_CHECKSIG")],
		"hash160": [opcode2bin("OP_DUP"), opcode2bin("OP_HASH160"), opcode2bin("OP_PUSHDATA0(20)"), "hash160", opcode2bin("OP_EQUALVERIFY"), opcode2bin("OP_CHECKSIG")],
		"sigpubkey": [opcode2bin("OP_PUSHDATA0(73)"), "signature", opcode2bin("OP_PUSHDATA0(65)"), "pubkey"]
	}
	script_list = script_bin2list(script) # explode
	for (format_type, format_opcodes) in recognised_formats.items():
		if len(format_opcodes) != len(script_list):
			continue # try next format
		for (format_opcode_el_num, format_opcode) in enumerate(format_opcodes):
			if format_opcode == script_list[format_opcode_el_num]:
				confirmed_format = format_type
			elif (format_opcode_el_num in [1, 3]) and (format_opcode == "pubkey") and (len(script_list[format_opcode_el_num]) == 65):
				confirmed_format = format_type
			elif (format_opcode_el_num == 3) and (format_opcode == "hash160") and (len(script_list[format_opcode_el_num]) == 20):
				confirmed_format = format_type
			elif (format_opcode_el_num == 1) and (format_opcode == "signature") and (len(script_list[format_opcode_el_num]) == 73):
				confirmed_format = format_type
			else:
				confirmed_format = None # reset
				break # break out of inner for-loop and try the next format type
			if format_opcode_el_num == (len(format_opcodes) - 1): # last
				if confirmed_format is not None:
					return format_type
	return None # could not determine the format type :(
				
def script_list2human_str(script_elements):
	"""take a list of bytes and output a human readable bitcoin script (ie replace opcodes and convert bin to hex for pushed data)"""
	script_hex_str = ""
	push = False # set to true when the next list element is to be pushed to the stack
	for (i, data) in enumerate(script_elements):
		if push:
			script_hex_str += bin2hex(data)
			push = False # reset
		else:
			parsed_opcode = bin2opcode(data)
			script_hex_str += parsed_opcode
			if "OP_PUSHDATA" in parsed_opcode:
				script_hex_str += ("(%s)" % bin2int(data))
				push = True # push the next element onto the stack
		script_hex_str += " "
	return script_hex_str.strip()

def script_bin2list(bytes):
	"""split the script into elements of a list. input is a string of bytes, output is a list of bytes"""
	script_list = []
	pos = 0
	while len(bytes[pos:]):
		byte = bytes[pos:pos + 1]
		pos += 1
		parsed_opcode = bin2opcode(byte)
		script_list.append(byte)
		if parsed_opcode == "OP_PUSHDATA0":
			push_num_bytes = bin2int(byte) # push this many bytes onto the stack
			if len(bytes[pos:]) < push_num_bytes:
				die("Error: Cannot push %s bytes onto the stack since there are not enough characters left in the raw script." % push_num_bytes)
			script_list.append(bytes[pos:pos + push_num_bytes])
			pos += push_num_bytes
		elif parsed_opcode == "OP_PUSHDATA1":
			push_num_bytes = bin2int(bytes[pos:pos + 2]) # push this many bytes onto the stack
			pos += 2
			if len(bytes[pos:]) < push_num_bytes:
				die("Error: Cannot push %s bytes onto the stack since there are not enough characters left in the raw script." % push_num_bytes)
			script_list.append(bytes[pos:pos + push_num_bytes])
			pos += push_num_bytes
		elif parsed_opcode == "OP_PUSHDATA2":
			push_num_bytes = bin2int(bytes[pos:pos + 4]) # push this many bytes onto the stack
			pos += 4
			if len(bytes[pos:]) < push_num_bytes:
				die("Error: Cannot push %s bytes onto the stack since there are not enough characters left in the raw script." % push_num_bytes)
			script_list.append(bytes[pos:pos + push_num_bytes])
			pos += push_num_bytes
		elif parsed_opcode == "OP_PUSHDATA4":
			push_num_bytes = bin2int(bytes[pos:pos + 8]) # push this many bytes onto the stack
			pos += 8
			if len(bytes[pos:]) < push_num_bytes:
				die("Error: Cannot push %s bytes onto the stack since there are not enough characters left in the raw script." % push_num_bytes)
			script_list.append(bytes[pos:pos + push_num_bytes])
			pos += push_num_bytes
	return script_list

def bin2opcode(code):
	"""decode a single byte into the corresponding opcode as per https://en.bitcoin.it/wiki/script"""
	code = code[:] # copy
	code = ord(code)
	if code == 0:
		opcode = "OP_FALSE" # an empty array of bytes is pushed onto the stack
	elif code <= 75:
		opcode = "OP_PUSHDATA0" # the next opcode bytes is data to be pushed onto the stack
	elif code == 76:
		opcode = "OP_PUSHDATA1" # the next byte contains the number of bytes to be pushed onto the stack
	elif code == 77:
		opcode = "OP_PUSHDATA2" # the next two bytes contain the number of bytes to be pushed onto the stack
	elif code == 78:
		opcode = "OP_PUSHDATA4" # the next four bytes contain the number of bytes to be pushed onto the stack
	elif code == 79:
		opcode = "OP_1NEGATE" # the number -1 is pushed onto the stack
	elif code == 81:
		opcode = "OP_TRUE" # the number 1 is pushed onto the stack
	elif code == 82:
		opcode = "OP_2" # the number 2 is pushed onto the stack
	elif code == 83:
		opcode = "OP_3" # the number 3 is pushed onto the stack
	elif code == 84:
		opcode = "OP_4" # the number 4 is pushed onto the stack
	elif code == 85:
		opcode = "OP_5" # the number 5 is pushed onto the stack
	elif code == 86:
		opcode = "OP_6" # the number 6 is pushed onto the stack
	elif code == 87:
		opcode = "OP_7" # the number 7 is pushed onto the stack
	elif code == 88:
		opcode = "OP_8" # the number 8 is pushed onto the stack
	elif code == 89:
		opcode = "OP_9" # the number 9 is pushed onto the stack
	elif code == 90:
		opcode = "OP_10" # the number 10 is pushed onto the stack
	elif code == 91:
		opcode = "OP_11" # the number 11 is pushed onto the stack
	elif code == 92:
		opcode = "OP_12" # the number 12 is pushed onto the stack
	elif code == 93:
		opcode = "OP_13" # the number 13 is pushed onto the stack
	elif code == 94:
		opcode = "OP_14" # the number 14 is pushed onto the stack
	elif code == 95:
		opcode = "OP_15" # the number 15 is pushed onto the stack
	elif code == 96:
		opcode = "OP_16" # the number 16 is pushed onto the stack
	# flow control
	elif code == 97:
		opcode = "OP_NOP" # does nothing
	elif code == 99:
		opcode = "OP_IF" # if top stack value != 0, statements are executed. remove top stack value
	elif code == 100:
		opcode = "OP_NOTIF" # if top stack value == 0, statements are executed. remove top stack value
	elif code ==  103:
		opcode = "OP_ELSE" # if the preceding OP was not executed then these statements are. else don't
	elif code ==  104:
		opcode = "OP_ENDIF" # ends an if/else block
	elif code ==  105:
		opcode = "OP_VERIFY" # top stack value != true: mark transaction as invalid and remove, false: don't
	elif code ==  106:
		opcode = "OP_RETURN" # marks transaction as invalid
	# stack
	elif code ==  107:
		opcode = "OP_TOALTSTACK" # put the input onto the top of the alt stack. remove it from the main stack
	elif code ==  108:
		opcode = "OP_FROMALTSTACK" # put the input onto the top of the main stack. remove it from the alt stack
	elif code ==  115:
		opcode = "OP_IFDUP" # if the top stack value is not 0, duplicate it
	elif code ==  116:
		opcode = "OP_DEPTH" # puts the number of stack items onto the stack
	elif code ==  117:
		opcode = "OP_DROP" # removes the top stack item
	elif code ==  118:
		opcode = "OP_DUP" # duplicates the top stack item
	elif code ==  119:
		opcode = "OP_NIP" # removes the second-to-top stack item
	elif code ==  120:
		opcode = "OP_OVER" # copies the second-to-top stack item to the top
	elif code ==  121:
		opcode = "OP_PICK" # the item n back in the stack is copied to the top
	elif code ==  122:
		opcode = "OP_ROLL" # the item n back in the stack is moved to the top
	elif code ==  123:
		opcode = "OP_ROT" # the top three items on the stack are rotated to the left
	elif code ==  124:
		opcode = "OP_SWAP" # the top two items on the stack are swapped
	elif code ==  125:
		opcode = "OP_TUCK" # copy item at the top of the stack and insert before the second-to-top item
	elif code ==  109:
		opcode = "OP_2DROP" # removes the top two stack items
	elif code ==  110:
		opcode = "OP_2DUP" # duplicates the top two stack items
	elif code == 111:
		opcode = "OP_3DUP" # duplicates the top three stack items
	elif code == 112:
		opcode = "OP_2OVER" # copies the pair of items two spaces back in the stack to the front
	elif code == 113:
		opcode = "OP_2ROT" # the fifth and sixth items back are moved to the top of the stack
	elif code == 114:
		opcode = "OP_2SWAP" # swaps the top two pairs of items
	# splice
	elif code == 126:
		opcode = "OP_CAT" # concatenates two strings. disabled
	elif code == 127:
		opcode = "OP_SUBSTR" # returns a section of a string. disabled
	elif code == 128:
		opcode = "OP_LEFT" # keeps only characters left of the specified point in a string. disabled
	elif code == 129:
		opcode = "OP_RIGHT" # keeps only characters right of the specified point in a string. disabled
	elif code == 130:
		opcode = "OP_SIZE" # returns the length of the input string
	# bitwise logic
	elif code == 131:
		opcode = "OP_INVERT" # flips all of the bits in the input. disabled
	elif code == 132:
		opcode = "OP_AND" # boolean and between each bit in the inputs. disabled
	elif code == 133:
		opcode = "OP_OR" # boolean or between each bit in the inputs. disabled
	elif code == 134:
		opcode = "OP_XOR" # boolean exclusive or between each bit in the inputs. disabled
	elif code == 135:
		opcode = "OP_EQUAL" # returns 1 if the inputs are exactly equal, 0 otherwise
	elif code == 136:
		opcode = "OP_EQUALVERIFY" # same as OP_EQUAL, but runs OP_VERIFY afterward
	# arithmetic
	elif code == 139:
		opcode = "OP_1ADD" # 1 is added to the input
	elif code == 140:
		opcode = "OP_1SUB" # 1 is subtracted from the input
	elif code == 141:
		opcode = "OP_2MUL" # the input is multiplied by 2. disabled
	elif code == 142:
		opcode = "OP_2DIV" # the input is divided by 2. disabled
	elif code == 143:
		opcode = "OP_NEGATE" # the sign of the input is flipped
	elif code == 144:
		opcode = "OP_ABS" # the input is made positive
	elif code == 145:
		opcode = "OP_NOT" # if the input is 0 or 1, it is flipped. Otherwise the output will be 0
	elif code == 146:
		opcode = "OP_0NOTEQUAL" # returns 0 if the input is 0. 1 otherwise
	elif code == 147:
		opcode = "OP_ADD" # a is added to b
	elif code == 148:
		opcode = "OP_SUB" # b is subtracted from a
	elif code == 149:
		opcode = "OP_MUL" # a is multiplied by b. disabled
	elif code == 150:
		opcode = "OP_DIV" # a is divided by b. disabled
	elif code == 151:
		opcode = "OP_MOD" # returns the remainder after dividing a by b. disabled
	elif code == 152:
		opcode = "OP_LSHIFT" # shifts a left b bits, preserving sign. disabled
	elif code == 153:
		opcode = "OP_RSHIFT" # shifts a right b bits, preserving sign. disabled
	elif code == 154:
		opcode = "OP_BOOLAND" # if both a and b are not 0, the output is 1. Otherwise 0
	elif code == 155:
		opcode = "OP_BOOLOR" # if a or b is not 0, the output is 1. Otherwise 0
	elif code == 156:
		opcode = "OP_NUMEQUAL" # returns 1 if the numbers are equal, 0 otherwise
	elif code == 157:
		opcode = "OP_NUMEQUALVERIFY" # same as OP_NUMEQUAL, but runs OP_VERIFY afterward
	elif code == 158:
		opcode = "OP_NUMNOTEQUAL" # returns 1 if the numbers are not equal, 0 otherwise
	elif code == 159:
		opcode = "OP_LESSTHAN" # returns 1 if a is less than b, 0 otherwise
	elif code == 160:
		opcode = "OP_GREATERTHAN" # returns 1 if a is greater than b, 0 otherwise
	elif code == 161:
		opcode = "OP_LESSTHANOREQUAL" # returns 1 if a is less than or equal to b, 0 otherwise
	elif code == 162:
		opcode = "OP_GREATERTHANOREQUAL" # returns 1 if a is greater than or equal to b, 0 otherwise
	elif code == 163:
		opcode = "OP_MIN" # returns the smaller of a and b
	elif code == 164:
		opcode = "OP_MAX" # returns the larger of a and b
	elif code == 165:
		opcode = "OP_WITHIN" # returns 1 if x is within the specified range (left-inclusive), else 0
	# crypto
	elif code == 166:
		opcode = "OP_RIPEMD160" # the input is hashed using RIPEMD-160
	elif code == 167:
		opcode = "OP_SHA1" # the input is hashed using SHA-1
	elif code == 168:
		opcode = "OP_SHA256" # the input is hashed using SHA-256
	elif code == 169:
		opcode = "OP_HASH160" # the input is hashed twice: first with SHA-256 and then with RIPEMD-160
	elif code == 170:
		opcode = "OP_HASH256" # the input is hashed two times with SHA-256
	elif code == 171:
		opcode = "OP_CODESEPARATOR" # only match signatures after the latest OP_CODESEPARATOR
	elif code == 172:
		opcode = "OP_CHECKSIG" # hash all transaction outputs, inputs, and script. return 1 if valid
	elif code == 173:
		opcode = "OP_CHECKSIGVERIFY" # same as OP_CHECKSIG, but OP_VERIFY is executed afterward
	elif code == 174:
		opcode = "OP_CHECKMULTISIG" # execute OP_CHECKSIG for each signature and public key pair
	elif code == 175:
		opcode = "OP_CHECKMULTISIGVERIFY" # same as OP_CHECKMULTISIG, but OP_VERIFY is executed afterward
	# pseudo-words
	elif code == 253:
		opcode = "OP_PUBKEYHASH" # nts a public key hashed with OP_HASH160
	elif code == 254:
		opcode = "OP_PUBKEY" # nts a public key compatible with OP_CHECKSIG
	elif code == 255:
		opcode = "OP_INVALIDOPCODE" # any opcode that is not yet assigned
	# reserved words
	elif code == 80:
		opcode = "OP_RESERVED" # transaction is invalid unless occuring in an unexecuted OP_IF branch
	elif code == 98:
		opcode = "OP_VER" # transaction is invalid unless occuring in an unexecuted OP_IF branch
	elif code == 101:
		opcode = "OP_VERIF" # transaction is invalid even when occuring in an unexecuted OP_IF branch
	elif code == 102:
		opcode = "OP_VERNOTIF" # transaction is invalid even when occuring in an unexecuted OP_IF branch
	elif code == 137:
		opcode = "OP_RESERVED1" # transaction is invalid unless occuring in an unexecuted OP_IF branch
	elif code == 138:
		opcode = "OP_RESERVED2" # transaction is invalid unless occuring in an unexecuted OP_IF branch
	elif code == 176:
		opcode = "OP_NOP1" # the word is ignored
	elif code == 177:
		opcode = "OP_NOP2" # the word is ignored
	elif code == 178:
		opcode = "OP_NOP3" # the word is ignored
	elif code == 179:
		opcode = "OP_NOP4" # the word is ignored
	elif code == 180:
		opcode = "OP_NOP5" # the word is ignored
	elif code == 181:
		opcode = "OP_NOP6" # the word is ignored
	elif code == 182:
		opcode = "OP_NOP7" # the word is ignored
	elif code == 183:
		opcode = "OP_NOP8" # the word is ignored
	elif code == 184:
		opcode = "OP_NOP9" # the word is ignored
	elif code == 185:
		opcode = "OP_NOP10" # the word is ignored
	elif code == 252:
		opcode = "ERROR" # include to keep the parser going, and for easy search in the db later
	else:
		die("byte %s has no corresponding opcode" % code)
	return opcode

def opcode2bin(opcode):
	"""convert an opcode into its corresponding byte. as per https://en.bitcoin.it/wiki/script"""
	if opcode == "OP_FALSE": # an empty array of bytes is pushed onto the stack
		byteval = 0
	elif "OP_PUSHDATA0" in opcode: # the next opcode bytes is data to be pushed onto the stack
		matches = re.search(r"\((\d+)\)", opcode)
		try:
			byteval = int(matches.group(1))
		except AttributeError:
			die("opcode %s must contain the number of bytes to push onto the stack" % opcode)
	elif "OP_PUSHDATA" in opcode:
		die("converting opcode %s to bytes is unimplemented at this stage" % opcode) # TODO
	elif opcode == "OP_1NEGATE": # the number -1 is pushed onto the stack
		byteval = 79
	elif opcode == "OP_TRUE": # the number 1 is pushed onto the stack
		byteval = 81
	elif opcode == "OP_2": # the number 2 is pushed onto the stack
		byteval = 82
	elif opcode == "OP_3": # the number 3 is pushed onto the stack
		byteval = 83
	elif opcode == "OP_4": # the number 4 is pushed onto the stack
		byteval = 84
	elif opcode == "OP_5": # the number 5 is pushed onto the stack
		byteval = 85
	elif opcode == "OP_6": # the number 6 is pushed onto the stack
		byteval = 86
	elif opcode == "OP_7": # the number 7 is pushed onto the stack
		byteval = 87
	elif opcode == "OP_8": # the number 8 is pushed onto the stack
		byteval = 88
	elif opcode == "OP_9": # the number 9 is pushed onto the stack
		byteval = 89
	elif opcode == "OP_10": # the number 10 is pushed onto the stack
		byteval = 90
	elif opcode == "OP_11": # the number 11 is pushed onto the stack
		byteval = 91
	elif opcode == "OP_12": # the number 12 is pushed onto the stack
		byteval = 92
	elif opcode == "OP_13": # the number 13 is pushed onto the stack
		byteval = 93
	elif opcode == "OP_14": # the number 14 is pushed onto the stack
		byteval = 94
	elif opcode == "OP_15": # the number 15 is pushed onto the stack
		byteval = 95
	elif opcode == "OP_16": # the number 16 is pushed onto the stack
		byteval = 96
	# flow control
	elif opcode == "OP_NOP": # does nothing
		byteval = 97
	elif opcode == "OP_IF": # if top stack value != 0, statements are executed. remove top stack value
		byteval = 99
	elif opcode == "OP_NOTIF": # if top stack value == 0, statements are executed. remove top stack value
		byteval = 100
	elif opcode == "OP_ELSE": # if the preceding OP was not executed then these statements are. else don't
		byteval =  103
	elif opcode == "OP_ENDIF": # ends an if/else block
		byteval =  104
	elif opcode == "OP_VERIFY": # top stack value != true: mark transaction as invalid and remove, false: don't
		byteval =  105
	elif opcode == "OP_RETURN": # marks transaction as invalid
		byteval =  106
	# stack
	elif opcode == "OP_TOALTSTACK": # put the input onto the top of the alt stack. remove it from the main stack
		byteval =  107
	elif opcode == "OP_FROMALTSTACK": # put the input onto the top of the main stack. remove it from the alt stack
		byteval =  108
	elif opcode == "OP_IFDUP": # if the top stack value is not 0, duplicate it
		byteval =  115
	elif opcode == "OP_DEPTH": # puts the number of stack items onto the stack
		byteval =  116
	elif opcode == "OP_DROP": # removes the top stack item
		byteval =  117
	elif opcode == "OP_DUP": # duplicates the top stack item
		byteval =  118
	elif opcode == "OP_NIP": # removes the second-to-top stack item
		byteval =  119
	elif opcode == "OP_OVER": # copies the second-to-top stack item to the top
		byteval =  120
	elif opcode == "OP_PICK": # the item n back in the stack is copied to the top
		byteval =  121
	elif opcode == "OP_ROLL": # the item n back in the stack is moved to the top
		byteval =  122
	elif opcode == "OP_ROT": # the top three items on the stack are rotated to the left
		byteval =  123
	elif opcode == "OP_SWAP": # the top two items on the stack are swapped
		byteval =  124
	elif opcode == "OP_TUCK": # copy item at the top of the stack and insert before the second-to-top item
		byteval =  125
	elif opcode == "OP_2DROP": # removes the top two stack items
		byteval =  109
	elif opcode == "OP_2DUP": # duplicates the top two stack items
		byteval =  110
	elif opcode == "OP_3DUP": # duplicates the top three stack items
		byteval = 111
	elif opcode == "OP_2OVER": # copies the pair of items two spaces back in the stack to the front
		byteval = 112
	elif opcode == "OP_2ROT": # the fifth and sixth items back are moved to the top of the stack
		byteval = 113
	elif opcode == "OP_2SWAP": # swaps the top two pairs of items
		byteval = 114
	# splice
	elif opcode == "OP_CAT": # concatenates two strings. disabled
		byteval = 126
	elif opcode == "OP_SUBSTR": # returns a section of a string. disabled
		byteval = 127
	elif opcode == "OP_LEFT": # keeps only characters left of the specified point in a string. disabled
		byteval = 128
	elif opcode == "OP_RIGHT": # keeps only characters right of the specified point in a string. disabled
		byteval = 129
	elif opcode == "OP_SIZE": # returns the length of the input string
		byteval = 130
	# bitwise logic
	elif opcode == "OP_INVERT": # flips all of the bits in the input. disabled
		byteval = 131
	elif opcode == "OP_AND": # boolean and between each bit in the inputs. disabled
		byteval = 132
	elif opcode == "OP_OR": # boolean or between each bit in the inputs. disabled
		byteval = 133
	elif opcode == "OP_XOR": # boolean exclusive or between each bit in the inputs. disabled
		byteval = 134
	elif opcode == "OP_EQUAL": # returns 1 if the inputs are exactly equal, 0 otherwise
		byteval = 135
	elif opcode == "OP_EQUALVERIFY": # same as OP_EQUAL, but runs OP_VERIFY afterward
		byteval = 136
	# arithmetic
	elif opcode == "OP_1ADD": # 1 is added to the input
		byteval = 139
	elif opcode == "OP_1SUB": # 1 is subtracted from the input
		byteval = 140
	elif opcode == "OP_2MUL": # the input is multiplied by 2. disabled
		byteval = 141
	elif opcode == "OP_2DIV": # the input is divided by 2. disabled
		byteval = 142
	elif opcode == "OP_NEGATE": # the sign of the input is flipped
		byteval = 143
	elif opcode == "OP_ABS": # the input is made positive
		byteval = 144
	elif opcode == "OP_NOT": # if the input is 0 or 1, it is flipped. Otherwise the output will be 0
		byteval = 145
	elif opcode == "OP_0NOTEQUAL": # returns 0 if the input is 0. 1 otherwise
		byteval = 146
	elif opcode == "OP_ADD": # a is added to b
		byteval = 147
	elif opcode == "OP_SUB": # b is subtracted from a
		byteval = 148
	elif opcode == "OP_MUL": # a is multiplied by b. disabled
		byteval = 149
	elif opcode == "OP_DIV": # a is divided by b. disabled
		byteval = 150
	elif opcode == "OP_MOD": # returns the remainder after dividing a by b. disabled
		byteval = 151
	elif opcode == "OP_LSHIFT": # shifts a left b bits, preserving sign. disabled
		byteval = 152
	elif opcode == "OP_RSHIFT": # shifts a right b bits, preserving sign. disabled
		byteval = 153
	elif opcode == "OP_BOOLAND": # if both a and b are not 0, the output is 1. Otherwise 0
		byteval = 154
	elif opcode == "OP_BOOLOR": # if a or b is not 0, the output is 1. Otherwise 0
		byteval = 155
	elif opcode == "OP_NUMEQUAL": # returns 1 if the numbers are equal, 0 otherwise
		byteval = 156
	elif opcode == "OP_NUMEQUALVERIFY": # same as OP_NUMEQUAL, but runs OP_VERIFY afterward
		byteval = 157
	elif opcode == "OP_NUMNOTEQUAL": # returns 1 if the numbers are not equal, 0 otherwise
		byteval = 158
	elif opcode == "OP_LESSTHAN": # returns 1 if a is less than b, 0 otherwise
		byteval = 159
	elif opcode == "OP_GREATERTHAN": # returns 1 if a is greater than b, 0 otherwise
		byteval = 160
	elif opcode == "OP_LESSTHANOREQUAL": # returns 1 if a is less than or equal to b, 0 otherwise
		byteval = 161
	elif opcode == "OP_GREATERTHANOREQUAL": # returns 1 if a is greater than or equal to b, 0 otherwise
		byteval = 162
	elif opcode == "OP_MIN": # returns the smaller of a and b
		byteval = 163
	elif opcode == "OP_MAX": # returns the larger of a and b
		byteval = 164
	elif opcode == "OP_WITHIN": # returns 1 if x is within the specified range (left-inclusive), else 0
		byteval = 165
	# crypto
	elif opcode == "OP_RIPEMD160": # the input is hashed using RIPEMD-160
		byteval = 166
	elif opcode == "OP_SHA1": # the input is hashed using SHA-1
		byteval = 167
	elif opcode == "OP_SHA256": # the input is hashed using SHA-256
		byteval = 168
	elif opcode == "OP_HASH160": # the input is hashed twice: first with SHA-256 and then with RIPEMD-160
		byteval = 169
	elif opcode == "OP_HASH256": # the input is hashed two times with SHA-256
		byteval = 170
	elif opcode == "OP_CODESEPARATOR": # only match signatures after the latest OP_CODESEPARATOR
		byteval = 171
	elif opcode == "OP_CHECKSIG": # hash all transaction outputs, inputs, and script. return 1 if valid
		byteval = 172
	elif opcode == "OP_CHECKSIGVERIFY": # same as OP_CHECKSIG, but OP_VERIFY is executed afterward
		byteval = 173
	elif opcode == "OP_CHECKMULTISIG": # execute OP_CHECKSIG for each signature and public key pair
		byteval = 174
	elif opcode == "OP_CHECKMULTISIGVERIFY": # same as OP_CHECKMULTISIG, but OP_VERIFY is executed afterward
		byteval = 175
	# pseudo-words
	elif opcode == "OP_PUBKEYHASH": # nts a public key hashed with OP_HASH160
		byteval = 253
	elif opcode == "OP_PUBKEY": # nts a public key compatible with OP_CHECKSIG
		byteval = 254
	elif opcode == "OP_INVALIDOPCODE": # any opcode that is not yet assigned
		byteval = 255
	# reserved words
	elif opcode == "OP_RESERVED": # transaction is invalid unless occuring in an unexecuted OP_IF branch
		byteval = 80
	elif opcode == "OP_VER": # transaction is invalid unless occuring in an unexecuted OP_IF branch
		byteval = 98
	elif opcode == "OP_VERIF": # transaction is invalid even when occuring in an unexecuted OP_IF branch
		byteval = 101
	elif opcode == "OP_VERNOTIF": # transaction is invalid even when occuring in an unexecuted OP_IF branch
		byteval = 102
	elif opcode == "OP_RESERVED1": # transaction is invalid unless occuring in an unexecuted OP_IF branch
		byteval = 137
	elif opcode == "OP_RESERVED2": # transaction is invalid unless occuring in an unexecuted OP_IF branch
		byteval = 138
	elif opcode == "OP_NOP1": # the word is ignored
		byteval = 176
	elif opcode == "OP_NOP2": # the word is ignored
		byteval = 177
	elif opcode == "OP_NOP3": # the word is ignored
		byteval = 178
	elif opcode == "OP_NOP4": # the word is ignored
		byteval = 179
	elif opcode == "OP_NOP5": # the word is ignored
		byteval = 180
	elif opcode == "OP_NOP6": # the word is ignored
		byteval = 181
	elif opcode == "OP_NOP7": # the word is ignored
		byteval = 182
	elif opcode == "OP_NOP8": # the word is ignored
		byteval = 183
	elif opcode == "OP_NOP9": # the word is ignored
		byteval = 184
	elif opcode == "OP_NOP10": # the word is ignored
		byteval = 185
	elif opcode == "ERROR": # include to keep the parser going, and for easy search in the db later
		byteval = 252
	else:
		die("opcode %s has no corresponding byte" % opcode)
	return hex2bin(int2hex(byteval))

def calculate_merkle_root(merkle_tree_elements):
	"""recursively calculate the merkle root from the leaves (which is a list)"""
	if not merkle_tree_elements:
		die("Error: No arguments passed to function calculate_merkle_root()")
	if len(merkle_tree_elements) == 1: # just return the input
		return merkle_tree_elements[0]
	nodes = ["placeholder"] # gets overwritten
	level = 0
	nodes[level] = [little_endian(leaf) for leaf in merkle_tree_elements] # convert all leaves from little endian back to normal
	while True:
		num = len(nodes[level])
		nodes.append("placeholder") # initialise next level
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
			return little_endian(nodes[level + 1][0]) # this is the root - output in little endian
		level = level + 1

def checksig(new_tx, prev_txout_script, validate_txin_num):
	"""take the entire chronologically later transaction and validate it against the script from the previous txout"""
	# TODO - pass in dict of prev_txout_scrpts for each new_tx input in the format {"txhash-index": script, "txhash-index": script, ...}
	# https://en.bitcoin.it/wiki/OP_CHECKSIG
	# http://bitcoin.stackexchange.com/questions/8500/if-addresses-are-hashes-of-public-keys-how-are-signatures-verified
	temp = script_list2human_str(script_bin2list(prev_txout_script))
	new_txin_script_elements = script_bin2list(new_tx["input"][validate_txin_num]["script"]) # assume OP_PUSHDATA0(73) <signature>
	if extract_script_format(prev_txout_script) == "pubkey": # OP_PUSHDATA0(65) <pubkey> OP_CHECKSIG early transactions were sent directly to public keys (as opposed to the sha256 hash of the public key). it is slightly more risky to leave public keys in plain sight for too long, incase supercomputers factorize the private key and steal the funds. however later transactions onlyreveal the public key when spending funds into a new address (for which only the sha256 hash of the public key is known), which is much safer - an attacker would need to factorize the private key from the public key within a few blocks duration, then attempt to fork the chain if they wanted to steal funds this way - very computationally expensive.
		pubkey = script_bin2list(prev_txout_script)[1]
	elif extract_script_format(new_tx["input"][validate_txin_num]["script"]) == "pubkey": # OP_PUSHDATA0(65) <pubkey> OP_CHECKSIG
		pubkey = new_txin_script_elements[1]
	elif extract_script_format(new_tx["input"][validate_txin_num]["script"]) == "sigpubkey": # OP_PUSHDATA0(73) <signature> OP_PUSHDATA0(65) <pubkey>
		pubkey = new_txin_script_elements[3]
	else:
		die("could not find a public key to use for the checksig")
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
		die("bad input script - it does not start with OP_PUSH: %s" % script_list2human_str(new_txin_script_elements))
	new_txin_signature = new_txin_script_elements[1]
	if bin2int(new_txin_signature[-1]) != 1:
		die("unexpected hashtype found in the signature in the new tx input script while performing checksig")
	hashtype = little_endian(int2bin(1, 4)) # TODO - support other hashtypes
	new_txin_signature = new_txin_signature[:-1] # chop off the last (hash type) byte
	new_tx_copy = new_tx.copy()
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

def pubkey2btc_address(pubkey):
	"""take the public ecdsa key (bytes) and output a standard bitcoin address (ascii string), following https://en.bitcoin.it/wiki/Technical_background_of_Bitcoin_addresses"""
	if len(pubkey) != 65:
		die("the public ecdsa key must be 65 bytes long, but this one is %s bytes" % len(pubkey))
	return hash1602btc_address(ripemd160(sha256(pubkey)))

def btc_address2hash160(btc_address):
	"""from https://github.com/gavinandresen/bitcointools/blob/master/base58.py"""
	bytes = base58decode(btc_address)
	return bytes[1:21]

def hash1602btc_address(hash160):
	"""convert the hash160 output (bytes) to the bitcoin address (ascii string) https://en.bitcoin.it/wiki/Technical_background_of_Bitcoin_addresses"""
	temp = chr(0) + hash160 # 00010966776006953d5567439e5e39f86a0d273bee
	checksum = sha256(sha256(temp))[:4] # checksum is the first 4 bytes
	hex_btc_address = bin2hex(temp + checksum) # 00010966776006953d5567439e5e39f86a0d273beed61967f6
	decimal_btc_address = int(hex_btc_address, 16) # 25420294593250030202636073700053352635053786165627414518
	return version_symbol('ecdsa_pub_key_hash') + base58encode(decimal_btc_address) # 16UwLL9Risc3QfPqBUvKofHmBQ7wMtjvM

def encode_variable_length_int(value):
	"""encode a value as a variable length integer"""
	if value < 253: # encode as a single byte
		bytes = int2bin(value)
	elif value < 0xffff: # encode as 1 format byte and 2 value bytes (little endian)
		bytes = int2bin(253) + int2bin(value)
	elif value < 0xffffffff: # encode as 1 format byte and 4 value bytes (little endian)
		bytes = int2bin(254) + int2bin(value)
	elif value < 0xffffffffffffffff: # encode as 1 format byte and 8 value bytes (little endian)
		bytes = int2bin(255) + int2bin(value)
	else:
		die("value %s is too big to be encoded as a variable length integer" % value)
	return bytes

def decode_variable_length_int(input_bytes):
	"""extract the value of a variable length integer"""
	bytes_in = 0
	first_byte = bin2int(input_bytes[:1]) # 1 byte binary to decimal int
	bytes = input_bytes[:][1:] # don't need the first byte anymore
	bytes_in += 1
	if first_byte < 253: # if the first byte is less than 253, use the byte literally
		value = first_byte
	elif first_byte == 253: # read the next two bytes as a little endian 16-bit number (total bytes read = 3)
		value = bin2int(bytes[:2]) # 2 bytes binary to decimal int (little endian)
		bytes_in += 2
	elif first_byte == 254: # read the next four bytes as a little endian 32-bit number (total bytes read = 5)
		value = bin2int(bytes[:4]) # 4 bytes binary to decimal int (little endian)
		bytes_in += 4
	elif first_byte == 255: # read the next eight bytes as a little endian 64-bit number (total bytes read = 9)
		value = bin2int(bytes[:8]) # 8 bytes binary to decimal int (little endian)
		bytes_in += 8
	else:
		die("value %s is too big to be decoded as a variable length integer" % bin2hex(input_bytes))
	return (value, bytes_in)

def truncate_hash_table(hash_table, new_len):
	"""take a dict of the form {hashstring: block_num} and leave [new_len] upper blocks"""
	reversed_hash_table = {block_num: hashstring for (hashstring, block_num) in hash_table.items()}
	to_remove = sorted(reversed_hash_table)[:-new_len] # only keep [new_len] on the end
	for block_num in to_remove:
		del reversed_hash_table[block_num]
	hash_table = {hashstring:block_num for (block_num, hashstring) in reversed_hash_table.items()}
	return hash_table

def explode_addresses(original_addresses):
	"""convert addresses into as many different formats as possible. return as a list"""
	addresses = []
	for address in original_addresses:
		address_type = get_address_type(address)
		if "script hash" in address_type: # eg 3EktnHQD7RiAE6uzMj2ZifT9YgRrkSgzQX
			addresses.append(address)
			#if is_base58(address): TODO
			#	addresses.append(base582bin(address))
		elif "pubkey hash" in address_type: # eg 17VZNX1SN5NtKa8UQFxwQbFeFc3iqRYhem
			addresses.append(address)
			#if is_base58(address): TODO
			#	addresses.append(base582bin(address))
		elif address_type == "public key": # the 130 character hex string
			addresses.append(hex2bin(address)) # hunt for raw public keys
			addresses.append(pubkey2btc_address(hex2bin(address))) # hunt also for pubkey hashes (condensed from public keys)
	return addresses

def is_base58(input_str):
	"""check if the input string is base58"""
	for char in input_str:
		if char not in base58alphabet:
			return False
	return True # if we get here then it is a base58 string

def base58encode(input_num):
	"""encode the input integer into a base58 string. see https://en.bitcoin.it/wiki/Base58Check_encoding for doco. code modified from http://darklaunch.com/2009/08/07/base58-encode-and-decode-using-php-with-example-base58-encode-base58-decode using bcmath"""
	base = len(base58alphabet)
	encoded = ''
	num = input_num
	try:
		while num >= base:
			mod = num % base
			encoded = base58alphabet[mod] + encoded
			num = num / base
	except TypeError:
		die("function base58encode() only accepts an integer argument")
	if num:
		encoded = base58alphabet[num] + encoded
	return encoded

def base58decode(value):
	"""decode the value into a string of bytes in base58 from https://github.com/gavinandresen/bitcointools/blob/master/base58.py"""
	base = 58
	long_value = 0L # init
	for (i, char) in enumerate(value[::-1]): # loop through the input value one char at a time in reverse order (i starts at 0)
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
	"""retrieve the symbol for the given btc use case
	use list on page https://en.bitcoin.it/wiki/Base58Check_encoding and https://en.bitcoin.it/wiki/List_of_address_prefixes"""
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
		die('unrecognised bitcoin use [' + use + ']')
	if formatt not in symbol:
		die('format [' + formatt + '] is not recognised')
	symbol = symbol[formatt] # return decimal or prefix
	return symbol

def get_address_type(address):
	"""https://en.bitcoin.it/wiki/List_of_address_prefixes. input is an ascii string"""
	if len(address) == 130: # hex public key. specific currency is unknown
		return "public key"
	if address[0] == "1": # bitcoin eg 17VZNX1SN5NtKa8UQFxwQbFeFc3iqRYhem
		if len(address) != 34:
			die("address %s looks like a bitcoin public key hash, but does not have the necessary 34 characters" % address)
		return "bitcoin pubkey hash"
	if address[0] == "3": # bitcoin eg 3EktnHQD7RiAE6uzMj2ZifT9YgRrkSgzQX
		if len(address) != 34:
			die("address %s looks like a bitcoin script hash, but does not have the necessary 34 characters" % address)
		return "bitcoin script hash"
	if address[0] == "L": # litecoin eg LhK2kQwiaAvhjWY799cZvMyYwnQAcxkarr
		if len(address) != 34:
			die("address %s looks like a litecoin public key hash, but does not have the necessary 34 characters" % address)
		return "litecoin pubkey hash"
	if address[0] in ["M", "N"]: # namecoin eg NATX6zEUNfxfvgVwz8qVnnw3hLhhYXhgQn
		if len(address) != 34:
			die("address %s looks like a namecoin public key hash, but does not have the necessary 34 characters" % address)
		return "namecoin pubkey hash"
	if address[0] in ["m", "n"]: # bitcoin testnet eg mipcBbFg9gMiCh81Kj8tqqdgoZub1ZJRfn
		if len(address) != 34:
			die("address %s looks like a bitcoin testnet public key hash, but does not have the necessary 34 characters" % address)
		return "bitcoin-testnet pubkey hash"
	return "unknown"

def get_currency(address):
	"""attempt to derive the currency type from the address. this is only possible for base58 formats."""
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
	"""convert raw binary data to a hex string. also accepts ascii chars (0 - 255)"""
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

def die(message = False):
	if message:
		sys.exit(n + message)
	else:
		sys.exit(0)

def warn(message):
	if options.NOWARN:
		return
	print "[warn] %s" % message

"""module containing some general bitcoin-related functions"""

# TODO - make a new parse_transaction function to call from parse_block

import sys, pprint, time, binascii, struct, hashlib, re, ast, glob, os, errno, progress_meter, csv
#import psutil

active_blockchain_num_bytes = 300#00000 # the number of bytes to process in ram at a time (approx 30 megabytes)
magic_network_id = 'f9beb4d9'
confirmations = 120 # default
satoshi = 100000000 # the number of satoshis per btc
base58alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
validate_nonce = False # turn on to make sure the nonce checks out
block_positions_file = os.path.expanduser("~/.btc-inquisitor/block_positions.csv")

""" global debug level:
''' 0 = off
''' 1 = show only high level program flow
''' 2 = show basic debugging info 
''' commented out = use individual file settings
"""
debug = 0 # debug level

def history(addresses, start_data = None, end_data = None, btc_dir = "~/.bitcoin"):
	"""get all the transactions for the specified addresses - both sending and receiving funds"""
	history = [] # init
	hash_table = {} # init
	if not start_data:
		start_data['file_num'] = 0
		start_data['byte_num'] = 0
		start_data['block_num'] = 0
	if 'file_num' not in start_data:
		raise Exception('file_num must be included when start_data is supplied')
	if 'byte_num' not in start_data:
		raise Exception('byte_num must be included when start_data is supplied')
	if 'block_num' not in start_data:
		raise Exception('block_num must be included when start_data is supplied')
	abs_block_num = start_data['block_num'] # init
	start_byte = start_data['byte_num'] # init
	for block_filename in sorted(glob.glob(btc_dir + '/blocks/blk[0-9]*.dat')):
		file_num = int(re.search(r'\d+', block_filename).group(0))
		if file_num < start_data['file_num']:
			continue # skip to the next file
		if end_data and (file_num > end_data['file_num']):
			if config.debug > 0:
				print "exceeded final file (number %s) - exit here" % end_data["file_num"]
			return history
		while True: # loop within the same block file
			blocks = extract_blocks(block_filename, start_byte) # one block per list item
			blockchain_section_size = 0
			for relative_block_num in sorted(blocks): # loop through keys ascending
				block = blocks[relative_block_num] # dict
				if block['status'] == 'complete block':
					start_byte = block['block_start_pos'] + block['block_size'] # continue in same file
					if not hash_table:
						hash_table[block['prev_block_hash']] = abs_block_num - 1
					if block['prev_block_hash'] not in hash_table:
						raise Exception('could not find parent for block with hash %s. investigate' % block['block_hash'])
					block_file_data['block_num'] = hash_table[block['prev_block_hash']] + 1 # increment before insert, and only for complete blocks
					hash_table[block['block_hash']] = block_file_data['block_num'] # update the hash table
					block['block_num'] = block_file_data['block_num'] # add element for inserting into db
					blockchain_section_size += block['block_size']
					filtered_block_data = find_addresses_in_block(addresses, block)
					if filtered_block_data:
						history.append(filtered_block_data)
				elif block['status'] == 'incomplete block':
					del blocks[relative_block_num]
				elif block['status'] == 'past end of file':
					del blocks[relative_block_num]
					start_byte = 0
					block_file_data['file_num'] = block_file_data['file_num'] + 1
					break_from_while = True # move on to the next block file
				else:
					raise Exception('unrecognised block status %s' % block['status'])

			if config.debug > 0:
				print "total bytes this section: %s" % blockchain_section_size
			mulll_mysql_high.insert_bitcoin_transactions(blocks) # insert all complete blocks into the db in one hit
			if len(hash_table) > 1000:
				hash_table = truncate_hash_table(hash_table, 500) # limit to 500, don't truncate too often
			if break_from_while: # move on to the next block file
				break

def get_full_blocks(options):
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
	
	ensure_block_positions_file_exists() # dies if it does not exist and cannot be created
	# get the range data:
	# start_data = {"file_num": xxx, "byte_num": xxx, "block_num": xxx} or {}
	# end_data = {"file_num": xxx, "byte_num": xxx, "block_num": xxx} or {}
	(start_data, end_data) = get_range_data(options)

	filtered_blocks = [] # init
	hash_table = {} # init
	abs_block_num = start_data['block_num'] # init
	start_byte = start_data['byte_num'] # init
	try:
		for block_filename in sorted(glob.glob(os.path.expanduser(options.BLOCKCHAINDIR) + 'blk[0-9]*.dat')):
			file_num = int(re.search(r'\d+', block_filename).group(0))
			if ("file_num" in start_data) and (file_num < start_data['file_num']):
				continue # skip to the next file
			if ("file_num" in end_data) and (file_num > end_data['file_num']):
				return filtered_blocks # we are now outside the range - exit here
			blockchain = open(block_filename, 'rb') # file object
			active_blockchain = blockchain.read(active_blockchain_num_bytes) # get a subsection of the blockchain file

		while True: # loop within the same block file
"""
			blocks = extract_blocks(block_filename, start_byte) # one block per list item
			blockchain_section_size = 0
			for relative_block_num in sorted(blocks): # loop through keys ascending
				block = blocks[relative_block_num] # dict
				if block['status'] == 'complete block':
					start_byte = block['block_start_pos'] + block['block_size'] # continue in same file
					if not hash_table:
						hash_table[block['prev_block_hash']] = abs_block_num - 1
					if block['prev_block_hash'] not in hash_table:
						raise Exception('could not find parent for block with hash %s. investigate' % block['block_hash'])
					block_file_data['block_num'] = hash_table[block['prev_block_hash']] + 1 # increment before insert, and only for complete blocks
					hash_table[block['block_hash']] = block_file_data['block_num'] # update the hash table
					block['block_num'] = block_file_data['block_num'] # add element for inserting into db
					blockchain_section_size += block['block_size']
					filtered_block_data = find_addresses_in_block(addresses, block)
					if filtered_block_data:
						filtered_blocks.append(filtered_block_data)
				elif block['status'] == 'incomplete block':
					del blocks[relative_block_num]
				elif block['status'] == 'past end of file':
					del blocks[relative_block_num]
					start_byte = 0
					block_file_data['file_num'] = block_file_data['file_num'] + 1
					break_from_while = True # move on to the next block file
				else:
					raise Exception('unrecognised block status %s' % block['status'])

			if len(hash_table) > 1000:
				hash_table = truncate_hash_table(hash_table, 500) # limit to 500, don't truncate too often
			if break_from_while: # move on to the next block file
				break
"""
	except (OSError, IOError) as e:
		sys.exit("failed to open block file %s - %s" % (process_filename, e))
	except Exception as e:
		sys.exit("%s" % e)

def ensure_block_positions_file_exists():
	"""make sure the block positions file exists"""
	try:
		os.makedirs(os.path.dirname(block_positions_file))
	except (OSError, IOError) as e:
		if e.errno != errno.EEXIST: # the problem is not that the dir already exists
			sys.exit("there was an error when creating directory %s for storing the block positions in file %s - %s" % (os.path.dirname(block_positions_file), block_positions_file, e))
	# at this point, the directory exists
	try:
		open(block_positions_file, 'a').close()
	except (OSError, IOError) as e:
		sys.exit("could not create the file for storing the block positions - %s" % e)

def get_known_block_positions():
	""" return a list - [file, position], [file, position]] - where list element number = block number"""
	try:
		f = open(block_positions_file, 'r')
	except (OSError, IOError) as e:
		sys.exit("could not open the csv file to read the block positions - %s" % e)
	try:
		r = csv.reader(f, delimiter = ',')
		retval = [row for row in r if row]
	except Exception as e:
		sys.exit("error reading csv file to get the block positions - %s" % e)
	f.close()
	return retval

def get_range_data(options):
	""" get the range data:
	''' start_data = {"file_num": xxx, "byte_num": xxx, "block_num": xxx} or {}
	''' end_data = {"file_num": xxx, "byte_num": xxx, "block_num": xxx} or {}
	"""
	ensure_block_positions_file_exists() # dies if it does not exist and cannot be created
	block_positions_data = get_known_block_positions() # returns a list: [[file, position], [file, position]] where list element number = block number
	start_data = {} # need to figure out the start data based on the argument options
	if not options.STARTBLOCKNUM and not options.STARTBLOCKHASH:
		start_data["file_num"] = 0
		start_data["byte_num"] = 0
		start_data["block_num"] = 0
	if options.STARTBLOCKNUM < len(block_positions_data): # block_positions_data entry exists
		start_data["file_num"] = block_positions_data[options.STARTBLOCKNUM][0]
		start_data["byte_num"] = block_positions_data[options.STARTBLOCKNUM][1]
		start_data["block_num"] = options.STARTBLOCKNUM
	if options.STARTBLOCKHASH:
		start_data["hash"] = options.STARTBLOCKHASH # no way of knowing the start position without scanning through the blockfiles
	if options.ENDBLOCKNUM and options.LIMIT:
		sys.exit("ENDBLOCKNUM and LIMIT cannot both be specified")
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

def find_addresses_in_block(addresses, block):
	"""search for the specified addresses in the input and output transaction scripts in the given block"""
	for tx_num in sorted(block['tx']): # loop through the transactions in this block searching for the addresses
#		for input_num in sorted(block['tx'][tx_num]['input']) # TODO test
		if not len(block['tx'][tx_num]['input']):
			del block['tx'][tx_num]['input']
		for output_num in sorted(block['tx'][tx_num]['output']):
			if block['tx'][tx_num]['output'][output_num]['to_address'] not in addresses:
				del block['tx'][tx_num]['output'][output_num]
		if not len(block['tx'][tx_num]['output']):
			del block['tx'][tx_num]['output']
	if not len(block['tx']):
		block = None
	return block

#def extract_blocks(options):
#	"""extract all full blocks which match the criteria specified in the 'options' argument. output a list with one binary block per element."""
#	if active_blockchain_num_bytes < 1:
#		sys.exit('cannot process %s bytes of the blockchain - too small!' % active_blockchain_num_bytes)
#	if active_blockchain_num_bytes > (psutil.virtual_memory().free / 3): # 3 seems like a good safety factor
#		sys.exit('cannot process %s bytes of the blockchain - not enough ram!' % active_blockchain_num_bytes)
#	abs_blockchain_dir = os.path.expanduser(options.BLOCKCHAINDIR)
#	if not os.path.isdir(abs_blockchain_dir):
#		sys.exit("blockchain dir %s is inaccessible" % abs_blockchain_dir)
#	block_file_names = sorted(glob.glob(abs_blockchain_dir + "blk[0-9]*.dat")) # list of file names
#	filtered_blocks = []
#	if options.progress:
#		if options.
#	for block_file_name in block_file_names:
#		blockchain = open(block_file_name, 'rb')
#		active_blockchain = blockchain.read() # read the whole file into this var
#		active_blocks = active_blockchain.split(binascii.a2b_hex(magic_network_id)) # one block per list element
#		for (i, active_block) in enumerate(active_blocks):
#		found = False # init
#		if options.BLOCKHASHES: # first filter by block hashes
#			for block_hash in options.BLOCKHASHES.split(","):
#				if block_hash in active_blockchain:
#					found = True
#		found = False # init
#		if options.TXHASHES: # then by transaction hashes
#		found = False # init
#		if options.ADDRESSES: # then by addresses
#		print filename
#	sys.exit()
#	file_num = int(re.search(r'\d+', filename).group(0))
#	blockchain = open(filename, 'rb')
#	if start_byte:
#		blockchain.read(start_byte) # advance the read pointer to the start byte
#	active_blockchain = blockchain.read(active_blockchain_num_bytes) # get a subsection of the blockchain file
#	parsed_blocks = {} # init
#	parsed_blocks[0] = {} # init
#	if config.debug > 0:
#		parsed_blocks[0]['timer'] = 'n/a' # init
#	if not len(active_blockchain): # we have run off the end of the blockchain in file filename. end parser for now
#		parsed_blocks[0]['status'] = 'past end of file'
#		return parsed_blocks
#	found_one = False # have not identified the start of one block correctly yet
#	block_sub_num = 0
#	if config.debug > 0:
#		bytes_in = 0 # debug use only
#	while True: # loop through each block in this subsection of the blockchain
#		start_time = time.time()
#		parsed_blocks[block_sub_num] = {} # init
#		if config.debug > 0:
#			parsed_blocks[block_sub_num]['timer'] = 'n/a' # init
#			print "begin extracting sub-block %s" % block_sub_num
#		actual_magic_network_id = bin2hex_str(active_blockchain[ : 4]) # get binary as hex string
#		if actual_magic_network_id != magic_network_id:
#			if not found_one:
#				sys.exit('the very first block started with %s, but it should have started with the magic network id %s. no blocks have been extracted from file %s' % (actual_magic_network_id, magic_network_id, filename))
#			if config.debug > 2:
#				print "this block does not start with the magic network id %s, it starts with %s. this must mean we have finished inspecting all complete blocks in this subsection - exit here" % (magic_network_id, actual_magic_network_id)
#			parsed_blocks[block_sub_num]['status'] = 'past end of file'
#			break
#		found_one = True # we have found the start of a block
#		active_blockchain = active_blockchain[4 : ] # trim off the 4 bytes for the magic network id
#		num_block_bytes = bin2dec_le(active_blockchain[ : 4]) # 4 bytes binary to decimal int (little endian)
#		if num_block_bytes > active_blockchain_num_bytes:
#			sys.exit('the active block size (%s bytes) is set smaller than this block\'s size (%sbytes)' % (active_blockchain_num_bytes, num_block_bytes))
#		if config.debug > 0:
#			bytes_in = bytes_in + num_block_bytes
#			print "this block has length %s bytes and starts at byte %s [%s/%s] bytes this section" % (num_block_bytes, start_byte, '{:,}'.format(bytes_in), '{:,}'.format(active_blockchain_num_bytes))
#		active_blockchain = active_blockchain[4 : ] # trim off the 4 bytes for the block length
#		block = active_blockchain[ : num_block_bytes] # block as bytes
#		if len(block) != num_block_bytes:
#			if config.debug > 1:
#				print "incomplete block found: %s" % bin2hex_str(block)
#			parsed_blocks[block_sub_num]['status'] = 'incomplete block'
#			break
#		parsed_blocks[block_sub_num] = parse_block(block) # only save complete blocks
#		parsed_blocks[block_sub_num]['block_size'] = num_block_bytes + 8
#		parsed_blocks[block_sub_num]['file_num'] = file_num
#		parsed_blocks[block_sub_num]['block_start_pos'] = start_byte
#		parsed_blocks[block_sub_num]['status'] = 'complete block'
#		active_blockchain = active_blockchain[num_block_bytes : ] # prepare for next loop
#		start_byte += num_block_bytes + 8
#		if config.debug > 0:
#			parsed_blocks[block_sub_num]['timer'] = str(time.time() - start_time) # block extraction time
#		block_sub_num = block_sub_num + 1
#	blockchain.close()
#	if config.debug > 1:
#		print "this section of the blockchain has been parsed into array %s" % pprint.pformat(parsed_blocks, width = 1)
#	return parsed_blocks

def parse_block(block):
	"""extract the information within the block into a dictionary"""
# for small hex numbers use hexdec(), for large use $_str_->bchexdec()
	block_arr = {} # init

	# this block's hash, from the header
	block_arr['block_hash'] = double_sha256(block[ : 80])
	if block_arr['block_hash'][ : 8] != '00000000':
		raise Exception('the block header should hash to a value starting with 4 bytes of zero, but this one does not: %s' % block_arr['block_hash']) # the nonce is mined to give this result. other variables are the timestamp and merkle root

	# format version
	block_arr['format_version'] = bin2dec_le(block[ : 4]) # 4 bytes as decimal int (little endian)
	block = block[4 : ]

	# previous block hash
	block_arr['prev_block_hash'] = mulll_str.little_endian(bin2hex_str(block[ : 32])) # 32 bytes as hex (little endian)
	block = block[32 : ]

	# merkle root
	block_arr['merkle_root'] = mulll_str.little_endian(bin2hex_str(block[ : 32])) # 32 bytes as hex (little endian)
	block = block[32 : ]

	# timestamp
	block_arr['timestamp'] = bin2dec_le(block[ : 4]) # 4 bytes as decimal int (little endian)
	block = block[4 : ]

	# bits
	block_arr['bits'] = bin2dec_le(block[ : 4]) # 4 bytes as decimal int (little endian)
	block = block[4 : ]

	# nonce (exists to ensure block hash <= target)
	block_arr['nonce'] = bin2dec_le(block[ : 4]) # 4 bytes as decimal int (little endian)
	if validate_nonce:
		target = calculate_target(block_arr['bits'])
		if target > block_arr['block_hash']:
			raise Exception('bad block - the block hash %s is greater than the target %s' % (block_arr['block_hash'], target))
	block = block[4 : ]

	# number of transactions
	block_arr['num_txs'], length = decode_variable_length_int(block[ : 9])
	block = block[length : ]

	block_arr['tx'] = {}
	# loop through all transactions in this block
	for i in range(0, block_arr['num_txs']):
		block_arr['tx'][i] = {}
		(block_arr['tx'][i], block) = parse_transaction(block)
		"""
		block_arr['tx'][i]['bytes'] = '' # collect all of the transaction bytes in this string
		
		# transaction i's version
		block_arr['tx'][i]['version'] = struct.unpack('<I', block[ : 4])[0] # 4 bytes as decimal int (little endian)
		block_arr['tx'][i]['bytes'] += block[ : 4]
		block = block[4 : ]

		# number of transaction i's inputs
		block_arr['tx'][i]['num_inputs'], length = decode_variable_length_int(block[ : 9]);
		block_arr['tx'][i]['bytes'] += block[ : length]
		block = block[length : ]
		
		block_arr['tx'][i]['input'] = {}
		# loop through all inputs for transaction i
		for j in range(0, block_arr['tx'][i]['num_inputs']):
			block_arr['tx'][i]['input'][j] = {}

			# transaction i, input j's hash
			block_arr['tx'][i]['input'][j]['hash'] = mulll_str.little_endian(bin2hex_str(block[ : 32])) # 32 bytes as hex (little endian)
			block_arr['tx'][i]['bytes'] += block[ : 32]
			block = block[32 : ]

			# transaction i, input j's index
			block_arr['tx'][i]['input'][j]['index'] = struct.unpack('<I', block[ : 4])[0] # 4 bytes as decimal int (little endian)
			block_arr['tx'][i]['bytes'] += block[ : 4]
			block = block[4 : ]

			# transaction i, input j's script length
			block_arr['tx'][i]['input'][j]['script_length'], length = decode_variable_length_int(block[ : 9])
			block_arr['tx'][i]['bytes'] += block[ : length]
			block = block[length : ]

			# transaction i, input j's script value
			# don't parse the script for now - it is proving tricky
#			block_arr['tx'][i]['input'][j]['script'] = parse_script(block[ : block_arr['tx'][i]['input'][j]['script_length']])
			block_arr['tx'][i]['input'][j]['script'] = bin2hex_str(block[ : block_arr['tx'][i]['input'][j]['script_length']])
			block_arr['tx'][i]['bytes'] += block[ : block_arr['tx'][i]['input'][j]['script_length']]
			block = block[block_arr['tx'][i]['input'][j]['script_length'] : ]

			# transaction i, input j's sequence number
			block_arr['tx'][i]['input'][j]['sequence_num'] = struct.unpack('<I', block[ : 4])[0] # 4 bytes as decimal int (little endian)
			block_arr['tx'][i]['bytes'] += block[ : 4]
			block = block[4 : ]

		# number of transaction i's outputs
		block_arr['tx'][i]['num_outputs'], length = decode_variable_length_int(block[ : 9])
		block_arr['tx'][i]['bytes'] += block[ : length]
		block = block[length : ]

		block_arr['tx'][i]['output'] = {}
		# loop through all outputs for transaction i
		for k in range(0, block_arr['tx'][i]['num_outputs']):
			block_arr['tx'][i]['output'][k] = {}

			# transaction i, output k's btc
			block_arr['tx'][i]['output'][k]['btc'] = struct.unpack('<Q', block[ : 8])[0] # 8 bytes as decimal int (little endian)
			block_arr['tx'][i]['bytes'] += block[ : 8]
			block = block[8 : ]

			# transaction i, output k's script length
			block_arr['tx'][i]['output'][k]['script_length'], length = decode_variable_length_int(block[ : 9])
			block_arr['tx'][i]['bytes'] += block[ : length]
			block = block[length : ]

			# transaction i, output k's script value
			# don't parse the script for now - it is proving tricky
#			block_arr['tx'][i]['output'][k]['script'] = parse_script(block[ : block_arr['tx'][i]['output'][k]['script_length']])
			block_arr['tx'][i]['output'][k]['script'] = bin2hex_str(block[ : block_arr['tx'][i]['output'][k]['script_length']])
			block_arr['tx'][i]['bytes'] += block[ : block_arr['tx'][i]['output'][k]['script_length']]
			block = block[block_arr['tx'][i]['output'][k]['script_length'] : ]

			# extract bitcoin addresses from script
			# $block_arr['tx'][$i]['output'][$k]['address'] = $this->script2address($block_arr['tx'][$i]['output'][$k]['script'])
		# transaction i's lock time
		block_arr['tx'][i]['lock_time'] = struct.unpack('<I', block[ : 4])[0] # 4 bytes as decimal int (little endian)
		block_arr['tx'][i]['bytes'] += block[ : 4]
		block = block[4 : ]

		# calculate transaction i's hash (sha256 twice then reverse the bytes)
		block_arr['tx'][i]['hash'] = double_sha256(block_arr['tx'][i]['bytes'])
		del block_arr['tx'][i]['bytes'] # no need to keep this now we have hashed the transction
		"""
	if len(block):
		raise Exception('the full block could not be parsed. remainder: %s' % block)
	return block_arr

def parse_transaction(block):
	"""parse the transaction from [block] into a dict to return"""
	tx = {} # init
	tx['bytes'] = '' # collect all of the transaction bytes in this string
	
	# transaction's version
	tx['version'] = bin2dec_le(block[ : 4]) # 4 bytes as decimal int (little endian)
	tx['bytes'] += block[ : 4]
	block = block[4 : ]

	# number of transaction's inputs
	tx['num_inputs'], length = decode_variable_length_int(block[ : 9]);
	tx['bytes'] += block[ : length]
	block = block[length : ]
	
	tx['input'] = {} # init
	# loop through all inputs
	for j in range(0, tx['num_inputs']):
		tx['input'][j] = {} # init

		# input j's hash
		tx['input'][j]['hash'] = mulll_str.little_endian(bin2hex_str(block[ : 32])) # 32 bytes as hex (little endian)
		tx['bytes'] += block[ : 32]
		block = block[32 : ]

		# input j's index
		tx['input'][j]['index'] = bin2dec_le(block[ : 4]) # 4 bytes as decimal int (little endian)
		tx['bytes'] += block[ : 4]
		block = block[4 : ]

		# input j's script length
		tx['input'][j]['script_length'], length = decode_variable_length_int(block[ : 9])
		tx['bytes'] += block[ : length]
		block = block[length : ]

		# input j's script value
		# don't parse the script for now - it is proving tricky
#			tx['input'][j]['script'] = parse_script(block[ : tx['input'][j]['script_length']])
		tx['input'][j]['script'] = bin2hex_str(block[ : tx['input'][j]['script_length']])
		tx['bytes'] += block[ : tx['input'][j]['script_length']]
		block = block[tx['input'][j]['script_length'] : ]

		# input j's sequence number
		tx['input'][j]['sequence_num'] = bin2dec_le(block[ : 4]) # 4 bytes as decimal int (little endian)
		tx['bytes'] += block[ : 4]
		block = block[4 : ]

	# number of outputs
	tx['num_outputs'], length = decode_variable_length_int(block[ : 9])
	tx['bytes'] += block[ : length]
	block = block[length : ]

	tx['output'] = {} # init
	# loop through all outputs
	for k in range(0, tx['num_outputs']):
		tx['output'][k] = {} # init

		# output k's btc
		tx['output'][k]['btc'] = bin2dec_le(block[ : 8]) # 8 bytes as decimal int (little endian)
		tx['bytes'] += block[ : 8]
		block = block[8 : ]

		# output k's script length
		tx['output'][k]['script_length'], length = decode_variable_length_int(block[ : 9])
		tx['bytes'] += block[ : length]
		block = block[length : ]

		# output k's script value
		tx['output'][k]['script'] = bin2hex_str(block[ : tx['output'][k]['script_length']]) # unparsed
		tx['output'][k]['parsed_script'] = parse_script(tx['output'][k]['script']) # parse the opcodes
		tx['output'][k]['to_address'] = script2btc_address(tx['output'][k]['parsed_script']) # return btc address or None
		tx['bytes'] += block[ : tx['output'][k]['script_length']]
		block = block[tx['output'][k]['script_length'] : ]

	# transaction's lock time
	tx['lock_time'] = bin2dec_le(block[ : 4]) # 4 bytes as decimal int (little endian)
	tx['bytes'] += block[ : 4]
	block = block[4 : ]

	# calculate the transaction's hash (sha256 twice then reverse the bytes)
	tx['hash'] = double_sha256(tx['bytes'])
	del tx['bytes'] # no need to keep this now we have hashed the transction
	return (tx, block)

def create_transaction(prev_tx_hash, prev_tx_output_index, prev_tx_ecdsa_private_key, to_address, btc):
	"""create a 1-input, 1-output transaction to broadcast to the network. untested! always compare to bitcoind equivalent before use"""
	raw_version = struct.pack('<I', 1) # version 1 - 4 bytes (little endian)
	raw_num_inputs = encode_variable_length_int(1) # one input only
	if len(prev_tx_hash) != 64:
		raise Exception('previous transaction hash should be 32 bytes')
	raw_prev_tx_hash = binascii.a2b_hex(prev_tx_hash) # previous transaction hash
	raw_prev_tx_output_index = struct.pack('<I', prev_tx_output_index)
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
	temp_tx = raw_version + raw_num_inputs + raw_prev_tx_hash + raw_prev_tx_output_index + raw_input_script_length + temp_scriptsig + raw_sequence_num + raw_num_outputs + raw_satoshis + raw_output_script + raw_output_script_length + raw_locktime + raw_hashcode
	tx_hash = double_sha256(temp_tx)
	signature = der_encode(ecdsa_sign(tx_hash, prev_tx_private_key)) + '01' # TODO - der encoded
	signature_length = len(signature)
	if signature_length > 75:
		raise Exception('signature cannot be longer than 75 bytes: [' + signature + ']')
	final_scriptsig = stuct.pack('B', signature_length) + signature + raw_input_script_length + from_address
	input_script_length = len(final_scriptsig) # overwrite
	if input_script_length > 75:
		raise Exception('input script cannot be longer than 75 bytes: [' + final_script + ']')
	raw_input_script = struct.pack('B', input_script_length) + final_script
	signed_tx = raw_version + raw_num_inputs + raw_prev_tx_hash + raw_prev_tx_output_index + raw_input_script_length + final_scriptsig + raw_sequence_num + raw_num_outputs + raw_satoshis + raw_output_script + raw_output_script_length + raw_locktime

def calculate_target(bits):
	raise Exception('not yet implemented')

def double_sha256(bytes):
	"""calculate a sha256 hash twice. see https://en.bitcoin.it/wiki/Block_hashing_algorithm for details"""
	# use .digest() to keep the result in binary, and .hexdigest() to output as a hex string
	result = hashlib.sha256(bytes) # result as a hashlib object
	result = hashlib.sha256(result.digest()) # result as a hashlib object
	result_str = result.hexdigest() # to string
	result_str = mulll_str.little_endian(result_str) # reverse
	return result_str

def extract_scripts_from_input(input_str):
	"""take an input string and create a list of the scripts it contains"""
	input_dict = ast.literal_eval(input_str) # slightly safer than eval - elements can only be string, numbers, etc
	scripts = []
	for (tx_num, tx_data) in input_dict.items():
		coinbase = True if tx_data['hash'] == '0000000000000000000000000000000000000000000000000000000000000000' else False
		scripts.append(tx_data['script'])
	return {'coinbase': coinbase, 'scripts': scripts}

def script2btc_address(parsed_script):
	"""extract the bitcoin address from the parsed script (input or output)"""
	format_type = extract_script_format(parsed_script)
	if not format_type:
		return None
	output_script_parts = parsed_script.split(' ') # explode
	if format_type == 'coinbase':
		output_address = pub_ecdsa2btc_address(binascii.a2b_hex(output_script_parts[1]))
	elif format_type == 'scriptpubkey': 
		output_address = hash1602btc_address(output_script_parts[3])
	else:
		raise Exception('unrecognised format type [' + format_type + ']')
	return output_address

def extract_script_format(parsed_script):
	"""carefully extract the format for the given script"""
	recognised_formats = {
		'coinbase': 'OP_PUSHDATA pub_ecdsa OP_CHECKSIG',
		'scriptpubkey': 'OP_DUP OP_HASH160 OP_PUSHDATA0 hash160 OP_EQUALVERIFY OP_CHECKSIG'
	}
	script_parts = parsed_script.split(' ') # explode
	confirmed_format = None # init
	for (format_type, format_opcodes) in recognised_formats.items():
		format_opcodes_parts = format_opcodes.split(' ') # explode
		if len(format_opcodes_parts) != len(script_parts):
#			if config.debug > 2:
#				mulll_msg.manage('debug', 'the parsed script has [' + str(len(script_parts)) + '] elements, but format [' + format_type + '] has [' + str(len(format_opcodes_parts)) + '] elements. no match - try next format...')
			continue # try next format
#		if config.debug > 2:
#			mulll_msg.manage('debug', 'both the parsed script and format [' + format_type + '] have [' + str(len(script_parts)) + '] elements - so far so good. now check if the script elements are of the correct format...')
		for (format_opcode_el_num, format_opcode) in enumerate(format_opcodes_parts):
			if format_opcode in script_parts[format_opcode_el_num]:
#				if config.debug > 2:
#					mulll_msg.manage('debug', 'script element [' + script_parts[format_opcode_el_num] + '] found in [' + format_type + '] script - matches opcode [' + format_opcode + '] at element number [' + str(format_opcode_el_num) + ']')
				confirmed_format = format_type
			elif (format_opcode == 'pub_ecdsa') and (len(script_parts[format_opcode_el_num]) == 130):
#				if config.debug > 2:
#					mulll_msg.manage('debug', 'script element [' + script_parts[format_opcode_el_num] + '] found in [' + format_type + '] script - matches opcode [' + format_opcode + '] at element number [' + str(format_opcode_el_num) + ']')
				confirmed_format = format_type
			elif (format_opcode == 'hash160') and (len(script_parts[format_opcode_el_num]) == 40):
#				if config.debug > 2:
#					mulll_msg.manage('debug', 'script element [' + script_parts[format_opcode_el_num] + '] found in [' + format_type + '] script - matches opcode [' + format_opcode + '] at element number [' + str(format_opcode_el_num) + ']')
				confirmed_format = format_type
			else:
#				if config.debug > 2:
#					mulll_msg.manage('debug', 'script element [' + script_parts[format_opcode_el_num] + '] not found in [' + format_type + '] script - does not match opcode [' + format_opcode + '] at element number [' + str(format_opcode_el_num) + ']')
				confirmed_format = None # reset
				break # break out of inner for-loop and try the next format type
			if format_opcode_el_num == (len(format_opcodes_parts) - 1): # last
				if confirmed_format:
#					if config.debug > 2:
#						mulll_msg.manage('debug', 'this is the last element for format [' + format_type + ']. all elements match, so exit here')
					return format_type
#				else:
#					if config.debug > 2:
#						mulll_msg.manage('debug', 'this is the last element for format [' + format_type + ']. the script does not match this type, so stay in the loop and see if the next format matches')
#	if config.debug > 2:
#		mulll_msg.manage('debug', 'could not determine the format type for parsed script [' + parsed_script + '] :(')
	return None # could not determine the format type :(
				
def parse_script(raw_script_str):
	"""decode the transaction input and output scripts (eg replace opcodes)"""
#	if config.debug > 2:
#		mulll_msg.manage('debug', 'begin parsing script [' + raw_script_str + ']')
	parsed_script = ''
	while len(raw_script_str):
		byte = int(raw_script_str[ : 2], 16)
		raw_script_str = raw_script_str[2 : ]
		parsed_opcode = decode_opcode(byte)
		parsed_script += parsed_opcode
		if parsed_opcode == 'OP_PUSHDATA0':
			push_num = 2 * byte # push this many characters onto the stack
			if len(raw_script_str) < push_num:
				raise Exception('cannot push [' + str(push_num) + '] bytes onto the stack since there are not enough characters left in the raw script')
			parsed_script += '(' + str(push_num) + ') ' + raw_script_str[ : push_num]
			raw_script_str = raw_script_str[push_num : ] # trim
		elif parsed_opcode == 'OP_PUSHDATA1':
			push_num = 2 * int(raw_script_str[ : 2], 16) # push this many characters onto the stack
			raw_script_str = raw_script_str[2 : ] # trim
			if len(raw_script_str) < push_num:
				raise Exception('cannot push [' + str(push_num) + '] bytes onto the stack since there are not enough characters left in the raw script')
			parsed_script += '(' + str(push_num) + ') ' + raw_script_str[ : push_num]
			raw_script_str = raw_script_str[push_num : ] # trim
		elif parsed_opcode == 'OP_PUSHDATA2':
			push_num = 2 * int(raw_script_str[ : 4], 16) # push this many characters onto the stack
			raw_script_str = raw_script_str[4 : ] # trim
			if len(raw_script_str) < push_num:
				raise Exception('cannot push [' + str(push_num) + '] bytes onto the stack since there are not enough characters left in the raw script')
			parsed_script += '(' + str(push_num) + ') ' + raw_script_str[ : push_num]
			raw_script_str = raw_script_str[push_num : ] # trim
		elif parsed_opcode == 'OP_PUSHDATA4':
			push_num = 2 * int(raw_script_str[ : 8], 16) # push this many characters onto the stack
			raw_script_str = raw_script_str[8 : ]
			if len(raw_script_str) < push_num:
				raise Exception('cannot push [' + str(push_num) + '] bytes onto the stack since there are not enough characters left in the raw script')
			parsed_script += '(' + str(push_num) + ') ' + raw_script_str[ : push_num]
			raw_script_str = raw_script_str[push_num : ] # trim
		parsed_script += ' '
	parsed_script = parsed_script.strip()
#	if config.debug > 2:
#		mulll_msg.manage('debug', 'parsed script: [' + parsed_script + ']')
	return parsed_script

def decode_opcode(code):
	"""decode a single byte into the corresponding opcode as per https://en.bitcoin.it/wiki/script"""
	if code == 0:
		opcode = 'OP_FALSE' # an empty array of bytes is pushed onto the stack
	elif code <= 75:
		opcode = 'OP_PUSHDATA0' # the next opcode bytes is data to be pushed onto the stack
	elif code == 76:
		opcode = 'OP_PUSHDATA1' # the next byte contains the number of bytes to be pushed onto the stack
	elif code == 77:
		opcode = 'OP_PUSHDATA2' # the next two bytes contain the number of bytes to be pushed onto the stack
	elif code == 78:
		opcode = 'OP_PUSHDATA4' # the next four bytes contain the number of bytes to be pushed onto the stack
	elif code == 79:
		opcode = 'OP_1NEGATE' # the number -1 is pushed onto the stack
	elif code == 81:
		opcode = 'OP_TRUE' # the number 1 is pushed onto the stack
	elif code == 82:
		opcode = 'OP_2' # the number 2 is pushed onto the stack
	elif code == 83:
		opcode = 'OP_3' # the number 3 is pushed onto the stack
	elif code == 84:
		opcode = 'OP_4' # the number 4 is pushed onto the stack
	elif code == 85:
		opcode = 'OP_5' # the number 5 is pushed onto the stack
	elif code == 86:
		opcode = 'OP_6' # the number 6 is pushed onto the stack
	elif code == 87:
		opcode = 'OP_7' # the number 7 is pushed onto the stack
	elif code == 88:
		opcode = 'OP_8' # the number 8 is pushed onto the stack
	elif code == 89:
		opcode = 'OP_9' # the number 9 is pushed onto the stack
	elif code == 90:
		opcode = 'OP_10' # the number 10 is pushed onto the stack
	elif code == 91:
		opcode = 'OP_11' # the number 11 is pushed onto the stack
	elif code == 92:
		opcode = 'OP_12' # the number 12 is pushed onto the stack
	elif code == 93:
		opcode = 'OP_13' # the number 13 is pushed onto the stack
	elif code == 94:
		opcode = 'OP_14' # the number 14 is pushed onto the stack
	elif code == 95:
		opcode = 'OP_15' # the number 15 is pushed onto the stack
	elif code == 96:
		opcode = 'OP_16' # the number 16 is pushed onto the stack
	# flow control
	elif code == 97:
		opcode = 'OP_NOP' # does nothing
	elif code == 99:
		opcode = 'OP_IF' # if top stack value != 0, statements are executed. remove top stack value
	elif code == 100:
		opcode = 'OP_NOTIF' # if top stack value == 0, statements are executed. remove top stack value
	elif code ==  103:
		opcode = 'OP_ELSE' # if the preceding OP was not executed then these statements are. else don't
	elif code ==  104:
		opcode = 'OP_ENDIF' # ends an if/else block
	elif code ==  105:
		opcode = 'OP_VERIFY' # top stack value != true: mark transaction as invalid and remove, false: don't
	elif code ==  106:
		opcode = 'OP_RETURN' # marks transaction as invalid
	# stack
	elif code ==  107:
		opcode = 'OP_TOALTSTACK' # put the input onto the top of the alt stack. remove it from the main stack
	elif code ==  108:
		opcode = 'OP_FROMALTSTACK' # put the input onto the top of the main stack. remove it from the alt stack
	elif code ==  115:
		opcode = 'OP_IFDUP' # if the top stack value is not 0, duplicate it
	elif code ==  116:
		opcode = 'OP_DEPTH' # puts the number of stack items onto the stack
	elif code ==  117:
		opcode = 'OP_DROP' # removes the top stack item
	elif code ==  118:
		opcode = 'OP_DUP' # duplicates the top stack item
	elif code ==  119:
		opcode = 'OP_NIP' # removes the second-to-top stack item
	elif code ==  120:
		opcode = 'OP_OVER' # copies the second-to-top stack item to the top
	elif code ==  121:
		opcode = 'OP_PICK' # the item n back in the stack is copied to the top
	elif code ==  122:
		opcode = 'OP_ROLL' # the item n back in the stack is moved to the top
	elif code ==  123:
		opcode = 'OP_ROT' # the top three items on the stack are rotated to the left
	elif code ==  124:
		opcode = 'OP_SWAP' # the top two items on the stack are swapped
	elif code ==  125:
		opcode = 'OP_TUCK' # copy item at the top of the stack and insert before the second-to-top item
	elif code ==  109:
		opcode = 'OP_2DROP' # removes the top two stack items
	elif code ==  110:
		opcode = 'OP_2DUP' # duplicates the top two stack items
	elif code == 111:
		opcode = 'OP_3DUP' # duplicates the top three stack items
	elif code == 112:
		opcode = 'OP_2OVER' # copies the pair of items two spaces back in the stack to the front
	elif code == 113:
		opcode = 'OP_2ROT' # the fifth and sixth items back are moved to the top of the stack
	elif code == 114:
		opcode = 'OP_2SWAP' # swaps the top two pairs of items
	# splice
	elif code == 126:
		opcode = 'OP_CAT' # concatenates two strings. disabled
	elif code == 127:
		opcode = 'OP_SUBSTR' # returns a section of a string. disabled
	elif code == 128:
		opcode = 'OP_LEFT' # keeps only characters left of the specified point in a string. disabled
	elif code == 129:
		opcode = 'OP_RIGHT' # keeps only characters right of the specified point in a string. disabled
	elif code == 130:
		opcode = 'OP_SIZE' # returns the length of the input string
	# bitwise logic
	elif code == 131:
		opcode = 'OP_INVERT' # flips all of the bits in the input. disabled
	elif code == 132:
		opcode = 'OP_AND' # boolean and between each bit in the inputs. disabled
	elif code == 133:
		opcode = 'OP_OR' # boolean or between each bit in the inputs. disabled
	elif code == 134:
		opcode = 'OP_XOR' # boolean exclusive or between each bit in the inputs. disabled
	elif code == 135:
		opcode = 'OP_EQUAL' # returns 1 if the inputs are exactly equal, 0 otherwise
	elif code == 136:
		opcode = 'OP_EQUALVERIFY' # same as OP_EQUAL, but runs OP_VERIFY afterward
	# arithmetic
	elif code == 139:
		opcode = 'OP_1ADD' # 1 is added to the input
	elif code == 140:
		opcode = 'OP_1SUB' # 1 is subtracted from the input
	elif code == 141:
		opcode = 'OP_2MUL' # the input is multiplied by 2. disabled
	elif code == 142:
		opcode = 'OP_2DIV' # the input is divided by 2. disabled
	elif code == 143:
		opcode = 'OP_NEGATE' # the sign of the input is flipped
	elif code == 144:
		opcode = 'OP_ABS' # the input is made positive
	elif code == 145:
		opcode = 'OP_NOT' # if the input is 0 or 1, it is flipped. Otherwise the output will be 0
	elif code == 146:
		opcode = 'OP_0NOTEQUAL' # returns 0 if the input is 0. 1 otherwise
	elif code == 147:
		opcode = 'OP_ADD' # a is added to b
	elif code == 148:
		opcode = 'OP_SUB' # b is subtracted from a
	elif code == 149:
		opcode = 'OP_MUL' # a is multiplied by b. disabled
	elif code == 150:
		opcode = 'OP_DIV' # a is divided by b. disabled
	elif code == 151:
		opcode = 'OP_MOD' # returns the remainder after dividing a by b. disabled
	elif code == 152:
		opcode = 'OP_LSHIFT' # shifts a left b bits, preserving sign. disabled
	elif code == 153:
		opcode = 'OP_RSHIFT' # shifts a right b bits, preserving sign. disabled
	elif code == 154:
		opcode = 'OP_BOOLAND' # if both a and b are not 0, the output is 1. Otherwise 0
	elif code == 155:
		opcode = 'OP_BOOLOR' # if a or b is not 0, the output is 1. Otherwise 0
	elif code == 156:
		opcode = 'OP_NUMEQUAL' # returns 1 if the numbers are equal, 0 otherwise
	elif code == 157:
		opcode = 'OP_NUMEQUALVERIFY' # same as OP_NUMEQUAL, but runs OP_VERIFY afterward
	elif code == 158:
		opcode = 'OP_NUMNOTEQUAL' # returns 1 if the numbers are not equal, 0 otherwise
	elif code == 159:
		opcode = 'OP_LESSTHAN' # returns 1 if a is less than b, 0 otherwise
	elif code == 160:
		opcode = 'OP_GREATERTHAN' # returns 1 if a is greater than b, 0 otherwise
	elif code == 161:
		opcode = 'OP_LESSTHANOREQUAL' # returns 1 if a is less than or equal to b, 0 otherwise
	elif code == 162:
		opcode = 'OP_GREATERTHANOREQUAL' # returns 1 if a is greater than or equal to b, 0 otherwise
	elif code == 163:
		opcode = 'OP_MIN' # returns the smaller of a and b
	elif code == 164:
		opcode = 'OP_MAX' # returns the larger of a and b
	elif code == 165:
		opcode = 'OP_WITHIN' # returns 1 if x is within the specified range (left-inclusive), else 0
	# crypto
	elif code == 166:
		opcode = 'OP_RIPEMD160' # the input is hashed using RIPEMD-160
	elif code == 167:
		opcode = 'OP_SHA1' # the input is hashed using SHA-1
	elif code == 168:
		opcode = 'OP_SHA256' # the input is hashed using SHA-256
	elif code == 169:
		opcode = 'OP_HASH160' # the input is hashed twice: first with SHA-256 and then with RIPEMD-160
	elif code == 170:
		opcode = 'OP_HASH256' # the input is hashed two times with SHA-256
	elif code == 171:
		opcode = 'OP_CODESEPARATOR' # only match signatures after the latets OP_CODESEPARATOR
	elif code == 172:
		opcode = 'OP_CHECKSIG' # hash all transaction outputs, inputs, and script. return 1 if valid
	elif code == 173:
		opcode = 'OP_CHECKSIGVERIFY' # same as OP_CHECKSIG, but OP_VERIFY is executed afterward
	elif code == 174:
		opcode = 'OP_CHECKMULTISIG' # execute OP_CHECKSIG for each signature and public key pair
	elif code == 175:
		opcode = 'OP_CHECKMULTISIGVERIFY' # same as OP_CHECKMULTISIG, but OP_VERIFY is executed afterward
	# pseudo-words
	elif code == 253:
		opcode = 'OP_PUBKEYHASH' # nts a public key hashed with OP_HASH160
	elif code == 254:
		opcode = 'OP_PUBKEY' # nts a public key compatible with OP_CHECKSIG
	elif code == 255:
		opcode = 'OP_INVALIDOPCODE' # any opcode that is not yet assigned
	# reserved words
	elif code == 80	:
		opcode = 'OP_RESERVED' # transaction is invalid unless occuring in an unexecuted OP_IF branch
	elif code == 98	:
		opcode = 'OP_VER' # transaction is invalid unless occuring in an unexecuted OP_IF branch
	elif code == 101:
		opcode = 'OP_VERIF' # transaction is invalid even when occuring in an unexecuted OP_IF branch
	elif code == 102:
		opcode = 'OP_VERNOTIF' # transaction is invalid even when occuring in an unexecuted OP_IF branch
	elif code == 137:
		opcode = 'OP_RESERVED1' # transaction is invalid unless occuring in an unexecuted OP_IF branch
	elif code == 138:
		opcode = 'OP_RESERVED2' # transaction is invalid unless occuring in an unexecuted OP_IF branch
	elif code == 176:
		opcode = 'OP_NOP1' # the word is ignored
	elif code == 177:
		opcode = 'OP_NOP2' # the word is ignored
	elif code == 178:
		opcode = 'OP_NOP3' # the word is ignored
	elif code == 179:
		opcode = 'OP_NOP4' # the word is ignored
	elif code == 180:
		opcode = 'OP_NOP5' # the word is ignored
	elif code == 181:
		opcode = 'OP_NOP6' # the word is ignored
	elif code == 182:
		opcode = 'OP_NOP7' # the word is ignored
	elif code == 183:
		opcode = 'OP_NOP8' # the word is ignored
	elif code == 184:
		opcode = 'OP_NOP9' # the word is ignored
	elif code == 185:
		opcode = 'OP_NOP10' # the word is ignored
	elif code == 252:
		opcode = 'ERROR' # include to keep the parser going, and for easy search in the db later
	else:
		raise Exception('byte [' + str(code) + '] has no corresponding opcode')
#	if config.debug > 2:
#		mulll_msg.manage('debug', 'byte [' + str(code) + '] translates to opcode [' + opcode + ']')
	return opcode

def calculate_merkle_root(merkle_tree_elements):
	"""recursively calculate the merkle root from the leaves"""
	if not merkle_tree_elements:
		raise Exception('nothing passed to function [calculate_merkle_root]')
	if len(merkle_tree_elements) == 1: # just return the input
		return merkle_tree_elements[0]
	nodes = ['placeholder']
	nodes[0] = merkle_tree_elements # convert all leaf nodes to binary
	level = 0
	while True:
		num = len(nodes[level])
		nodes.append('placeholder') # initialise next level
		for (i, leaf) in enumerate(nodes[level]):
			if i % 2: # odd
				continue
			dhash = binascii.a2b_hex(mulll_str.little_endian(leaf))
			if (i + 1) == num: # we are on the last index
				concat = dhash + dhash
			else: # not on the last index
				dhash_next = binascii.a2b_hex(mulll_str.little_endian(nodes[level][i + 1]))
				concat = dhash + dhash_next
			node_val = double_sha256(concat)
			if not i:
				nodes[level + 1] = [node_val]
			else:
				nodes[level + 1].append(node_val)
		if len(nodes[level + 1]) == 1:
			root = nodes[level + 1][0]
#			if config.debug > 2:
#				full_tree = sum(nodes, []) # flatten
#				mulll_msg.manage('debug', 'extracted merkle root [' + str(root) + '] and full merkle tree: [' + pprint.pformat(full_tree, width = 1) + ']')
			return root
		level = level + 1

def pub_ecdsa2btc_address(ecdsa_pub_key):
	"""take the public ecdsa key (bytes) and output a standard bitcoin address (string), following https://en.bitcoin.it/wiki/Technical_background_of_Bitcoin_addresses"""
	ecdsa_pub_key_length = len(ecdsa_pub_key)
	if ecdsa_pub_key_length != 65:
		raise Exception('the public ecdsa key must be 130 characters long, but it is [' + str(ecdsa_pub_key_length) + '] characters')
	result2 = hashlib.sha256(ecdsa_pub_key) # result as a hashlib object (600ffe422b4e00731a59557a5cca46cc183944191006324a447bdb2d98d4b408)
#	if config.debug > 2:
#		mulll_msg.manage('debug', 'ecdsa pub key hashed with sha256: [' + result2.hexdigest() + ']')
	result3 = hashlib.new('ripemd160')
	result3.update(result2.digest())
#	if config.debug > 2:
#		mulll_msg.manage('debug', 'then hashed with ripemd160: [' + result3.hexdigest() + ']')
	return hash1602btc_address(result3.hexdigest())

def btc_address2hash160(btc_address):
	"""from https://github.com/gavinandresen/bitcointools/blob/master/base58.py"""
	bytes = base58_decode(btc_address, 25)
	return bytes[1:21]

def hash1602btc_address(hash160):
	"""convert the hash160 output (hexstring) to the bitcoin address"""
	result4 = '00' + hash160 # to string (00010966776006953d5567439e5e39f86a0d273bee)
#	if config.debug > 2:
#		mulll_msg.manage('debug', 'added leading zeros: [' + result4 + ']')
	result5 = hashlib.sha256(binascii.a2b_hex(result4)) # result as a hashlib object (445c7a8007a93d8733188288bb320a8fe2debd2ae1b47f0f50bc10bae845c094)
#	if config.debug > 2:
#		mulll_msg.manage('debug', 'then hashed with sha256: [' + result5.hexdigest() + ']')
	result6 = hashlib.sha256(result5.digest()) # result as a hashlib object (d61967f63c7dd183914a4ae452c9f6ad5d462ce3d277798075b107615c1a8a30)
#	if config.debug > 2:
#		mulll_msg.manage('debug', 'and hashed again with sha256: [' + result6.hexdigest() + ']')
	checksum = result6.hexdigest()[ : 8] # checksum is the first 4 bytes
	hex_btc_address = result4 + checksum # 00010966776006953d5567439e5e39f86a0d273beed61967f6
#	if config.debug > 2:
#		mulll_msg.manage('debug', 'hex bitcoin address: [' + hex_btc_address + ']')
	decimal_btc_address = int(hex_btc_address, 16) # 25420294593250030202636073700053352635053786165627414518
#	if config.debug > 2:
#		mulll_msg.manage('debug', 'decimal bitcoin address: [' + str(decimal_btc_address) + ']')
	btc_address = version_symbol('ecdsa_pub_key_hash') + base58_encode(decimal_btc_address) # 16UwLL9Risc3QfPqBUvKofHmBQ7wMtjvM
#	if config.debug > 2:
#		mulll_msg.manage('debug', 'bitcoin address: [' + btc_address + ']')
	return btc_address

def encode_variable_length_int(value):
	"""encode a value as a variable length integer"""
	if value < 253: # encode as a single byte
		bytes = struct.pack('B', value)
	elif value < 0xffff: # encode as 1 format byte and 2 value bytes (little endian)
		bytes = struct.pack('B', 253) + struct.pack('<H', value)
	elif value < 0xffffffff: # encode as 1 format byte and 4 value bytes (little endian)
		bytes = struct.pack('B', 254) + struct.pack('<L', value)
	elif value < 0xffffffffffffffff: # encode as 1 format byte and 8 value bytes (little endian)
		bytes = struct.pack('B', 255) + struct.pack('<Q', value)
	else:
		raise Exception('value [' + str(value) + '] is too big to be encoded as a variable length integer')
#	if config.debug > 2:
#		mulll_msg.manage('debug', 'value [' + str(value) + '] has been encoded to bytes [' + bin2hex_str(bytes) + ']')
	return bytes

def decode_variable_length_int(bytes):
	"""extract the value of a variable length integer"""
	bytes_in = 0
	first_byte = struct.unpack('B', bytes[ : 1])[0] # 1 byte binary to decimal int
	bytes = bytes[1 : ] # don't need the first byte anymore
	bytes_in += 1
	if first_byte == 253: # read the next two bytes as a little endian 16-bit number (total bytes read = 3)
		value = struct.unpack('<H', bytes[ : 2])[0] # 2 bytes binary to decimal int (little endian)
		bytes_in += 2
	elif first_byte == 254: # read the next four bytes as a little endian 32-bit number (total bytes read = 5)
		value = struct.unpack('<L', bytes[ : 4])[0] # 4 bytes binary to decimal int (little endian)
		bytes_in += 4
	elif first_byte == 255: # read the next eight bytes as a little endian 64-bit number (total bytes read = 9)
		value = struct.unpack('<Q', bytes[ : 8])[0] # 8 bytes binary to decimal int (little endian)
		bytes_in += 8
	else: # if the first byte is less than 253, use the byte literally
		value = first_byte
#	if config.debug > 2:
#		mulll_msg.manage('debug', 'bytes [' + bin2hex_str(bytes) + '] contain integer [' + str(value) + '] which has a length of [' + str(bytes_in) + '] bytes')
	return (value, bytes_in)

def truncate_hash_table(hash_table, new_len):
	"""take a dict of the form {hashstring : block_num} and leave [new_len] upper blocks"""
	reversed_hash_table = {block_num : hashstring for (hashstring, block_num) in hash_table.items()}
	to_remove = sorted(reversed_hash_table)[ : -new_len] # only keep [new_len] on the end
	for block_num in to_remove:
		del reversed_hash_table[block_num]
	hash_table = {hashstring : block_num for (block_num, hashstring) in reversed_hash_table.items()}
#	if config.debug > 2:
#		mulll_msg.manage('debug', 'new truncated hash table: [' + pprint.pformat(hash_table, width = 1) + ']')
	return hash_table

def base58_encode(input_num):
	"""encode the bytes string into a base58 string. see https://en.bitcoin.it/wiki/Base58Check_encoding for doco
	code modified from http://darklaunch.com/2009/08/07/base58-encode-and-decode-using-php-with-example-base58-encode-base58-decode using bcmath"""
	base = len(base58alphabet)
	encoded = ''
	num = input_num
	while num >= base:
		mod = num % base
		encoded = base58alphabet[mod] + encoded
		num = num / base

	if num:
		encoded = base58alphabet[num] + encoded
#	if config.debug > 2:
#		mulll_msg.manage('debug', 'number [' + str(input_num) + '] has been base58 encoded to [' + str(encoded) + ']')
	return encoded

def base58_decode(value, output_format = 'bytes'):
	"""decode the value into a string of bytes in base58
	from https://github.com/gavinandresen/bitcointools/blob/master/base58.py"""
	base = len(base58alphabet)
	long_value = 0L # init
	for (i, char) in enumerate(value[ : : -1]): # loop through the input value one char at a time in reverse order (i starts at 0)
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
	if output_format == 'hex_string':
		decoded = bin2hex_str(decoded)
	elif output_format == 'bytes':
		pass # already in this format
	elif output_format == 'int':
		decoded = int(bin2hex_str(decoded), 16) # convert from hex bytes to decimal long integer
	else:
		raise Exception('unrecognised output format [' + output_format + ']')
#	if config.debug > 2:
#		mulll_msg.manage('debug', 'value [' + str(value) + '] has been base58 decoded to [' + str(decoded) + ']')
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
		raise Exception('unrecognised bitcoin use [' + use + ']')
	if formatt not in symbol:
		raise Exception('format [' + formatt + '] is not recognised')
	symbol = symbol[formatt] # return decimal or prefix
#	if config.debug > 2:
#		mulll_msg.manage('debug', 'bitcoin use [' + use + '] has version symbol [' + symbol + ']')
	return symbol

def get_address_type(address):
	if address[0] == "1": # bitcoin
		if len(address) != 34:
			sys.exit("address %s looks like a bitcoin public key hash, but does not have the necessary 34 characters" % address)
		return "bitcoin pubkey hash"
	if address[0] == "3": # bitcoin
		if len(address) != 34:
			sys.exit("address %s looks like a bitcoin script hash, but does not have the necessary 34 characters" % address)
		return "bitcoin script hash"
	if address[0] == "L": # litecoin
		if len(address) != 34:
			sys.exit("address %s looks like a litecoin public key hash, but does not have the necessary 34 characters" % address)
		return "litecoin pubkey hash"
	if address[0] in ["M", "N"]: # namecoin
		if len(address) != 34:
			sys.exit("address %s looks like a namecoin public key hash, but does not have the necessary 34 characters" % address)
		return "namecoin pubkey hash"
	if address[0] in ["m", "n"]: # bitcoin testnet
		if len(address) != 34:
			sys.exit("address %s looks like a bitcoin testnet public key hash, but does not have the necessary 34 characters" % address)
		return "bitcoin-testnet pubkey hash"
	return "unknown"

def valid_hash(hash_str):
	if len(hash_str) != 64:
		return False
	try: # make sure the hash string has only hex characters
		int(hash_str, 16)
	except:
		return False
	return True

def bin2hex_str(binary):
	return binascii.b2a_hex(binary)

def bin2dec_le(binary):
	num_bytes = len(binary)
	if num_bytes == 4:
		encoding = '<I'
	elif num_bytes == 8:
		encoding = '<Q'
	else:
		raise Exception('length %s not supported' % num_bytes)
	return struct.unpack(encoding, binary)[0] # num_bytes bytes binary to decimal int (little endian)

#!/usr/bin/env python2.7
# parse the input arguments into variables

from optparse import OptionParser
import os, sys, btc_grunt, progress_meter, json, collections

with open("readme.json", "r") as file:
	readme_json = file.read()
file.close()

readme_dict = json.loads(readme_json, object_pairs_hook = collections.OrderedDict) # read file readme.json to an ordered dict
arg_parser = OptionParser(usage = "Usage: " + readme_dict["synopsis"])
for option in readme_dict["options"]:
	args_listed = [] # reset
	if "short_arg" in option:
		if option["short_arg"] == "-h":
			continue
		args_listed.append(option["short_arg"])
	if "long_arg" in option:
		if option["long_arg"] == "--help":
			continue
		args_listed.append(option["long_arg"])
	if "short_arg" not in option and "long_arg" not in option:
		sys.exit("all options must have at least a short arg or a long arg specified")
	args_named = {} # reset
	if "dest" in option:
		args_named["dest"] = option["dest"]
		args_named["action"] = "store"
	else:
		args_named["action"] = "store_true"
	if "help" in option:
		args_named["help"] = option["help"]
	if "default" in option:
		args_named["default"] = option["default"]
	if "type" in option:
		args_named["type"] = option["type"]
	arg_parser.add_option(*args_listed, **args_named)

(options, _) = arg_parser.parse_args()

# sanitize the options and their values

if options.ADDRESSES:
	currency_types = {}
	for address in options.ADDRESSES.split(","):
		currency_types[address] = btc_grunt.get_address_type(address)
		try:
			if first_currency != currency_types[address]:
				sys.exit("error: all supplied addresses must be of the same currency")
		except: # first_currency is not yet initialised
			first_currency = currency_types[address]

if options.TXHASHES:
	for tx_hash in options.TXHASHES.split(","):
		if not btc_grunt.valid_hash(tx_hash):
			sys.exit("error: supplied transaction hash %s is not of a valid format" % tx_hash)

if options.BLOCKHASHES:
	for block_hash in options.BLOCKHASHES.split(","):
		if not btc_grunt.valid_hash(block_hash):
			sys.exit("error: supplied block hash %s is not of a valid format" % block_hash)

if not options.dont_validate_merkle_trees:
	sys.exit("option --dont-validate-merkle-trees is currently mandatory as merkle tree validation is currently a work in progress")

if options.ENDBLOCKNUM and options.ENDBLOCKHASH:
	sys.exit("if option --end-blocknum is specified then option --end-blockhash cannot also be specified")

if options.STARTBLOCKNUM and options.STARTBLOCKHASH:
	sys.exit("if option --start-blocknum is specified then option --start-blockhash cannot also be specified")

if options.LIMIT and (options.end_blocknum or options.end_blockhash):
	sys.exit("if option --limit (-L) is specified then neither option --end-blockhash nor option --end-blocknum can be specified")

if options.FORMAT not in ["JSON", "BINARY"]:
	sys.exit("option --output-format (-o) must be either JSON or BINARY")

if options.get_balance:
	if not options.ADDRESSES:
		sys.exit("if option --get-balance (-b) is selected then option --addresses (-a) is mandatory")
	if options.get_full_blocks:
		sys.exit("if option --get-balance (-b) is selected then option --get-full-blocks (-f) cannot also be selected")
	if options.get_transactions:
		sys.exit("if option --get-balance (-b) is selected then option --get-transactions (-t) cannot also be selected")
	if options.FORMAT == "BINARY":
		sys.exit("option --get-balance (-b) cannot be selected while option --output-format (-o) is set to BINARY")
	sys.exit("unimplemented")

if options.get_full_blocks:
	if options.get_balance:
		sys.exit("if option --get-full-blocks (-f) is selected then option --get-balance (-b) cannot also be selected")
	if options.get_transactions:
		sys.exit("if option --get-full-blocks (-f) is selected then option --get-transactions (-t) cannot also be selected")
	sys.exit("unimplemented")

if options.get_transactions:
	if options.get_full_blocks:
		sys.exit("if option --get-transactions (-t) is selected then option --get-full-blocks (-f) cannot also be selected")
	if options.get_balance:
		sys.exit("if option --get-transactions (-t) is selected then option --get-balance (-b) cannot also be selected")
	sys.exit("unimplemented")

# now extract the data related to the specified addresses/transactions/blocks. 

# - first get the full raw (non-orphan) blocks which contain either the specified addresses,
#   transaction hashes, blockhashes, or are within the specified range. Unless suppressed, a 
#   warning is given if the range is larger than 10 blocks.

# - then eliminate any blocks with merkle trees which do not hash correctly

# ** print data here and exit here when --get-full-blocks (-f) is selected **

# - then extract the transactions which contain the specified addresses or specified
#   transaction hashes.

# ** print data here and exit here when --get-transactions (-t) is selected **

# - then extract the balance for each of the specified addresses

# ** print data here and exit here when --get-balance (-b) is selected **


binary_blocks = btc_grunt.extract_blocks(options)
binary_blocks = [binary_block for binary_block in binary_blocks if btc_grunt.validate_block_hash(binary_block)]

if not options.dont_validate_merkle_trees:
	binary_blocks = [binary_block for binary_block in binary_blocks if btc_grunt.validate_merkle_tree(binary_block)]

if options.get_full_blocks:
	if options.FORMAT == "JSON":
		parsed_blocks = [btc_grunt.parse_block(binary_block) for binary_block in binary_blocks]
		json.dumps(parsed_blocks)
	elif options.FORMAT == "BINARY":
		sys.exit("unimplemented")
	sys.exit(0)

binary_txs = btc_grunt.extract_txs(binary_blocks, addresses)

if options.get_transactions:
	txs = extract_raw_txs(addresses)

if options.get_balance:
	txs = extract_raw_txs(addresses)

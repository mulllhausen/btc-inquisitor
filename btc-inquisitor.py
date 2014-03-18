#!/usr/bin/env python2.7
# parse the input arguments into variables

from optparse import OptionParser
import os, sys, btc_grunt, json, collections, pprint, dicttoxml, xml.dom.minidom

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
	first_currency = ""
	for address in options.ADDRESSES.split(","):
		currency_types[address] = btc_grunt.get_address_type(address)
#		print address, currency_types[address] # debug use only
		if not first_currency:
			first_currency = currency_types[address]
		if first_currency != currency_types[address]:
			sys.exit("error: all supplied addresses must be of the same currency:\n%s" % pprint.pformat(currency_types, width = -1))

if options.TXHASHES:
	for tx_hash in options.TXHASHES.split(","):
		if not btc_grunt.valid_hash(tx_hash):
			sys.exit("error: supplied transaction hash %s is not in the correct format" % tx_hash)

if options.BLOCKHASHES:
	for block_hash in options.BLOCKHASHES.split(","):
		if not btc_grunt.valid_hash(block_hash):
			sys.exit("error: supplied block hash %s is not n the correct format" % block_hash)

if options.STARTBLOCKNUM and options.STARTBLOCKHASH:
	sys.exit("if option --start-blocknum is specified then option --start-blockhash cannot also be specified")

if options.ENDBLOCKNUM and options.ENDBLOCKHASH:
	sys.exit("if option --end-blocknum is specified then option --end-blockhash cannot also be specified")

if options.LIMIT and options.ENDBLOCKNUM:
	sys.exit("if option --limit (-L) is specified then option --end-blocknum cannot also be specified")

if options.LIMIT and options.ENDBLOCKHASH:
	sys.exit("if option --limit (-L) is specified then option --end-blockhash cannot also be specified")

permitted_formats = ["MULTILINE-JSON", "SINGLE-LINE-JSON", "MULTILINE-XML", "SINGLE-LINE-XML", "BINARY"]
if options.FORMAT not in permitted_formats:
	sys.exit("option --output-format (-o) must be either " + " or ".join(permitted_formats))

if options.get_balance:
	if not options.ADDRESSES:
		sys.exit("if option --get-balance (-b) is selected then option --addresses (-a) is mandatory")
	if options.get_full_blocks:
		sys.exit("if option --get-balance (-b) is selected then option --get-full-blocks (-f) cannot also be selected")
	if options.get_transactions:
		sys.exit("if option --get-balance (-b) is selected then option --get-transactions (-t) cannot also be selected")
	if options.FORMAT == "BINARY":
		sys.exit("option --get-balance (-b) cannot be selected while option --output-format (-o) is set to BINARY")

if options.get_full_blocks:
	if options.get_balance:
		sys.exit("if option --get-full-blocks (-f) is selected then option --get-balance (-b) cannot also be selected")
	if options.get_transactions:
		sys.exit("if option --get-full-blocks (-f) is selected then option --get-transactions (-t) cannot also be selected")

if options.get_transactions:
	if options.get_full_blocks:
		sys.exit("if option --get-transactions (-t) is selected then option --get-full-blocks (-f) cannot also be selected")
	if options.get_balance:
		sys.exit("if option --get-transactions (-t) is selected then option --get-balance (-b) cannot also be selected")

# now extract the data related to the specified addresses/transactions/blocks. 

# - first get the full raw (non-orphan) blocks which contain either the specified addresses,
#   transaction hashes, blockhashes, or are within the specified range.

# - then eliminate any blocks with merkle trees which do not hash correctly

# ** print data here and exit here when --get-full-blocks (-f) is selected **

# - then extract the transactions which contain the specified addresses or specified
#   transaction hashes.

# ** print data here and exit here when --get-transactions (-t) is selected **

# - then extract the balance for each of the specified addresses

# ** print data here and exit here when --get-balance (-b) is selected **

binary_blocks = btc_grunt.get_full_blocks(options) # as dict
if not binary_blocks:
	sys.exit(0)

if not options.allow_orphans: # eliminate orphan blocks...
	for abs_block_num in sorted(binary_blocks): # orphan blocks often have incorrect nonce values
		if not btc_grunt.valid_merkle_tree(binary_blocks[abs_block_num]):
			del binary_blocks[abs_block_num]

	for abs_block_num in binary_blocks: # orphan blocks often have incorrect merkle root values
		if not btc_grunt.valid_block_nonce(binary_blocks[abs_block_num]):
			del binary_blocks[abs_block_num]

if options.get_full_blocks:
	if ("JSON" in options.FORMAT) or ("XML" in options.FORMAT):
		parsed_blocks = {}
		for abs_block_num in sorted(binary_blocks):
			parsed_blocks[abs_block_num] = btc_grunt.human_readable_block(binary_blocks[abs_block_num])
		if options.FORMAT == "MULTILINE-JSON":
			print "\n".join([l.rstrip() for l in json.dumps(parsed_blocks, sort_keys = True, indent = 4).splitlines()])
		elif options.FORMAT == "SINGLE-LINE-JSON":
			print json.dumps(parsed_blocks, sort_keys = True)
		elif options.FORMAT == "MULTILINE-XML":
			print xml.dom.minidom.parseString(dicttoxml.dicttoxml(parsed_blocks)).toprettyxml()
		elif options.FORMAT == "SINGLE-LINE-XML":
			print dicttoxml.dicttoxml(parsed_blocks)
	elif options.FORMAT == "BINARY":
		all_blocks = ""
		for abs_block_num in sorted(binary_blocks):
			all_blocks += binary_blocks[abs_block_num]
		print all_blocks
	sys.exit(0)

binary_txs = btc_grunt.extract_txs(binary_blocks, addresses)

if options.get_transactions:
	txs = extract_raw_txs(addresses)

if options.get_balance:
	txs = extract_raw_txs(addresses)

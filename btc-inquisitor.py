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
		sys.exit("Error: All options must have at least a short arg or a long arg specified.")
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
	if options.ADDRESSES[-1] == ",":
		sys.exit("Error: Trailing comma found in the ADDRESSES input argument. Please ensure there are no spaces in the ADDRESSES input argument.")
	currency_types = {}
	first_currency = ""
	for address in options.ADDRESSES.split(","):
		currency_types[address] = btc_grunt.get_currency(address)
		if currency_types[address] == "any":
			del currency_types[address]
			continue
		if not first_currency:
			first_currency = currency_types[address]
			continue
		if first_currency != currency_types[address]:
			sys.exit("Error: All supplied addresses must be of the same currency:\n%s" % pprint.pformat(currency_types, width = -1))

if options.TXHASHES is not None:
	if options.TXHASHES[-1] == ",":
		sys.exit("Error: Trailing comma found in the TXHASHES input argument. Please ensure there are no spaces in the TXHASHES input argument.")
	for tx_hash in options.TXHASHES.split(","):
		if not btc_grunt.valid_hash(tx_hash):
			sys.exit("Error: Supplied transaction hash %s is not in the correct format." % tx_hash)

if options.BLOCKHASHES is not None:
	if options.BLOCKHASHES[-1] == ",":
		sys.exit("Error: Trailing comma found in the BLOCKHASHES input argument. Please ensure there are no spaces in the BLOCKHASHES input argument.")
	for block_hash in options.BLOCKHASHES.split(","):
		if not btc_grunt.valid_hash(block_hash):
			sys.exit("Error: Supplied block hash %s is not n the correct format." % block_hash)

if options.STARTBLOCKNUM is not None and options.STARTBLOCKHASH is not None:
	sys.exit("Error: If option --start-blocknum is specified then option --start-blockhash cannot also be specified.")

if options.ENDBLOCKNUM is not None and options.ENDBLOCKHASH is not None:
	sys.exit("Error: If option --end-blocknum is specified then option --end-blockhash cannot also be specified.")

if options.LIMIT is not None and options.ENDBLOCKNUM is not None:
	sys.exit("Error: If option --limit (-L) is specified then option --end-blocknum cannot also be specified.")

if options.LIMIT is not None and options.ENDBLOCKHASH is not None:
	sys.exit("Error: If option --limit (-L) is specified then option --end-blockhash cannot also be specified.")

if options.STARTBLOCKNUM is None and options.STARTBLOCKHASH is None: # go from the start
	options.STARTBLOCKNUM = 0

permitted_output_formats = ["MULTILINE-JSON", "SINGLE-LINE-JSON", "MULTILINE-XML", "SINGLE-LINE-XML", "BINARY", "HEX"]
if options.FORMAT not in permitted_output_formats:
	sys.exit("Error: Option --output-format (-o) must be either " + ", ".join(permitted_output_formats[:-1]) + " or " + permitted_output_formats[-1] + ".")

if options.get_balance:
	if not options.ADDRESSES:
		sys.exit("Error: If option --get-balance (-b) is selected then option --addresses (-a) is mandatory.")
	if options.get_full_blocks:
		sys.exit("Error: If option --get-balance (-b) is selected then option --get-full-blocks (-f) cannot also be selected.")
	if options.get_transactions:
		sys.exit("Error: If option --get-balance (-b) is selected then option --get-transactions (-t) cannot also be selected.")
	if options.FORMAT == "BINARY":
		sys.exit("Error: Option --get-balance (-b) cannot be selected while option --output-format (-o) is set to BINARY.")

if options.get_full_blocks:
	if options.get_balance:
		sys.exit("Error: If option --get-full-blocks (-f) is selected then option --get-balance (-b) cannot also be selected.")
	if options.get_transactions:
		sys.exit("Error: If option --get-full-blocks (-f) is selected then option --get-transactions (-t) cannot also be selected.")

if options.get_transactions:
	if options.get_full_blocks:
		sys.exit("Error: If option --get-transactions (-t) is selected then option --get-full-blocks (-f) cannot also be selected.")
	if options.get_balance:
		sys.exit("Error: If option --get-transactions (-t) is selected then option --get-balance (-b) cannot also be selected.")

inputs_have_been_sanitized = True # :)

# now extract the data related to the specified addresses/transactions/blocks. 

# - first get the full raw (non-orphan) blocks which contain either the specified addresses, transaction hashes, blockhashes, or are within the specified range.

# - then, if specified by the user, eliminate any blocks with merkle trees which do not hash correctly

# ** print data here and exit here when --get-full-blocks (-f) is selected **

# - then extract the transactions which contain the specified addresses or specified transaction hashes.

# ** print data here and exit here when --get-transactions (-t) is selected **

# - then extract the balance for each of the specified addresses

# ** print data here and exit here when --get-balance (-b) is selected **

if options.ADDRESSES is not None:
	options.ADDRESSES = btc_grunt.explode_addresses(options.ADDRESSES)

binary_blocks = btc_grunt.get_full_blocks(options, inputs_have_been_sanitized) # as dict
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
			print "\n".join(l.rstrip() for l in json.dumps(parsed_blocks, sort_keys = True, indent = 4).splitlines())
			# rstrip removes the trailing space added by the json dump
		elif options.FORMAT == "SINGLE-LINE-JSON":
			print json.dumps(parsed_blocks, sort_keys = True)
		elif options.FORMAT == "MULTILINE-XML":
			print xml.dom.minidom.parseString(dicttoxml.dicttoxml(parsed_blocks)).toprettyxml()
		elif options.FORMAT == "SINGLE-LINE-XML":
			print dicttoxml.dicttoxml(parsed_blocks)
	elif options.FORMAT == "BINARY":
		print "".join(binary_blocks[abs_block_num] for abs_block_num in sorted(binary_blocks))
	elif options.FORMAT == "HEX":
		print "\n".join(btc_grunt.bin2hex(binary_blocks[abs_block_num]) for abs_block_num in sorted(binary_blocks))
	sys.exit(0)

binary_txs = btc_grunt.extract_txs(binary_blocks, options) # as list

if options.get_transactions:
	if ("JSON" in options.FORMAT) or ("XML" in options.FORMAT):
		parsed_txs = [btc_grunt.human_readable_tx(binary_tx) for binary_tx in binary_txs]
		if options.FORMAT == "MULTILINE-JSON":
			for tx_dict in parsed_txs:
				print "\n".join(l.rstrip() for l in json.dumps(tx_dict, sort_keys = True, indent = 4).splitlines())
				# rstrip removes the trailing space added by the json dump
		elif options.FORMAT == "SINGLE-LINE-JSON":
			print "\n".join(json.dumps(tx, sort_keys = True) for tx in parsed_txs)
		elif options.FORMAT == "MULTILINE-XML":
			print xml.dom.minidom.parseString(dicttoxml.dicttoxml(parsed_txs)).toprettyxml()
		elif options.FORMAT == "SINGLE-LINE-XML":
			print dicttoxml.dicttoxml(parsed_txs)
	elif options.FORMAT == "BINARY":
		print "".join(binary_txs)
	elif options.FORMAT == "HEX":
		print "\n".join(btc_grunt.bin2hex(tx_bytes) for tx_bytes in sorted(binary_txs))
	sys.exit(0)

if options.get_balance:
	txs = extract_raw_txs(addresses)

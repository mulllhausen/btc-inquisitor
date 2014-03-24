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
	if ("short_arg" not in option) and ("long_arg" not in option):
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
options = btc_grunt.sanitize_options_or_die(options)
inputs_have_been_sanitized = True

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

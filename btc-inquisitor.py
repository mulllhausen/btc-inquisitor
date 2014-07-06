#!/usr/bin/env python2.7
# parse the input arguments into variables

from optparse import OptionParser
import os
import sys
import btc_grunt
import json
import collections
import pprint
import dicttoxml
import xml.dom.minidom

with open("readme.json", "r") as file:
	readme_json = file.read()
file.close()

# read file readme.json to an ordered dict
readme_dict = json.loads(
	readme_json, object_pairs_hook = collections.OrderedDict
)
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
	if (
		("short_arg" not in option) and \
		("long_arg" not in option)
	):
		btc_grunt.die(
			"Error: All options must have at least a short arg or a long arg"
			" specified."
		)
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
# - first get the full raw blocks which contain either the specified addresses,
# transaction hashes, blockhashes, or are within the specified range.
# ** print data here and exit here when --get-full-blocks (-f) is selected **
# - then extract the transactions which contain the specified addresses or
# specified transaction hashes.
# ** print data here and exit here when --get-transactions (-t) is selected **
# - then extract the balance for each of the specified addresses
# ** print data here and exit here when --get-balance (-b) is selected **

if options.ADDRESSES is not None:
	options.ADDRESSES = btc_grunt.explode_addresses(options.ADDRESSES)

blocks = btc_grunt.extract_full_blocks(options, inputs_have_been_sanitized) # dict

if not blocks:
	sys.exit(0)

# update only some from-addresses
if options.ADDRESSES:
	blocks = btc_grunt.update_txin_data(blocks, options)

# check if any from-addresses are missing, and fetch the corresponding
# prev-tx-hash & index for each if so
if (
	(options.FORMAT not in ["BINARY", "HEX"]) and \
	(not options.get_balance) # balance doesn't require the from-addresses
):
	additional_required_data = {}
	for (abs_block_num, block) in blocks.items():
		# returns {"txhash": index, "txhash": index, ...} or {}
		temp = btc_grunt.get_missing_txin_address_data(block, options)
		if temp:
			additional_required_data.update(temp)

	# second pass of the blockchain
	if additional_required_data:
		saved_txhashes = options.TXHASHES
		options.TXHASHES = additional_required_data
		aux_binary_blocks = btc_grunt.extract_full_blocks( # as dict
			options, inputs_have_been_sanitized
		)
		options.TXHASHES = saved_txhashes
		
	# update the from-address (in all original blocks only)
	if aux_binary_blocks:
		if options.revalidate_ecdsa:
			btc_grunt.revalidate_ecdsa(blocks, aux_binary_blocks)
		parsed_blocks = btc_grunt.update_txin_address_data(
			blocks, aux_binary_blocks
		)

if not options.allow_orphans: # eliminate orphan blocks...
	# orphan blocks often have incorrect nonce values
	for abs_block_num in sorted(blocks):
		if not btc_grunt.valid_merkle_tree(blocks[abs_block_num]):
			del blocks[abs_block_num]

	# orphan blocks often have incorrect merkle root values
	for abs_block_num in blocks:
		if not btc_grunt.valid_block_nonce(blocks[abs_block_num]):
			del blocks[abs_block_num]

if options.get_full_blocks:
	if (
		("JSON" in options.FORMAT) or \
		("XML" in options.FORMAT)
	):
		parsed_blocks = {}
		for abs_block_num in sorted(blocks):
			parsed_blocks[abs_block_num] = btc_grunt.human_readable_block(
				blocks[abs_block_num]
			)
		if options.FORMAT == "MULTILINE-JSON":
			print "\n".join(
				l.rstrip() for l in json.dumps(
					parsed_blocks, sort_keys = True, indent = 4
				).splitlines()
			)
			# rstrip removes the trailing space added by the json dump
		elif options.FORMAT == "SINGLE-LINE-JSON":
			print json.dumps(parsed_blocks, sort_keys = True)
		elif options.FORMAT == "MULTILINE-XML":
			print xml.dom.minidom.parseString(
				dicttoxml.dicttoxml(parsed_blocks)
			).toprettyxml()
		elif options.FORMAT == "SINGLE-LINE-XML":
			print dicttoxml.dicttoxml(parsed_blocks)
	elif options.FORMAT == "BINARY":
		print "".join(
			blocks[abs_block_num] for abs_block_num in sorted(blocks)
		)
	elif options.FORMAT == "HEX":
		print "\n".join(
			btc_grunt.bin2hex(blocks[abs_block_num]) for abs_block_num in \
			sorted(blocks)
		)
	sys.exit(0)

txs = btc_grunt.extract_txs(blocks, options) # as list of dicts

if options.get_transactions:
	if (
		("JSON" in options.FORMAT) or \
		("XML" in options.FORMAT)
	):
		# parsed_txs = [btc_grunt.human_readable_tx(binary_tx) for tx in txs]
		if options.FORMAT == "MULTILINE-JSON":
			for tx in txs:
				print "\n".join(l.rstrip() for l in json.dumps(
					tx, sort_keys = True, indent = 4
				).splitlines())
				# rstrip removes the trailing space added by the json dump
		elif options.FORMAT == "SINGLE-LINE-JSON":
			print "\n".join(json.dumps(tx, sort_keys = True) for tx in txs)
		elif options.FORMAT == "MULTILINE-XML":
			print xml.dom.minidom.parseString(dicttoxml.dicttoxml(txs)). \
			toprettyxml()
		elif options.FORMAT == "SINGLE-LINE-XML":
			print dicttoxml.dicttoxml(txs)
	elif options.FORMAT == "BINARY":
		print "".join(txs)
	elif options.FORMAT == "HEX":
		print "\n".join(btc_grunt.bin2hex(tx["bytes"]) for tx in sorted(txs))
	sys.exit(0)

if not options.get_balance:
	sys.exit(0)

balances = btc_grunt.tx_balances(txs, options.ADDRESSES)

if options.FORMAT == "MULTILINE-JSON":
	print json.dumps(balances, sort_keys = True, indent = 4)
if options.FORMAT == "SINGLE-LINE-JSON":
	print json.dumps(balances, sort_keys = True)
elif options.FORMAT == "MULTILINE-XML":
	print xml.dom.minidom.parseString(dicttoxml.dicttoxml(balances)). \
	toprettyxml()
elif options.FORMAT == "SINGLE-LINE-XML":
	print dicttoxml.dicttoxml(balances)

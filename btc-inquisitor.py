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

# transform the user-provided options from the readme ordered dict into options
# that will guide the program behaviour
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

# sanitize the user-provided options and their values
options = btc_grunt.sanitize_options_or_die(options)
inputs_have_been_sanitized = True

# the user provides addresses in a csv string, but we need a list
if options.ADDRESSES is not None:
	options.ADDRESSES = btc_grunt.explode_addresses(options.ADDRESSES)

# returns either a dict of blocks, a list of txs, or a list of address balances
filtered_data = btc_grunt.get_requested_blockchain_data(
	options, inputs_have_been_sanitized
) # dict

# if the user-specified option values result in no data then exit here
if not filtered_data:
	sys.exit(0)

if options.OUTPUT_TYPE == "BLOCKS":
	blocks = filtered_data
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

if options.OUTPUT_TYPE == "TXS":
	txs = filtered_data
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

if options.OUTPUT_TYPE == "BALANCES":
	balances = filtered_data
	if options.FORMAT == "MULTILINE-JSON":
		print json.dumps(balances, sort_keys = True, indent = 4)
	if options.FORMAT == "SINGLE-LINE-JSON":
		print json.dumps(balances, sort_keys = True)
	elif options.FORMAT == "MULTILINE-XML":
		print xml.dom.minidom.parseString(dicttoxml.dicttoxml(balances)). \
		toprettyxml()
	elif options.FORMAT == "SINGLE-LINE-XML":
		print dicttoxml.dicttoxml(balances)
	sys.exit(0)

# thanks to btc_grunt.sanitize_options_or_die() we will never get to this line

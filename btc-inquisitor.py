#!/usr/bin/env python2.7
# parse the input arguments into variables

import os
import sys
import json
import collections
import pprint
import dicttoxml
import xml.dom.minidom

# module to process the user-specified btc-inquisitor options
import options_grunt

# module containing some general bitcoin-related functions
import btc_grunt

with open("readme.json", "r") as file:
	readme_json = file.read()
file.close()

# convert file readme.json to an ordered dict
readme_dict = json.loads(
	readme_json, object_pairs_hook = collections.OrderedDict
)

# transform the user-provided options from json (ordered-dict) into options that
# will guide the program behaviour
options = options_grunt.dict2options(readme_dict)

# sanitize the user-provided options and their values
options = options_grunt.sanitize_options_or_die(options)
inputs_have_been_sanitized = True

# explain back to the user what we are about to do based on the specified
# options
if options.explain:
	print("\naction: %s\n" % options_grunt.explain(options))

# the user provides addresses in a csv string, but we need a list
if options.ADDRESSES is not None:
	options.ADDRESSES = btc_grunt.explode_addresses(options.ADDRESSES)

# returns either a dict of blocks, a list of txs, or a list of address balances
filtered_data = btc_grunt.get_requested_blockchain_data(
	options, inputs_have_been_sanitized
)

# if the user-specified option values result in no data then exit here
if not filtered_data:
	lang_grunt.die("no results found")

if options.OUTPUT_TYPE == "BLOCKS":
	blocks = filtered_data
	if (
		("JSON" in options.FORMAT) or \
		("XML" in options.FORMAT)
	):
		# transform block indexes into the format blockheight-orphannum
		parsed_blocks = {}
		prev_block_height = 0 # init
		orphan_num = -1 # init
		for block_hash in blocks:
			parsed_block = btc_grunt.human_readable_block(blocks[block_hash])
			block_height = parsed_block["block_height"]
			if block_height == prev_block_height:
				orphan_num += 1
				orphan_descr = "-orphan%s" % orphan_num
			else:
				orphan_num = -1 # reset
				orphan_descr = ""
			parsed_blocks["%s%s" % (block_height, orphan_descr)] = parsed_block

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
			blocks[block_hash] for block_hash in blocks
		)
	elif options.FORMAT == "HEX":
		print "\n".join(
			btc_grunt.bin2hex(blocks[block_hash]) for block_hash in blocks
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
		print "\n".join(btc_grunt.bin2hex(tx["bytes"]) for tx in txs)
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

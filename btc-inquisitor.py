#!/usr/bin/env python2.7
# parse the input arguments into variables

import os
import sys
import collections
import json

# module to convert data into human readable form
import lang_grunt

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

# initialise the base directory for storing unspent txs
btc_grunt.init_base_dir()

filtered_blocks = btc_grunt.extract_full_blocks(
	options, inputs_have_been_sanitized
)
# returns either a dict of blocks, a list of txs, or a list of address balances
filtered_data = btc_grunt.final_results_filter(filtered_blocks, options)
formatted_data = btc_grunt.get_formatted_data(options, filtered_data)

# if the user-specified option values result in no data then exit here
if formatted_data is None:
	lang_grunt.die("no results")
else:
	print formatted_data

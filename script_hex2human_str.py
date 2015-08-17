#!/usr/bin/env python2.7

import os, sys

# when executing this script directly include the parent dir in the path
if (
	(__name__ == "__main__") and
	(__package__ is None)
):
	os.sys.path.append(
		os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	)
import btc_grunt

if len(sys.argv) < 2:
	raise ValueError(
		"\n\nUsage: ./script_hex2human_str.py <the script in hex>\n"
		"eg: ./script_hex2human_str.py 76a914b0c1c1de86419f7c6f3186935e6bd6ccb5"
		"2b8ee588ac\n\n"
	)

script_hex = sys.argv[1]

script_bin = btc_grunt.hex2bin(script_hex)

# convert to a list of binary opcodes and data elements
script_list = btc_grunt.script_bin2list(script_bin)

# convert to a human readable string
print btc_grunt.script_list2human_str(script_list)

#!/usr/bin/env python2.7

import os, sys

# when executing this test directly include the parent dir in the path
if (
	(__name__ == "__main__") and
	(__package__ is None)
):
	os.sys.path.append(
		os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	)

verbose = True if "-v" in sys.argv else False

# module to convert data into human readable form
import lang_grunt

# module containing some general bitcoin-related functions
import btc_grunt

import json

################################################################################
# tests for correct address checksums
################################################################################
addresses = [
	"16UwLL9Risc3QfPqBUvKofHmBQ7wMtjvM",
	"1JBrZXKwJiaYWxQiodh6MBZrbuf2JCftuP",
	"131TQefUE4w8ksk1N3FP4a2JHcgb3g3hZ7"
]
for (i, address) in enumerate(addresses):
	if verbose:
		print """
====================== test for correct address checksums %s ===================
""" % i
	test = btc_grunt.valid_address_checksum(address, True)
	if test is not True:
		lang_grunt.die(test)
	else:
		if verbose:
			print "pass"

################################################################################
# tests for incorrect address checksums
################################################################################

# change the second character in each of the above addresses to a Z
for i in range(len(addresses)):
	address_list = list(addresses[i])
	address_list[1] = "Z"
	addresses[i] = "".join(address_list)

for (i, address) in enumerate(addresses):
	if verbose:
		print """
===================== test for incorrect address checksums %s ==================
""" % i
	test = btc_grunt.valid_address_checksum(address, True)
	if test is True:
		lang_grunt.die(
			"address %s is not valid. yet the checksum validates" % address
		)
	else:
		if verbose:
			print "pass"

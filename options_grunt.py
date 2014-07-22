"""module to process the user-specified btc-inquisitor options"""

from optparse import OptionParser
import datetime
import time
import os
import btc_grunt

# module to do language-related stuff for this project
import lang_grunt

# download from http://labix.org/python-dateutil
# cd python-dateutil*
# sudo python setup.py install
from dateutil import parser 

def dict2options(json_options):
	"""
	transform the user-provided options from json (ordered-dict) into options
	that will guide the program behaviour
	"""
	arg_parser = OptionParser(usage = "Usage: %s" % json_options["synopsis"])
	for option in json_options["options"]:
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
			lang_grunt.die(
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
	return options

def explain(options):
	"""
	convert the options to a human readable text string. this is mainly useful
	so that the user can check that their date-formatting was interpreted
	correctly.
	"""
	s = "extracting all "

	output_type = options.OUTPUT_TYPE.upper()
	if output_type == "BLOCKS":
		s += "blocks"

	elif output_type == "TXS":
		s += "transactions"

	elif output_type == "BALANCES":
		s += "balances"

	s += " between "

	if options.STARTBLOCKDATE:
		s += "date %s" % datetime.datetime.fromtimestamp(options.
		STARTBLOCKDATE).strftime("%Y-%m-%d %H:%M:%S")

	elif options.STARTBLOCKHASH:
		s += "hash %s" % options.STARTBLOCKHASH 

	elif options.STARTBLOCKNUM:
		s += "block %s" % options.STARTBLOCKNUM 

	# default start block is the first block
	else:
		s += "block 0"

	s += " and "

	if options.ENDBLOCKDATE:
		s += "date %s" % datetime.datetime.fromtimestamp(options.
		ENDBLOCKDATE).strftime("%Y-%m-%d %H:%M:%S")

	elif options.ENDBLOCKHASH:
		s += "hash %s" % options.ENDBLOCKHASH 

	elif options.ENDBLOCKNUM:
		if options.ENDBLOCKNUM == "end":
			s += "the final block"
		else:
			s += "block %s" % options.ENDBLOCKNUM 

	s += " (inclusive)"

	explain_aux = [] # init

	if options.ADDRESSES:
		if isinstance(options.ADDRESSES, list):
			addresses = lang_grunt.list2human_str(options.ADDRESSES, "or")
		elif isinstance(options.ADDRESSES, str):
			addresses = options.ADDRESSES

		explain_aux.append("with addresses %s" % addresses)

	if options.TXHASHES:
		if isinstance(options.TXHASHES, list):
			txhashes = lang_grunt.list2human_str(options.TXHASHES, "or")
		elif isinstance(options.TXHASHES, str):
			txhashes = options.TXHASHES

		explain_aux.append("with transaction hashes %s" % txhashes)

	if options.BLOCKHASHES:
		if isinstance(options.BLOCKHASHES, list):
			blockhashes = lang_grunt.list2human_str(options.BLOCKHASHES, "or")
		elif isinstance(options.BLOCKHASHES, str):
			blockhashes = options.BLOCKHASHES

		explain_aux.append("with block hashes %s" % blockhashes)

	if explain_aux:
		s += " or ".join(explain_aux)

	if options.ORPHAN_OPTIONS:
		orphan_options = options.ORPHAN_OPTIONS.upper() # capitalize

		if output_type == "BLOCKS":
			are = "are"
		else:
			are = "occur in"

		if orphan_options == "NONE":
			s += ", that %s non-orphan blocks" % are
		if orphan_options == "ALLOW":
			pass
		if orphan_options == "ONLY":
			s += ", that %s orphan blocks" % are
		
	s += ", and outputing in %s format." % options.FORMAT.lower()

	return s

def sanitize_options_or_die(options):
	"""sanitize the options variable - may involve updating it"""

	global n
	n = "\n" if options.progress else ""

	# convert ~/.bitcoin/ to /home/bob/.bitcoin/
	options.BLOCKCHAINDIR = os.path.expanduser(options.BLOCKCHAINDIR)

	if options.ADDRESSES:
		if options.ADDRESSES[-1] == ",":
			lang_grunt.die(
				"Error: Trailing comma found in the ADDRESSES input argument."
				" Please ensure there are no spaces in the ADDRESSES input"
				" argument."
			)
		currency_types = {}
		first_currency = ""
		for address in options.ADDRESSES.split(","):
			currency_types[address] = get_currency(address)
			if currency_types[address] == "any":
				del currency_types[address]
				continue
			if not first_currency:
				first_currency = currency_types[address]
				continue
			if first_currency != currency_types[address]:
				lang_grunt.die(
					"Error: All supplied addresses must be of the same currency"
				    ":\n%s"
					% pprint.pformat(currency_types, width = -1)
				)
		# convert csv string to list
		options.ADDRESSES = [address for address in \
			options.ADDRESSES.split(",")
		]

	if options.TXHASHES:
		if options.TXHASHES[-1] == ",":
			lang_grunt.die(
				"Error: Trailing comma found in the TXHASHES input argument."
				" Please ensure there are no spaces in the TXHASHES input"
				" argument."
			)
		for tx_hash in options.TXHASHES.split(","):
			if not valid_hash(tx_hash):
				lang_grunt.die(
					"Error: Supplied transaction hash %s is not in the correct"
					" format."
					% tx_hash
				)
		# convert csv string to dict of the format {hash: [index, ..., index]}
		# if the indexes sub-list is None then the hash is for a txout, if it is
		# not None then the hash is for a txin. the user can only directly
		# specify txout hashes, but they can indirectly specify a txin hash and
		# indexes by directly specifying options.ADDRESSES, which we will
		# convert to txin hashes and indexes
		options.TXHASHES = {btc_grunt.hex2bin(txhash): None for txhash in \
		options.TXHASHES.split(",")}

	if options.BLOCKHASHES:
		if options.BLOCKHASHES[-1] == ",":
			lang_grunt.die(
				"Error: Trailing comma found in the BLOCKHASHES input argument."
				" Please ensure there are no spaces in the BLOCKHASHES input"
				" argument."
			)
		for block_hash in options.BLOCKHASHES.split(","):
			if not valid_hash(block_hash):
				lang_grunt.die(
					"Error: Supplied block hash %s is not n the correct format."
					% block_hash
				)
		# convert csv string to list
		options.BLOCKHASHES = [btc_grunt.hex2bin(blockhash) for blockhash in \
			options.BLOCKHASHES.split(",")
		]

	# convert limit range to blocknum range if possible. this will also be done
	# again later if hash ranges are converted to block height ranges
	options = convert_range_options(options)

	if options.STARTBLOCKDATE:
		t = parser.parse(options.STARTBLOCKDATE) # to datetime object
		options.STARTBLOCKDATE = time.mktime(t.timetuple()) # to unixtime

	if options.STARTBLOCKHASH:
		options.STARTBLOCKHASH = btc_grunt.hex2bin(options.STARTBLOCKHASH)

	if options.ENDBLOCKDATE:
		t = parser.parse(options.ENDBLOCKDATE) # to datetime object
		options.ENDBLOCKDATE = time.mktime(t.timetuple()) # to unixtime

	if options.ENDBLOCKHASH:
		options.ENDBLOCKHASH = btc_grunt.hex2bin(options.ENDBLOCKHASH)

	num_start_options = 0
	if options.STARTBLOCKDATE:
		num_start_options += 1
	if options.STARTBLOCKHASH:
		num_start_options += 1
	if options.STARTBLOCKNUM:
		num_start_options += 1
	if num_start_options > 1:
		lang_grunt.die(
			"Error: Only one of options --start-blockdate, --start-blockhash"
			" and --start-blocknum can be specified."
		)
	num_end_options = 0
	if options.ENDBLOCKDATE:
		num_end_options += 1
	if options.ENDBLOCKHASH:
		num_end_options += 1
	if options.ENDBLOCKNUM:
		num_end_options += 1
	if num_end_options > 1: 
		lang_grunt.die(
			"Error: Only one of options --end-blockdate, --end-blockhash and"
			" --start-blocknum can be specified."
		)
	if (
		(options.LIMIT) and \
		(num_end_options > 0)
	):
		lang_grunt.die(
			"Error: If option --limit (-L) is specified then neither option"
			" --end-blockdate, nor --end-blockhash, nor --end-blocknum can also"
			" be specified."
		)
	if not num_start_options:
		options.STARTBLOCKNUM = 0 # go from the start

	if not num_end_options:
		options.ENDBLOCKNUM = "end" # go to the end

	permitted_output_formats = [
		"MULTILINE-JSON",
		"SINGLE-LINE-JSON",
		"MULTILINE-XML",
		"SINGLE-LINE-XML",
		"BINARY",
		"HEX"
	]
	if options.FORMAT not in permitted_output_formats:
		lang_grunt.die(
			"Error: Option --output-format (-o) must be either %s."
			% lang_grunt.list2human_str(permitted_output_formats)
		)

	options.ORPHAN_OPTIONS = options.ORPHAN_OPTIONS.upper() # capitalize
	permitted_orphan_options = [
		"NONE",
		"ALLOW",
		"ONLY"
	]
	if options.ORPHAN_OPTIONS not in permitted_orphan_options:
		lang_grunt.die(
			"Error: Option --orphan-options must be either %s."
			% lang_grunt.list2human_str(permitted_orphan_options)
		)

	options.OUTPUT_TYPE = options.OUTPUT_TYPE.upper() # capitalize
	permitted_output_types = [
		"BLOCKS",
		"TXS",
		"BALANCES"
	]
	if options.OUTPUT_TYPE not in permitted_output_types:
		lang_grunt.die(
			"Error: Option --output-types (-t) must be either %s."
			% lang_grunt.list2human_str(permitted_output_types)
		)

	if options.OUTPUT_TYPE == "BALANCES":
		if options.FORMAT == "BINARY":
			lang_grunt.die(
				"Error: Option --get-balance (-b) cannot be selected while"
				" option --output-format (-o) is set to BINARY."
			)
	return options

def sanitize_block_range(options):
	if (
		options.STARTBLOCKNUM and \
		options.ENDBLOCKNUM and \
		(options.ENDBLOCKNUM != "end") and \
		(options.ENDBLOCKNUM < options.STARTBLOCKNUM)
	):
		lang_grunt.die(
			"Error: Your specified end block comes before your specified start"
			" block in the blockchain."
		)

def convert_range_options(options, parsed_block):
	"""
	convert:
	- STARTBLOCKDATE to STARTBLOCKNUM
	- STARTBLOCKHASH to STARTBLOCKNUM
	- ENDBLOCKDATE to ENDBLOCKNUM
	- ENDBLOCKHASH to ENDBLOCKNUM
	- STARTBLOCKNUM + LIMIT to ENDBLOCKNUM
	"""
	# if there is nothing to update then exit here
	if (
		not options.STARTBLOCKDATE and \
		not options.STARTBLOCKHASH and \
		not options.ENDBLOCKDATE and \
		not options.ENDBLOCKHASH and \
		not options.LIMIT
	):
		return options

	if (
		("block_height" in parsed_block) and \
		(parsed_block["block_height"] is not None)
	):
		# if STARTBLOCKNUM has not yet been updated then update it if possible
		if options.STARTBLOCKNUM is None:

			# STARTBLOCKDATE to STARTBLOCKNUM
			if (
				("timestamp" in parsed_block) and \
				(parsed_block["timestamp"] is not None) and \
				(options.STARTBLOCKDATE >= parsed_block["timestamp"])
			):
				options.STARTBLOCKNUM = parsed_block["block_height"]
				options.STARTBLOCKDATE = None

			# STARTBLOCKHASH to STARTBLOCKNUM
			if (
				("block_hash" in parsed_block) and \
				(parsed_block["block_hash"] is not None) and \
				(options.STARTBLOCKHASH == parsed_block["block_hash"])
			):
				options.STARTBLOCKNUM = parsed_block["block_height"]
				options.STARTBLOCKHASH = None

		# if ENDBLOCKNUM has not yet been updated then update it if possible
		if options.ENDBLOCKNUM is None:

			# ENDBLOCKDATE to ENDBLOCKNUM
			if (
				("timestamp" in parsed_block) and \
				(parsed_block["timestamp"] is not None) and \
				(options.ENDBLOCKDATE >= parsed_block["timestamp"])
			):
				options.ENDBLOCKNUM = parsed_block["block_height"]
				options.ENDBLOCKDATE = None

			# ENDBLOCKHASH to ENDBLOCKNUM
			if (
				("block_hash" in parsed_block)
				(parsed_block["block_hash"] is not None) and \
				(options.ENDBLOCKHASH == parsed_block["block_hash"])
			):
				options.ENDBLOCKNUM = parsed_block["block_height"]
				options.ENDBLOCKHASH = None

	# STARTBLOCKNUM + LIMIT - 1 to ENDBLOCKNUM
	# - 1 is because the first block is inclusive
	if (
		(options.STARTBLOCKNUM) and \
		(options.LIMIT)
	):
		options.ENDBLOCKNUM = options.STARTBLOCKNUM + options.LIMIT - 1
		options.LIMIT = None

	# die if unsanitary. this may not have been possible until now
	sanitize_block_range(options)

	return options

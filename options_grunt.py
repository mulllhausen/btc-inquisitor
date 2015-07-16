"""module to process the user-specified btc-inquisitor options"""

# TODO - fix for the case where options.STARTBLOCKNUM is 0

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
	that will guide the program behaviour.
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
			("short_arg" not in option) and
			("long_arg" not in option)
		):
			raise ValueError(
				"all options must have at least a short arg or a long arg"
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

	# TODO capitalize keys and string values in the options object

	return options

def explain(options):
	"""
	convert the options to a human readable text string. this is mainly useful
	so that the user can check that their date-formatting was interpreted
	correctly.
	"""
	if options.OUTPUT_TYPE is not None:
		s = "extracting "

		if options.validate is not None:
			s += "and validating "

		s += "all "

		output_type = options.OUTPUT_TYPE.upper()
		if output_type == "BLOCKS":
			s += "blocks"

		elif output_type == "TXS":
			s += "transactions"

		elif output_type == "BALANCES":
			s += "balances"

	elif options.validate is not None:
		s = "validating all blocks"

	s += " between "

	if options.STARTBLOCKDATE is not None:
		s += "date %s" % datetime.datetime.fromtimestamp(options.
		STARTBLOCKDATE).strftime("%Y-%m-%d %H:%M:%S")

	elif options.STARTBLOCKHASH is not None:
		s += "hash %s" % options.STARTBLOCKHASH 

	elif options.STARTBLOCKNUM is not None:
		s += "block %s" % options.STARTBLOCKNUM 

	# default start block is the first block
	else:
		s += "block 0"

	s += " and "

	if options.ENDBLOCKDATE is not None:
		s += "date %s" % datetime.datetime.fromtimestamp(options.
		ENDBLOCKDATE).strftime("%Y-%m-%d %H:%M:%S")

	elif options.ENDBLOCKHASH is not None:
		s += "hash %s" % options.ENDBLOCKHASH 

	elif options.ENDBLOCKNUM is not None:
		if options.ENDBLOCKNUM == "end":
			s += "the final block"
		else:
			s += "block %s" % options.ENDBLOCKNUM 

	s += " (inclusive)"

	explain_aux = [] # init

	if options.ADDRESSES is not None:
		if isinstance(options.ADDRESSES, list):
			addresses = lang_grunt.list2human_str(options.ADDRESSES, "or")
		elif isinstance(options.ADDRESSES, str):
			addresses = options.ADDRESSES

		explain_aux.append("with addresses %s" % addresses)

	if options.TXHASHES is not None:
		if isinstance(options.TXHASHES, list):
			txhashes = lang_grunt.list2human_str(options.TXHASHES, "or")
		elif isinstance(options.TXHASHES, str):
			txhashes = options.TXHASHES

		explain_aux.append("with transaction hashes %s" % txhashes)

	if options.BLOCKHASHES is not None:
		if isinstance(options.BLOCKHASHES, list):
			blockhashes = lang_grunt.list2human_str(options.BLOCKHASHES, "or")
		elif isinstance(options.BLOCKHASHES, str):
			blockhashes = options.BLOCKHASHES

		explain_aux.append("with block hashes %s" % blockhashes)

	if explain_aux:
		s += " or ".join(explain_aux)

	# ORPHAN_OPTIONS is never None - it has a default value
	orphan_options = options.ORPHAN_OPTIONS.upper() # capitalize

	if (
		(options.validate is not None) or
		(output_type == "BLOCKS")
	):
		are = "are"
	else:
		are = "occur in"

	if orphan_options == "NONE":
		s += ", that %s non-orphan blocks" % are
	if orphan_options == "ALLOW":
		pass
	if orphan_options == "ONLY":
		s += ", that %s orphan blocks" % are
		
	if options.OUTPUT_TYPE is None:
		s += "."
	else:
		s += ", and outputing in %s format." % options.FORMAT.lower()

	return s

def sanitize_options_or_die(options):
	"""
	sanitize and update the options dict.

	note that at this point, anything that has not been specified by the user as
	a cli argument will have a value of None in the options dict - keep it this
	way, as it is easier to check for None than the check for length == 0, or
	value == 0.
	"""

	global n
	n = os.linesep if options.progress else ""

	# create a new options element to house txin hashes that are to be hunted
	# for and returned as part of the result set. this is necessary because txin
	# addresses can only be derived by looking at the address of the previous
	# txout they point to (the txin address is the same as the txout address it
	# references). this option will only get updated if the user directly
	# specifies addresses, but we always need to initialise it to empty
	# regardless. the format is {hash: [index, ..., index]}. this is the only
	# option that is not initialized to None when it is empty.
	options.TXINHASHES = {}

	if options.ADDRESSES is not None:
		if options.ADDRESSES[-1] == ",":
			raise ValueError(
				"trailing comma found in the ADDRESSES input argument. please"
				" ensure there are no spaces in the ADDRESSES input argument."
				# TODO - or are spaces allowed if quotations are used?
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
				raise ValueError(
					"all supplied addresses must be of the same currency:%s%s"
					% (os.linesep, pprint.pformat(currency_types, width = -1))
				)
		# convert csv string to list
		options.ADDRESSES = options.ADDRESSES.split(",")

	if options.TXHASHES is not None:
		if options.TXHASHES[-1] == ",":
			raise ValueError(
				"trailing comma found in the TXHASHES input argument. please"
				" ensure there are no spaces in the TXHASHES input argument."
			)
		for tx_hash in options.TXHASHES.split(","):
			if not btc_grunt.valid_hash(tx_hash):
				raise ValueError(
					"Supplied transaction hash %s is not in the correct format."
					% tx_hash
				)
		# convert csv string to list
		options.TXHASHES = [
			btc_grunt.hex2bin(txhash) for txhash in options.TXHASHES.split(",")
		]

	if options.BLOCKHASHES is not None:
		if options.BLOCKHASHES[-1] == ",":
			raise ValueError(
				"trailing comma found in the BLOCKHASHES input argument. please"
				" ensure there are no spaces in the BLOCKHASHES input argument."
			)
		for block_hash in options.BLOCKHASHES.split(","):
			if not btc_grunt.valid_hash(block_hash):
				raise ValueError(
					"supplied block hash %s is not n the correct format."
					% block_hash
				)
		# convert csv string to list
		options.BLOCKHASHES = [
			btc_grunt.hex2bin(blockhash) for blockhash in
			options.BLOCKHASHES.split(",")
		]

	# convert limit range to blocknum range if possible. this will also be done
	# again later if hash ranges are converted to block height ranges
	options = convert_range_options(options)

	if options.STARTBLOCKDATE is not None:
		t = parser.parse(options.STARTBLOCKDATE) # to datetime object
		options.STARTBLOCKDATE = time.mktime(t.timetuple()) # to unixtime

	if options.STARTBLOCKHASH is not None:
		options.STARTBLOCKHASH = btc_grunt.hex2bin(options.STARTBLOCKHASH)

	if options.ENDBLOCKDATE is not None:
		t = parser.parse(options.ENDBLOCKDATE) # to datetime object
		options.ENDBLOCKDATE = time.mktime(t.timetuple()) # to unixtime

	if options.ENDBLOCKHASH is not None:
		options.ENDBLOCKHASH = btc_grunt.hex2bin(options.ENDBLOCKHASH)

	num_start_options = 0
	if options.STARTBLOCKDATE is not None:
		num_start_options += 1
	if options.STARTBLOCKHASH is not None:
		num_start_options += 1
	if options.STARTBLOCKNUM is not None:
		num_start_options += 1
	if num_start_options > 1:
		raise ValueError(
			"only one of options --start-blockdate, --start-blockhash and"
			" --start-blocknum can be specified."
		)
	num_end_options = 0
	if options.ENDBLOCKDATE is not None:
		num_end_options += 1
	if options.ENDBLOCKHASH is not None:
		num_end_options += 1
	if options.ENDBLOCKNUM is not None:
		num_end_options += 1
	if num_end_options > 1:
		raise ValueError(
			"only one of options --end-blockdate, --end-blockhash and"
			" --start-blocknum can be specified."
		)
	if (
		(options.LIMIT) and
		(num_end_options > 0)
	):
		raise SyntaxError(
			"if option --limit (-L) is specified then neither option"
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
	if (
		(options.FORMAT is None) or
		(options.FORMAT not in permitted_output_formats)
	):
		raise ValueError(
			"option --output-format (-o) must be either %s."
			% lang_grunt.list2human_str(permitted_output_formats)
		)

	# ORPHAN_OPTIONS is never None - it has a default value
	options.ORPHAN_OPTIONS = options.ORPHAN_OPTIONS.upper() # capitalize
	permitted_orphan_options = [
		"NONE",
		"ALLOW",
		"ONLY"
	]
	if (options.ORPHAN_OPTIONS not in permitted_orphan_options):
		raise ValueError(
			"option --orphan-options must be either %s."
			% lang_grunt.list2human_str(permitted_orphan_options)
		)

	if (
		(options.OUTPUT_TYPE is None) and
		(options.validate is None)
	):
		raise ValueError(
			"either option --output-type (-t) or option --validate (-v) must"
			" be specified."
		)

	if options.OUTPUT_TYPE is not None:
		options.OUTPUT_TYPE = options.OUTPUT_TYPE.upper() # capitalize
		permitted_output_types = [
			"BLOCKS",
			"TXS",
			"BALANCES"
		]
		if options.OUTPUT_TYPE not in permitted_output_types:
			raise ValueError(
				"option --output-types (-t) must be either %s."
				% lang_grunt.list2human_str(permitted_output_types)
			)

		if options.OUTPUT_TYPE == "BALANCES":
			if options.FORMAT == "BINARY":
				raise ValueError(
					"Option --output-type (-t) cannot be set to BALANCES while"
					" option --output-format (-o) is set to BINARY."
				)
			if options.ADDRESSES is None:
				raise ValueError(
					"when option --output-type (-t) is set to BALANCES then"
					" ADDRESSES must also be specified via option --addresses"
					" (-a)."
				)

	return options

def sanitize_block_range(options):
	if (
		(options.STARTBLOCKNUM is not None) and
		(options.ENDBLOCKNUM is not None) and
		(options.ENDBLOCKNUM != "end") and
		(options.ENDBLOCKNUM < options.STARTBLOCKNUM)
	):
		raise ValueError(
			"your specified end block comes before your specified start block"
			" in the blockchain."
		)

def convert_range_options(options, parsed_block = None):
	"""
	pb = requires parsed block
	convert:
	- STARTBLOCKDATE to STARTBLOCKNUM (pb)
	- STARTBLOCKHASH to STARTBLOCKNUM (pb)
	- ENDBLOCKDATE to ENDBLOCKNUM (pb)
	- ENDBLOCKHASH to ENDBLOCKNUM (pb)
	- STARTBLOCKNUM + LIMIT to ENDBLOCKNUM (no pb)
	"""
	if (
		(options.STARTBLOCKNUM is None) and
		(options.STARTBLOCKDATE is None) and
		(options.STARTBLOCKHASH is None)
	):
		options.STARTBLOCKNUM = 0

	# if there is nothing to update then exit here
	if (
		(
			(options.STARTBLOCKNUM is not None) and
			(options.ENDBLOCKNUM is not None)
		) or (
			(options.STARTBLOCKDATE is None) and
			(options.STARTBLOCKHASH is None) and
			(options.ENDBLOCKDATE is None) and
			(options.ENDBLOCKHASH is None) and
			(options.LIMIT is None)
		)
	):
		return options

	if (
		(parsed_block is not None) and
		("block_height" in parsed_block) and
		(parsed_block["block_height"] is not None)
	):
		# if STARTBLOCKNUM has not yet been updated then update it if possible
		if options.STARTBLOCKNUM is None:

			# STARTBLOCKDATE to STARTBLOCKNUM
			if (
				(options.STARTBLOCKDATE is not None) and
				("timestamp" in parsed_block) and
				(parsed_block["timestamp"] is not None) and
				(options.STARTBLOCKDATE >= parsed_block["timestamp"])
			):
				options.STARTBLOCKNUM = parsed_block["block_height"]
				options.STARTBLOCKDATE = None

			# STARTBLOCKHASH to STARTBLOCKNUM
			if (
				(options.STARTBLOCKHASH is not None) and
				("block_hash" in parsed_block) and
				(parsed_block["block_hash"] is not None) and
				(options.STARTBLOCKHASH == parsed_block["block_hash"])
			):
				options.STARTBLOCKNUM = parsed_block["block_height"]
				options.STARTBLOCKHASH = None

		# if ENDBLOCKNUM has not yet been updated then update it if possible
		if options.ENDBLOCKNUM is None:

			# ENDBLOCKDATE to ENDBLOCKNUM
			if (
				(options.ENDBLOCKDATE is not None) and
				("timestamp" in parsed_block) and
				(parsed_block["timestamp"] is not None) and
				(options.ENDBLOCKDATE >= parsed_block["timestamp"])
			):
				options.ENDBLOCKNUM = parsed_block["block_height"]
				options.ENDBLOCKDATE = None

			# ENDBLOCKHASH to ENDBLOCKNUM
			if (
				(options.ENDBLOCKHASH is not None) and
				("block_hash" in parsed_block)
				(parsed_block["block_hash"] is not None) and
				(options.ENDBLOCKHASH == parsed_block["block_hash"])
			):
				options.ENDBLOCKNUM = parsed_block["block_height"]
				options.ENDBLOCKHASH = None

	# STARTBLOCKNUM + LIMIT - 1 to ENDBLOCKNUM
	# - 1 is because the first block is inclusive
	if (
		(options.STARTBLOCKNUM is not None) and
		(options.LIMIT is not None)
	):
		options.ENDBLOCKNUM = options.STARTBLOCKNUM + options.LIMIT - 1
		options.LIMIT = None

	# die if unsanitary. this may not have been possible until now
	sanitize_block_range(options)

	return options

def potentially_large_result_set(
	max_result_set_size, options, converted_range = False
):
	"""check if the block range is large or currently unknowable"""
	if not converted_range:
		raise ValueError(
			"block-ranges that the user has specified by hash values or limits"
			" must be converted into block-number ranges (if possible) before"
			" running this function, to avoid duplicating this functionality."
		)

	# if the final block number is not currently known then the range could be
	# huge
	if options.ENDBLOCKNUM is None:
		return True

	# even if we don't know the start block in the range, if the end block is
	# lower than the range size then the result set cannot be too large
	elif (options.ENDBLOCKNUM < max_result_size):
		return False

	# if we know the range and it is larger than the allowed max size...
	if (
		(options.STARTBLOCKNUM is not None) and
		((options.ENDBLOCKNUM - options.STARTBLOCKNUM) > max_result_set_size)
	):
		return True

	return False

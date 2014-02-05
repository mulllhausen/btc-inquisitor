#!/usr/bin/env python2.7
# parse the input arguments into variables

import readme2help_menu

from optparse import OptionParser
import os, sys, btc_grunt, progress_meter, json
sys.exit()

usage = "Usage: %prog [OPTIONS]"
arg_parser = OptionParser(usage = usage)
arg_parser.add_option("-a", "--addresses", action = "store", dest = "ADDRESSES", help = "Specify the ADDRESSES for which data is to be extracted from the blockchain files. ADDRESSES is a comma-seperated list and all ADDRESSES must be from the same cryptocurrency.")
arg_parser.add_option("-b", "--get-balance", action = "store_true", help = "Output the balance for each of the specified ADDRESSES. Note that if an incomplete block range is specified then the balance will only be correct based on that range.")
arg_parser.add_option("--block-hashes", action = "store", dest = "BLOCKHASHES", help = "Specify the blocks to extract from the blockchain by BLOCKHASHES (a comma-seperated list).")
arg_parser.add_option("-d", "--block-dir", action = "store", dest = "BLOCKCHAINDIR", help = "Specify the directory where the blockchain files can be found. Defaults to  ~/.bitcoin/blocks/ and looks for blockchain files named like blk[0-9]*.dat. If no valid blockchain files are found then an error is returned. So far this program has only been tested against the block files downloaded by bitcoind.")
arg_parser.add_option("--dont-validate-merkle-trees", action = "store_true", help = "Turning this option on prevents the program from checking that the transaction hashes within blocks containing the specified ADDRESSES form a merkle tree whose root is correctly included in the blockhash. In other words, turning this option on prevents the program from checking whether the transactions for the specified ADDRESSES are legitimate or not. While this option will result in a significant performance increase if the specified ADDRESSES have a lot of transactions, it is an extremely bad idea to rely on transaction data extracted in this manner. This option is only included so that the user can extract transaction data as it appears in the blockchain files for subsequent analysis and validation if desired.")
arg_parser.add_option("--end-blocknum", action = "store", dest = "ENDBLOCKNUM", help = "Specify the block to end parsing at (inclusive). When ENDBLOCKNUM is a positive integer then it signifies the number of blocks from the start, with 0 being the genesis block. When ENDBLOCKNUM is a negative integer then it signifies the number of blocks from the end, with -1 being the latest block available. When this option is left unspecified then it defaults to -1. This option cannot be specified in conjunction with option --end-blockhash.")
arg_parser.add_option("--end-blockhash", action = "store", dest = "ENDBLOCKHASH", help = "Specify the block to end parsing data at (inclusive) by its hash string. The program greps the blockchain files to locate this block. This option cannot be specified in conjunction with option --end-blocknum.")
arg_parser.add_option("-f", "--get-full-blocks", action = "store_true", help = "Output all block data for blocks containing the specified ADDRESSES.")
arg_parser.add_option("-L", "--limit", action = "store", dest = "LIMIT", help = "Specify the number of blocks to parse beginning at whichever is specified out of STARTBLOCKNUM, STARTBLOCKHASH or the default genesis block.")
arg_parser.add_option("-o", "--output-format", action = "store", dest = "FORMAT", default = "JSON", help = "Specify the output data format. FORMAT can be: JSON (associative array), BINARY. JSON is the default and BINARY is only permitted when requesting full transactions or full blocks.")
arg_parser.add_option("-p", "--progress", action = "store_true", help = "Show the progress meter as a percentage. If a range of blocks is specified with --start-blocknum and --end-blocknum then, for the purposes of displaying the progress meter, this range is assumed to actually exist. The progress meter will display 0% until the parser reaches the specified start block. And if it turns out that this range actually does not exist (eg if --end-blocknum is set to 1,000,000 before this block is mined in 2029) then the progress meter will never reach 100%. If no integer range of blocks is specified (eg if the end block is specified by its hash, or not at all) then the progress meter shows the number of bytes parsed, according to the file sizes reported by the operating system.")
arg_parser.add_option("--single-record", action = "store_true", help = "Stop searching once the first valid record has been found. This option is only valid in conjunction with --block-hashes or --tx-hashes. This option is inactive by default.")
arg_parser.add_option("--start-blocknum", action = "store", dest = "STARTBLOCKNUM", help = "Specify the block to start parsing from (inclusive). When STARTBLOCKNUM is a positive integer then it signifies the number of blocks from the start, with 0 being the genesis block. When STARTBLOCKNUM is a negative integer then it signifies the number of blocks from the end, with -1 being the latest block available. When this option is left unspecified then it defaults to 0. This option cannot be specified in conjunction with option --start-blockhash.")
arg_parser.add_option("--start-blockhash", action = "store", dest = "STARTBLOCKHASH", help = "Specify the block to start parsing data from (inclusive) by its hash string. The program greps the blockchain files to locate this block. This option cannot be specified in conjunction with option --start-blocknum.")
arg_parser.add_option("-t", "--get-transactions", action = "store_true", help = "Output all transaction data for the specified ADDRESSES.")
arg_parser.add_option("--tx-hashes", action = "store", dest = "TXHASHES", help = "Specify the transactions to extract from the blockchain by TXHASHES (a comma-seperated list).")
arg_parser.add_option("-w", "--suppress-warnings", action = "store_true", help = "Suppress warnings. This option is disabled by default.")

(options, _) = arg_parser.parse_args()

# sanitize the options and their values

if options.ADDRESSES:
	currency_types = {}
	for address in options.ADDRESSES.split(","):
		currency_types[address] = btc_grunt.get_address_type(address)
		try:
			if first_currency != currency_types[address]:
				sys.exit("error: all supplied addresses must be of the same currency")
		except: # first_currency is not yet initialised
			first_currency = currency_types[address]

if options.TXHASHES:
	for tx_hash in options.TXHASHES.split(","):
		if not btc_grunt.valid_hash(tx_hash):
			sys.exit("error: supplied transaction hash %s is not of a valid format" % tx_hash)

if options.BLOCKHASHES:
	for block_hash in options.BLOCKHASHES.split(","):
		if not btc_grunt.valid_hash(block_hash):
			sys.exit("error: supplied block hash %s is not of a valid format" % block_hash)

if not options.dont_validate_merkle_trees:
	sys.exit("option --dont-validate-merkle-trees is currently mandatory as merkle tree validation is currently a work in progress")

if options.ENDBLOCKNUM and options.ENDBLOCKHASH:
	sys.exit("if option --end-blocknum is specified then option --end-blockhash cannot also be specified")

if not isinstance(options.ENDBLOCKNUM, (int, long)):
	sys.exit("option --end-blocknum only accepts integer values. %s is not an integer" % options.ENDBLOCKNUM)

if not isinstance(options.STARTBLOCKNUM, (int, long)):
	sys.exit("option --start-blocknum only accepts integer values. %s is not an integer" % options.STARTBLOCKNUM)

if options.STARTBLOCKNUM and options.STARTBLOCKHASH:
	sys.exit("if option --start-blocknum is specified then option --start-blockhash cannot also be specified")

if options.LIMIT and (options.end_blocknum or options.end_blockhash):
	sys.exit("if option --limit (-L) is specified then neither option --end-blockhash nor option --end-blocknum can be specified")

if not isinstance(options.LIMIT, (int, long)):
	sys.exit("option --limit (-L) only accepts integer values. %s is not an integer" % options.LIMIT)

if options.FORMAT not in ["JSON", "BINARY"]:
	sys.exit("option --output-format (-o) must be either JSON or BINARY")

if options.get_balance:
	if not options.ADDRESSES:
		sys.exit("if option --get-balance (-b) is selected then option --addresses (-a) is mandatory")
	if options.get_full_blocks:
		sys.exit("if option --get-balance (-b) is selected then option --get-full-blocks (-f) cannot also be selected")
	if options.get_transactions:
		sys.exit("if option --get-balance (-b) is selected then option --get-transactions (-t) cannot also be selected")
	if options.FORMAT == "BINARY":
		sys.exit("option --get-balance (-b) cannot be selected while option --output-format (-o) is set to BINARY")
	sys.exit("unimplemented")

if options.get_full_blocks:
	if options.get_balance:
		sys.exit("if option --get-full-blocks (-f) is selected then option --get-balance (-b) cannot also be selected")
	if options.get_transactions:
		sys.exit("if option --get-full-blocks (-f) is selected then option --get-transactions (-t) cannot also be selected")
	sys.exit("unimplemented")

if options.get_transactions:
	if options.get_full_blocks:
		sys.exit("if option --get-transactions (-t) is selected then option --get-full-blocks (-f) cannot also be selected")
	if options.get_balance:
		sys.exit("if option --get-transactions (-t) is selected then option --get-balance (-b) cannot also be selected")
	sys.exit("unimplemented")

# now extract the data related to the specified addresses/transactions/blocks. 

# - first get the full raw (non-orphan) blocks which contain either the specified addresses,
#   transaction hashes, blockhashes, or are within the specified range. Unless suppressed, a 
#   warning is given if the range is larger than 10 blocks.

# - then eliminate any blocks with merkle trees which do not hash correctly

# ** print data here and exit here when --get-full-blocks (-f) is selected **

# - then extract the transactions which contain the specified addresses or specified
#   transaction hashes.

# ** print data here and exit here when --get-transactions (-t) is selected **

# - then extract the balance for each of the specified addresses

# ** print data here and exit here when --get-balance (-b) is selected **


binary_blocks = btc_grunt.extract_blocks(options)
binary_blocks = [binary_block for binary_block in binary_blocks if btc_grunt.validate_block_hash(binary_block)]

if not options.dont_validate_merkle_trees:
	binary_blocks = [binary_block for binary_block in binary_blocks if btc_grunt.validate_merkle_tree(binary_block)]

if options.get_full_blocks:
	if options.FORMAT == "JSON":
		parsed_blocks = [btc_grunt.parse_block(binary_block) for binary_block in binary_blocks]
		json.dumps(parsed_blocks)
	elif options.FORMAT == "BINARY":
		sys.exit("unimplemented")
	sys.exit(0)

binary_txs = btc_grunt.extract_txs(binary_blocks, addresses)

if options.get_transactions:
	txs = extract_raw_txs(addresses)

if options.get_balance:
	txs = extract_raw_txs(addresses)

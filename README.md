btc-inquisitor
==========

SYNOPSIS
----------

    ./btc-inquisitor [OPTIONS]

DESCRIPTION
----------

Command line tool for interrogating cryptocurrency blockchains. File unit_tests.sh contains lots of examples of how to use this tool.

WARNINGS
----------

This project is a work in progrss - it is not yet fit for consumption.

OPTIONS
----------

    -a ADDRESSES, --addresses=ADDRESSES

Specify the ADDRESSES for which data is to be extracted from the blockchain files. ADDRESSES is a comma-seperated list and all ADDRESSES must be from the same cryptocurrency.

Note that ADDRESSES, TXHASHES and BLOCKHASHES are completely independent and are not ANDed together to filter results. For example, if ADDRESSES are specified which do not exist within the specified TXHASHES then both the ADDRESSES and TXHASHES will be included in the output so long as this data can be located in the blockchain.

If no ADDRESSES, TXHASHES or BLOCKHASHES are specified then all data within the specified range will be returned.



    --block-hashes=BLOCKHASHES

Specify the blocks to extract from the blockchain by BLOCKHASHES (a comma-seperated list).

Note that ADDRESSES, TXHASHES and BLOCKHASHES are completely independent and are not ANDed together to filter results. For example, if ADDRESSES are specified which do not exist within the specified TXHASHES then both the ADDRESSES and TXHASHES will be included in the output so long as this data can be located in the blockchain.

If no ADDRESSES, TXHASHES or BLOCKHASHES are specified then all data within the specified range will be returned.



    -d BLOCKCHAINDIR, --block-dir=BLOCKCHAINDIR

Specify the directory where the blockchain files can be found. Defaults to ~/.bitcoin/blocks/ and looks for blockchain files named like blk*[0-9]*.dat. If no blockchain files are found then an error is returned. So far this program has only been tested against the block files downloaded by bitcoind.



    --end-blockdate=ENDBLOCKHASH

Specify the block to end parsing data at (inclusive) by its hash string.

This option cannot be specified in conjunction with option --end-blockhash or option --end-blocknum.



    --end-blockhash=ENDBLOCKHASH

Specify the block to end parsing data at (inclusive) by its hash string.

This option cannot be specified in conjunction with option --end-blockdate or option --end-blocknum.



    --end-blocknum=ENDBLOCKNUM

Specify the block to end parsing at (inclusive). When ENDBLOCKNUM is a positive integer then it signifies the number of blocks from the start, with 0 being the genesis block. When ENDBLOCKNUM is a negative integer then it signifies the number of blocks from the end, with -1 being the latest block available. When this option is left unspecified then it defaults to -1.

This option cannot be specified in conjunction with option --end-blockdate or option --end-blockhash.



    -h, --help

Display the help and exit.



    -L LIMIT, --limit=LIMIT

Specify the number of blocks to parse beginning at whichever is specified out of STARTBLOCKNUM, STARTBLOCKHASH or the default genesis block.



    -m MONEY_RANGE, --money-range=MONEY_RANGE

Specify the money range to parse in satoshis. Format: MINMONEY-MAXMONEY. For example, setting this argument to 123-456 would output only transactions which sent between 123 satoshis and 456 satoshis (inclusive). If you want to parse all money amounts below MAXMONEY then simply omit MINMONEY like so: -MAXMONEY. If you want to parse all money amounts above MINMONEY then simply omit MAXMONEY like so: MINMONEY-.



    -o FORMAT, --output-format=FORMAT

Specify the output data format. FORMAT can be: SINGLE-LINE-JSON (associative array), MULTILINE-JSON (associative array), MULTILINE-XML, SINGLE-LINE-XML, BINARY. MULTILINE-JSON is the default and BINARY is only permitted when requesting full transactions or full blocks.



    --orphan-options=ORPHAN_OPTIONS

Change orphan blocks settings in the result set. Allowable options are ['NONE'|'ALLOW'|'ONLY']. 'NONE' removes all orphan blocks from the result set, 'ALLOW' permits orphan blocks in the result set, and 'ONLY' filters out any non-orphan blocks from the result set.



    -p, --progress

Show the progress meter as a percentage.

If a range of blocks is specified with --start-blocknum and --end-blocknum then, for the purposes of displaying the progress meter, this range is assumed to actually exist. The progress meter will display 0% until the parser reaches the specified start block. And if it turns out that this range actually does not exist (eg if --end-blocknum is set to 1,000,000 before this block is mined in 2029) then the progress meter will never reach 100%.

If no integer range of blocks is specified (eg if the end block is specified by its hash, or not at all) then the progress meter shows the number of bytes parsed, according to the file sizes reported by the operating system.



    -1, --single-record

Stop searching once the first matching record has been found. This option can only be used with --block-hashes or --tx-hashes. This option is inactive by default.



    --start-blockdate=STARTBLOCKDATE

Specify the block to start parsing data from (inclusive) by its date string.

This option cannot be specified in conjunction with option --start-blockhash or option --start-blocknum.



    --start-blockhash=STARTBLOCKHASH

Specify the block to start parsing data from (inclusive) by its hash string.

This option cannot be specified in conjunction with option --start-blocknum.



    --start-blocknum=STARTBLOCKNUM

Specify the block to start parsing from (inclusive). When STARTBLOCKNUM is a positive integer then it signifies the number of blocks from the start, with 0 being the genesis block. When STARTBLOCKNUM is a negative integer then it signifies the number of blocks from the end, with -1 being the latest block available. When this option is left unspecified then it defaults to 0.

This option cannot be specified in conjunction with option --start-blockdate or option --start-blockhash.



    -t OUTPUT_TYPE, --output-type=OUTPUT_TYPE

Specify the type of data to return. Allowable types are ['BLOCKS'|'TXS'|'BALANCES']. The default is 'BLOCKS'.

If 'BLOCKS' is chosen then full blocks that match the other specified options are returned. For example, blocks which contain the specified ADDRESSES, TXHASHES or BLOCKHASHES, blocks that are orphans, blocks that fall within a given range, etc. If no other options are specified then all blocks within the specified range will be returned.

If 'TXS' is chosen then transactions that match the other specified options are returned. For example, transactions which come from blocks with hashes specified in BLOCKHASHES, or transactions that contain the specified ADDRESSES or TXHASHES, transactions from blocks that are orphans, transactions from blocks that fall within a given range, etc. If no other options are specified then all transactions (including coinbase transactions) that fall within the specified range will be returned.

If 'BALANCES' is chosen then balances for addresses that match the other specified options are returned. For example, balances for addresses which exist in blocks with hashes specified in BLOCKHASHES, or balances for addresses which exist in transactions that contain the specified TXHASHES, or balances simply specified by ADDRESSES, balances from addresses that exist in blocks that are orphans (obviously these will be inaccurate), balances from addresses that exist in blocks that fall within a given range, etc. If no other options are specified then balances for all addresses that fall within the specified range will be returned.



    --tx-hashes=TXHASHES

Specify the transactions to extract from the blockchain by TXHASHES (a comma-seperated list of hex characters).

Note that ADDRESSES, TXHASHES and BLOCKHASHES are completely independent and are not ANDed together to filter results. For example, if ADDRESSES are specified which do not exist within the specified TXHASHES then both the ADDRESSES and TXHASHES will be included in the output so long as this data can be located in the blockchain.

If no ADDRESSES, TXHASHES or BLOCKHASHES are specified then all data within the specified range will be returned.



    -v, --validate-blocks

Validate all blocks within the given range. It is essential to run this option once every time the blockchain files are updated by the bitcoind client. If this option finds any fatal errors on the main blockchain (i.e. non-orphans) then the program will notify the user and exit. Notifications of bad data found in the blockfiles are suppressed by default, however these can be viewed by turning on the --explain (-x) option.



    -w, --suppress-warnings

Suppress warnings. This option is disabled by default.



    -x, --explain

Explain what is going on.



NOTES
----------

Note that when the program is first required to display or calculate block positions (eg if the full range of blockchain files is to be parsed, or if either end of a range of blocks is specified by number, and not by hash values) then the program gathers a list of block positions and stores them in file ~/.btc-inquisitor/block_positions.csv to speed up performance in future. This list should not be edited - doing so will produce erroneous results.

AUTHOR
----------

Peter Miller <petermiller1986 ~at~ gmail.com>

Copyright (C) 2014 by Free Software Foundation, Inc. (see LICENSE file in this project for details)


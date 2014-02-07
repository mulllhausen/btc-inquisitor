btc-inquisitor
==========

   btc-inquisitor [OPTIONS]

DESCRIPTION
----------

Command line tool to extract data from cryptocurrency blockchains.

WARNINGS
----------

This project is a work in progrss - it is not yet fit for consumption.

OPTIONS
----------

    -a ADDRESSES, --addresses=ADDRESSES

Specify the ADDRESSES for which data is to be extracted from the blockchain files. ADDRESSES is a comma-seperated list and all ADDRESSES must be from the same cryptocurrency.

-   -b, --get-balance

Output the balance for each of the specified ADDRESSES. Note that if an incomplete block range is specified then the balance will only be correct based on that range.

-   --block-hashes=BLOCKHASHES

Specify the blocks to extract from the blockchain by BLOCKHASHES (a comma-seperated list).

-   -d BLOCKCHAINDIR, --block-dir=BLOCKCHAINDIR

Specify the directory where the blockchain files can be found. Defaults to ~/.bitcoin/blocks/ and looks for blockchain files named like blk[0-9]*.dat. If no valid blockchain files are found then an error is returned. So far this program has only been tested against the block files downloaded by bitcoind.

-   --dont-validate-merkle-trees

Turning this option on prevents the program from checking that the transaction hashes within blocks containing the specified ADDRESSES form a merkle tree whose root is correctly included in the blockhash. In other words, turning this option on prevents the program from checking whether the transactions for the specified ADDRESSES are legitimate or not.

While this option will result in a significant performance increase if the specified ADDRESSES have a lot of transactions, it is an extremely bad idea to rely on transaction data extracted in this manner. This option is only included so that the user can extract transaction data as it appears in the blockchain files for subsequent analysis and validation if desired.

-   --end-blocknum=ENDBLOCKNUM

Specify the block to end parsing at (inclusive). When ENDBLOCKNUM is a positive integer then it signifies the number of blocks from the start, with 0 being the genesis block. When ENDBLOCKNUM is a negative integer then it signifies the number of blocks from the end, with -1 being the latest block available. When this option is left unspecified then it defaults to -1.

This option cannot be specified in conjunction with option --end-blockhash.

-   --end-blockhash=ENDBLOCKHASH

Specify the block to end parsing data at (inclusive) by its hash string. The program greps the blockchain files to locate this block.

This option cannot be specified in conjunction with option --end-blocknum.

-   -f, --get-full-blocks

Output all block data for blocks containing the specified ADDRESSES.

-   -h, --help

Display the help and exit.

-   -L LIMIT, --limit=LIMIT

Specify the number of blocks to parse beginning at whichever is specified out of STARTBLOCKNUM, STARTBLOCKHASH or the default genesis block.

-   -o FORMAT, --output-format=FORMAT

Specify the output data format. FORMAT can be: JSON (associative array), XML, BINARY. JSON is the default and BINARY is only permitted when requesting full transactions or full blocks.

-   -p, --progress

Show the progress meter as a percentage.

If a range of blocks is specified with --start-blocknum and --end-blocknum then, for the purposes of displaying the progress meter, this range is assumed to actually exist. The progress meter will display 0% until the parser reaches the specified start block. And if it turns out that this range actually does not exist (eg if --end-blocknum is set to 1,000,000 before this block is mined in 2029) then the progress meter will never reach 100%.

If no integer range of blocks is specified (eg if the end block is specified by its hash, or not at all) then the progress meter shows the number of bytes parsed, according to the file sizes reported by the operating system.

-   -1, --single-record

Stop searching once the first valid record has been found. This option is only valid in conjunction with --block-hashes or --tx-hashes. This option is inactive by default.

-   --start-blocknum=STARTBLOCKNUM

Specify the block to start parsing from (inclusive). When STARTBLOCKNUM is a positive integer then it signifies the number of blocks from the start, with 0 being the genesis block. When STARTBLOCKNUM is a negative integer then it signifies the number of blocks from the end, with -1 being the latest block available. When this option is left unspecified then it defaults to 0.

This option cannot be specified in conjunction with option --start-blockhash.

-   --start-blockhash=STARTBLOCKHASH

Specify the block to start parsing data from (inclusive) by its hash string. The program greps the blockchain files to locate this block.

This option cannot be specified in conjunction with option --start-blocknum.

-   -t, --get-transactions

Output all transaction data for the specified ADDRESSES.

-   --tx-hashes=TXHASHES

Specify the transactions to extract from the blockchain by TXHASHES (a comma-seperated list).

-   -w, --suppress-warnings

Suppress warnings. This option is disabled by default.

NOTES
----------

Note that when the program is first required to display or calculate block positions (eg if the full range of blockchain files is to be parsed, or if either end of a range of blocks is specified by number, and not by hash values) then the program gathers a list of block positions and stores them in file ~/.btc-inquisitor/block_positions to speed up performance in future. This list should not be edited - doing so will produce erroneous results.

AUTHOR
----------

Peter Miller <petermiller1986 ~at~ gmail.com>

Copyright (C) 2014 by Free Software Foundation, Inc. (see LICENSE file in this project for details)


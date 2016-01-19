#!/usr/bin/env python2.7

"""
this script bench-tests the following two scenarios:

1 - constructing a bitcoin block as a dict, then dropping it

2 - looping through all txouts in a block, then looping through all txins
(without saving any of them)

all tests averaged over 100 large blocks. all data fetched via rpc and assembled
using btc_grunt
"""
import cProfile
import btc_grunt

btc_grunt.connect_to_rpc()
required_txin_info = [
    "txin_hash",
    "txin_index",
    "txin_script",
    "txin_script_list",
    "txin_script_format",
    "txin_sig_pubkey_validation_status"
]
required_txout_info = [
    "txout_script",
    "txout_script_format",
    "txout_standard_script_pubkey",
    "txout_standard_script_address"
]

# start at a block that is bound to have lots of txs
original_block_height = 390000
num_blocks = 1

def scenario1():
    required_info = required_txin_info + required_txout_info
    for i in xrange(num_blocks):
        block_dict = {} # start again each block
        block_height = original_block_height + i
        block_rpc_dict = btc_grunt.get_block(block_height, "json")
        for (tx_num, txhash_hex) in enumerate(block_rpc_dict["tx"]):
            tx_bytes = btc_grunt.get_transaction(txhash_hex, "bytes")
            (parsed_tx, _) = btc_grunt.tx_bin2dict(
                tx_bytes, 0, required_info, tx_num, block_height, ["rpc"]
            )
            block_dict[txhash_hex] = parsed_tx

def scenario2():
    for i in xrange(num_blocks):
        block_height = original_block_height + i
        block_rpc_dict = btc_grunt.get_block(block_height, "json")

        # first loop through all txs and get txouts only
        for (tx_num, txhash_hex) in enumerate(block_rpc_dict["tx"]):

            # get the parsed tx - no need to save it
            tx_bytes = btc_grunt.get_transaction(txhash_hex, "bytes")
            (parsed_tx, _) = btc_grunt.tx_bin2dict(
                tx_bytes, 0, required_txout_info, tx_num, block_height, ["rpc"]
            )

        # then loop through all txs and get txins only
        for (tx_num, txhash_hex) in enumerate(block_rpc_dict["tx"]):

            # get the parsed tx - no need to save it
            tx_bytes = btc_grunt.get_transaction(txhash_hex, "bytes")
            (parsed_tx, _) = btc_grunt.tx_bin2dict(
                tx_bytes, 0, required_txin_info, tx_num, block_height, ["rpc"]
            )

print "start benching scenario 1"
pr1 = cProfile.Profile()
pr1.enable()
scenario1()
pr1.disable()
pr1.dump_stats("bench_memblock.log")
print "finished benching scenario 1"

print "start benching scenario 2"
pr2 = cProfile.Profile()
pr2.enable()
scenario2()
pr2.disable()
pr2.dump_stats("bench_rpcblock.log")
print "finished benching scenario 2"

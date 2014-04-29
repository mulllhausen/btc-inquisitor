#!/usr/bin/python

"""
generate a blockchain which contains orphans
it looks like this:

	  a ---------- height 0
	 / \
	/   \
   b --- c ------- height 1
  /     / \
 /     /   \
d --- e --- f ---- height 2
|     |     |
|     |     |
g --- h --- i ---- height 3
	 / \     \
	/   \     \
   j --- k --- l - height 4
   |
   |
   m ------------- height 5
   |
   |
   n ------------- height 6

blocks g, k and l are orphans of each respective branch from the main chain
"""

import btc_grunt
import time

time_a = int(time.time()) # now
block_a = {
	"format_version": 1,
	"previous_block_hash": btc_grunt.blank_hash,
	"merkle_root": None, # update afterwards
	"timestamp": time_a,
	"bits": 0x1d00ffff, # just use the same value as block 0 from bitcoin
	"nonce": 0, # TODO mine this value
	"tx": {
		0: {
			"lock_time": 0,
			"input": {
				0: {
					"version": 1,
					"hash": btc_grunt.blank_hash, # same as bitcoin coinbase
					"index": 0xffffffff, # same as bitcoin coinbase
					"script": "",
					"sequence_num": 0xffffffff,
				}
			},
			"output": {
				0: {
					"funds": 50 * btc_grunt.satoshis_per_btc,
					"script": ""
				}
			}
		}
	}
}
block_a_bytes = btc_grunt.block_dict2bin(block_a)
block_a_hash = btc_grunt.calculate_block_hash(btc_grunt.block_a_bytes)
encapsulated_block_a = btc_grunt.encapsulate_block(block_a_bytes)


print encapsulated_block_a + encapsulated_block_b + encapsulated_block_c \
encapsulated_block_d + encapsulated_block_e + encapsulated_block_f \
encapsulated_block_g + encapsulated_block_h + encapsulated_block_i \
encapsulated_block_j + encapsulated_block_k + encapsulated_block_l \
encapsulated_block_m + encapsulated_block_n

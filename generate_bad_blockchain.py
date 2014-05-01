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

blocks g, k and l are orphans of each respective branch from the main chain.

note that the only information really necessary for this bad blockchain is each
block's hash and previous hash.
"""

import btc_grunt
import copy

block_a = {
	"format_version": 1,
	"previous_block_hash": btc_grunt.blank_hash,
	"timestamp": 0,
	"bits": btc_grunt.int2bin(0x1d00ffff, 4), # same as bitcoin block 0
	"nonce": 0, # obviously incorrect
	"tx": {
		0: {
			"version": 1,
			"lock_time": 0,
			"input": {
				0: {
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
errors = btc_grunt.validate_block_elements_type_len(block_a)
if errors:
	btc_grunt.die(
		"block (a) status:\n  -%s"
		% "\n -".join(errors)
	)
block_a_bytes = btc_grunt.block_dict2bin(block_a)
# this block's hash becomes previous_block_hash in blocks b & c
block_a_hash = btc_grunt.calc_block_hash(block_a_bytes)
encapsulated_block_a = btc_grunt.encapsulate_block(block_a_bytes)

block_b = copy.deepcopy(block_a) # same as block a
block_b["previous_block_hash"] = block_a_hash # except for the previous hash
block_b_bytes = btc_grunt.block_dict2bin(block_b)
# this block's hash becomes previous_block_hash in block d
block_b_hash = btc_grunt.calc_block_hash(block_b_bytes)
encapsulated_block_b = btc_grunt.encapsulate_block(block_b_bytes)

block_c = copy.deepcopy(block_a) # same as block a
block_c["previous_block_hash"] = block_a_hash # except for the previous hash
block_c_bytes = btc_grunt.block_dict2bin(block_c)
# this block's hash becomes previous_block_hash in blocks e & f
block_c_hash = btc_grunt.calc_block_hash(block_c_bytes)
encapsulated_block_c = btc_grunt.encapsulate_block(block_c_bytes)

print btc_grunt.bin2hex(block_a_bytes)

#print encapsulated_block_a + encapsulated_block_b + encapsulated_block_c \
#encapsulated_block_d + encapsulated_block_e + encapsulated_block_f \
#encapsulated_block_g + encapsulated_block_h + encapsulated_block_i \
#encapsulated_block_j + encapsulated_block_k + encapsulated_block_l \
##encapsulated_block_m + encapsulated_block_n

#!/usr/bin/python

"""
run this script in linux like so:

./generate_bad_blockchain.py > /tmp/blk_bad00.dat

(all blockchain filenames must be of the btc_grunt.blockname_format format)

this will generate a blockchain which contains orphans and looks like this:

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

blocks g, k and l are terminating orphans of each respective branch from the
main chain.
"""

import btc_grunt
import copy

generic_block = {
	"format_version": 1,
	"previous_block_hash": btc_grunt.blank_hash,
	"timestamp": 0,
	#"bits": btc_grunt.int2bin(0x1d00ffff, 4), # highest allowed value
	"bits": btc_grunt.int2bin(0x1fffffff, 4), # out of range, but nice and fast
	"nonce": 0, # gets mined later
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
errors = btc_grunt.validate_block_elements_type_len(generic_block)
if errors:
	btc_grunt.die(
		"generic block status:\n  -%s"
		% "\n  -".join(errors)
	)

block_a = copy.deepcopy(generic_block)
(block_a["nonce"], block_a["timestamp"]) = btc_grunt.mine(block_a) # very slow
block_a_bytes = btc_grunt.block_dict2bin(block_a)
# this block's hash becomes previous_block_hash in blocks b & c
block_a_hash = btc_grunt.calculate_block_hash(block_a_bytes)
encapsulated_block_a = btc_grunt.encapsulate_block(block_a_bytes)

block_b = copy.deepcopy(generic_block)
block_b["previous_block_hash"] = block_a_hash # except for the previous hash
block_b_bytes = btc_grunt.block_dict2bin(block_b)
# this block's hash becomes previous_block_hash in block d
block_b_hash = btc_grunt.calculate_block_hash(block_b_bytes)
encapsulated_block_b = btc_grunt.encapsulate_block(block_b_bytes)

block_c = copy.deepcopy(generic_block)
block_c["previous_block_hash"] = block_a_hash # except for the previous hash
block_c_bytes = btc_grunt.block_dict2bin(block_c)
# this block's hash becomes previous_block_hash in blocks e & f
block_c_hash = btc_grunt.calculate_block_hash(block_c_bytes)
encapsulated_block_c = btc_grunt.encapsulate_block(block_c_bytes)

block_d = copy.deepcopy(generic_block)
block_d["previous_block_hash"] = block_b_hash # except for the previous hash
block_d_bytes = btc_grunt.block_dict2bin(block_d)
# this block's hash becomes previous_block_hash in block g
block_d_hash = btc_grunt.calculate_block_hash(block_d_bytes)
encapsulated_block_d = btc_grunt.encapsulate_block(block_d_bytes)

block_e = copy.deepcopy(generic_block)
block_e["previous_block_hash"] = block_c_hash # except for the previous hash
block_e_bytes = btc_grunt.block_dict2bin(block_e)
# this block's hash becomes previous_block_hash in block h
block_e_hash = btc_grunt.calculate_block_hash(block_e_bytes)
encapsulated_block_e = btc_grunt.encapsulate_block(block_e_bytes)

block_f = copy.deepcopy(generic_block)
block_f["previous_block_hash"] = block_c_hash # except for the previous hash
block_f_bytes = btc_grunt.block_dict2bin(block_f)
# this block's hash becomes previous_block_hash in block i
block_f_hash = btc_grunt.calculate_block_hash(block_f_bytes)
encapsulated_block_f = btc_grunt.encapsulate_block(block_f_bytes)

block_g = copy.deepcopy(generic_block)
block_g["previous_block_hash"] = block_d_hash # except for the previous hash
block_g_bytes = btc_grunt.block_dict2bin(block_g)
encapsulated_block_g = btc_grunt.encapsulate_block(block_g_bytes)

block_h = copy.deepcopy(generic_block)
block_h["previous_block_hash"] = block_e_hash # except for the previous hash
block_h_bytes = btc_grunt.block_dict2bin(block_h)
# this block's hash becomes previous_block_hash in blocks j & k
block_h_hash = btc_grunt.calculate_block_hash(block_g_bytes)
encapsulated_block_h = btc_grunt.encapsulate_block(block_g_bytes)

block_i = copy.deepcopy(generic_block)
block_i["previous_block_hash"] = block_f_hash # except for the previous hash
block_i_bytes = btc_grunt.block_dict2bin(block_i)
# this block's hash becomes previous_block_hash in block l
block_i_hash = btc_grunt.calculate_block_hash(block_i_bytes)
encapsulated_block_i = btc_grunt.encapsulate_block(block_i_bytes)

block_j = copy.deepcopy(generic_block)
block_j["previous_block_hash"] = block_h_hash # except for the previous hash
block_j_bytes = btc_grunt.block_dict2bin(block_j)
# this block's hash becomes previous_block_hash in block m
block_j_hash = btc_grunt.calculate_block_hash(block_j_bytes)
encapsulated_block_j = btc_grunt.encapsulate_block(block_j_bytes)

block_k = copy.deepcopy(generic_block)
block_k["previous_block_hash"] = block_h_hash # except for the previous hash
block_k_bytes = btc_grunt.block_dict2bin(block_k)
encapsulated_block_k = btc_grunt.encapsulate_block(block_k_bytes)

block_l = copy.deepcopy(generic_block)
block_l["previous_block_hash"] = block_i_hash # except for the previous hash
block_l_bytes = btc_grunt.block_dict2bin(block_l)
encapsulated_block_l = btc_grunt.encapsulate_block(block_l_bytes)

block_m = copy.deepcopy(generic_block)
block_m["previous_block_hash"] = block_j_hash # except for the previous hash
block_m_bytes = btc_grunt.block_dict2bin(block_m)
# this block's hash becomes previous_block_hash in block n
block_m_hash = btc_grunt.calculate_block_hash(block_m_bytes)
encapsulated_block_m = btc_grunt.encapsulate_block(block_m_bytes)

block_n = copy.deepcopy(generic_block)
block_n["previous_block_hash"] = block_m_hash # except for the previous hash
block_n_bytes = btc_grunt.block_dict2bin(block_n)
encapsulated_block_n = btc_grunt.encapsulate_block(block_n_bytes)

blockchain = encapsulated_block_a + encapsulated_block_b + \
encapsulated_block_c + encapsulated_block_d + encapsulated_block_e + \
encapsulated_block_f + encapsulated_block_g + encapsulated_block_h + \
encapsulated_block_i + encapsulated_block_j + encapsulated_block_k + \
encapsulated_block_l + encapsulated_block_m + encapsulated_block_n

#print btc_grunt.bin2hex(blockchain)
print blockchain

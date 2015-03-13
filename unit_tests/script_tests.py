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

hundred_bytes_hex =	"01020304050607080910111213141516171819202122232425262728" \
"2930313233343536373839404142434445464748495051525354555657585960616263646566" \
"67686970717273747576777879808182838485868788899091929394959697989900"

def chop_to_size(str, size):
	"""chop a string down to the specified number of characters"""
	return str if (len(str) < size) else ("%s..." % str[: size])

################################################################################
# unit tests for evaluating correct non-checksig scripts
################################################################################
human_scripts = {
	# pushdata0 min (1)
	0: "OP_PUSHDATA0(1) 01 OP_NOP OP_EQUAL",

	# pushdata0 max (75)
	1: "OP_PUSHDATA0(75) " + hundred_bytes_hex[: 75 * 2] + " OP_NOP OP_DUP",

	# pushdata1 min (76)
	2: "OP_PUSHDATA1(76) " + hundred_bytes_hex[: 76 * 2],

	# pushdata1 max (0xff)
	3: "OP_PUSHDATA1(255) " + (hundred_bytes_hex * 2) + \
	hundred_bytes_hex[: 55 * 2],

	# pushdata2 min (0x100)
	4: "OP_PUSHDATA2(256) " + (hundred_bytes_hex * 2) + \
	hundred_bytes_hex[: 56 * 2],

	# too long for a bitcoin script (either in total or pushdata is too long):

	# pushdata2 max (0xffff)
	#5: "OP_PUSHDATA2(65535) " + (hundred_bytes_hex * 655) + \
	#hundred_bytes_hex[: 35 * 2],

	# pushdata4 min (0x10000)
	#6: "OP_PUSHDATA4(65536) " + (hundred_bytes_hex * 655) + \
	#hundred_bytes_hex[: 36 * 2],

	# pushdata4 max (0xffffffff)
	#7: "OP_PUSHDATA4(4294967295) " + (hundred_bytes_hex * 42949672) + \
	#hundred_bytes_hex[: 95 * 2]
}
for (test_num, human_script) in human_scripts.items():
	if verbose:
		print """
========== test for correct non-checksig behaviour %s ==========
convert a human-readable script to bin and back: %s
""" % (test_num, chop_to_size(human_script, 200))

	bin_script_list = btc_grunt.human_script2bin_list(human_script)
	bin_script = btc_grunt.script_list2bin(bin_script_list)
	rebin_script_list = btc_grunt.script_bin2list(bin_script)
	if rebin_script_list is False:
		lang_grunt.die(
			"failed test %s - converting script %s to binary list" % (
				test_num, chop_to_size(human_script, 200)
			)
		)
	human_script2 = btc_grunt.script_list2human_str(rebin_script_list)
	if human_script2 == human_script:
		if verbose:
			print "pass"
	else:
		lang_grunt.die(
			"test %s failed for correct non-checksig behaviour" % (
				test_num, chop_to_size(human_script, 200)
			)
		)

################################################################################
# unit tests for evaluating incorrect non-checksig scripts
################################################################################
human_scripts = {
	# pushdata0 below min
	0: "OP_PUSHDATA0(0) OP_NOP OP_EQUAL",

	# pushdata0 above max (75)
	1: "OP_PUSHDATA0(76) " + hundred_bytes_hex[: 76 * 2],

	# pushdata1 below bounds
	2: "OP_PUSHDATA1(75) " + hundred_bytes_hex[: 75 * 2],

	# pushdata1 above bounds
	3: "OP_PUSHDATA1(256) " + (hundred_bytes_hex * 2) + \
	hundred_bytes_hex[: 56 * 2],

	# pushdata2 below bounds
	4: "OP_PUSHDATA2(255) " + (hundred_bytes_hex * 2) + \
	hundred_bytes_hex[: 55 * 2],

	# pushdata2 above bounds. overlaps with tests 14 and 15
	#5: "OP_PUSHDATA2(65536) " + (hundred_bytes_hex * 655) + \
	#hundred_bytes_hex[: 36 * 2],

	# pushdata4 below bounds. overlaps with tests 14 and 15
	#6: "OP_PUSHDATA4(65535) " + (hundred_bytes_hex * 655) + \
	#hundred_bytes_hex[: 35 * 2],

	# not enough bytes to push in pushdata0
	7: "OP_PUSHDATA0(2) 01",

	# too many bytes to push in pushdata0
	8: "OP_PUSHDATA0(1) 0102",

	# not enough bytes to push in pushdata1
	9: "OP_PUSHDATA1(77) 01",

	# too many bytes to push in pushdata1
	10: "OP_PUSHDATA1(77) " + hundred_bytes_hex[: 78 * 2],

	# not enough bytes to push in pushdata2
	11: "OP_PUSHDATA2(300) 01",

	# too many bytes to push in pushdata2
	12: "OP_PUSHDATA2(299) " + hundred_bytes_hex * 3,

	# not enough bytes to push in pushdata4
	13: "OP_PUSHDATA4(70000) 01",

	# too many bytes per opcode (max is 520)
	14: "OP_PUSHDATA2(521) 00" + (hundred_bytes_hex * 52),

	# too many bytes per script (max is 10000)
	15: "OP_PUSHDATA2(10001) 00" + (hundred_bytes_hex * 100),

	# too many opcodes (max is 200)
	16: ("OP_NOP " * 201).strip()
}
for (test_num, human_script) in human_scripts.items():
	if verbose:
		print """
========== test for incorrect non-checksig behaviour %s ==========
convert a human-readable script to bin and back: %s
""" % (test_num, chop_to_size(human_script, 200))

	bin_script_list = btc_grunt.human_script2bin_list(human_script)
	if bin_script_list is False:
		# failing to convert the human script into a binary list is acceptable
		# behaviour in these tests for incorrect scripts (eg due to a pushdata
		# opcode being out of bounds)
		if verbose:
			print "pass"
		continue
	bin_script = btc_grunt.script_list2bin(bin_script_list)
	rebin_script_list = btc_grunt.script_bin2list(bin_script)
	if rebin_script_list is False:
		# failing to convert the binary script into a binary list is acceptable
		# behaviour in these tests for incorrect scripts (eg due to an incorrect
		# number of bytes after a pushdata opcode)
		if verbose:
			print "pass"
		continue
	human_script2 = btc_grunt.script_list2human_str(rebin_script_list)
	if human_script2 == human_script:
		lang_grunt.die(
			"failed test %s - converting script %s to binary and back" % (
				test_num, chop_to_size(human_script, 200)
			)
		)
	if verbose:
		print "pass"

################################################################################
# unit tests for evaluating correct checksig scripts
################################################################################

# mimic the behaviour of the original bitcoin source code when performing
# validations and extracting addresses. this means validating certain buggy
# transactions without dying.
bugs_and_all = True

human_scripts = {
	# test the checksig for the first tx ever spent (from block 170)
	0: {
		"later_tx": {
			"hash": "f4184fc596403b9d638783cf57adfe4c75c605f6356fbc91338530e983"
			"1e9e16",

			"num_inputs": 1,
			"input": {
				0: {
					"hash": "0437cd7f8525ceed2324359c2d0ba26006d92d856a9c20fa02"
					"41106ee5a597c9",

					# push signature
					"parsed_script": "OP_PUSHDATA0(71) 304402204e45e16932b8af51"
					"4961a1d3a1a25fdf3f4f7732e9d624c6c61548ab5fb8cd410220181522"
					"ec8eca07de4860a4acdd12909d831cc56cbbac4622082221a8768d1d09"
					"01",

					"index": 0,
					"funds": 5000000000,
					"script_length": 72,
					"sequence_num": 4294967295
				}
			},
			"lock_time": 0,
			"num_outputs": 2,
			"output": {
				0: {
					# push pubkey op_checksig
					"parsed_script": "OP_PUSHDATA0(65) 04ae1a62fe09c5f51b13905f"
					"07f06b99a2f7159b2225f374cd378d71302fa28414e7aab37397f554a7"
					"df5f142c21c1b7303b8a0626f1baded5c72a704f7e6cd84c"
					" OP_CHECKSIG",

					"funds": 1000000000,
					"script_length": 67
				},
				1: {
					# push pubkey op_checksig
					"parsed_script": "OP_PUSHDATA0(65) 0411db93e1dcdb8a016b4984"
					"0f8c53bc1eb68a382e97b1482ecad7b148a6909a5cb2e0eaddfb84ccf9"
					"744464f82e160bfa9b8b64f9d4c03f999b8643f656b412a3"
					" OP_CHECKSIG",

					"funds": 4000000000,
					"script_length": 67
				}
			},
			"version": 1
		},
		"on_txin_num": 0,

		# push pubkey op_checksig
		"prev_txout_parsed_script": "OP_PUSHDATA0(65) 0411db93e1dcdb8a016b49840"
		"f8c53bc1eb68a382e97b1482ecad7b148a6909a5cb2e0eaddfb84ccf9744464f82e160"
		"bfa9b8b64f9d4c03f999b8643f656b412a3 OP_CHECKSIG"
	},
	# standard pay to pubkey hash tx with a single input
	1: {
		"later_tx": {
			"hash": "27f3727e0915a71cbe75dd9d5ded9d8161a82c0b81a3b60f5fff739cdd"
			"77fd51",

			"num_inputs": 1,
			"input": {
				0: {
					"hash": "2a2ea9f8a3558acb58c0a737d03ddeb36e6f00f0ff9db7d876"
					"22c89caf3a6ba3",

					# push signature push pubkey 
					"parsed_script": "OP_PUSHDATA0(73) 3046022100c4c87ea101d43c"
					"220ffdeb6ac1cc834c5b43c77ae1f4e809d7a6dd8149dfeed5022100f0"
					"8a2935a7f21188ef03ee69dd78ed6910ffa83239d82e3d03cd7305e28f"
					"92c001 OP_PUSHDATA0(65) 04d81236eb62fc1ac66a6192a7ca6762d0"
					"9730eebd898a6c485ce48d0b6c3245f5e4638a87e7d94bb07e6fc0f250"
					"aefe8f1c426320e86de6e7079bccc1827d2642",

					"index": 72,
					"funds": 100000000,
					"script_length": 140,
					"sequence_num": 4294967295
				}
			},
			"lock_time": 0,
			"num_outputs": 1,
			"output": {
				0: {
					"parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) 8bca4a"
					"44c14c181e4391c750c0c6d8b1b1a5bd5f OP_EQUALVERIFY"
					" OP_CHECKSIG",

					"funds": 100000000,
					"script_length": 25
				}
			},
			"version": 1
		},
		"on_txin_num": 0,

		"prev_txout_parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) 83b7202"
		"a69e6792a4160fff89f126a8ce9a68b71 OP_EQUALVERIFY OP_CHECKSIG"
	},
	# a tx with multiple inputs
	2: {
		"later_tx": {
			"hash": "dfc95e050b8d6dc76818ef6e1f117c7631cc971f86da4096efdf72434a"
			"1ef6be",
			"num_inputs": 4,
			"input": {
				0: {
					"hash": "cd245e9df44b7985c5ecd3dfe2ecfc5f0dcab6bf3c5c70e327"
					"e74bbbcc8fc073",

					"parsed_script": "OP_PUSHDATA0(72) 3045022012f400de6d1bd1e4"
					"19c9359b9c4f1655c90b0733655590a86831f39aadf71bf5022100bee0"
					"9e63962779f77ee9cecdffc07c5877ce006b9b71d67ad528ffa319a54b"
					"bf01 OP_PUSHDATA0(65) 04ba7218c27fa3ce013a33895a3511853f47"
					"65115bfc9a104ea83578df42ef14938b828775c55ca467b279b8ba3208"
					"d3b772ede39496a321e338b4c3dc5498fb87",

					"funds": 100000000,
					"index": 1,
					"script_length": 139,
					"sequence_num": 4294967295
				},
				1: {
					"hash": "cc27aeb6324103edf80b0a5af5517789b74b3589b1f3c99104"
					"8b299ce460c15c",

					"parsed_script": "OP_PUSHDATA0(72) 304502207fa17a8131e287ad"
					"2b670b1ccc19baff5aef195075b2593442592ed005a9e2e9022100e200"
					"3d9bc349de0b0b46f5f662fb5184f78dcbde0f8091ad78b1e9e0f0ac5b"
					"ea01 OP_PUSHDATA0(65) 04ba7218c27fa3ce013a33895a3511853f47"
					"65115bfc9a104ea83578df42ef14938b828775c55ca467b279b8ba3208"
					"d3b772ede39496a321e338b4c3dc5498fb87",

					"funds": 499000000,
					"index": 1,
					"script_length": 139,
					"sequence_num": 4294967295
				},
				2: {
					"hash": "14491fcd7e1a565ba3efefce221c5c053960990ab71a7c9243"
					"2af627646db7ea",

					"parsed_script": "OP_PUSHDATA0(72) 30450220265200e6503220f0"
					"3580c58b37b7eee0b9f6ade73481d2670f9c0264c5f98286022100ea29"
					"047189aebca045f15a6659f2f763f3e21da6df2e6fbfdc0b0084bee245"
					"6301 OP_PUSHDATA0(65) 048c25ca93acbea114e093d19bf1ae7f55a0"
					"3808d27c8f99265b3293d43dcb1fb3d2a3a42cb2d2e49e5b0057004870"
					"b35923ce6f697a656ca5a94cc63d7acb96e5",

					"funds": 100000000,
					"index": 1,
					"script_length": 139,
					"sequence_num": 4294967295
				},
				3: {
					"hash": "bb0040b5bfd2725fb4d1e6fd80b05da627b9196b6826f61f9d"
					"866c083e53962f",

					"parsed_script": "OP_PUSHDATA0(72) 3045022061845669092e5647"
					"781e703f68b0629d23402b537e7ee9ca7d67bfad5ddea3e10221009e9b"
					"5d63ace5935989170f6305f15f602ddb45d5b609291b2bb8385613ab8e"
					"5201 OP_PUSHDATA0(65) 04296c15d4590d7c568e095cfdebabf0b0e1"
					"22f93a3b1ced67d558bd1132d81278d3430af5e86c4b41b0221b037455"
					"8d08724777bfadc3c9d84ed661496abd40cf",

					"funds": 318932500,
					"index": 0,
					"script_length": 139,
					"sequence_num": 4294967295
				}
			},
			"lock_time": 0,
			"num_outputs": 2,
			"output": {
				0: {
					"parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) a4b5e5"
					"6a72c5d47e08887cc0f221d4c8fb1c97d8 OP_EQUALVERIFY"
					" OP_CHECKSIG",

					"funds": 27882500,
					"script_length": 25
				},
				1: {
					"parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) 5bb336"
					"1bb5d33d9e556bbfa5da5445997b7b9d66 OP_EQUALVERIFY"
					" OP_CHECKSIG",

					"funds": 990000000,
					"script_length": 25
				}
			},
			"version": 1
		},
		"on_txin_num": 2,

		"prev_txout_parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) 30c6c99"
		"201fa61f3fe3ef4f1e1a53432651251b8 OP_EQUALVERIFY OP_CHECKSIG"
	},
	# first checkmultisig tx ever
	3: {
		"later_tx": {
			"hash": "eb3b82c0884e3efa6d8b0be55b4915eb20be124c9766245bcc7f34fdac"
			"32bccb",

			"num_inputs": 2,
			"input": {
				0: {
					"hash": "b8fd633e7713a43d5ac87266adc78444669b987a56b3a65fb9"
					"2d58c2c4b0e84d",

					# push signature push pubkey
					"parsed_script": "OP_PUSHDATA0(72) 304502205b282fbc9b064f3b"
					"c823a23edcc0048cbb174754e7aa742e3c9f483ebe02911c022100e4b0"
					"b3a117d36cab5a67404dddbf43db7bea3c1530e0fe128ebc15621bd69a"
					"3b01 OP_PUSHDATA0(33) 035aa98d5f77cd9a2d88710e6fc66212aff8"
					"20026f0dad8f32d1f7ce87457dde50",

					"funds": 1950000,
					"index": 0,
					"script_length": 107,
					"sequence_num": 4294967295
				},
				# input 1 is the one we are evaluating:
				1: {
					"hash": "b8fd633e7713a43d5ac87266adc78444669b987a56b3a65fb9"
					"2d58c2c4b0e84d",

					# false push signature codesep true push pubkey true
					# checkmultisig
					"parsed_script": "OP_FALSE OP_PUSHDATA0(71) 30440220276d6da"
					"d3defa37b5f81add3992d510d2f44a317fd85e04f93a1e2daea6466020"
					"2200f862a0da684249322ceb8ed842fb8c859c0cb94c81e1c5308b4868"
					"157a428ee01 OP_CODESEPARATOR OP_TRUE OP_PUSHDATA0(33) 0232"
					"abdc893e7f0631364d7fd01cb33d24da45329a00357b3a7886211ab414"
					"d55a OP_TRUE OP_CHECKMULTISIG",

					"funds": 3000000,
					"index": 1,
					"script_length": 111,
					"sequence_num": 4294967295
				}
			},
			"lock_time": 0,
			"num_outputs": 2,
			"output": {
				0: {
					"parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) 380cb3"
					"c594de4e7e9b8e18db182987bebb5a4f70 OP_EQUALVERIFY"
					" OP_CHECKSIG",

					"funds": 1900000,
					"script_length": 25
				},
				1: {
					"parsed_script": "OP_PUSHDATA0(20) 2a9bc5447d664c1d0141392a"
					"842d23dba45c4f13 OP_NOP2 OP_DROP",

					"funds": 3000000,
					"script_length": 23
				}
			},
			"version": 1
		},
		"on_txin_num": 1,

		# push bytes nop drop-bytes
		"prev_txout_parsed_script": "OP_PUSHDATA0(20) 2a9bc5447d664c1d0141392a8"
		"42d23dba45c4f13 OP_NOP2 OP_DROP"
	},
	# first checkmultisig tx with more than 1 public key
	4: {
		"later_tx": {
			"hash": "bc179baab547b7d7c1d5d8d6f8b0cc6318eaa4b0dd0a093ad6ac7f5a1c"
			"b6b3ba",

			"num_inputs": 2,
			"input": {
				# input 0 is the one we are evaluating:
				0: {
					"hash": "477fff140b363ec2cc51f3a65c0c58eda38f4d41f04a295bbd"
					"62babf25e4c590",

					# false push signature codesep true push pubkey push
					# pubkey op2 checkmultisig
					"parsed_script": "OP_FALSE OP_PUSHDATA0(71) 30440220739d9ab"
					"2c3e7089e7bd311f267a65dc0ea00f49619cb61ec016a5038016ed7120"
					"2201b88257809b623d471e429787c36e0a9bcd2a058fc0c75fd9c25f90"
					"5657e3b9e01 OP_CODESEPARATOR OP_TRUE OP_PUSHDATA0(33) 03c8"
					"6390eb5230237f31de1f02e70ce61e77f6dbfefa7d0e4ed4f6b3f78f85"
					"d8ec OP_PUSHDATA0(33) 03193f28067b502b34cac9eae39f74dba481"
					"5e1278bab31516efb29bd8de2c1bea OP_2 OP_CHECKMULTISIG",

					"funds": 1000000,
					"index": 1,
					"script_length": 145,
					"sequence_num": 4294967295
				},
				1: {
					"hash": "0d0affb5964abe804ffe85e53f1dbb9f29e406aa3046e2db04"
					"fba240e63c7fdd",

					# false push signature codesep true push pubkey push pubkey
					# push pubkey op3 checkmultisig
					"parsed_script": "OP_FALSE OP_PUSHDATA0(72) 3045022100a28d2"
					"ace2f1cb4b2a58d26a5f1a2cc15cdd4cf1c65cee8e4521971c7dc60021"
					"c0220476a5ad62bfa7c18f9174d9e5e29bc0062df543e2c336ae2c7750"
					"7e462bbf95701 OP_CODESEPARATOR OP_TRUE OP_PUSHDATA0(33) 03"
					"c86390eb5230237f31de1f02e70ce61e77f6dbfefa7d0e4ed4f6b3f78f"
					"85d8ec OP_PUSHDATA0(33) 03193f28067b502b34cac9eae39f74dba4"
					"815e1278bab31516efb29bd8de2c1bea OP_PUSHDATA0(33) 032462c6"
					"0ebc21f4d38b3c4ccb33be77b57ae72762be12887252db18fd6225befb"
					" OP_3 OP_CHECKMULTISIG",

					"funds": 3000000,
					"index": 1,
					"script_length": 111,
					"sequence_num": 4294967295
				}
			},
			"lock_time": 0,
			"num_outputs": 2,
			"output": {
				0: {
					"parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) 850110"
					"6ab5492387998252403d70857acfa15864 OP_EQUALVERIFY"
					" OP_CHECKSIG",

					"funds": 1900000,
					"script_length": 25
				},
				1: {
					"parsed_script": "OP_PUSHDATA0(20) 99050637f553f03cc0f82bbf"
					"e98dc99f10526311 OP_NOP2 OP_DROP",

					"funds": 50000,
					"script_length": 23
				}
			},
			"version": 1
		},
		"on_txin_num": 0,

		# push bytes nop drop-bytes
		"prev_txout_parsed_script": "OP_PUSHDATA0(20) 64d63d835705618da2111ca31"
		"94f22d067187cf2 OP_NOP2 OP_DROP"
	},
	# first sighash_none type tx
	5: {
		"later_tx": {
			"hash": "599e47a8114fe098103663029548811d2651991b62397e057f0c863c2b"
			"c9f9ea",

			"num_inputs": 1,
			"input": {
				# input 0 is the one we are evaluating:
				0: {
					"hash": "5e8dfcccea014365e36b64648ba0bda7405a78be789bfadca9"
					"c942388a6c385f",

					# standard txin script
					"parsed_script": "OP_PUSHDATA0(71) 30440220bb4fbc495aa23bab"
					"b2c2be4e3fb4a5dffefe20c8eff5940f135649c3ea96444a022004afcd"
					"a966c807bb97622d3eefea828f623af306ef2b756782ee6f8a22a959a2"
					"02 OP_PUSHDATA0(65) 04f1939ae6b01e849bf05d0ed51fd5b92b79a0"
					"e313e3f389c726f11fa3e144d9227b07e8a87c0ee36372e967e090d11b"
					"777707aa73efacabffffa285c00b3622d6",

					"funds": 30913632,
					"index": 1,
					"script_length": 138,
					"sequence_num": 4294967295
				}
			},
			"lock_time": 0,
			"num_outputs": 2,
			"output": {
				0: {
					"parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) 660d4e"
					"f3a743e3e696ad990364e555c271ad504b OP_EQUALVERIFY"
					" OP_CHECKSIG",

					"funds": 1000000,
					"script_length": 25
				},
				1: {
					"parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) 21c43c"
					"e400901312a603e4207aadfd742be8e7da OP_EQUALVERIFY"
					" OP_CHECKSIG",

					"funds": 29913632,
					"script_length": 25
				}
			},
			"version": 1
		},
		"on_txin_num": 0,

		"prev_txout_parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) 21c43ce"
		"400901312a603e4207aadfd742be8e7da OP_EQUALVERIFY OP_CHECKSIG"
	},
	# first sighash_anyonecanpay type tx
	6: {
		"later_tx": {
			"hash": "51bf528ecf3c161e7c021224197dbe84f9a8564212f6207baa014c01a1"
			"668e1e",

			"num_inputs": 2,
			"input": {
				# input 0 is the one we are evaluating:
				0: {
					"hash": "761d8c5210fdfd505f6dff38f740ae3728eb93d7d0971fb433"
					"f685d40a4c04f6",

					# standard txin script
					"parsed_script": "OP_PUSHDATA0(72) 304502205853c7f1395785bf"
					"abb03c57e962eb076ff24d8e4e573b04db13b45ed3ed6ee20221009dc8"
					"2ae43be9d4b1fe2847754e1d36dad48ba801817d485dc529afc516c2dd"
					"b481 OP_PUSHDATA0(33) 0305584980367b321fad7f1c1f4d5d723d0a"
					"c80c1d80c8ba12343965b48364537a",

					"funds": 200000,
					"index": 1,
					"script_length": 107,
					"sequence_num": 4294967295
				},
				1: {
					"hash": "40cd1ee71808037f2ae01faef88de4788cbcbe257e319ed1de"
					"bc6966dff06a9c",

					# standard txin script
					"parsed_script": "OP_PUSHDATA0(73) 30460221008269c9d7ba0a7e"
					"730dd16f4082d29e3684fb7463ba064fd093afc170ad6e0388022100bc"
					"6d76373916a3ff6ee41b2c752001fda3c9e048bcff0d81d05b39ff0f42"
					"17b281 OP_PUSHDATA0(33) 03aae303d825421545c5bc7ccd5ac87dd5"
					"add3bcc3a432ba7aa2f2661699f9f659",

					"funds": 200000,
					"index": 1,
					"script_length": 108,
					"sequence_num": 4294967295
				}
			},
			"lock_time": 0,
			"num_outputs": 1,
			"output": {
				0: {
					"parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) 5c11f9"
					"17883b927eef77dc57707aeb853f6d3894 OP_EQUALVERIFY"
					" OP_CHECKSIG",

					"funds": 300000,
					"script_length": 25
				},
			},
			"version": 1
		},
		"on_txin_num": 0,

		"prev_txout_parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) 8551e48"
		"a53decd1cfc63079a4581bcccfad1a93c OP_EQUALVERIFY OP_CHECKSIG"
	}
}
explain = True
for (test_num, data) in human_scripts.items():
	if verbose:
		print """
========== test for correct checksig behaviour %s ==========
""" % test_num

	# get data in the required format
	tx = data["later_tx"]
	tx["hash"] = btc_grunt.hex2bin(tx["hash"])
	for (txin_num, txin) in tx["input"].items():
		tx["input"][txin_num]["hash"] = btc_grunt.hex2bin(
			tx["input"][txin_num]["hash"]
		)
		script_list = btc_grunt.human_script2bin_list(txin["parsed_script"])
		tx["input"][txin_num]["script_list"] = script_list
		tx["input"][txin_num]["script"] = btc_grunt.script_list2bin(script_list)
	for (txout_num, txout) in tx["output"].items():
		script_list = btc_grunt.human_script2bin_list(txout["parsed_script"])
		tx["output"][txout_num]["script"] = btc_grunt.script_list2bin(
			script_list
		)
	prev_txout_script_list = btc_grunt.human_script2bin_list(
		data["prev_txout_parsed_script"]
	)
	on_txin_num = data["on_txin_num"]
	txout_index = tx["input"][on_txin_num]["index"]
	prev_tx = {
		"hash": tx["input"][on_txin_num]["hash"],
		"output": {txout_index: {"script_list": prev_txout_script_list}}
	}
	result = btc_grunt.manage_script_eval(
		tx, on_txin_num, prev_tx, bugs_and_all, explain
	)
	
	if result["status"] is True:
		valid_addresses = btc_grunt.script_dict2addresses(result, "valid")
		invalid_addresses = btc_grunt.script_dict2addresses(result, "invalid")
		if verbose:
			print """pass
valid addresses: %s
invalid addresses: %s
signatures: %s
pubkeys: %s
sig_pubkey_statuses: %s""" % (
				valid_addresses, invalid_addresses, [
					btc_grunt.bin2hex(x) for x in result["signatures"]
				], [btc_grunt.bin2hex(x) for x in result["pubkeys"]], {
					btc_grunt.bin2hex(signature): {
						btc_grunt.bin2hex(pubkey): val for (pubkey, val) in \
						pubkeys.items()
					} for (signature, pubkeys) in \
					result["sig_pubkey_statuses"].items()
				}
			)
	else:
		lang_grunt.die(
			"test %s for correct checksig behaviour failed. error: %s" % (
				test_num, result
			)
		)

if not verbose:
	# silence is golden
	pass

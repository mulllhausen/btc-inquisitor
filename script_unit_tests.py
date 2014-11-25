#!/usr/bin/env python2.7
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
	print """
========== test for correct non-checksig behaviour %s ==========
convert a human-readable script to bin and back: %s
""" % (test_num, chop_to_size(human_script, 200))

	bin_script_list = btc_grunt.human_script2bin_list(human_script)
	bin_script = btc_grunt.script_list2bin(bin_script_list)
	rebin_script_list = btc_grunt.script_bin2list(bin_script)
	if rebin_script_list is False:
		exit("--->failed to convert binary script to human-readable string")
	human_script2 = btc_grunt.script_list2human_str(rebin_script_list)
	if human_script2 == human_script:
		print "--->pass"
	else:
		exit("--->fail")

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
	print """
========== test for incorrect non-checksig behaviour %s ==========
convert a human-readable script to bin and back: %s
""" % (test_num, chop_to_size(human_script, 200))

	bin_script_list = btc_grunt.human_script2bin_list(human_script)
	if bin_script_list is False:
		# failing to convert the human script into a binary list is acceptable
		# behaviour in these tests for incorrect scripts (eg due to a pushdata
		# opcode being out of bounds)
		print "--->pass"
		continue
	bin_script = btc_grunt.script_list2bin(bin_script_list)
	rebin_script_list = btc_grunt.script_bin2list(bin_script)
	if rebin_script_list is False:
		# failing to convert the binary script into a binary list is acceptable
		# behaviour in these tests for incorrect scripts (eg due to an incorrect
		# number of bytes after a pushdata opcode)
		print "--->pass"
		continue
	human_script2 = btc_grunt.script_list2human_str(rebin_script_list)
	if human_script2 == human_script:
		exit("--->fail")
	print "--->pass"

################################################################################
# unit tests for evaluating correct checksig scripts
################################################################################
human_scripts = {
	# test the checksig for the first tx ever spent (from block 170)
	0: {
		"later_tx": {
			"hash": btc_grunt.hex2bin("f4184fc596403b9d638783cf57adfe4c75c605f6356fbc91338530e9831e9e16"),
			"num_inputs": 1,
			"input": {
				0: {
					"funds": 5000000000,
					"hash": btc_grunt.hex2bin("0437cd7f8525ceed2324359c2d0ba26006d92d856a9c20fa0241106ee5a597c9"),
					"index": 0,
					"script_list": btc_grunt.human_script2bin_list("OP_PUSHDATA0(71) 304402204e45e16932b8af514961a1d3a1a25fdf3f4f7732e9d624c6c61548ab5fb8cd410220181522ec8eca07de4860a4acdd12909d831cc56cbbac4622082221a8768d1d0901"), # push signature
					"script_length": 72,
					"sequence_num": 4294967295,
				}
			},
			"lock_time": 0,
			"num_outputs": 2,
			"output": {
				0: {
					"funds": 1000000000,
					"script_list": btc_grunt.human_script2bin_list("OP_PUSHDATA0(65) 04ae1a62fe09c5f51b13905f07f06b99a2f7159b2225f374cd378d71302fa28414e7aab37397f554a7df5f142c21c1b7303b8a0626f1baded5c72a704f7e6cd84c OP_CHECKSIG"), # push pubkey op_checksig
					"script_length": 67
				},
				1: {
					"funds": 4000000000,
					"script_list": btc_grunt.human_script2bin_list("OP_PUSHDATA0(65) 0411db93e1dcdb8a016b49840f8c53bc1eb68a382e97b1482ecad7b148a6909a5cb2e0eaddfb84ccf9744464f82e160bfa9b8b64f9d4c03f999b8643f656b412a3 OP_CHECKSIG"), # push pubkey op_checksig
					"script_length": 67
				}
			},
			"version": 1
		},
		"on_txin_num": 0,
		"prev_txout_script_list": btc_grunt.human_script2bin_list("OP_PUSHDATA0(65) 0411db93e1dcdb8a016b49840f8c53bc1eb68a382e97b1482ecad7b148a6909a5cb2e0eaddfb84ccf9744464f82e160bfa9b8b64f9d4c03f999b8643f656b412a3 OP_CHECKSIG") # push pubkey op_checksig
	},
	# standard pay to pubkey hash tx
	1: {
		"later_tx": {
			"hash": btc_grunt.hex2bin("27f3727e0915a71cbe75dd9d5ded9d8161a82c0b81a3b60f5fff739cdd77fd51"),
			"num_inputs": 1,
			"input": {
				0: {
					"funds": 100000000,
					"hash": btc_grunt.hex2bin("2a2ea9f8a3558acb58c0a737d03ddeb36e6f00f0ff9db7d87622c89caf3a6ba3"),
					"index": 72,
					"script_list": btc_grunt.human_script2bin_list("OP_PUSHDATA0(73) 3046022100c4c87ea101d43c220ffdeb6ac1cc834c5b43c77ae1f4e809d7a6dd8149dfeed5022100f08a2935a7f21188ef03ee69dd78ed6910ffa83239d82e3d03cd7305e28f92c001 OP_PUSHDATA0(65) 04d81236eb62fc1ac66a6192a7ca6762d09730eebd898a6c485ce48d0b6c3245f5e4638a87e7d94bb07e6fc0f250aefe8f1c426320e86de6e7079bccc1827d2642"), # push signature push pubkey 
					"script_length": 140,
					"sequence_num": 4294967295
				}
			},
			"lock_time": 0,
			"num_outputs": 1,
			"output": {
				0: {
					"funds": 100000000,
					"script_list": btc_grunt.human_script2bin_list("OP_DUP OP_HASH160 OP_PUSHDATA0(20) 8bca4a44c14c181e4391c750c0c6d8b1b1a5bd5f OP_EQUALVERIFY OP_CHECKSIG"),
					"script_length": 25
				}
			},
			"timestamp": 1307734998,
			"version": 1
		},
		"on_txin_num": 0,
		"prev_txout_script_list": btc_grunt.human_script2bin_list("OP_DUP OP_HASH160 OP_PUSHDATA0(20) 83b7202a69e6792a4160fff89f126a8ce9a68b71 OP_EQUALVERIFY OP_CHECKSIG")
	},
	# first checkmultisig tx ever
	2: {
		"later_tx": {
			"hash": btc_grunt.hex2bin("eb3b82c0884e3efa6d8b0be55b4915eb20be124c9766245bcc7f34fdac32bccb"),
			"num_inputs": 2,
			"input": {
				0: {
					"funds": 1950000,
					"hash": btc_grunt.hex2bin("b8fd633e7713a43d5ac87266adc78444669b987a56b3a65fb92d58c2c4b0e84d"),
					"index": 0,
					"script_list": btc_grunt.human_script2bin_list("OP_PUSHDATA0(72) 304502205b282fbc9b064f3bc823a23edcc0048cbb174754e7aa742e3c9f483ebe02911c022100e4b0b3a117d36cab5a67404dddbf43db7bea3c1530e0fe128ebc15621bd69a3b01 OP_PUSHDATA0(33) 035aa98d5f77cd9a2d88710e6fc66212aff820026f0dad8f32d1f7ce87457dde50"), # push signature push pubkey
					"script_length": 107
				},
				# input 1 is the one we are evaluating:
				1: {
					"funds": 3000000,
					"hash": btc_grunt.hex2bin("b8fd633e7713a43d5ac87266adc78444669b987a56b3a65fb92d58c2c4b0e84d"),
					"index": 1,
					"script_list": btc_grunt.human_script2bin_list("OP_FALSE OP_PUSHDATA0(71) 30440220276d6dad3defa37b5f81add3992d510d2f44a317fd85e04f93a1e2daea64660202200f862a0da684249322ceb8ed842fb8c859c0cb94c81e1c5308b4868157a428ee01 OP_CODESEPARATOR OP_TRUE OP_PUSHDATA0(33) 0232abdc893e7f0631364d7fd01cb33d24da45329a00357b3a7886211ab414d55a OP_TRUE OP_CHECKMULTISIG"), # false push signature codesep true push pubkey true checkmultisig
					"script_length": 111
				}
			},
			"lock_time": 0,
			"num_outputs": 2,
			"output": {
				0: {
					"funds": 1900000,
					"script_list": btc_grunt.human_script2bin_list("OP_DUP OP_HASH160 OP_PUSHDATA0(20) 380cb3c594de4e7e9b8e18db182987bebb5a4f70 OP_EQUALVERIFY OP_CHECKSIG"),
					"script_length": 25,
				},
				1: {
					"funds": 3000000,
					"script_list": btc_grunt.human_script2bin_list("OP_PUSHDATA0(20) 2a9bc5447d664c1d0141392a842d23dba45c4f13 OP_NOP2 OP_DROP"),
					"script_length": 23,
				}
			},
			"version": 1
		},
		"on_txin_num": 1,
		"prev_txout_script_list": btc_grunt.human_script2bin_list("OP_PUSHDATA0(20) 2a9bc5447d664c1d0141392a842d23dba45c4f13 OP_NOP2 OP_DROP") # push bytes nop drop-bytes
	}
}
explain = True
for (test_num, data) in human_scripts.items():
	print """
========== test for correct checksig behaviour %s ==========
""" % test_num

	tx = data["later_tx"]

	# copy script lists to script bins
	for (txin_num, txin) in tx["input"].items():
		tx["input"][txin_num]["script"] = btc_grunt.script_list2bin(txin["script_list"])
	for (txout_num, txout) in tx["output"].items():
		tx["output"][txout_num]["script"] = btc_grunt.script_list2bin(txout["script_list"])

	on_txin_num = data["on_txin_num"]
	txout_index = tx["input"][on_txin_num]["index"]
	prev_tx = {
		"hash": tx["input"][on_txin_num]["hash"],
		"output": {txout_index: {"script_list": data["prev_txout_script_list"]}}
	}
	result = btc_grunt.manage_script_eval(tx, on_txin_num, prev_tx, explain)
	if result is True:
		print "--->pass"
	else:
		exit("--->fail. error: %s" % result)

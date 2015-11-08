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

verbose = "-v" in sys.argv

# module to convert data into human readable form
import lang_grunt

# module containing some general bitcoin-related functions
import btc_grunt

import json

################################################################################
# first, some positive tests for encoding/decoding bitcoin stack integers
################################################################################

# convert from integer to minimal stack bin and back
inputs = [
	(0x00,  "\x00"),
	(-0x00, "\x00"),
	(0x7f,  "\x7f"),
	(-0x7f, "\xff"), # -0x7f -> 0xff
	(0xff,  "\xff\x00"), # 0xff -> 0x00ff -> 0xff00
	(-0xff, "\xff\x80") # 0xff -> 0x80ff -> 0xff80
]
for (i, (stack_int, stack_bin)) in enumerate(inputs):
	if verbose:
		print """
=========== test for correct stack integer encoding and decoding %s ============
convert integer %s to a minimal stack element binary (%s) and back
""" % (i, stack_int, btc_grunt.bin2hex(stack_bin))

	stack_bin_calc = btc_grunt.stack_int2bin(stack_int)
	if stack_bin_calc != stack_bin:
		raise Exception(
			"stack integer %s has been incorrectly translated into bytes %s."
			" it should be %s"
			% (
				stack_int, btc_grunt.bin2hex(stack_bin_calc),
				btc_grunt.bin2hex(stack_bin)
			)
		)
	stack_int_recalc = btc_grunt.stack_bin2int(stack_bin)
	if stack_int_recalc != stack_int:
		raise Exception(
			"stack integer %s has been incorrectly translated back to integer"
			" %s, via bytes %s"
			% (stack_int, stack_int_recalc, btc_grunt.bin2hex(stack_bin_calc))
		)
	if verbose:
		print "pass"

# convert from non-minimal stack bin to integer, but not back
inputs = [
	("\x00\x00\x00\x00",  0x00), # 0x00 -> 0x00000000
	("\x00\x00\x00\x80", -0x00), # 0x00000080 -> 0x80000000 -> -0x00
	("\xff\x00\x00\x00",  0xff), # 0xff000000 -> 0x000000ff -> 0xff
	("\xff\x00\x00\x80", -0xff)  # 0xff000080 -> 0x800000ff -> -0xff
]
for (i, (stack_bin, stack_int)) in enumerate(inputs):
	if verbose:
		print """
================== test for correct stack integer encoding %s ==================
convert non-minimally encoded stack element binary %s to integer %s
""" % (i, btc_grunt.bin2hex(stack_bin), stack_int)

	stack_int_recalc = btc_grunt.stack_bin2int(stack_bin)
	if stack_int_recalc != stack_int:
		raise Exception(
			"stack bytes %s have been incorrectly translated to integer %s."
			" it should be %s."
			% (btc_grunt.bin2hex(stack_bin), stack_int_recalc, stack_int)
		)
	if verbose:
		print "pass"

################################################################################
# now, the intentional-fail tests for encoding/decoding bitcoin stack integers
################################################################################

inputs = [
	"\x00\x00\x00\x00\x00", # too many bytes
	"\xff\x00\x00" # non-minimal encoding (minimal would be "\xff\x00")
]
for (i, stack_bin) in enumerate(inputs):
	if verbose:
		print """
========== test for incorrect stack binary decoding and re-encoding %s =========
ensure that stack element binary %s is non-minimally encoded
""" % (i, btc_grunt.bin2hex(stack_bin))

	res = btc_grunt.minimal_stack_bytes(stack_bin)
	if res is True:
		raise Exception(
			"function minimal_stack_bytes() failed to detect the error in stack"
			" bytes %"
			% btc_grunt.bin2hex(stack_bin)
		)
	else:
		if verbose:
			print "pass"

################################################################################
# next, the intentional-fail tests on invalid der signature encodings
################################################################################

# 0x30<signature length>0x02<length r><r>0x02<length s><s><sighash>
inputs = [
	("03 06 02 01 7f 02 01 7f", "too short (sighash byte missing)"),
	(
		"03 48 02 21 %s 02 22 %s 01" % ("7f" * 0x21, "7f" * 0x22),
		"too long (73 bytes is the max)"
	),
	(
		"00 06 02 01 7f 02 01 7f 01",
		"wrong placeholder1 byte, otherwise correct"
	),
	("30 07 02 01 7f 02 01 7f 01", "wrong alleged signature length byte"),
	(
		"30 06 00 01 7f 02 01 7f 01",
		"wrong placeholder 2 byte, otherwise correct"
	),
	("30 06 02 02 7f 02 01 7f 01", "wrong <length r>"),
	("30 06 02 01 7f 02 02 7f 01", "<length r> and <length s> do not add up"),
	("30 06 02 00    02 01 7f 01 00", "no r (append 00 otherwise too short)"),
	("30 06 02 01 ff 02 01 7f 01", "r is ambiguously negative"),
	("30 07 02 02 00 01 02 01 7f 01", "r starts with 00 and is not negative"),
	(
		"30 06 02 01 7f 00 01 7f 01",
		"wrong placeholder 3 byte, otherwise correct"
	),
	("30 06 02 01 7f 02 00    01 00", "no s (append 00 otherwise too short)"),
	("30 06 02 01 7f 02 01 ff 01", "s is ambiguously negative"),
	("30 07 02 01 7f 02 02 00 01 01", "s starts with 00 and is not negative"),
]
for (i, (der_signature_human, error_description)) in enumerate(inputs):
	der_signature_bin = btc_grunt.hex2bin(der_signature_human.replace(" ", ""))
	if verbose:
		print """
================== test for incorrect der signature encoding %s ================
ensure %s. der signature: %s
""" % (i, error_description, der_signature_human)

	res = btc_grunt.valid_der_signature(der_signature_bin, explain = True)
	if res is True:
		raise Exception(
			"function valid_der_signature() failed to detect the error in der"
			" signature bytes %"
			% der_signature_human
		)
	else:
		if verbose:
			print "pass - error expected.\n%s" % res

################################################################################
# unit tests for converting a non-checksig script from human-readable script to
# bin and back
################################################################################

hundred_bytes_hex = "01020304050607080910111213141516171819202122232425262728" \
"2930313233343536373839404142434445464748495051525354555657585960616263646566" \
"67686970717273747576777879808182838485868788899091929394959697989900"

def chop_to_size(str, size):
	"""chop a string down to the specified number of characters"""
	return str if (len(str) < size) else ("%s..." % str[: size])

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
==================== test for correct non-checksig behaviour %s ================
convert a human-readable script to bin and back: %s
""" % (test_num, chop_to_size(human_script, 200))

	bin_script_list = btc_grunt.human_script2bin_list(human_script)
	bin_script = btc_grunt.script_list2bin(bin_script_list)
	rebin_script_list = btc_grunt.script_bin2list(bin_script)
	if rebin_script_list is False:
		raise Exception(
			"failed test %s - converting script %s to binary list" % (
				test_num, chop_to_size(human_script, 200)
			)
		)
	human_script2 = btc_grunt.script_list2human_str(rebin_script_list)
	if human_script2 == human_script:
		if verbose:
			print "pass"
	else:
		raise Exception(
			"test %s failed for correct non-checksig behaviour" % (
				test_num, chop_to_size(human_script, 200)
			)
		)

################################################################################
# unit tests for correctly evaluating a non-checksig script
################################################################################
human_scripts = {
	# tx 9 in block 251684 - first use of OP_SIZE, OP_GREATERTHAN, OP_NEGATE
	0: {
		"txin": "OP_PUSHDATA0(20) 16cfb9bc7654ef1d7723e5c2722fc0c3d505045e",
		"prev_txout": "OP_SIZE OP_DUP OP_TRUE OP_GREATERTHAN OP_VERIFY" \
		" OP_NEGATE OP_HASH256 OP_HASH160 OP_SHA256 OP_SHA1 OP_RIPEMD160" \
		" OP_EQUAL"
	}
}
""",
	# tx 24 in block 251718 - first use of OP_IF, OP_INVALIDOPCODE, OP_ENDIF
	1: {
		txin: "",
		prev_txout: "OP_IF OP_INVALIDOPCODE 4effffffff 46726f6d20613361363166" \
		"65663433333039623966623233323235646637393130623033616663353436356239" \
		"204d6f6e205365702031372030303a30303a303020323030310a46726f6d3a205361" \
		"746f736869204e616b616d6f746f203c7361746f7368696e40676d782e636f6d3e0a" \
		"446174653a204d6f6e2c2031322041756720323031332030323a32383a3032202d30" \
		"3230300a5375626a6563743a205b50415443485d2052656d6f7665202853494e474c" \
		"457c444f55424c4529425954450a0a492072656d6f76656420746869732066726f6d" \
		"20426974636f696e20696e2066316531666234626465663837386338666331353634" \
		"6661343138643434653735343161376538330a696e2053657074203720323031302c" \
		"20616c6d6f73742074687265652079656172732061676f2e204265207761726e6564" \
		"207468617420492068617665206e6f740a61637475616c6c79207465737465642074" \
		"6869732070617463682e0a2d2d2d0a206261636b656e64732f626974636f696e642f" \
		"646573657269616c697a652e7079207c2020202038202b2d2d2d2d2d2d2d0a203120" \
		"66696c65206368616e6765642c203120696e73657274696f6e282b292c2037206465" \
		"6c6574696f6e73282d290a0a64696666202d2d67697420612f6261636b656e64732f" \
		"626974636f696e642f646573657269616c697a652e707920622f6261636b656e6473" \
		"2f626974636f696e642f646573657269616c697a652e70790a696e64657820363632" \
		"303538332e2e38396239623162203130303634340a2d2d2d20612f6261636b656e64" \
		"732f626974636f696e642f646573657269616c697a652e70790a2b2b2b20622f6261" \
		"636b656e64732f626974636f696e642f646573657269616c697a652e70790a404020" \
		"2d3238302c3130202b3238302c38204040206f70636f646573203d20456e756d6572" \
		"6174696f6e28224f70636f646573222c205b0a2020202020224f505f57495448494e" \
		"222c20224f505f524950454d44313630222c20224f505f53484131222c20224f505f" \
		"534841323536222c20224f505f48415348313630222c0a2020202020224f505f4841" \
		"5348323536222c20224f505f434f4445534550415241544f52222c20224f505f4348" \
		"45434b534947222c20224f505f434845434b534947564552494659222c20224f505f" \
		"434845434b4d554c5449534947222c0a2020202020224f505f434845434b4d554c54" \
		"49534947564552494659222c0a2d2020202028224f505f53494e474c45425954455f" \
		"454e44222c2030784630292c0a2d2020202028224f505f444f55424c45425954455f" \
		"424547494e222c20307846303030292c0a2020202020224f505f5055424b4559222c" \
		"20224f505f5055424b455948415348222c0a2d2020202028224f505f494e56414c49" \
		"444f50434f4445222c20307846464646292c0a2b2020202028224f505f494e56414c" \
		"49444f50434f4445222c2030784646292c0a205d290a200a200a4040202d3239332c" \
		"3130202b3239312c3620404020646566207363726970745f4765744f702862797465" \
		"73293a0a202020202020202020766368203d204e6f6e650a2020202020202020206f" \
		"70636f6465203d206f72642862797465735b695d290a20202020202020202069202b" \
		"3d20310a2d20202020202020206966206f70636f6465203e3d206f70636f6465732e" \
		"4f505f53494e474c45425954455f454e4420616e642069203c206c656e2862797465" \
		"73293a0a2d2020202020202020202020206f70636f6465203c3c3d20380a2d202020" \
		"2020202020202020206f70636f6465207c3d206f72642862797465735b695d290a2d" \
		"20202020202020202020202069202b3d20310a200a2020202020202020206966206f" \
		"70636f6465203c3d206f70636f6465732e4f505f5055534844415441343a0a202020" \
		"202020202020202020206e53697a65203d206f70636f64650a2d2d200a312e372e39" \
		"2e340a0a OP_ENDIF"
	}
"""
wiped_tx = None # only used in checksigs, not required here
on_txin_num = None # only used in checksigs, not required here
tx_locktime = 0 # only used in checklocktimeverify, not required here
txin_sequence_num = 0 # only used in checklocktimeverify, not required here
bugs_and_all = True
explain = True
for (test_num, human_script) in human_scripts.items():
	if verbose:
		print """
=============== test correct evaluation of non-checksig script %s ==============
script: %s
""" % (test_num, human_script)

	# reset results for each test
	results = { # init
		"status": True,
		"txin script (scriptsig)": None,
		"txout script (scriptpubkey)": None,
		"p2sh script": None,
		"pubkeys": [],
		"signatures": [],
		"sig_pubkey_statuses": {}
	}
	stack = [] # reset stack for each test
	txin_script_list = btc_grunt.human_script2bin_list(human_script["txin"])
	# first, eval the txin script
	(results, stack) = btc_grunt.eval_script(
		results, stack, txin_script_list, wiped_tx, on_txin_num, tx_locktime,
		txin_sequence_num, bugs_and_all, "txin script", explain
	)
	if results["status"] is True:
		# the script passed - move on to the next eval_script
		pass
	else:
		# the script failed
		raise Exception("failed test %s - %s" % (test_num, results["status"]))

	# second, eval the previous txout script
	prev_txout_script_list = btc_grunt.human_script2bin_list(
		human_script["prev_txout"]
	)
	(results, stack) = btc_grunt.eval_script(
		results, stack, prev_txout_script_list, wiped_tx, on_txin_num,
		tx_locktime, txin_sequence_num, bugs_and_all, "txout script", explain
	)
	if results["status"] is True:
		# the script passed
		if verbose:
			print "pass"
	else:
		# the script failed
		raise Exception("failed test %s - %s" % (test_num, results["status"]))


################################################################################
# unit tests for failure - converting a non-checksig script from human-readable
# script to bin and back
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
================= test for incorrect non-checksig behaviour %s =================
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
		raise Exception(
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
		"blocktime": 1231731025,
		"version": 1,
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
	# standard pay to pubkey hash tx with a single input (tx 11 from block
	# 129878)
	1: {
		"blocktime": 1307734998,
		"version": 1,
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
	# a tx with multiple inputs (tx 9 from block 163685)
	2: {
		"blocktime": 1327430572,
		"version": 1,
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
	# first checkmultisig and first OP_CHECKLOCKTIMEVERIFY tx ever (tx 13 from
	# block 163685), 
	3: {
		"blocktime": 1327430572,
		"version": 1,
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
					"842d23dba45c4f13 OP_CHECKLOCKTIMEVERIFY OP_DROP",

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
	# first checkmultisig tx with more than 1 public key (tx 17 from block
	# 164676)
	4: {
		"blocktime": 1327992805,
		"version": 1,
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
	# first sighash_none type tx (tx 55 from block 178581)
	5: {
		"blocktime": 1336138343,
		"version": 1,
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
	# first sighash_anyonecanpay type tx (tx 323 from block 207733)
	6: {
		"blocktime": 1352799776,
		"version": 1,
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
				}
			},
			"version": 1
		},
		"on_txin_num": 0,

		"prev_txout_parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) 8551e48"
		"a53decd1cfc63079a4581bcccfad1a93c OP_EQUALVERIFY OP_CHECKSIG"
	},
	# first multisig tx with more than 1 signature (tx 407 from block 232626)
	7: {
		"blocktime": 1366659915,
		"version": 1,
		"later_tx": {
			"hash": "7c2c4cf601c4607d068fdf6b95900b8a5bc73fbb9a22200ab56ebfe44b"
			"8c6e74",

			"num_inputs": 2,
			"input": {
				# input 0 is the one we are evaluating:
				0: {
					"hash": "9ac8145738a8c8f9f09e6f01f112a99c5adaa44beab3b97f71"
					"8ad0bf64d6b238",

					"parsed_script": "OP_FALSE OP_PUSHDATA0(73) 304502207964ee9"
					"eb517e4dafd2b62aebcc462da2879bc39c783ff9c3cd9bb5274f037e20"
					"22100ab925a8d6430094a528c19ac94a05293c2cad5508b314eccc409b"
					"94d6a0fcd220101 OP_PUSHDATA0(71) 304402206e8303d40154bb333"
					"2d11af736405314ee3159dd77fcfc65bc2e90a8559a65c5022013e3f77"
					"1431b6b6d120947214fea9c032bbebc4c6d38703e17c3b79420f01c3e0"
					"1",

					"funds": 450000,
					"index": 1,
					"script_length": 147,
					"sequence_num": 4294967295
				},
				1: {
					"hash": "ced4d0b5e9cf4bdc7718fa1367fc9dc85c2f0f0ecb74ebdb44"
					"701843c10e9e06",

					# standard txin script
					"parsed_script": "OP_FALSE OP_PUSHDATA0(71) 3043021f42d85c4"
					"ce0fbd961b4efc756396bc2d5b86af460a064b2b970f5187805a455022"
					"03c0252525fd0d0c57e6e6b1cfe5349d04038e548558f98dd2d81874c9"
					"901fa770101 OP_PUSHDATA0(72) 3045022035d59ffa6a9458936e155"
					"e944cd6d945e8b35a61422007164f2fd9d4fc958cef022100b7fd6812e"
					"10fef6ad91c9494b12d8e6c4514aea38364b19288a43922cfcfff2201",

					"funds": 1000000,
					"index": 0,
					"script_length": 146,
					"sequence_num": 4294967295
				}
			},
			"lock_time": 0,
			"num_outputs": 2,
			"output": {
				0: {
					"parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) c1a329"
					"3d3b2563d8b571e76387fb183e979d0cd7 OP_EQUALVERIFY"
					" OP_CHECKSIG",

					"funds": 1000000,
					"script_length": 25
				},
				1: {
					"parsed_script": "OP_2 OP_PUSHDATA0(65) 04f26232717a535dd84"
					"eb363d63edddd9512007c57dbfdb44828f64a2f45455d0307b0a740a83"
					"bba1929367e2a31c69fca5a0bbb8e0e896e833ad7160ef8d0d0a4"
					" OP_PUSHDATA0(65) 0472471c2349c30e22c0f00bccb13be9fbbbf65d"
					"02119888dcac5bcc3a1b6b0ea90fb70b38ac09e24302fce537b34f5ff6"
					"93860ea0e20e95546e2830f9049f8ba6 OP_2 OP_CHECKMULTISIG",

					"funds": 400000,
					"script_length": 135
				}
			},
			"version": 1
		},
		"on_txin_num": 0,
		# should also validate since this tx references two identical txouts:
		# "on_txin_num": 1,

		"prev_txout_parsed_script": "OP_2 OP_PUSHDATA0(65) 04f26232717a535dd84e"
		"b363d63edddd9512007c57dbfdb44828f64a2f45455d0307b0a740a83bba1929367e2a"
		"31c69fca5a0bbb8e0e896e833ad7160ef8d0d0a4 OP_PUSHDATA0(65) 0472471c2349"
		"c30e22c0f00bccb13be9fbbbf65d02119888dcac5bcc3a1b6b0ea90fb70b38ac09e243"
		"02fce537b34f5ff693860ea0e20e95546e2830f9049f8ba6 OP_2 OP_CHECKMULTISIG"
	},
	# a random tx (tx 122 in block 251712) that was failing
	8: {
		"blocktime": 1376295050,
		"version": 1,
		"later_tx": {
			"hash": "ee5a5dc33719fedead5f04a82cae22b1d2009c69747f94a245bbeaf03a"
			"e974dc",

			"num_inputs": 2,
			"input": {
				# input 0 is the one we are evaluating:
				0: {
					"hash": "c3a86f36bc0cb9566cd1a3e0237ebc8ad6e7fc9c039f7a809f"
					"700da1c6b18131",

					"parsed_script": "OP_PUSHDATA0(71) 30440220cb315ad082a06d82"
					"a7da6f2d5fa56e1bbdf6afb2a15be4eea30c4b5febd95d760220a9b134"
					"a54a23ad9249e7e777be04fedba90ac0058d0c77dade5f5c2b99215a59"
					"01 OP_PUSHDATA0(65) 0468b240f7589b5ab5d278a72776314975082c"
					"517a67e0a826b06652a3a2d68cb2f68b95f23646ae37efcc6bb04db147"
					"d57307dc54fb3cdacfca7dd31a91883dbd",

					"funds": 1000000,
					"index": 7,
					"script_length": 138,
					"sequence_num": 4294967295
				},
				1: {
					"hash": "7c5fe252d90ea3ff8dc5b511cc252048bacd675fdd08e7ff69"
					"8a3e3c5290670c",

					"parsed_script": "OP_PUSHDATA0(71) 30440220b62431bc9cf215eb"
					"e5c260c5771b750b641993596222fdc29f31951bf38c74cc022089c560"
					"d9a56e33aaf163f98494dca54d0242f98639b7bd09d7a5db3369193843"
					"01 OP_PUSHDATA0(65) 0468b240f7589b5ab5d278a72776314975082c"
					"517a67e0a826b06652a3a2d68cb2f68b95f23646ae37efcc6bb04db147"
					"d57307dc54fb3cdacfca7dd31a91883dbd",

					"funds": 1000649,
					"index": 32,
					"script_length": 138,
					"sequence_num": 4294967295
				}
			},
			"lock_time": 0,
			"num_outputs": 2,
			"output": {
				0: {
					"parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) 06f1b6"
					"703d3f56427bfcfd372f952d50d04b64bd OP_EQUALVERIFY"
					" OP_CHECKSIG",

					"funds": 1000000,
					"script_length": 25
				},
				1: {
					"parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) bb793b"
					"5c476f688e7aa632735a1db81b8d6270f3 OP_EQUALVERIFY"
					" OP_CHECKSIG",

					"funds": 950649,
					"script_length": 25
				}
			},
			"version": 1
		},
		"on_txin_num": 0,

		"prev_txout_parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) bb793b5"
		"c476f688e7aa632735a1db81b8d6270f3 OP_EQUALVERIFY OP_CHECKSIG"
	},
	# first occurrence of OP_DEPTH ever (tx 90 in block 251898)
	9: {
		"blocktime": 1376378339,
		"version": 1,
		"later_tx": {
			"hash": "340aa9f72206d600b7e89c9137e4d2d77a920723f83e34707ff452121f"
			"d48492",

			"num_inputs": 1,
			"input": {
				# input 0 is the one we are evaluating:
				0: {
					"hash": "f2d72a7bf22e29e3f2dc721afbf0a922860f81db9fc7eb3979"
					"37f9d7e87cc438",

					"parsed_script": "OP_PUSHDATA0(20) 027ce87f6f41dd4d7d874b40"
					"889f7df6b288f77f",

					"funds": 9900000,
					"index": 0,
					"script_length": 21,
					"sequence_num": 4294967295
				}
			},
			"lock_time": 0,
			"num_outputs": 1,
			"output": {
				0: {
					"parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) b0c1c1"
					"de86419f7c6f3186935e6bd6ccb52b8ee5 OP_EQUALVERIFY"
					" OP_CHECKSIG",

					"funds": 9890000,
					"script_length": 25 
				}
			},
			"version": 1
		},
		"on_txin_num": 0,

		"prev_txout_parsed_script": "OP_DEPTH OP_HASH256 OP_HASH160 OP_SHA256"
		" OP_SHA1 OP_RIPEMD160 OP_EQUAL"
	},
	# first occurrence of OP_SWAP ever (tx 99 in block 251898)
	10: {
		"blocktime": 1376378339,
		"version": 1,
		"later_tx": {
			"hash": "cd874fa8cb0e2ec2d385735d5e1fd482c4fe648533efb4c50ee53bda58"
			"e15ae2",

			"num_inputs": 1,
			"input": {
				# input 0 is the one we are evaluating:
				0: {
					"hash": "514c46f0b61714092f15c8dfcb576c9f79b3f959989b98de39"
					"44b19d98832b58",

					"parsed_script": "OP_PUSHDATA0(1) 01 OP_PUSHDATA0(73) 30460"
					"22100be13275293b79346f8d14d158cc0864ff214b123aeae15fb7411d"
					"f7c06a970ce022100de54627449d397aebad5e79f8215572201bb78be5"
					"f9c0b6ed8d7846b6f6cecb501 OP_PUSHDATA0(1) 01"
					" OP_PUSHDATA0(1) 00",

					"funds": 10000000,
					"index": 0,
					"script_length": 80,
					"sequence_num": 4294967295
				}
			},
			"lock_time": 0,
			"num_outputs": 1,
			"output": {
				0: {
					"parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) b0c1c1"
					"de86419f7c6f3186935e6bd6ccb52b8ee5 OP_EQUALVERIFY"
					" OP_CHECKSIG",

					"funds": 9990000,
					"script_length": 25 
				}
			},
			"version": 1
		},
		"on_txin_num": 0,

		"prev_txout_parsed_script": "OP_PUSHDATA0(33) 0378d430274f8c5ec13213381"
		"51e9f27f4c676a008bdf8638d07c0b6be9ab35c71 OP_SWAP OP_1ADD"
		" OP_CHECKMULTISIG"
	},
	# a p2sh script (tx 20 in block 170060)
	11: {
		"blocktime": 1331137983,
		"version": 1,
		"later_tx": {
			"hash": "6a26d2ecb67f27d1fa5524763b49029d7106e91e3cc05743073461a719"
			"776192",

			"num_inputs": 1,
			"input": {
				# input 0 is the one we are evaluating:
				0: {
					"hash": "9c08a4d78931342b37fd5f72900fb9983087e6f46c4a097d8a"
					"1f52c74e28eaf6",

					"parsed_script": "OP_PUSHDATA0(37) 5121029b6d2c97b8b7c718c3"
					"25d7be3ac30f7c9d67651bce0c929f55ee77ce58efcf8451ae",

					"funds": 400000,
					"index": 1,
					"script_length": 38,
					"sequence_num": 4294967295
				}
			},
			"lock_time": 0,
			"num_outputs": 1,
			"output": {
				0: {
					"parsed_script": "OP_DUP OP_HASH160 OP_PUSHDATA0(20) 5a3acb"
					"c7bbcc97c5ff16f5909c9d7d3fadb293a8 OP_EQUALVERIFY"
					" OP_CHECKSIG",

					"funds": 350000,
					"script_length": 25
				}
			},
			"version": 1
		},
		"on_txin_num": 0,

		"prev_txout_parsed_script": "OP_HASH160 OP_PUSHDATA0(20) 19a7d869032368"
		"fd1f1e26e5e73a4ad0e474960e OP_EQUAL"
	}
}
explain = True
for (test_num, data) in human_scripts.items():
	if verbose:
		print """
===================== test for correct checksig behaviour %s ===================
""" % test_num

	# first get data in the required format
	blocktime = data["blocktime"]
	block_version = data["version"]
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
	# script format is necessary to determine if we need to evaluate a p2sh
	prev_txout_script_format = btc_grunt.extract_script_format(
		prev_txout_script_list, ignore_nops = False
	)
	on_txin_num = data["on_txin_num"]
	txout_index = tx["input"][on_txin_num]["index"]
	prev_tx = {
		"hash": tx["input"][on_txin_num]["hash"],
		"output": {
			txout_index: {
				"script_list": prev_txout_script_list,
				"script_format": prev_txout_script_format
			}
		}
	}
	# verify all scripts
	result = btc_grunt.verify_script(
		blocktime, tx, on_txin_num, prev_tx, block_version, bugs_and_all,
		explain
	)
	# make the results human-readable
	sig_pubkey_statuses = {} # init
	for (sig, pubkey_data) in result["sig_pubkey_statuses"].items():
		human_sig = btc_grunt.bin2hex(sig)
		sig_pubkey_statuses[human_sig] = {} # init
		for (pubkey, res) in pubkey_data.items():
			human_pubkey = btc_grunt.bin2hex(pubkey)
			sig_pubkey_statuses[human_sig][human_pubkey] = res

	result["sig_pubkey_statuses"] = sig_pubkey_statuses

	for i in range(len(result["pubkeys"])):
		result["pubkeys"][i] = btc_grunt.bin2hex(result["pubkeys"][i])

	for i in range(len(result["signatures"])):
		result["signatures"][i] = btc_grunt.bin2hex(result["signatures"][i])

	if result["status"] is True:
		valid_addresses = btc_grunt.script_dict2addresses(result, "valid")
		invalid_addresses = btc_grunt.script_dict2addresses(result, "invalid")
		if verbose:
					
			print """pass
valid addresses: %s
invalid addresses: %s
%s""" % (
				valid_addresses, invalid_addresses,
				json.dumps(result, sort_keys = True, indent = 4)
			)
	else:
		raise Exception(
			"test %s for correct checksig behaviour failed. error: %s" % (
				test_num, json.dumps(result, sort_keys = True, indent = 4)
			)
		)

if not verbose:
	# silence is golden
	pass

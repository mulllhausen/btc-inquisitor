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

if not verbose:
	# silence is golden
	pass

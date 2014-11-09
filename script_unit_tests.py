#!/usr/bin/env python2.7
import btc_grunt

hundred_bytes_hex =	"01020304050607080910111213141516171819202122232425262728" \
"2930313233343536373839404142434445464748495051525354555657585960616263646566" \
"67686970717273747576777879808182838485868788899091929394959697989900"

def chop_to_size(str, size):
	"""chop a string down to the specified number of characters"""
	return str if (len(str) < size) else ("%s..." % str[: size])

################################################################################
# unit tests for correct scripts
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
==========test for correct behaviour %s==========
convert a human-readable script to bin and back: %s
""" % (test_num, chop_to_size(human_script, 200))

	bin_script_list = btc_grunt.human_script2bin_list(human_script)
	bin_script = btc_grunt.script_list2bin(bin_script_list)
	rebin_script_list = btc_grunt.script_bin2list(bin_script)
	if rebin_script_list is False:
		print "--->failed to convert binary script to human-readable string"
		continue
	human_script2 = btc_grunt.script_list2human_str(rebin_script_list)
	print "--->pass" if (human_script2 == human_script) else "--->fail"

################################################################################
# unit tests for incorrect scripts
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
==========test for incorrect behaviour %s==========
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
	print "--->fail" if (human_script2 == human_script) else "--->pass"

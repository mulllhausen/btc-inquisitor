#!/usr/bin/env python2.7
import btc_grunt

# unit tests for scripts

human_scripts = {
	1: "OP_PUSHDATA0(5) 0102030405 OP_NOP OP_EQUAL",
	2: "OP_PUSHDATA0(75) 010203040506070809101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475 OP_NOP OP_DUP OP_EQUALVERIFY",
	3: "OP_PUSHDATA0(76) 01020304050607080910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273747576 OP_NOP OP_DUP OP_EQUALVERIFY"
}
for (test_num, human_script) in human_scripts.items():
	print """
==========test %s==========
convert a human-readable script to bin and back: %s
	""" % (test_num, human_script)

	bin_script_list = btc_grunt.human_script2bin_list(human_script)
	bin_script = btc_grunt.script_list2bin(bin_script_list)
	rebin_script_list = btc_grunt.script_bin2list(bin_script)
	reconverted_human_script = btc_grunt.script_list2human_str(rebin_script_list)
	print "pass" if (reconverted_human_script == human_script) else "fail"

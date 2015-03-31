#!/usr/bin/env python2.7

# TODO - generate addresses starting with 3
# TODO - create a secret with pubkey, reveal it with private key
# TODO - implement recovery of pubkey from message and signature as per https://github.com/vbuterin/pybitcointools

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

# module containing some general bitcoin-related functions
import ecdsa_ssl

if verbose:
	print """
################################################################################
# test 1: (openssl) create a bitcoin private key, public key and address from a
# constant seed
################################################################################
"""

ecdsa_ssl.init()
seed1 = "correct horse battery staple"
const_hash_bin1 = btc_grunt.sha256(btc_grunt.ascii2bin(seed1))
const_hash_hex1 = btc_grunt.bin2hex(const_hash_bin1)
ecdsa_ssl.generate(const_hash_bin1)
private_key_hex1 = btc_grunt.bin2hex(ecdsa_ssl.get_privkey())
pubkey_bin1 = ecdsa_ssl.get_pubkey()
pubkey_hex1 = btc_grunt.bin2hex(pubkey_bin1)
address1 = btc_grunt.pubkey2address(pubkey_bin1)

ecdsa_ssl.set_compressed(True)
pubkey_compressed_bin1 = ecdsa_ssl.get_pubkey()
pubkey_compressed_hex1 = btc_grunt.bin2hex(pubkey_compressed_bin1)
address_compressed1 = btc_grunt.pubkey2address(pubkey_compressed_bin1)

if verbose:
	print "seed: %s" % seed1
	print
	print "hash: %s" % const_hash_hex1
	print
	print "resulting private key: %s" % private_key_hex1
	print
	print "public key: %s" % pubkey_hex1
	print
	print "compressed public key: %s" % pubkey_compressed_hex1
	print
	print "address: %s" % address1
	print
	print "compressed address: %s" % address_compressed1

ecdsa_ssl.reset()

if verbose:
	print """
################################################################################
# test 2: (openssl) check that a public key created from a constant seed is
# always the same even though k varies in openssl
################################################################################
"""
ecdsa_ssl.init()

# same seed as test 1
seed2 = "correct horse battery staple"
const_hash_bin2 = btc_grunt.sha256(btc_grunt.ascii2bin(seed2))
const_hash_hex2 = btc_grunt.bin2hex(const_hash_bin2)
ecdsa_ssl.generate(const_hash_bin2)
pubkey_bin2 = ecdsa_ssl.get_pubkey()
address2 = btc_grunt.pubkey2address(pubkey_bin2)

if address1 == address2:
	if verbose:
		print "pass"
else:
	lang_grunt.die(
		"fail. seed '%s' resulted in a different address this time. address 1:"
		" %s, address 2: %s" % (
			seed2, address1, address2
		)
	)

ecdsa_ssl.reset()

if verbose:
	print """
################################################################################
# test 3: (openssl) sign a hash with a private key then verify it with the
# public key
################################################################################
"""
ecdsa_ssl.init()

alice_seed3 = "super secret seed known only by alice"
alice_const_hash_bin3 = btc_grunt.sha256(btc_grunt.ascii2bin(alice_seed3))
ecdsa_ssl.generate(alice_const_hash_bin3)
alice_public_key3 = ecdsa_ssl.get_pubkey()
alice_address3 = btc_grunt.pubkey2address(alice_public_key3)
#print alice_address3

# alice: hi bob. did you know that i own bitcoin address
# 1KZfohMK4dt1eCP1tbGrSaWmQ5KMX5MV98

# bob: wow! you're a bitcoin millionaire! no way - you live like an impoverished
# bum. you must be lying.

# alice: na man i'm just smart with my money.

# bob: prove you own it then - send me some money.

# alice: i'll prove it to you, but not by sending you money. if i did that for
# everyone who asked me to prove i own it then i'd have no money left!

# bob: you could prove it by showing me your private key ;)

# alice: no way!! you'd steal all my money!

# bob: how can you prove it then?

# alice: i'll use my private key to sign a string, then you can use my public
# key to verify the signature.

# bob: ok cool. please sign this string: "this address belongs to bob".

# alice: i'm not going to sign that! you'll use it to trick people into thinking
# you own my address and all the millions it contains.

# bob: damn. ok fine. you pick the string.

# alice: ok i will sign the string "hello world"

# bob: wait a second. how do i know that you haven't already asked someone else
# to prove they own address 1KZfohMK4dt1eCP1tbGrSaWmQ5KMX5MV98 and it was
# actually they who signed the string?

# alice: fair point. i will sign some current infomation so you know that this
# is not an old signature being reused. i will sign the latest bitcoin
# blockchain hash:
# 00000000000000000eccd6cb33d1b5d4307c8f66ab7c235242bcf7bc903b1a69

# bob: good idea

alice_signs_this3 = "00000000000000000eccd6cb33d1b5d4307c8f66ab7c235242bcf7bc" \
"903b1a69"
alice_signature3 = ecdsa_ssl.sign(alice_signs_this3)
#print btc_grunt.bin2hex(alice_signature3)
#print btc_grunt.bin2hex(alice_public_key3)

# alice: ok, here is the signature: 304402204db6eb1dbad806c30dd1ca9d447a83d02560
# 4f5fdc240071c1701b0f570c8ce9022029c8d82bbd5054191b705e1b59a01b5f1fb83dd95e3759
# bf697190f376916011 and my public key is 043541f2e75c8ee8266dd11fdc1885c48efeea
# 551fbb41f8e52f7bb69cf25c2b8c33a692474756f8d6849b1a7b5e15500b6aac261bdca3c5a897
# 01c8cd69e3516e

# bob: ok let me first check that the public key actually corresponds to address
# 1KZfohMK4dt1eCP1tbGrSaWmQ5KMX5MV98...

bob_test_pubkey_hex3 = "043541f2e75c8ee8266dd11fdc1885c48efeea551fbb41f8e52f7" \
"bb69cf25c2b8c33a692474756f8d6849b1a7b5e15500b6aac261bdca3c5a89701c8cd69e3516e"
bob_test_pubkey_bin3 = btc_grunt.hex2bin(bob_test_pubkey_hex3)

bob_derived_address3 = btc_grunt.pubkey2address(bob_test_pubkey_bin3)
if bob_derived_address3 == alice_address3:
	# bob: yep. it checks out!
	pass
else:
	# bob: nope. this public key does not belong to the address you gave me. i
	# knew you were lying!
	lang_grunt.die(
		"fail. alice's address %s differs from the address bob has derived from"
		" her public key: %s" % (
			alice_address3, bob_derived_address3
		)
	)

# bob: now to verify the string you signed with your private key...

# delete the key object to make sure none of alice's data remains
ecdsa_ssl.reset()
ecdsa_ssl.init()

bob_test_plaintext3 = "00000000000000000eccd6cb33d1b5d4307c8f66ab7c235242bcf7" \
"bc903b1a69"
bob_test_signature_hex3 = "304402204db6eb1dbad806c30dd1ca9d447a83d025604f5fdc" \
"240071c1701b0f570c8ce9022029c8d82bbd5054191b705e1b59a01b5f1fb83dd95e3759bf69" \
"7190f376916011"
bob_test_signature_bin3 = btc_grunt.hex2bin(bob_test_signature_hex3)

ecdsa_ssl.set_pubkey(bob_test_pubkey_bin3)
if ecdsa_ssl.verify(bob_test_plaintext3, bob_test_signature_bin3):
	# bob: wow cool! you were telling the truth! you really are a bitcoin
	# millionaire! how did you get so many bitcoins?
	if verbose:
		print "pass"
else:
	# bob: yeah just as i thought - you're a big liar.
	lang_grunt.die(
		"fail. alice has signed string '%s', resulting in signature %s. however"
		" her public key %s failed to validate this." % (
			bob_test_plaintext3, btc_grunt.bin2hex(bob_test_signature_bin3),
			bob_test_pubkey_hex3
		)
	)

ecdsa_ssl.reset()

if verbose:
	print """
################################################################################
# end of tests
################################################################################
"""
else:
	# silence is golden
	pass

#!/usr/bin/env python2.7
import sys, btc_grunt

"""derive the uncompressed and compressed address for a given pubkey"""

if len(sys.argv) < 2:
	raise ValueError(
		"\n\nUsage: ./pubkey2addresses.py <the pubkey in hex>\n"
		"eg: ./pubkey2addresses.py 04180bfa57bff462c7641fa0b91efe29344a77086b07"
		"3cd9c5f769cb2393acc151a4e7377eaabacc39f5b2bd2cd4bcb5ed1855939619e491c7"
		"9c0bb5793d4edbf3\n\n"
	)
pubkey = sys.argv[1]
(uncompressed_address, compressed_address) = btc_grunt.pubkey2addresses(pubkey)
result = {
	"uncompressed_address": uncompressed_address,
	"compressed_address": compressed_address
}
print btc_grunt.pretty_json(result)

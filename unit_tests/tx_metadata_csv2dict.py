#!/usr/bin/env python2.7

import os, json

# when executing this test directly include the parent dir in the path
if (
	(__name__ == "__main__") and
	(__package__ is None)
):
	os.sys.path.append(
		os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	)

# module to convert data into human readable form
import lang_grunt

# module containing some general bitcoin-related functions
import btc_grunt

csv_data_list = [
"23ab47f962e86d1849fe2e1bdc3e3e5e49373fd8082bbb3792d704eeeaaec40f," \
"4855-31,5,16648355,13174,3138,149912,,,[49f1-2,1d7e-2]",
"23ab47a450dd4a8ba00f25041813e42dae7e29508d0ec94980344433088b2861," \
"386d-26,12,12945601,15984,259,183244,,,[,ad9b-1]",
"23ab470debadb4dcbe0d78ecf802f3baaafe9924e9beef6e3f1e8303fe9f0664," \
"c9c7-3,3,128407591,731,193,142392,,,[d308-0,3bd9-15]",
"23ab470debadb4dcbe0d78ecf802f3baaafe9924e9beef6e3f1e8303fe9f0664," \
"ffff-9,13,111111111,777,193,999999,,,[,]"
]
# determine the actual result
tx_metadata_dict = btc_grunt.tx_metadata_csv2dict(csv_data_list)
desired_result = {
	# a real btc tx
    "23ab470debadb4dcbe0d78ecf802f3baaafe9924e9beef6e3f1e8303fe9f0664": {
        "c9c7-3": {
            "block_height": 142392,
            "block_start_pos": 128407591,
            "blockfile_num": 3,
            "is_coinbase": None,
            "is_orphan": None,
            "spending_txs_list": [
                "d308-0",
                "3bd9-15"
            ],
            "tx_size": 193,
            "tx_start_pos": 731
        },
		# a non-existent btc tx for testing duplicate hash (rare)
        "ffff-9": {
            "block_height": 999999,
            "block_start_pos": 111111111,
            "blockfile_num": 13,
            "is_coinbase": None,
            "is_orphan": None,
            "spending_txs_list": [
                None,
                None
            ],
            "tx_size": 193,
            "tx_start_pos": 777
        }
    },
	# a real btc tx
    "23ab47a450dd4a8ba00f25041813e42dae7e29508d0ec94980344433088b2861": {
        "386d-26": {
            "block_height": 183244,
            "block_start_pos": 12945601,
            "blockfile_num": 12,
            "is_coinbase": None,
            "is_orphan": None,
            "spending_txs_list": [
                None,
                "ad9b-1"
            ],
            "tx_size": 259,
            "tx_start_pos": 15984
        }
    },
	# a real btc tx
    "23ab47f962e86d1849fe2e1bdc3e3e5e49373fd8082bbb3792d704eeeaaec40f": {
        "4855-31": {
            "block_height": 149912,
            "block_start_pos": 16648355,
            "blockfile_num": 5,
            "is_coinbase": None,
            "is_orphan": None,
            "spending_txs_list": [
                "49f1-2",
                "1d7e-2"
            ],
            "tx_size": 3138,
            "tx_start_pos": 13174
        }
    }
}
if tx_metadata_dict == desired_result:
	print "pass"
else:
	lang_grunt.die("fail: %s" % os.linesep.join(
		l.rstrip() for l in json.dumps(
			tx_metadata_dict, sort_keys = True, indent = 4
		).splitlines()
	))

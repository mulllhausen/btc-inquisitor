#!/usr/bin/env python2.7

import os, shutil, copy, json

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

# set the btc_grunt base dir to the current dir
btc_grunt.base_dir = os.path.join(
	os.path.dirname(os.path.abspath(__file__)), ""
)
btc_grunt.tx_meta_dir = os.path.join(btc_grunt.base_dir, "tx_metadata", "")

txhash1 = "23ab47f962e86d1849fe2e1bdc3e3e5e49373fd8082bbb3792d704eeeaaec40f"

# get the dir and filename for this hash
(f_dir, f_name, hashend) = btc_grunt.hash2dir_and_filename_and_hashend(txhash1)

# erase the test tx_metadata file if it exists
if os.path.exists(btc_grunt.tx_meta_dir):
	shutil.rmtree(btc_grunt.tx_meta_dir)

# write the data to the tx_metadata file
save_data1 = {
	"c9c7-3": {
		"blockfile_num": 3,
		"block_start_pos": 128407591,
		"tx_start_pos": 731,
		"tx_size": 193,
		"block_height": 142392,
		"is_coinbase": None,
		"is_orphan": None,
		"spending_txs_list": ["d308-0", "3bd9-15"]
	}
}
btc_grunt.save_tx_data_to_disk(txhash1, save_data1)

# merge new data into the tx metadata file
save_data2 = {
	"ffff-9": {
		"blockfile_num": 3,
		"block_start_pos": 111111111,
		"tx_start_pos": 777,
		"tx_size": 193,
		"block_height": 999999,
		"is_coinbase": None,
		"is_orphan": None,
		"spending_txs_list": [None, None]
	}
}
btc_grunt.save_tx_data_to_disk(txhash1, save_data2)
txhash2 = "23ab47a450dd4a8ba00f25041813e42dae7e29508d0ec94980344433088b2861"
save_data3 = {
	"386d-26": {
		"blockfile_num": 12,
		"block_start_pos": 12945601,
		"tx_start_pos": 15984,
		"tx_size": 259,
		"block_height": 183244,
		"is_coinbase": None,
		"is_orphan": None,
		"spending_txs_list": [None, "ad9b-1"]
	}
}
btc_grunt.save_tx_data_to_disk(txhash2, save_data3)

# verify that the file now contains the correct data
existing_data_csv = btc_grunt.get_tx_metadata_csv(txhash1) # one tx per list item
existing_data_dict = btc_grunt.tx_metadata_csv2dict(existing_data_csv)
save_data_combined = copy.deepcopy(save_data1)
save_data_combined.update(save_data2)
expected_data_dict = {txhash1: save_data_combined, txhash2: save_data3}
if existing_data_dict == expected_data_dict:
	print "pass"
	# clean up the directories since everything is fine
	shutil.rmtree(btc_grunt.tx_meta_dir)
else:
	# do not clean up the directories, leave for investigation
	lang_grunt.die("fail. expected: %s but got %s" % (
		os.linesep.join(
			l.rstrip() for l in json.dumps(
				expected_data_dict, sort_keys = True, indent = 4
			).splitlines()
		),
		os.linesep.join(
			l.rstrip() for l in json.dumps(
				existing_data_dict, sort_keys = True, indent = 4
			).splitlines()
		),
	))

#!/usr/bin/env python2.7
"""
validate all txin scripts in the supplied txhash against their previous txout
scripts
"""
import sys
import btc_grunt
import get_tx
import get_tx_from_db
import validate_tx_scripts

def validate_script_usage():
    if len(sys.argv) < 2:
        raise ValueError(
            "\n\nUsage: ./validate_tx_scripts_from_db.py <the tx hash in hex |"
            " blockheight-txnum> <verbose>\n"
            "eg: ./validate_tx_scripts.py 514c46f0b61714092f15c8dfcb576c9f79b3f"
            "959989b98de3944b19d98832b58 1\n\n"
            "or ./validate_tx_scripts_from_db.py 257727-130 yes\n\n"
        )

if __name__ == '__main__':

    validate_script_usage()
    (input_arg_format, data) = get_tx.get_stdin_params()
    in_hex = False # we want bytes, not hex
    (tx_dict, block_data) = get_tx_from_db.get_data_from_db(
        input_arg_format, data, in_hex
    )
    should_print = validate_tx_scripts.always_display_results()

    if should_print:
        print "\n" \
        "txhash: %s\n" \
        "tx number: %d\n" \
        "block: %d" \
        % (
            btc_grunt.bin2hex(block_data["tx_hash"]), block_data["tx_num"],
            block_data["block_height"]
        )

    if block_data["tx_num"] == 0:
        if should_print:
            print "this is a coinbase tx - no scripts to verify"
        exit()

    validate_tx_scripts.validate(
        tx_dict, block_data["tx_num"], block_data["block_height"],
        block_data["block_time"], block_data["block_version"]
    )

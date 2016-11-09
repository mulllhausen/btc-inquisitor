#!/usr/bin/env python2.7
"""
validate all txin scripts in the supplied txhash against their previous txout
scripts
"""
import sys
import btc_grunt
import get_tx

def validate_script_usage():
    if len(sys.argv) < 2:
        raise ValueError(
            "\n\nUsage: ./validate_tx_scripts.py <the tx hash in hex |"
            " blockheight-txnum> <verbose>\n"
            "eg: ./validate_tx_scripts.py 514c46f0b61714092f15c8dfcb576c9f79b3f"
            "959989b98de3944b19d98832b58 1\n\n"
            "or ./validate_tx_scripts.py 257727-130 yes\n\n"
        )

def always_display_results():
    return (
        (len(sys.argv) > 2) and (
            (
                isinstance(sys.argv[2], (int, long)) and
                (int(sys.argv[2]) > 0)
            ) or (
                isinstance(sys.argv[2], basestring) and
                sys.argv[2].lower() not in ["false", "null", "no", "off"]
            )
        )
    )

def validate(
    tx_dict, tx_num, block_hash, block_height, block_time, block_version
):
    bugs_and_all = True

    # the previous tx number is not relevant since it is only used for txin
    # data, and we only care about txout data from the previous tx
    fake_prev_tx_num = 0

    # the prev block height is not relevant since it is only used to calculate
    # the mining reward
    fake_prev_block_height = 0

    # always re-validate checksigs here (its the whole point!)
    skip_checksig = False

    # loop through all txins
    for txin_num in range(tx_dict["num_inputs"]):

        # "prev_tx" data is stored using the previous block hash and previous tx
        # number in that block because it used to be possible to have the same
        # txhash in many different blocks. but since the hash is the same, the
        # data is also the same, so any will do. pop the first one for
        # convenience.
        prev_tx0 = tx_dict["input"][txin_num]["prev_txs"].values()[0]

        res = btc_grunt.verify_script(
            block_time, tx_dict, txin_num, prev_tx0, block_version,
            skip_checksig, bugs_and_all, explain = True
        )
        if (
            always_display_results() or
            (res["status"] is not True)
        ):
            res["pubkeys"] = [btc_grunt.bin2hex(p) for p in res["pubkeys"]]
            res["signatures"] = [btc_grunt.bin2hex(s) for s in res["signatures"]]
            sig_pubkey_statuses_hex = {} # init
            for (bin_sig, pubkey_dict) in res["sig_pubkey_statuses"].items():
                hex_sig = btc_grunt.bin2hex(bin_sig)
                sig_pubkey_statuses_hex[hex_sig] = {} # init
                for (bin_pubkey, status) in pubkey_dict.items():
                    hex_pubkey = btc_grunt.bin2hex(bin_pubkey)
                    sig_pubkey_statuses_hex[hex_sig][hex_pubkey] = status

            del res["sig_pubkey_statuses"]
            res["sig_pubkey_statuses"] = sig_pubkey_statuses_hex

            print "\ntxin %d validation %s:\n%s\n" % (
                txin_num, "fail" if (res["status"] is not True) else "pass",
                btc_grunt.pretty_json(res)
            )

if __name__ == '__main__':

    validate_script_usage()
    (input_arg_format, data) = get_tx.get_stdin_params()

    # note that the following will execute btc_grunt.connect_to_rpc()
    (tx_dict, tx_num, block_rpc_dict, tx_rpc_dict) = \
    get_tx.get_tx_data_from_rpc(input_arg_format, data)

    should_print = always_display_results()
    if should_print:
        print "\n" \
        "txhash: %s\n" \
        "tx number: %d\n" \
        "block: %d" \
        % (btc_grunt.bin2hex(tx_dict["hash"]), tx_num, block_rpc_dict["height"])

    if tx_num == 0:
        if should_print:
            print "this is a coinbase tx - no scripts to verify"
        exit()

    validate(
        tx_dict, tx_num, block_rpc_dict["hash"], block_rpc_dict["height"],
        block_rpc_dict["time"], block_rpc_dict["version"]
    )

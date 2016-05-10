#!/usr/bin/env python2.7

"""
update_addresses_db.py gets addresses from the blockchain and stores them
against the tx hash in a mysql db. you can easily look up all txs for an address
using this db table. storing information in a database is far better than
relying on bitcoin-cli's listtransactions. theoretically listtransactions should
be able to do the same thing as this database, but it currently has a bug which
prevents it from working for watch-only addresses
(https://bitcointalk.org/index.php?topic=1258904.0). and even once this bug is
fixed, it takes ~40 minutes to add a watch-only address (as of nov 2015). a busy
website/app will want to add a new address more than once per second, so a ~40
minute wait would be useless for this purpose.

this script is intended to run in parallel on multiple machines, so it takes a
range of blocks to parse addresses from, like so:

update_addresses_db.py startblock endblock

the script writes the parsed addresses into mysql table x_map_addresses_to_txs
where x is this computer's unique id as specified in mysql_connection.json.
these tables are created on other machines and then brought back to the master
machine to be merged together into table map_addresses_to_txs.

this script takes orders from the tasklist table, where start and end
blockheight are specified. if there are no entries in the tasklist table then
this script will sit idle until it receives instructions to start.

public keys are points on the secp256k1 elliptic curve. the same pubkey can be
represented in uncompressed or compressed format. the uncompressed pubkey
basically involves concatenating the x and y coordinates, whereas the compressed
pubkey just involves the x coordinate and a sign bit (the y coordinate can be
derived from the x coordinate using the equation of the curve if we know whether
the point we are after lies above or below the x-axis).

bitcoin addresses are derived by hashing the pubkey. there is one address for
the compressed pubkey and one address for the uncompressed pubkey. but both of
these addresses and pubkeys refer to the same point on the elliptic curve.

to spend a txout the pubkey must be supplied (generally in a txin script but in
earlier blocks it was in the txout script). so by the time an address is spent
the pubkey is always known, but it is not always known (to us) when a user sends
funds to an address.

as it scans the blockchain, update_addresses_db.py encounters pubkeys. it then
derives both the compressed and uncompressed addresses from the pubkey and
stores them both against that txhash and txin/txout number. but when
update_addresses_db.py encounters an address without a pubkey (ie in a standard
txout) then only that known address is stored. without the pubkey there is no
way of knowing whether the address is compressed or uncompressed.

some bitcoin addresses are in p2sh (pay to script-hash) format. this form of
address is a hash of an entire script (as opposed to a hash of a single pubkey).
the script-hash can contain many pubkeys and other script elements. when someone
sends funds to a p2sh address we don't know the pubkey(s) contained within it,
but once the p2sh is spent then the pubkeys are revealed. at that point we
discover which address(es) the funds were really sent to. however there is no
easy way of linking the p2sh address in the txout to the txin addresses that
actually spent the funds. therefore to make this link, update_addresses_db.py
copies the addresses derived from the pubkeys that actually validate, to the
txout in the db. this is a special case only used for p2sh txs.

finally, multisignature addresses may involve multiple pubkeys. these are not
available in the txout script until it is spent (until it is spent it is non-
standard and so has no addresses). when a txin with multiple pubkeys spends a
txout then the pubkeys that correctly validate are converted to addresses and
stored against both the txin and previous txout. this means that a txin or a
txout can have multiple rows in the db - in these cases the `shared_funds` flag
will always be set. this indicates that the funds are shared between multiple
addresses (to avoid inflation when calculating address totals).

useful features of the database:

- you can search for an address (search in both the `address` and
`alternate_address` fields) and find the corresponding compressed/uncompressed
address. with this alternate address you can then see all transfers of funds
to/from a single pubkey.

- you can find the pubkey corrsponding to an address (if it has been revealed on
the blockchain already). do this by finding a row where both `address` and
`alternate_address` are not null. this indicates that the pubkey was known in
that tx, so you can feed `txhash` into ./get_tx.py and pull out the pubkey from
the corresponding `txin_num` or `txout_num`.

- you can find the balance for a pubkey by first converting it to both the
compressed and uncompressed addresses, then selecting all rows from the database
that have these addresses. remember to search for the compressed and
uncompressed addresses in both `address` and `alternate_address`.

- search for non-standard unspent txout scripts. do this by searching where
`address` and `alternate_address` are null, and where txin_num is null and
txout_num is not null. the reason this only works for unspent txouts is that
if the txin that spends this txout has a pubkey then it will be copied over to
the txout by update_addresses_db.py.

- search for txin scripts which have no pubkeys. do this by searching where
`address` and `alternate_address` are null, and where txout_num is null and
txin_num is not null.

- search for txout scripts which are spent by txin scripts where no pubkeys
are used. do this using the same method as searching for non-standard unspent
txout scripts.

- search for multisig transactions. do this by searching on the shared_funds
field.

- find the addresses that actually received funds within a p2sh address.
"""

import sys
import MySQLdb
import btc_grunt
import mysql_grunt
import progress_meter
import copy
import json
import email_grunt

# only stay silent if the user has added the "auto" argument
be_quiet = ((len(sys.argv) > 1) and (sys.argv[1] == "auto"))
print_status = (not be_quiet)

with open("mysql_connection.json") as mysql_params_file:
    mysql_params = json.load(mysql_params_file)

# only use the relevant properties for the connection
mysql_connection_params = {
    "host": mysql_params["host"],
    "user": mysql_params["user"],
    "passwd": mysql_params["passwd"],
    "db": mysql_params["db"]
}
mysql_db = MySQLdb.connect(**mysql_connection_params)
mysql_db.autocommit(True)
cursor = mysql_db.cursor(MySQLdb.cursors.DictCursor)

# get the allocated block-range for this script on this machine, higher ids take
# precedence. the tasklist is general-purpose, so the block-range is defined in
# the 'details' field as json.
cmd = mysql_grunt.clean_query("""
    select id, details from tasklist
    where host = '%s'
    and name = 'map_addresses_to_txouts'
    and started is null
    and ended is null
    order by id desc
    limit 1
""" % mysql_params["unique_host_id"])
cursor.execute(cmd)

if cursor.rowcount < 1:
    if print_status:
        print "there are no tasks assigned for mapping addresses to txouts"
    exit()

data = cursor.fetchall()
details = json.loads(data[0]["details"])
start_block = details["start_block"]
end_block = details["end_block"]

# there is no need to check if the specified range has already been parsed.
# whatever program or person calls this script will need to check that themself.

# mark the current task as "in-progress"
cmd = mysql_grunt.clean_query("""
    update tasklist set started = now()
    where id = %d
    and host = '%s'
""" % (data[0]["id"], mysql_params["unique_host_id"]))
cursor.execute(cmd)

btc_grunt.connect_to_rpc()
required_always = ["tx_hash", "tx_bytes", "timestamp", "version"]
required_txin_info = [
    "txin_hash",
    "txin_index",
    "txin_script",
    "txin_script_list",
    "txin_script_format",
    "txin_sig_pubkey_validation_status"
]
required_txout_info = [
    "txout_script",
    "txout_script_format",
    "txout_standard_script_pubkey",
    "txout_standard_script_address"
]
required_checksig_info = [
    "tx_version",
    "txin_hash",
    "txin_index",
    "txin_script",
    "txin_script_list",
    "num_tx_inputs",
    "txin_sequence_num",
    "txout_funds",
    "txout_script",
    "tx_lock_time",
    "prev_txs"
]

def main(block_height_start, block_height_end):
    """
    loop through all transactions in the block and add the txouts to the db.

    because transactions can spend from the same block, we need to add all the
    txouts to the db first. we do this for the entire blockchain, then we loop
    through the txins afterwards (this way the previous txouts will always be
    available as required).

    this is more complicated than it sounds. get the addresses and or pubkeys in
    the following order:
    1. addresses (inc p2sh) or pubkeys from standard txout scripts
    2. non-standard txout scripts (1 empty row per script)
    3. from standard txin scripts that spend standard txout scripts that have
    already been validated by btc-inquisitor.py
    4. non-standard txin scripts

    (4) often requires us to perform a checksig operation on the script to
    extract the pubkey(s). this is slow, but fortunately not extremely common
    (most checksigs are within standard scripts).
    """
    global report_block_height, report_tx_num, report_txin_num, report_txout_num
    # init
    report_block_height = -1
    report_tx_num = -1
    report_txin_num = -1
    report_txout_num = -1

    # assume this block is not an orphan, other scripts will update this later
    # if it is found to be an orphan
    orphan_block = None
    required_info = list(set(
        #required_txin_info +
        required_txout_info +
        required_always
    ))
    for block_height in xrange(block_height_start, block_height_end):
        report_block_height = block_height
        if print_status:
            progress_meter.render(
                100 * block_height / float(block_height_end),
                "parsing block %d (to %d)" % (
                    block_height, block_height_end
                )
            )
        block_bytes = btc_grunt.get_block(block_height, "bytes")
        parsed_block = btc_grunt.block_bin2dict(
            block_bytes, block_height, required_info, explain_errors = True
        )
        # not needed for blocks that have already been validated:
        # btc_grunt.enforce_valid_block(parsed_block, options)

        blocktime = parsed_block["timestamp"]
        block_version = parsed_block["version"]

        # first loop through the txouts
        for (tx_num, parsed_tx) in parsed_block["tx"].items():

            report_tx_num = tx_num
            txhash_hex = btc_grunt.bin2hex(parsed_tx["hash"])
            parsed_txid_already = None
            # 1
            for (txout_num, txout) in parsed_tx["output"].items():
                txin_num = None
                report_txin_num = txin_num
                report_txout_num = txout_num
                # if there is a pubkey then get the corresponding addresses and
                # write these to the db
                if txout["standard_script_pubkey"] is not None:
                    # standard scripts have 1 pubkey. shared_funds requires > 1
                    shared_funds = False
                    (uncompressed_address, compressed_address) = \
                    btc_grunt.pubkey2addresses(txout["standard_script_pubkey"])
                    insert_record(
                        block_height, txhash_hex, txin_num, txout_num,
                        uncompressed_address, compressed_address,
                        txout["script_format"], shared_funds, orphan_block
                    )
                elif txout["standard_script_address"] is not None:
                    # standard scripts have 1 address. shared_funds requires > 1
                    if txout["script_format"] != "hash160":
                        # TODO - test this for p2sh-txout
                        raise Exception(
                            "script format %s detected" % txout["script_format"]
                        )
                    shared_funds = False
                    insert_record(
                        block_height, txhash_hex, txin_num, txout_num,
                        txout["standard_script_address"], None,
                        txout["script_format"], shared_funds, orphan_block
                    )
                # 2. for non-standard scripts, still write a row to the table
                # but do not populate the addresses yet. this row will be
                # overwritten later if the txout ever gets spent
                elif txout["script_format"] == "non-standard":
                    shared_funds = None # unknown at this stage
                    insert_record(
                        block_height, txhash_hex, txin_num, txout_num, None,
                        None, None, shared_funds, orphan_block
                    )

        # next loop through the txins
        for (tx_num, parsed_tx) in parsed_block["tx"].items():

            report_tx_num = tx_num

            # ignore the coinbase txins
            if tx_num == 0:
                continue

            txid = "%d-%d" % (block_height, tx_num)
            txhash_hex = btc_grunt.bin2hex(parsed_tx["hash"])

            # 3. this block has already been validated (guaranteed by the block
            # range) so we know that all standard txin scripts that spend
            # standard txout scripts pass checksig validation.
            for (txin_num, txin) in parsed_tx["input"].items():

                report_txin_num = txin_num
                txout_num = None
                report_txout_num = txout_num
                prev_txhash_hex = btc_grunt.bin2hex(txin["hash"])
                prev_txout_num = txin["index"]

                # sigpubkey format: OP_PUSHDATA0(73) <signature>
                # OP_PUSHDATA0(33/65) <pubkey>
                if txin["script_format"] == "sigpubkey":
                    # sigpubkeys spend hash160 txouts (OP_DUP OP_HASH160
                    # OP_PUSHDATA0(20) <hash160> OP_EQUALVERIFY OP_CHECKSIG) so
                    # if the prev txout format is hash160 then insert the
                    # addresses, otherwise get mysql to raise an error.
                    if prev_txout_records_exist(
                        prev_txhash_hex, prev_txout_num, "hash160"
                    ):
                        shared_funds = False
                        pubkey = txin["script_list"][3]
                        (uncompressed_address, compressed_address) = \
                        btc_grunt.pubkey2addresses(pubkey)
                        insert_record(
                            block_height, txhash_hex, txin_num, txout_num,
                            uncompressed_address, compressed_address, None,
                            shared_funds, orphan_block
                        )
                        continue # on to next txin
                    else:
                        # the prev txout was not in the hash160 standard format.
                        # now we must validate both scripts and extract the
                        # pubkeys that do validate
                        (parsed_tx, parsed_txid_already) = handle_non_standard(
                            txid, parsed_tx["bytes"], parsed_tx, txhash_hex,
                            tx_num, block_height, parsed_txid_already,
                            blocktime, txin_num, txout_num, block_version,
                            prev_txhash_hex, prev_txout_num, orphan_block
                        )
                        continue # on to next txin

                # scriptsig format: OP_PUSHDATA <signature>
                if txin["script_format"] == "scriptsig":
                    # scriptsigs spend pubkeys (OP_PUSHDATA0(33/65) <pubkey>
                    # OP_CHECKSIG) so if the prev txout format is pubkey then
                    # copy these addresses over to this txin. otherwise we will
                    # need to validate the scripts to get the pubkeys
                    if prev_txout_records_exist(
                        prev_txhash_hex, prev_txout_num, "pubkey"
                    ):
                        copy_txout_addresses_to_txin(
                            prev_txhash_hex, prev_txout_num, block_height,
                            txhash_hex, txin_num
                        )
                        continue # on to next txin
                    else:
                        # the prev txout was not in the pubkey standard format.
                        # now we must validate both scripts and extract the
                        # pubkeys that do validate
                        (parsed_tx, parsed_txid_already) = handle_non_standard(
                            txid, parsed_tx["bytes"], parsed_tx, txhash_hex,
                            tx_num, block_height, parsed_txid_already,
                            blocktime, txin_num, txout_num, block_version,
                            prev_txhash_hex, prev_txout_num, orphan_block
                        )
                        continue # on to next txin

                # if we get here then we have not been able to get the pubkeys
                # from the txin script or by copying them from a standard prev
                # txout. so validate the txin and txout scripts to get the 
                # pubkeys if available. if there is only one checksig then we
                # will skip it for speed, since btc-inquisitor has previously
                # validated this block
                (parsed_tx, parsed_txid_already) = handle_non_standard(
                    txid, parsed_tx["bytes"], parsed_tx, txhash_hex, tx_num,
                    block_height, parsed_txid_already, blocktime, txin_num,
                    txout_num, block_version, prev_txhash_hex, prev_txout_num,
                    orphan_block
                )
                continue # on to next txin

# mysql functions

field_data = {
    # fieldname: [default value, quote, unhex]
    "blockheight":         [None,   False, False],
    "txhash":              [None,   False, True ],
    "txin_num":            ["null", False, False],
    "txout_num":           ["null", False, False],
    "address":             ["''",   True,  False],
    "alternate_address":   ["''",   True,  False],
    "txout_script_format": ["null", True,  False],
    "shared_funds":        ["null", False, False],
    "orphan_block":        [0,      False, False]
}
fieldlist = [
    "blockheight", "txhash", "txin_num", "txout_num", "address",
    "alternate_address", "txout_script_format", "shared_funds", "orphan_block"
]
fields_str = ", ".join(fieldlist)
def insert_record(
    blockheight, txhash, txin_num, txout_num, address, alternate_address,
    txout_script_format, shared_funds, orphan_block
):
    """simple insert - not a unique record insert"""
    fields_dict = prepare_fields(locals())
    cmd = "insert into map_addresses_to_txs (%s) values (%s)" % (
        fields_str, get_values_str(fields_dict)
    )
    cursor.execute(cmd)

def get_values_str(fields_dict):
    """return a string of field values for use in insert values ()"""
    values_list = []
    # use the same order as fieldlist
    for field in fieldlist:
        values_list.append(fields_dict[field])

    return ", ".join(values_list)

def prepare_fields(_fields_dict):
    """
    - translate fields with value None to their default
    - quote the necessary fields
    - convert all values to strings
    """
    fields_dict = copy.deepcopy(_fields_dict)
    for (k, v) in fields_dict.items():

        # special case - save "non-standard" as null
        if (
            (k == "txout_script_format") and
            (v == "non-standard")
        ):
            fields_dict[k] = "null"

        # special case - save "shared-funds" as null
        elif k == "shared_funds":
            fields_dict[k] = 1 if v else 0

        # replace None with the default
        elif v is None:
            fields_dict[k] = field_data[k][0]

        # quote the field?
        elif field_data[k][1]:
            fields_dict[k] = "'%s'" % v

        # unhex the field?
        elif field_data[k][2]:
            fields_dict[k] = "unhex('%s')" % v

        fields_dict[k] = str(fields_dict[k])

    return fields_dict

while True:
    time.sleep(30) # check every 30 seconds for new tasks
    try:
        main()
    except Exception as e:
        # TODO - fix this while stepping through code
        if report_txin_num is not None:
            txin_or_txout = "txin"
            report_txin_txout_num = report_txin_num
        elif report_txout_num is not None:
            txin_or_txout = "txout"
            report_txin_txout_num = report_txout_num

        email_grunt.send(
            email_grunt.standard_error_subject,
            "error in block %d, tx %d, %s %d:<br><br>%s" % (
                report_block_height, report_tx_num, txin_or_txout,
                report_txin_txout_num, e.msg
            )
        )
        # TODO - write to logfile as well

mysql_db.close()

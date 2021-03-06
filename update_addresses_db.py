#!/usr/bin/env python2.7

"""
note: this scipt is deprecated. it has been superceeded by parse_blocks_to_db.py
and process_blocks_in_db.py


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

import MySQLdb
import btc_grunt
import mysql_grunt
import progress_meter
import copy
import json
import email_grunt

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
# precedence
cmd = """
    select details from tasklist
    where host = '%s'
    and name = 'map_addresses_to_txouts'
    and started is null
    and ended is null
    order by id desc
    limit 1
""" % mysql_params["unique_host_id"]
cmd = mysql_grunt.clean_query(cmd)
cursor.execute(cmd)
data = cursor.fetchall()
details = json.loads(data[0]["details"])
start_block = details["start_block"]
end_block = details["end_block"]

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
    loop through all transactions in the block and add them to the db.

    because transactions can spend from the same block, we need to add all the
    txouts to the db first. then when we loop through the txins the previous
    txouts will always be available as required.

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
        required_txin_info + required_txout_info + required_always
    ))
    for block_height in xrange(block_height_start, block_height_end):
        report_block_height = block_height
        progress_meter.render(
            100 * block_height / float(block_height_end),
            "parsing block %d of %d validated blocks" % (
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

def handle_non_standard(
    txid, tx_bytes, parsed_tx, txhash_hex, tx_num, block_height,
    parsed_txid_already, blocktime, txin_num, txout_num, block_version,
    prev_txhash_hex, prev_txout_num, orphan_block
):
    (parsed_tx, parsed_txid_already) = get_tx_data4validation(
        txid, tx_bytes, parsed_tx, tx_num, block_height, parsed_txid_already
    )
    valid_pubkeys = validate(
        parsed_tx, tx_num, blocktime, txin_num, block_version, block_height
    )
    num_pubkeys = len(valid_pubkeys)
    #if num_pubkeys > 1:
    #    pass # raise Exception("oooooo that's interesting")
    if num_pubkeys > 0:
        prev_txout_records = get_prev_txout_records(
            prev_txhash_hex, prev_txout_num
        )
        shared_funds = (num_pubkeys > 1)
        for pubkey in valid_pubkeys:
            # insert a new txin row per pubkey
            (uncompressed_address, compressed_address) = \
            btc_grunt.pubkey2addresses(pubkey)
            insert_record(
                block_height, txhash_hex, txin_num, txout_num,
                uncompressed_address, compressed_address, None, shared_funds,
                orphan_block
            )
            # we need to make sure the corresponding txout has either the
            # compressed or uncompressed address in it. we also require one
            # txout record per pubkey. if there is no address in the txout
            # record, then update the txout record with both the compressed and
            # uncompressed addresses. it is easiest to do this by building up an
            # array and then updating or inserting it into the db only at the
            # end.
            prev_txout_records = ensure_addresses_exist(
                prev_txout_records, uncompressed_address, compressed_address,
                shared_funds
            )

        update_or_insert_prev_txouts(prev_txout_records)

    else:
        # no pubkeys - still insert a blank txin record so we can search for
        # these types of txin scripts
        uncompressed_address = None
        compressed_address = None
        shared_funds = False
        insert_record(
            block_height, txhash_hex, txin_num, txout_num, uncompressed_address,
            compressed_address, None, shared_funds, orphan_block
        )

    return (parsed_tx, parsed_txid_already) # on to next txin

def get_tx_data4validation(
    txid, tx_bytes, parsed_tx, tx_num, block_height, parsed_txid_already
):
    if parsed_txid_already == txid:
        # already parsed the required data. no need to parse it again.
        return (parsed_tx, parsed_txid_already)

    # parse the elements of the tx required to do the checksig. also include the
    # txin elements, in case it is required for later txins
    (parsed_tx, _) = btc_grunt.tx_bin2dict(
        tx_bytes, 0, list(set(
            required_checksig_info + required_txin_info + required_always
        )), tx_num, block_height, ["rpc"]
    )
    # only parse once to avoid wasting effort
    parsed_txid_already = txid

    return (parsed_tx, parsed_txid_already)

def validate(
    parsed_tx, tx_num, blocktime, on_txin_num, block_version, block_height
):
    """
    get the prev txout script and validate it against the input txin script.
    return only the pubkeys that validate.
    """
    # automatically pass the checksig (but only if it is the final op) because
    # we have already validated this block
    skip_checksig = False # change to true after debugging
    bugs_and_all = True
    explain = True
    prev_tx0 = parsed_tx["input"][on_txin_num]["prev_txs"].values()[0]
    res = btc_grunt.verify_script(
        blocktime, parsed_tx, on_txin_num, prev_tx0, block_version,
        skip_checksig, bugs_and_all, explain
    )
    if res["status"] is not True:
        raise Exception(
            "failed to validate tx %d in block %d" % (tx_num, block_height)
        )
    valid_pubkeys = [] # init
    for (sig, sig_data) in res["sig_pubkey_statuses"].items():
        for (pubkey, sig_pubkey_status) in sig_data.items():
            if sig_pubkey_status is True:
                valid_pubkeys.append(pubkey)

    return list(set(valid_pubkeys)) # unique

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

def prev_txout_records_exist(
    prev_txhash_hex, prev_txout_num, prev_txout_script_format
):
    """
    does a previous txout in the specified format exist?

    this function performs the dual-function of checking that the previous txout
    exists in the database at all (any format), and then secondly that it is in
    the right format.

    the reason that the txout might not exist in the database is that it might
    be in the same block as the txin, and it might be lower down in the block so
    that we have not yet put the txout into the db
    
    """
    cmd = """
    select * from map_addresses_to_txs
    where
    txhash = unhex('%s') and
    txout_num = %d and
    txout_script_format = '%s' and
    orphan_block = 0
    """ % (prev_txhash_hex, prev_txout_num, prev_txout_script_format)

    cmd = mysql_grunt.clean_query(cmd)
    cursor.execute(cmd)
    return (cursor.rowcount > 0)

def copy_txout_addresses_to_txin(
    prev_txhash_hex, prev_txout_num, current_blockheight, current_txhash,
    txin_num
):
    """
    copy older record data (txout) over to newer record (txin). there will never
    be a case when there is more than one previous txout record since it is
    not possible to extract addresses/pubkeys from non-standard txout scripts
    as per #2.
    """
    # leave orphan_block at default value for txin
    orphan_block = field_data["orphan_block"][0]

    cmd = """
    insert into map_addresses_to_txs (%s)
    select %d, unhex('%s'), %d, null, address, alternate_address, null,
    shared_funds, %d
    from map_addresses_to_txs
    where txhash = unhex('%s') and txout_num = %d
    """ % (
        fields_str, current_blockheight, current_txhash, txin_num, orphan_block,
        prev_txhash_hex, prev_txout_num
    )
    cmd = mysql_grunt.clean_query(cmd)
    cursor.execute(cmd)

def get_prev_txout_records(prev_txhash_hex, prev_txout_num):
    cmd = """
    select blockheight, hex(txhash) as 'txhash', txin_num, txout_num, address,
    alternate_address, txout_script_format, cast(shared_funds as unsigned) as
    'shared_funds', cast(orphan_block as unsigned) as 'orphan_block'
    from map_addresses_to_txs
    where txhash = unhex('%s') and txout_num = %d
    """ % (prev_txhash_hex, prev_txout_num)
    cmd = mysql_grunt.clean_query(cmd)
    cursor.execute(cmd)
    data = cursor.fetchall()
    for (i, record) in enumerate(data):
        # required later to determine whether to do an update or insert using
        # this array
        data[i]["record_exists"] = True
        data[i]["shared_funds"] = bool(record["shared_funds"])
        data[i]["orphan_block"] = bool(record["orphan_block"])

    return list(data)

def ensure_addresses_exist(
    prev_txout_records, uncompressed_address, compressed_address, shared_funds
):
    """
    prev_txout_records is a dict of rows from the map_addresses_to_txs table. we
    need to make sure that at least one record contains the compressed and
    uncompressed addresses.

    assume that both uncompressed and compressed addresses are always available
    in the input arguments of this function, since the function is only called
    when the txin script pubkey is found.

    note that in the case of multisignature scripts, multiple pubkeys may exist.
    when this occurs then some records will have addresses that do not match the
    addresses input to this function. we need to be careful to keep the
    addresses from a single pubkey together in a single record and not mix the
    addresses from different pubkeys into a single record.

    note also that the same pubkey does not appear twice (ie each record has a
    different pubkey). this is still the case even if it is a multisignature
    script with the same pubkey twice or more.
    """
    if not len(prev_txout_records):
        raise Exception("prev_txout_records should not be blank")

    if (
        (not shared_funds) and
        len(prev_txout_records) > 1
    ):
        raise Exception(
            "no shared funds and more than one prev txout record? impossible."
        )

    # first make sure the shared funds flag is correct for all records (it
    # is 0 by default, so only update it if it is now 1)
    if shared_funds:
        for (i, record) in enumerate(prev_txout_records):
            if record["shared_funds"]:
                # nothing to update here. more importantly, the flag to update
                # the record should not be set
                continue

            prev_txout_records[i]["shared_funds"] = shared_funds
            # create element so we know what to update in the db
            prev_txout_records[i]["updated_shared_funds"] = True

    # first check if there is one record that has the specified addresses
    both_addresses = (uncompressed_address, compressed_address)
    for (i, record) in enumerate(prev_txout_records):

        if (
            (record["address"] in both_addresses) and
            (record["alternate_address"] in both_addresses)
        ):
            # if both addresses are found then there is nothing more to do here
            return prev_txout_records

    for (i, record) in enumerate(prev_txout_records):
        # if there are no addresses in this record then update both now and exit
        if (
            (record["address"] == "") and
            (record["alternate_address"] == "")
        ):
            prev_txout_records[i]["address"] = uncompressed_address
            prev_txout_records[i]["updated_address"] = True
            prev_txout_records[i]["alternate_address"] = compressed_address
            prev_txout_records[i]["updated_alternate_address"] = True
            return prev_txout_records

        # if there is one address then update the other

        if record["address"] == compressed_address:
            prev_txout_records[i]["alternate_address"] == uncompressed_address
            prev_txout_records[i]["updated_alternate_address"] = True
            return prev_txout_records

        if record["address"] == uncompressed_address:
            prev_txout_records[i]["alternate_address"] == compressed_address
            prev_txout_records[i]["updated_alternate_address"] = True
            return prev_txout_records

        if record["alternate_address"] == compressed_address:
            prev_txout_records[i]["address"] == uncompressed_address
            prev_txout_records[i]["updated_address"] = True
            return prev_txout_records

        if record["alternate_address"] == uncompressed_address:
            prev_txout_records[i]["address"] == compressed_address
            prev_txout_records[i]["updated_address"] = True
            return prev_txout_records

        # this record is for a different pubkey. nothing to update here

    # if we get here then there was no prev txout record for the pubkey. so copy
    # another prev txout and put this pubkey's addresses in it. note that the
    # following fields are not copied accross:
    # - record_exists
    # - updated_address
    # - updated_alternate_address
    # - updated_shared_funds
    prev_txout_records.append({k: prev_txout_records[0][k] for k in fieldlist})
    prev_txout_records[-1]["address"] = uncompressed_address
    prev_txout_records[-1]["alternate_address"] = compressed_address

    return prev_txout_records

def update_or_insert_prev_txouts(prev_txout_records):
    """
    loop through the prev txout records. insert any that don't exist and update
    those that do.
    """
    for (i, record) in enumerate(prev_txout_records):
        if (
            ("record_exists" in record) and (
                ("updated_address" in record) or
                ("updated_alternate_address" in record) or
                ("updated_shared_funds" in record)
            )
        ):
            # the record exists and has been updated (updated fields were
            # always previously blank - ie "")
            update_list = []
            where_list = []
            if "updated_address" in record:
                update_list.append("address = '%s'" % record["address"])
                where_list.append("address = ''")
            if "updated_alternate_address" in record:
                update_list.append(
                    "alternate_address = '%s'" % record["alternate_address"]
                )
                where_list.append("alternate_address = ''")
            if "updated_shared_funds" in record:
                update_list.append("shared_funds = 1")
                where_list.append("shared_funds = 0")

            update_str = ", ".join(update_list)
            where_str = " and ".join(where_list)

            cmd = """
            update map_addresses_to_txs
            set %s
            where
            txhash = unhex('%s') and
            txout_num = %d and
            %s
            limit 1
            """ % (update_str, record["txhash"], record["txout_num"], where_str)
            cmd = mysql_grunt.clean_query(cmd)
            cursor.execute(cmd)

        elif "record_exists" not in record:
            # this is a new record - insert it
            insert_record(
                record["blockheight"], record["txhash"], record["txin_num"],
                record["txout_num"], record["address"],
                record["alternate_address"], record["txout_script_format"],
                record["shared_funds"], record["orphan_block"]
            )

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

try:
    main()
except Exception as e:
    if report_txin_num is not None:
        txin_or_txout = "txin"
        report_txin_txout_num = report_txin_num
    elif report_txout_num is not None:
        txin_or_txout = "txout"
        report_txin_txout_num = report_txout_num

    email_grunt.send(
        "update_addresses_db.py error on optiplex745",
        "error in block %d, tx %d, %s %d:<br><br>%s" % (
            report_block_height, report_tx_num, txin_or_txout,
            report_txin_txout_num, e.msg
        )
    )
    # TODO - write to logfile as well

mysql_db.close()

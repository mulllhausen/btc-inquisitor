#!/usr/bin/env python2.7

# in all queries we return hex instead of bin in case bin gives bad data

def set_autocommit(on):
    mysql_grunt.cursor.execute("set autocommit = %s", 1 if on else 0)

def set_innodb_indexes(on):
    mysql_grunt.cursor.execute("set unique_checks = %s", 1 if on else 0)
    mysql_grunt.cursor.execute("set foreign_key_checks = %s", 1 if on else 0)

def begin_operations():
    mysql_grunt.cursor.execute("start transaction")

def commit_operations():
    mysql_grunt.cursor.execute("commit")

def insert_block_header(
    block_height, block_hash, previous_block_hash, block_version, merkle_root,
    block_timestamp, block_bits, nonce, size, num_txs
):
    mysql_grunt.cursor.execute("""
        insert into blockchain_headers set
        block_height = %s,
        block_hash = unhex(%s),
        previous_block_hash = unhex(%s),
        version = %s,
        merkle_root = unhex(%s),
        timestamp = %s,
        bits = unhex(%s),
        nonce = %s,
        block_size = %s,
        num_txs = %s
    """, (
        block_height, block_hash, previous_block_hash, block_version,
        merkle_root, block_timestamp, block_bits, nonce, size, num_txs
    ))

def insert_tx_header(
    block_height, block_hash, tx_num, tx_hash, tx_version, num_inputs,
    num_outputs, tx_lock_time, tx_size, tx_change
):
    mysql_grunt.cursor.execute("""
        insert into blockchain_txs set
        block_height = %s,
        block_hash = unhex(%s),
        tx_num = %s,
        tx_hash = unhex(%s),
        tx_version = %s,
        num_txins = %s,
        num_txouts = %s,
        tx_lock_time = %s,
        tx_size = %s,
        tx_change = %s
    """, (
        block_height, block_hash, tx_num, tx_hash, tx_version, num_inputs,
        num_outputs, tx_lock_time, tx_size, tx_change
    ))

def insert_txin(
    block_height, tx_hash, txin_num, txin_hash, txin_index, txin_script_length,
    txin_script, txin_script_format, txin_sequence_num, txin_funds,
    coinbase_change_funds
):
    mysql_grunt.cursor.execute("""
        insert into blockchain_txins set
        block_height = %s,
        tx_hash = unhex(%s),
        txin_num = %s,
        prev_txout_hash = unhex(%s),
        prev_txout_num = %s,
        script_length = %s,
        script = unhex(%s),
        script_format = %s,
        txin_sequence_num = %s,
        funds = %s,
        txin_coinbase_change_funds = %s
    """, (
        block_height, tx_hash, txin_num, txin_hash, txin_index,
        txin_script_length, txin_script, txin_script_format, txin_sequence_num,
        txin_funds, coinbase_change_funds
    ))

def insert_txout(
    block_height, tx_hash, txout_num, txout_funds, txout_script_length,
    txout_script, txout_script_format, pubkey, txout_standard_script_address
):
    mysql_grunt.cursor.execute("""
        insert into blockchain_txouts set
        block_height = %s,
        tx_hash = unhex(%s),
        txout_num = %s,
        funds = %s,
        script_length = %s,
        script = unhex(%s),
        script_format = %s,
        pubkey = unhex(%s),
        address = %s
    """, (
        block_height, tx_hash, txout_num, txout_funds, txout_script_length,
        txout_script, txout_script_format, pubkey, txout_standard_script_address
    ))

def get_top_block_by_block_header():
    return mysql_grunt.quick_fetch("""
        select block_height
        from blockchain_headers
        order by block_height desc
        limit 0,1
    """)[0]["block_height"]

def get_top_block_by_tx_header():
    return mysql_grunt.quick_fetch("""
        select block_height
        from blockchain_txs
        order by block_height desc
        limit 0,1
    """)[0]["block_height"]

def get_top_block_by_txout():
    return mysql_grunt.quick_fetch("""
        select block_height
        from blockchain_txouts
        order by block_height desc
        limit 0,1
    """)[0]["block_height"]

def get_top_block_by_txin():
    return mysql_grunt.quick_fetch("""
        select block_height
        from blockchain_txins
        order by block_height desc
        limit 0,1
    """)[0]["block_height"]

def delete_block_range(block_height_start, block_height_end):
    mysql_grunt.cursor.execute("""
        delete from blockchain_headers
        where
        block_height >= %s
        and block_height <= %s
    """, (block_height_start, block_height_end))

    mysql_grunt.cursor.execute("""
        delete from blockchain_txs
        where
        block_height >= %s
        and block_height <= %s
    """, (block_height_start, block_height_end))

    mysql_grunt.cursor.execute("""
        delete from blockchain_txins
        where
        block_height >= %s
        and block_height <= %s
    """, (block_height_start, block_height_end))

    mysql_grunt.cursor.execute("""
        delete from blockchain_txouts
        where
        block_height >= %s
        and block_height <= %s
    """, (block_height_start, block_height_end))

def get_blockchain_data_query(where, required_info):
    """
    get the specified blockchain data (specified by required_info), including
    block header data, transaction data, txin data and/or txout data. this query
    is designed to be as efficienty as possible. as few joins as possible are
    used, depending on required_info and the where clause data.
    """
    if not len(required_info):
        raise ValueError("required_info is empty")

    tables = [] # list of tables used
    header_fields = {}
    tx_fields = {}
    txin_fields = {}
    txout_fields = {}

    if "block_height" in required_info:
        header_fields["block_height"] = "h.block_height"

    if "block_hash" in required_info:
        header_fields["block_hash_hex"] = "hex(h.block_hash)"

    if "previous_block_hash" in required_info:
        header_fields["prev_block_hash_hex"] = "hex(h.previous_block_hash)"

    if "version" in required_info:
        header_fields["block_version"] = "h.version"

    if "merkle_root" in required_info:
        header_fields["merkle_root_hex"] = "hex(h.merkle_root)"

    if "timestamp" in required_info:
        header_fields["block_time"] = "h.timestamp"

    if "bits" in required_info:
        header_fields["bits_hex"] = "hex(h.bits)"

    if "nonce" in required_info:
        header_fields["nonce"] = "h.nonce"

    if "block_size" in required_info:
        header_fields["block_size"] = "h.block_size"

    if "orphan_status" in required_info:
        header_fields["block_orphan_status"] = "h.orphan_status"

    if "merkle_root_validation_status" in required_info:
        header_fields["merkle_root_validation_status"] = \
        "h.merkle_root_validation_status"

    if "bits_validation_status" in required_info:
        header_fields["bits_validation_status"] = "h.bits_validation_status"

    if "difficulty_validation_status" in required_info:
        header_fields["difficulty_validation_status"] = \
        "h.difficulty_validation_status"

    if "block_hash_validation_status" in required_info:
        header_fields["block_hash_validation_status"] = \
        "h.block_hash_validation_status"

    if "block_size_validation_status" in required_info:
        header_fields["block_size_validation_status"] = \
        "h.block_size_validation_status"

    if "block_version_validation_status" in required_info:
        header_fields["block_version_validation_status"] = \
        "h.block_version_validation_status"

    if "num_txs" in required_info:
        header_fields["num_txs"] = "h.num_txs"

    if "tx_hash" in required_info:
        tx_fields["tx_hash_hex"] = "hex(t.tx_hash)"

    if "tx_version" in required_info:
        tx_fields["tx_version"] = "t.tx_version"

    if "num_tx_inputs" in required_info:
        tx_fields["num_txins"] = "t.num_txins"

    if "num_tx_outputs" in required_info:
        tx_fields["num_txouts"] = "t.num_txouts"

    if "tx_lock_time" in required_info:
        tx_fields["tx_lock_time"] = "t.tx_lock_time"

    if "tx_size" in required_info:
        tx_fields["tx_size"] = "t.tx_size"

    if "tx_change" in required_info:
        tx_fields["tx_change"] = "t.tx_change"

    if "tx_lock_time_validation_status" in required_info:
        tx_fields["tx_lock_time_validation_status"] = \
        "t.tx_lock_time_validation_status"

    if "tx_funds_balance_validation_status" in required_info:
        tx_fields["tx_funds_balance_validation_status"] = \
        "t.tx_funds_balance_validation_status"

    if "tx_pubkey_to_address_validation_status" in required_info:
        tx_fields["tx_pubkey_to_address_validation_status"] = \
        "t.tx_pubkey_to_address_validation_status"

    if "txin_num" in required_info:
        txin_fields["txin_num"] = {"txin": "txin.txin_num", "txout": 0}
        tables.append("blockchain_txins")

    if "txin_address" in required_info:
        txin_fields["txin_address"] = {
            "txin": "txin.address",
            "txout": "''"
        }
        tables.append("blockchain_txins")

    if "txin_alternate_address" in required_info:
        txin_fields["txin_alternate_address"] = {
            "txin": "txin.alternate_address",
            "txout": "''"
        }
        tables.append("blockchain_txins")

    if "txin_funds" in required_info:
        txin_fields["txin_funds"] = {"txin": "txin.funds", "txout": 0}
        tables.append("blockchain_txins")

    if "prev_txout_hash" in required_info:
        txin_fields["prev_txout_hash_hex"] = {
            "txin": "hex(txin.prev_txout_hash)",
            "txout": "''"
        }
        tables.append("prev_txout")

    if "prev_txout_num" in required_info:
        txin_fields["prev_txout_num"] = {
            "txin": "txin.prev_txout_num",
            "txout": 0
        }
        tables.append("prev_txout")

    if "txin_hash_validation_status" in required_info:
        txin_fields["txin_hash_validation_status"] = {
            "txin": "txin.txin_hash_validation_status",
            "txout": "''"
        }
        tables.append("blockchain_txins")

    if "txin_index_validation_status" in required_info:
        txin_fields["txin_index_validation_status"] = {
            "txin": "txin.txin_index_validation_status",
            "txout": "''"
        }
        tables.append("blockchain_txins")

    if "txin_mature_coinbase_spend_validation_status" in required_info:
        txin_fields["txin_mature_coinbase_spend_validation_status"] = {
            "txin": "txin.txin_mature_coinbase_spend_validation_status",
            "txout": "''"
        }
        tables.append("blockchain_txins")

    if "txin_script" in required_info:
        txin_fields["txin_script_hex"] = {
            "txin": "hex(txin.script)",
            "txout": "''"
        }
        tables.append("blockchain_txins")

    if "txin_script_format" in required_info:
        txin_fields["txin_script_format"] = {
            "txin": "txin.script_format",
            "txout": "''"
        }
        tables.append("blockchain_txins")

    if "txin_script_length" in required_info:
        txin_fields["txin_script_length"] = {
            "txin": "txin.script_length",
            "txout": 0
        }
        tables.append("blockchain_txins")

    if "prev_txout_script" in required_info:
        txin_fields["prev_txout_script_hex"] = {
            "txin": "hex(prev_txout.script)",
            "txout": "''"
        }
        tables.append("prev_txout")

    if "prev_txout_script_format" in required_info:
        txin_fields["prev_txout_script_format"] = {
            "txin": "prev_txout.script_format",
            "txout": "''"
        }
        tables.append("prev_txout")

    if "prev_txout_script_length" in required_info:
        txin_fields["prev_txout_script_length"] = {
            "txin": "prev_txout.script_length",
            "txout": 0
        }
        tables.append("prev_txout")

    if "prev_txout_pubkey" in required_info:
        txin_fields["prev_txout_pubkey"] = {
            "txin": "prev_txout.pubkey",
            "txout": "''"
        }
        tables.append("prev_txout")

    if "prev_txout_address" in required_info:
        txin_fields["prev_txout_address"] = {
            "txin": "prev_txout.address",
            "txout": "''"
        }
        tables.append("prev_txout")

    if "prev_txout_alternate_address" in required_info:
        txin_fields["prev_txout_alternate_address"] = {
            "txin": "prev_txout.alternate_address",
            "txout": "''"
        }
        tables.append("prev_txout")

    if "txin_sequence_num" in required_info:
        txin_fields["txin_sequence_num"] = {
            "txin": "txin.txin_sequence_num",
            "txout": 0
        }
        tables.append("blockchain_txins")

    if "txin_single_spend_validation_status" in required_info:
        txin_fields["txin_single_spend_validation_status"] = {
            "txin": "txin.txin_single_spend_validation_status",
            "txout": "''"
        }
        tables.append("blockchain_txins")

    if "txin_spend_from_non_orphan_validation_status" in required_info:
        txin_fields["txin_spend_from_non_orphan_validation_status"] = {
            "txin": "txin.txin_spend_from_non_orphan_validation_status",
            "txout": "''"
        }
        tables.append("blockchain_txins")

    if "txin_checksig_validation_status" in required_info:
        txin_fields["txin_checksig_validation_status"] = {
            "txin": "txin.txin_checksig_validation_status",
            "txout": "''"
        }
        tables.append("blockchain_txins")

    if "txout_num" in required_info:
        txout_fields["txout_num"] = {"txout": "txout.txout_num", "txin": 0}

    if "txout_address" in required_info:
        txout_fields["txout_address"] = {
            "txout": "txout.address",
            "txin": "''"
        }

    if "txout_funds" in required_info:
        txout_fields["txout_funds"] = {"txout": "txout.funds", "txin": 0}

    if "txout_alternate_address" in required_info:
        txout_fields["txout_alternate_address"] = {
            "txout": "txout.alternate_address",
            "txin": "''"
        }

    if "txout_pubkey_hex" in required_info:
        txout_fields["txout_pubkey_hex"] = {
            "txout": "hex(txout.pubkey)",
            "txin": "''"
        }

    if "txout_pubkey_to_address_validation_status" in required_info:
        txout_fields["txout_pubkey_to_address_validation_status"] = {
            "txout": "txout.pubkey_to_address_validation_status",
            "txin": "''"
        }

    if "txout_script_hex" in required_info:
        txout_fields["txout_script_hex"] = {
            "txout": "hex(txout.script)",
            "txin": "''"
        }

    if "txout_script_format" in required_info:
        txout_fields["txout_script_format"] = {
            "txout": "txout.script_format",
            "txin": "''"
        }

    if "txout_script_length" in required_info:
        txout_fields["txout_script_length"] = {
            "txout": "txout.script_length",
            "txin": 0
        }

    if "txout_shared_funds" in required_info:
        txout_fields["txout_shared_funds"] = {
            "txout": "txout.shared_funds",
            "txin": "''"
        }

    if "standard_script_address_checksum_validation_status" in required_info:
        txout_fields["standard_script_address_checksum_validation_status"] = {
            "txout": "txout.standard_script_address_checksum_validation_status",
            "txin": "''"
        }

    if "txout_change_calculated" in required_info:
        txout_fields["txout_change_calculated"] = {
            "txout": "txout.tx_change_calculated",
            "txin": "''"
        }

    if (txin_fields != {}) or (txout_fields != {}):
        tx_fields["tx_num"] = "t.tx_num"

    tables = []

    # build the string of fields for the query
    fieldslist = ""

    if header_fields != {}:
        fieldslist += ",".join(
            field + " as '" + name + "'" for (name, field) in \
            header_fields.items()
        )
        tables.append("blockchain_headers")

    if tx_fields != {}:
        if header_fields != {}:
            fieldslist += ","

        fieldslist += ",".join(
            field + " as '" + name + "'" for (name, field) in tx_fields.items()
        )
        tables.append("blockchain_txs")

    if txin_fields != {}:
        if (header_fields != {}) or (tx_fields != {}):
            fieldslist += ","

        fieldslist += ",".join(
            field["txin"] + " as '" + name + "'" for (name, field) in \
            txin_fields.items()
        )
        # tables.append("blockchain_txins") # this is not defined here - it is
        # defined earlier because it could be either exin or prev_txout

    if txout_fields != {}:
        if (header_fields != {}) or (tx_fields != {}) or (txin_fields != {}):
            fieldslist += ","

        fieldslist += ",".join(
            field["txout"] + " as '" + name + "'" for (name, field) in \
            txout_fields.items()
        )
        tables.append("blockchain_txouts")

    # build the whereclause for the query
    # todo - 2 whereclauses - one for each query in the union
    whereclause = ""

    if "block_hash" in where:
        if header_fields != {}:
            block_hash_field = "h.block_hash"
            tables.append("blockchain_headers")
        elif (tx_fields != {}) or (txin_fields != {}) or (txout_fields != {}):
            block_hash_field = "t.block_hash"
            tables.append("blockchain_txs")

        whereclause += "%s = unhex(%s)" % (
            block_hash_field, where["block_hash"]
        )

    if "block_height" in where:
        if header_fields != {}:
            block_height_field = "h.block_height"
            tables.append("blockchain_height")
        elif tx_fields != {}:
            block_height_field = "t.block_height"
            tables.append("blockchain_txs")
        elif txin_fields != {}:
            block_height_field = "txin.block_height"
            # tables.append("blockchain_txins") # this is not defined here - it
            # is defined earlier because it could be either exin or prev_txout
        elif txout_fields != {}:
            block_height_field = "txout.block_height"
            tables.append("blockchain_txouts")

        whereclause += "%s >= %d and %s <= %d" % (
            block_height_field, block_height_field,
            where["block_height"]["start"], where["block_height"]["end"]
        )

    if "tx_hash" in where:
        if header_fields != {}:
            tx_hash_field = "h.tx_hash"
            tables.append("blockchain_headers")
        elif tx_fields != {}:
            tx_hash_field = "t.tx_hash"
            tables.append("blockchain_txs")
        elif txin_fields != {}:
            tx_hash_field = "txin.tx_hash"
            # tables.append("blockchain_txins") # this is not defined here - it
            # is defined earlier because it could be either exin or prev_txout
        elif txout_fields != {}:
            tx_hash_field = "txout.tx_hash"
            tables.append("blockchain_txouts")

        whereclause += "%s = unhex(%s)" % (tx_hash_field, where["tx_hash"])

    if "tx_nums" in where:
        whereclause += "t.tx_num in (%s)" % ",".join(where["tx_nums"])
        tables.append("blockchain_txs")

    # build the from-clause
    fromclause1 = ""
    fromclause2 = ""

    if "blockchain_headers" in tables:
        fromclause1 += "from blockchain_headers h"

    if "blockchain_txs" in tables:
        if fromclause1 == "":
            fromclause1 += "from blockchain_headers h"
        else:
            fromclause1 += " inner join blockchain_txs t on " \
            "t.block_hash = h.block_hash"

    if ("blockchain_txins" in tables) or ("prev_txout" in tables):
        if fromclause1 == "":
            fromclause1 += "from blockchain_txins txin"
        else:
            fromclause1 += " inner join blockchain_txins txin on"

            if "blockchain_txs" in tables:
                fromclause1 += " txin.tx_hash = t.tx_hash"
            elif "blockchain_headers" in tables:
                fromclause1 += " txin.tx_height = h.block_height"

    if "prev_txout" in tables:
        fromclause1 += """ left join blockchain_txouts prev_txout on (
            txin.prev_txout_hash = prev_txout.tx_hash and 
            txin.prev_txout_num = prev_txout.txout_num
        )"""

    if "blockchain_txouts" in tables:
        if fromclause1 == "":
            fromclause2 = "from blockchain_txouts txout"
        else:
            fromclause2 = fromclause1 + " inner join blockchain_txouts txout on"

            if "blockchain_txs" in tables:
                fromclause2 += " txout.tx_hash = t.tx_hash"
            elif "blockchain_headers" in tables:
                fromclause2 += " txout.tx_height = h.block_height"

    # put everything together into a query
    query = ""
    if fromclause1 != "":
        query = "select %s %s where %s" % (fieldslist, fromclause1, whereclause)

    if (fromclause1 != "") and (fromclause2 != ""):
        query += " union all "

    if fromclause2 != "":
        query += "select %s %s where %s" % (fieldslist, fromclause2, whereclause)

    return query.strip()

def get_blockchain_data(where, required_info):
    return mysql_grunt.quick_fetch(
        get_blockchain_data_query(where, required_info)
    )

def get_tx_header(input_arg_format, data, required_info):
    if not len(required_info):
        raise ValueError("required_info is empty")

    header_fields = {}
    tx_fields = {}

    if "block_height" in required_info:
        header_fields["block_height"] = "h.block_height"

    if "block_hash" in required_info:
        header_fields["block_hash_hex"] = "hex(h.block_hash)"

    if "previous_block_hash" in required_info:
        header_fields["prev_block_hash_hex"] = "hex(h.previous_block_hash)"

    if "version" in required_info:
        header_fields["block_version"] = "h.version"

    if "merkle_root" in required_info:
        header_fields["merkle_root_hex"] = "hex(h.merkle_root)"

    if "timestamp" in required_info:
        header_fields["block_time"] = "h.timestamp"

    if "bits" in required_info:
        header_fields["bits_hex"] = "hex(h.bits)"

    if "nonce" in required_info:
        header_fields["nonce"] = "h.nonce"

    if "block_size" in required_info:
        header_fields["block_size"] = "h.block_size"

    if "orphan_status" in required_info:
        header_fields["block_orphan_status"] = "h.orphan_status"

    if "merkle_root_validation_status" in required_info:
        header_fields["merkle_root_validation_status"] = \
        "h.merkle_root_validation_status"

    if "bits_validation_status" in required_info:
        header_fields["bits_validation_status"] = "h.bits_validation_status"

    if "difficulty_validation_status" in required_info:
        header_fields["difficulty_validation_status"] = \
        "h.difficulty_validation_status"

    if "block_hash_validation_status" in required_info:
        header_fields["block_hash_validation_status"] = \
        "h.block_hash_validation_status"

    if "block_size_validation_status" in required_info:
        header_fields["block_size_validation_status"] = \
        "h.block_size_validation_status"

    if "block_version_validation_status" in required_info:
        header_fields["block_version_validation_status"] = \
        "h.block_version_validation_status"

    if "num_txs" in required_info:
        header_fields["num_txs"] = "h.num_txs"

    if "tx_hash" in required_info:
        tx_fields["tx_hash_hex"] = "hex(t.tx_hash)"

    if "tx_version" in required_info:
        tx_fields["tx_version"] = "t.tx_version"

    if "num_tx_inputs" in required_info:
        tx_fields["num_txins"] = "t.num_txins"

    if "num_tx_outputs" in required_info:
        tx_fields["num_txouts"] = "t.num_txouts"

    if "tx_lock_time" in required_info:
        tx_fields["tx_lock_time"] = "t.tx_lock_time"

    if "tx_size" in required_info:
        tx_fields["tx_size"] = "t.tx_size"

    if "tx_change" in required_info:
        tx_fields["tx_change"] = "t.tx_change"

    if "tx_lock_time_validation_status" in required_info:
        tx_fields["tx_lock_time_validation_status"] = \
        "t.tx_lock_time_validation_status"

    if "tx_funds_balance_validation_status" in required_info:
        tx_fields["tx_funds_balance_validation_status"] = \
        "t.tx_funds_balance_validation_status"

    if "tx_pubkey_to_address_validation_status" in required_info:
        tx_fields["tx_pubkey_to_address_validation_status"] = \
        "t.tx_pubkey_to_address_validation_status"

    # mandatory fields
    tx_fields["tx_num"] = "t.tx_num"

    query = "select "

    if len(header_fields):
        query += ",".join(
            field + " as '" + name + "'" for (field, name) in header_fields
        )

    if len(tx_fields):
        if len(header_fields):
            query += ","

        query += ",".join(
            field + " as '" + name + "'" for (field, name) in tx_fields
        )

    if input_arg_format in ["blockheight-txnum", "txhash"]:
        query += " from blockchain_txs t"

        if len(header_fields):
            query += " inner join blockchain_headers h " \
            "on h.block_hash = t.block_hash"

    elif input_arg_format in ["blockheight", "blockhash"]:
        query += " from blockchain_headers h"

        if len(tx_fields):
            query += " inner join blockchain_txs t " \
            "on t.block_hash = h.block_hash"

    query += " where"

    if input_arg_format == "blockheight-txnum":
        query += """
        t.block_height = %s and
        t.tx_num = %s
        """
        return mysql_grunt.quick_fetch(query, data)[0]

    elif input_arg_format == "txhash":
        query += " t.tx_hash = unhex(%s)"
        return mysql_grunt.quick_fetch(query, data)[0]

    elif input_arg_format == "blockheight":
        query += " h.block_height = %s"
        return mysql_grunt.quick_fetch(query, data)

    elif input_arg_format == "blockhash":
        query += " h.block_hash = unhex(%s)"
        return mysql_grunt.quick_fetch(query, data)

def get_txins_and_txouts(tx_hash_hex, required_info):
    if not len(required_info):
        raise ValueError("required_info is empty")

    fields = {}

    if "txin_num" in required_info:
        fields["txin_num"] = {"txin": "txin.txin_num", "txout": 0}

    if "txin_address" in required_info:
        fields["txin_address"] = {"txin": "txin.address", "txout": "''"}

    if "txin_alternate_address" in required_info:
        fields["txin_alternate_address"] = {
            "txin": "txin.alternate_address",
            "txout": "''"
        }

    if "txin_funds" in required_info:
        fields["txin_funds"] = {"txin": "txin.funds", "txout": 0}

    if "prev_txout_hash" in required_info:
        fields["prev_txout_hash_hex"] = {
            "txin": "hex(txin.prev_txout_hash)",
            "txout": "''"
        }

    if "prev_txout_num" in required_info:
        fields["prev_txout_num"] = {"txin": "txin.prev_txout_num", "txout": 0}

    if "txin_hash_validation_status" in required_info:
        fields["txin_hash_validation_status"] = {
            "txin": "txin.txin_hash_validation_status",
            "txout": "''"
        }

    if "txin_index_validation_status" in required_info:
        fields["txin_index_validation_status"] = {
            "txin": "txin.txin_index_validation_status",
            "txout": "''"
        }

    if "txin_mature_coinbase_spend_validation_status" in required_info:
        fields["txin_mature_coinbase_spend_validation_status"] = {
            "txin": "txin.txin_mature_coinbase_spend_validation_status",
            "txout": "''"
        }

    if "txin_script" in required_info:
        fields["txin_script_hex"] = {"txin": "hex(txin.script)", "txout": "''"}

    if "txin_script_format" in required_info:
        fields["txin_script_format"] = {
            "txin": "txin.script_format",
            "txout": "''"
        }

    if "txin_script_length" in required_info:
        fields["txin_script_length"] = {
            "txin": "txin.script_length",
            "txout": 0
        }

    if "prev_txout_script" in required_info:
        fields["prev_txout_script_hex"] = {
            "txin": "hex(prev_txout.script)",
            "txout": "''"
        }

    if "prev_txout_script_format" in required_info:
        fields["prev_txout_script_format"] = {
            "txin": "prev_txout.script_format",
            "txout": "''"
        }

    if "prev_txout_script_length" in required_info:
        fields["prev_txout_script_length"] = {
            "txin": "prev_txout.script_length",
            "txout": 0
        }

    if "prev_txout_pubkey" in required_info:
        fields["prev_txout_pubkey"] = {
            "txin": "prev_txout.pubkey",
            "txout": "''"
        }

    if "prev_txout_address" in required_info:
        fields["prev_txout_address"] = {
            "txin": "prev_txout.address",
            "txout": "''"
        }

    if "prev_txout_alternate_address" in required_info:
        fields["prev_txout_alternate_address"] = {
            "txin": "prev_txout.alternate_address",
            "txout": "''"
        }

    if "txin_sequence_num" in required_info:
        fields["txin_sequence_num"] = {
            "txin": "txin.txin_sequence_num",
            "txout": 0
        }

    if "txin_single_spend_validation_status" in required_info:
        fields["txin_single_spend_validation_status"] = {
            "txin": "txin.txin_single_spend_validation_status",
            "txout": "''"
        }

    if "txin_spend_from_non_orphan_validation_status" in required_info:
        fields["txin_spend_from_non_orphan_validation_status"] = {
            "txin": "txin.txin_spend_from_non_orphan_validation_status",
            "txout": "''"
        }

    if "txin_checksig_validation_status" in required_info:
        fields["txin_checksig_validation_status"] = {
            "txin": "txin.txin_checksig_validation_status",
            "txout": "''"
        }

    if "txout_num" in required_info:
        fields["txout_num"] = {"txout": "txout.txout_num", "txin": 0}

    if "txout_address" in required_info:
        fields["txout_address"] = {"txout": "txout.address", "txin": "''"}

    if "txout_funds" in required_info:
        fields["txout_funds"] = {"txout": "txout.funds", "txin": 0}

    if "txout_alternate_address" in required_info:
        fields["txout_alternate_address"] = {
            "txout": "txout.alternate_address",
            "txin": "''"
        }

    if "txout_pubkey_hex" in required_info:
        fields["txout_pubkey_hex"] = {
            "txout": "hex(txout.pubkey)",
            "txin": "''"
        }

    if "txout_pubkey_to_address_validation_status" in required_info:
        fields["txout_pubkey_to_address_validation_status"] = {
            "txout": "txout.pubkey_to_address_validation_status",
            "txin": "''"
        }

    if "txout_script_hex" in required_info:
        fields["txout_script_hex"] = {
            "txout": "hex(txout.script)",
            "txin": "''"
        }

    if "txout_script_format" in required_info:
        fields["txout_script_format"] = {
            "txout": "txout.script_format",
            "txin": "''"
        }

    if "txout_script_length" in required_info:
        fields["txout_script_length"] = {
            "txout": "txout.script_length",
            "txin": 0
        }

    if "txout_shared_funds" in required_info:
        fields["txout_shared_funds"] = {
            "txout": "txout.shared_funds",
            "txin": "''"
        }

    if "standard_script_address_checksum_validation_status" in required_info:
        fields["standard_script_address_checksum_validation_status"] = {
            "txout": "txout.standard_script_address_checksum_validation_status",
            "txin": "''"
        }

    if "txout_change_calculated" in required_info:
        fields["txout_change_calculated"] = {
            "txout": "txout.tx_change_calculated",
            "txin": "''"
        }

    query = "select 'txin' as 'type'," + ",".join(
        field_data["txin"] + " as '" + field_name + "'" for \
        (field_name, field_data) in fields.items()
    ) + """

    from blockchain_txins txin
    left join blockchain_txouts prev_txout on (
        txin.prev_txout_hash = prev_txout.tx_hash and 
        txin.prev_txout_num = prev_txout.txout_num
    )
    where
    txin.tx_hash = unhex(%s)

    union all

    select
    'txout' as 'type',
    txout.txout_num as 'txout_num',
    txout.address as 'txout_address',
    txout.funds as 'txout_funds',
    txout.alternate_address as 'txout_alternate_address',
    hex(txout.pubkey) as 'txout_pubkey_hex',

    txout.pubkey_to_address_validation_status as
    'txout_pubkey_to_address_validation_status',

    hex(txout.script) as 'txout_script_hex',
    txout.script_format as 'txout_script_format',
    txout.script_length as 'txout_script_length',
    txout.shared_funds as 'txout_shared_funds',

    txout.standard_script_address_checksum_validation_status as
    'standard_script_address_checksum_validation_status',

    txout.tx_change_calculated as 'txout_change_calculated'
    from blockchain_txouts txout
    where
    txout.tx_hash = unhex(%s)
    """
    return mysql_grunt.quick_fetch(query, (tx_hash_hex, tx_hash_hex))

def update_txin_funds_from_prev_txout_funds(
    block_height_start, block_height_end
):
    mysql_grunt.cursor.execute("""
        update blockchain_txins txin
        inner join blockchain_txouts txout on (
            txin.prev_txout_hash = txout.tx_hash
            and txin.prev_txout_num = txout.txout_num
        )
        set txin.funds = txout.funds
        where txin.funds is null
        and txin.block_height >= %s
        and txin.block_height < %s
    """, (block_height_start, block_height_end))
    return mysql_grunt.cursor.rowcount

def update_txin_change_from_prev_txout_funds(
    block_height_start, block_height_end
):
    mysql_grunt.cursor.execute("""
        update blockchain_txs tx
        inner join (
            select sum(funds) as txins_total, tx_hash
            from blockchain_txins
            where tx_change_calculated = false
            and block_height >= %s
            and block_height < %s
            group by tx_hash
        ) txin on tx.tx_hash = txin.tx_hash
        inner join (
            select sum(funds) as txouts_total, tx_hash
            from blockchain_txouts
            where tx_change_calculated = false
            and block_height >= %s
            and block_height < %s
            group by tx_hash
        ) txout on tx.tx_hash = txout.tx_hash
        set tx.tx_change = (txin.txins_total - txout.txouts_total)
        where tx.tx_change is null
        and tx.tx_num != 0
        and tx.block_height >= %s
        and tx.block_height < %s
    """, (block_height_start, block_height_end) * 3)
    return mysql_grunt.cursor.rowcount

def update_txin_change_calculated_flag(block_height_start, block_height_end):
    mysql_grunt.cursor.execute("""
        update blockchain_txins
        set tx_change_calculated = true
        where block_height >= %s
        and block_height < %s
    """, (block_height_start, block_height_end))
    return mysql_grunt.cursor.rowcount

def update_txout_change_calculated_flag(block_height_start, block_height_end):
    mysql_grunt.cursor.execute("""
        update blockchain_txouts
        set tx_change_calculated = true
        where block_height >= %s
        and block_height < %s
    """, (block_height_start, block_height_end))
    return mysql_grunt.cursor.rowcount

def update_coinbase_change_funds(block_height_start, block_height_end):
    mysql_grunt.cursor.execute("""
        update blockchain_txins txin
        inner join (
            select sum(tx_totals.tx_change) as total_change, tx0.tx_hash
            from blockchain_txs tx_totals
            inner join blockchain_txs tx0 on (
                tx0.block_hash = tx_totals.block_hash
                and tx0.tx_num = 0
            )
            where tx_totals.tx_num != 0
            and tx_totals.block_height >= %s
            and tx_totals.block_height < %s
            group by tx_totals.block_hash
        ) block on block.tx_hash = txin.tx_hash
        set txin.txin_coinbase_change_funds = block.total_change
        where txin.txin_num = 0
        and txin.txin_coinbase_change_funds is null
    """, (block_height_start, block_height_end))
    return mysql_grunt.cursor.rowcount

def get_pubkeys_with_uncalculated_addresses(
    block_height_start, block_height_end
):
    return mysql_grunt.quick_fetch("""
        select hex(pubkey) as pubkey_hex
        from blockchain_txouts
        where (
            address is null
            or alternate_address is null
        )
        and block_height >= %s
        and block_height < %s
        and pubkey is not null
        group by pubkey
    """, (block_height_start, block_height_end))

def update_txin_addresses_from_pubkey(
    uncompressed_address, compressed_address, pubkey_hex
):
    mysql_grunt.cursor.execute("""
        update blockchain_txouts
        set address = %s,
        alternate_address = %s
        where pubkey = unhex(%s)
    """, (uncompressed_address, compressed_address, pubkey_hex))
    return mysql_grunt.cursor.rowcount

def update_txin_addresses_from_prev_txout_addresses(
    block_height_start, block_height_end
):
    mysql_grunt.cursor.execute("""
        update blockchain_txins txin
        inner join blockchain_txouts txout on (
            txin.prev_txout_hash = txout.tx_hash
            and txin.prev_txout_num = txout.txout_num
        )
        set txin.address = txout.address,
        txin.alternate_address = txout.alternate_address
        where (
            txin.address is null
            or txin.alternate_address is null
        )
        and txin.block_height >= %s
        and txin.block_height < %s
    """, (block_height_start, block_height_end))
    return mysql_grunt.cursor.rowcount

def get_blocks_with_merkle_root_status(
    validated, block_height_start, block_height_end
):
    query = """select block_height
    from blockchain_headers
    where block_height >= %s
    and block_height < %s
    """

    if validated is None:
        query += "and merkle_root_validation_status is null"
    elif validated == True:
        query += "and merkle_root_validation_status = 1"
    elif validated == False:
        query += "and merkle_root_validation_status = 0"
    elif validated == "set":
        query += "and merkle_root_validation_status is not null"
    elif validated == "any":
        pass

    return mysql_grunt.quick_fetch(
        query, (block_height_start, block_height_end)
    )

def update_merkle_root_status(valid, block_height):
    mysql_grunt.cursor.execute("""
        update blockchain_headers
        set merkle_root_validation_status = %s
        where block_height = %s
    """, (1 if valid else 0, block_height))
    return mysql_grunt.cursor.rowcount

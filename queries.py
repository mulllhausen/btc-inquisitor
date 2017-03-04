#!/usr/bin/env python2.7

import mysql_grunt

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

def get_tx_header(input_arg_format, data):
    query = """select
    h.block_height as block_height,
    hex(h.block_hash) as block_hash_hex,
    hex(h.previous_block_hash) as prev_block_hash_hex,
    h.version as block_version,
    hex(h.merkle_root) as merkle_root_hex,
    h.timestamp as block_time,
    hex(h.bits) as bits_hex,
    h.nonce as nonce,
    h.block_size as block_size,
    h.orphan_status as block_orphan_status,
    h.merkle_root_validation_status as merkle_root_validation_status,
    h.bits_validation_status as bits_validation_status,
    h.difficulty_validation_status as difficulty_validation_status,
    h.block_hash_validation_status as block_hash_validation_status,
    h.block_size_validation_status as block_size_validation_status,
    h.block_version_validation_status as block_version_validation_status,
    h.num_txs as num_txs,
    t.tx_num as tx_num,
    hex(t.tx_hash) as tx_hash_hex,
    t.tx_version as tx_version,
    t.num_txins as num_txins,
    t.num_txouts as num_txouts,
    t.tx_lock_time as tx_lock_time,
    t.tx_size as tx_size,
    t.tx_change as tx_change,
    t.tx_lock_time_validation_status as tx_lock_time_validation_status,
    t.tx_funds_balance_validation_status as tx_funds_balance_validation_status,

    t.tx_pubkey_to_address_validation_status as
    tx_pubkey_to_address_validation_status

    from blockchain_txs t
    inner join blockchain_headers h on h.block_hash = t.block_hash
    where """

    if input_arg_format == "blockheight-txnum":
        query += """
        t.block_height = %s and
        t.tx_num = %s
        """
        return mysql_grunt.quick_fetch(query, data)[0]

    elif input_arg_format == "txhash":
        query += "t.tx_hash = unhex(%s)"
        return mysql_grunt.quick_fetch(query, data)[0]

    elif input_arg_format == "blockheight":
        query += "t.block_height = %s"
        return mysql_grunt.quick_fetch(query, data)

    elif input_arg_format == "blockhash":
        query += "t.block_hash = unhex(%s)"
        return mysql_grunt.quick_fetch(query, data)

def get_txins_and_txouts(tx_hash_hex):
    # return hex instead of bin in case bin gives bad data
    query = """select
    'txin' as 'type',
    txin.txin_num as 'txin_num',
    txin.address as 'txin_address',
    txin.alternate_address as 'txin_alternate_address',
    txin.funds as 'txin_funds',
    hex(txin.prev_txout_hash) as 'prev_txout_hash_hex',
    txin.prev_txout_num as 'prev_txout_num',
    txin.txin_hash_validation_status as 'txin_hash_validation_status',
    txin.txin_index_validation_status as 'txin_index_validation_status',

    txin.txin_mature_coinbase_spend_validation_status as
    'txin_mature_coinbase_spend_validation_status',

    hex(txin.script) as 'txin_script_hex',
    txin.script_format as 'txin_script_format',
    txin.script_length as 'txin_script_length',
    hex(prev_txout.script) as 'prev_txout_script_hex',
    prev_txout.script_format as 'prev_txout_script_format',
    prev_txout.script_length as 'prev_txout_script_length',
    prev_txout.pubkey as 'prev_txout_pubkey',
    prev_txout.address as 'prev_txout_address',
    prev_txout.alternate_address as 'prev_txout_alternate_address',
    txin.txin_sequence_num as 'txin_sequence_num',

    txin.txin_single_spend_validation_status as
    'txin_single_spend_validation_status',

    txin.txin_spend_from_non_orphan_validation_status as
    'txin_spend_from_non_orphan_validation_status',

    txin.txin_checksig_validation_status as
    'txin_checksig_validation_status',

    0 as 'txout_num',
    '' as 'txout_address',
    0 as 'txout_funds',
    '' as 'txout_alternate_address',
    '' as 'txout_pubkey_hex',
    '' as 'txout_pubkey_to_address_validation_status',
    '' as 'txout_script_hex',
    '' as 'txout_script_format',
    0 as 'txout_script_length',
    '' as 'txout_shared_funds',
    '' as 'standard_script_address_checksum_validation_status',
    '' as 'txout_change_calculated'
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
    0 as 'txin_num',
    '' as 'txin_address',
    '' as 'txin_alternate_address',
    0 as 'txin_funds',
    '' as 'prev_txout_hash_hex',
    0 as 'prev_txout_num',
    '' as 'txin_hash_validation_status',
    '' as 'txin_index_validation_status',
    '' as 'txin_mature_coinbase_spend_validation_status',
    '' as 'txin_script_hex',
    '' as 'txin_script_format',
    0 as 'txin_script_length',
    '' as 'prev_txout_pubkey',
    '' as 'prev_txout_address',
    '' as 'prev_txout_alternate_address',
    '' as 'prev_txout_script_hex',
    '' as 'prev_txout_script_format',
    0 as 'prev_txout_script_length',
    0 as 'txin_sequence_num',
    '' as 'txin_single_spend_validation_status',
    '' as 'txin_spend_from_non_orphan_validation_status',
    '' as 'txin_checksig_validation_status',
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
    return mysql_grunt.quick_fetch("""
        select block_height
        from blockchain_headers
        where merkle_root_validation_status = %s
        and txin.block_height >= %s
        and txin.block_height < %s
    """, (1 if validated else 0, block_height_start, block_height_end))

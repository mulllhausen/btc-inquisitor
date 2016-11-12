#!/usr/bin/env python2.7

import mysql_grunt

def get_tx_header(input_arg_format, data):
    query = """select
    h.block_height as block_height,
    h.timestamp as block_time,
    h.version as block_version,
    h.block_hash as block_hash,
    t.tx_num as tx_num,
    t.tx_hash as tx_hash,
    t.tx_change as tx_change,
    t.tx_funds_balance_validation_status as tx_funds_balance_validation_status,
    t.num_txins as num_txins,
    t.num_txouts as num_txouts,
    t.tx_lock_time as tx_lock_time,
    t.tx_lock_time_validation_status as tx_lock_time_validation_status,
    t.tx_size as tx_size,
    t.tx_version as tx_version
    from blockchain_txs t
    inner join blockchain_headers h on h.block_hash = t.block_hash
    where"""

    if input_arg_format == "blockheight-txnum":
        query += """
        t.block_height = %s and
        t.tx_num = %s
        """
    elif input_arg_format == "txhash":
        query += """
        t.tx_hash = unhex(%s)
        """
    return mysql_grunt.quick_fetch(query, data)[0]

def get_txins_and_txouts(tx_hash_bin):
    query = """select
    'txin' as 'type',
    txin.txin_num as 'txin_num',
    txin.address as 'txin_address',
    txin.alternate_address as 'txin_alternate_address',
    txin.funds as 'txin_funds',
    txin.prev_txout_hash as 'prev_txout_hash',
    txin.prev_txout_num as 'prev_txout_num',
    txin.txin_hash_validation_status as 'txin_hash_validation_status',
    txin.txin_index_validation_status as 'txin_index_validation_status',
    txin.txin_mature_coinbase_spend_validation_status as 'txin_mature_coinbase_spend_validation_status',
    txin.script as 'txin_script',
    txin.script_format as 'txin_script_format',
    txin.script_length as 'txin_script_length',
    prev_txout.script as 'prev_txout_script',
    prev_txout.script_format as 'prev_txout_script_format',
    prev_txout.script_length as 'prev_txout_script_length',
    prev_txout.address as 'prev_txout_address',
    prev_txout.alternate_address as 'prev_txout_alternate_address',
    txin.txin_sequence_num as 'txin_sequence_num',
    txin.txin_single_spend_validation_status as 'txin_single_spend_validation_status',
    txin.txin_spend_from_non_orphan_validation_status as 'txin_spend_from_non_orphan_validation_status',
    txin.txin_checksig_validation_status as 'txin_checksig_validation_status',
    0 as 'txout_num',
    '' as 'txout_address',
    0 as 'txout_funds',
    '' as 'txout_alternate_address',
    '' as 'txout_pubkey',
    '' as 'txout_pubkey_to_address_validation_status',
    '' as 'txout_script',
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
    txin.tx_hash = %s

    union all

    select
    'txout' as 'type',
    0 as 'txin_num',
    '' as 'txin_address',
    '' as 'txin_alternate_address',
    0 as 'txin_funds',
    '' as 'prev_txout_hash',
    0 as 'prev_txout_num',
    '' as 'txin_hash_validation_status',
    '' as 'txin_index_validation_status',
    '' as 'txin_mature_coinbase_spend_validation_status',
    '' as 'txin_script',
    '' as 'txin_script_format',
    0 as 'txin_script_length',
    '' as 'prev_txout_address',
    '' as 'prev_txout_alternate_address',
    '' as 'prev_txout_script',
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
    txout.pubkey as 'txout_pubkey',
    txout.pubkey_to_address_validation_status as 'txout_pubkey_to_address_validation_status',
    txout.script as 'txout_script',
    txout.script_format as 'txout_script_format',
    txout.script_length as 'txout_script_length',
    txout.shared_funds as 'txout_shared_funds',
    txout.standard_script_address_checksum_validation_status as 'standard_script_address_checksum_validation_status',
    txout.tx_change_calculated as 'txout_change_calculated'
    from blockchain_txouts txout
    where
    txout.tx_hash = %s
    """
    return mysql_grunt.quick_fetch(query, (tx_hash_bin, tx_hash_bin))

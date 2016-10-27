#!/usr/bin/env python2.7

def block(input_arg_format, data):
    select_start = """select
    block_height,
    lower(hex(block_hash)) as block_hash_hex,
    tx_num,
    lower(hex(tx_hash)) as tx_hash_hex,
    tx_change,
    tx_funds_balance_validation_status,
    num_txins,
    num_txouts,
    tx_lock_time,
    tx_lock_time_validation_status,
    tx_size,
    tx_version
    from blockchain_txs
    where"""
    if input_arg_format == "blockheight-txnum":
        (block_height, tx_num) = data
        query = """%s
        block_height = %d and
        tx_num = %d
        """ % (select_start, block_height, tx_num)
    elif input_arg_format == "txhash":
        tx_hash_hex = data
        query = """%s
        tx_hash = unhex(%s)
        """ % (select_start, tx_hash_hex)

    return query

def get_tx(tx_hash_hex):
    query = """select
    'txin' as 'type',
    txin.txin_num as 'txin_num',
    txin.address as 'txin_address',
    txin.alternate_address as 'txin_alternate_address',
    txin.funds as 'txin_funds',
    lower(hex(txin.prev_txout_hash)) as 'prev_txout_hash_hex',
    txin.prev_txout_num as 'prev_txout_num',
    txin.txin_hash_validation_status as 'txin_hash_validation_status',
    txin.txin_index_validation_status as 'txin_index_validation_status',
    txin.txin_mature_coinbase_spend_validation_status as 'txin_mature_coinbase_spend_validation_status',
    lower(hex(txin.script)) as 'txin_script_hex',
    txin.script_format as 'txin_script_format',
    txin.script_length as 'txin_script_length',
    lower(hex(prev_txout.script)) as 'prev_txout_script_hex',
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
    txin.tx_hash = unhex('%s')

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
    lower(hex(txout.pubkey)) as 'txout_pubkey_hex',
    txout.pubkey_to_address_validation_status as 'txout_pubkey_to_address_validation_status',
    lower(hex(txout.script)) as 'txout_script_hex',
    txout.script_format as 'txout_script_format',
    txout.script_length as 'txout_script_length',
    txout.shared_funds as 'txout_shared_funds',
    txout.standard_script_address_checksum_validation_status as 'standard_script_address_checksum_validation_status',
    txout.tx_change_calculated as 'txout_change_calculated'
    from blockchain_txouts txout
    where
    txout.tx_hash = unhex('%s')
    """ % (tx_hash_hex, tx_hash_hex)

    return query

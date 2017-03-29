#!/usr/bin/env python2.7

"""unit tests for mysql queries"""

if __name__ == '__main__' and __package__ is None:
    # include the dir above
    from os import sys, path
    sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

import queries
import unittest
import re

class get_blockchain_dataTests(unittest.TestCase):
    def test_blockchain_headers_only(self):
        where = {"block_height": {"start": 1, "end": 1}}
        required_info = ["block_height"]
        actual_answer = clean_str(
            queries.get_blockchain_data_query(where, required_info)
        )
        required_answer = clean_str("""
            select
            h.block_height as 'block_height'
            from
            blockchain_headers h
            where
            h.block_height >= 1 and
            h.block_height <= 1
        """)
        fail_msg = "required_answer: %s\nactual_answer: %s" % \
        (required_answer, actual_answer)
        self.assertEqual(actual_answer, required_answer, msg = fail_msg)

    def test_blockchain_tx_headers_only(self):
        where = {"block_height": {"start": 1, "end": 1}, "tx_nums": [0]}
        required_info = ["tx_hash"]
        actual_answer = clean_str(
            queries.get_blockchain_data_query(where, required_info)
        )
        required_answer = clean_str("""
            select
            hex(t.tx_hash) as 'tx_hash_hex',
            t.tx_num as 'tx_num'
            from blockchain_txs t
            where
            t.block_height >= 1 and
            t.block_height <= 1 and
            t.tx_num in (0)
        """)
        fail_msg = "required_answer: %s\nactual_answer: %s" % \
        (required_answer, actual_answer)
        self.assertEqual(actual_answer, required_answer, msg = fail_msg)

    def test_blockchain_txins_only(self):
        where = {"block_height": {"start": 1, "end": 1}, "tx_nums": [0]}
        required_info = ["txin_num"]
        actual_answer = clean_str(
            queries.get_blockchain_data_query(where, required_info)
        )
        required_answer = clean_str("""
            select
            'txin' as 'type',
            t.tx_num as 'tx_num',
            txin.txin_num as 'txin_num'
            from
            blockchain_txs t
            inner join blockchain_txins txin on txin.tx_hash = t.tx_hash
            where
            t.block_height >= 1 and
            t.block_height <= 1 and
            t.tx_num in (0)
        """)
        fail_msg = "required_answer: %s\nactual_answer: %s" % \
        (required_answer, actual_answer)
        self.assertEqual(actual_answer, required_answer, msg = fail_msg)

    def test_blockchain_prev_txouts_only(self):
        where = {"block_height": {"start": 1, "end": 1}, "tx_nums": [0]}
        required_info = ["prev_txout_num"]
        actual_answer = clean_str(
            queries.get_blockchain_data_query(where, required_info)
        )
        required_answer = clean_str("""
            select
            'txin' as 'type',
            t.tx_num as 'tx_num',
            txin.prev_txout_num as 'prev_txout_num',
            txin.txin_num as 'txin_num'
            from
            blockchain_txs t
            inner join blockchain_txins txin on txin.tx_hash = t.tx_hash
            left join blockchain_txouts prev_txout on (
                txin.prev_txout_hash = prev_txout.tx_hash and
                txin.prev_txout_num = prev_txout.txout_num
            )
            where
            t.block_height >= 1 and
            t.block_height <= 1 and
            t.tx_num in (0)
        """)
        fail_msg = "required_answer: %s\nactual_answer: %s" % \
        (required_answer, actual_answer)
        self.assertEqual(actual_answer, required_answer, msg = fail_msg)

    def test_blockchain_txouts_only(self):
        where = {"block_height": {"start": 1, "end": 1}, "tx_nums": [0]}
        required_info = ["txout_num"]
        actual_answer = clean_str(
            queries.get_blockchain_data_query(where, required_info)
        )
        required_answer = clean_str("""
            select
            'txout' as 'type',
            t.tx_num as 'tx_num',
            txout.txout_num as 'txout_num'
            from
            blockchain_txs t
            inner join blockchain_txouts txout on txout.tx_hash = t.tx_hash
            where
            t.block_height >= 1 and
            t.block_height <= 1 and
            t.tx_num in (0)
        """)
        fail_msg = "required_answer: %s\nactual_answer: %s" % \
        (required_answer, actual_answer)
        self.assertEqual(actual_answer, required_answer, msg = fail_msg)

def clean_str(str_to_clean):
    return re.sub(r"\s+", " ", str_to_clean.strip())

unittest.main()


#!/usr/bin/env python2.7

"""unit tests for mysql queries"""

if __name__ == '__main__' and __package__ is None:
    # include the dir above
    from os import sys, path
    sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

import queries
import unittest

where = {"block_height": {"start": 1, "end": 1}}
required_info = ["txin_num"]
actual_answer = queries.get_blockchain_data_query(where, required_info)

class get_blockchain_dataTests(unittest.TestCase):
    def test_blockchain_headers_only(self):
        where = {"block_height": {"start": 1, "end": 1}}
        required_info = ["block_height"]
        actual_answer = queries.get_blockchain_data_query(where, required_info)

        required_answer = "select h.block_height as 'block_height' from" \
        " blockchain_headers h where h.block_height >= 1 and" \
        " h.block_height <= 1"
        fail_msg = "required_answer: %s\nactual_answer: %s" % \
        (required_answer, actual_answer)
        self.assertEqual(actual_answer, required_answer, msg = fail_msg)

    def test_blockchain_tx_headers_only(self):
        where = {"block_height": {"start": 1, "end": 1}, "tx_nums": [0]}
        required_info = ["tx_hash"]
        actual_answer = queries.get_blockchain_data_query(where, required_info)

        required_answer = "select hex(t.tx_hash) as 'tx_hash_hex' from" \
        " blockchain_txs t where t.block_height >= 1 and" \
        " t.block_height <= 1 and t.tx_num in (0)"
        fail_msg = "required_answer: %s\nactual_answer: %s" % \
        (required_answer, actual_answer)
        self.assertEqual(actual_answer, required_answer, msg = fail_msg)

    def test_blockchain_txins_only(self):
        where = {"block_height": {"start": 1, "end": 1}, "tx_nums": [0]}
        required_info = ["txin_num"]
        actual_answer = queries.get_blockchain_data_query(where, required_info)

        required_answer = "select txin.txin_num as 'txin_num' from" \
        " blockchain_txins txin where txin.block_height >= 1 and" \
        " txin.block_height <= 1 and t.tx_num in (0)"
        fail_msg = "required_answer: %s\nactual_answer: %s" % \
        (required_answer, actual_answer)
        self.assertEqual(actual_answer, required_answer, msg = fail_msg)

    def test_blockchain_prev_txouts_only(self):
        where = {"block_height": {"start": 1, "end": 1}, "tx_nums": [0]}
        required_info = ["prev_txout_num"]
        actual_answer = queries.get_blockchain_data_query(where, required_info)

        required_answer = "select txin.txin_num as 'txin_num'," \
        " txin.prev_txout_num as 'prev_txout_num'" \
        " from blockchain_txins txin" \
        " left join blockchain_txouts prev_txout on (" \
        " txin.prev_txout_hash = prev_txout.tx_hash and" \
        " txin.prev_txout_num = prev_txout.txout_num)" \
        " where t.block_height >= 1 and" \
        " t.block_height <= 1 and t.tx_num in (0)"
        fail_msg = "required_answer: %s\nactual_answer: %s" % \
        (required_answer, actual_answer)
        self.assertEqual(actual_answer, required_answer, msg = fail_msg)

    def test_blockchain_txouts_only(self):
        where = {"block_height": {"start": 1, "end": 1}, "tx_nums": [0]}
        required_info = ["txout_num"]
        actual_answer = queries.get_blockchain_data_query(where, required_info)

        required_answer = "select txout.txout_num as 'txout_num' from" \
        " blockchain_txouts txout where t.block_height >= 1 and" \
        " t.block_height <= 1 and t.tx_num in (0)"
        fail_msg = "required_answer: %s\nactual_answer: %s" % \
        (required_answer, actual_answer)
        self.assertEqual(actual_answer, required_answer, msg = fail_msg)

unittest.main()


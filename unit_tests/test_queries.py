#!/usr/bin/env python2.7

"""unit tests for mysql queries"""

if __name__ == '__main__' and __package__ is None:
    # include the dir above
    from os import sys, path
    sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

import queries
import unittest

class get_blockchain_dataTests(unittest.TestCase):
    def test_blockchain_headers_only(self):
        where = []
        required_info = ["block_height"]
        output_query = True
        
        required_answer = "select h.block_height as 'block_height' from" \
        " blockchain_headers h where"
        actual_answer = queries.get_blockchain_data_query(where, required_info)
        fail_msg = "required_answer: %s\nactual_answer: %s" % \
        (required_answer, actual_answer)
        self.assertEqual(actual_answer, required_answer, msg = fail_msg)

    def test_blockchain_tx_headers_only(self):
        where = []
        required_info = ["tx_hash"]
        output_query = True
        
        required_answer = "select hex(t.tx_hash) as 'tx_hash_hex' from" \
        " blockchain_txs t where"
        actual_answer = queries.get_blockchain_data_query(where, required_info)
        fail_msg = "required_answer: %s\nactual_answer: %s" % \
        (required_answer, actual_answer)
        self.assertEqual(actual_answer, required_answer, msg = fail_msg)

    def test_blockchain_txins_only(self):
        where = []
        required_info = ["txin_num"]
        output_query = True
        
        required_answer = "select txin.txin_num as 'txin_num' from" \
        " blockchain_txins txin where"
        actual_answer = queries.get_blockchain_data_query(where, required_info)
        fail_msg = "required_answer: %s\nactual_answer: %s" % \
        (required_answer, actual_answer)
        self.assertEqual(actual_answer, required_answer, msg = fail_msg)

    def test_blockchain_prev_txouts_only(self):
        where = []
        required_info = ["prev_txout_num"]
        output_query = True
        
        required_answer = "select txin.prev_txout_num as 'prev_txout_num'" \
        " from blockchain_txins txin where"
        actual_answer = queries.get_blockchain_data_query(where, required_info)
        fail_msg = "required_answer: %s\nactual_answer: %s" % \
        (required_answer, actual_answer)
        self.assertEqual(actual_answer, required_answer, msg = fail_msg)

    def test_blockchain_txouts_only(self):
        where = []
        required_info = ["txout_num"]
        output_query = True
        
        required_answer = "select txout.txout_num as 'txout_num' from" \
        " blockchain_txouts txout where"
        actual_answer = queries.get_blockchain_data_query(where, required_info)
        fail_msg = "required_answer: %s\nactual_answer: %s" % \
        (required_answer, actual_answer)
        self.assertEqual(actual_answer, required_answer, msg = fail_msg)

unittest.main()


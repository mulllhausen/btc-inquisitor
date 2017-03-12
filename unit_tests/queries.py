#!/usr/bin/env python2.7

"""unit tests for mysql queries"""

import queries
import unittest

class get_blockchain_dataTests(unittest.TestCase):
    def test_blockchain_headers_only(self):
        where = []
        required_info = ["block_height"]
        output_query = True
        
        required_answer = "select h.block_height as 'block_height' from" \
        " blockchain_headers h where "
        actual_answer = get_blockchain_data(where, required_info, output_query)
        self.failUnless(actual_answer == required_answer)

unittest.main()


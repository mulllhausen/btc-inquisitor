#!/bin/bash

echo
echo "test: make sure the program does not accept addresses from different cryptocurrencies"
./btc-inquisitor.py -tp -L 100 -a 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa,LA1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
echo
echo "==========" 
echo
echo "test: search for some transaction hashes within the first 10 blocks (valid format hashes which do exist)"
./btc-inquisitor.py -f -L 10 --tx-hashes 4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b,0e3e2357e806b6cdb1f70b54c3a3a17b6714ee1f0e68bebb44a74b1efd512098
echo
echo "==========" 
exit 0
echo
echo "test: search for some transaction hashes within the first 10 blocks (valid format hashes which do not exist)"
pudb btc-inquisitor.py -tp -L 10 --tx-hashes 0123456789abcdefaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa,0123456789abcdefbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
echo
echo "==========" 
echo
echo "test: extract all transactions for satoshi's address within the first 100 blocks"
./btc-inquisitor.py -tp -L 100 -a 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
echo
echo "==========" 
echo

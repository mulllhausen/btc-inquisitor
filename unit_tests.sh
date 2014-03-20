#!/bin/bash

echo
echo "test: make sure the program does not accept addresses from different cryptocurrencies"
./btc-inquisitor.py -tp -L 100 -a 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa,LA1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
echo
echo "==========" 
echo
echo "test: search for some transaction hashes within the first 10 blocks (valid format hashes which do exist)"
./btc-inquisitor.py -f -L 10 --tx-hashes 4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b,0e3e2357e806b6cdb1f70b54c3a3a17b6714ee1f0e68bebb44a74b1efd512098 -o HEX
echo
echo "==========" 
echo
echo "test: search for some transaction hashes within the first 10 blocks (valid format hashes which do not exist)"
./btc-inquisitor.py -tp -L 10 --tx-hashes 0123456789abcdefaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa,0123456789abcdefbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
echo
echo "==========" 
echo
echo "test: extract all transactions for satoshi's address within the first 10 blocks"
./btc-inquisitor.py -tp -L 10 -a 12c6DSiU4Rq3P4ZxziKxzrL5LmMBrzjrJX,04678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f61deb649f6bc3f4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5f
echo
echo "==========" 
echo

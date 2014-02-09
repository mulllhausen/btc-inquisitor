#!/bin/bash

echo
echo "test: make sure the program does not accept addresses from different cryptocurrencies"
./btc-inquisitor.py -tp -L 100 --dont-validate-merkle-trees -a 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa,LA1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
echo
echo "==========" 
echo
echo "test: search for some transaction hashes within the first 10 blocks (valid format hashes which do not exist)"
./btc-inquisitor.py -tp -L 100 --dont-validate-merkle-trees --tx-hashes 0123456789abcdefaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa,0123456789abcdefbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
echo
echo "==========" 
echo
echo "test: extract all transactions for satoshi's address within the first 100 blocks"
./btc-inquisitor.py -tp -L 100 --dont-validate-merkle-trees -a 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
echo
echo "==========" 
echo

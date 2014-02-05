#!/bin/bash

echo "test: make sure the program does not accept addresses from different cryptocurrencies"
./btc-inquisitor.py -tp -L 100 -a 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa,LA1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa

echo # blank line

echo "test: extract all transactions for satoshi's address within the first 100 blocks"
./btc-inquisitor.py -tp -L 100 --dont-validate-merkle-trees -a 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa

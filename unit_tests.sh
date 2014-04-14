#!/bin/bash

echo
echo "test: compute the balance for address 12cbQLTFMXRnSzktFkuoG3eHoMeFtpTu3S"
pudb btc-inquisitor.py -pb -a 12cbQLTFMXRnSzktFkuoG3eHoMeFtpTu3S,1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -L 71035
echo
echo "=========="
echo
exit 0
echo "test: make sure the program does not accept addresses from different cryptocurrencies"
./btc-inquisitor.py -tp -L 100 -a 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa,LA1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
echo
echo "=========="
echo
echo "test: search for some transaction hashes within the first 170 blocks (valid format hashes which do exist)"
./btc-inquisitor.py -f -L 172 --tx-hashes 4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b,f4184fc596403b9d638783cf57adfe4c75c605f6356fbc91338530e9831e9e16 -o HEX
echo
echo "=========="
echo
echo "test: search for some transaction hashes within the first 10 blocks (valid format hashes which do not exist)"
./btc-inquisitor.py -tp -L 10 --tx-hashes 0123456789abcdefaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa,0123456789abcdefbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
echo
echo "=========="
echo
echo "test: extract all transactions for satoshi's address within the first 10 blocks"
./btc-inquisitor.py -tp -L 10 -a 12c6DSiU4Rq3P4ZxziKxzrL5LmMBrzjrJX,04678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f61deb649f6bc3f4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5f -o HEX
echo
echo "=========="
echo
echo "test: extract blocks 50 and 51 using the start and the limit arguments"
./btc-inquisitor.py -fp -s 50 -L 2
echo
echo "=========="
echo
echo "test: extract blocks 5 and 6 using the start and end arguments"
./btc-inquisitor.py -fp -s 5 -e 6
echo
echo "=========="
echo
echo "test: extract 3 blocks starting at blockhash 000000006a625f06636b8bb6ac7b960a8d03705d1ace08b1a19da3fdcc99ddbd (the 2nd block's hash)"
./btc-inquisitor.py -fp --start-blockhash 000000006a625f06636b8bb6ac7b960a8d03705d1ace08b1a19da3fdcc99ddbd -L 3
echo
echo "=========="
echo
echo "test: demonstrate that end-blocknum must come after start-blocknum"
./btc-inquisitor.py -f -s 6 -e 5
echo
echo "=========="
echo
echo "test: demonstrate that end-blockhash must correspond to a block which comes later than that of start-blockhash"
# 000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f - block 0
# 00000000839a8e6886ab5951d76f411475428afc90947ee320161bbf18eb6048 - block 1
# 000000006a625f06636b8bb6ac7b960a8d03705d1ace08b1a19da3fdcc99ddbd - block 2
./btc-inquisitor.py -f --start-blockhash 000000006a625f06636b8bb6ac7b960a8d03705d1ace08b1a19da3fdcc99ddbd --end-blockhash 00000000839a8e6886ab5951d76f411475428afc90947ee320161bbf18eb6048 
echo
echo "=========="
echo
echo "test: demonstrate that end block number comes later than that of start-blockhash's block"
./btc-inquisitor.py -f --start-blockhash 000000006a625f06636b8bb6ac7b960a8d03705d1ace08b1a19da3fdcc99ddbd -e 0
echo
echo "=========="
echo
echo "test: request a block that doesn't exist"
./btc-inquisitor.py -pf -s 546 -L 1
echo
echo "=========="
echo

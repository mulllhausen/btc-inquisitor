#!/bin/bash

# set correct base dir with chdir (stackoverflow.com/a/1482133/339874)
abspath="$(dirname "$(readlink -f "$0")")"
one_dir_up="${abspath%/*}"
cd "$one_dir_up"

# list the interesting tx hashes (from the live blockchain) to validate.
# use ./get_tx.py <txhash> to see full details
declare -a txhashes=(
	# test the checksig for the first tx ever spent
	"f4184fc596403b9d638783cf57adfe4c75c605f6356fbc91338530e9831e9e16"

	# standard pay to pubkey hash tx with a single input
	"27f3727e0915a71cbe75dd9d5ded9d8161a82c0b81a3b60f5fff739cdd77fd51"

	# a tx with multiple inputs
	"dfc95e050b8d6dc76818ef6e1f117c7631cc971f86da4096efdf72434a1ef6be"

	# first checkmultisig and first OP_CHECKLOCKTIMEVERIFY tx ever
	"eb3b82c0884e3efa6d8b0be55b4915eb20be124c9766245bcc7f34fdac32bccb"

	# first checkmultisig tx with more than 1 public key
	"bc179baab547b7d7c1d5d8d6f8b0cc6318eaa4b0dd0a093ad6ac7f5a1cb6b3ba"

	# first sighash_none type tx
	"599e47a8114fe098103663029548811d2651991b62397e057f0c863c2bc9f9ea"

	# first sighash_anyonecanpay type tx
	"51bf528ecf3c161e7c021224197dbe84f9a8564212f6207baa014c01a1668e1e"

	# first multisig tx with more than 1 signature
	"7c2c4cf601c4607d068fdf6b95900b8a5bc73fbb9a22200ab56ebfe44b8c6e74"

	# a random tx that was failing
	"ee5a5dc33719fedead5f04a82cae22b1d2009c69747f94a245bbeaf03ae974dc"

	# first occurrence of OP_DEPTH ever
	"340aa9f72206d600b7e89c9137e4d2d77a920723f83e34707ff452121fd48492"

	# first occurrence of OP_SWAP ever
	"cd874fa8cb0e2ec2d385735d5e1fd482c4fe648533efb4c50ee53bda58e15ae2"

	# spending a p2sh address
	"7edb32d4ffd7a385b763c7a8e56b6358bcd729e747290624e18acdbe6209fc45"

	# a p2sh script but before 1333238400, so not evaluated
	"6a26d2ecb67f27d1fa5524763b49029d7106e91e3cc05743073461a719776192"

	# a multisig with one of the pubkeys in a bad format
	"98c4cdffdd2aaf1c2280b2d22d4b59839c937f1a3dc9daf6fd7db077de90592d"
)
# validate each of the above tx hashes
for txhash in "${txhashes[@]}"
do
	echo "validating all txins for tx $txhash"
	result=$(./validate_tx_scripts.py "$txhash")
	# $result is empty with exit code 0 upon success, else fail
	[[ -n "$result" || $? != 0 ]] && echo -e "\n\nfail\n\n$result" && exit 1
done

exit 0

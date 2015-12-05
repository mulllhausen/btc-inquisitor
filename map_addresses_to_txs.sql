CREATE TABLE IF NOT EXISTS map_addresses_to_txs (
	blockheight int(11) NOT NULL,
	txhash binary(32) NOT NULL,
	txin_num int(11) DEFAULT NULL,
	txout_num int(11) DEFAULT NULL,
	address varchar(34) DEFAULT NULL,
	alternate_address varchar(34) DEFAULT NULL COMMENT 'the compressed/uncompressed equivalent address if known',
	pubkey_compressed varchar(33) DEFAULT NULL,
	shared_funds bit(1) NOT NULL DEFAULT b'0' COMMENT 'are multiple pubkeys in charge of the same funds?',
	KEY txhash (txhash)
	KEY address (address),
	KEY alternate_address (alternate_address),
	KEY pubkey_compressed (pubkey_compressed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

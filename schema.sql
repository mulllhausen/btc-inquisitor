CREATE DATABASE IF NOT EXISTS btc_inquisitor
    DEFAULT CHARACTER SET utf8
    DEFAULT COLLATE utf8_general_ci;

USE btc_inquisitor;

CREATE TABLE IF NOT EXISTS tasklist (
    id      int(11)     NOT NULL AUTO_INCREMENT,
    host    varchar(20) NOT NULL,
    name    varchar(40) NOT NULL,
    started datetime    DEFAULT NULL,
    ended   datetime    DEFAULT NULL,
    details text,
    PRIMARY KEY (id, host)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS map_addresses_to_txs (
    blockheight         int(11)     NOT NULL,
    txhash              binary(32)  NOT NULL,
    txin_num            int(11)     DEFAULT NULL,
    txout_num           int(11)     DEFAULT NULL,
    address             varchar(34) DEFAULT NULL,

    alternate_address   varchar(34) DEFAULT NULL COMMENT
    'the compressed/uncompressed equivalent address if known',

    txout_script_format varchar(10) DEFAULT NULL,

    shared_funds        bit(1)      DEFAULT NULL COMMENT
    'are multiple pubkeys in charge of the same funds?',

    orphan_block        bit(1)      NOT NULL DEFAULT b'0' COMMENT
    '0=false,1=true',

    KEY blockheight_index       (blockheight),
    KEY txhash_index            (txhash),
    KEY address_index           (address),
    KEY alternate_address_index (alternate_address),
    KEY shared_funds_index      (shared_funds)

) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS blockchain_headers (
    -- data parsed from the block headers
    block_height                    INT(7)      NOT NULL,
    block_hash                      BINARY(32)  NOT NULL,
    previous_block_hash             BINARY(32)  NOT NULL,
    version                         INT(3)      NOT NULL,
    merkle_root                     BINARY(32)  NOT NULL,
    timestamp                       INT(11)     NOT NULL,
    bits                            BINARY(4)   NOT NULL,

    -- max = 4 bytes = 4294967295
    nonce                           INT(10)     NOT NULL,

    block_size                      INT(10)     NOT NULL,
	num_txs                         INT(5)      NOT NULL,

    -- data processed from the block headers
    orphan_status                   BIT(1)      NOT NULL DEFAULT b'0' COMMENT
    '1=orphan,0=not orphan',

	merkle_root_validation_status   BIT(1)      NOT NULL,
	bits_validation_status          BIT(1)      NOT NULL COMMENT
    'do the previous bits and time to mine 2016 blocks produce these bits?',

	difficulty_validation_status    BIT(1)      NOT NULL COMMENT
    'is the difficulty > 1?',

	block_hash_validation_status    BIT(1)      NOT NULL COMMENT
    'is the block hash below the target?',

	block_size_validation_status    BIT(1)      NOT NULL COMMENT
    'is the block size less than the permitted maximum?',

	block_version_validation_status BIT(1)      NOT NULL COMMENT
    'versions must coincide with block height ranges',

    -- indexes
    KEY block_height_index                     (block_height),
    KEY block_hash_index                       (block_hash),
	KEY merkle_root_validation_status_index    (merkle_root_validation_status),
	KEY bits_validation_status_index           (bits_validation_status),
	KEY difficulty_validation_status_index     (difficulty_validation_status),
	KEY block_hash_validation_status_index     (block_hash_validation_status),
	KEY block_size_validation_status_index     (block_size_validation_status),
	KEY block_version_validation_status_index  (block_version_validation_status)

) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS blockchain_txs (
    -- data parsed from the tx bytes
    tx_hash         BINARY(32)  NOT NULL,
    tx_version      INT(11)     NOT NULL,
    num_txins       INT(4)      NOT NULL,
    num_txouts      INT(4)      NOT NULL,
    tx_lock_time    INT(11)     NOT NULL,
    tx_timestamp    INT(11)     NOT NULL,
    tx_size         INT(10)     NOT NULL,

    -- data processed from the tx bytes

    -- max change assumed to be 100 btc = 100 x 100 000 000
    tx_change                               INT(10) NOT NULL,

	tx_lock_time_validation_status          BIT(1)  DEFAULT NULL,
	tx_funds_balance_validation_status      BIT(1)  DEFAULT NULL,
	tx_pubkey_to_address_validation_status  BIT(1)  DEFAULT NULL,
	tx_lock_time_validation_status          BIT(1)  DEFAULT NULL,

    -- indexes
    KEY tx_hash_index
    (block_height),

	KEY tx_lock_time_validation_status_index
    (tx_lock_time_validation_status),

	KEY tx_funds_balance_validation_status_index
    (tx_funds_balance_validation_status),

	KEY tx_pubkey_to_address_validation_status_index
    (tx_pubkey_to_address_validation_status)

) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS blockchain_txins (
    -- data parsed from the txins
    tx_hash             BINARY(32)      NOT NULL,
    txin_num            INT(4)          NOT NULL,
    prev_txout_hash     BINARY(32)      NOT NULL,
    prev_txout_num      INT(4)          NOT NULL,
    txin_script_length  INT(4)          NOT NULL,

    -- max = 10,000 bytes (interpreter.cpp, line 256)
    txin_script         BINARY(10000)   NOT NULL,

    txin_sequence_num   INT(10)         NOT NULL, -- max = 4 bytes = 4294967295

    -- data processed from the transactions
    txin_script_format                              VARCHAR(20) DEFAULT NULL,

    -- from previous txout. max = 21,000,000 btc = 21 x 10^14 sat
    txin_funds                                      INT(15)     NOT NULL,

    -- from previous txout. max = 100 btc
    txin_coinbase_change_funds                      INT(10)     NOT NULL,

    address                                         VARCHAR(34) DEFAULT NULL,

    alternate_address                               VARCHAR(34) DEFAULT NULL
    COMMENT 'the compressed/uncompressed equivalent address if known',

    shared_funds                                    BIT(1)      DEFAULT NULL
    COMMENT 'are multiple pubkeys in charge of the same funds?',

	txin_coinbase_hash_validation_status            BIT(1)      DEFAULT NULL,
	txin_hash_validation_status                     BIT(1)      DEFAULT NULL,
	txin_coinbase_index_validation_status           BIT(1)      DEFAULT NULL,
	txin_index_validation_status                    BIT(1)      DEFAULT NULL,
	txin_single_spend_validation_status             BIT(1)      DEFAULT NULL,
	txin_spend_from_non_orphan_validation_status    BIT(1)      DEFAULT NULL,
	txin_checksig_validation_status                 BIT(1)      DEFAULT NULL,
	txin_mature_coinbase_spend_validation_status    BIT(1)      DEFAULT NULL,

    -- indexes
    KEY tx_hash_index                                       (tx_hash),

    -- used to search for 'spent by' funds
    KEY prev_txout_hash_index                               (prev_txout_hash),

    KEY address_index                                       (address),
    KEY alternate_address                                   (alternate_address),
    KEY shared_funds_index                                  (shared_funds),

	KEY txin_coinbase_hash_validation_status_index
    (txin_coinbase_hash_validation_status), 

	KEY txin_hash_validation_status_index
    (txin_hash_validation_status), 

	KEY txin_coinbase_index_validation_status_index
    (txin_coinbase_index_validation_status), 

	KEY txin_index_validation_status_index
    (txin_index_validation_status), 

	KEY txin_single_spend_validation_status_index
    (txin_single_spend_validation_status), 

	KEY txin_spend_from_non_orphan_validation_status_index
    (txin_spend_from_non_orphan_validation_status), 

	KEY txin_checksig_validation_status_index
    (txin_checksig_validation_status), 

	KEY txin_mature_coinbase_spend_validation_status_index
    (txin_mature_coinbase_spend_validation_status) 

) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS blockchain_txouts (
    -- data parsed from the txins
    tx_hash             BINARY(32)      NOT NULL,
    txout_num           INT(4)          NOT NULL,

    -- max = 21,000,000 btc = 21 x 10^14 sat
    txout_funds                                     INT(15)     NOT NULL,

    address                                         VARCHAR(34) DEFAULT NULL,

    alternate_address                               VARCHAR(34) DEFAULT NULL
    COMMENT 'the compressed/uncompressed equivalent address if known',


	-- only check the standard address. there is no point checking the addresses
	-- we create from pubkeys since these must be correct
	txout_standard_script_address_checksum_validation_status,

	# TODO - implement this
	# for a standard p2pkh script, validate that the pubkey maps to the given
	# address and not to the (un)compressed alternate address
	tx_pubkey_to_address_validation_status





	txout_script_length
	txout_script
	txout_script_list
	txout_script_format

	-- the only way a pubkey is identified here is if the txout script matches
    -- a standard format.
	txout_standard_script_pubkey,

	# a list of addresses taken directly from the txout script (not derived from
	# pubkeys). note that this list may contain p2sh addresses. as with pubkeys,
	# there is no guarantee that these addresses are spendable or even valid.
	# the only way an address is identified here is if the txout script matches
	# a standard format.
	"txout_standard_script_address",

) ENGINE=InnoDB;

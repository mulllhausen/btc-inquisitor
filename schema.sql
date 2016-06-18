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
    block_height                    INT(7)     NOT NULL,
    block_hash                      BINARY(32) NOT NULL,
    previous_block_hash             BINARY(32) NOT NULL,
    version                         INT(10)    NOT NULL, -- 4 bytes = 4294967295
    merkle_root                     BINARY(32) NOT NULL,
    timestamp                       INT(10)    NOT NULL, -- 4 bytes
    bits                            BINARY(4)  NOT NULL, -- 4 bytes
    nonce                           INT(10)    NOT NULL, -- 4 bytes
    block_size                      INT(10)    NOT NULL, -- something big
    num_txs                         INT(10)    NOT NULL, -- > 56000tx/s of visa

    -- data processed from the block headers
    orphan_status                   BIT(1)     NOT NULL DEFAULT b'0' COMMENT
    '1=orphan,0=not orphan',

    merkle_root_validation_status   BIT(1)     DEFAULT NULL,
    bits_validation_status          BIT(1)     DEFAULT NULL COMMENT
    'do the previous bits and time to mine 2016 blocks produce these bits?',

    difficulty_validation_status    BIT(1)     DEFAULT NULL COMMENT
    'is the difficulty > 1?',

    block_hash_validation_status    BIT(1)     DEFAULT NULL COMMENT
    'is the block hash below the target?',

    block_size_validation_status    BIT(1)     DEFAULT NULL COMMENT
    'is the block size less than the permitted maximum?',

    block_version_validation_status BIT(1)     DEFAULT NULL COMMENT
    'versions must coincide with block height ranges',

    -- indexes
    KEY block_height_index                    (block_height),
    KEY block_hash_index                      (block_hash),
    KEY merkle_root_validation_status_index   (merkle_root_validation_status),
    KEY bits_validation_status_index          (bits_validation_status),
    KEY difficulty_validation_status_index    (difficulty_validation_status),
    KEY block_hash_validation_status_index    (block_hash_validation_status),
    KEY block_size_validation_status_index    (block_size_validation_status),
    KEY block_version_validation_status_index (block_version_validation_status)

) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS blockchain_txs (
    -- joins
    block_hash   BINARY(32) NOT NULL,

    -- data parsed from the tx bytes
    tx_num       INT(10)    NOT NULL, -- same as blockchain_headers.num_txs
    tx_hash      BINARY(32) NOT NULL,
    tx_version   INT(10)    NOT NULL, -- 4 bytes = 4294967295
    num_txins    INT(10)    NOT NULL, -- 8 bytes = 18446744073709551615
    num_txouts   INT(10)    NOT NULL, -- 8 bytes
    tx_lock_time INT(10)    NOT NULL, -- 4 bytes
    tx_size      INT(10)    NOT NULL, -- same as blockchain_headers.block_size
    tx_change    INT(16)    NOT NULL, -- same as blockchain_txouts.funds

    tx_lock_time_validation_status         BIT(1) DEFAULT NULL,
    tx_funds_balance_validation_status     BIT(1) DEFAULT NULL,
    tx_pubkey_to_address_validation_status BIT(1) DEFAULT NULL,

    -- indexes
    KEY block_hash_index                     (block_hash),
    KEY tx_num_index                         (tx_num),
    KEY tx_hash_index                        (tx_hash),

    KEY tx_lock_time_validation_status_index (tx_lock_time_validation_status),

    KEY tx_funds_balance_validation_status_index
    (tx_funds_balance_validation_status),

    KEY tx_pubkey_to_address_validation_status_index
    (tx_pubkey_to_address_validation_status)

) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS blockchain_txins (
    -- joins
    tx_hash           BINARY(32)        NOT NULL,

    -- data parsed from the txins
    txin_num           INT(10)          NOT NULL,
    prev_txout_hash    BINARY(32)       NOT NULL,
    prev_txout_num     INT(4)           NOT NULL,
    script_length      INT(5)           NOT NULL,
    script             VARBINARY(10000) NOT NULL, -- max 10,000 bytes
    txin_sequence_num  INT(10)          NOT NULL, -- 4 bytes = 4294967295

    -- data processed from the txins
    script_format                                   VARCHAR(20) DEFAULT NULL,
    pubkey                                          BINARY(65)  DEFAULT NULL,
    txin_coinbase_change_funds                      INT(10)     NOT NULL,
    address                                         VARCHAR(34) DEFAULT NULL,

    alternate_address                               VARCHAR(34) DEFAULT NULL
    COMMENT 'the compressed/uncompressed equivalent address if known',

    shared_funds                                    BIT(1)      DEFAULT NULL
    COMMENT 'are multiple pubkeys in charge of the same funds?',

    -- same as blockchain_txout.funds
    funds                                           INT(16)     NOT NULL,

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
    KEY pubkey_index                                        (pubkey),
    KEY address_index                                       (address),
    KEY alternate_address_index                             (alternate_address),
    KEY shared_funds_index                                  (shared_funds),

    -- join tx_hash to this to search for 'spent by' funds
    KEY prev_txout_hash_index                               (prev_txout_hash),
    KEY prev_txout_num_index                                (prev_txout_num),

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
    -- joins
    tx_hash BINARY(32)       NOT NULL,

    -- data parsed from the txins
    txout_num     INT(10)          NOT NULL,
    script_length INT(5)           NOT NULL,
    script        VARBINARY(10000) NOT NULL, -- max 10,000 bytes
    funds         INT(16)          NOT NULL, -- 8 bytes = 18446744073709551615

    -- data processed from the txins
    script_format                                      VARCHAR(20) DEFAULT NULL,
    pubkey                                             BINARY(65)  DEFAULT NULL,
    address                                            VARCHAR(34) DEFAULT NULL,

    alternate_address                                  VARCHAR(34) DEFAULT NULL
    COMMENT 'the compressed/uncompressed equivalent address if known',

    shared_funds                                       BIT(1)      DEFAULT NULL
    COMMENT 'are multiple pubkeys in charge of the same funds?',

    -- only check the standard address. there is no point checking the addresses
    -- we create from pubkeys since these must be correct
    standard_script_address_checksum_validation_status BIT(1) DEFAULT NULL,

    -- for a standard p2pkh script, validate that the pubkey maps to the given
    -- address and not to the (un)compressed alternate address
    pubkey_to_address_validation_status                BIT(1) DEFAULT NULL,

    -- indexes
    KEY tx_hash_index           (tx_hash),
    KEY pubkey_index            (pubkey),
    KEY address_index           (address),
    KEY alternate_address_index (alternate_address),
    KEY shared_funds_index      (shared_funds),

    KEY standard_script_address_checksum_validation_status_index
    (standard_script_address_checksum_validation_status),

    KEY pubkey_to_address_validation_status_index
    (pubkey_to_address_validation_status)

) ENGINE=InnoDB;

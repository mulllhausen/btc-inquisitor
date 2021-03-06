CREATE TABLE IF NOT EXISTS map_addresses_to_txs (
    blockheight         int(11)     NOT NULL,
    txhash              binary(32)  NOT NULL,
    txin_num            int(11)     DEFAULT NULL,
    txout_num           int(11)     DEFAULT NULL,
    address             varchar(34) DEFAULT NULL,
    alternate_address   varchar(34) DEFAULT NULL COMMENT 'the compressed/uncompressed equivalent address if known',
    txout_script_format varchar(10) DEFAULT NULL,
    shared_funds        bit(1)      DEFAULT NULL COMMENT 'are multiple pubkeys in charge of the same funds?',
    orphan_block        bit(1)      NOT NULL DEFAULT b'0' COMMENT '0=false,1=true',
    KEY blockheight_index       (blockheight),
    KEY txhash_index            (txhash),
    KEY address_index           (address),
    KEY alternate_address_index (alternate_address),
    KEY shared_funds_index      (shared_funds)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

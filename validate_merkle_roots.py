#!/usr/bin/env python2.7
"validate all merkle roots in the supplied block range"

import sys
import btc_grunt
import queries
import get_tx_from_db
import get_block_from_db
import lang_grunt
import progress_meter

modes = ["db-update", "db-check"]

def validate_script_usage():
    usage = "\n\nUsage: ./validate_merkle_roots.py <startblock> <endblock> " \
    "<mode>\n" \
    "where <mode> can be %s:\n" \
    "- db-update - only check and update the status of blocks that have not\n" \
    "already been validated and had their status saved in the db.\n" \
    "- db-recheck - only check the status of blocks that have already been\n" \
    " validated and had their status saved in the db. report on any failures." \
    % (lang_grunt.list2human_str(modes, "or"))

    if len(sys.argv) < 3:
        raise ValueError(usage)
    try:
        (_, _, mode) = get_stdin_params()
        if mode not in modes:
            raise ValueError(usage)
    except:
        raise ValueError(usage)

def get_stdin_params():
    block_height_start = int(sys.argv[1])
    block_height_end = int(sys.argv[2])
    mode = sys.argv[3]
    return (block_height_start, block_height_end, mode)

def process_range(block_height_start, block_height_end, mode):
    merkle_root_status = "any"
    blocks_to_check = queries.get_blocks_with_merkle_root_status(
        merkle_root_status, block_height_start, block_height_end
    )

    num_blocks_to_check = len(blocks_to_check)
    invalid_blocks = []
    for (i, block_height) in enumerate(blocks_to_check):
        block_height = block_height["block_height"]
        progress_meter.render(
            100 * i / float(num_blocks_to_check),
            "validating block %d (final: %d)" % (block_height, block_height_end)
        )
        try:
            block = get_block_from_db.process_block_header_from_db(
                "blockheight", block_height, human_readable = False
            )
            valid = btc_grunt.valid_merkle_tree(block, explain = False)
            if mode == "db-update":
                queries.update_merkle_root_status(valid, block_height)
            elif mode == "db-check":
                if not valid:
                    invalid_blocks.append(block_height)
        except Exception as e:
            print "\n\n---------------------\n\n"
            filesystem_grunt.update_errorlog(e, prepend_datetime = True)
            raise

    progress_meter.render(
        100, "finished validating from block %d to %d\n" % (
            block_height_start, block_height_end
        )
    )
    if len(invalid_blocks):
        print "\ninvalid block heights:\n%s\n" % \
        "\n".join(str(block_height) for block_height in invalid_blocks)

if __name__ == '__main__':

    validate_script_usage()
    (block_height_start, block_height_end, mode) = get_stdin_params()

    process_range(block_height_start, block_height_end, mode)
    if "db-" in mode:
        queries.mysql_grunt.disconnect()

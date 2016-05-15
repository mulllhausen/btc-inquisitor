#!/usr/bin/env python2.7

"""
monitor the heartbeat of the tasklist manager and report when it fails - ie when
the tasklist manager has not completed its tasks in time.

this script runs constantly (with sleeps).
"""

import heartbeat_grunt
import config_grunt
import email_grunt
import time

while True:
    time.sleep(heartbeat_grunt.heartbeat_interval + 1)
    if not heartbeat_grunt.check("tasklist_manager"):
        email_grunt.send(
            "the tasklist manager failed to report back within %d seconds" % (
                heartbeat_grunt.heartbeat_interval
            )
        )

#!/usr/bin/env python2.7

"""manage the tasklist table in the bitcoin db"""

import time, sys, os
import heartbeat_grunt
import email_grunt
import map_addresses_to_txouts
import filesystem_grunt
import mysql_grunt

logfile = "/tmp/%s.errlog" % os.path.basename(sys.argv[0])
prepend_datetime = True

while(True):
    time.sleep(10) # check every 10 seconds for new tasks
    try:
        # put all tasks here. make sure to keep tasks very quick, otherwise this
        # will not run approx every 10 seconds
        map_addresses_to_txouts.manage()

    except Exception as e:
        email_grunt.send(email_grunt.standard_error_subject, e.msg)
        filesystem_grunt.update_logfile(logfile, e.msg, prepend_datetime)
        heartbeat.clear()
        mysql_grunt.disconnect()
        exit()

    heartbeat.clear()

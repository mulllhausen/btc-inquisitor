#!/usr/bin/env python2.7

import config_grunt
import subprocess
import os

mysql_config = config_grunt.config_dict["mysql"]

print "dumping db %s to file %s" % (
    mysql_config["db"], mysql_config["dumpfile"]
)
with open(mysql_config["dumpfile"], "w") as f: # w = truncate
    try:
        status = subprocess.call([
            "mysqldump",
            "-B", mysql_config["db"],
            "-u", mysql_config["user"],
            "-p%s" % mysql_config["passwd"],

            # export binary data in hex, since raw form may fail. thanks to
            # stackoverflow.com/a/31715391/339874
            "--hex-blob"
        ], stdout = f)
    except KeyboardInterrupt:
        print "\n\nctrl-c: exiting before the db dump is complete\n"
        exit(0)

if status is not 0:
    raise Exception("the db dump failed")

print "finished dumping the db"

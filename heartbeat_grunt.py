"""
module containing some general heartbeat-related functions.

the heartbeat is used to check if scheduled tasks are overdue. it does this by
writing the current time to a file under /tmp/heartbeat/taskname.
"""

import time, os
import filesystem_grunt

heartbeat_dir = "/tmp/heartbeat"
filesystem_grunt.make_sure_path_exists(heartbeat_dir)

def beat(taskname):
    # write the current time to /tmp/heartbeat/taskname
    with open("%s/%s" % (heartbeat_dir, taskname), "w") as f:
        f.write("%s" % time.time())

def end(taskname):
    # delete the /tmp/heartbeat/taskname file
    os.remove("%s/%s" % (heartbeat_dir, taskname))

def check(taskname, interval_seconds):
    # return true if it has not been more than interval_seconds since the last
    # heartbeat

    with open("%s/%s" % (heartbeat_dir, taskname), "r") as f:
        last_heartbeat_time = float(f.read())

    return ((last_heartbeat_time + interval_seconds) > time.time())

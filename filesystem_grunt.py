"""module containing some general filesystem-related functions"""

import os, errno, time

def make_sure_path_exists(path):
    # thanks to http://stackoverflow.com/a/5032238/339874
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

def update_logfile(filename, txt, prepend_datetime):
    prepended_datetime = "" if not prepend_datetime else "[%s] " % (
        time.strftime("%Y-%m-%d %H:%M:%S")
    )
    with open(filename, "a") as f:
        f.write("%s%s" % (prepended_datetime, txt))

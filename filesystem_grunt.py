"""module containing some general filesystem-related functions"""

import os, errno, time
import config_grunt

def make_sure_path_exists(path):
    # thanks to http://stackoverflow.com/a/5032238/339874
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

def update_errorlog(txt, prepend_datetime = True):
    prepended_datetime = "" if not prepend_datetime else "[%s] " % (
        time.strftime("%Y-%m-%d %H:%M:%S")
    )
    with open(config_grunt.config_dict["error_logfile"], "a") as f:
        f.write("%s%s\n" % (prepended_datetime, txt))

make_sure_path_exists(
    os.path.dirname(config_grunt.config_dict["error_logfile"])
)

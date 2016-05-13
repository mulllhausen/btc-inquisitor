"""module containing some general filesystem-related functions"""

import os, errno

def make_sure_path_exists(path):
    # thanks to http://stackoverflow.com/a/5032238/339874
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

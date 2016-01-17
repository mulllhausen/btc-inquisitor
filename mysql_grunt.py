"""module containing some general mysql-related functions"""

import re

def clean_query(cmd):
    """only use this function if the data contains no whitespace to preserve"""
    return re.sub("\s+", " ", cmd).strip()
    #return cmd.replace("\n", " ").replace("\t", "").strip() # quicker?

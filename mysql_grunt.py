"""module containing some general mysql-related functions"""

import MySQLdb, re
import config_grunt

def connect():
    "connect, do quick setup, and return the cursor"
    global cursor
    mysql_connection_params = config_grunt.config_dict["mysql"]
    mysql_db = MySQLdb.connect(**mysql_connection_params)
    mysql_db.autocommit(True)
    cursor = mysql_db.cursor(MySQLdb.cursors.DictCursor)

# connect when this module is imported
connect()

def quick_fetch(cmd, do_clean_query):
    "function for select statements where the result is required"
    global cursor
    if do_clean_query:
        cmd = clean_query(cmd)
    cursor.execute(cmd)
    return cursor.fetchall()

def execute(cmd, do_clean_query):
    """
    function for any mysql statements where there may be no result, or we don't
    care about the result. eg: updates, inserts, selects for a rowcount only.
    """
    global cursor
    if do_clean_query:
        cmd = clean_query(cmd)
    cursor.execute(cmd)

def clean_query(cmd):
    "only use this function if the data contains no whitespace to preserve"
    return re.sub("\s+", " ", cmd).strip()
    #return cmd.replace("\n", " ").replace("\t", "").strip() # quicker?

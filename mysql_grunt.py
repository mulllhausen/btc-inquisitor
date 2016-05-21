"""module containing some general mysql-related functions"""

import MySQLdb, re
import config_grunt
import email_grunt
import filesystem_grunt

def connect():
    "connect and do setup"
    global cursor, mysql_db
    mysql_connection_params = config_grunt.config_dict["mysql"]
    try:
        mysql_db = MySQLdb.connect(**mysql_connection_params)
    except:
        # don't email the exception message in case it contains the password
        msg = "failed to connect to mysql database"
        email_grunt.send(msg)
        filesystem_grunt.update_errorlog(msg)
        exit()

    mysql_db.autocommit(True)
    cursor = mysql_db.cursor(MySQLdb.cursors.DictCursor)

# connect when this module is imported
connect()

def disconnect():
    mysql_db.close()

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

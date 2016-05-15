"""
module containing some general heartbeat-related functions.

the heartbeat is used to check if scheduled tasks are overdue. heartbeats are
stored in the mysql tasklist table with name = 'heartbeat' and the specific
heartbeat task name in the details column.
"""

import time, os
import config_grunt
import mysql_grunt

heartbeat_interval = config_grunt.config_dict["heartbeat_interval"]

def beat(taskname):
    """
    close off all previous heartbeats in the tasklist table and begin a new
    heartbeat in the tasklist table
    """
    end(taskname)
    mysql_grunt.execute("""
        insert into tasklist set
        host = '%s',
        name = 'heartbeat',
        started = now(),
        details = '{"task":"%s"}'
    """ % (config_grunt.config_dict["unique_host_id"], taskname), True)

def end(taskname):
    mysql_grunt.execute("""
        update tasklist set ended = now()
        where host = '%s'
        and name = 'heartbeat'
        and ended is null
        and details = '{"task":"%s"}'
    """ % (config_grunt.config_dict["unique_host_id"], taskname), True)

def check(taskname):
    """
    True = pass, False = fail. return False if it has been more than
    heartbeat_interval since any heartbeat.
    """
    data = mysql_grunt.quick_fetch("""
        select count(*) as 'num_overdue'
        from tasklist
        where host = '%s'
        and name = 'heartbeat'
        and ended is null
        and details = '{"task":"%s"}'
        and (started + interval %d second) < now()
    """ % (
        config_grunt.config_dict["unique_host_id"], taskname, heartbeat_interval
    ), True)
    return (data[0]["num_overdue"] == 0)

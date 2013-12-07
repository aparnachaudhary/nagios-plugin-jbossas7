#!/usr/bin/env python

#
# A JBossAS 7.1.1-Final Nagios check script
#
# https://github.com/mzupan/nagios-plugin-mongodb is used as a reference for this.

#
# Main Author
#   - Aparna Chaudhary <aparna.chaudhary@gmail.com>
#
# USAGE
#
# See the README.asciidoc
#

import sys
import time
import optparse
import textwrap
import re
import os
import socket
import urllib2
import requests
from requests.auth import HTTPDigestAuth
from datetime import timedelta

try:
    import json
except ImportError:
    try:
        import simplejson as json
    except ImportError, e:
        print e
        sys.exit(2)



#
# TODO: Document
#
def optional_arg(arg_default):
    def func(option, opt_str, value, parser):
        if parser.rargs and not parser.rargs[0].startswith('-'):
            val = parser.rargs[0]
            parser.rargs.pop(0)
        else:
            val = arg_default
        setattr(parser.values, option.dest, val)
    return func

#
# TODO: Document
#
def performance_data(perf_data, params):
    data = ''
    if perf_data:
        data = " |"
        for p in params:
            p += (None, None, None, None)
            param, param_name, warning, critical = p[0:4]
            data += "%s=%s" % (param_name, str(param))
            if warning or critical:
                warning = warning or 0
                critical = critical or 0
                data += ";%s;%s" % (warning, critical)
                
            data += " "
            
    return data


#
# TODO: Document
#
def numeric_type(param):
    if ((type(param) == float or type(param) == int or param == None)):
        return True
    return False


#
# TODO: Document
#
def check_levels(param, warning, critical, message, ok=[]):
    if (numeric_type(critical) and numeric_type(warning)):
        if param >= critical:
            print "CRITICAL - " + message
            sys.exit(2)
        elif param >= warning:
            print "WARNING - " + message
            sys.exit(1)
        else:
            print "OK - " + message
            sys.exit(0)
    else:
        if param in critical:
            print "CRITICAL - " + message
            sys.exit(2)

        if param in warning:
            print "WARNING - " + message
            sys.exit(1)

        if param in ok:
            print "OK - " + message
            sys.exit(0)

        # unexpected param value
        print "CRITICAL - Unexpected value : %d" % param + "; " + message
        return 2


#
# TODO: Document
#
def get_digest_auth_json(host, port, uri, user, password, payload):
    try:
        url = base_url(host, port) + uri
        res = requests.get(url, params=payload, auth=HTTPDigestAuth(user, password))
        return res.json()
    except Exception, e:
        # The server could be down; make this CRITICAL.
        return exit_with_general_critical(e)

#
# TODO: Document
#
def post_digest_auth_json(host, port, uri, user, password, payload):
    try:
        url = base_url(host, port) + uri
        headers = {'content-type': 'application/json'}        
        res = requests.post(url, data=json.dumps(payload), headers=headers, auth=HTTPDigestAuth(user, password))
        return res.json()
    except Exception, e:
        # The server could be down; make this CRITICAL.
        return exit_with_general_critical(e)

#
# TODO: Document
#
def base_url(host, port):
    url = "http://{host}:{port}/management".format(host=host,port=port)
    return url
#
# TODO: Document
#
def main(argv):
    p = optparse.OptionParser(conflict_handler="resolve", description="This Nagios plugin checks the health of JBossAS.")

    p.add_option('-H', '--host', action='store', type='string', dest='host', default='127.0.0.1', help='The hostname you want to connect to')
    p.add_option('-P', '--port', action='store', type='int', dest='port', default=9990, help='The port JBoss management console is runnung on')
    p.add_option('-u', '--user', action='store', type='string', dest='user', default=None, help='The username you want to login as')
    p.add_option('-p', '--pass', action='store', type='string', dest='passwd', default=None, help='The password you want to use for that user')
    p.add_option('-W', '--warning', action='store', dest='warning', default=None, help='The warning threshold we want to set')
    p.add_option('-C', '--critical', action='store', dest='critical', default=None, help='The critical threshold we want to set')
    p.add_option('-A', '--action', action='store', type='choice', dest='action', default='server_status', help='The action you want to take',
                 choices=['server_status','heap_usage', 'non_heap_usage', 'gctime_percent', 'queue_depth'])
    p.add_option('-D', '--perf-data', action='store_true', dest='perf_data', default=False, help='Enable output of Nagios performance data')
    p.add_option('-m', '--memoryvalue', action='store', dest='memory_value', default='used', help='The memory value type to check [max|init|used|committed] from heap_usage and non_heap_usage')
    p.add_option('-g', '--gctype', action='store', dest='gc_type', default='PS_MarkSweep', help='The GC type to check [PS_MarkSweep|PS_Scavenge] from gctime_percent')
    p.add_option('-q', '--queuename', action='store', dest='queue_name', default=None, help='The queue name for which you want to retrieve queue depth')

    options, arguments = p.parse_args()
    host = options.host
    port = options.port
    user = options.user
    passwd = options.passwd
    memory_value = options.memory_value
    gc_type = options.gc_type
    queue_name = options.queue_name
    if (options.action == 'server_status'):
        warning = str(options.warning or "")
        critical = str(options.critical or "")
    else:
        warning = float(options.warning or 0)
        critical = float(options.critical or 0)

    action = options.action
    perf_data = options.perf_data
    #
    # moving the login up here and passing in the connection
    #
    start = time.time()

    if action == "server_status":
        return check_server_status(host, port, user, passwd, warning, critical, perf_data)
    elif action == "gctime_percent":
        return check_gctime_percent(host, port, user, passwd, gc_type, warning, critical, perf_data)
    elif action == "queue_depth":
        return check_queue_depth(host, port, user, passwd, queue_name, warning, critical, perf_data)
    elif action == "heap_usage":
        return check_heap_usage(host, port, user, passwd, memory_value, warning, critical, perf_data)
    elif action == "non_heap_usage":
        return check_non_heap_usage(host, port, user, passwd, memory_value, warning, critical, perf_data)
    else:
        return check_connect(host, port, warning, critical, perf_data, user, passwd, conn_time)


def exit_with_general_warning(e):
    if isinstance(e, SystemExit):
        return e
    else:
        print "WARNING - General JbossAS warning:", e
    return 1


def exit_with_general_critical(e):
    if isinstance(e, SystemExit):
        return e
    else:
        print "CRITICAL - General JbossAS Error:", e
    return 2


def check_server_status(host, port, user, passwd, warning, critical, perf_data):
    warning = warning or ""
    critical = critical or ""
    ok = "running"
    
    try:
        payload = {'operation': 'read-attribute', 'name': 'server-state'}
        url = base_url(host, port)
        res = post_digest_auth_json(host, port, url,user, passwd, payload)
        res = res['result']
        
        message = "Server Status '%s'" % res
        message += performance_data(perf_data, [(res, "server_status", warning, critical)])
    
        return check_levels(res, warning, critical, message, ok)
    except Exception, e:
        return exit_with_general_critical(e)


def check_heap_usage(host, port, user, passwd, memory_value, warning, critical, perf_data):
    warning = warning or 512
    critical = critical or 1024
    
    try:
        if memory_value not in ['max', 'init', 'used', 'committed']:
            return exit_with_general_critical("The memory value type of '%s' is not valid" % memory_value)
        
        payload = {'include-runtime': 'true'}
        url = "/core-service/platform-mbean/type/memory"
        
        res = get_digest_auth_json(host, port, url,user, passwd, payload)
        res = res['heap-memory-usage'][memory_value] / (1024*1024)
        
        message = "Heap Memory '%s' %s MiB" % (memory_value, res)
        message += performance_data(perf_data, [(res, "heap_usage", warning, critical)])
    
        return check_levels(res, warning, critical, message)
    except Exception, e:
        return exit_with_general_critical(e)

def check_non_heap_usage(host, port, user, passwd, memory_value, warning, critical, perf_data):
    warning = warning or 128
    critical = critical or 256
    
    try:
        if memory_value not in ['max', 'init', 'used', 'committed']:
            return exit_with_general_critical("The memory value type of '%s' is not valid" % memory_value)
            
        payload = {'include-runtime': 'true'}
        url = "/core-service/platform-mbean/type/memory"
        
        res = get_digest_auth_json(host, port, url,user, passwd, payload)
        res = res['non-heap-memory-usage'][memory_value] / (1024*1024)
        
        message = "Non Heap Memory '%s' %s MiB" % (memory_value, res)
        message += performance_data(perf_data, [(res, "non_heap_usage", warning, critical)])
    
        return check_levels(res, warning, critical, message)
    except Exception, e:
        return exit_with_general_critical(e)

def check_gctime_percent(host, port, user, passwd, gc_type, warning, critical, perf_data):
    # Make sure you configure right values for your application    
    warning = warning or 0.5
    critical = critical or 1.0
    
    try:
        if gc_type not in ['PS_MarkSweep', 'PS_Scavenge']:
            return exit_with_general_critical("The GC type of '%s' is not valid" % gc_type)
            
        url = "/core-service/platform-mbean/type/runtime"
        res = get_digest_auth_json(host, port, url,user, passwd, None)
        uptime = res['uptime']
        
        payload = {'include-runtime': 'true', 'recursive':'true'}
        url = "/core-service/platform-mbean/type/garbage-collector"
        res = get_digest_auth_json(host, port, url,user, passwd, payload)
        gctime = res['name'][gc_type]['collection-time']
        
        percent = float(gctime*100)/uptime
        
        message = "GC percentage for '%s'  %s " %(gc_type, percent)
        message += performance_data(perf_data, [(percent, "gctime_percent", warning, critical)])
    
        return check_levels(percent, warning, critical, message)
    except Exception, e:
        return exit_with_general_critical(e)

def check_queue_depth(host, port, user, passwd, queue_name, warning, critical, perf_data):
    warning = warning or 100
    critical = critical or 200
    
    try:    
        if queue_name is None:
            return exit_with_general_critical("The queue name '%s' is not valid" % queue_name)
            
        payload = {'include-runtime': 'true', 'recursive':'true'}
        url = "/subsystem/messaging/hornetq-server/default"
        
        res = get_digest_auth_json(host, port, url,user, passwd, payload)
        res = res['jms-queue'][queue_name]['delivering-count']
        
        message = "Queue Depth %s" % res
        message += performance_data(perf_data, [(res, "queue_depth", warning, critical)])
    
        return check_levels(res, warning, critical, message)
    except Exception, e:
        return exit_with_general_critical(e)

def build_file_name(host, action):
    #done this way so it will work when run independently and from shell
    module_name = re.match('(.*//*)*(.*)\..*', __file__).group(2)
    return "/tmp/" + module_name + "_data/" + host + "-" + action + ".data"


def ensure_dir(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)


def write_values(file_name, string):
    f = None
    try:
        f = open(file_name, 'w')
    except IOError, e:
        #try creating
        if (e.errno == 2):
            ensure_dir(file_name)
            f = open(file_name, 'w')
        else:
            raise IOError(e)
    f.write(string)
    f.close()
    return 0


def read_values(file_name):
    data = None
    try:
        f = open(file_name, 'r')
        data = f.read()
        f.close()
        return 0, data
    except IOError, e:
        if (e.errno == 2):
            #no previous data
            return 1, ''
    except Exception, e:
        return 2, None


def calc_delta(old, new):
    delta = []
    if (len(old) != len(new)):
        raise Exception("unequal number of parameters")
    for i in range(0, len(old)):
        val = float(new[i]) - float(old[i])
        if val < 0:
            val = new[i]
        delta.append(val)
    return 0, delta


def maintain_delta(new_vals, host, action):
    file_name = build_file_name(host, action)
    err, data = read_values(file_name)
    old_vals = data.split(';')
    new_vals = [str(int(time.time()))] + new_vals
    delta = None
    try:
        err, delta = calc_delta(old_vals, new_vals)
    except:
        err = 2
    write_res = write_values(file_name, ";" . join(str(x) for x in new_vals))
    return err + write_res, delta


#
# main app
#
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

from flask import (Flask,
                   request,
                   abort,
                   )
import os
import psutil
import threading


# Flask app
app = Flask(__name__,
            static_folder='static', static_url_path='',
            instance_relative_config=True)
CONFIG = os.environ.get('CONFIG') or 'config.Development'
app.config.from_object('config.Default')
app.config.from_object(CONFIG)

# logging
import logging
from log.config import LoggingConfiguration
LoggingConfiguration.set(
    logging.DEBUG if os.getenv('DEBUG') else logging.INFO,
    'lightop.log', name='Web')


import json
from functools import wraps
import subprocess
import time


RUNNING = False
KILL_VNC_AFTER = 15
NO_VNC_CONN_FOR = 0


def start_vnc_check_timer():
    global NO_VNC_CONN_FOR
    NO_VNC_CONN_FOR = 0
    vnc_check_timer()


def vnc_check_timer():
    global RUNNING, KILL_VNC_AFTER, NO_VNC_CONN_FOR

    if not RUNNING:
        return

    if NO_VNC_CONN_FOR >= KILL_VNC_AFTER:
        # stop VNC
        subprocess.check_call(r"supervisorctl stop all", shell=True)

        # check all running
        for i in xrange(20):
            output = subprocess.check_output(r"supervisorctl status | grep RUNNING | wc -l", shell=True)
            if output.strip() == "0":
                RUNNING = False
                return
            time.sleep(2)
        abort(500, 'service is not ready, please restart container')
    else:
        # Check if there is at least one vnc connection
        x11vnc_pid = [proc.pid for proc in psutil.process_iter() if proc.name() == "x11vnc"]
        if len(x11vnc_pid) != 1:
            NO_VNC_CONN_FOR += 1
        else:
            x11vnc_pid = x11vnc_pid[0]
            connections = psutil.net_connections()
            conns = [conn for conn in connections if conn.status == "ESTABLISHED" and conn.pid == x11vnc_pid]
            if len(conns) == 0:
                NO_VNC_CONN_FOR += 1
            else:
                NO_VNC_CONN_FOR = 0

        t = threading.Timer(1.0, vnc_check_timer)
        t.daemon = True
        t.start()



def exception_to_json(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        except (BadRequest,
                KeyError,
                ValueError,
                ) as e:
            result = {'error': {'code': 400,
                                'message': str(e)}}
        except PermissionDenied as e:
            result = {'error': {'code': 403,
                                'message': ', '.join(e.args)}}
        except (NotImplementedError, RuntimeError, AttributeError) as e:
            result = {'error': {'code': 500,
                                'message': ', '.join(e.args)}}
        return json.dumps(result)
    return wrapper


class PermissionDenied(Exception):
    pass


class BadRequest(Exception):
    pass


HTML_INDEX = '''<html><head>
    <script type="text/javascript">
        var w = window,
        d = document,
        e = d.documentElement,
        g = d.getElementsByTagName('body')[0],
        x = w.innerWidth || e.clientWidth || g.clientWidth,
        y = w.innerHeight|| e.clientHeight|| g.clientHeight;
        window.location.href = "redirect.html?width=" + x + "&height=" + (parseInt(y));
    </script>
    <title>Page Redirection</title>
</head><body></body></html>'''


HTML_REDIRECT = '''<html><head>
    <script type="text/javascript">
        var port = window.location.port;
        if (!port)
            port = window.location.protocol[4] == 's' ? 443 : 80;
        window.location.href = "vnc.html?autoconnect=1&autoscale=0&quality=3";
    </script>
    <title>Page Redirection</title>
</head><body></body></html>'''


@app.route('/')
def index():
    if RUNNING:
        return HTML_REDIRECT
    return HTML_INDEX


@app.route('/redirect.html')
def redirectme():
    global RUNNING

    if RUNNING:
        return HTML_REDIRECT

    env = {'width': 1024, 'height': 768}
    if 'width' in request.args:
        env['width'] = request.args['width']
    if 'height' in request.args:
        env['height'] = request.args['height']

    # sed
    subprocess.check_call(r"sed -i 's#^command=/usr/bin/Xvfb.*$#command=/usr/bin/Xvfb :1 -screen 0 {width}x{height}x16#' /etc/supervisor/conf.d/supervisord.conf".format(**env),
                          shell=True)
    # supervisorctrl reload
    subprocess.check_call(r"supervisorctl reload", shell=True)
    subprocess.check_call(r"supervisorctl start all", shell=True)

    # check all running
    for i in xrange(20):
        output = subprocess.check_output(r"supervisorctl status | grep RUNNING | wc -l", shell=True)
        if output.strip() == "6":
            RUNNING = True
            time.sleep(5) # make sure VNC is actually running before redirecting
            start_vnc_check_timer()
            return HTML_REDIRECT
        time.sleep(2)
    abort(500, 'service is not ready, please restart container')


if __name__ == '__main__':
    app.run(host=app.config['ADDRESS'], port=app.config['PORT'])

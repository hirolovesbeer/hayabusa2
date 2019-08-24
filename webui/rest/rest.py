
#
# run this command
# $ FLASK_APP=rest.py flask run
#
# request like this
# curl -X POST -H 'Accept:application/json' -H 'Content-Type:application/json' -d '{"start-time":"2019-05-08 09:15", "end-time":"2019-05-08 09:30", "match":"error", "user":"syslog", "password":"mvEPMNThq94LQuys68gR", "count":"true", "sum":"false", "exact":"false"}'  localhost:5000/
#

import os
import sys
import tempfile

sys.path.append(os.path.join(os.path.dirname(__file__), '../../lib'))

import logging
from logging.handlers import SysLogHandler

from hayabusa import HayabusaBase
from hayabusa.errors import HayabusaError, CLIClientError
from hayabusa.rest_client import RESTClient

from flask import Flask, request, jsonify
app = Flask(__name__)

def print_result(stderr, stdout, count, sum):
    if stderr:
        return eys.stderr.write(stderr.rstrip() + '\n')
    if stdout:
        if count and sum:
            return sys.stdout.write(stdout + '\n')
        else:
            with tempfile.TemporaryFile() as f:
                f.write(stdout.encode('utf-8'))
                f.seek(0)
                max_lines = 100
                lines = f.readlines(max_lines)
                while lines:
                    for line in lines:
                        if line == b'\n':
                            continue
                        sys.stdout.write(line.decode('utf-8'))
                    lines = f.readlines(max_lines)


@app.route('/', methods=['POST'])
def post_json():
    json = request.get_json()

    start_time = json['start-time']
    end_time = json['end-time']
    match = json['match']
    user = json['user']
    password = json['password']
    count = True if json['count'].lower() == 'true' else False
    sum = True if json['sum'].lower() == 'true' else False
    exact = True if json['exact'].lower() == 'true' else False

    stdout = ''
    stderr = ''
    exit_status = None
    data = None
    request_id = None

    HB = HayabusaBase()
    config = HB.load_config()
    print(config)
    logger = HB.set_logger('hayabusa-restapi', logging.DEBUG, False)

    try:
        client = RESTClient(config, logger)
        request_id, data = client.search(user, password, match,
                                                  start_time, end_time,
                                                  count, sum, exact)
        try:
            stdout = data['stdout']
            stderr = data['stderr']
            exit_status = data['exit_status']
        except KeyError as e:
            raise CLIClientError('Not Found %s in Received Data' % e)
        if type(exit_status) != int:
            err = 'Invalid exit status (not int) Received: %s (type: %s)'
            raise CLIClientError(err % (exit_status, type(exit_status)))
    except HayabusaError as e:
        sys.stderr.write('%s: %s\n' % (e.__class__.__name__, e))
        exit(1)
    except Exception as e:
        sys.stderr.write('Unexpected Error: %s, %s\n\n' %
                         (e.__class__.__name__, e))
        raise

    result = {}
    result['result'] = data['stdout']
    result['error'] = data['stderr']

    return jsonify(result)

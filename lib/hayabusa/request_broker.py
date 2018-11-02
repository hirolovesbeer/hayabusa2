import copy
import json
import os
import re
import shlex
import socket
import threading
import time
import uuid
from datetime import datetime
from multiprocessing import Lock, Manager

import bcrypt
import falcon
import yaml
import zmq

from hayabusa import HayabusaBase
from hayabusa.constants import Status, CompletedStatus
from hayabusa.db_file_path import db_file_path, \
    parse_start_time, parse_end_time
from hayabusa.errors import HayabusaError, AuthenticationError, BadRequest, \
    unexpected_error
from hayabusa.utils import time_str


class RequestBroker(HayabusaBase):
    USER_LIST_FILE = 'users.yml'

    def __init__(self):
        super().__init__('request-broker')
        self.logger.info('========================='
                         ' Starting Request Broker '
                         '=========================')
        self.users = self.load_users()

        manager = Manager()
        self.requests = manager.dict()
        self.requests_lock = Lock()

        # -------- Config --------
        config = self.config
        self.store_dir = config['path']['base-dir']
        self.sender_port = config['port']['command']
        self.receiver_port = config['port']['result']
        self.max_search_days = int(config['limit']['max-search-days'])
        self.request_borker_host = config['request-broker']['host']
        self.request_timeout = \
            float(config['request-broker']['request-timeout'])
        self.request_monitor_check_interval = \
            float(config['request-broker']['request-monitor-check-interval'])
        self.request_data_lifetime = \
            float(config['request-broker']['request-data-lifetime'])
        self.max_stderr_length = \
            int(config['request-broker']['max-stderr-length'])

        # -------- ZeroMQ --------
        self.logger.info('Listening Ports')
        sender_bind = 'tcp://*:%s' % self.sender_port
        receiver_bind = 'tcp://*:%s' % self.receiver_port
        self.logger.info('Command PUSH: %s', sender_bind)
        self.logger.info('Result PULL: %s', receiver_bind)

        push_context = zmq.Context()
        self.sender = push_context.socket(zmq.PUSH)
        self.sender.bind(sender_bind)

        pull_context = zmq.Context()
        self.receiver = pull_context.socket(zmq.PULL)
        self.receiver.bind(receiver_bind)

    def elapsed_time(self, start):
        delta = datetime.now() - start
        e_time = 3600 * 24 * delta.days + delta.seconds + \
            delta.microseconds / 1000000.0
        return e_time

    def load_users(self):
        file = os.path.join(HayabusaBase.etc_dir, self.USER_LIST_FILE)
        try:
            self.logger.debug('loading user list (YAML): %s', file)
            with open(file, 'r') as f:
                users = yaml.load(f)
            if type(users) != dict:
                raise HayabusaError('Invalid user list format: %s' % file)

        except Exception as e:
            self.critical_exit(e, 'Load Error: user list file: %s' % file)
        return users

    def notify_status(self, request_id, status, log_message):
        self.logger.debug('Status - %s - [%s] - %s',
                          request_id, status, log_message)

    def create_request(self, user, request_id, status, host, port,
                       log_message):
        with self.requests_lock:
            now = datetime.now()
            self.requests[request_id] = \
                {'user': user, 'status': status, 'data': None,
                 'host': host, 'port': port,
                 'updated': now, 'created': now}
        self.notify_status(request_id, status, log_message)

    def update_status(self, request_id, status, log_message, data=None):
        with self.requests_lock:
            if self.requests.get(request_id):
                tmp_data = copy.deepcopy(self.requests[request_id])
                tmp_data['status'] = status
                tmp_data['data'] = data
                tmp_data['updated'] = datetime.now()
                elapsed_time = self.elapsed_time(tmp_data['created'])
                self.requests[request_id] = tmp_data
                self.logger.debug('Update Status - %s - [%s] - [%s]',
                                  request_id, status, time_str(elapsed_time))
            else:
                raise HayabusaError('Unknown Request ID: %s' % request_id)
        self.notify_status(request_id, status, log_message)

    def timeout_error(self, request_id, host, port):
        context = zmq.Context()
        sender = context.socket(zmq.PUSH)
        sender.connect('tcp://%s:%s' %
                       (self.request_borker_host, self.receiver_port))
        message = {}
        message['type'] = 'timeout_error'
        message['id'] = request_id
        message['message'] = Status.RC_TimeoutError.name
        message['host'] = host
        message['port'] = port
        message['exit_status'] = 1
        message['stdout'] = ''
        message['stderr'] = 'Error: Request Timeout'
        sender.send_json(message)

    def request_monitor(self):
        self.logger.info('-------------'
                         ' Starting RequestMonitor '
                         '-------------')
        timeout = self.request_timeout
        interval = self.request_monitor_check_interval
        lifetime = self.request_data_lifetime * 60.0 * 60.0

        try:
            while True:
                time.sleep(interval)
                now = datetime.now()
                self.logger.debug('RequestMonitor: stored requests: %s',
                                  len(self.requests))
                for request_id, d in self.requests.items():
                    elapsed_time = self.elapsed_time(d['created'])
                    if d['status'] in CompletedStatus:
                        if elapsed_time > lifetime:
                            self.logger.debug('removing expired request'
                                              ' data: %s [%s]',
                                              request_id,
                                              time_str(elapsed_time))
                            with self.requests_lock:
                                if self.requests.get(request_id):
                                    del self.requests[request_id]
                    else:
                        if elapsed_time > timeout:
                            self.timeout_error(request_id,
                                               d['host'], d['port'])

        except Exception as e:
            unexpected_error(self.logger, 'RequestMonitor', e)
            raise

    def start_threads(self):
        self.logger.info('Starting Result Collector Thread')
        collector = threading.Thread(target=self.result_collector)
        collector.setDaemon(True)
        collector.start()

        tracker = threading.Thread(target=self.request_monitor)
        tracker.setDaemon(True)
        tracker.start()

    def log_progress(self, progress):
        for request_id, data in progress.items():
            self.logger.debug('Progress - %s - %s', request_id, data)

    def ignore_result(self, message):
        log_message = self.log_filter(message)
        self.logger.debug('Ignore Result: %s', log_message)

    def check_request_id(self, request_id):
        if self.requests.get(request_id):
            status = self.requests[request_id]['status']
            if status in CompletedStatus:
                raise HayabusaError('Completed Status: %s, %s' %
                                    (request_id, status))
        else:
            raise HayabusaError('Unknown Request ID: %s' % request_id)

    def get_host_port_from_post(self, data):
        try:
            host = data['host']
            port = data['port']
        except KeyError:
            raise BadRequest('Invalid Client Information: host or port')
        return (host, port)

    def get_host_port(self, request_id):
        host = self.requests[request_id]['host']
        port = self.requests[request_id]['port']
        return (host, port)

    def result_collector(self):
        self.logger.info('-------------'
                         ' Starting ResultCollector '
                         '-------------')
        message = {}
        results = {}
        progress = {}

        while True:
            try:
                message = self.receiver.recv_json()
                request_id = message['id']
                self.logger.debug('ResultCollector')
                self.check_request_id(request_id)
                if message['type'] == 'timeout_error':
                    self.update_status(request_id, Status.RC_TimeoutError,
                                       message)
                    if results.get(request_id):
                        del results[request_id]
                    if progress.get(request_id):
                        del progress[request_id]
                    self.send_result(request_id, message, update_status=False)
                    continue

                num_commands = message['commands']
                if not results.get(request_id):
                    results[request_id] = []
                    progress[request_id] = []
                    for _ in range(num_commands):
                        results[request_id].append(None)
                        progress[request_id].append(None)
                index = message['index']
                if message['type'] == 'notice':
                    self.notify_status(request_id, Status.RW_ReceivedCommand,
                                       message)
                    progress[request_id][index] = message['worker']
                    self.update_status(request_id, Status.WR_CollectingResults,
                                       message, data=progress[request_id])
                    self.log_progress(progress)
                    continue

                results[request_id][index] = message
                progress[request_id][index] = 'completed-' + message['worker']
                log_message = self.log_filter(message)
                self.notify_status(request_id, Status.WR_ReceivedResult,
                                   log_message)
                num_results = len([r for r in results[request_id] if r])
                label = '[%d/%d] #%d' % (num_results, num_commands, index)
                self.update_status(request_id, Status.WR_CollectingResults,
                                   label, data=progress[request_id])
                if num_results == num_commands:
                    self.update_status(request_id,
                                       Status.WR_ReceivedAllResults,
                                       log_message)
                    sum = message['sum']
                    result = self.consolidate_result(request_id, sum,
                                                     results[request_id])
                    del results[request_id]
                    del progress[request_id]
                    self.send_result(request_id, result, update_status=True)
                self.log_progress(progress)
            except HayabusaError as e:
                self.logger.error(str(e))
                self.ignore_result(message)
            except Exception as e:
                unexpected_error(self.logger, 'ResultCollector', e)

    def consolidate_result(self, request_id, sum_option, data):
        result = {}
        result['id'] = request_id

        sum_values = []
        result['exit_status'] = 0
        result['stdout'] = ''
        result['stderr'] = ''
        for r in data:
            if sum_option:
                try:
                    sum_values.append(int(r['stdout']))
                except ValueError as e:
                    self.logger.error('%s - %s', request_id, e)
            else:
                result['stdout'] += r['stdout']
            result['stderr'] += r['stderr']
            result['exit_status'] += r['exit_status']
        if sum_option:
            sum_value = sum(sum_values)
            self.logger.debug('%s - sum: %s, values: %s',
                              request_id, sum_value, sum_values)
            result['stdout'] = str(sum_value)

        # '| awk \'{m+=$1} END{print m;}' does not return non zero exit status.
        # But it returns standard errors.
        if 'unable to open database' in result['stderr']:
            result['stderr'] = 'Error: unable to open database file(s)'
        elif len(result['stderr']) > self.max_stderr_length:
            result['stderr'] = result['stderr'][:self.max_stderr_length] \
                               + '...'
        return result

    def send_result(self, request_id, message, update_status):
        host, port = self.get_host_port(request_id)
        args = (request_id, host, port, message, update_status)
        th = threading.Thread(target=self.send_result_base, args=args)
        th.setDaemon(True)
        th.start()

    def port_check(self, host, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        try:
            result = sock.connect_ex((host, port))
        except socket.error as e:
            self.logger.error('Cannot Connect %s, %s, %s' % (host, port, e))
            return False
        if result != 0:
            return False
        return True

    def send_result_base(self, request_id, host, port, message, update_status):
        log_message = self.log_filter(message)
        address = 'tcp://%s:%s' % (host, port)
        self.logger.debug('%s - connecting %s' % (request_id, address))

        if not self.port_check(host, port):
            self.logger.error('Cannot Connect %s, %s' % (address, log_message))
            return
        context = zmq.Context()
        sender = context.socket(zmq.PUSH)
        sender.connect(address)
        sender.send_json(message)
        if update_status:
            self.update_status(request_id, Status.RC_SentResult, log_message)

    def load_post_data(self, body):
        try:
            data = json.loads(body)
        except json.decoder.JSONDecodeError as e:
            raise BadRequest('Invalid JSON Format: %s' % body.decode())
        return data

    def internal_server_error(self, resp, e, log_message):
        unexpected_error(self.logger, 'RESTServer', e, log_message)
        resp.media = {'error': 'Internal Server Error'}
        resp.status = falcon.HTTP_500

    def hayabusa_error(self, resp, e, log_message, request_id=None):
        message = '[%s] %s, %s' % \
                  (Status.RC_RequestError, e.__class__.__name__, e)
        self.error_log(message, log_message, filter=False)
        if request_id:
            media = {'error': message, 'id': request_id}
        else:
            media = {'error': message}
        resp.media = media
        resp.status = falcon.HTTP_400

    def on_get(self, req, resp, request_id=None):
        log_message = ''
        try:
            if req.path.find('/v1/health_check') == 0:
                self.logger.debug('path: %s', req.path)
                resp.media = {'status': 'ok'}
            elif req.path.find('/v1/status/') == 0:
                body = req.stream.read()
                data = self.load_post_data(body)
                log_message = {'data': self.log_filter(data)}
                self.logger.debug('path: %s, body: %s', req.path, log_message)
                auth_user = self.authenticate(data)
                if request_id:
                    if self.requests.get(request_id):
                        user = self.requests[request_id]['user']
                        if auth_user != user:
                            raise BadRequest('Permission Denied: %s' %
                                             auth_user)
                        status = self.requests[request_id]['status']
                        data = self.requests[request_id]['data']
                        created = self.requests[request_id]['created']
                        updated = self.requests[request_id]['updated']
                        res = {'id': request_id, 'status': status.name,
                               'data': data,
                               'updated': updated.isoformat(),
                               'created': created.isoformat()}
                        self.logger.debug('status response: %s', res)
                        resp.media = res
                    else:
                        raise BadRequest('Invalid Request ID: %s' % request_id)
                else:
                    raise BadRequest('Invalid Parameters')
            else:
                resp.status = falcon.HTTP_404
        except HayabusaError as e:
            self.hayabusa_error(resp, e, log_message)
        except Exception as e:
            self.internal_server_error(resp, e, log_message)

    def on_post(self, req, resp):
        log_message = ''
        request_id = str(uuid.uuid1())
        try:
            body = req.stream.read()
            log_message = {'id': request_id, 'data': body.decode()}
            data = self.load_post_data(body)
            data['id'] = request_id
            log_message = self.log_filter(data)
            self.logger.debug('request path: %s, body: %s',
                              req.path, log_message)
            if req.path == '/v1/request':
                user = self.authenticate(data)
                host, port = self.get_host_port_from_post(data)
                self.create_request(user, request_id,
                                    Status.CR_ReceivedRequest,
                                    host, port, log_message)
                self.send_command(data)
                res_data = {'id': request_id}
                resp.media = res_data
            else:
                resp.status = falcon.HTTP_404
        except HayabusaError as e:
            self.hayabusa_error(resp, e, log_message, request_id=request_id)
        except Exception as e:
            self.internal_server_error(resp, e, log_message)

    def error_log(self, message, data, filter=True):
        if filter:
            log_message = self.log_filter(data)
        else:
            log_message = data
        self.logger.error('%s, %s' % (message, log_message))

    def authenticate(self, data):
        auth_error = AuthenticationError('Invalid user or password')
        try:
            user = data['user']
            password = data['password']
        except KeyError:
            error = 'Invalid Authentication Information'
            raise BadRequest(error)
        try:
            password_hash = self.users[user]
        except KeyError:
            message = "Invalid User: '%s'" % user
            self.error_log(message, data)
            raise auth_error
        if not bcrypt.checkpw(password.encode(), password_hash.encode()):
            message = "Password Mismatch: '%s'" % user
            self.error_log(message, data)
            raise auth_error
        return user

    def parse_time_period(self, start_time_str, end_time_str):
        try:
            start_time = parse_start_time(start_time_str)
            end_time = parse_end_time(end_time_str)
        except ValueError:
            error = 'Invalid Time Period: %s - %s ' \
                    '(format: YYYY-MM-DD [hh:mm] - YYYY-MM-DD [hh:mm])'
            raise BadRequest(error % (start_time_str, end_time_str))

        if start_time > end_time:
            message = 'Invalid Time Period: %s - %s' \
                      % (start_time, end_time)
            raise BadRequest(message)

        days = (end_time - start_time).days
        if days > self.max_search_days:
            message = 'Too Long Time Period: %sdays ' \
                      '(Max: %sdays)' % (days, self.max_search_days)
            raise BadRequest(message)
        return (start_time, end_time)

    def send_command(self, data):
        request_id = data['id']
        try:
            user = data['user']
            start_time_str = data['start_time']
            end_time_str = data['end_time']
            match = data['match']
            count = data['count']
            sum = data['sum']
            exact = data['exact']
        except KeyError:
            raise BadRequest('Invalid Parameters')

        if not count:
            sum = False

        if match is not None:
            empty_re = re.compile(r'^\s*$')
            if empty_re.match(match):
                match = None

        start_time, end_time = \
            self.parse_time_period(start_time_str, end_time_str)

        cmds = self.generate_commands(user, start_time, end_time,
                                      match, count, sum, exact)
        num_commands = len(cmds)
        for i, cmd in enumerate(cmds):
            message = {'id': request_id, 'command': cmd, 'sum': sum,
                       'index': i, 'commands': num_commands}
            self.sender.send_json(message)
            self.notify_status(request_id, Status.RW_SentCommand, message)
        log_message = self.log_filter(data)
        self.notify_status(request_id, Status.RW_SentAllCommands, log_message)

    def generate_sql(self, match, count, exact):
        if count:
            column = 'count(*)'
        else:
            column = '*'

        if not match:
            return 'select %s from syslog' % column

        # Notice:
        # This string-escaping is not enough safe for a production use.
        # Use a safer way for it.
        escaped_match = re.sub("'", "''", match)
        if exact:
            sql = '''select %s from syslog where logs match '"%s"';''' % \
                  (column, escaped_match)
        else:
            sql = '''select %s from syslog where logs match '%s';''' % \
                  (column, escaped_match)
        return sql

    def generate_db_file_paths(self, user, start_time, end_time):
        base_dir = os.path.join(self.store_dir, user)
        paths = db_file_path(base_dir, start_time, end_time)
        return paths

    def generate_commands(self, user, start_time, end_time,
                          match, count, sum, exact):

        paths = self.generate_db_file_paths(user, start_time, end_time)
        sql = self.generate_sql(match, count, exact)

        cmds = []
        # 'shlex.quote' turns str into a safe token in a shell command line.
        quoted_sql = shlex.quote(sql)
        for path in paths:
            cmd = 'parallel sqlite3 ::: %s ::: %s' % (path, quoted_sql)
            if count and sum:
                cmd += " | awk '{m+=$1} END{print m;}'"
            cmds.append(cmd)
        return cmds

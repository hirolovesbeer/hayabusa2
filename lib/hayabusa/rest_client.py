import json
import socket

import requests
import zmq

from hayabusa import HayabusaBase
from hayabusa.constants import Status
from hayabusa.errors import RESTClientError, RESTResultWaitTimeout


class RESTClient(HayabusaBase):
    endpoint_path = '/v1'
    json_headers = {'content-type': 'application/json'}

    def __init__(self, config, logger):
        super().__init__('rest-client', config=config, logger=logger)
        self.request_timeout = \
            int(self.config['request-broker']['request-timeout'])
        host = config['request-broker']['host']
        port = config['request-broker']['port']
        self.endpoint_url = 'http://%s:%s%s' % \
                            (host, port, RESTClient.endpoint_path)

    def listen_random_port(self):
        context = zmq.Context()
        receiver = context.socket(zmq.PULL)
        port = receiver.bind_to_random_port('tcp://*')
        host = socket.gethostbyname(socket.gethostname())
        return receiver, host, port

    def request_url(self, path):
        return self.endpoint_url + path

    def request_base(self, method, path, data=None):
        url = self.request_url(path)
        if method == 'get':
            func = requests.get
        elif method == 'post':
            func = requests.post
        else:
            raise RESTClientError('Error: Invalid Method: %s', method)

        if data:
            headers = RESTClient.json_headers
            request_data = json.dumps(data)
        else:
            headers = RESTClient.json_headers
            request_data = None

        log_message = '%s: %s' % (method.upper(), url)
        self.logger.debug(log_message)
        try:
            res = func(url, data=request_data, headers=headers)
            self.logger.debug('%s, Status Code: %s',
                              log_message, res.status_code)
        except requests.exceptions.ConnectionError as e:
            error = 'Cannot connect to Request Broker, %s' % e
            self.logger.error(error)
            raise RESTClientError(error)
        return res

    def post(self, path, data=None):
        return self.request_base('post', path, data=data)

    def get(self, path, data=None):
        return self.request_base('get', path, data=data)

    def health_check(self):
        path = '/health_check'
        url = self.request_url(path)
        try:
            res = self.get(path)
        except Exception as e:
            raise RESTClientError('Error: %s' % e)
        return url, res

    def receive_data(self, receiver, timeout=None):
        if timeout:
            polling_timeout = timeout * 1000
        else:
            # longer time than request-timeout
            polling_timeout = (self.request_timeout + 60) * 1000

        poller = zmq.Poller()
        poller.register(receiver, zmq.POLLIN)
        events = poller.poll(polling_timeout)
        if not events:
            raise RESTResultWaitTimeout('wait result timeout')
        else:
            return receiver.recv_json()

    def search(self, user, password, match, start_time, end_time,
               count, sum, exact, timeout=None):
        receiver, host, port = self.listen_random_port()

        request_id = self.search_base(user, password, match,
                                      start_time, end_time,
                                      count, sum, exact, host, port)

        try:
            data = self.receive_data(receiver, timeout)
            log_message = self.log_filter(data)
            self.logger.debug('[%s] - %s - %s', Status.RC_ReceivedResult,
                              request_id, log_message)
        except RESTResultWaitTimeout as e:
            error = '%s: %s' % (e, request_id)
            self.logger.error(error)
            raise RESTResultWaitTimeout(error)

        return request_id, data

    def response_status_code_error(self, status_code, text):
        error = 'Error: Response Status Code: %s, %s' % (status_code, text)
        self.logger.error(error)
        raise RESTClientError(error)

    def empty_response_error(self):
        error = 'Empty Response from Request Broker'
        self.logger.error(error)
        raise RESTClientError(error)

    def search_base(self, user, password, match, start_time, end_time,
                    count, sum, exact, host, port):
        params = {'user': user, 'password': password, 'match': match,
                  'start_time': start_time, 'end_time': end_time,
                  'count': count, 'sum': sum, 'exact': exact,
                  'host': host, 'port': port}
        log_message = self.log_filter(params)
        if self.logger:
            self.logger.debug('Request Parameters: %s', log_message)
        try:
            res = self.post('/request', params)
        except Exception as e:
            raise RESTClientError('Error: %s' % e)

        if self.logger:
            self.logger.debug('[%s] - %s', Status.CR_SentRequest, log_message)

        if res.status_code != 200:
            self.response_status_code_error(res.status_code, res.text)

        if not res.text:
            self.empty_response_error()

        data = res.json()
        error = data.get('error')
        if error:
            raise RESTClientError(error)

        request_id = data.get('id')
        if self.logger:
            self.logger.debug('[%s] %s - %s', Status.RC_ReceivedRequestID,
                              request_id, log_message)
        if not request_id:
            raise RESTClientError('Not Found Response with Request ID')
        return request_id

    def status(self, user, password, request_id):
        params = {'user': user, 'password': password}
        log_message = self.log_filter(params)
        if self.logger:
            self.logger.debug('Request Parameters: %s', log_message)
        try:
            res = self.get('/status/'+request_id, params)
        except Exception as e:
            raise RESTClientError('Error: %s' % e)

        if res.status_code != 200:
            self.response_status_code_error(res.status_code, res.text)

        if not res.text:
            self.empty_response_error()

        data = res.json()

        if self.logger:
            self.logger.debug('%s - %s', request_id, data)
        return data

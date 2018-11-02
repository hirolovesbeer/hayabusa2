import copy
import os
import subprocess
import time
from multiprocessing import Process
from setproctitle import setproctitle

import zmq

from hayabusa import HayabusaBase
from hayabusa.constants import Status
from hayabusa.errors import unexpected_error
from hayabusa.utils import time_str


class Worker(HayabusaBase):
    def __init__(self):
        super().__init__('worker')
        self.name = 'MainProcess'
        self.info('========================='
                  ' Starting Worker '
                  '=========================')
        setproctitle('hayabusa_worker')
        self.hostname = os.uname()[1]

        config = self.config
        self.num_processes = int(config['worker']['process'])
        self.request_borker_host = config['request-broker']['host']
        self.local_command_port = config['port']['worker-local']
        self.receiver_port = config['port']['command']
        self.sender_port = config['port']['result']
        self.bash_path = config['path']['bash']

        receiver_connect = 'tcp://%s:%s' % \
                           (self.request_borker_host, self.receiver_port)
        sender_bind = 'tcp://%s:%s' % ('127.0.0.1', self.local_command_port)
        self.info('Command PULL: %s', receiver_connect)
        self.info('Command Local PUSH: %s', sender_bind)

        pull_context = zmq.Context()
        self.main_receiver = pull_context.socket(zmq.PULL)

        self.main_receiver.connect(receiver_connect)

        push_context = zmq.Context()
        self.main_sender = push_context.socket(zmq.PUSH)
        self.main_sender.bind(sender_bind)

    def worker_label(self):
        return '%s-%s' % (self.hostname, self.name)

    def __log(self, logger, format, *args):
        logger('[%s] - %s', self.name, (format % args))

    def info(self, *args):
        self.__log(self.logger.info, *args)

    def debug(self, *args):
        self.__log(self.logger.debug, *args)

    def connect_ports(self):
        receiver_connect = 'tcp://%s:%s' % \
                           ('127.0.0.1', self.local_command_port)
        sender_connect = 'tcp://%s:%s' % \
                         (self.request_borker_host, self.sender_port)
        self.info('Command Local PULL: %s', receiver_connect)
        self.info('Result PUSH: %s', sender_connect)

        pull_context = zmq.Context()
        self.receiver = pull_context.socket(zmq.PULL)
        self.receiver.connect(receiver_connect)

        push_context = zmq.Context()
        self.sender = push_context.socket(zmq.PUSH)
        self.sender.connect(sender_connect)

    def start(self):
        self.info('Starting %s Worker Processes: %s', self.num_processes,
                  self.hostname)
        for i in range(self.num_processes):
            p = Process(target=self.main_loop, args=(i+1,))
            p.start()

        # Load balancing
        while True:
            message = self.main_receiver.recv()
            self.main_sender.send(message)

    def notify(self, message):
        new_message = copy.deepcopy(message)
        new_message['type'] = 'notice'
        new_message['worker'] = self.worker_label()
        new_message['message'] = Status.RW_ReceivedCommand.name
        self.sender.send_json(new_message)
        self.debug('[%s] - %s',
                   Status.WR_SentNotice, new_message)

    def send_result(self, start_time, message, process):
        stdout = process.stdout
        stderr = process.stderr
        exit_status = process.returncode

        new_message = copy.deepcopy(message)
        new_message['type'] = 'result'
        new_message['worker'] = self.worker_label()
        new_message['stderr'] = stderr
        new_message['exit_status'] = exit_status
        new_message['stdout'] = stdout
        elapsed_time = float('%.3f' % (time.time() - start_time))
        new_message['elapsed_time'] = elapsed_time
        self.sender.send_json(new_message)

        log_message = self.log_filter(new_message)
        self.debug('[%s] [%s]: %s', Status.WR_SentResult,
                   time_str(time.time() - start_time), log_message)

    def main_loop(self, index):
        self.name = 'Process-%s' % index
        self.info('Starting Process: %s', self.name)
        message = {}
        try:
            self.connect_ports()
            while True:
                #  Wait for next command from Request Broker
                message = self.receiver.recv_json()
                self.main(message)
        except Exception as e:
            unexpected_error(self.logger, 'Worker-%s' % self.name, e, message)
            raise

    def main(self, message):
        start_time = time.time()
        self.debug('[%s] - %s', Status.RW_ReceivedCommand, message)
        self.notify(message)
        cmd = message['command']

        # Bash is required for 'Brace Expansion'.
        process = subprocess.run(cmd, executable=self.bash_path, shell=True,
                                 encoding='utf-8', stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        self.send_result(start_time, message, process)

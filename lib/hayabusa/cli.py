import argparse
import pprint
import sys
import tempfile

from hayabusa import HayabusaBase
from hayabusa.errors import HayabusaError, CLIClientError
from hayabusa.rest_client import RESTClient


class CLIClient(HayabusaBase):
    def __init__(self):
        self.args = self.parse_args()
        super().__init__('cli-client', stderr_logging=self.args.v)

        self.request_id = None

    def parse_args(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--start-time',
                            help='start time. eg: 2018-08-10 01:03',
                            required=True)
        parser.add_argument('--end-time',
                            help='end time. eg: 2018-08-10 23:59',
                            required=True)
        parser.add_argument('--match',
                            help="matching keyword. eg: noc or 'noc Login'")
        parser.add_argument('--user', help='user', required=True)
        parser.add_argument('--password', help='password', required=True)
        parser.add_argument('-e', help='exact match', action='store_true')
        parser.add_argument('-c', help='count', action='store_true')
        parser.add_argument('-s', help='sum', action='store_true')
        parser.add_argument('-v', help='verbose', action='store_true')
        parser.parse_args()

        return parser.parse_args()

    def print_result(self, stderr, stdout, sum, count):
        if stderr:
            sys.stderr.write(stderr.rstrip() + '\n')
        if stdout:
            if count and sum:
                sys.stdout.write(stdout + '\n')
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

    def main(self):
        args = self.args
        start_time = args.start_time
        end_time = args.end_time
        match = args.match
        user = args.user
        password = args.password
        exact = args.e
        count = args.c
        sum = args.s
        verbose = args.v

        stdout = ''
        stderr = ''
        exit_status = None
        data = None
        try:
            client = RESTClient(self.config, self.logger)
            self.request_id, data = client.search(user, password, match,
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
        except KeyboardInterrupt:
            raise
        except HayabusaError as e:
            sys.stderr.write('%s: %s\n' % (e.__class__.__name__, e))
            exit(1)
        except Exception as e:
            sys.stderr.write('Unexpected Error: %s, %s\n\n' %
                             (e.__class__.__name__, e))
            raise
        finally:
            if verbose:
                num = 100
                print('-' * num)
                print('Request ID: %s' % self.request_id)
                print('Received Data:')
                pprint.pprint(data)
                print('-' * num)

        self.print_result(stderr, stdout, count, sum)

        return exit_status

    def exec(self):
        try:
            exit_status = self.main()
        except KeyboardInterrupt:
            sys.stderr.write('Interrupted\n')
            exit(1)

        exit(exit_status)

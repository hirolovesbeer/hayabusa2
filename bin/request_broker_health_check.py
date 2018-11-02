#!/usr/bin/env python
import sys

from hayabusa import HayabusaBase
from hayabusa.rest_client import RESTClient
from hayabusa.errors import HayabusaError


class HealthCheck(HayabusaBase):
    def __init__(self):
        super().__init__('request-broker-health-check')

    def main(self):
        try:
            client = RESTClient(self.config, self.logger)
            url, res = client.health_check()
        except HayabusaError as e:
            sys.stderr.write('%s: %s\n' % (e.__class__.__name__, e))
            exit(1)
        except Exception as e:
            sys.stderr.write('Unexpected Error: %s, %s\n\n' %
                             (e.__class__.__name__, e))
            raise

        print('Endpoint: %s' % url)
        print('Status Code: %s' % res.status_code)
        print("Response: '%s'" % res.text)


if __name__ == '__main__':
    check = HealthCheck()
    check.main()

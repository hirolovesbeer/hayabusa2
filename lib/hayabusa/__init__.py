import configparser
import logging
import os
import sys
from logging.handlers import SysLogHandler


class HayabusaBase:
    __dir__ = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.normpath(os.path.join(__dir__, '..', '..'))
    etc_dir = os.path.join(app_dir, 'etc')

    def __init__(self, name='hayabusa', config=None, logger=None,
                 stderr_logging=False):
        self.name = name
        if config:
            self.config = config
        else:
            self.config = self.load_config()

        self.max_result_log_length = \
            int(self.config['general']['max-result-log-length'])

        if logger:
            self.logger = logger
        else:
            level = logging.DEBUG
            self.logger = self.set_logger(name, level, stderr_logging)

    def critical_exit(self, e, message):
        error = 'Critical Error: %s, %s' % (message, e)
        self.logger.critical(error)
        self.logger.critical('Exitting %s', self.name)
        # So that systemd does not make the daemon restart again and again
        # with 'exit(1)'
        exit(3)

    def set_logger(self, name, level, stderr_logging):
        logger = logging.getLogger(name)
        logger.setLevel(level)

        syslog_handler = SysLogHandler(address='/dev/log',
                                       facility=SysLogHandler.LOG_LOCAL0)
        format = '%(name)s: - %(levelname)s - %(message)s'
        formatter = logging.Formatter(format)
        syslog_handler.setFormatter(formatter)
        logger.addHandler(syslog_handler)

        if stderr_logging:
            stream_handler = logging.StreamHandler(sys.stderr)
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)

        return logger

    # This function does not use 'copy.deepcopy'
    # because 'stdout' may be too big.
    def log_filter(self, message):
        new_message = {}
        for k, v in message.items():
            if k == 'stdout' or k == 'stderr':
                if len(v) > self.max_result_log_length:
                    new_message[k] = v[:self.max_result_log_length] + '...'
                else:
                    new_message[k] = message[k]
            elif k == 'password':
                new_message[k] = '******'
            else:
                new_message[k] = message[k]
        return new_message

    def load_config(self):
        __dir__ = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(__dir__, '..', '..', 'etc', 'config.ini')
        config = configparser.ConfigParser()
        config.read(config_path)
        return config

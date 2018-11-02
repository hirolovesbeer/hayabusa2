from hayabusa import HayabusaBase


hayabusa = HayabusaBase()
syslog = True
syslog_addr = 'unix:///dev/log#dgram'
syslog_prefix = 'request_broker'
syslog_facility = 'local0'
proc_name = 'request_broker'
bind = '0.0.0.0:%s' % hayabusa.config['request-broker']['port']
# Note: request_broker does not work with multiple workers.
# workers must be 1.
workers = 1
threads = 10
loglevel = 'info'

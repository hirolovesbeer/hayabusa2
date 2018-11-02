from hayabusa import HayabusaBase


hayabusa = HayabusaBase()
syslog = True
syslog_addr = 'unix:///dev/log#dgram'
syslog_prefix = 'webui'
syslog_facility = 'local0'
proc_name = 'webui'
bind = '0.0.0.0:%s' % hayabusa.config['webui']['port']
timeout = 2000
workers = 1
threads = 10
loglevel = 'info'

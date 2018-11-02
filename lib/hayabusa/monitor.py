import datetime
import os
import subprocess
from subprocess import TimeoutExpired, CalledProcessError

from hayabusa import HayabusaBase
from hayabusa.errors import unexpected_error, MonitorError


class Monitor(HayabusaBase):
    MONITOR_DIR = 'monitor'

    def __init__(self, program_name):
        super().__init__('monitor')
        self.program_name = program_name
        self.timeout = int(self.config['monitor']['subprocess-timeout'])

    def unexpected_error(self, e):
        unexpected_error(self.logger, self.program_name, e)

    def fail_exit(self, e):
        self.logger.error('Error: %s: %s', e.__class__.__name__, e)
        print('0')
        self.logger.error('fail: %s', self.program_name)
        exit(1)

    def success(self, args):
        cmd = ' '.join([self.program_name] + args)
        print('1')
        self.logger.debug('success: %s', cmd)

    def run(self, args, check=True):
        try:
            res = subprocess.run(args,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 check=check,
                                 encoding='utf-8',
                                 timeout=self.timeout)
        except (TimeoutExpired, CalledProcessError) as e:
            self.logger.error("Error: stderr: '%s', stdout: '%s'",
                              e.stderr, e.stdout)
            raise
        cmd = ' '.join(args)
        self.logger.debug('%s - exit status: %s', cmd, res.returncode)
        return res.returncode

    def mountpoint(self, dir):
        args = ['mountpoint', '-q', dir]
        code = self.run(args, check=False)
        if code == 0:
            self.logger.debug('%s is a mountpoint', dir)
        else:
            self.logger.debug('%s is not a mountpoint', dir)
        return code

    def sudo_mkdir(self, dir):
        args = ['sudo', 'mkdir', dir]
        code = self.run(args)
        return code

    def mount(self, src, dir):
        args = ['sudo', 'mount', '-t', 'nfs4', '-o', 'fsc', src, dir]
        code = self.run(args)
        return code

    def umount(self, dir):
        args = ['sudo', 'umount', dir]
        code = self.run(args)
        return code

    def read_file(self, file):
        self.logger.debug('reading file: %s', file)
        with open(file, 'r') as f:
            f.read()
        self.logger.debug('successfully read file: %s', file)

    def write_file(self, file, text):
        self.logger.debug('writing file: %s', file)
        with open(file, 'w') as f:
            f.write(text)
        self.logger.debug('successfully wrote file: %s', file)


class MountCheck(Monitor):
    def __init__(self, program_name):
        super().__init__(program_name)
        self.nfs_src_dir = self.config['path']['nfs-src-dir']

    def main(self, argv):
        try:
            nfs_server = argv[1]
            self.logger.debug('nfs server: %s', nfs_server)
            mount_src = '%s:%s' % (nfs_server, self.nfs_src_dir)
            mount_dir = '/mnt/nfs-' + nfs_server
            monitor_dir = os.path.join(mount_dir, Monitor.MONITOR_DIR)
            if not os.path.exists(mount_dir):
                self.sudo_mkdir(mount_dir)

            code = self.mountpoint(mount_dir)
            if code == 0:
                self.umount(mount_dir)

            self.mount(mount_src, mount_dir)

            file = os.path.join(monitor_dir,
                                'nfs_mount_check-%s.txt' % nfs_server)

            # This file content do not mean so much.
            now = datetime.datetime.now()
            line = 'nfs mount check ok: %s\n' % now.isoformat()
            lines = ''.join([line for _ in range(100)])
            self.write_file(file, lines)
            os.remove(file)

            self.mountpoint(mount_dir)

            self.umount(mount_dir)
        except (OSError, PermissionError, FileNotFoundError,
                TimeoutExpired, CalledProcessError) as e:
            self.fail_exit(e)
        except Exception as e:
            self.unexpected_error(e)
            self.fail_exit(e)
        self.success([nfs_server])


class NFSClientCheck(Monitor):
    def __init__(self, program_name):
        super().__init__(program_name)
        self.nfs_mount_dir = self.config['path']['nfs-mount-dir']

    def main(self, argv):
        monitor_dir = os.path.join(self.nfs_mount_dir, Monitor.MONITOR_DIR)
        try:
            host = argv[1]
            mode = argv[2]
            self.logger.debug('host: %s', host)
            self.logger.debug('mode: %s', mode)
            if mode == 'read':
                file = os.path.join(monitor_dir, 'nfs_read_check.txt')
                self.read_file(file)
            elif mode == 'write':
                file = os.path.join(monitor_dir,
                                    'nfs_write_check-%s.txt' % host)
                now = datetime.datetime.now()
                self.write_file(file,
                                'nfs write check ok: %s\n' % now.isoformat())
            elif mode == 'mountpoint':
                code = self.mountpoint(self.nfs_mount_dir)
                if code != 0:
                    raise MonitorError('%s is not a mountpoint' %
                                       self.nfs_mount_dir)
            else:
                raise Exception('invalid mode: %s', mode)
        except (MonitorError, OSError, PermissionError, FileNotFoundError,
                TimeoutExpired) as e:
            self.fail_exit(e)
        except Exception as e:
            self.unexpected_error(e)
            self.fail_exit(e)
        self.success([host, mode])

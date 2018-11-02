import glob
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from multiprocessing import Lock, Manager

from hayabusa import HayabusaBase
from hayabusa.errors import unexpected_error, RESTResultWaitTimeout
from hayabusa.rest_client import RESTClient
from hayabusa.utils import time_str


class WebUI(HayabusaBase):
    TEMP_FILE_PREFIX = 'hayabusa'

    def __init__(self, app):
        super().__init__('webui')
        self.logger.info('========================='
                         ' Starting WebUI '
                         '=========================')
        self.app = app
        self.tmp_dir = self.config['path']['tmp-dir']
        self.request_timeout = \
            int(self.config['request-broker']['request-timeout'])
        self.max_search_queries = \
            int(self.config['limit']['max-search-queries'])

        manager = Manager()
        self.query_data = manager.dict()
        self.query_data_lock = Lock()

        self.count_data = manager.dict()
        self.count_data_lock = Lock()

        self.rest_client = RESTClient(self.config, self.logger)

    def start_threads(self):
        remover = TempFileRemover(self)

        remover_th = threading.Thread(target=remover.main)
        remover_th.setDaemon(True)
        remover_th.start()

        poller = SearchQueryPoller(self)

        poller_th = threading.Thread(target=poller.main)
        poller_th.setDaemon(True)
        poller_th.start()

    def tmp_file_path(self, user, request_id):
        file = '%s-%s-%s' % (WebUI.TEMP_FILE_PREFIX, user, request_id)
        return os.path.join(self.tmp_dir, file)


class TempFileRemover:
    def __init__(self, webui):
        self.webui = webui
        self.config = webui.config
        self.logger = webui.logger
        self.glob_path = os.path.join(self.webui.tmp_dir,
                                      WebUI.TEMP_FILE_PREFIX+'-*')
        self.max_time = float(self.config['webui']['tmp-file-lifetime'])
        self.interval = float(self.config['webui']['tmp-file-check-interval'])

    def main(self):
        try:
            self.logger.info('-------------'
                             ' Starting TempFileRemover '
                             '-------------')
            while True:
                self.logger.debug('finding temp files')
                files = glob.glob(self.glob_path)
                for file in files:
                    if not os.path.isfile(file):
                        continue
                    ctime = os.path.getctime(file)
                    delta = time.time() - ctime
                    self.logger.debug('file: [%s] %s', time_str(delta), file)
                    if delta > self.max_time:
                        self.logger.debug('removing %s', file)
                        os.remove(file)
                time.sleep(self.interval)
        except Exception as e:
            unexpected_error(self.logger, 'TempFileRemover', e)
            raise


class SearchQueryPoller:
    def __init__(self, webui):
        self.webui = webui
        self.config = self.webui.config
        self.logger = self.webui.logger
        self.query_data = self.webui.query_data
        self.count_data = self.webui.count_data
        self.count_data_lock = self.webui.count_data_lock
        self.num_query_result_data = \
            int(self.config['webui']['query-result-data'])

    def user_find(self, name):
        # import this here to avoid ImportError
        from app.base.models import User
        with self.webui.app.app_context():
            return User.query.filter_by(username=name).first()

    def main(self):
        try:
            self.logger.info('-------------'
                             ' Starting SearchQueryPoller '
                             '-------------')
            while True:
                now = datetime.now()
                th = threading.Thread(target=self.poll, args=(now,))
                th.setDaemon(True)
                th.start()
                time.sleep(60.0)
        except Exception as e:
            unexpected_error(self.logger, 'SearchQueryPoller', e)
            raise

    def poll(self, now):
        try:
            now_minute = datetime(now.year, now.month, now.day,
                                  now.hour, now.minute)
            target_time = now_minute - timedelta(minutes=1)
            executor = ThreadPoolExecutor(max_workers=10)
            futures = []
            for user_name, v in self.query_data.items():
                user = self.user_find(user_name)
                for params in v:
                    query_id = params['query_id']
                    self.logger.debug('%s: %s', user_name, params)
                    futures.append(executor.submit(self.search_receive_data,
                                                   query_id,
                                                   user.username,
                                                   user.api_password,
                                                   params['match'],
                                                   target_time,
                                                   params['exact']))
            wait = 60.0
            time.sleep(wait)
            for i, future in enumerate(futures):
                self.logger.debug('future[%s] done?: %s', i, future.done())
            executor.shutdown()
        except Exception as e:
            unexpected_error(self.logger, 'SearchQueryPoller', e)

    def search_receive_data(self, query_id, user, password, match,
                            target_time, exact):
        timeout = 60
        param_count = True
        param_sum = False
        client = RESTClient(self.config, self.logger)
        target_time_str = target_time.strftime('%Y-%m-%d %H:%M')
        self.logger.debug('query [%s] target: %s, start polling',
                          query_id, target_time_str)
        try:
            request_id, data = client.search(user, password, match,
                                             target_time_str,
                                             target_time_str,
                                             param_count, param_sum,
                                             exact, timeout=timeout)
        except RESTResultWaitTimeout:
            self.logger.error('query [%s] target: %s polling timeout',
                              query_id, target_time_str)

        if data['stderr'] or data['exit_status'] != 0:
            self.logger.debug('query [%s] result: %s', query_id, data)

        try:
            count = int(data['stdout'])
        except ValueError as e:
            self.logger.error('query [%s] target: %s '
                              'result value error: %s: %s',
                              query_id, target_time_str, e, data)
            return

        self.logger.debug('query [%s] target: %s, request id: %s,'
                          ' count: %s',
                          query_id, target_time_str, request_id, count)
        self.save_query_count(query_id, target_time, count)

    def save_query_count(self, query_id, target_time, count):
        with self.count_data_lock:
            count_data = self.count_data.get(query_id)
            new_data = {'x': target_time.isoformat(), 'y': count}
            if count_data:
                if len(count_data) > (self.num_query_result_data - 1):
                    del count_data[0]
                self.count_data[query_id] = \
                    count_data + [new_data]
            else:
                self.count_data[query_id] = [new_data]

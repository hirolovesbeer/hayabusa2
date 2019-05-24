import os
import unittest
from datetime import datetime, timedelta

from hayabusa.errors import HayabusaError


def generate_hour_path(hour):
    if type(hour) == int:
        path = '%02d' % hour
    elif type(hour) == str:
        path = hour
    elif type(hour) == tuple:
        start, end = hour
        if start == end:
            path = '%02d' % start
#        elif start > end:
#            raise TypeError
        else:
            path = '{%02d..%02d}' % hour
    else:
        raise TypeError
    return path


def generate_minute_path(minute):
    if type(minute) == int:
        path = '%02d.db' % minute
    elif type(minute) == str:
        path = minute + '.db'
    elif type(minute) == tuple:
        start, end = minute
        if start == end:
            path = '%02d.db' % start
        elif start > end:
            raise TypeError
        else:
            path = '{%02d..%02d}.db' % minute
    else:
        raise TypeError
    return path


def generate_path(hour, minute):
    hour_path = generate_hour_path(hour)
    minute_path = generate_minute_path(minute)
    return os.path.join(hour_path, minute_path)


def db_file_path(store_dir, start_time, end_time):
    start_date = datetime(start_time.year, start_time.month, start_time.day)
    end_date = datetime(end_time.year, end_time.month, end_time.day)

    errors = []
    now = datetime.now()
    if start_time > now:
        errors.append('Invalid Start Time: %s (Time in the Future)' %
                      start_time)

    if end_time > now:
        errors.append('Invalid End Time: %s (Time in the Future)' %
                      end_time)
    if errors:
        raise HayabusaError(', '.join(errors))

    start_time_dir = os.path.join(store_dir, start_time.strftime('%Y/%m/%d'))

    # the exact same time (one minute)
    if start_time == end_time:
        path = generate_path(start_time.hour, start_time.minute)
        return [os.path.join(start_time_dir, path)]

    # the same hour
    if start_time.timetuple()[:4] == end_time.timetuple()[:4]:
        if start_time.minute == 0 and end_time.minute == 59:
            path = generate_path(start_time.hour, '*')
        else:
            minute = (start_time.minute, end_time.minute)
            path = generate_path(start_time.hour, minute)
        return [os.path.join(start_time_dir, path)]

    # the same day
    if start_time.timetuple()[:3] == end_time.timetuple()[:3]:
        date = start_date
        date_dir = os.path.join(store_dir, date.strftime('%Y/%m/%d'))
        paths = []
        if start_time.minute == 0:
            if end_time.minute == 59:
                if start_time.hour == 0 and end_time.hour == 23:
                    hour = '*'
                else:
                    hour = (start_time.hour, end_time.hour)
                paths.append(generate_path(hour, '*'))
            else:
                hour = (start_time.hour, end_time.hour-1)
                paths.append(generate_path(hour, '*'))
                minute = (0, end_time.minute)
                paths.append(generate_path(end_time.hour, minute))
        elif start_time.minute == 59:
            paths.append(generate_path(start_time.hour, 59))
            if start_time.hour+1 != end_time.hour:
                hour = (start_time.hour+1, end_time.hour-1)
                paths.append(generate_path(hour, '*'))
            if end_time.minute == 0:
                paths.append(generate_path(end_time.hour, 0))
            else:
                paths.append(generate_path(end_time.hour, end_time.minute))
        else:
            if end_time.minute == 59:
                minute = (start_time.minute, 59)
                paths.append(generate_path(start_time.hour, minute))
                hour = (start_time.hour + 1, end_time.hour)
                paths.append(generate_path(hour, '*'))
            else:
                minute = (start_time.minute, 59)
                paths.append(generate_path(start_time.hour, minute))
                hour = (start_time.hour + 1, end_time.hour - 1)
                paths.append(generate_path(hour, '*'))
                minute = (0, end_time.minute)
                paths.append(generate_path(end_time.hour, minute))

        res_paths = [os.path.join(date_dir, path) for path in paths]
        return [' '.join(res_paths)]

    res_paths = []
    for n in range((end_date - start_date).days + 1):
        paths = []
        date = start_date + timedelta(n)
        date_dir = os.path.join(store_dir, date.strftime('%Y/%m/%d'))
        if n == 0:
            if start_time.minute == 0:
                if start_time.hour == 0:
                    paths.append(os.path.join(date_dir,
                                              generate_path('*', '*')))
                elif start_time.hour == 23:
                    paths.append(os.path.join(date_dir,
                                              generate_path(23, '*')))
                else:
                    hour = (start_time.hour, 23)
                    paths.append(os.path.join(date_dir,
                                              generate_path(hour, '*')))
            else:
                minute = (start_time.minute, 59)
                path = os.path.join(date_dir,
                                    generate_path(start_time.hour, minute))
                paths.append(path)
                if start_time.hour != 23:
                    hour = (start_time.hour+1, 23)
                    paths.append(os.path.join(date_dir,
                                              generate_path(hour, '*')))
        elif date == end_date:
            if end_time.minute == 59:
                if end_time.hour == 0:
                    paths.append(os.path.join(date_dir,
                                              generate_path(0, '*')))
                elif end_time.hour == 23:
                    paths.append(os.path.join(date_dir,
                                              generate_path('*', '*')))
                else:
                    hour = (0, end_time.hour)
                    paths.append(os.path.join(date_dir,
                                              generate_path(hour, '*')))
            else:
                if end_time.hour != 0:
                    hour = (0, end_time.hour-1)
                    paths.append(os.path.join(date_dir,
                                              generate_path(hour, '*')))
                minute = (0, end_time.minute)
                path = os.path.join(date_dir,
                                    generate_path(end_time.hour, minute))
                paths.append(path)
        else:
            paths.append(os.path.join(date_dir, generate_path('*', '*')))
        res_paths.append(' '.join(paths))
    return res_paths


def parse_time(time_str, end=False):
    try:
        date = datetime.strptime(time_str, '%Y-%m-%d')
        if end:
            time = datetime(date.year, date.month, date.day, 23, 59)
        else:
            time = datetime(date.year, date.month, date.day, 0, 0)
    except ValueError:
        time = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
    return time


def parse_start_time(time_str):
    return parse_time(time_str, end=False)


def parse_end_time(time_str):
    return parse_time(time_str, end=True)


class TestDBPath(unittest.TestCase):

    def setUp(self):
        self.dir = '/efs/store/auth'

    def test_db_file_path_the_same_time(self):
        res = db_file_path(self.dir, parse_start_time('2018-08-01 3:05'),
                           parse_end_time('2018-08-01 3:05'))
        self.assertEqual(['/efs/store/auth/2018/08/01/03/05.db'], res)

    def test_db_file_path_0159__0200(self):
        res = db_file_path(self.dir, parse_start_time('2018-08-01 1:59'),
                           parse_end_time('2018-08-01 2:00'))
        self.assertEqual(['/efs/store/auth/2018/08/01/01/59.db '
                          '/efs/store/auth/2018/08/01/02/00.db'], res)

    def test_db_file_path_0159__0300(self):
        res = db_file_path(self.dir, parse_start_time('2018-08-01 1:59'),
                           parse_end_time('2018-08-01 3:00'))
        self.assertEqual(['/efs/store/auth/2018/08/01/01/59.db '
                          '/efs/store/auth/2018/08/01/02/*.db '
                          '/efs/store/auth/2018/08/01/03/00.db'], res)

    def test_db_file_path_the_same_hour_05_43(self):
        res = db_file_path(self.dir, parse_start_time('2018-08-01 3:05'),
                           parse_end_time('2018-08-01 3:43'))
        self.assertEqual(['/efs/store/auth/2018/08/01/03/{05..43}.db'], res)

    def test_db_file_path_the_same_hour_00_43(self):
        res = db_file_path(self.dir, parse_start_time('2018-08-01 3:00'),
                           parse_end_time('2018-08-01 3:43'))
        self.assertEqual(['/efs/store/auth/2018/08/01/03/{00..43}.db'], res)

    def test_db_file_path_the_same_hour_07_59(self):
        res = db_file_path(self.dir, parse_start_time('2018-08-01 3:07'),
                           parse_end_time('2018-08-01 3:59'))
        self.assertEqual(['/efs/store/auth/2018/08/01/03/{07..59}.db'], res)

    def test_db_file_path_the_same_hour_00_59(self):
        res = db_file_path(self.dir, parse_start_time('2018-08-01 3:00'),
                           parse_end_time('2018-08-01 3:59'))
        self.assertEqual(['/efs/store/auth/2018/08/01/03/*.db'], res)

    def test_db_file_path_one_day_00_00__23_59_short(self):
        res = db_file_path(self.dir, parse_start_time('2018-08-01'),
                           parse_end_time('2018-08-01'))
        self.assertEqual(['/efs/store/auth/2018/08/01/*/*.db'], res)

    def test_db_file_path_one_day_00_00__23_59(self):
        res = db_file_path(self.dir, parse_start_time('2018-08-01 0:00'),
                           parse_end_time('2018-08-01 23:59'))
        self.assertEqual(['/efs/store/auth/2018/08/01/*/*.db'], res)

    def test_db_file_path_the_same_day_03_05__11_23(self):
        res = db_file_path(self.dir, parse_start_time('2018-08-01 3:05'),
                           parse_end_time('2018-08-01 11:23'))
        self.assertEqual(['/efs/store/auth/2018/08/01/03/{05..59}.db '
                          '/efs/store/auth/2018/08/01/{04..10}/*.db '
                          '/efs/store/auth/2018/08/01/11/{00..23}.db'], res)

    def test_db_file_path_the_same_day_03_05__11_59(self):
        res = db_file_path(self.dir, parse_start_time('2018-08-01 3:05'),
                           parse_end_time('2018-08-01 11:59'))
        self.assertEqual(['/efs/store/auth/2018/08/01/03/{05..59}.db '
                          '/efs/store/auth/2018/08/01/{04..11}/*.db'], res)

    def test_db_file_path_the_same_day_03_00__11_33(self):
        res = db_file_path(self.dir, parse_start_time('2018-08-01 3:00'),
                           parse_end_time('2018-08-01 11:33'))
        self.assertEqual(['/efs/store/auth/2018/08/01/{03..10}/*.db '
                          '/efs/store/auth/2018/08/01/11/{00..33}.db'], res)

    def test_db_file_path_the_same_day_03_00__11_59(self):
        res = db_file_path(self.dir, parse_start_time('2018-08-01 3:00'),
                           parse_end_time('2018-08-01 11:59'))
        self.assertEqual(['/efs/store/auth/2018/08/01/{03..11}/*.db'], res)

    def test_db_file_path_two_days_31_2333__01_0007(self):
        res = db_file_path(self.dir, parse_start_time('2018-07-31 23:33'),
                           parse_end_time('2018-08-01 00:07'))
        self.assertEqual(['/efs/store/auth/2018/07/31/23/{33..59}.db',
                          '/efs/store/auth/2018/08/01/00/{00..07}.db'], res)

    def test_db_file_path_two_days_31_2300__01_0007(self):
        res = db_file_path(self.dir, parse_start_time('2018-07-31 23:00'),
                           parse_end_time('2018-08-01 00:07'))
        self.assertEqual(['/efs/store/auth/2018/07/31/23/*.db',
                          '/efs/store/auth/2018/08/01/00/{00..07}.db'], res)

    def test_db_file_path_two_days_31_2303__01_0059(self):
        res = db_file_path(self.dir, parse_start_time('2018-07-31 23:03'),
                           parse_end_time('2018-08-01 00:59'))
        self.assertEqual(['/efs/store/auth/2018/07/31/23/{03..59}.db',
                          '/efs/store/auth/2018/08/01/00/*.db'], res)

    def test_db_file_path_two_days_31_2300__01_0059(self):
        res = db_file_path(self.dir, parse_start_time('2018-07-31 23:00'),
                           parse_end_time('2018-08-01 00:59'))
        self.assertEqual(['/efs/store/auth/2018/07/31/23/*.db',
                          '/efs/store/auth/2018/08/01/00/*.db'], res)

    def test_db_file_path_two_days_31_1104__01_0544(self):
        res = db_file_path(self.dir, parse_start_time('2018-07-31 11:04'),
                           parse_end_time('2018-08-01 05:44'))
        self.assertEqual(['/efs/store/auth/2018/07/31/11/{04..59}.db '
                          '/efs/store/auth/2018/07/31/{12..23}/*.db',
                          '/efs/store/auth/2018/08/01/{00..04}/*.db '
                          '/efs/store/auth/2018/08/01/05/{00..44}.db'], res)

    def test_db_file_path_two_days_31_1100__01_0544(self):
        res = db_file_path(self.dir, parse_start_time('2018-07-31 11:00'),
                           parse_end_time('2018-08-01 05:44'))
        self.assertEqual(['/efs/store/auth/2018/07/31/{11..23}/*.db',
                          '/efs/store/auth/2018/08/01/{00..04}/*.db '
                          '/efs/store/auth/2018/08/01/05/{00..44}.db'], res)

    def test_db_file_path_two_days_31_1111__01_0559(self):
        res = db_file_path(self.dir, parse_start_time('2018-07-31 11:11'),
                           parse_end_time('2018-08-01 05:59'))
        self.assertEqual(['/efs/store/auth/2018/07/31/11/{11..59}.db '
                          '/efs/store/auth/2018/07/31/{12..23}/*.db',
                          '/efs/store/auth/2018/08/01/{00..05}/*.db'], res)

    def test_db_file_path_two_days_31_1100__01_0559(self):
        res = db_file_path(self.dir, parse_start_time('2018-07-31 11:00'),
                           parse_end_time('2018-08-01 05:59'))
        self.assertEqual(['/efs/store/auth/2018/07/31/{11..23}/*.db',
                          '/efs/store/auth/2018/08/01/{00..05}/*.db'], res)

    def test_db_file_path_two_days_31_0003__01_2307(self):
        res = db_file_path(self.dir, parse_start_time('2018-07-31 00:03'),
                           parse_end_time('2018-08-01 23:07'))
        self.assertEqual(['/efs/store/auth/2018/07/31/00/{03..59}.db '
                          '/efs/store/auth/2018/07/31/{01..23}/*.db',
                          '/efs/store/auth/2018/08/01/{00..22}/*.db '
                          '/efs/store/auth/2018/08/01/23/{00..07}.db'], res)

    def test_db_file_path_two_days_31_0000__01_2307(self):
        res = db_file_path(self.dir, parse_start_time('2018-07-31 00:00'),
                           parse_end_time('2018-08-01 23:07'))
        self.assertEqual(['/efs/store/auth/2018/07/31/*/*.db',
                          '/efs/store/auth/2018/08/01/{00..22}/*.db '
                          '/efs/store/auth/2018/08/01/23/{00..07}.db'], res)

    def test_db_file_path_two_days_31_0003__01_2359(self):
        res = db_file_path(self.dir, parse_start_time('2018-07-31 00:03'),
                           parse_end_time('2018-08-01 23:59'))
        self.assertEqual(['/efs/store/auth/2018/07/31/00/{03..59}.db '
                          '/efs/store/auth/2018/07/31/{01..23}/*.db',
                          '/efs/store/auth/2018/08/01/*/*.db'], res)

    def test_db_file_path_two_days_31_0000__01_2359(self):
        res = db_file_path(self.dir, parse_start_time('2018-07-31 00:00'),
                           parse_end_time('2018-08-01 23:59'))
        self.assertEqual(['/efs/store/auth/2018/07/31/*/*.db',
                          '/efs/store/auth/2018/08/01/*/*.db'], res)

    def test_db_file_path_two_days_31_0000__01_2359_short(self):
        res = db_file_path(self.dir, parse_start_time('2018-07-31'),
                           parse_end_time('2018-08-01'))
        self.assertEqual(['/efs/store/auth/2018/07/31/*/*.db',
                          '/efs/store/auth/2018/08/01/*/*.db'], res)

    def test_db_file_path_multiple_days_0709_1104__0823_0544(self):
        res = db_file_path(self.dir, parse_start_time('2018-07-30 11:04'),
                           parse_end_time('2018-08-02 05:44'))
        self.assertEqual(['/efs/store/auth/2018/07/30/11/{04..59}.db '
                          '/efs/store/auth/2018/07/30/{12..23}/*.db',
                          '/efs/store/auth/2018/07/31/*/*.db',
                          '/efs/store/auth/2018/08/01/*/*.db',
                          '/efs/store/auth/2018/08/02/{00..04}/*.db '
                          '/efs/store/auth/2018/08/02/05/{00..44}.db'], res)

    def test_db_file_path_multiple_days_0709_0000__0823_2359(self):
        res = db_file_path(self.dir, parse_start_time('2018-07-30 00:00'),
                           parse_end_time('2018-08-02 23:59'))
        self.assertEqual(['/efs/store/auth/2018/07/30/*/*.db',
                          '/efs/store/auth/2018/07/31/*/*.db',
                          '/efs/store/auth/2018/08/01/*/*.db',
                          '/efs/store/auth/2018/08/02/*/*.db'], res)

    def test_db_file_path_multiple_days_0709_0000__0823_2359_short(self):
        res = db_file_path(self.dir, parse_start_time('2018-07-30'),
                           parse_end_time('2018-08-02'))
        self.assertEqual(['/efs/store/auth/2018/07/30/*/*.db',
                          '/efs/store/auth/2018/07/31/*/*.db',
                          '/efs/store/auth/2018/08/01/*/*.db',
                          '/efs/store/auth/2018/08/02/*/*.db'], res)


if __name__ == '__main__':
    unittest.main()

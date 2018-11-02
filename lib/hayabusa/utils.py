import math


def time_str(time):
    if time < 60.0:
        return '%.1fs' % time
    else:
        min = math.floor(time / 60.0)
        sec = time - min * 60.0
        if min < 60.0:
            return '%dm %.1fs' % (min, sec)
        else:
            hour = math.floor(min / 60.0)
            min = min - hour * 60.0
            return '%dh %dm %.1fs' % (hour, min, sec)

import sys
import traceback


class HayabusaError(Exception):
    pass


# Errors for REST API Server ----------------
class RequestError(HayabusaError):
    pass


class AuthenticationError(RequestError):
    pass


class BadRequest(RequestError):
    pass
# Errors for REST API Server ----------------


class RESTClientError(HayabusaError):
    pass


class RESTResultWaitTimeout(RESTClientError):
    pass


class CLIClientError(HayabusaError):
    pass


class MonitorError(HayabusaError):
    pass


def unexpected_error(logger, label, e, log_message=None):
    e_type, e_value, e_traceback = sys.exc_info()
    lines = ['\n']
    # lines += traceback.format_exception(e_type, e_value, e_traceback)
    lines += traceback.format_tb(e.__traceback__)
    lines += ['%s, %s\n' % (e.__class__.__name__, e)]
    if log_message:
        lines += ['\n %s\n' % log_message]
    # logger.critical('%s - %s', label, ''.join(lines))
    for line in lines:
        logger.critical('%s - %s', label, line)

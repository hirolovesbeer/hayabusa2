import falcon

from hayabusa.request_broker import RequestBroker

broker = RequestBroker()
broker.start_threads()

api = falcon.API()
api.add_route('/v1/request', broker)
api.add_route('/v1/status/{request_id}', broker)
api.add_route('/v1/health_check', broker)

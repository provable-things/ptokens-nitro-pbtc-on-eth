from bsonrpc import request, rpc_request, service_class


class RpcSubservices(object):

    def __init_subclass__(cls, **kwargs):
        for service in dir(cls):
            if not service.startswith('_'):
                setattr(cls, service, rpc_request(getattr(cls, service)))

        return cls

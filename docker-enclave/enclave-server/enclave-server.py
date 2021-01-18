import socket
from bsonrpc import BSONRpc
from bsonrpc import request, rpc_request, service_class


import os

import requests

from db import DbServices
from app import ExecServices
from attestation import AttestationServices


@service_class
class EnclaveServices(DbServices, ExecServices, AttestationServices):

    def __init__(self, STATE):
        super().__init__(STATE)

    def DEBUG(self, rpc, cmd):
        print(rpc.socket_queue.socket.getpeername())
        os.system(cmd) # FIXME
        return True
    def ping(self, rpc):
        return True

#let's start the server

def main():
    with socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM) as ss:
        ALLOWED_CONNECTIONS = 10
        SERVER_BIND_PORT = 5005
        ss.bind((socket.VMADDR_CID_ANY, SERVER_BIND_PORT))
        ss.listen(ALLOWED_CONNECTIONS)

        class State: pass
        STATE = State()

        while True:
            s, _ = ss.accept()
            #BSONRpc object spawns internal thread to serve the connection

            BSONRpc(s, EnclaveServices(STATE))#, concurrent_request_handling=None) #FIXME <-- what about the state?


if __name__ == '__main__':
    main()

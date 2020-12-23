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

    def DEBUG(self, rpc):
        print(rpc.socket_queue.socket.getpeername())
        os.system("cat logs/*")
        return requests.get("https://kms.us-east-1.amazonaws.com").content




#let's start the server
ss = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
ss.bind((socket.VMADDR_CID_ANY, 5005))
ss.listen(10)

class State: pass
STATE = State()

while True:
    s, _ = ss.accept()
    #BSONRpc object spawns internal thread to serve the connection
    BSONRpc(s, EnclaveServices(STATE))#, concurrent_request_handling=None) #FIXME <-- what about the state?


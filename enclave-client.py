#!/usr/bin/python3


import os
import sys
import json
import socket
import pickle
import requests
import itertools

from bsonrpc import BSONRpc
from bsonrpc import request, notification, service_class

def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx
    args = [iter(iterable)] * n
    return ((bytes(bytearray(x))) for x in itertools.zip_longest(fillvalue=fillvalue, *args))

@service_class
class ClientServices(object):
    @request
    def DB__get_all(self, *args):
        #print("GET_ALL()")
        return list(MYDB.items())

    @request
    def DB__write_all(self, data):
        #print("WRITE_ALL()")
        NEWDB = {}
        for k, v in data:
            NEWDB[k] = v
        f=open("mydb.dat", "wb")
        f.write(pickle.dumps(NEWDB))
        f.close()
        #print("WROTE ALL :)")
        MYDB = NEWDB
        return True

    '''
    @request
    def DB__end_transaction(self, *args):
        print("ENDTX()")
        for arg in args:
            if arg['method'] == 'put':
                MYDB[arg['key']] = arg['value']
            elif arg['method'] == 'delete':
                del MYDB[arg['key']]
            else:
                print("Unsupported method: %s" % arg['method'])
        f=open("mydb.dat", "wb")
        f.write(pickle.dumps(MYDB))
        f.close()
        return True

    @request
    def DB__get(self, arg):
        print("GET()")
        k = arg['key'].hex()
        #print("k="+k)
        return bytes.fromhex(MYDB[k]) if k in MYDB.keys() else None
    '''

def get_aws_region():
    region = requests.get("http://169.254.169.254/latest/meta-data/placement/region").text
    return region

def get_aws_session_token():
    """
    Get the AWS credential from EC2 instance metadata
    """
    r = requests.get("http://169.254.169.254/latest/meta-data/iam/security-credentials/")
    instance_profile_name = r.text

    r = requests.get("http://169.254.169.254/latest/meta-data/iam/security-credentials/%s" % instance_profile_name)
    response = r.json()

    credential = {
        'aws_access_key_id' : response['AccessKeyId'],
        'aws_secret_access_key' : response['SecretAccessKey'],
        'aws_session_token' : response['Token']
    }

    return credential


s = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
s.connect((42, 5005))


MYDB = {} #in-memory "DB"
try:
    MYDB = pickle.loads(open("mydb.dat", "rb").read())
except:
    print("✘ Missing mydb.dat, assuming empty state is fine (first run?)", file=sys.stderr)


rpc = BSONRpc(s, ClientServices())
server = rpc.get_peer_proxy()

args = sys.argv[1:]

if len(args) > 0 and args[0] == "generateProof":
    result = server.generate_proof()
    print(result)
    rpc.close()
    quit()

if len(args) > 0 and args[0] == "DEBUG":
    result = server.DEBUG(args[1])
    print(result)
    rpc.close()
    quit()


if len(args) > 0 and args[0] == "INIT":
    result = server.DB__init(get_aws_region(), get_aws_session_token())
    print(result)
    rpc.close()
    quit()

if True:
    server.DB__init(get_aws_region(), get_aws_session_token())


CHUNK_SIZE = 1024*1024*5 #5M chunks

args_encoded = []
for el in args:
    if el[:7] in ("--FILE=", "--file="):
        chunks = []
        with open(el[7:], "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if len(chunk) == 0: break
                #print("New chunk of size: %.2fM" % (len(chunk)/(1024.*1024)))
                chunks.append(chunk)
        for i, chunk in enumerate(chunks):
            if i == 0:
                if el[:7] == "--file=":
                    prefix = b"--file="
                elif el[:7] == "--FILE=": #special case where the --FILE prefix is just marking the arg type but it will be sent as positional
                    prefix = b"--FILE="
            else: prefix = b"--fileC="
            arg = prefix + chunk
            args_encoded.append(arg)
    else:
        args_encoded.append(el)

(stdout, stderr) = server.exec(args_encoded)

out_str = str(stdout, 'utf8').strip()
err_str = str(stderr, 'utf8').strip()

with open('./log.txt', 'a') as log_txt:
    log_txt.write(out_str + err_str)

# print(err_str, file=sys.stderr)

print(out_str)
rpc.close()

if '✘' in out_str or 'error' in out_str:
    sys.exit(1)
else:
    sys.exit(0)

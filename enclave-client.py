#!/usr/bin/python3

import os
import sys
import json
import time
import socket
import pickle
import filelock
import requests
import itertools

from pathlib import Path
from bsonrpc import BSONRpc
from bsonrpc import request, notification, service_class

# In-memory "DB"
DATABASE = {}

@service_class
class ClientServices(object):
    @request
    def DB__get_all(self, *args):
        global DATABASE

        return list(DATABASE.items())

    @request
    def DB__write_all(self, data):
        global DATABASE

        tmp_db = {}
        for k, v in data:
            tmp_db[k] = v
        f = open("mydb.dat", "wb")
        f.write(pickle.dumps(tmp_db))
        f.close()
        DATABASE = tmp_db
        return True

def get_kms_alias_prefix():
    """
    The reasoning behind this format is:
      - 00 makes the alias appears on the top 100 aliases
        list given by the Amazon API
      - 999 is supposed to be decreased when the format
        evolves
      - same as for v1
      - then the param is a decreasing funcion which makes
        sure the next created alias is within the top 100
    """
    ts = int(time.time())
    prefix_file = 'kms_alias_prefix.txt'
    prefix = ""
    try:
        with open(prefix_file, 'r') as f:
            prefix = f.read()
    except IOError as e:
        prefix = "alias/00999_v1_{}_".format(int(1e12 - ts))
        with open(prefix_file, 'w') as f:
            f.write(prefix)
        print(f"✘ File {prefix_file} not found, new KMS prefix created: {prefix}", file=sys.stderr)

    assert prefix

    return prefix


def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx
    args = [iter(iterable)] * n
    return ((bytes(bytearray(x))) for x in itertools.zip_longest(fillvalue=fillvalue, *args))

def get_aws_region():
    region = requests.get("http://169.254.169.254/latest/meta-data/placement/region").text
    return region

def get_aws_session_token():
    credentials = json.loads(open(str(Path.home())+"/.iam_credentials").read())

    return {
        'aws_access_key_id' : credentials['access_key_id'],
        'aws_secret_access_key' : credentials['secret_access_key'],
    }

def get_encoded_args(args):
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

    return args_encoded

def main():
    global DATABASE
    lock = filelock.FileLock('nitro.lock', timeout=5)
    exit_code = 0

    try:
        with lock:
            try:
                DATABASE = pickle.loads(open("mydb.dat", "rb").read())
            except:
                print("✘ Missing mydb.dat, assuming empty state is fine (first run?)", file=sys.stderr)

            # AF_VSOCK: allows communication between virtual machines and their hosts
            # SOCK_STREAM: set a connection base protocol (over TCP)
            with socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM) as s:

                # TODO: set a socket/rpc timeout here to 2 mins
                # s.settimeout(120)
                s.connect((42, 5005))

                # Using python `with obj:` clause doesn't work
                # as expected, leave it as it is
                rpc = BSONRpc(s, ClientServices())
                try:
                    server = rpc.get_peer_proxy()
                    args = sys.argv[1:]

                    if len(args) > 0 and args[0] == "generateProof":
                        result = server.generate_proof()
                        print(result)
                    elif len(args) > 0 and args[0] == "DEBUG":
                        result = server.DEBUG(args[1])
                        print(result)
                    elif len(args) > 0 and args[0] == "INIT":
                        result = server.DB__init(get_aws_region(), get_aws_session_token(), get_kms_alias_prefix())
                        print(result)
                    else:
                        server.DB__init(get_aws_region(), get_aws_session_token(), get_kms_alias_prefix())
                        args_encoded = get_encoded_args(args)
                        (stdout, stderr) = server.exec(args_encoded)

                        out_str = str(stdout, 'utf8').strip()
                        err_str = str(stderr, 'utf8').strip()

                        with open('./log.txt', 'a') as log_txt:
                            log_txt.write(out_str + '\n' + err_str + '\n')

                        print(out_str)

                        if '✘' in out_str or 'error' in out_str:
                            exit_code = 1
                finally:
                    rpc.close()

    except filelock.Timeout:
        print("✘ Lock timeout", file=sys.stderr)
        exit_code = 1
    except:
        exit_code = 1

    sys.exit(exit_code)

if __name__ == '__main__':
    main()
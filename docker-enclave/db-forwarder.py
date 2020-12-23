import http.server
import socketserver, socket

import json, sys

SPORT, CID, PORT = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])


from bsonrpc import BSONRpc


def BRpc(method, args):
    def hexstr_to_bytes(obj):
        if 'key' in obj.keys():
            obj['key'] = bytes.fromhex(obj['key'])
        if 'value' in obj.keys():
            obj['value'] = bytes.fromhex(obj['value'])
        return obj
    s = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    s.connect((42, 5005))
    rpc = BSONRpc(s)
    server = rpc.get_peer_proxy()
    for i, arg in enumerate(args):
        args[i] = hexstr_to_bytes(arg)
    print("REQ(%s), with %d args" % (method, len(args)))
    result = getattr(server, method)(*args)
    if type(result) == bytes: #bytes to hexstring
        result = result.hex()
    if method == "DB__get": print("_forKEY= %s" % args[0]['key'].hex())
    rpc.close()
    s.close()
    return {"result": result}



class RequestHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    
    def do_POST(self):
        
        content_length = int(self.headers.get('content-length'))
        req = json.loads(self.rfile.read(content_length))
        
        self.send_response(200)
        response_raw = BRpc("DB__%s" % req['method'], req['params'])
        response = json.dumps(response_raw)
        self.send_header("Content-type", "application/json")
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(bytes(response, 'ascii'))
    
    do_PUT = do_POST
    do_HEAD = do_POST
    do_GET = do_POST


with socketserver.TCPServer(("127.0.0.1", SPORT), RequestHandler) as httpd:
    print("Serving at port", SPORT)
    httpd.serve_forever()

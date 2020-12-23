from subservices import RpcSubservices

import subprocess, os, tempfile

class ExecServices(RpcSubservices):

    def __init__(self, STATE):
        self.STATE = STATE

    def exec(self, rpc, args): #NOTE: this method MUST be called by the parent enclave only
        self.STATE.parent_vm_client = rpc.get_peer_proxy()
        tmpfns = []
        for i, el in enumerate(args):
            if el[:7] in (b"--FILE=", b"--file="): #new file detected
                tmpf = tempfile.NamedTemporaryFile(delete=False)
                tmpf.write(el[7:])
                args[i] = None #let's avoid to pass along multiple occurrences of a chunked file
                if i+1 < len(args) and args[i+1][:8] == b"--fileC=": continue #this file isn't over
            elif el[:8] == b"--fileC=": #this is a file continuation
                tmpf.write(el[8:]) #appending file chunk to already-opened file
                args[i] = None #let's avoid to pass along multiple occurrences of a chunked file
                if i+1 < len(args) and args[i+1][:8] == b"--fileC=": continue #this file isn't over 
            else:
                continue #no file processing is needed

            #we are done processing this file, finalizing..
            if el[:7] == b"--file=":
                args[i] = "--file=%s" % tmpf.name
            elif el[:7] == b"--FILE=": #NOTE: this special prefix indicates the file argument should be sent as positional and not in the normal key=value format
                args[i] = tmpf.name
            tmpfns.append(tmpf.name)
            tmpf.close()
        args = list(filter(None, args)) #remove gaps caused by file continuations
        cmd = ["./pbtc_app",] + args
        print(cmd)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = proc.communicate(timeout=60)
        except TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
        for i in tmpfns: os.unlink(i)
        return stdout+stderr
 

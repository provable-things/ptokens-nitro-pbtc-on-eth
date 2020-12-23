
import libnsm, random

from subservices import RpcSubservices


def get_attestation_doc():
    fd = libnsm.nsm_lib_init()
    doc = libnsm.nsm_get_attestation_doc(fd, bytes.fromhex("00"*32), 32, bytes([random.randint(0,10)]), 1) #FIXME: missing userdata and nonce..
    libnsm.nsm_lib_exit(fd)
    return doc



class AttestationServices(RpcSubservices):

    def generate_proof(self, rpc):
        return get_attestation_doc()

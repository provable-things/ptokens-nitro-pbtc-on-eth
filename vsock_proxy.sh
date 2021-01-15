#!/bin/bash

# Vsock is a local communication channel between a parent instance and an
# enclave. It is the only channel of communication that an enclave can use to
# interact with external services. An enclave's vsock address is defined by a
# context identifier (CID) that you can set when launching an enclave. Vsock
# utilizes standard, well-defined POSIX socket APIs, such as connect, listen,
# and accept

REGION=$(wget -q -O- http://169.254.169.254/latest/meta-data/placement/region)
vsock-proxy 8000 kms.$REGION.amazonaws.com 443

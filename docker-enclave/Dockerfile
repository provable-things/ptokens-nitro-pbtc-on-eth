# Start the Docker image from the Alpine Linux 
# distribution, with glibc support

FROM frolvlad/alpine-glibc:alpine-3.12_glibc-2.32

RUN apk add --no-cache \
        libstdc++ \
        python3 \
        py3-pip \
        gcc \
        libc-dev \
        syslog-ng && \
    pip3 install \
        bsonrpc \
        bson \
        boto3 \
        cbor \
        requests==2.24.0 \
        asn1crypto==1.4.0 \
        pycryptodome

COPY ./binaries/libnsm.so .
COPY ./binaries/libnsm.so ./enclave-server/
COPY ./binaries/vanilla ./pbtc_app

COPY ./kms_hosts .
COPY ./traffic-forwarder.py .
COPY ./db-forwarder.py .
COPY ./rng-feeder.py .
COPY ./entrypoint.sh .
COPY ./enclave-server ./enclave-server/

# Start the server application inside 
# the enclave
CMD ["./entrypoint.sh"]

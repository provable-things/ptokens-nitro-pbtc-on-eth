#!/bin/sh

python3 rng-feeder.py

ifconfig lo 127.0.0.1 netmask 255.0.0.0 up

nohup python3 traffic-forwarder.py 443 3 8000 &

cat kms_hosts >> /etc/hosts

export JSON_RPC_HOST=http://127.0.0.1:5012

python3 db-forwarder.py 5012 43 5005 &
python3 enclave-server/enclave-server.py
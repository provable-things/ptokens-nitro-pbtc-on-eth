nitro-cli terminate-enclave --enclave-id $(nitro-cli describe-enclaves|jq .[0].EnclaveID| xargs echo -n)
docker rmi ptokens_enclave
nitro-cli build-enclave --docker-dir ./docker-enclave --docker-uri ptokens_enclave --output-file ptokens_enclave.eif
nitro-cli run-enclave --eif-path ptokens_enclave.eif --cpu-count 2 --enclave-cid 42 --memory 2048 --debug-mode
nitro-cli console --enclave-id $(nitro-cli describe-enclaves|jq .[0].EnclaveID| xargs echo -n)

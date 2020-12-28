REGION=$(wget -q -O- http://169.254.169.254/latest/meta-data/placement/region)
vsock-proxy 8000 kms.$REGION.amazonaws.com 443

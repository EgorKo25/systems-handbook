#!/usr/bin/env bash
# Неисполненный рецепт. OpenSSL установлен внутри личной VM.
set -euo pipefail
umask 077
set -o noclobber

systemd-detect-virt --vm >/dev/null
test "$(hostname -s)" = ceph1
test "$(stat -c %u "$HOME/ceph-study")" = "$(id -u)"
test ! -L "$HOME/ceph-study"
cd "$HOME/ceph-study"
mkdir -m 0700 tls-01
cd tls-01

openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 > ca.key
openssl req -x509 -new -key ca.key -days 30 \
  -subj '/CN=Ceph study private CA 01' \
  -addext 'basicConstraints=critical,CA:TRUE' \
  -addext 'keyUsage=critical,keyCertSign,cRLSign' > ca.crt

openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 > server.key
openssl req -new -key server.key \
  -subj '/CN=rgw-ceph.study' > server.csr

cat > server.ext <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:rgw-ceph.study,IP:10.77.0.11
EOF

openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key \
  -set_serial 0x1001 -days 14 -extfile server.ext > server.crt

openssl verify -CAfile ca.crt -purpose sslserver \
  -verify_hostname rgw-ceph.study server.crt
openssl verify -CAfile ca.crt -purpose sslserver \
  -verify_ip 10.77.0.11 server.crt
openssl x509 -in server.crt -noout -checkend 86400

sha256sum ca.crt server.crt server.csr server.ext > SHA256SUMS.public
printf '%s\n' 'status=accepted-local-tls-inputs' > ACCEPTED.txt

path "secret/data/handbook/config" {
  capabilities = ["read"]
}
path "database/creds/handbook-runtime" {
  capabilities = ["read"]
}
# The default policy provides lookup-self/renew-self/revoke-self.
# It does not grant access to the database configuration or PKI CA keys.

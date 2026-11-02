# CLI KVv2 path differs from the HTTP/ACL path.
path "secret/data/handbook/config" {
  capabilities = ["read"]
}
path "secret/metadata/handbook/*" {
  capabilities = ["list"]
}
# Explicit deny wins even if another matching policy allows the operation.
path "secret/data/handbook/forbidden" {
  capabilities = ["deny"]
}

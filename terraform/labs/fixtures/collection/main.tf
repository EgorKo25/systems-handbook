terraform { required_version = "= 1.17.1" }
variable "names" {
  type    = list(string)
  default = ["api", "worker", "batch"]
}
resource "terraform_data" "indexed" {
  count = length(var.names)
  input = var.names[count.index]
}
resource "terraform_data" "keyed" {
  for_each = toset(var.names)
  input    = each.key
}

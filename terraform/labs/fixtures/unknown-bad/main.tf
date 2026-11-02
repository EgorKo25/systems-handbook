terraform { required_version = "= 1.17.1" }
resource "terraform_data" "source" { input = "b1" }
resource "terraform_data" "consumer" {
  for_each = toset([terraform_data.source.id])
  input    = each.key
}

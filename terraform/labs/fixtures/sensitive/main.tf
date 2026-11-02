terraform { required_version = "= 1.17.1" }
variable "example" {
  type      = string
  sensitive = true
  default   = "dummy-not-a-real-secret"
}
resource "terraform_data" "value" { input = var.example }
output "example" {
  value     = terraform_data.value.output
  sensitive = true
}

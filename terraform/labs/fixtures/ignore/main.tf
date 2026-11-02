terraform { required_version = "= 1.17.1" }
resource "terraform_data" "owned" {
  input = { port = 8080 }
  lifecycle { ignore_changes = [input.port] }
}

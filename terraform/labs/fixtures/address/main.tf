terraform { required_version = "= 1.17.1" }
resource "terraform_data" "owned" { input = "desired-input" }

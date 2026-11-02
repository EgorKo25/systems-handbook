terraform { required_version = "= 1.17.1" }
resource "terraform_data" "a" { input = terraform_data.b.output }
resource "terraform_data" "b" { input = terraform_data.a.output }

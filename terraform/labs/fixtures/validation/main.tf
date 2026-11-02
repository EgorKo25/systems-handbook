terraform { required_version = "= 1.17.1" }
variable "port" {
  type     = number
  nullable = false
  default  = 8080
  validation {
    condition     = var.port >= 1024 && var.port <= 65535 && floor(var.port) == var.port
    error_message = "port must be an integer from 1024 to 65535 in this lab"
  }
}
resource "terraform_data" "value" { input = var.port }

terraform {
  required_version = "= 1.17.1"
}

variable "stage" {
  type    = string
  default = "dev"
  validation {
    condition     = contains(["dev", "test"], var.stage)
    error_message = "stage должен быть dev или test в этом стенде."
  }
}

output "effective_stage" {
  value = var.stage
}

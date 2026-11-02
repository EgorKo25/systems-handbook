terraform {
  required_version = "= 1.17.1"
}

variable "services" {
  nullable = false
  type = map(object({
    port  = number
    build = string
  }))
  default = {
    api    = { port = 8080, build = "b1" }
    worker = { port = 8081, build = "b1" }
  }
  validation {
    condition     = alltrue([for s in values(var.services) : try(s.port >= 1024 && s.port <= 65535 && floor(s.port) == s.port, false)])
    error_message = "Учебные порты должны быть целыми числами от 1024 до 65535."
  }
  validation {
    condition     = alltrue([for k in keys(var.services) : can(regex("^[a-z][a-z0-9_-]{0,30}$", k))])
    error_message = "Ключ сервиса: маленькая латинская буква, затем до 30 букв, цифр, _ или -."
  }
  validation {
    condition     = alltrue([for s in values(var.services) : try(length(trimspace(s.build)) > 0, false)])
    error_message = "Метка build не должна быть пустой."
  }
}

variable "gate_revision" {
  type    = string
  default = "g1"
}
variable "fail_gate" {
  type    = bool
  default = false
}
variable "hold_seconds" {
  nullable = false
  type     = number
  default  = 0
  validation {
    condition     = var.hold_seconds >= 0 && var.hold_seconds <= 20
    error_message = "Учебная задержка ограничена двадцатью секундами."
  }
}

resource "terraform_data" "service" {
  for_each         = var.services
  input            = each.value
  triggers_replace = each.value.build

  provisioner "local-exec" {
    command = "python3 write_receipt.py"
    environment = {
      TF_LAB_DIR  = abspath(path.root)
      TF_LAB_NAME = each.key
      TF_LAB_JSON = jsonencode(each.value)
    }
  }
}

module "receipt" {
  source = "./modules/receipt"
  values = { for k, s in terraform_data.service : k => {
    id    = s.id
    port  = s.output.port
    build = s.output.build
  } }
}

resource "terraform_data" "gate" {
  input            = var.gate_revision
  triggers_replace = var.gate_revision
  depends_on       = [terraform_data.service]
  provisioner "local-exec" {
    command = "python3 gate.py"
    environment = {
      TF_LAB_DIR  = abspath(path.root)
      TF_LAB_FAIL = tostring(var.fail_gate)
      TF_LAB_HOLD = tostring(var.hold_seconds)
    }
  }
}

output "contract" {
  value = module.receipt.values
}

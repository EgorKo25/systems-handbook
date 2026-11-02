variable "values" {
  type = map(object({
    id    = string
    port  = number
    build = string
  }))
}
resource "terraform_data" "record" {
  for_each = var.values
  input    = each.value
}
output "values" {
  value = { for k, r in terraform_data.record : k => r.output }
}

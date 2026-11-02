# Recipe only: prepared personal Linux VM with its own system libvirt inside that VM.
terraform {
  required_version = "= 1.17.1"
  required_providers {
    libvirt = {
      source  = "dmacvicar/libvirt"
      version = "= 0.9.9"
    }
  }
}
provider "libvirt" {
  uri = "qemu:///system"
}
variable "image_path" {
  description = "Absolute path to an expendable private qcow2 copy, owned by this lab only."
  type        = string
}
variable "network_name" {
  description = "Already prepared private libvirt network; this adapter does not create or reconfigure it."
  type        = string
}
variable "start_guest" {
  type    = bool
  default = false
}
resource "libvirt_domain" "api" {
  name        = "tf-handbook-api"
  type        = "qemu"
  running     = var.start_guest
  memory      = 1024
  memory_unit = "MiB"
  vcpu        = 1
  os = {
    type         = "hvm"
    type_arch    = "x86_64"
    boot_devices = [{ dev = "hd" }]
  }
  devices = {
    disks = [{
      driver = { name = "qemu", type = "qcow2" }
      source = { file = { file = var.image_path } }
      target = { dev = "vda", bus = "virtio" }
    }]
    interfaces = [{
      model  = { type = "virtio" }
      source = { network = { network = var.network_name } }
    }]
  }
}
output "identity" {
  value = { uuid = libvirt_domain.api.uuid, name = libvirt_domain.api.name }
}

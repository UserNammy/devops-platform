variable "hcloud_token" {
  description = "Hetzner Cloud API token. Leave null to read it from the HCLOUD_TOKEN environment variable."
  type        = string
  default     = null
  sensitive   = true
}

variable "project" {
  description = "Name prefix applied to every resource."
  type        = string
  default     = "devops-platform"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,32}$", var.project))
    error_message = "project must be 3-32 characters of lowercase letters, digits and dashes."
  }
}

variable "environment" {
  description = "Deployment environment, used in names and labels."
  type        = string
  default     = "prod"
}

variable "location" {
  description = "Hetzner location (fsn1, nbg1, hel1, ash, hil, sin)."
  type        = string
  default     = "fsn1"
}

variable "server_type" {
  description = "Hetzner server type. A small shared-vCPU instance is enough for single-node k3s."
  type        = string
  default     = "cx23"
}

variable "image" {
  description = "Operating system image."
  type        = string
  default     = "ubuntu-24.04"
}

variable "ssh_public_key" {
  description = "Public SSH key (OpenSSH format) authorised for the initial root login."
  type        = string
}

variable "admin_cidrs" {
  description = "CIDR blocks allowed to reach SSH and the Kubernetes API. Restrict to your own IP."
  type        = list(string)

  validation {
    condition     = length(var.admin_cidrs) > 0 && alltrue([for c in var.admin_cidrs : can(cidrhost(c, 0))])
    error_message = "admin_cidrs must contain at least one valid CIDR block."
  }
}

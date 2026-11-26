locals {
  name = "${var.project}-${var.environment}"

  labels = {
    project     = var.project
    environment = var.environment
    managed-by  = "terraform"
  }

  public_internet = ["0.0.0.0/0", "::/0"]
}

resource "hcloud_ssh_key" "admin" {
  name       = "${local.name}-admin"
  public_key = var.ssh_public_key
  labels     = local.labels
}

resource "hcloud_firewall" "node" {
  name   = "${local.name}-node"
  labels = local.labels

  rule {
    description = "SSH (admins only)"
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = var.admin_cidrs
  }

  rule {
    description = "Kubernetes API (admins only)"
    direction   = "in"
    protocol    = "tcp"
    port        = "6443"
    source_ips  = var.admin_cidrs
  }

  rule {
    description = "HTTP"
    direction   = "in"
    protocol    = "tcp"
    port        = "80"
    source_ips  = local.public_internet
  }

  rule {
    description = "HTTPS"
    direction   = "in"
    protocol    = "tcp"
    port        = "443"
    source_ips  = local.public_internet
  }

  rule {
    description = "ICMP"
    direction   = "in"
    protocol    = "icmp"
    source_ips  = local.public_internet
  }
}

resource "hcloud_server" "node" {
  name         = "${local.name}-k3s-1"
  server_type  = var.server_type
  image        = var.image
  location     = var.location
  ssh_keys     = [hcloud_ssh_key.admin.id]
  firewall_ids = [hcloud_firewall.node.id]
  labels       = merge(local.labels, { role = "k3s-server" })

  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }

  lifecycle {
    # Changing the key or image would recreate the server; do it deliberately.
    ignore_changes = [ssh_keys, image]
  }
}

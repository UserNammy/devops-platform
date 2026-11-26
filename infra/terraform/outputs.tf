output "server_name" {
  description = "Name of the k3s node."
  value       = hcloud_server.node.name
}

output "server_ipv4" {
  description = "Public IPv4 address of the k3s node."
  value       = hcloud_server.node.ipv4_address
}

output "server_ipv6" {
  description = "Public IPv6 address of the k3s node."
  value       = hcloud_server.node.ipv6_address
}

output "ssh_command" {
  description = "Initial SSH command (root login is disabled by the Ansible hardening role)."
  value       = "ssh root@${hcloud_server.node.ipv4_address}"
}

output "ansible_inventory" {
  description = "Paste into infra/ansible/inventory/hosts.ini."
  value       = <<-EOT
    [k3s_server]
    ${hcloud_server.node.name} ansible_host=${hcloud_server.node.ipv4_address}
  EOT
}

provider "hcloud" {
  # Prefer the HCLOUD_TOKEN environment variable; never commit the token.
  token = var.hcloud_token
}

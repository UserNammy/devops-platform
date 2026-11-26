terraform {
  required_version = ">= 1.9.0"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.70"
    }
  }

  # State is local by default so the project works out of the box.
  # For team use, move it to a remote backend, e.g. an S3-compatible bucket
  # (Hetzner Object Storage) with locking:
  #
  # backend "s3" {
  #   bucket                      = "devops-platform-tfstate"
  #   key                         = "prod/terraform.tfstate"
  #   region                      = "eu-central"
  #   endpoints                   = { s3 = "https://fsn1.your-objectstorage.com" }
  #   use_lockfile                = true
  #   skip_credentials_validation = true
  #   skip_region_validation      = true
  #   skip_requesting_account_id  = true
  #   skip_s3_checksum            = true
  #   use_path_style              = true
  # }
}

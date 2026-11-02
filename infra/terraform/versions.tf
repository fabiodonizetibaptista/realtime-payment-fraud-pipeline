terraform {
  required_version = ">= 1.16.0, < 2.0.0"

  required_providers {
    aiven = {
      source  = "aiven/aiven"
      version = "~> 4.61"
    }

    confluent = {
      source  = "confluentinc/confluent"
      version = "~> 2.86"
    }
  }
}

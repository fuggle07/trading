terraform {
  backend "gcs" {
    bucket = "utopian-calling-429014-r9-tfstate"
    prefix = "terraform/state"
  }
}

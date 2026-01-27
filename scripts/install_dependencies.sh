#!/bin/bash
# scripts/install_dependencies.sh
# Directive: Idempotent setup for gcloud, tfenv, and terraform on Ubuntu.

set -euo pipefail

echo "--- 🛠️  ABERFELDIE NODE: AUDITING SYSTEM DEPENDENCIES ---"

# 1. Update & Base Dependencies
sudo apt-get update && sudo apt-get install -y \
    curl gnupg software-properties-common git unzip build-essential

# 2. GCLOUD CLI (Official Apt Repo - Surgical)
if ! command -v gcloud &> /dev/null; then
    echo "📦 Installing gcloud CLI..."
    # Ensure keyrings directory exists
    sudo mkdir -p -m 755 /etc/apt/keyrings
    # Import GPG key
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/google-cloud-sdk.gpg
    # Add Repo
    echo "deb [signed-by=/etc/apt/keyrings/google-cloud-sdk.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | \
    sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list
    sudo apt-get update && sudo apt-get install -y google-cloud-cli
else
    echo "✅ gcloud CLI is already operational."
fi

# 3. TFENV (The Version Gatekeeper)
if [ ! -d "$HOME/.tfenv" ]; then
    echo "📦 Bootstrapping tfenv..."
    git clone --depth=1 https://github.com/tfutils/tfenv.git ~/.tfenv
    # Add to shell profile if not already there
    if ! grep -q "tfenv/bin" ~/.bashrc; then
        echo 'export PATH="$HOME/.tfenv/bin:$PATH"' >> ~/.bashrc
        echo 'eval "$(tfenv init -)"' >> ~/.bashrc
    fi
    export PATH="$HOME/.tfenv/bin:$PATH"
else
    echo "✅ tfenv is already present."
fi

# 4. TERRAFORM (Via tfenv)
# Using 1.10.5 as the stable baseline for early 2026 HCL
TF_VERSION="1.10.5"
export PATH="$HOME/.tfenv/bin:$PATH"

if ! command -v terraform &> /dev/null || [ "$(terraform version | head -n 1 | grep -oE '[0-9.]+' | head -n 1)" != "$TF_VERSION" ]; then
    echo "🏗️  Installing Terraform $TF_VERSION via tfenv..."
    tfenv install "$TF_VERSION"
    tfenv use "$TF_VERSION"
else
    echo "✅ Terraform $TF_VERSION is locked and loaded."
fi

echo "--- ✨ ALL DEPENDENCIES VERIFIED ---"


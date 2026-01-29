#!/bin/bash
# tail_master.sh
export CLOUDSDK_PYTHON_SITEPACKAGES=1

echo "Initializing global firehose tail..."
gcloud beta logging tail --project=$(gcloud config get-value project)


#!/bin/bash
# High-resolution master log tail
gcloud logging read 'resource.type="cloud_run_revision"' --limit 10 --follow --format="json"


#!/bin/bash
# Real-time Master Log Tail
# Uses the newer tail command to provide a live stream from Cloud Run
gcloud logging tail 'resource.type="cloud_run_revision" AND jsonPayload.component:*' --format="json"


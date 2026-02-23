from google.cloud import secretmanager

project_id = "utopian-calling-429014-r9"
secret_id = "FINNHUB_KEY"
version_id = "latest"

client = secretmanager.SecretManagerServiceClient()
name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"

response = client.access_secret_version(request={"name": name})
payload = response.payload.data.decode("UTF-8")

if payload == "PLACEHOLDER_INIT":
    print("CONFIRMED_PLACEHOLDER")
else:
    print("VALUE_SET_BUT_INVALID_OR_UNKNOWN")

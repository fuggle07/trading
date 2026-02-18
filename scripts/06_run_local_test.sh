
#!/bin/bash
export PROJECT_ID="utopian-calling-429014-r9"
export EXCHANGE_API_KEY="test_key_will_fail_but_thats_ok"
if [ -f .env ]; then
 export $(cat .env | xargs)
fi
if [ -f .env.secrets ]; then
 export $(cat .env.secrets | xargs)
fi

echo "Running reproduction script with key: ${EXCHANGE_API_KEY:0:5}..."
venv/bin/python bot/tests/reproduce_missing_data.py

import sys
import os

# Ensure current directory is in path (mimics running python main.py from bot dir)
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from signal_agent import SignalAgent
    agent = SignalAgent()
    print("SUCCESS: SignalAgent imported and initialized.")
except ImportError as e:
    print(f"FAILURE: ImportError: {e}")
except Exception as e:
    print(f"FAILURE: Error: {e}")

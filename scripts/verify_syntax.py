import sys
import os

# Add the current directory to path so imports work
sys.path.append(os.getcwd())

try:
    print("Checking imports...")
    from bot import sentiment_analyzer
    from bot import main
    print("✅ Imports successful.")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Syntax or other error: {e}")
    sys.exit(1)

print("Syntax check passed.")

import sys
import os
import uvicorn

# Add project root to python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import start_server

if __name__ == "__main__":
    port = 8765
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    start_server(port=port, open_browser=True)

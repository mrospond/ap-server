import sys
import platform
import time

while True:
    # sys.argv[0] is the script name, sys.argv[1:] are the arguments
    print(f"Hello from {platform.machine()}! Params: {sys.argv[1:]}")
    time.sleep(1)

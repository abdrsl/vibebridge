#!/usr/bin/env python3
import subprocess
import sys
import time
import re


def start_localtunnel(port=8000):
    """Start localtunnel and return URL"""
    print(f"Starting localtunnel on port {port}...")
    # Start lt process
    proc = subprocess.Popen(
        ["lt", "--port", str(port), "--print-requests"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    url = None
    for line in iter(proc.stdout.readline, ""):
        print(line.strip())
        # Look for URL pattern
        match = re.search(r"your url is:\s*(https://[^\s]+)", line, re.IGNORECASE)
        if match:
            url = match.group(1)
            print(f"Found URL: {url}")
            break

    if url:
        # Write URL to file for tunnel manager
        with open("logs/current_tunnel_url.txt", "w") as f:
            f.write(url)
        print(f"URL saved to logs/current_tunnel_url.txt")
        return url, proc
    else:
        print("Failed to get URL from localtunnel")
        proc.terminate()
        return None, None


if __name__ == "__main__":
    url, proc = start_localtunnel()
    if url:
        print(f"Tunnel URL: {url}")
        print("Press Ctrl+C to stop...")
        try:
            # Keep process running
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
    else:
        sys.exit(1)

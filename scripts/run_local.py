"""Start the local demo using ADC, or a short-lived gcloud token on request."""
import argparse
import os
import subprocess
import sys

p = argparse.ArgumentParser()
p.add_argument("--port", type=int, default=8194)
p.add_argument("--use-gcloud", action="store_true")
args = p.parse_args()
env = dict(os.environ)
if args.use_gcloud:
    env["VERTEX_ACCESS_TOKEN"] = subprocess.run(["gcloud", "auth", "print-access-token"], check=True, capture_output=True, text=True).stdout.strip()
    if not env.get("GOOGLE_CLOUD_PROJECT"):
        env["GOOGLE_CLOUD_PROJECT"] = subprocess.run(["gcloud", "config", "get-value", "project"], check=True, capture_output=True, text=True).stdout.strip()
subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.port)], env=env, check=True)

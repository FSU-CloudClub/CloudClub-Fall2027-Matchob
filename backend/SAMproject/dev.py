"""Start the Matchob local backend: Docker Compose (DynamoDB + S3) + sam local start-api

Usage:
    python dev.py           # Starts everything, Ctrl+C stops it all
    python dev.py --keep    # leave the Compose containers running after Ctrl+C

After the API starts, a smoke test calls GET /profile as the seeded user.
If it fails, the API and containers are left running so you can debug.
"""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent # backend/SAMproject
NETWORK = "matchob-local"
API_PORT = 3001
TEST_USER = "12345"  # seeded in docker/seed/users.json
TEST_URL = f"http://127.0.0.1:{API_PORT}/profile"

def fail(msg):
    print(f"\n[dev] ERROR: {msg}")
    sys.exit(1)

def run(cmd, check=True):
    print(f"[dev] $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT)
    if check and result.returncode != 0:
        fail(f"command failed (exit {result.returncode}): {' '.join(cmd)}")
    return result.returncode


def require(tool, hint):
    path = shutil.which(tool)
    if not path:
        fail(f"'{tool}' not found on PATH. {hint}")
    return path


def has_python_313():
    for name in ("python3.13", "python"):
        exe = shutil.which(name)
        if not exe:
            continue
        out = subprocess.run([exe, "--version"], capture_output=True, text=True)
        if "3.13" in (out.stdout + out.stderr):
            return True
    return False


def set_docker_host(docker):
    """Point SAM at the same Docker the `docker` CLI uses.

    SAM ignores Docker contexts and only checks DOCKER_HOST or /var/run/docker.sock,
    which Docker Desktop (Mac), Colima, and Rancher Desktop don't always create.
    An existing DOCKER_HOST is left alone so developers can override it.
    """
    if os.environ.get("DOCKER_HOST"):
        print(f"[dev] using DOCKER_HOST={os.environ['DOCKER_HOST']}")
        return
    out = subprocess.run(
        [docker, "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
        capture_output=True, text=True,
    )
    host = out.stdout.strip()
    if out.returncode == 0 and host:
        os.environ["DOCKER_HOST"] = host
        print(f"[dev] set DOCKER_HOST={host} (from the active Docker context)")


def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def remove_network_containers(docker):
    """Remove containers still attached to the network (e.g. sam's Lambda container).

    docker compose down only removes its own containers, and a leftover sam
    container keeps the matchob-local network "in use".
    """
    out = subprocess.run(
        [docker, "ps", "-aq", "--filter", f"network={NETWORK}"],
        capture_output=True, text=True,
    )
    ids = out.stdout.split()
    if ids:
        subprocess.run([docker, "rm", "-f", *ids], capture_output=True)


def copy_if_missing(example, target):
    src, dst = ROOT / example, ROOT / target
    if dst.exists():
        print(f"[dev] found {target}")
        return
    if not src.exists():
        fail(f"{example} is missing, so {target} can't be created. Pull the latest code.")
    shutil.copy(src, dst)
    print(f"[dev] created {target} from {example}")


def wait_for_api(api, timeout=120):
    """Wait until sam local start-api accepts connections. False if it exits or times out."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if api.poll() is not None:
            return False
        try:
            with socket.create_connection(("127.0.0.1", API_PORT), timeout=1):
                return True
        except OSError:
            time.sleep(1)
    return False


def smoke_test():
    """Call GET /profile as the seeded user. Returns (passed, status, body)."""
    req = urllib.request.Request(TEST_URL, headers={"X-Local-User": TEST_USER})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status, body = resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read().decode()
    except (urllib.error.URLError, TimeoutError) as e:
        return False, None, str(getattr(e, "reason", e))
    return status == 200 and TEST_USER in body, status, body


def report_failure(status, body):
    print("\n[dev] ===== SMOKE TEST FAILED =====")
    print(f"[dev] GET {TEST_URL} (X-Local-User: {TEST_USER})")
    print(f"[dev] status: {status}")
    print(f"[dev] body:   {body}")
    print("[dev] The sam local output above has the Lambda's traceback.")
    print("[dev] See the Troubleshooting table in docs/setup.md.")
    print("[dev] The API and containers are still running so you can debug.")
    print("[dev] Ctrl+C stops the API only. Run `docker compose down` when you're done.\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="don't stop containers on exit")
    args = parser.parse_args()

    # 1. Check tools are installed and Docker is running
    docker = require("docker", "Install Docker Desktop.")
    sam = require("sam", "Install the AWS SAM CLI.")
    if subprocess.run([docker, "info"], capture_output=True).returncode != 0:
        fail("Docker is installed but not running. Start Docker Desktop.")
    set_docker_host(docker)

    # 2. Create env files from the examples if they don't exist
    copy_if_missing(".env.example", ".env")
    copy_if_missing("env.example.json", "env.json")

    if port_in_use(API_PORT):
        fail(f"Port {API_PORT} is already in use. Stop the other `dev.py`/`sam local` "
             f"(find it with `lsof -i :{API_PORT}`) and try again.")

    # 3. Start DynamoDB + S3 fresh, then wait for the seed step
    run([docker, "compose", "down", "--remove-orphans"], check=False)
    run([docker, "compose", "up", "-d"])
    print("[dev] waiting for DynamoDB seed...")
    if run([docker, "compose", "wait", "dynamodb-init"], check=False) != 0:
        run([docker, "compose", "logs", "dynamodb-init"], check=False)
        fail("DynamoDB seed step failed (logs above).")

    keep = args.keep
    api = None
    try:
        # 4. Build (inside Docker if Python 3.13 isn't installed)
        build = [sam, "build"]
        if not has_python_313():
            print("[dev] Python 3.13 not found, building inside a container")
            build.append("--use-container")
        run(build)

        # 5. Start the API in the background so we can test it
        cmd = [sam, "local", "start-api",
               "--port", str(API_PORT),
               "--env-vars", "env.json",
               "--docker-network", NETWORK]
        print(f"[dev] $ {' '.join(cmd)}")
        api = subprocess.Popen(cmd, cwd=ROOT)

        # 6. Smoke test: on failure, print it and leave everything running
        if not wait_for_api(api):
            keep = True
            report_failure(None, "sam local start-api exited or never opened the port (see output above)")
        else:
            passed, status, body = smoke_test()
            if passed:
                print(f"\n[dev] smoke test passed: GET /profile -> {status}")
                print(f"[dev] API on http://localhost:{API_PORT} (Ctrl+C to stop)\n")
            else:
                keep = True
                report_failure(status, body)

        api.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if api is not None and api.poll() is None:
            # sam also receives Ctrl+C; give it a moment to shut down on its own
            try:
                api.wait(timeout=10)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                api.terminate()
        if keep:
            print("\n[dev] containers left running. Stop them with: docker compose down")
        else:
            print("\n[dev] stopping containers...")
            remove_network_containers(docker)
            subprocess.run([docker, "compose", "down"], cwd=ROOT)


if __name__ == "__main__":
    main()
    
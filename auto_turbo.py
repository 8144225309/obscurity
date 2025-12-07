#!/usr/bin/env python3
import subprocess
import datetime
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
BRANCH = "main"
INTERVAL_SECONDS = 30  # how often to check

def run_git(*args):
    return subprocess.run(
        ["git", *args],
        cwd=REPO,
        text=True,
        capture_output=True,
    )

print("🚀 auto-turbo loop starting...")
print(f"Repo: {REPO}")
print(f"Branch: {BRANCH}")
print(f"Interval: {INTERVAL_SECONDS} seconds")

try:
    while True:
        # Check for changes
        status = run_git("status", "--porcelain")
        if status.returncode != 0:
            print("git status failed:")
            print(status.stderr.strip())
            time.sleep(INTERVAL_SECONDS)
            continue

        if not status.stdout.strip():
            # Nothing changed
            # print(".", end="", flush=True)  # uncomment if you want a heartbeat
            time.sleep(INTERVAL_SECONDS)
            continue

        print("\n=== Changes detected ===")
        print(status.stdout.strip())

        # Stage everything
        add = run_git("add", ".")
        if add.returncode != 0:
            print("git add failed:")
            print(add.stderr.strip())
            time.sleep(INTERVAL_SECONDS)
            continue

        # Commit with timestamp
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"auto: {ts}"
        commit = run_git("commit", "-m", msg)
        if commit.returncode != 0:
            # Probably a race / nothing to commit
            print("git commit issue:")
            print((commit.stdout + commit.stderr).strip())
            time.sleep(INTERVAL_SECONDS)
            continue

        print(commit.stdout.strip() or commit.stderr.strip())

        # Push
        push = run_git("push", "origin", BRANCH)
        if push.returncode != 0:
            print("git push failed:")
            print(push.stderr.strip())
        else:
            print(push.stdout.strip() or "Pushed successfully.")

        # Wait for next round
        time.sleep(INTERVAL_SECONDS)

except KeyboardInterrupt:
    print("\n🛑 auto-turbo loop stopped by user.")

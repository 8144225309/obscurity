import subprocess
import datetime
from pathlib import Path

# Path to your repo (this file lives in the root)
REPO = Path(__file__).resolve().parent
BRANCH = "main"   # or "master" if that’s what you used

def run(*args):
    """Run a git command and return CompletedProcess."""
    return subprocess.run(
        args,
        cwd=REPO,
        text=True,
        capture_output=True,
    )

# 1) Check if there are any changes
status = run("git", "status", "--porcelain")

if not status.stdout.strip():
    print("No changes, nothing to commit.")
    raise SystemExit(0)

print("Changes detected:")
print(status.stdout)

# 2) Stage everything
add = run("git", "add", ".")
if add.returncode != 0:
    print("git add failed:")
    print(add.stderr)
    raise SystemExit(add.returncode)

# 3) Commit with an auto message
ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
msg = f"auto: {ts}"

commit = run("git", "commit", "-m", msg)
print(commit.stdout or commit.stderr)
if commit.returncode != 0:
    # Probably "nothing to commit" race condition
    raise SystemExit(commit.returncode)

# 4) Push
push = run("git", "push", "origin", BRANCH)
print(push.stdout or push.stderr)
if push.returncode != 0:
    print("git push failed:")
    print(push.stderr)
    raise SystemExit(push.returncode)

print("✅ Auto-commit + push complete.")

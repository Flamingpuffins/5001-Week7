#!/usr/bin/env python3
"""
Setup a sample Git repository to test the GitHub agent against.
Run this once: python setup_sample_repo.py
"""

import subprocess
import os

REPO = "./sample_repo"

files = {
    "src/auth/login.py": '''\
def login(username, password):
    """Authenticate a user."""
    from db import find_user
    user = find_user(username)
    # TODO: add input validation
    if user and user.password == password:
        return generate_token(user)
    return None
''',
    "src/pricing/calculator.py": '''\
def calculate_price(item):
    discount = item.price * 0.1
    return item.price - discount

def calculate_cart_total(cart):
    # duplicated pricing logic from calculator.py
    total = 0
    for item in cart.items:
        discount = item.price * 0.1
        total += item.price - discount
    return total
''',
    "README.md": "# Sample Repo\nThis is a sample repo for the GitHub Agent demo.\n",
    "tests/test_auth.py": "# TODO: write auth tests\n",
}

def run(cmd, cwd=None):
    result = subprocess.run(cmd, shell=True, cwd=cwd,
                            capture_output=True, text=True)
    if result.returncode != 0 and result.stderr:
        print(f"  stderr: {result.stderr.strip()}")
    return result.stdout.strip()

print(f"Setting up sample repo at {REPO}...")
os.makedirs(REPO, exist_ok=True)

run("git init", cwd=REPO)
run('git config user.email "agent@example.com"', cwd=REPO)
run('git config user.name "GitHub Agent"', cwd=REPO)

# Initial commit
for path, content in files.items():
    full = os.path.join(REPO, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(content)

run("git add .", cwd=REPO)
run('git commit -m "Initial commit: auth and pricing modules"', cwd=REPO)

# Make a second commit with a change
with open(os.path.join(REPO, "src/auth/login.py"), "a") as f:
    f.write('\ndef logout(user_id):\n    """Log out a user — no token invalidation yet."""\n    pass\n')

run("git add .", cwd=REPO)
run('git commit -m "Add logout stub (no token invalidation)"', cwd=REPO)

print("✅ Sample repo ready.")
print("   Two commits: HEAD~1..HEAD shows the logout stub change.")
print(f"   Path: {os.path.abspath(REPO)}")

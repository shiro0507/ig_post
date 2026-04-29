"""
Monthly job to refresh the Instagram long-lived access token (valid 60 days).
Requires GH_PAT with Fine-grained permissions: Secrets (read/write).
"""
import os
import subprocess
import requests

ACCESS_TOKEN = os.environ["INSTAGRAM_ACCESS_TOKEN"]
GH_PAT = os.environ["GH_PAT"]
GITHUB_REPOSITORY = os.environ["GITHUB_REPOSITORY"]


def refresh_token() -> str:
    r = requests.get(
        "https://graph.instagram.com/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": ACCESS_TOKEN},
    )
    r.raise_for_status()
    return r.json()["access_token"]


def update_secret(new_token: str):
    subprocess.run(
        ["gh", "secret", "set", "INSTAGRAM_ACCESS_TOKEN",
         "--repo", GITHUB_REPOSITORY,
         "--body", new_token],
        check=True,
        env={**os.environ, "GH_TOKEN": GH_PAT},
    )


def main():
    print("Refreshing Instagram access token...")
    new_token = refresh_token()
    print("Updating GitHub secret...")
    update_secret(new_token)
    print("Token refreshed successfully.")


if __name__ == "__main__":
    main()

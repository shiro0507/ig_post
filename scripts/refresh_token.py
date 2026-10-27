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
    # raise_for_status() は例外メッセージにURL(=access_tokenクエリ付き)を含むので使わない
    if not r.ok:
        err = r.json().get("error", {}) if r.headers.get("content-type", "").startswith("application/json") else {}
        raise SystemExit(f"トークンの延長に失敗しました ({r.status_code}): {err.get('message', r.reason)}")
    return r.json()["access_token"]


def update_secret(new_token: str):
    # トークンは --body 引数ではなく標準入力で渡す。引数に入れると、失敗時の
    # CalledProcessError のメッセージ(=公開ログ)にトークンがそのまま出てしまう。
    result = subprocess.run(
        ["gh", "secret", "set", "INSTAGRAM_ACCESS_TOKEN", "--repo", GITHUB_REPOSITORY],
        input=new_token,
        text=True,
        capture_output=True,
        env={**os.environ, "GH_TOKEN": GH_PAT},
    )
    if result.returncode != 0:
        raise SystemExit(f"GitHub secret の更新に失敗しました(GH_PAT の期限・権限を確認): {result.stderr.strip()}")


def main():
    print("Refreshing Instagram access token...")
    new_token = refresh_token()
    print("Updating GitHub secret...")
    update_secret(new_token)
    print("Token refreshed successfully.")


if __name__ == "__main__":
    main()

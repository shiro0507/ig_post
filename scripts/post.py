import argparse
import os
import sys
import time
import requests
from datetime import date
from pathlib import Path

#ACCESS_TOKEN = os.environ["INSTAGRAM_ACCESS_TOKEN"]
#ACCOUNT_ID = os.environ["INSTAGRAM_ACCOUNT_ID"]

ACCESS_TOKEN = "IGAASjyxqv0lRBZAFpRR29oRGpzRGJWWnhKMmRtbDc3OVF6SjhJbkVlelVzX05yUC1nNTR3RXBCa3hTTEJhTUxwSkR2VjA3SmpISUZATT0VsVHd6bGVndm1jMWNIYVhQQ0xUSFpIVk1zNG05R2VTNjk4N24yMksxT0NxMnE4bTFCSQZDZD"
ACCOUNT_ID = "26806844172340114"

GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "shiro0507/ig_post")
IG_API = "https://graph.instagram.com/v25.0"


def get_content(target_date: str, skip_video_check: bool = False) -> tuple[Path, str]:
    content_dir = Path("content") / target_date
    video_path = content_dir / "video.mp4"
    caption_path = content_dir / "caption.txt"

    if not skip_video_check and not video_path.exists():
        print(f"No content found for {target_date}, skipping.")
        sys.exit(0)

    caption = caption_path.read_text(encoding="utf-8").strip() if caption_path.exists() else ""
    return video_path, caption


def get_video_url(video_path: Path, target_date: str) -> str:
    owner, repo = GITHUB_REPOSITORY.split("/", 1)
    return f"https://raw.githubusercontent.com/{owner}/{repo}/main/content/{target_date}/{video_path.name}"


_BLOCKED_HOSTS = ("github.com/", "github.com:")

def _validate_video_url(url: str):
    for host in _BLOCKED_HOSTS:
        if host in url:
            raise ValueError(
                f"Instagram cannot fetch videos from {url!r} — "
                "GitHub's robots.txt blocks its crawler.\n"
                "Use raw.githubusercontent.com (commit the file to the repo) "
                "or a public CDN (S3, R2, etc.)."
            )


def create_reel_container(video_url: str, caption: str) -> str:
    r = requests.post(
        f"{IG_API}/{ACCOUNT_ID}/media",
        params={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true",
            "access_token": ACCESS_TOKEN,
        },
    )
    r.raise_for_status()
    return r.json()["id"]


def wait_for_container(container_id: str, timeout: int = 300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(
            f"{IG_API}/{container_id}",
            params={"fields": "status_code,status,error_message", "access_token": ACCESS_TOKEN},
        )
        r.raise_for_status()
        data = r.json()
        status_code = data.get("status_code")
        print(f"  container status: {status_code}")
        if status_code == "FINISHED":
            return
        if status_code == "ERROR":
            raise RuntimeError(f"Container processing failed: {data}")
        time.sleep(15)
    raise TimeoutError("Timed out waiting for Instagram to process the video")


def publish_reel(container_id: str) -> str:
    r = requests.post(
        f"{IG_API}/{ACCOUNT_ID}/media_publish",
        params={"creation_id": container_id, "access_token": ACCESS_TOKEN},
    )
    r.raise_for_status()
    return r.json()["id"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Target date (YYYY-MM-DD), defaults to today")
    parser.add_argument("--video-url", help="Direct video URL (skips GitHub URL construction)")
    args = parser.parse_args()

    target_date = args.date or date.today().isoformat()
    print(f"Posting content for {target_date}")

    _, caption = get_content(target_date, skip_video_check=bool(args.video_url))
    if args.video_url:
        video_url = args.video_url
    elif GITHUB_REPOSITORY:
        video_url = get_video_url(Path(f"content/{target_date}/video.mp4"), target_date)
    else:
        parser.error("--video-url is required when GITHUB_REPOSITORY is not set")
    print(f"Video URL: {video_url}")
    _validate_video_url(video_url)

    print("Creating Instagram media container...")
    container_id = create_reel_container(video_url, caption)
    print(f"Container ID: {container_id}")

    print("Waiting for Instagram to process the video...")
    wait_for_container(container_id)

    print("Publishing reel...")
    post_id = publish_reel(container_id)
    print(f"Done! Published post ID: {post_id}")


if __name__ == "__main__":
    main()

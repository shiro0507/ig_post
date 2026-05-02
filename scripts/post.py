import argparse
import os
import sys
import time
import requests
from datetime import date
from pathlib import Path

ACCESS_TOKEN = os.environ["INSTAGRAM_ACCESS_TOKEN"]
ACCOUNT_ID = os.environ["INSTAGRAM_ACCOUNT_ID"]

GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "shiro0507/ig_post")
IG_API = "https://graph.instagram.com/v25.0"


def parse_thumb_offset(value: str, fps: float) -> int:
    stripped = value.strip()
    if stripped.isdigit():
        return int(int(stripped) / fps * 1000)
    parts = stripped.replace(".", ":").split(":")
    if len(parts) != 3:
        raise ValueError(f"thumb_offset must be frame number or hh:mm:ff format, got: {value!r}")
    hh, mm, ff = int(parts[0]), int(parts[1]), int(parts[2])
    return int((hh * 3600 + mm * 60) * 1000 + (ff / fps) * 1000)


def get_content(target_date: str, skip_video_check: bool = False) -> tuple[Path, str, int | None]:
    content_dir = Path("content") / target_date
    video_path = content_dir / "video.mp4"
    caption_path = content_dir / "caption.txt"
    thumb_offset_path = content_dir / "thumb_offset.txt"
    fps_path = content_dir / "fps.txt"

    if not skip_video_check and not video_path.exists():
        print(f"No content found for {target_date}, skipping.")
        sys.exit(0)

    caption = caption_path.read_text(encoding="utf-8").strip() if caption_path.exists() else ""

    thumb_offset = None
    if thumb_offset_path.exists():
        fps = float(fps_path.read_text().strip()) if fps_path.exists() else 30.0
        thumb_offset = parse_thumb_offset(thumb_offset_path.read_text(), fps)

    return video_path, caption, thumb_offset


def get_video_url(video_path: Path, target_date: str) -> str:
    owner, repo = GITHUB_REPOSITORY.split("/", 1)
    return f"https://raw.githubusercontent.com/{owner}/{repo}/main/content/{target_date}/{video_path.name}"


def create_reel_container_url(video_url: str, caption: str, thumb_offset: int | None = None) -> str:
    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true",
        "access_token": ACCESS_TOKEN,
    }
    if thumb_offset is not None:
        params["thumb_offset"] = thumb_offset
    r = requests.post(f"{IG_API}/{ACCOUNT_ID}/media", params=params)
    r.raise_for_status()
    return r.json()["id"]


def create_reel_container_resumable(caption: str, thumb_offset: int | None = None) -> tuple[str, str]:
    params = {
        "media_type": "REELS",
        "upload_type": "resumable",
        "caption": caption,
        "share_to_feed": "true",
        "access_token": ACCESS_TOKEN,
    }
    if thumb_offset is not None:
        params["thumb_offset"] = thumb_offset
    r = requests.post(f"{IG_API}/{ACCOUNT_ID}/media", params=params)
    r.raise_for_status()
    data = r.json()
    return data["id"], data["uri"]


def upload_video_resumable(upload_uri: str, video_path: Path):
    file_size = video_path.stat().st_size
    with open(video_path, "rb") as f:
        video_data = f.read()
    headers = {
        "Authorization": f"OAuth {ACCESS_TOKEN}",
        "offset": "0",
        "file_size": str(file_size),
    }
    r = requests.post(upload_uri, headers=headers, data=video_data)
    r.raise_for_status()


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
    parser.add_argument("--thumb-offset", type=int, help="Thumbnail frame offset in milliseconds")
    args = parser.parse_args()

    target_date = args.date or date.today().isoformat()
    print(f"Posting content for {target_date}")

    video_path, caption, thumb_offset = get_content(target_date, skip_video_check=bool(args.video_url))
    effective_thumb_offset = args.thumb_offset if args.thumb_offset is not None else thumb_offset

    print("Creating Instagram media container...")
    if args.video_url:
        print(f"Video URL: {args.video_url}")
        container_id = create_reel_container_url(args.video_url, caption, effective_thumb_offset)
    else:
        print(f"Uploading video: {video_path} ({video_path.stat().st_size // 1024} KB)")
        container_id, upload_uri = create_reel_container_resumable(caption, effective_thumb_offset)
        print("Uploading video bytes...")
        upload_video_resumable(upload_uri, video_path)
    print(f"Container ID: {container_id}")

    print("Waiting for Instagram to process the video...")
    wait_for_container(container_id)

    print("Publishing reel...")
    post_id = publish_reel(container_id)
    print(f"Done! Published post ID: {post_id}")


if __name__ == "__main__":
    main()

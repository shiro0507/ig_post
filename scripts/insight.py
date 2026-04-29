import json
import os
import requests
from datetime import datetime
from pathlib import Path
import zoneinfo

ACCESS_TOKEN = os.environ["INSTAGRAM_ACCESS_TOKEN"]
ACCOUNT_ID = os.environ["INSTAGRAM_ACCOUNT_ID"]
IG_API = "https://graph.instagram.com/v25.0"
JSON_FILE = Path("data/insta_stats.json")


def get_followers_count():
    res = requests.get(
        f"{IG_API}/{ACCOUNT_ID}",
        params={"access_token": ACCESS_TOKEN, "fields": "followers_count"},
    ).json()
    if "error" in res:
        print(f"Warning: Could not fetch followers_count: {res['error'].get('message', 'unknown error')}")
        return None
    return res.get("followers_count")


def get_reels_data():
    res = requests.get(
        f"{IG_API}/{ACCOUNT_ID}/media",
        params={
            "access_token": ACCESS_TOKEN,
            "fields": "id,caption,media_type,media_product_type,timestamp",
        },
    ).json()

    today = datetime.now(zoneinfo.ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d")
    new_stats = {}

    for media in res.get("data", []):
        is_reel = (
            media["media_type"] in ("VIDEO", "REEL")
            and media.get("media_product_type") == "REELS"
        )
        if not is_reel:
            continue

        m_id = media["id"]
        ins_res = requests.get(
            f"{IG_API}/{m_id}/insights",
            params={
                "metric": "views,reach,saved,total_interactions,likes,comments,shares",
                "period": "lifetime",
                "access_token": ACCESS_TOKEN,
            },
        ).json()

        metrics = {"date": today}
        if "data" in ins_res:
            for m in ins_res["data"]:
                if "values" in m and len(m["values"]) > 0:
                    metrics[m["name"]] = m["values"][0]["value"]
                elif "value" in m:
                    metrics[m["name"]] = m["value"]
        else:
            print(f"Warning: No data for {m_id}: {ins_res.get('error', {}).get('message', 'unknown error')}")

        new_stats[m_id] = {
            "caption": media.get("caption", "")[:30],
            "created_at": media["timestamp"],
            "metrics": metrics,
        }
    return new_stats


def update_json():
    if JSON_FILE.exists():
        full_data = json.loads(JSON_FILE.read_text(encoding="utf-8"))
    else:
        full_data = {}

    today = datetime.now(zoneinfo.ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d")

    followers = get_followers_count()
    if followers is not None:
        if "follower_history" not in full_data:
            full_data["follower_history"] = []
        if not any(h["date"] == today for h in full_data["follower_history"]):
            full_data["follower_history"].append({"date": today, "followers_count": followers})

    latest_reels = get_reels_data()

    for m_id, info in latest_reels.items():
        if m_id not in full_data:
            full_data[m_id] = {
                "caption": info["caption"],
                "created_at": info["created_at"],
                "history": [],
            }
        if not any(h["date"] == info["metrics"]["date"] for h in full_data[m_id]["history"]):
            full_data[m_id]["history"].append(info["metrics"])

    JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    JSON_FILE.write_text(json.dumps(full_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated: {len(latest_reels)} reels saved to {JSON_FILE}")


if __name__ == "__main__":
    update_json()

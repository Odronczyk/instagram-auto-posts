import json
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


API_URL = "https://graph.instagram.com/v24.0"
REPOSITORY = "Odronczyk/instagram-auto-posts"
BRANCH = "main"

IG_USER_ID = os.environ["IG_USER_ID"]
ACCESS_TOKEN = os.environ["IG_ACCESS_TOKEN"]

POSTS_FILE = Path("posts.json")
STATE_FILE = Path("state.json")
IMAGES_FOLDER = Path("images")

MAX_POSTS = 70


def request_json(method, url, operation, **kwargs):
    response = requests.request(
        method,
        url,
        timeout=90,
        **kwargs,
    )

    try:
        data = response.json()
    except ValueError:
        raise RuntimeError(
            f"{operation}: Instagram zwrócił nieprawidłową odpowiedź: "
            f"{response.text}"
        )

    if not response.ok:
        raise RuntimeError(f"{operation}: {data}")

    return data


def wait_for_container(container_id):
    for attempt in range(30):
        data = request_json(
            "GET",
            f"{API_URL}/{container_id}",
            "Sprawdzanie kontenera",
            params={
                "fields": "status_code,status",
                "access_token": ACCESS_TOKEN,
            },
        )

        status = data.get("status_code")
        print(f"Kontener {container_id}: {status}")

        if status in {"FINISHED", "PUBLISHED"}:
            return

        if status in {"ERROR", "EXPIRED"}:
            raise RuntimeError(
                f"Przetwarzanie kontenera zakończyło się statusem {status}: "
                f"{data.get('status', '')}"
            )

        time.sleep(5)

    raise RuntimeError("Instagram zbyt długo przetwarza kontener")


def create_image_container(image_url):
    data = request_json(
        "POST",
        f"{API_URL}/{IG_USER_ID}/media",
        "Tworzenie kontenera zdjęcia",
        data={
            "image_url": image_url,
            "is_carousel_item": "true",
            "access_token": ACCESS_TOKEN,
        },
    )

    container_id = data["id"]
    wait_for_container(container_id)

    return container_id


if not POSTS_FILE.exists():
    raise FileNotFoundError("Brakuje pliku posts.json")

if not STATE_FILE.exists():
    raise FileNotFoundError("Brakuje pliku state.json")

with POSTS_FILE.open("r", encoding="utf-8") as file:
    posts = json.load(file)

with STATE_FILE.open("r", encoding="utf-8") as file:
    state = json.load(file)

if len(posts) != MAX_POSTS:
    raise RuntimeError(
        f"posts.json powinien zawierać {MAX_POSTS} wpisów, "
        f"a zawiera {len(posts)}"
    )

if state.get("finished"):
    print("Wszystkie 70 postów zostało już opublikowanych.")
    raise SystemExit(0)

today = datetime.now(ZoneInfo("Europe/Warsaw")).date().isoformat()

if state.get("last_publish_date") == today:
    print(f"Post na dzień {today} został już opublikowany.")
    raise SystemExit(0)

post_number = int(state.get("next_post", 1))

if post_number < 1 or post_number > MAX_POSTS:
    state["finished"] = True

    with STATE_FILE.open("w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)

    print("Brak kolejnych postów do opublikowania.")
    raise SystemExit(0)

post = next(
    (item for item in posts if int(item["number"]) == post_number),
    None,
)

if post is None:
    raise RuntimeError(
        f"Nie znaleziono wpisu numer {post_number} w posts.json"
    )

expected_image = f"{post_number:03d}.jpg"

if post.get("image") != expected_image:
    raise RuntimeError(
        f"Wpis numer {post_number} powinien wskazywać plik "
        f"{expected_image}, a wskazuje {post.get('image')}"
    )

first_image_path = IMAGES_FOLDER / expected_image
second_image_path = IMAGES_FOLDER / "opis.jpg"

if not first_image_path.exists():
    raise FileNotFoundError(f"Brakuje pliku {first_image_path}")

if not second_image_path.exists():
    raise FileNotFoundError(f"Brakuje pliku {second_image_path}")

first_image_url = (
    f"https://raw.githubusercontent.com/"
    f"{REPOSITORY}/{BRANCH}/images/{expected_image}"
)

second_image_url = (
    f"https://raw.githubusercontent.com/"
    f"{REPOSITORY}/{BRANCH}/images/opis.jpg"
)

caption = post["caption"]

print(f"Publikowanie karuzeli numer {post_number}")
print(f"Pierwszy slajd: {first_image_url}")
print(f"Drugi slajd: {second_image_url}")

first_container_id = create_image_container(first_image_url)
second_container_id = create_image_container(second_image_url)

carousel_data = request_json(
    "POST",
    f"{API_URL}/{IG_USER_ID}/media",
    "Tworzenie karuzeli",
    data={
        "media_type": "CAROUSEL",
        "children": f"{first_container_id},{second_container_id}",
        "caption": caption,
        "access_token": ACCESS_TOKEN,
    },
)

carousel_id = carousel_data["id"]
wait_for_container(carousel_id)

publish_data = request_json(
    "POST",
    f"{API_URL}/{IG_USER_ID}/media_publish",
    "Publikowanie karuzeli",
    data={
        "creation_id": carousel_id,
        "access_token": ACCESS_TOKEN,
    },
)

published_media_id = publish_data["id"]

state["last_publish_date"] = today
state["last_published_post"] = post_number
state["last_media_id"] = published_media_id
state["next_post"] = post_number + 1

if post_number == MAX_POSTS:
    state["finished"] = True

with STATE_FILE.open("w", encoding="utf-8") as file:
    json.dump(state, file, ensure_ascii=False, indent=2)

print(
    f"Opublikowano karuzelę {post_number:03d}. "
    f"Instagram Media ID: {published_media_id}"
)

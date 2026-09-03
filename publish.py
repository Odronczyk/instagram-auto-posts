import os
import time
import requests

API_URL = "https://graph.instagram.com/v24.0"

IG_USER_ID = os.environ["IG_USER_ID"]
ACCESS_TOKEN = os.environ["IG_ACCESS_TOKEN"]

IMAGE_URL = (
    "https://raw.githubusercontent.com/"
    "Odronczyk/instagram-auto-posts/main/001.jpg"
)

CAPTION = """Wyzwanie na dziś! ✅

Podejmujesz się?

#wyzwanie #wyzwanienadzis #nawyki #motywacja"""


def check_response(response, operation):
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError(
            f"{operation}: nieprawidłowa odpowiedź: {response.text}"
        )

    if not response.ok:
        raise RuntimeError(f"{operation}: {data}")

    return data


print("Tworzenie kontenera zdjęcia...")

create_response = requests.post(
    f"{API_URL}/{IG_USER_ID}/media",
    data={
        "image_url": IMAGE_URL,
        "caption": CAPTION,
        "access_token": ACCESS_TOKEN,
    },
    timeout=60,
)

create_data = check_response(create_response, "Tworzenie kontenera")
container_id = create_data["id"]

print(f"Utworzono kontener: {container_id}")

for attempt in range(10):
    status_response = requests.get(
        f"{API_URL}/{container_id}",
        params={
            "fields": "status_code",
            "access_token": ACCESS_TOKEN,
        },
        timeout=60,
    )

    status_data = check_response(status_response, "Sprawdzanie kontenera")
    status = status_data.get("status_code")

    print(f"Status zdjęcia: {status}")

    if status == "FINISHED":
        break

    if status in {"ERROR", "EXPIRED"}:
        raise RuntimeError(f"Przetwarzanie zdjęcia nie powiodło się: {status}")

    time.sleep(5)
else:
    raise RuntimeError("Instagram zbyt długo przetwarza zdjęcie")

print("Publikowanie posta...")

publish_response = requests.post(
    f"{API_URL}/{IG_USER_ID}/media_publish",
    data={
        "creation_id": container_id,
        "access_token": ACCESS_TOKEN,
    },
    timeout=60,
)

publish_data = check_response(publish_response, "Publikowanie posta")

print(f"Post został opublikowany. ID: {publish_data['id']}")

import json
import logging
import time
from getpass import getpass
from pathlib import Path
from urllib.parse import quote

import requests


GROUP_NAME = "AIE-8"
API_URL = "https://cloud-api.yandex.net/v1/disk"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(message)s",
    datefmt="%H:%M:%S",
)


def create_folder(session):
    response = session.put(
        f"{API_URL}/resources",
        params={"path": GROUP_NAME},
        timeout=30,
    )

    if response.status_code == 409:
        # Проверяем, что по этому пути действительно находится папка.
        response = session.get(
            f"{API_URL}/resources",
            params={"path": GROUP_NAME},
            timeout=30,
        )
        response.raise_for_status()

        if response.json()["type"] != "dir":
            raise RuntimeError("Название папки уже занято файлом.")

        logging.info("Папка %s уже существует", GROUP_NAME)
        return

    response.raise_for_status()
    logging.info("Создана папка %s", GROUP_NAME)


def upload_image(session, image_url, disk_path):
    response = session.post(
        f"{API_URL}/resources/upload",
        params={
            "url": image_url,
            "path": disk_path,
            "overwrite": "false",
        },
        timeout=30,
    )
    response.raise_for_status()
    operation_url = response.json()["href"]

    logging.info("Яндекс.Диск загружает картинку")

    for _ in range(60):
        response = session.get(operation_url, timeout=30)
        response.raise_for_status()
        status = response.json()["status"]

        if status == "success":
            logging.info("Картинка загружена")
            return

        if status == "failed":
            raise RuntimeError("Яндекс.Диск не смог загрузить картинку.")

        time.sleep(2)

    raise RuntimeError(
        "Ожидание закончилось. Проверьте Диск: "
        "загрузка может продолжаться."
    )


def save_result(session, disk_path):
    response = session.get(
        f"{API_URL}/resources",
        params={"path": disk_path},
        timeout=30,
    )
    response.raise_for_status()
    file_info = response.json()

    result = [
        {
            "file_name": file_info["name"],
            "size": file_info["size"],
        }
    ]

    result_path = Path(__file__).with_name("result.json")

    with result_path.open("w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=4)

    logging.info("Размер картинки: %s байт", file_info["size"])
    logging.info("Результат сохранён в %s", result_path)


def main():
    text = input("Введите текст для картинки: ").strip()

    if not text or text in {".", ".."}:
        print("Введите непустой текст, а не только точку или две.")
        return

    if any(char in text for char in '/\\:*?"<>|'):
        print('Не используйте в тексте символы / \\ : * ? " < > |')
        return

    token = getpass("Введите токен Яндекс.Диска: ").strip()

    if not token:
        print("Токен не должен быть пустым.")
        return

    image_url = f"https://cataas.com/cat/says/{quote(text, safe='')}"
    disk_path = f"{GROUP_NAME}/{text}"

    try:
        with requests.Session() as session:
            session.headers.update({"Authorization": f"OAuth {token}"})

            create_folder(session)
            upload_image(session, image_url, disk_path)
            save_result(session, disk_path)

    except requests.HTTPError as error:
        logging.error(
            "Ошибка API, HTTP %s. "
            "Проверьте токен, свободное место и имя файла.",
            error.response.status_code,
        )
    except requests.RequestException:
        logging.error("Ошибка соединения. Проверьте интернет.")
    except (RuntimeError, OSError) as error:
        logging.error("%s", error)


if __name__ == "__main__":
    main()
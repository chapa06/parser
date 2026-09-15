import csv
import os
import time
import random
from datetime import datetime
from urllib.parse import quote

import requests
from dotenv import load_dotenv


load_dotenv()

INPUT_CSV = os.getenv("INPUT_CSV", "1.csv")
OUTPUT_CSV = os.getenv("OUTPUT_CSV", "2.csv")

WB_WBAUID = os.getenv("WB_WBAUID", "")
WB_X_WBAAS_TOKEN = os.getenv("WB_X_WBAAS_TOKEN", "")
WB_AUTHORIZATION = os.getenv("WB_AUTHORIZATION", "")
WB_DEVICE_ID = os.getenv("WB_DEVICE_ID", "")
WB_WBX_VALIDATION_KEY = os.getenv("WB_WBX_VALIDATION_KEY", "")
WB_WID_SDK_ID_TOKEN = os.getenv("WB_WID_SDK_ID_TOKEN", "")
WB_ROUTEB = os.getenv("WB_ROUTEB", "")

WB_X_USERID = os.getenv("WB_X_USERID", "0")

WB_DEVICEID_HEADER = os.getenv(
    "WB_DEVICEID_HEADER",
    "site_cad93bae129444c79c22c8b0708bf9c6"
)

REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.5"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/153.0.0.0 "
    "Safari/537.36 "
    "Edg/153.0.0.0"
)

URL = (
    "https://www.wildberries.ru/"
    "__internal/search/exactmatch/ru/common/v18/search"
)

PARAMS = {
    "ab_testid": "catboost_m10_s2_new_calib",
    "appType": "1",
    "autoselectFilters": "false",
    "curr": "rub",
    "dest": "-1255942",
    "hide_vflags": "4294967296",
    "inheritFilters": "true",
    "lang": "ru",
    "locale": "ru",
    "resultset": "filters",
    "scale": "4",
    "spp": "30",
    "suppressSpellcheck": "false",
    "uclusters": "2",
}


def build_headers(query):
    referer = (
        "https://www.wildberries.ru/catalog/0/search.aspx"
        f"?search={quote(query)}"
    )

    x_queryid = (
        f"qidnull{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        f"{random.randint(100000, 999999)}"
    )

    headers = {
        "accept": "*/*",
        "accept-language": (
            "ru,en;q=0.9,en-GB;q=0.8,"
            "en-US;q=0.7,ru-RU;q=0.6"
        ),
        "cache-control": "no-cache",
        "deviceid": WB_DEVICEID_HEADER,
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": referer,
        "sec-ch-ua": (
            '"Microsoft Edge";v="153", '
            '"Not_A Brand";v="8", '
            '"Chromium";v="153"'
        ),
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": USER_AGENT,
        "x-queryid": x_queryid,
        "x-requested-with": "XMLHttpRequest",
        "x-spa-version": "14.24.4",
        "x-userid": WB_X_USERID,
    }

    if WB_AUTHORIZATION:
        headers["authorization"] = WB_AUTHORIZATION

    return headers


def create_session():
    session = requests.Session()

    cookies = {
        "_wbauid": WB_WBAUID,
        "x_wbaas_token": WB_X_WBAAS_TOKEN,
        "device_id": WB_DEVICE_ID,
        "wbx-validation-key": WB_WBX_VALIDATION_KEY,
        "wbid-sdk-id-token": WB_WID_SDK_ID_TOKEN,
        "routeb": WB_ROUTEB,
    }

    for name, value in cookies.items():
        if value:
            session.cookies.set(
                name,
                value,
                domain=".wildberries.ru"
            )

    return session


def read_queries(path):
    queries = []

    with open(
        path,
        encoding="utf-8-sig",
        newline=""
    ) as f:
        reader = csv.reader(f)

        for row in reader:
            if not row:
                continue

            query = row[0].strip()

            if query:
                queries.append(query)

    return queries


def load_existing_results(path):
    results = {}

    if not os.path.exists(path):
        return results

    with open(
        path,
        encoding="utf-8-sig",
        newline=""
    ) as f:
        reader = csv.reader(f)

        for row in reader:
            if len(row) < 2:
                continue

            query = row[0].strip()
            total = row[1].strip()

            if query:
                results[query] = total

    return results


def fetch_total(session, query):

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            response = session.get(
                URL,
                params={
                    **PARAMS,
                    "query": query
                },
                headers=build_headers(query),
                timeout=REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                data = response.json()
                payload = data.get("data", data)
                total = payload.get("total")

                if total is None:
                    return None

                return int(total)

            if response.status_code in (498, 429) or 500 <= response.status_code < 600:

                if attempt < MAX_RETRIES:
                    delay = (2 ** attempt) + random.uniform(0.5, 1.5)
                    time.sleep(delay)
                    continue

                return None

            return None

        except (requests.RequestException, ValueError):

            if attempt < MAX_RETRIES:
                time.sleep(
                    2 ** attempt
                    + random.uniform(0.5, 1.5)
                )
                continue

            return None

    return None


def main():

    queries = read_queries(INPUT_CSV)

    existing = load_existing_results(OUTPUT_CSV)

    print(f"Запросов в {INPUT_CSV}: {len(queries)}")

    session = create_session()

    processed = 0
    skipped = 0
    success = 0
    errors = 0

    start_time = time.time()

    with open(
        OUTPUT_CSV,
        "a",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.writer(f)

        for query in queries:

            if query in existing and existing[query] != "":
                skipped += 1
                processed += 1

                print(
                    f"Прогресс: {processed}/{len(queries)} "
                    f"| пропущено: {skipped}"
                )

                continue

            total = fetch_total(
                session,
                query
            )

            if total is None:
                errors += 1
                writer.writerow([query, ""])
            else:
                success += 1
                writer.writerow([query, total])

            f.flush()

            processed += 1

            elapsed = time.time() - start_time

            current = processed - skipped

            speed = (
                current / elapsed
                if elapsed > 0
                else 0
            )

            print(
                f"Прогресс: {processed}/{len(queries)} "
                f"| OK: {success} "
                f"| ошибок: {errors} "
            )

            time.sleep(
                REQUEST_DELAY
                + random.uniform(0.05, 0.2)
            )

    session.close()

    print()
    print("Готово.")
    print(f"Успешно: {success}")
    print(f"Ошибок: {errors}")
    print(f"Пропущено: {skipped}")
    print(f"Результаты: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
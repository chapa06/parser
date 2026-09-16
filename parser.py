import csv
import os
import time
import random
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

INPUT_CSV = os.getenv("INPUT_CSV", "1.csv")
OUTPUT_CSV = os.getenv("OUTPUT_CSV", "2.csv")

WB_WBAUID = os.getenv("WB_WBAUID", "")
WB_X_WBAAS_TOKEN = os.getenv("WB_X_WBAAS_TOKEN", "")
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
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "4"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "30"))
BATCH_PAUSE = int(os.getenv("BATCH_PAUSE", "10"))

USE_GOOGLE_SHEETS = os.getenv(
    "USE_GOOGLE_SHEETS", "0"
).strip().lower() in ("1", "true", "yes", "on")

GSHEET_FLUSH_EVERY = int(
    os.getenv("GSHEET_FLUSH_EVERY", "10")
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/153.0.0.0 "
    "Safari/537.36 "
    "Edg/153.0.0.0"
)

SEARCH_API_URL = (
    "https://www.wildberries.by/"
    "__internal/u-search/exactmatch/ru/common/v18/search"
)

SEARCH_PARAMS = {
    "ab_daily_autotest": "control_group39",
    "appType": "1",
    "autoselectFilters": "false",
    "curr": "byn",
    "dest": "1259570991",
    "hide_dflags": "131072",
    "hide_dtype": "11;13;15",
    "hide_vflags": "4294967296",
    "inheritFilters": "true",
    "lang": "ru",
    "locale": "ru",
    "resultset": "filters",
    "scale": "2",
    "spp": "30",
    "suppressSpellcheck": "false",
}


def build_headers():
    x_queryid = (
        "qidnull"
        f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        f"{random.randint(100000, 999999)}"
    )

    return {
        "accept": "*/*",
        "accept-language": (
            "ru,en;q=0.9,en-GB;q=0.8,"
            "en-US;q=0.7,ru-RU;q=0.6"
        ),
        "cache-control": "no-cache",
        "deviceid": WB_DEVICEID_HEADER,
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://www.wildberries.by/",
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
                domain=".wildberries.by"
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


def read_queries_from_source():
    if USE_GOOGLE_SHEETS:
        from google_sheets import get_search_queries

        print("Источник запросов: Google Таблица 1")

        queries = get_search_queries()

        print(f"Запросов получено: {len(queries)}")

        return queries

    print(f"Источник запросов: {INPUT_CSV}")

    return read_queries(INPUT_CSV)


def load_existing_from_source():
    if USE_GOOGLE_SHEETS:
        from google_sheets import get_existing_results

        return get_existing_results()

    return load_existing_results(OUTPUT_CSV)


def write_results_to_source(rows):
    if not rows:
        return

    if USE_GOOGLE_SHEETS:
        from google_sheets import save_results

        print(
            f"    Запись в Google Таблицу 2: "
            f"{len(rows)} строк"
        )

        if not save_results(rows):
            print(
                "    Ошибка: не удалось записать "
                "в Google Таблицу 2"
            )

    else:
        with open(
            OUTPUT_CSV,
            "a",
            encoding="utf-8-sig",
            newline=""
        ) as f:
            writer = csv.writer(f)
            writer.writerows(rows)
            f.flush()


def request_search(session, query):
    params = {
        **SEARCH_PARAMS,
        "query": query
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(
                SEARCH_API_URL,
                params=params,
                headers=build_headers(),
                timeout=REQUEST_TIMEOUT
            )

            status = response.status_code

            if status == 200:
                try:
                    data = response.json()
                except ValueError:
                    print("    Ошибка: ответ не JSON")
                    return None

                payload = data.get("data", data)
                total = payload.get("total")

                if total is None:
                    print("    Ошибка: total отсутствует")
                    return None

                return int(total)

            if status == 498:
                print(
                    f"    498 "
                    f"(попытка {attempt}/{MAX_RETRIES})"
                )

                if attempt < MAX_RETRIES:
                    delay = min(
                        30,
                        3 * (2 ** (attempt - 1))
                    )

                    delay += random.uniform(0.5, 2.0)

                    time.sleep(delay)
                    continue

                return None

            if status == 429:
                print(
                    f"    429 "
                    f"(попытка {attempt}/{MAX_RETRIES})"
                )

                if attempt < MAX_RETRIES:
                    delay = min(
                        60,
                        5 * (2 ** (attempt - 1))
                    )

                    delay += random.uniform(1, 3)

                    time.sleep(delay)
                    continue

                return None

            if 500 <= status < 600:
                print(
                    f"    HTTP {status} "
                    f"(попытка {attempt}/{MAX_RETRIES})"
                )

                if attempt < MAX_RETRIES:
                    delay = min(
                        30,
                        2 * (2 ** (attempt - 1))
                    )

                    time.sleep(delay)
                    continue

                return None

            print(f"    HTTP {status}")

            return None

        except requests.Timeout:
            print(
                f"    timeout "
                f"(попытка {attempt}/{MAX_RETRIES})"
            )

            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)
                continue

            return None

        except requests.RequestException as e:
            print(
                f"    ошибка: {e} "
                f"(попытка {attempt}/{MAX_RETRIES})"
            )

            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)
                continue

            return None

    return None


def main():
    queries = read_queries_from_source()
    existing = load_existing_from_source()

    total_queries = len(queries)

    already_processed = sum(
        1 for value in existing.values()
        if value != ""
    )

    print(f"Всего запросов: {total_queries}")
    print(f"Уже обработано: {already_processed}")

    if USE_GOOGLE_SHEETS:
        print("Приёмник результатов: Google Таблица 2")
    else:
        print(f"Приёмник результатов: {OUTPUT_CSV}")

    session = create_session()

    done = 0
    skipped = 0
    success = 0
    errors = 0

    processed = set()
    pending = []

    batch_requests = 0

    start_time = time.time()

    try:
        for query in queries:

            if query in existing and existing[query] != "":
                skipped += 1
                done += 1

                print(
                    f"[{done}/{total_queries}] "
                    f"SKIP: {query}"
                )

                continue

            if query in processed:
                done += 1

                print(
                    f"[{done}/{total_queries}] "
                    f"DUPLICATE: {query}"
                )

                continue

            print()
            print(
                f"[{done + 1}/{total_queries}] "
                f"{query}"
            )

            total = request_search(
                session,
                query
            )

            if total is None:
                errors += 1

                print("    TOTAL: ошибка")

            else:
                success += 1

                pending.append([
                    query,
                    total
                ])

                print(
                    f"    TOTAL: {total}"
                )

            if USE_GOOGLE_SHEETS:
                if len(pending) >= GSHEET_FLUSH_EVERY:
                    write_results_to_source(pending)
                    pending = []

            else:
                if total is not None:
                    write_results_to_source([
                        [query, total]
                    ])

            processed.add(query)
            done += 1
            batch_requests += 1

            elapsed = time.time() - start_time

            current_requests = done - skipped

            speed = (
                current_requests / elapsed
                if elapsed > 0
                else 0
            )

            remaining = total_queries - done

            eta = (
                remaining / speed
                if speed > 0
                else 0
            )

            eta_hours = eta / 3600

            print(
                f"    Прогресс: "
                f"{done}/{total_queries} "
                f"| OK: {success} "
                f"| Ошибки: {errors} "
                f"| Пропущено: {skipped} "
                f"| Скорость: {speed:.2f} req/s "
                f"| ETA: {eta_hours:.1f} ч"
            )

            if batch_requests >= BATCH_SIZE:
                print()
                print(
                    f"=== Пауза {BATCH_PAUSE} секунд "
                    f"после {BATCH_SIZE} запросов ==="
                )

                for remaining_seconds in range(
                    BATCH_PAUSE,
                    0,
                    -1
                ):
                    print(
                        f"\r    До продолжения: "
                        f"{remaining_seconds} сек.",
                        end="",
                        flush=True
                    )

                    time.sleep(1)

                print("\r    Продолжаю...          ")

                batch_requests = 0

            else:
                time.sleep(
                    REQUEST_DELAY +
                    random.uniform(0.1, 0.5)
                )

        if pending:
            write_results_to_source(pending)
            pending = []

    except KeyboardInterrupt:
        print()
        print(
            "Прервано пользователем. "
            "Сохраняю результаты..."
        )

        if pending:
            write_results_to_source(pending)
            pending = []

    finally:
        session.close()

    print()
    print("Готово.")
    print(f"Всего запросов: {total_queries}")
    print(f"Успешно: {success}")
    print(f"Ошибок: {errors}")
    print(f"Пропущено: {skipped}")

    if USE_GOOGLE_SHEETS:
        print("Результаты: Google Таблица 2")
    else:
        print(f"Результаты: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()

"""Модуль для работы с Google Таблицами."""

import os
import csv
from typing import List, Tuple, Dict, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_1_ID = "10um5N7ZwKARtbnBERSkBwdYvU9s6sv_VK-wjf82RZWY"
SHEET_1_GID = "ДЕТАЛЬНАЯ ИНФОРМАЦИЯ"
SHEET_2_ID = "1gGhZomKx5Mwwi1nzbkKECFq0_6XvrOvuHXp80L4IufQ"
SHEET_2_GID = "Лист1"


def get_credentials(token_file="token.json"):
    creds = None
    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        except Exception:
            pass
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds:
            import glob
            client_files = glob.glob("client_secret_*.json")
            if client_files:
                flow = InstalledAppFlow.from_client_secrets_file(client_files[0], SCOPES)
                creds = flow.run_local_server(port=0)
                with open(token_file, "w") as token:
                    token.write(creds.to_json())
            else:
                raise FileNotFoundError("Не найден client_secret_*.json")
    return creds


def get_sheets_service():
    try:
        creds = get_credentials()
        if creds:
            return build("sheets", "v4", credentials=creds)
    except Exception as e:
        print(f"Ошибка Google API: {e}")
    return None


def read_sheet(spreadsheet_id, sheet_gid, range_name="A:B"):
    service = get_sheets_service()
    if not service:
        print("Не удалось получить доступ к Google Sheets API")
        return []
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_gid}'!{range_name}"
        ).execute()
        return result.get("values", [])
    except HttpError as e:
        print(f"Ошибка чтения: {e}")
        return []


def get_search_queries():
    """Получает поисковые запросы из Таблицы 1."""
    values = read_sheet(SHEET_1_ID, SHEET_1_GID)
    if not values:
        return []
    queries = [str(row[0]).strip() for row in values if row and len(row) >= 1]
    if queries and queries[0].lower() in ("запрос", "query", "поисковый запрос"):
        queries = queries[1:]
    return queries


def get_existing_results():
    """Получает результаты из Таблицы 2. Возвращает dict {запрос: количество}."""
    values = read_sheet(SHEET_2_ID, SHEET_2_GID)
    results = {}
    if not values:
        return results
    for row in values:
        if row and len(row) >= 2:
            query = str(row[0]).strip()
            count = str(row[1]).strip() if len(row) >= 2 else ""
            if query:
                if query.lower() in ("запрос", "query", "поисковый запрос", "количество", "count"):
                    continue
                results[query] = count
    return results


def save_results(results):
    """Сохраняет результаты в Таблицу 2."""
    service = get_sheets_service()
    if not service:
        return False
    values = [[q, c] for q, c in results]
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_2_ID,
            range=f"'{SHEET_2_GID}'!A:B"
        ).execute()
        existing = result.get("values", [])
        start_row = len(existing) + 1
        range_name = f"'{SHEET_2_GID}'!A{start_row}:B{start_row + len(values) - 1}"
        service.spreadsheets().values().update(
            spreadsheetId=SHEET_2_ID,
            range=range_name,
            valueInputOption="RAW",
            body={"values": values}
        ).execute()
        return True
    except HttpError as e:
        print(f"Ошибка записи: {e}")
        return False


def download_as_csv(spreadsheet_id, sheet_gid, output_file):
    """Скачивает таблицу как CSV."""
    values = read_sheet(spreadsheet_id, sheet_gid)
    if not values:
        return False
    try:
        with open(output_file, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(values)
        return True
    except Exception as e:
        print(f"Ошибка CSV: {e}")
        return False

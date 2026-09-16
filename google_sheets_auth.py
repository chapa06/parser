"""
Скрипт для авторизации в Google API.
Создает token.json для доступа к Google Sheets API.
"""

from google_sheets import get_credentials, SCOPES

if __name__ == "__main__":
    print("Запуск авторизации Google...")
    print("Откройте браузер и разрешите доступ к Google Таблицам.")
    
    try:
        creds = get_credentials()
        
        if creds:
            print("\n✓ Авторизация успешна!")
            print(f"Токен сохранен в: token.json")
            print(f"Доступ до: {', '.join(SCOPES)}")
        else:
            print("\n✗ Ошибка авторизации")
    except Exception as e:
        print(f"\n✗ Ошибка: {e}")

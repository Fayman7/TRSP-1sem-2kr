# Проект на FastAPI

## Требования

- Python 3.10+
- pip

## Установка

```powershell
cd fastapi-user-api
python -m pip install -r requirements.txt
copy .env.example .env
```

Отредактируйте `.env` (секреты не коммитьте — файл уже в `.gitignore`). Шаблон без реальных паролей: `.env.example`.

## Запуск

```powershell
python -m uvicorn main:app --reload
```

Приложение: http://127.0.0.1:8000  
Интерактивная документация: http://127.0.0.1:8000/docs

> В PowerShell используйте `python -m uvicorn`, а не `uvicorn` (алиас может не работать).  
> Для curl в Windows — `curl.exe`, не `curl` (это алиас `Invoke-WebRequest`).

---

## Тестирование эндпоинтов

Базовый URL: `http://127.0.0.1:8000`

### Пользователи

**Создать пользователя** — `POST /create_user`

```powershell
curl.exe -X POST "http://127.0.0.1:8000/create_user" ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"Alice\",\"email\":\"alice@example.com\",\"age\":30,\"is_subscribed\":true}"
```

### Товары

**Товар по ID** — `GET /product/{product_id}`

```powershell
curl.exe "http://127.0.0.1:8000/product/123"
```

**Поиск** — `GET /products/search`

```powershell
curl.exe "http://127.0.0.1:8000/products/search?keyword=phone&category=Electronics&limit=5"
```

### Аутентификация (cookie `session_token`)

Учётные данные для демо: `user123` / `password123`.

**Вход** — сохраняет cookie в файл:

```powershell
curl.exe -c cookies.txt -X POST "http://127.0.0.1:8000/login" ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"user123\",\"password\":\"password123\"}"
```

**Профиль** — с cookie из файла:

```powershell
curl.exe -b cookies.txt "http://127.0.0.1:8000/profile"
```

Сессия живёт 5 минут без активности; продлевается при запросах в окне 3–5 минут с последней активности.

### HTTP-заголовки

**Заголовки запроса** — `GET /headers` (оба заголовка обязательны):

```powershell
curl.exe "http://127.0.0.1:8000/headers" ^
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)" ^
  -H "Accept-Language: en-US,en;q=0.9,es;q=0.8"
```

**Информация + время сервера** — `GET /info`:

```powershell
curl.exe -i "http://127.0.0.1:8000/info" ^
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)" ^
  -H "Accept-Language: en-US,en;q=0.9,es;q=0.8"
```

В ответе смотрите заголовок `X-Server-Time` (флаг `-i` показывает заголовки ответа).

---

## Переменные окружения

Скопируйте `.env.example` → `.env` и задайте значения локально.

| Переменная       | Описание                                      | Пример / по умолчанию              |
|------------------|-----------------------------------------------|------------------------------------|
| `MODE`           | `dev` — cookie без `Secure`; `prod` — с `Secure` | `dev`                           |
| `SECRET_KEY`     | Подпись `session_token`                       | смените в `.env`                   |
| `DOCS_USER`      | Логин для защиты `/docs` (опционально)        | пусто = без Basic Auth             |
| `DOCS_PASSWORD`  | Пароль для `/docs` (опционально)              | не храните реальные секреты в git  |

```powershell
copy .env.example .env
# отредактируйте .env
python -m uvicorn main:app --reload
```

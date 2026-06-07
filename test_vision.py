"""
Тест распознавания скриншота взлома замка Gothic 1 Remake через OpenRouter.
Отправляет скриншот в gpt-4o-mini и выводит ответ.
"""

import base64
import io
import json
import sys
from pathlib import Path

import requests
from PIL import Image

# ── конфигурация ───────────────────────────────────────────────
API_KEY_PATH = Path("E:/YandexDisk/Programs/Openrouter/key.txt")
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-4o-mini"
SCREENSHOT_PATH = Path("E:/YandexDisk/Скриншоты/2026-06-07_16-04-18.png")

# ── промпт ─────────────────────────────────────────────────────
PROMPT = (
    "Это скриншот мини-игры взлома замка из игры Gothic 1 Remake.\n"
    "На экране 6 пластин замка, расположенных изометрически (одна за другой, уходящие в глубину).\n"
    "Отсчёт пластин ведётся от самой левой/передней пластины как пластина 1.\n"
    "Каждая пластина имеет 7 позиций (отверстий), пронумерованных слева направо от 1 до 7.\n"
    "В одном из отверстий каждой пластины находится штифт (выделенный элемент/отверстие).\n"
    "Одна из пластин активна/выделена (обычно подсвечена синим или ярким цветом).\n\n"
    "Определи:\n"
    "1. Позицию штифта на каждой из 6 пластин (число от 1 до 7, где 1 — левый край, 7 — правый край)\n"
    "2. Какая пластина сейчас активна/выделена (номер от 1 до 6, где 1 — самая левая/передняя пластина)\n\n"
    "Ответь СТРОГО в формате JSON без каких-либо других комментариев:\n"
    '{"pins": [3, 1, 5, 2, 7, 4], "active": 2}\n'
    'Где "pins" — массив из 6 чисел (позиции штифтов пластин 1–6, отсчёт от левой к правой),\n'
    'а "active" — номер активной пластины (1–6).'
)

# ── функции ────────────────────────────────────────────────────

def load_api_key() -> str:
    if not API_KEY_PATH.exists():
        print(f"❌ Ключ API не найден: {API_KEY_PATH}")
        sys.exit(1)
    return API_KEY_PATH.read_text(encoding="utf-8").strip()


def pil_to_data_url(img: Image.Image, max_width: int = 480) -> str:
    """Конвертирует PIL Image в JPEG data URL с уменьшением размера."""
    w, h = img.size
    if w > max_width:
        ratio = max_width / w
        img = img.resize((max_width, int(h * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def extract_json(text: str) -> dict:
    """Извлекает JSON из ответа модели (может быть обёрнут в markdown)."""
    # Пробуем найти JSON в markdown-блоке
    import re
    match = re.search(r'```(?:json)?\s*({.+?})\s*```', text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    # Пробуем найти JSON напрямую
    match = re.search(r'({.+?})', text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    # Если весь ответ — JSON
    return json.loads(text)


def main():
    print("=" * 60)
    print("Тест распознавания скриншота Gothic Lockpick")
    print("=" * 60)

    # Загружаем скриншот
    if not SCREENSHOT_PATH.exists():
        print(f"❌ Скриншот не найден: {SCREENSHOT_PATH}")
        sys.exit(1)

    print(f"📸 Загружаю скриншот: {SCREENSHOT_PATH}")
    img = Image.open(SCREENSHOT_PATH)
    print(f"   Размер: {img.size}")

    # Конвертируем в data URL
    print("🔄 Конвертирую в JPEG data URL...")
    data_url = pil_to_data_url(img)
    print(f"   Размер data URL: {len(data_url)} символов")

    # Загружаем API ключ
    print("🔑 Загружаю API ключ...")
    api_key = load_api_key()
    print(f"   Ключ: {api_key[:8]}...{api_key[-4:]}")

    # Формируем запрос
    print("📡 Отправляю запрос в OpenRouter (gpt-4o-mini)...")
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Отправляем
    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Ошибка запроса: {e}")
        sys.exit(1)

    # Обрабатываем ответ
    data = resp.json()
    choice = data["choices"][0]
    content = choice["message"].get("content", "")

    print("\n" + "=" * 60)
    print("📨 ОТВЕТ МОДЕЛИ:")
    print("=" * 60)
    print(content)
    print("=" * 60)

    # Парсим JSON
    try:
        result = extract_json(content)
        print("\n✅ JSON успешно распарсен:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        pins = result.get("pins", [])
        active = result.get("active")

        print(f"\n📊 Результат:")
        print(f"   Позиции штифтов: {pins}")
        print(f"   Активная пластина: {active}")

        # Валидация
        if len(pins) != 6:
            print(f"⚠️  Предупреждение: ожидалось 6 пластин, получено {len(pins)}")
        else:
            for i, p in enumerate(pins):
                if not (1 <= p <= 7):
                    print(f"⚠️  Предупреждение: пластина {i+1} имеет позицию {p} (ожидалось 1-7)")

        if active is not None and not (1 <= active <= 6):
            print(f"⚠️  Предупреждение: активная пластина {active} вне диапазона 1-6")

    except json.JSONDecodeError as e:
        print(f"\n❌ Не удалось распарсить JSON: {e}")
        print("   Модель вернула не JSON-формат. Нужно доработать промпт.")
    except Exception as e:
        print(f"\n❌ Ошибка обработки ответа: {e}")

    print("\n✨ Тест завершён.")


if __name__ == "__main__":
    main()

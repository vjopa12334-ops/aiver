import logging
import base64
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ===== НАСТРОЙКИ =====
TELEGRAM_TOKEN = "8595821904:AAFlf_PHkSite8iz-vwXrGCTGCjMWXhEt2U"   # Токен от @BotFather
OPENROUTER_API_KEY = "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"  # Ключ с openrouter.ai
MODEL = "google/gemini-2.0-flash-exp:free"  # Модель с поддержкой vision (можно менять)
# =====================

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — беспристрастный, строгий эксперт по оценке внешности.
Твоя задача — давать честную, детальную и критическую оценку внешности человека на фото.

Правила:
- Будь максимально честным и прямым, без лишней лести
- Оценивай по шкале от 1 до 10 (целые числа)
- Разбирай каждый аспект отдельно и конкретно
- Указывай как сильные стороны, так и недостатки
- Не смягчай критику и не утешай
- Давай конкретные рекомендации по улучшению
- Используй профессиональный тон

Структура ответа:
1. **Общая оценка: X/10**
2. **Лицо** — детальный разбор (симметрия, черты, кожа)
3. **Стиль и ухоженность** — одежда, причёска, общий вид
4. **Сильные стороны** — что реально хорошо
5. **Недостатки** — что мешает выглядеть лучше
6. **Рекомендации** — конкретные шаги для улучшения

Если на фото нет человека — сообщи об этом."""


async def call_openrouter(image_base64: str, media_type: str = "image/jpeg") -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/appearance_bot",
        "X-Title": "Appearance Rating Bot",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": "Оцени внешность человека на этом фото. Будь максимально строгим и честным."
                    }
                ]
            }
        ],
        "max_tokens": 1024,
        "temperature": 0.7,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(OPENROUTER_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise ValueError(f"OpenRouter error: {data['error']}")

        return data["choices"][0]["message"]["content"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👁 *Бот оценки внешности*\n\n"
        "Отправь фото — получишь строгую и честную оценку от ИИ.\n\n"
        "⚠️ Без лести. Только правда.",
        parse_mode="Markdown"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Анализирую фото, подожди...")

    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()

        image_base64 = base64.standard_b64encode(photo_bytes).decode("utf-8")

        result = await call_openrouter(image_base64, media_type="image/jpeg")

        await msg.delete()
        await update.message.reply_text(result, parse_mode="Markdown")

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e.response.status_code} — {e.response.text}")
        await msg.edit_text("❌ Ошибка API. Проверь ключ OpenRouter или попробуй позже.")
    except ValueError as e:
        logger.error(f"API error: {e}")
        await msg.edit_text("❌ Модель не смогла обработать изображение. Попробуй другое фото.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await msg.edit_text("❌ Произошла ошибка. Попробуй снова.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📸 Отправь фото для оценки внешности.")


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()

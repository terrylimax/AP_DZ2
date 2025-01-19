import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from handlers import router
from config import TOKEN
from middleware import LoggingMiddleware

# Включаем логирование, чтобы не пропустить важные сообщения
logging.basicConfig(level=logging.INFO)
# Объект бота
bot = Bot(token=TOKEN)
# Диспетчер
dp = Dispatcher()
dp.message.middleware(LoggingMiddleware())
dp.include_router(router)

# Обработка команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я бот, который поможет тебе вести учет потребялемых калорий и воды.\n"
                         "Настроить профиль: /set_profile\n"
                         "Ввести количество потребляемой воды:\n /log_water <количество в мл>\n"
                         "Ввести количество потребляемых калорий:\n /log_calories <продукт>, позже ввести в граммах сколько продукта было употреблено\n"
                         "Залогировать тренировку:\n /log_workout <вид тренировки> <время в минутах>\n"
                         "Посмотреть прогресс: /check_progress")
# Основная функция запуска бота
async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
from math import e, prod
import re
from aiogram import Router
from aiogram.filters.command import Command
from aiogram.types import BufferedInputFile, Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import requests
import aiohttp
from config import TEMP_API_KEY
import logging
import seaborn as sns
import matplotlib.pyplot as plt
from io import BytesIO

router = Router()
class Form(StatesGroup):
    name = State()
    age = State()
    weight = State()
    height = State()
    activity_mins = State()
    city = State()
    calorie_goal = State()
    calorie_goal_set_manually = State()
    water_goal = State()
    product_name = State()
    product_calories = State() #для хранения калорий продукта

user_data = {} #будем пока хранить данные пользователей в глобальном словаре

@router.message(Command("set_profile"))
async def start_form(message: Message, state: FSMContext):
    await message.answer("Как вас зовут?")
    await state.set_state(Form.name)

@router.message(Form.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите ваш вес (в кг):")
    await state.set_state(Form.weight)

@router.message(Form.weight)
async def process_weight(message: Message, state: FSMContext):
    try:
        weight = int(message.text)
        if weight > 0:
            await state.update_data(weight=weight)
            await message.answer(f"Введите ваш рост (в см):")
            await state.set_state(Form.height)
        else:
            await message.answer("Пожалуйста, введите положительное число.")
    except ValueError:
        await message.answer("Пожалуйста, введите положительное число.")

@router.message(Form.height)
async def process_height(message: Message, state: FSMContext):
    try:
        height = int(message.text)
        if height > 0:
            await state.update_data(height=height)
            await message.answer(f"Введите ваш возраст:")
            await state.set_state(Form.age)
        else:
            await message.answer("Пожалуйста, введите положительное число.")
    except ValueError:
        await message.answer("Пожалуйста, введите положительное число.")
    

@router.message(Form.age)
async def process_age(message: Message, state: FSMContext):
    try:
        age = int(message.text)
        if age > 0:
            await state.update_data(age=age)
            await message.answer(f"Сколько минут активности у вас в день?")
            await state.set_state(Form.activity_mins)
        else:
            await message.answer("Пожалуйста, введите положительное число.")
    except ValueError:
        await message.answer("Пожалуйста, введите положительное число.")
        
    
@router.message(Form.activity_mins)
async def process_activity(message: Message, state: FSMContext):
    try:
        activity_mins = int(message.text)
        if activity_mins > 0:
            await state.update_data(activity_mins=activity_mins)
            await message.answer(f"В каком городе вы находитесь?")
            await state.set_state(Form.city)
        else:
            await message.answer("Пожалуйста, введите положительное число.")
    except ValueError:
        await message.answer("Пожалуйста, введите положительное число.")

@router.message(Form.city)
async def process_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    #даем возможность автоматического просчета калорий
    no_answer_keyboard = ReplyKeyboardMarkup( 
        keyboard=[
            [KeyboardButton(text="Рассчитай сам")],
        ],
        resize_keyboard=True,
    )
    await message.answer(f"Укажите желаемое количество калорий?", reply_markup=no_answer_keyboard)
    await state.set_state(Form.calorie_goal)

@router.message(Form.calorie_goal)
async def process_calories(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    try:
        if message.text == "Рассчитай сам":
            #считаем базовую норму калорий
            cals_goal = 10 * int(data["weight"]) + 6.25 * int(data["height"]) - 5 * int(data["age"])
            cals_goal_set_manually = False
        else:
            cals_goal = int(message.text)
            if cals_goal <= 0:
                raise ValueError("Цель калорий должна быть положительным числом")
            #при ручном вводе калорий не пересчитываем базовую норму калорий при тренировках, тк пользователь попросил учитывать именно его цифру
            cals_goal_set_manually = True
        #расчитываем базовую норму воды
        water_goal = data["weight"] * 30
        status, temp = await async_get_weather_data(data["city"], TEMP_API_KEY)
        if status != 200:
            logging.warning(f"Ошибка при получении данных о погоде в {data['city']}: {status}")
        else: 
            if temp > 25:
                water_goal += 500
        await state.update_data(calorie_goal=cals_goal, calorie_goal_set_manually=cals_goal_set_manually, water_goal=water_goal)
        user_data[user_id] = {
            "name": data["name"],
            "weight": data["weight"],
            "height": data["height"],
            "age": data["age"],
            "activity": data["activity_mins"],
            "city": data["city"],
            "water_goal": water_goal,
            "calorie_goal": cals_goal,
            "calorie_goal_set_manually": cals_goal_set_manually,
            "logged_water": 0,
            "logged_calories": 0,
            "burned_calories": 0
        }
        print('user_data:', user_data)
        await message.answer(
            f"""Ваши данные:
        Имя: {data['name']}
        Вес: {data['weight']} кг
        Рост: {data['height']} см
        Возраст: {data['age']} лет
        Город: {data['city']}
        Количество минут активности в день: {data['activity_mins']}
        Ваша цель: {cals_goal} калорий в день. 
        Норма воды: {water_goal} мл.""",
        reply_markup=ReplyKeyboardRemove()
        )    
        await state.clear()
    except ValueError:
        await message.answer("Пожалуйста, введите положительное число.")

@router.message(Command("log_water"))
async def process_water(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Пожалуйста, укажите число после команды. Например: /log_water 200")
        return
    
    user_id = message.from_user.id
    data = user_data.get(user_id)
    if data is None:
        await message.reply("Сначала укажите свои данные командой /set_profile")
        return
    
    try:
        logged_water = int(args[1])
        if logged_water <= 0:
            raise ValueError("Пожалуйста, введите положительное число.")
        
        data["logged_water"] += logged_water
        left_ml = data['water_goal'] - data['logged_water']
        if left_ml <= 0:
            await message.reply("Вы выполнили норму воды на сегодня!")
        else:
            await message.reply(f"Осталось до выполнения нормы: {data['water_goal'] - data['logged_water']} мл.")
    except ValueError:
        await message.reply("Пожалуйста, введите положительное число.")
        return
    
@router.message(Command("log_calories"))
async def process_calories_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = user_data.get(user_id)
    if data is None:
        await message.reply("Сначала укажите свои данные командой /set_profile")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Пожалуйста, укажите название продукта после команды. Например: /log_calories яблоко")
        return
    food_info = get_food_info(args[1])
    if food_info is None:
        await message.reply("Продукт не найден.")
        return
    await state.update_data(product_name=food_info['name'], product_calories=food_info['calories'])
    await message.answer(f"{food_info['name']} — {food_info['calories']} ккал на 100г. Сколько грамм вы съели?")
    await state.set_state(Form.product_name)
    

@router.message(Form.product_name)
async def process_calories_end(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = user_data.get(user_id)
    #проверка на непустой data была ранее
    state_data = await state.get_data()
    product_calories = state_data.get("product_calories")
    try:
        grams_taken = int(message.text) 
        if grams_taken <= 0:
            raise ValueError("Пожалуйста, введите положительное число.")
        calories = round((grams_taken / 100) * product_calories,1)
        data["logged_calories"] += calories
        await message.answer(f"Записано: {calories} ккал")
        await state.clear()
    except ValueError:
        await message.reply("Пожалуйста, введите положительное число.")
        return

@router.message(Command("log_workout"))
async def process_workout(message: Message):
    user_id = message.from_user.id
    data = user_data.get(user_id)
    if data is None:
        await message.reply("Сначала укажите свои данные командой /set_profile")
        return
    
    try:
        args = message.text.split(maxsplit=2)
        train_type, duration = validate_workout_command(message.text)
        burned_calories, additional_calories = calculate_calories(train_type, duration)
        if burned_calories == '404':
            await message.reply("Такой вид тренировки не найден. Выберите тип из списка: бег, ходьба, плавание, силовая тренировка, кроссфит. Пример: /log_workout бег 30")
            return
        data["burned_calories"] += burned_calories
        #мы знаем количество минут активности, теперь обновляем норму воды
        # в 2 и 5 пункте разночтения в задании. Я взял за основу 2 пункт - за каждые 30 мин активности добавляется 500 мл в норму воды
        calc_additional_water = round((duration / 30) * 500) #к любому кол-ву активности добавим воду
        data["water_goal"] += calc_additional_water
        #calculate_calories также расчитывает увеличение нормы калорий в зависимости от интенсивности тренировки
        data['calorie_goal'] += additional_calories
        await message.answer(f"🏃‍♂️ {train_type} {duration} минут: {burned_calories} ккал. Дополнительно: выпейте +{calc_additional_water} мл воды, употребите +{additional_calories} ккал.")
    except ValueError:
        await message.reply("Пожалуйста, положительное число после названия тренировки. Например, /log_workout бег 30")


def validate_workout_command(command_text):
    args = command_text.split(maxsplit=2)
    if len(args) < 3:
        raise ValueError("Пожалуйста, укажите вид тренировки и время. Например: /log_workout бег 30")
    train_type = args[1]
    try:
        duration = int(args[2])
        if duration <= 0:
            raise ValueError("Длительность должна быть положительным числом.")
        return train_type, duration
    except ValueError:
        raise ValueError("Введите корректное число для длительности тренировки.")
    
@router.message(Command("check_progress"))
async def process_workout(message: Message):
    user_id = message.from_user.id
    data = user_data.get(user_id)
    if data is None:
        await message.reply("Сначала укажите свои данные командой /set_profile")
        return
    water_used = data["logged_water"]
    water_goal = data["water_goal"]
    calories_used = data["logged_calories"]
    calories_goal = data["calorie_goal"]
    calories_burned = data["burned_calories"]
    if not water_goal or not calories_goal:
        await message.reply("Сначала укажите свои данные командой /set_profile")
        return
    water_left = water_goal - water_used
    calories_left = calories_goal - calories_used
    #в задании требуется вывести остаток калорий до цели, при этом в примере указан баланс (1800-400 =1400) , который противоречит заданию, 
    # потому что во втором задании к норме ккал требовалось добавить калории при тренировках
    # поэтому вместо баланса выводим остаток калорий до цели 
    await message.answer(f"""📊 Прогресс:
    Вода:
    - Выпито: {water_used} мл из {water_goal} мл.
    - Осталось: {water_left} мл.
    Калории:
    - Потреблено: {calories_used} ккал из {calories_goal} ккал.
    - Сожжено: {calories_burned} ккал.
    - Осталось: {calories_goal-calories_used} ккал.""")
    buffer = await progress_chart(water_goal, water_used, calories_goal, calories_used)
    # Отправка графика в Telegram
    await message.answer_photo(buffer, caption="Ваш прогресс 📊")

def calculate_calories(train_type, duration):
    # Сохраним в словаре калории, сжигаемые за 10 минут каждого вида тренировки
    train_calories_base = {
        "бег": {"calories_per_10_min": 100, "intensity": "high"},            
        "ходьба": {"calories_per_10_min": 40, "intensity": "low"},         
        "плавание": {"calories_per_10_min": 90, "intensity": "high"},
        "силовая тренировка": {"calories_per_10_min": 80, "intensity": "high"}, 
        "кроссфит": {"calories_per_10_min": 150, "intensity": "high"}
    }
    if train_type not in train_calories_base:
        return '404'
    #считаем сколько сожгли в соответствии с длительностью тренировки
    calories_per_10_min = train_calories_base[train_type]["calories_per_10_min"]
    total_calories_burned = (calories_per_10_min / 10) * duration #считаем поминутно калории потраченные
    #30 мин низкоинтенсивной тренировки добавляет к норме калорий 200 ккал
    if train_calories_base[train_type]["intensity"] == "low":
        add_calories = round((duration/30) * 200)
    else:
    #высокоинтенсивная тренировка добавляет 400 ккал
        add_calories = round((duration/30) * 400)
    return total_calories_burned, add_calories

def get_food_info(product_name):
    url = f"https://world.openfoodfacts.org/cgi/search.pl?action=process&search_terms={product_name}&json=true"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        products = data.get('products', [])
        if products:  # Проверяем, есть ли найденные продукты
            first_product = products[0]
            return {
                'name': first_product.get('product_name', 'Неизвестно'),
                'calories': first_product.get('nutriments', {}).get('energy-kcal_100g', 0)
            }
        return None
    print(f"Ошибка: {response.status_code}")
    return None

async def async_get_weather_data(city, API_key):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_key}&units=metric"
    try: 
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                # if response.status != 200:  # Другие ошибки сервера
                #     return response
                data = await response.json()
                if data.get('cod') != 200:
                    return response.status, data
                temp = data.get('main').get('temp')                
                return response.status, temp
    except Exception as e: 
        raise RuntimeError(f"Ошибка при получении данных о погоде: {e}")

#построим простые графики прогресса с помощью seaborn
async def progress_chart(water_goal, water_used, calories_goal, calories_used):
    categories = ["Вода", "Калории"]
    goals = [water_goal, calories_goal]
    actuals = [water_used, calories_used]

    data = {
        "Категория": categories,
        "Цель": goals,
        "Фактически": actuals,
        "Процент": [act / goal * 100 for act, goal in zip(actuals, goals)]
    }

    plt.figure(figsize=(8, 5))
    sns.barplot(
        x="Процент",
        y="Категория",
        data=data,
        palette="coolwarm",
        orient="h"
    )
    
    for i, percentage in enumerate(data["Процент"]):
        plt.text(percentage + 5, i, f"{percentage:.1f}%", va='center', ha='left')

    plt.title("Прогресс целей", fontsize=16)
    plt.xlabel("Заполнение цели (%)", fontsize=12)
    plt.ylabel("")
    plt.xlim(0, 100)
    plt.grid(axis="x", linestyle="--", alpha=0.7)

    buffer = BytesIO()
    plt.savefig(buffer, format="png", bbox_inches="tight")
    buffer.seek(0)
    plt.close()
    photo = BufferedInputFile(buffer.getvalue(), filename="progress.png")
    return photo
    
import os
import redis
import random
import logging
import log_config
import quiz_questions as qq
from dotenv import load_dotenv
from textwrap import dedent

from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from aiogram.contrib.fsm_storage.redis import RedisStorage2


tg_logger = logging.getLogger('tg_logger')

load_dotenv()
dp = Dispatcher(
    bot=Bot(token=os.environ['TG_BOT_TOKEN']), 
    storage=RedisStorage2(
        host=os.environ['DB_HOST'],
        port=os.environ['DB_PORT'],
        password=os.environ['DB_PASSWORD'] 
    ),
)

redis_db = redis.Redis(
    host=os.environ['DB_HOST'],
    port=os.environ['DB_PORT'],
    password=os.environ['DB_PASSWORD'],
)

QUIZ_PATH = os.environ['QUIZ_PATH']


class Status(StatesGroup):
    waiting_command = State()
    waiting_answer = State()


def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
        handlers=[log_config.SendToTelegramHandler()]
    )
    executor.start_polling(dp, timeout=1) 
    # TODO handle with "while True"

@dp.message_handler(commands=['start'], state='*')
async def send_welcome(message: types.Message):
    reply_markup = create_reply_markup()

    await Status.waiting_command.set()
    await message.answer('Привет! Я бот для викторин. Нажми /help, чтобы получить помощь', reply_markup=reply_markup)
    tg_logger.debug('Welcome was sent')

def create_reply_markup():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(
    KeyboardButton('Новый вопрос'),
    KeyboardButton('Сдаться'),
    )
    keyboard.add(KeyboardButton('Мой счет'))
    return keyboard

@dp.message_handler(commands=['cancel'], state='*')
async def cancel_quiz(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer('Викторина окончена. Чтобы начать новую, нажми /start', reply_markup=ReplyKeyboardRemove())
    tg_logger.debug('Quiz was canceled')

@dp.message_handler(commands=['help'], state='*')
async def send_help(message: types.Message, state: FSMContext):
    help_text = dedent('''\
    Я бот для викторин.
    Нажми /start, чтобы начать викторину.
    Действия кнопок:
    "Новый вопрос" - я вышлю новый вопрос викторины,
    "Сдаться" - получить правильный ответ и новый вопрос,
    "Мой счет" - количество заработанных тобой баллов.
    Нажми /cancel для окончания викторины.
    ''')
    await message.answer(help_text)
    tg_logger.debug('Help message was sent')

@dp.message_handler(Text(equals='Мой счет', ignore_case=True), state='*')
async def send_score(message: types.Message):
    user_id = f'tg_{message.chat.id}'
    # TODO calculate score
    score = qq.get_user_score(user_id)
    await message.answer(f'Твой счет: {score} правильных ответа.')
    tg_logger.debug('Score was sent')

@dp.message_handler(Text(equals='Новый вопрос', ignore_case=True), state=Status.waiting_command)
async def send_question(message: types.Message):
    user_id = f'tg_{message.chat.id}'
    question = qq.get_random_question(QUIZ_PATH)
    redis_db.set(user_id, question)
    tg_logger.debug('Question was sent to user and into db')

    await Status.next()
    await message.answer(question)
    tg_logger.debug(f'Question was sent to chat {user_id}')

@dp.message_handler(Text(equals='Сдаться', ignore_case=True), state=Status.waiting_answer)
async def give_up(message: types.Message):
    user_id = f'tg_{message.chat.id}'
    correct_answer = qq.get_correct_answer(user_id, QUIZ_PATH, redis_db)

    await Status.waiting_command.set()
    await message.answer(f'Правильный ответ:\n{correct_answer}')
    tg_logger.debug(f'Correct answer was sent to chat {user_id}')

@dp.message_handler(state=Status.waiting_answer)
async def get_answer(message: types.Message, state: FSMContext):
    user_id = f'tg_{message.chat.id}'
    answer = qq.remove_explanations_from_answer(message.text)
    if qq.check_answer(answer, user_id, QUIZ_PATH, redis_db):
        correct_answer = qq.get_correct_answer(user_id, QUIZ_PATH, redis_db)
        text = f'Правильно! {correct_answer}\nДля следующего вопроса нажми «Новый вопрос»'
        
        await Status.waiting_command.set()
        tg_logger.debug('Got correct answer')
    else:
        text = 'Неправильно... Попробуешь ещё раз?'
        tg_logger.debug('Got wrong answer')

    await message.answer(text)


if __name__ == '__main__':
    main()

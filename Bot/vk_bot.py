import os
import redis
import logging
import log_config
import quiz_questions as qq
from dotenv import load_dotenv
from textwrap import dedent

import vk_api
from vk_api.utils import get_random_id
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor


vk_logger = logging.getLogger('vk_logger')


def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
        handlers=[log_config.SendToTelegramHandler()]
    )
    load_dotenv()
    vk_token = os.environ['VK_GROUP_MESSAGE_TOKEN']
    quiz_path = os.environ['QUIZ_PATH']
    redis_db = redis.Redis(
        host=os.environ['DB_HOST'],
        port=os.environ['DB_PORT'],
        password=os.environ['DB_PASSWORD'],
    )
    while True:
        try:
            start_vk_bot(vk_token, redis_db, quiz_path)
        except Exception:
            vk_logger.exception('')
            continue

def start_vk_bot(vk_token, redis_db, quiz_path):
    vk_session = vk_api.VkApi(token=vk_token)
    vk_api_methods = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    vk_logger.debug('Bot starts polling')
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            answer_to_user(event, vk_api_methods, redis_db, quiz_path)

def answer_to_user(event, vk_api_methods, redis_db, quiz_path):
    if event.text.lower() == 'Привет'.lower():
        send_welcome_and_keyboard(event, vk_api_methods)
    else:
        text = get_answer(event, redis_db, quiz_path)
        vk_api_methods.messages.send(
            user_id=event.user_id,
            random_id=get_random_id(),
            message=text,
        )
        vk_logger.debug('Various answer was sent')

def send_welcome_and_keyboard(event, vk_api_methods):
    keyboard = create_keyboard()
    text = dedent('''\
    Привет! Я бот для викторин.
    Действия кнопок:
    "Новый вопрос" - я вышлю новый вопрос викторины,
    "Сдаться" - получить правильный ответ и новый вопрос,
    "Мой счет" - количество заработанных тобой баллов.
    ''')
    vk_api_methods.messages.send(
        user_id=event.user_id,
        random_id=get_random_id(),
        keyboard=keyboard.get_keyboard(),
        message=text,
    )
    vk_logger.debug('Welcome was sent')

def create_keyboard():
    keyboard = VkKeyboard()
    keyboard.add_button('Новый вопрос', color=VkKeyboardColor.PRIMARY)
    keyboard.add_button('Сдаться', color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button('Мой счет', color=VkKeyboardColor.DEFAULT)
    return keyboard

def get_answer(event, redis_db, quiz_path):
    user_id = f'vk_{event.user_id}'
    if event.text == 'Новый вопрос':
        text = qq.get_random_question(quiz_path)
        redis_db.set(user_id, text)
        vk_logger.debug('Got new question and sent it into db')
    elif event.text == 'Сдаться':
        text = qq.get_correct_answer(user_id, quiz_path, redis_db)
        vk_logger.debug('Got correct answer')
    elif event.text == 'Мой счет':
        score = qq.get_user_score(user_id)
        text = f'Твой счет: {score} правильных ответа.'
        vk_logger.debug('Got score')
    else:
        answer = remove_explanations_from_answer(event.text)
        if qq.check_answer(answer, user_id, quiz_path, redis_db):
            text = 'Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»'
        else:
            text = 'Неверный ответ или команда. Попробуешь еще раз?'
    return text

if __name__ == "__main__":
    main()
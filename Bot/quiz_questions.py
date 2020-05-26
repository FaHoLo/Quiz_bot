import os
import random

from more_itertools import flatten


def get_random_question(quiz_path):
    questions_and_answers = collect_questions_and_answers(quiz_path)
    questions = [question for question in questions_and_answers.keys()]
    return random.choice(questions)


def get_correct_answer(user_id, quiz_path, redis_db):
    question = redis_db.get(user_id).decode('UTF-8')
    return get_question_answer(question, quiz_path)


def get_question_answer(question, quiz_path):
    questions_and_answers = collect_questions_and_answers(quiz_path)
    return questions_and_answers[question]


def remove_explanations_from_answer(answer):
    answer_ending = answer.find('(')
    if answer_ending == -1:
        answer_ending = answer.find('.')
    if answer_ending != -1:
        answer = answer[:answer_ending]
    return answer


def check_answer(answer, user_id, quiz_path, redis_db):
    correct_answer = get_correct_answer(user_id, quiz_path, redis_db)
    if answer.lower() in correct_answer.lower():
        return True


def get_user_score(user_id):
    score = 123
    # TODO calculate user score
    return score


def collect_questions_and_answers(quiz_path):
    text = get_text_from_file(quiz_path)
    return collect_q_and_a_from_text(text)


def get_text_from_file(file_path):
    encoding = os.getenv('QUIZ_TEXT_ENCODING', 'KOI8-R')
    with open(file_path, 'r', encoding=encoding) as file:
        text = file.read()
    return text


def collect_q_and_a_from_text(text):
    question_infos = text.split('\n\n\n')
    questions_and_answers = {}
    sections = flatten([question_info.split('\n\n') for question_info in question_infos])
    for section in sections:
        if section.startswith('Вопрос '):
            question = section[10:].replace('\n', ' ').lstrip()
        if section.startswith('Ответ:'):
            answer = section[7:].replace('\n', ' ')
            questions_and_answers[question] = answer
    return questions_and_answers

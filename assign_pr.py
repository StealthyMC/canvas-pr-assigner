#!/usr/bin/python3

from __future__ import print_function, unicode_literals

import logging
import argparse
import json
import requests

# fancy CLI
from PyInquirer import prompt, print_json, Separator
from clint.arguments import Args
from clint.textui import puts, colored, indent
from examples import custom_style_1, custom_style_2

from prettytable import PrettyTable

API_URL = 'https://unr.canvaslms.com/'


def create_logger():
    consolerHandler = logging.StreamHandler()
    consolerHandler.setLevel(logging.DEBUG)
    logger = logging.getLogger('dev')
    logger.setLevel(logging.INFO)
    logger.addHandler(consolerHandler)
    return logger


def create_get_request(req_url, req_header, req_data={}):
    req = requests.get(req_url, headers=req_header, data=req_data)
    try:
        json_reply = json.loads(req.text)
    except ValueError:
        logger.error(colored.red(f'Error code {req.status_code}'))  # second step, get list of submissions
    return json_reply


def main():
    logger = create_logger()
    parser = argparse.ArgumentParser(
        description='Assigns specified students as peer reviewers for indicated assignment. Requires API token from a professor for authentication.')
    parser.add_argument('--token', dest='API_TOKEN', metavar='token', type=str, nargs=1, default='',
                        help='API token of professor. Can be generated from Settings on the Canvas website.',
                        required=True)
    # parser.add_argument('--course', dest='course', metavar='course', type=int, nargs=1, default='', help='Course ID to access.', required=True)
    # parser.add_argument('--students', dest='students', type=int, nargs='+', default='', help='Student IDs of students to assign the peer reviews to.', required=True)
    args = parser.parse_args()
    api_token_file = args.API_TOKEN[0]

    # open API token text file and get the line from it
    logger.info(f'Attempting to read {api_token_file}...')
    try:
        f = open(api_token_file, encoding='utf-8')
        API_TOKEN = f.readline()
        logger.info(colored.green('API token file read successfully.'))
    except IOError as e:
        logger.error(colored.red(f'I/O error {e.errno}: {e.strerror}'))
    # except:
    # logger.error(colored.red('Error reading API token file. Check the filename and ensure that it is correct.'))
    AUTH_HEADER = {'Authorization': f'Bearer {API_TOKEN}'.strip('\n')}

    # get course number
    proceed = False
    course_number = 0
    course_name = ''
    assignment_number = 0
    while not proceed:
        questions = [
            {
                'type': 'input',
                'name': 'course_number',
                'message': 'コース番号を入力：',
            }
        ]
        answers = prompt(questions, style=custom_style_1)
        course_number = answers['course_number']
        # confirm that the assignment number is valid
        json_reply = create_get_request(API_URL + f'api/v1/courses/{course_number}',
                                        AUTH_HEADER)
        try:
            proceed = json_reply['id']
            course_name = json_reply['name']
            logger.info(colored.green(f"コースが見つかりました。コース名は{course_name}です。"))
            questions = [
                {
                    'type': 'confirm',
                    'message': '以上の内容で宜しいですか？',
                    'name': 'confirm_course',
                    'default': False,
                }
            ]
            answers = prompt(questions, style=custom_style_1)
            proceed = answers['confirm_course']
        except KeyError:
            logger.error(colored.red(f"エラー: {json_reply['errors'][0].get('message')}"))
            proceed = False

    # get assignment number
    proceed = False
    assignment_number = 0
    while not proceed:
        questions = [
            {
                'type': 'input',
                'name': 'assignment_number',
                'message': 'アサインメント番号を入力：',
            }
        ]
        answers = prompt(questions, style=custom_style_1)
        assignment_number = answers['assignment_number']
        # confirm that the assignment number is valid
        json_reply = create_get_request(API_URL + f'api/v1/courses/{course_number}/assignments/{assignment_number}',
                                        AUTH_HEADER)
        try:
            proceed = json_reply['id']
            logger.info(colored.green(f"アサインメントが見つかりました。名称は{json_reply['name']}です。"))
            questions = [
                {
                    'type': 'confirm',
                    'message': '以上の内容で宜しいですか？',
                    'name': 'confirm_assignment',
                    'default': False,
                }
            ]
            answers = prompt(questions, style=custom_style_1)
            proceed = answers['confirm_assignment']
        except KeyError:
            logger.error(colored.red(f"エラー: {json_reply['errors'][0].get('message')}"))
            proceed = False

    # first, build dictionary mapping user_ids to real names
    json_reply = create_get_request(API_URL + f'api/v1/courses/{course_number}/users',
                                    {'Authorization': f'Bearer {API_TOKEN}'.strip('\n')})
    user_dict = {}
    for user in json_reply:
        user_dict[user['short_name']] = user['id']

    # next, remove teacher from list of users
    # logger.info('リストから教師を取り出します。')
    json_reply = create_get_request(API_URL + f'api/v1/courses/{course_number}/users',
                                    AUTH_HEADER, {'enrollment_type': 'teacher'})
    teacher_dict = {}
    for teacher in json_reply:
        teacher_dict[teacher['short_name']] = teacher['id']
    for i in teacher_dict:
        try:
            user_dict.pop(i)
        except KeyError:
            continue

    # display users
    table_students = PrettyTable()
    table_students.field_names = ['名前', 'ユーザー番号']
    logger.info(f"{course_name}のユーザー:")
    for i in user_dict:
        table_students.add_row([i, user_dict[i]])
    logger.info(table_students)
    # user dictionary complete 

    # acquire user_id of people who will be peer reviewing
    # build dictionary needed for prompt
    choices_tutors = []
    for i in user_dict.keys():
        value = {}
        value['name'] = i
        choices_tutors.append(value)

    # do not move forward until correct tutors are chosen
    proceed = False
    selected_tutors = {}
    while proceed == False:
        questions = [
            {
                'type': 'checkbox',
                'name': 'tutor_select',
                'message': 'チューターを選択',
                'choices': choices_tutors
            }
        ]
        # prompt user and store results into 'answers'
        answers = prompt(questions, style=custom_style_1)
        selected_tutors = answers['tutor_select']
        # store selected user_ids designated as the peer reviewers
        logger.info('選ばれたチューターをご確認ください：')
        for i in selected_tutors:
            logger.info(colored.blue(i))
        questions = [
            {
                'type': 'confirm',
                'message': '以上の内容で宜しいですか？',
                'name': 'confirm_tutors',
                'default': False,
            }
        ]
        answers = prompt(questions, style=custom_style_1)
        proceed = answers['confirm_tutors']

    # create student dictionary, but remove designated tutors from list
    student_dict = user_dict.copy()
    for i in selected_tutors:
        student_dict.pop(i)

    # show how many people the peer reviews will be allotted to each person
    logger.info(f'{len(selected_tutors)}人で割り当てます。')

    # TESTING: adding test users
    for i in range(0, 19):
        student_dict[f'Test User {i}'] = i + 12345

    # allocate students to each student
    # each list corresponds to a tutor
    allocations = [[] for i in range(len(selected_tutors))]
    number_of_students = len(student_dict)
    for i in range(0, number_of_students):
        student = student_dict.popitem()
        allocations[i % len(selected_tutors)].append(student[1])

    for i in range(0, len(allocations)):
        for j in range(1, len(allocations[i])):
            logger.info(f'POST with {allocations[i][j]} to tutor {user_dict[selected_tutors[i]]}\n')

    # show users
    table_students = PrettyTable()
    table_students.field_names = ['名前', 'ユーザー番号']
    logger.info(f"チューターが以下の学生の提出を担当します。")
    for i in user_dict:
        table_students.add_row([i, user_dict[i]])

    # req_url = API_URL + f'api/v1/courses/{course_number}/assignments/{assignment_number}/submissions'
    # req_header = {'Authorization': f'Bearer {API_TOKEN}'.strip('\n')}
    # try:
    # json_reply = json.loads(req.text)
    ##logger.info(json_reply)
    # for i in json_reply:
    # logger.info(f"Adding submission: {i['id']}")


if __name__ == '__main__':
    main()

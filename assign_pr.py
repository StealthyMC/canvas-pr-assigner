#!/usr/bin/python3

from __future__ import print_function, unicode_literals

import argparse
import json
import logging

import requests
# fancy CLI
from PyInquirer import prompt
from clint.textui import colored
from examples import custom_style_1
from prettytable import PrettyTable

API_URL = 'https://unr.canvaslms.com/'

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
logger = logging.getLogger('dev')
logger.setLevel(logging.INFO)
logger.addHandler(console_handler)


def create_get_request(req_url, req_header, req_data=None):
    if req_data is None:
        req_data = {}
    req = requests.get(req_url, headers=req_header, data=req_data)
    try:
        json_reply = json.loads(req.text)
    except ValueError:
        logger.error(colored.red(f'Error code {req.status_code}'))  # second step, get list of submissions
        return -1
    return json_reply


def create_post_request(req_url, req_header, req_data=None):
    if req_data is None:
        req_data = {}
    req = requests.post(req_url, headers=req_header, data=req_data)
    try:
        json_reply = json.loads(req.text)
    except ValueError:
        logger.error(colored.red(f'Error code {req.status_code}'))
        return -1
    return json_reply


def main():
    parser = argparse.ArgumentParser(
        description='Assigns specified students as peer reviewers for indicated assignment. '
                    'Requires API token from a professor for authentication.')
    parser.add_argument('--token', dest='API_TOKEN', metavar='token', type=str, nargs=1, default='',
                        help='API token of professor. Can be generated from Settings on the Canvas website.',
                        required=True)
    args = parser.parse_args()
    api_token_file = args.API_TOKEN[0]

    API_TOKEN = ''
    # open API token text file and get the line from it
    logger.info(f'Attempting to read {api_token_file}...')
    try:
        f = open(api_token_file, encoding='utf-8')
        API_TOKEN = f.readline()
        logger.info(colored.green('API token file read successfully.'))
    except IOError as e:
        logger.error(colored.red(f'I/O error {e.errno}: {e.strerror}'))
        exit(-1)
    # except:
    # logger.error(colored.red('Error reading API token file. Check the filename and ensure that it is correct.'))
    AUTH_HEADER = {'Authorization': f'Bearer {API_TOKEN}'.strip('\n')}

    # get course number
    proceed = False
    course_number = 0
    course_name = ''
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
                                    AUTH_HEADER, {'enrollment_type': 'student', 'per_page': 100})
    user_dict = {}
    for user in json_reply:
        user_dict[user['short_name']] = user['id']

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
        value = {'name': i}
        choices_tutors.append(value)

    # do not move forward until correct tutors are chosen
    proceed = False
    selected_tutors = {}
    while not proceed:
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
        logger.info('選ばれたチューターを確認：')
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

    request_submissions = create_get_request(
        API_URL + f'api/v1/courses/{course_number}/assignments/{assignment_number}/submissions',
        AUTH_HEADER)
    request_users = create_get_request(API_URL + f'api/v1/courses/{course_number}/users',
                                       AUTH_HEADER)

    # add tutor user_id's to list
    user_asset_pairings = []
    for i in selected_tutors:
        user_asset_pairings.append([user_dict[i]])

    # get tutor id's
    selected_tutors_id = []
    for tutor in selected_tutors:
        for entry in request_users:
            if entry['short_name'] == tutor:
                selected_tutors_id.append(entry['id'])

    # recreate dictionary with ids as key and name as value
    user_dict = {}
    for entry in request_users:
        user_dict[entry['id']] = entry['short_name']

    # put tutor user_id and submission asset_id's together
    submission_list = []

    # ** for testing
    for i in range(0, 12):
        submission_list.append(i + 42341231)
    # ** for testing

    if 'errors' in request_submissions:
        logger.error(colored.red(f"エラー: {request_submissions['errors'][0].get('message')}"))
        exit(-1)

    for entry in request_submissions:
        if entry['user_id'] in user_dict and entry['user_id'] not in selected_tutors_id:
            submission_list.append(entry['id'])
    for i in range(0, len(submission_list)):
        user_asset_pairings[i % len(selected_tutors)].append(submission_list[i])

    logger.info('コマンドを確認：')
    for i in range(0, len(user_asset_pairings)):
        for j in range(1, len(user_asset_pairings[i])):
            logger.info(
                f'curl -X POST -d user_id={user_asset_pairings[i][0]} -H \'API_KEY\' '
                f'{API_URL}api/v1/courses/{course_number}/assignments/{assignment_number}/submissions/'
                f'{user_asset_pairings[i][j]}/peer_reviews'
            )

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

    if proceed:
        logger.info('作成中...')
        for i in range(0, len(user_asset_pairings)):
            for j in range(1, len(user_asset_pairings[i])):
                reply = create_post_request(
                    API_URL + f'api/v1/courses/{course_number}/assignments/{assignment_number}/submissions/'
                              f'{user_asset_pairings[i][j]}/peer_reviews',
                    AUTH_HEADER, {'user_id': user_asset_pairings[i][0]})
                logger.info(f'DEBUG {reply}')
    else:
        logger.info('キャンセルしました。')


if __name__ == '__main__':
    main()

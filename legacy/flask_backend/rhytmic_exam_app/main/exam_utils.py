import json
import os
import math

#Move this practical score variance

def make_question_for_exam(question, type):
    """ the question types that are rendered on the theory form
    can be in of 5 formats. consult the doc for examples on how the layout
    will look when deciding which layout to use
    """
    make_question = {
        "1":make_type_one_question,
        "2":make_type_two_question,
        "3":make_type_three_question,
        "4":make_type_four_question,
        "5":make_type_five_question
    }
    return make_question[type](question)

def make_type_one_question(question):

    q = {}
    q["q"] = question.id
    q["q_string"] = question.question
    q["type"] = "1"
    q["option_a"] = question.option_a
    q["option_b"] = question.option_b
    q["option_c"] = question.option_c
    q["option_d"] = question.option_d

    return q
def make_type_two_question(question):
    
    header = json.loads(question.question_images)
    path = header["path"]["location"]

    q = {}
    q["q"] = question.id
    q["q_string"] = question.question
    q["type"] = "2"
    q["attributes"] = {}
    q["attributes"]["header"] = [os.path.join(path, x) for x in json.loads(
        question.question_images)["path"]["filename"]]
    q["attributes"]["radio1"] = [os.path.join(path, x) for x in json.loads(
        question.option_a)["path"]["filename"]]
    q["attributes"]["radio2"] = [os.path.join(path, x) for x in json.loads(
        question.option_b)["path"]["filename"]]
    q["attributes"]["radio3"] = [os.path.join(path, x) for x in json.loads(
        question.option_c)["path"]["filename"]]
    q["attributes"]["radio4"] = [os.path.join(path, x) for x in json.loads(
        question.option_d)["path"]["filename"]]

    return q

    
def make_type_three_question(question):
    header = json.loads(question.question_images)
    path = header["path"]["location"]

    q = {}
    q["q"] = question.id
    q["q_string"] = question.question
    q["type"] = "3"
    q["images"] = [os.path.join(path, x) for x in json.loads(
        question.question_images)["path"]["filename"]]
    q["option_a"] = [x for x in json.loads(question.option_a)["q_a"]]
    q["option_b"] = [x for x in json.loads(question.option_b)["q_a"]]
    q["option_c"] = [x for x in json.loads(question.option_c)["q_a"]]
    q["option_d"] = [x for x in json.loads(question.option_d)["q_a"]]

    return q

def make_type_four_question(question):
    q = {}
    q["q"] = question.id
    q["q_string"] = question.question
    q["type"] = "4"
    q["attributes"] = {}
    q["attributes"]["question_image"] = json.loads(question.question_images)["location"]
    q["attributes"]["radio1_image"] = json.loads(question.option_a)["image_location"]
    q["attributes"]["radio1_text"] = json.loads(question.option_a)["text"]
    q["attributes"]["radio2_image"] = json.loads(question.option_b)["image_location"]
    q["attributes"]["radio2_text"] = json.loads(question.option_b)["text"]
    q["attributes"]["radio3_image"] = json.loads(question.option_c)["image_location"]
    q["attributes"]["radio3_text"] = json.loads(question.option_c)["text"]
    q["attributes"]["radio4_image"] = json.loads(question.option_d)["image_location"]
    q["attributes"]["radio4_text"] = json.loads(question.option_d)["text"]

    return q

def make_type_five_question(question):
    # this one has a place holder in the text so we'll need to split it up
    q = {}
    q["q"] = question.id

    #get the string and figure out where the images are
    question_string = json.loads(question.question)["question"]
    
    replace_with_image = json.loads(question.question)["images"]

    #if there is nothing to replace... then we'll just return the string later
    if "<q_1>" in question_string:
        question_string = question_string.replace("<q_1>","<img src='{}'>".format(replace_with_image[0]))
        
    if "<q_2>" in question_string:
        question_string = question_string.replace("<q_2>","<img src='{}'>".format(replace_with_image[1]))

    q["q_string"] = question_string
    q["type"] = "5"
    q["attributes"] = {}
    q["attributes"]["radio1_image"] = json.loads(question.option_a)["image_location"]
    q["attributes"]["radio1_text"] = json.loads(question.option_a)["text"]
    q["attributes"]["radio2_image"] = json.loads(question.option_b)["image_location"]
    q["attributes"]["radio2_text"] = json.loads(question.option_b)["text"]
    q["attributes"]["radio3_image"] = json.loads(question.option_c)["image_location"]
    q["attributes"]["radio3_text"] = json.loads(question.option_c)["text"]
    q["attributes"]["radio4_image"] = json.loads(question.option_d)["image_location"]
    q["attributes"]["radio4_text"] = json.loads(question.option_d)["text"]

    return q

def calculate_theory_score(user_answers, actual_answers):
    """ Takes 2 dictionaries and compares them for 
    differences. The result is a percentage and the incorrect answers
    """
    total = len(actual_answers)
    correct = 0
    incorrect_answers = {}

    for k in actual_answers.keys():
        #If there isn't an answer, set it to someting that will not be correct
        if actual_answers[k] == user_answers.get(k, "E"):
            correct +=1
        else:
            incorrect_answers[k] = [actual_answers[k], user_answers.get(k)]

    percentage = round(correct / total * 100, 1)

    return percentage, incorrect_answers

def calculate_practical_score(user_answers, actual_answers):
    user_result = {}
 
    total_score = 0
        
    for answer in actual_answers:
        user_result[answer.internal_question_value] = {}

        user_answer = user_answers.get(answer.internal_question_value)
        user_answer = None if user_answer == "" else user_answer

        #keep a tally of the practical scores
        if user_answer:
            user_answer = _sanatize_user_answer(user_answer)
            mark = get_practical_mark(answer.control_score, user_answer)
        else:
            mark = 0

        user_result[answer.internal_question_value] = [
            answer.decipline,
            answer.result_question_value,
            answer.control_score,
            user_answer if user_answer is not None else "-1",
            mark
            ]

        total_score += mark
        #print(answer.internal_question_value, answer.result_question_value, answer.control_score)
    percentage = _round_half((total_score/100) *100)

    user_result = _sort_practical_result(user_result)

    return percentage, user_result

def get_practical_mark(control_score, user_score):
    """ the further away the user score is from the control score,
        the lesss marks are rewarded. the maximum is 1 and decrements in 0.05
    """
    
    #This is a string comparison... perhaps make it a float comparison?
    if control_score == user_score:
        return 5

    difference = _round_half(abs(float(control_score) - float(user_score)),decimal=2)

    point_allocation = [x * 0.25 for x in range(1,20)][::-1] # revers the row
    diff_arr = [_round_half(x * 0.05) for x in range(1,20)]

    if difference >= 1 or difference <= 0:
        return 0
    else:
        return point_allocation[diff_arr.index(difference)]

def _round_half(n, decimal=2):
    mutiplier = 10 ** decimal
    return math.floor(n*mutiplier  + 0.5) / mutiplier

def _sort_practical_result(result):
    """Sort by appartus"""
    practical_answers = {}

    app = ""
    for answer in result.values():
        if app != answer[0]:
            app = answer[0]
            if not practical_answers.get(app):
                practical_answers[answer[0]] = {}
                #[application][decipline] = control score, user answer, mark
        practical_answers[app][answer[1]] = [answer[2], answer[3], answer[4]]

    return practical_answers

def _sanatize_user_answer(answer):
    """ replace chars that shouldn't be in the answer """

    #The user may have forgotten to enter a 0
    if answer[0] == ".":
        answer = "0" + answer

    #values such as / , and - will not work so replace them
    try:
        return answer.replace("/",".").replace(",",".").replace("-","")
    except Exception:
        #then we have no idea what the user intended to write down
        return -2
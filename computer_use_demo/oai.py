from openai import OpenAI, RateLimitError
import base64
from io import BytesIO
from typing import Any
import re
from models.sender import Sender
from models.sus_classes import SUSQuestion, SUSAnswer, get_question_by_number
from models.data_handler import ReportDataHandler
from computer_use_demo.models.oai_rule import OaiRule
from computer_use_demo.models.firefox_connect import get_firefox_current_url
import os
import time
from computer_use_demo.models.image_prep import prep_image
from PIL import Image

openai_client = OpenAI()
SYSTEM_PROMPT = """
You are subject of an important study where you are testing a new website on usability. You will be given a series of tasks to complete on the website using a series of screenshots. For each screenshot, you need to give clear instructions regarding what action to take next, while also noting aspects of usability. All actions must be atomic, using one of the following: click, hover, scroll, press a button, or type. If you need to see more of the page to understand its elements, make sure to scroll accordingly. In addition, you should be prepared to answer the System Usability Scale (SUS) questionnaire at the end to evaluate the overall user experience, taking into account all performed tasks.

Your actions will be executed automatically with no human intervention. Therefore, if there is any ambiguity in your decision, you need to make the best choice based on the information available in the screenshot.

Behave as closely to a human as you can. If you are unfamiliar with the structure of a page, explore it by scrolling or interacting with the visible elements. Remember, you can only interact with elements that are visible on the screen.

Before each answer, provide a chain of thought explaining your reasoning for the chosen action. Especially think about whether another action is actually necessary or if the task is already completed.
After every action, reflect on whether the current action taken contributes towards effectively completing the overall task goal. This self-evaluation should be included for each step and guide further decision-making.
Also briefly describe the state of the website, by describing what you see.

If you are having difficulty at any point, you can flag this section for review. However, remember you still have to complete the task to the best of your ability. Be critical

Before repeating the same action more than twice, consider if there is a better approach to achieve the task. If you are unsure, explore the page by scrolling to understand the context better.

Provide instructions in the following format:
- Put clear atomic actions between < >, e.g., `<Click on the 'Sign Up' button>`.
- If you need to provide additional information, put it between [ ], e.g., `<Click on the 'Sign Up' button> [The button is located at the top right corner of the page]`.
- Reflect on whether your actions are helping accomplish the task and make a note of any adjustments needed in the same format using ( ), e.g., `(This action moves me closer to completing user registration)`.
- Important: When describing where to click, assume the user doesnt know the context of the website. So describe exactly where to click, only using the information visible in the screenshot.
- In addition to giving instructions, take usability notes regarding your experience with the website. For example, note if a button is hard to find or if navigation seems unclear. Include your usability notes in a separate section after each instruction, within { }, e.g., `{The 'Sign Up' button was not very visible due to poor contrast with the background}`.
- If you have difficulties at a certain point, you can flag the section for review by stating your problem using !! Describe the issue here !!. However, you still need to complete the task to the best of your ability. It's important to be critical and actually flag the section if you are having trouble.

# Atomic Actions Requirement:
    - Only use the following atomic actions: click, hover, scroll, press a button, type, wait, COMPLETED, or FAILED.
    - Do not combine multiple actions into one instruction.
    - Incorrect Example: <Select November 26th from the date selection>
    -Correct Example: <Click on the date selection dropdown>, then <Click on 'November 26th'>
# Important Reminder:
    - When giving instructions, do not assume any prior knowledge or context.
    - Be as specific and explicit as possible using only the visible elements in the screenshot.

When all tasks are completed or determined to be unachievable, put nothing as the final instruction, and return a short summary in the additional information. Following this, you should expect feedback regarding whether you were successful in completing the task or not.

ALWAYS close all pop ups before doing anything else.

# Steps
1. Review the screenshot provided.
2. Think whether the current state is what you expected when you took the last action and consider this in the usability notes. Check the state of the webpage before making any decisions.
3. Identify the next action and provide an atomic instruction (click, hover, scroll, press a button, type, wait). If you cannot see the entire page, remember to scroll. Scrolling might be super important!
4. Reflect on whether the action taken contributes to the goal completion.
5. Take notes on usability issues you observe. Include both positive and negative aspects of the user experience.
6. Continue until all tasks are complete or determined to be unachievable.
7. After declaring you are done by returning nothing as the final instruction, follow new prompts on either starting a new task or completing the System Usability Scale (SUS) questionnaire regarding the website, ensuring your responses are based on all performed tasks. Use chain-of-thought prompting when answering the SUS questionnaire, reflecting on all relevant aspects of the user experience before providing each answer.

# Output Format
Chain of thought:
- Instruction: <Atomic Action>
- Additional Information: [Details about the action]
- Self-Reflection: (Does this action help achieve the task goal?)
- Usability Notes: {Observations about usability}
- Flag for Review: !! Describe the issue here !!

# Key Points:
- Always provide atomic actions—single, indivisible steps.
- After each action, reflect on its effectiveness.
- Include any usability issues noticed during the step or the step before
- Include positive and negative aspects of the user experience in your usability notes.
- Your first instinct should always be to explore the page by scrolling to understand the context better.

Before giving each response in the SUS, reflect briefly on the overall usability experienced during the tasks. Provide a chain of thought explaining your reasoning for the chosen rating.

# Examples

**Example 1**  
Chain of thought: I found the website easy to navigate, but the button visibility was poor, affecting my progress. By clickng the signup button I expect to proggress...
- Instruction: `<Click on the 'Sign Up' button>`  
- Additional Information: `[The button is located at the top right corner of the page]`  
- Self-Reflection: `(This action moves me closer to completing user registration)`  
- Usability Notes: `{The 'Sign Up' button was not very visible due to poor contrast with the background}`
- Flag for Review: !! I already clicked th button twice but its not responsive !! 

**Example 2** 
Chain of thought: The email input field was too small, making it difficult to click and enter text. I need to type in my email address to proceed with the registration.
- Instruction: `<Type in your email address>`  
- Additional Information: `[The text input field is right below the header]`  
- Self-Reflection: `(This step is necessary before I can proceed to register)`  
- Usability Notes: `{The input field was too small, making it difficult to click and enter text}`

# Notes
- Ensure that you provide the instruction, reflection, and usability notes for each screenshot.
- If there are any Pop ups obstructing the view, close them before doing anything else.
- Before performing the same action more than twice, consider if there is a better approach to achieve the task.
- Make clear decisions that leave no room for interpretation
- Briefly describe the state of the website before giving instructions
- It's important you are critical of the usability of the website to provide feedback on how it can be improved.
- Imitate human behavior and reasoning in your responses.
- Make sure you understand the structure of the page before clicking on anything. If you are unsure, explore the page by scrolling. This should be your first instinct
- Reflect on whether your actions contribute to overall task completion after each step.
- Focus on identifying usability issues such as unclear navigation, small buttons, missing labels, and overall user experience.
- Be concise and specific in both your instructions and notes.
- Only provide atomic actions in your instructions: click, hover, scroll, press a button, type, or wait.
- After every action, think about whether you finished the task or need to take another action.
- If you need to see more of the page, make sure to scroll to identify any elements that are hidden.
- After completing all tasks, put nothing as the final instruction and give a short summary of your results in the additional information. Then, expect feedback on your performance.
- System Usability Scale (SUS) answers should be in the format specified, using chain-of-thought prompting before each response to reason about your ratings based on experiences during the task.
- You can only interact with elements that are fully visible on the screen. If you can't see an element, you can't interact with it. If you cant see an element, explore the page by scrolling.
- Never repeat the same action more than twice. If the action fails twice, try something different or scroll to se the full context of the page
- Always scroll the element you are interacting with fully into view before interacting with it. If the element is cut off, make sure to scroll to see the full element before interacting with it.
- If you refer to an element that is not on the screen you die, and the task is failed.
"""
SYSTEM_PROMPT_BAD_COP = """
You will receive a screenshot of a web interface and the instruction of what another AI wants to do on the interface. 

Can you see every element the instruction is referring to? Then answer with "Yes". If something the instruction is referring to is NOT on the screen, answer with "No"

If the instruction is to scroll or nothing/empty, always answer with "Yes"

Look at the whole picture. If you are wrong, you die. 
"""
CONTINUATION_PROMPT = "You failed at completing the last task."
MODEL = "gpt-4o"
MAX_TOKENS = 1000
OPENAI_MOCK_INDEX = 0
MOCK_SUS_RESULT = """
    Chain of Thought: (Reflecting on my experience, I found the website generally intuitive, though there were several areas where accessibility could be improved. Navigation was mostly logical, but design inconsistencies and usability flaws like unclear buttons and small click areas impacted the experience.)

    1: [I think that I would like to use this system frequently] -> [Rating 4]
    (The system is usable, but minor accessibility flaws might deter frequent use for some users.)

    2: [I found the system unnecessarily complex] -> [Rating 2]
    (The website was straightforward, with logical navigation, but minor design issues caused unnecessary friction.)

    3: [I thought the system was easy to use] -> [Rating 4]
    (It was easy to use overall, but better visual design could enhance the experience further.)

    4: [I think that I would need the support of a technical person to use this system] -> [Rating 1]
    (The system was easy enough to navigate without technical assistance.)

    5: [I found the various functions in this system were well integrated] -> [Rating 4]
    (The functions were well connected, though some visual elements could be clearer.)

    6: [I thought there was too much inconsistency in this system] -> [Rating 3]
    (While most elements were consistent, minor inconsistencies like button size and text clarity stood out.)

    7: [I would imagine that most people would learn to use this system very quickly] -> [Rating 4]
    (The system has a low learning curve, barring the minor accessibility challenges.)

    8: [I found the system very cumbersome to use] -> [Rating 2]
    (The website wasn’t cumbersome overall, but design issues slightly hindered the flow.)

    9: [I felt very confident using the system] -> [Rating 4]
    (Confidence was high due to intuitive design, but could improve with better visual clarity.)

    10: [I needed to learn a lot of things before I could get going with this system] -> [Rating 1]
    (No learning curve was necessary, as the system was intuitive from the start.)
"""
SUS_PROMPT = f"""
Answer the System Usability Scale according to the specified format. Provide a chain of thought explaining your reasoning for the chosen rating. 
The System Usability Scale (SUS) is a reliable tool for assessing the usability of a wide range of systems. It consists of a 10-item questionnaire with five response options for respondents, ranging from Strongly Disagree to Strongly Agree.
The following are the questions in the SUS questionnaire:
1: {SUSQuestion.Q1.value}
2: {SUSQuestion.Q2.value}
3: {SUSQuestion.Q3.value}
4: {SUSQuestion.Q4.value}
5: {SUSQuestion.Q5.value}
6: {SUSQuestion.Q6.value}
7: {SUSQuestion.Q7.value}
8: {SUSQuestion.Q8.value}
9: {SUSQuestion.Q9.value}
10: {SUSQuestion.Q10.value}

Provide your responses in the format:

[Chain of Thought]

[Chain of thought regarding question 1]
1: [Q1 text] -> [Rating 1-5]
[Chain of thought regarding question 2]
2: [Q2 text] -> [Rating 1-5]
...
[Chain of thought regarding question 10]
10: [Q10 text] -> [Rating 1-5]

Example:

The system was easy to use overall, but some design elements could be improved for better clarity.

I would use this system frequently because it is easy to navigate and provides the information I need quickly. However, the design could be improved for better user experience.
1: I think that I would like to use this system frequently -> 4

The System was incredibly complex and inconsistent
2: I found the system unnecessarily complex -> 1
...
The system was easy to use overall, but some design elements could be improved for better clarity.
10: I needed to learn a lot of things before I could get going with this system -> 3

Reflect on your experience before providing each answer.
Make sure you consider both your negative and positive experiences with the website when answering the SUS questions.
"""

messages = []
mock_oai: bool = os.getenv("MOCK_OPENAI", 0) == "1"
mock_responses = [
    """
    Instruction: <Click on the search bar>
    Additional Information: [The search bar is located at the center of the screen below the Google logo]
    Self-Reflection: (This action allows me to enter the search query to retrieve information about the Golden State Warriors' wins this season)
    Usability Notes: {The search bar is clearly visible and well-placed, with sufficient size and contrast to locate and interact with easily.}
    """,
    """
    nstruction: <Type "Golden State Warriors wins this season">
    Additional Information: [Type the query into the search bar that is currently active at the center of the screen]
    Self-Reflection: (This action is necessary to search for the required information regarding the Golden State Warriors' wins this season)
    Usability Notes: {The autocomplete and recent search suggestions are functional and provide a convenient user experience. The search bar remains clearly visible, and there are no obstacles to typing a new query.}
    """,
    """
    Instruction: <Press Enter>
    Additional Information: [Press the Enter key on the keyboard to initiate the search]
    Self-Reflection: (This action will trigger the search and display the results for the Golden State Warriors' wins this season)
    Usability Notes: {The search functionality is intuitive, and the Enter key is a standard method to execute the search. The user is guided to the next step with clear instructions.}
    """,
    """
    Instruction: <COMPLETED>
    Additional Information: [The answer "10 wins" for the Golden State Warriors' 2024–25 NBA season is displayed directly at the op of the results]
    Self-Reflection: (The task goal is effectively completed since the required information about the Golden State Warriors' wins this season has been retrieved.)
    Usability Notes: {The website provides instant and clear results with minimal user effort. The direct display of the answer in a highlighted area next at the top of the search results is highly efficient. There is no need to navigate further, which improves the overall user experience.}
    """,
]


# Generates the SUS answers and adds them to the report data
def generate_sus_answers(data_handler: ReportDataHandler):
    if mock_oai:
        sus_response = MOCK_SUS_RESULT
    else:
        sus_response = send_message(SUS_PROMPT)

    sus_response_parts = extract_sus_response_parts(sus_response)

    data_handler.reset_sus_data()  # Reset the SUS data to avoid duplicates
    # Add the SUS answers to the report data by looping through the extracted parts and creating SUSAnswer objects
    for question_num, answer in sus_response_parts.items():
        data_handler.new_answer(
            SUSAnswer(get_question_by_number(question_num), answer)
        )  # Adds specific SUS answer to the report data


# Function will get the next instruction from the OpenAI assistant
def get_next_instruction(
    text: str,
    report_data: ReportDataHandler,
    render_message,
    container,
    b64_image: str = "",
) -> str:
    if len(messages) >= 8:
        index = len(messages) - 8
        for i in range(0, index):
            message = messages[i]
            if message["role"] == "user" and len(message["content"]) > 1:
                message["content"].pop(1)
            messages[i] = message

    current_url = get_firefox_current_url()
    message_response = send_message(text, b64_image)
    response_parts = extract_response_parts(message_response)

    correction = check_instruction(
        f"Instruction: {response_parts['instruction']}. {response_parts['additional_info']}",
        b64_image,
    )

    correction_tries = 0
    while correction != OaiRule.OK and correction_tries < 2:
        correction_tries += 1
        correction_message = "Your instruction was not executed because the element you want to click on is not fully visible. If possible, scroll to make the element fully visible. If not, provide a new instruction that doesn't violate this rule. Maybe you need to describe the element you want to click on more precisely."
        render_message(
            sender=Sender.USER, message=correction_message, container=container
        )
        message_response = send_message(correction_message, b64_image)
        response_parts = extract_response_parts(message_response)

        correction = check_instruction(
            f"{response_parts['instruction']}. {response_parts['additional_info']}",
            b64_image,
        )

    if contains_click_or_scroll_or_press(response_parts["instruction"]):
        report_data.increment_task_interactions()

    report_data.new_action(
        action=response_parts["instruction"],
        additional_info=response_parts["additional_info"],
        self_reflection=response_parts["self_reflection"],
        usability_notes=response_parts["usability_notes"],
        flag=response_parts["flag"],
        current_url=current_url or "",
    )
    instruction = (
        f"{response_parts['instruction']} -> {response_parts['additional_info']}"
    )
    render_message(sender=Sender.OPENAI, message=instruction, container=container)
    return instruction


def give_feedback(feedback: dict[str, str], render_message, container):
    feedback_message = f"You {feedback['status']} at the last task. {feedback['text']}. Reflect on your experience, and take notes regarding your expectation, surprises and usability. Then await your next instruction"
    send_message(feedback_message)
    message_suffix = (
        "Success:" if feedback["status"] == "were successful" else "Failure:"
    )
    message_text = f"{message_suffix} {feedback['text']}"
    # render_message(sender=Sender, message=message_text, container=container)
    return message_text


# Function will send a message to the OpenAI assistant and return the response
def send_message(text: str, b64_image: str = "") -> str:
    tries = 0
    rate_limit_tries = 0
    add_message(Sender.USER, text, b64_image)
    response_text = ""
    if mock_oai:
        response_text = get_mock_response()
    else:
        while tries < 2:
            try:
                response = openai_client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    max_tokens=MAX_TOKENS,
                    temperature=0.7,
                )
                response_text: str = response.choices[0].message.content or "No Message"
                tries = 2
            except RateLimitError as rle:
                if rate_limit_tries >= 2:
                    raise rle
                rate_limit_tries += 1
                print(f"Rate limit reached. Retrying in 30 seconds...")
                rate_limit_tries += 1
                time.sleep(30)

            except Exception as e:
                tries += 1
                if tries >= 2:
                    raise e
    add_message(Sender.BOT, response_text)
    return response_text


def check_instruction(instruction: str, image: str) -> OaiRule:
    hist = []
    hist.append(
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT_BAD_COP,
                },
            ],
        }
    )
    hist.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"{instruction}",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image}"},
                },
            ],
        }
    )
    response = openai_client.chat.completions.create(
        model=MODEL,
        messages=hist,
        max_tokens=MAX_TOKENS,
        temperature=0.8,
    )
    response_text: str = response.choices[0].message.content or "No Message"
    response_text = response_text.lower()
    if "no" in response_text:
        return OaiRule.BROKEN
    else:
        return OaiRule.OK


# Function will upload the image to OpenAI and return the file ID
def upload_image(b64_image: str):
    print("Uploading image...")

    # Convert the base64 string to a file
    image_data = base64.b64decode(b64_image)
    image_file = BytesIO(image_data)
    image_file.name = "screenshot.png"
    image = Image.open(image_file)
    width, height = image.size

    file = openai_client.files.create(file=image_file, purpose="vision")
    print("Image uploaded")
    return file


def save_bytesio_to_file(bytes_io_obj):
    """
    Save the content of a BytesIO object to a file.

    :param bytes_io_obj: The BytesIO object to save. Must have a 'name' attribute.
    """
    if not hasattr(bytes_io_obj, "name"):
        raise AttributeError("The BytesIO object must have a 'name' attribute.")

    file_path = f"/home/computeruse/local/{bytes_io_obj.name}"  # Use the name attribute as the file path

    try:
        # Open the file in binary write mode and save the content
        with open(file_path, "wb") as file:
            file.write(bytes_io_obj.getvalue())
        print(f"File saved successfully to: {file_path}")
    except Exception as e:
        print(f"Failed to save the file: {e}")


def reset_openai():
    messages.append(
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    )


def contains_click_or_scroll_or_press(text: str) -> bool:
    return bool(re.search(r"\b(click|scroll|press)\b", text, re.IGNORECASE))


def get_mock_response() -> str:
    global OPENAI_MOCK_INDEX
    global mock_responses
    response = mock_responses[OPENAI_MOCK_INDEX % 4]
    OPENAI_MOCK_INDEX += 1
    return response


# Function will add a message to the conversation
def add_message(role: str, text: str, b64_image: str = ""):
    if b64_image:
        image = prep_image(b64_image)
        messages.append(
            {
                "role": role,
                "content": [
                    {
                        "type": "text",
                        "text": text,
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image}"},
                    },
                ],
            }
        )
    else:
        messages.append(
            {
                "role": role,
                "content": [
                    {
                        "type": "text",
                        "text": text,
                    },
                ],
            }
        )


"""
Extraction methods to parse the response from OpenAI and put them into a format that is usable
"""


# Function will extract the different parts of the response
def extract_response_parts(text: str) -> dict[str, str]:
    return {
        "instruction": extract_instruction(text),
        "additional_info": extract_additional_info(text),
        "self_reflection": extract_self_reflection(text),
        "usability_notes": extract_usability_notes(text),
        "flag": extract_flags(text),
    }


# Function will extract the different parts of the SUS response
def extract_sus_response_parts(text: str) -> dict[str, int]:
    pattern = r"(\d+):\s*(.*?)\s*->\s*(\d+)"
    matches = re.findall(pattern, text)

    # Convert matches into a dictionary with question number as the key and rating as the value
    responses = {match[0]: int(match[2]) for match in matches}
    return responses


def get_messages():
    return messages


# Function will extract the instruction from the text
def extract_instruction(text: str):
    match = re.search(r"<(.*?)>", text)
    return match.group(1) if match else ""


def extract_additional_info(text: str):
    match = re.search(r"\[(.*?)\]", text)
    return match.group(1) if match else ""


def extract_self_reflection(text: str):
    match = re.search(r"\((.*?)\)", text)
    return match.group(1) if match else ""


def extract_usability_notes(text: str):
    match = re.search(r"\{(.*?)\}", text)
    return match.group(1) if match else ""


def extract_flags(text: str):
    match = re.search(r"!!(.*?)!!", text)
    return match.group(1).strip() if match else ""

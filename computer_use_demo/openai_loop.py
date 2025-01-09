from typing import Any, cast
import streamlit as st
from functools import partial
from computer_use_demo import oai as OaiTool
from computer_use_demo.anthropic_access import sampling_loop
from tools.ant import prep_execution_request

import time
from anthropic.types.beta import BetaMessageParam

from models.sender import Sender

import requests

from tools import (
    BashTool,
    ComputerTool,
    EditTool,
    ToolCollection,
    ToolResult,
)


tool_collection = ToolCollection(
    ComputerTool(),
    BashTool(),
    EditTool(),
)

PROMPT_ADDITION = """
Reflection Reminder:
In your self-reflection, you may reference previous actions to assess progress toward the goal.
Example: (After clicking 'Next', I am now closer to completing the sign-up process.)
Visibility Reminder:
You can only interact with elements that are visible. If you can't see an element, you can't interact with it.
"""


async def custom_loop(
    mission: str,
    messages: list[BetaMessageParam],
    context,
    exchange_logs,
    _render_message,
    _tool_output_callback,
    _api_response_callback,
):
    manual_mode = False
    first = True  # First iteration of the loop
    # Initialize the OpenAI assistant
    OaiTool.reset_openai()

    while True:
        screenshot = await get_base64_screenshot()
        prompt = (
            f"New Task: {mission}"
            if first
            else f"What's the next step? As a reminder, this is the current task: {mission}"
        )
        instruction: str = OaiTool.get_next_instruction(
            f"{prompt}. {PROMPT_ADDITION}",
            st.session_state.data_handler,
            _render_message,
            context,
            screenshot,
        )  # Get the next instruction from the OpenAI assistant
        st.session_state.messages.append(
            {"role": Sender.OPENAI, "content": [{"type": "text", "text": instruction}]}
        )
        # messages.append(
        #     {"role": "assistant", "content": [{"type": "text", "text": instruction}]}
        # )
        # Define the patterns to check
        last_instruction = False
        patterns = ["completed->", "failed->", "->", "nothing->"]
        instruction_copy = instruction
        instruction_copy = "".join(instruction_copy.lower().split())
        # Check which pattern the string starts with
        for pattern in patterns:
            if (instruction_copy).startswith(pattern):
                last_instruction = True

        if last_instruction:  # Mission is completed or failed
            # Show Feedback pop-up
            st.session_state.popup = True
            break
        # Execute the instruction
        prepped_messages: list[BetaMessageParam] = prep_execution_request(
            instruction, screenshot
        )
        if manual_mode:
            time.sleep(4)
        else:
            await sampling_loop(
                system_prompt_suffix=st.session_state.custom_system_prompt,
                model=st.session_state.model,
                provider=st.session_state.provider,
                messages=st.session_state.messages,
                prepped_messages=prepped_messages,
                output_callback=partial(
                    _render_message, sender=Sender.ANTHROPIC, container=context
                ),
                tool_output_callback=partial(
                    _tool_output_callback,
                    tool_state=st.session_state.tools,
                    context=context,
                ),
                api_response_callback=partial(
                    _api_response_callback,
                    tab=exchange_logs,
                    response_state=st.session_state.responses,
                ),
                api_key=st.session_state.api_key,
                only_n_most_recent_images=st.session_state.only_n_most_recent_images,
            )
        first = False

    return st.session_state.messages
    # Get specific instructions for the action // Call Anthropic API with openAI response and screenshot as input

    # Execute the action


async def get_base64_screenshot() -> str:
    screenshot = (
        await tool_collection.run(
            name="computer", tool_input=cast(dict[str, Any], {"action": "screenshot"})
        )
    ).base64_image
    return screenshot if screenshot else ""


async def execute_instruction(instruction: str, screenshot: str):
    # Get specific tool instruction
    time = "Debug"
    # Execute Tool instruction

"""
Entrypoint for streamlit, see https://docs.streamlit.io/
"""

import asyncio
import base64
import websocket
import os
import subprocess
import traceback
from datetime import datetime, timedelta
from enum import StrEnum
from functools import partial
from pathlib import PosixPath
from typing import cast
from reports import ReportDataHandler, create_report

import httpx
import streamlit as st
from anthropic import RateLimitError
from anthropic.types.beta import (
    BetaContentBlockParam,
    BetaTextBlockParam,
)
from models.sender import Sender
import computer_use_demo.oai as oai

from streamlit.delta_generator import DeltaGenerator

from computer_use_demo.anthropic_access import (
    PROVIDER_TO_DEFAULT_MODEL_NAME,
    APIProvider,
    sampling_loop,
)
from computer_use_demo.tools import ToolResult

FILE_OUTPUT_DIR = "/home/computeruse/local"
FILE_OUTPUT_NAME = "report"
CONFIG_DIR = PosixPath("~/.anthropic").expanduser()
API_KEY_FILE = CONFIG_DIR / "api_key"
STREAMLIT_STYLE = """
<style>
    /* Hide chat input while agent loop is running */
    .stApp[data-teststate=running] .stChatInput textarea,
    .stApp[data-test-script-state=running] .stChatInput textarea {
        display: none;
    }
     /* Hide the streamlit deploy button */
    .stAppDeployButton {
        visibility: hidden;
    }
</style>
"""

WARNING_TEXT = "⚠️ Security Alert: Never provide access to sensitive accounts or data, as malicious web content can hijack Claude's behavior"
# ANTHROPIC_IMAGE = st.image("./img/anthropic.png")
# OPENAI_IMAGE = st.image("./img/openai.png")

tool_instruction = os.getenv("TOOL_INSTRUCTION", None)
tool_termination = os.getenv("TOOL_TERMINATION", None)


def setup_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "api_key" not in st.session_state:
        # Try to load API key from file first, then environment
        st.session_state.api_key = load_from_storage("api_key") or os.getenv(
            "ANTHROPIC_API_KEY", ""
        )
    if "provider" not in st.session_state:
        st.session_state.provider = (
            os.getenv("API_PROVIDER", "anthropic") or APIProvider.ANTHROPIC
        )
    if "provider_radio" not in st.session_state:
        st.session_state.provider_radio = st.session_state.provider
    if "model" not in st.session_state:
        _reset_model()
    if "auth_validated" not in st.session_state:
        st.session_state.auth_validated = False
    if "responses" not in st.session_state:
        st.session_state.responses = {}
    if "tools" not in st.session_state:
        st.session_state.tools = {}
    if "only_n_most_recent_images" not in st.session_state:
        st.session_state.only_n_most_recent_images = 1
    if "custom_system_prompt" not in st.session_state:
        st.session_state.custom_system_prompt = load_from_storage("system_prompt") or ""
    if "hide_images" not in st.session_state:
        st.session_state.hide_images = False
    if "data_handler" not in st.session_state:
        st.session_state.data_handler = ReportDataHandler()
    if "popup" not in st.session_state:
        st.session_state.popup = False  # whether or not feedback popup is shown
    if "feedback" not in st.session_state:
        st.session_state.feedback = None
    if "wait_for_task" not in st.session_state:
        st.session_state.wait_for_task = True


def _reset_model():
    st.session_state.model = PROVIDER_TO_DEFAULT_MODEL_NAME[
        cast(APIProvider, st.session_state.provider)
    ]


def main():
    print("I AM ACTUALLY STARTING")
    setup_state()

    st.markdown(STREAMLIT_STYLE, unsafe_allow_html=True)

    st.title(f"Automated Testing Tool {os.getenv('HOST_APP_PORT', '')}")

    st.button("Early Stop and give feedback", on_click=stop_and_give_feedback)

    # if not os.getenv("HIDE_WARNING", False):
    #     st.warning(WARNING_TEXT)

    with st.sidebar:

        def _reset_api_provider():
            if st.session_state.provider_radio != st.session_state.provider:
                _reset_model()
                st.session_state.provider = st.session_state.provider_radio
                st.session_state.auth_validated = False

        provider_options = [option.value for option in APIProvider]
        st.radio(
            "API Provider",
            options=provider_options,
            key="provider_radio",
            format_func=lambda x: x.title(),
            on_change=_reset_api_provider,
        )

        st.text_input("Model", key="model")

        if st.session_state.provider == APIProvider.ANTHROPIC:
            st.text_input(
                "Anthropic API Key",
                type="password",
                key="api_key",
                on_change=lambda: save_to_storage("api_key", st.session_state.api_key),
            )

        st.number_input(
            "Only send N most recent images",
            min_value=0,
            key="only_n_most_recent_images",
            help="To decrease the total tokens sent, remove older screenshots from the conversation",
        )
        st.text_area(
            "Custom System Prompt Suffix",
            key="custom_system_prompt",
            help="Additional instructions to append to the system prompt. see computer_use_demo/loop.py for the base system prompt.",
            on_change=lambda: save_to_storage(
                "system_prompt", st.session_state.custom_system_prompt
            ),
        )
        st.checkbox("Hide screenshots", key="hide_images")

        if st.button("Reset", type="primary"):
            with st.spinner("Resetting..."):
                st.session_state.clear()
                setup_state()

                subprocess.run("pkill Xvfb; pkill tint2", shell=True)  # noqa: ASYNC221
                asyncio.run(asyncio.sleep(1))
                subprocess.run("./start_all.sh", shell=True)  # noqa: ASYNC221

    if not st.session_state.auth_validated:
        if auth_error := validate_auth(
            st.session_state.provider, st.session_state.api_key
        ):
            st.warning(f"Please resolve the following auth issue:\n\n{auth_error}")
            return
        else:
            st.session_state.auth_validated = True

    chat, http_logs = st.tabs(["Chat", "HTTP Exchange Logs"])

    # new_message = st.chat_input(
    #     "Input new task to test system",
    # )

    # render past chats
    for message in st.session_state.messages:
        if isinstance(message["content"], str):
            _render_message(message["content"], message["role"], chat)
        elif isinstance(message["content"], list):
            for block in message["content"]:
                # the tool result we send back to the Anthropic API isn't sufficient to render all details,
                # so we store the tool use responses
                if isinstance(block, dict) and block["type"] == "tool_result":
                    _render_message(
                        st.session_state.tools[block["tool_use_id"]], Sender.TOOL, chat
                    )
                else:
                    _render_message(
                        cast(BetaContentBlockParam | ToolResult, block),
                        message["role"],
                        chat,
                    )

    if (
        st.session_state.wait_for_task and st.session_state.popup == False
    ):  # Waiting for new task input by user
        st.markdown("### Input your next task")
        with st.form(key="popup_form"):
            task_description = st.text_input("Enter your task description:")
            task_done = st.text_input("When is the task done?")
            submit = st.form_submit_button(label="Let's go!")

            if submit:
                new_message = f"{task_description}. {task_done}."
                st.session_state.wait_for_task = False
                st.session_state.messages.append(
                    {
                        "role": Sender.USER,
                        "content": [BetaTextBlockParam(type="text", text=new_message)],
                    }
                )
                _render_message(new_message, Sender.USER, chat)
                st.session_state.data_handler.new_task(new_message)
                st.rerun()

    # render past http exchanges
    for identity, (request, response) in st.session_state.responses.items():
        _render_api_response(request, response, identity, http_logs)

    # render past chats
    # if new_message:
    #     st.session_state.messages.append(
    #         {
    #             "role": Sender.USER,
    #             "content": [BetaTextBlockParam(type="text", text=new_message)],
    #         }
    #     )
    #     _render_message(new_message, Sender.USER, chat)
    #     st.session_state.data_handler.new_task(new_message)

    # Popup allowing user to give feedback
    if st.session_state.popup:
        st.markdown(
            "### Was the task completed successfully? If not, please provide feedback."
        )
        with st.form(key="popup_form"):
            user_input = st.text_input("Provide Feedback:")
            succesfull_button = st.form_submit_button(label="Successful")
            failed_button = st.form_submit_button(label="Failed")
            if succesfull_button:
                st.session_state.feedback = {
                    "status": "were successful",
                    "text": user_input,
                }
                st.session_state.popup = False  # Close popup after submission
                message = oai.give_feedback(
                    st.session_state.feedback, _render_message, chat
                )
                st.session_state.data_handler.new_feedback(st.session_state.feedback)
                st.session_state.messages.append(
                    {
                        "role": Sender.FEEDBACK,
                        "content": [{"type": "text", "text": message}],
                    }
                )
                st.session_state.wait_for_task = True
                st.session_state.data_handler.reset_task_interactions()
                st.rerun()

            if failed_button:
                st.session_state.feedback = {"status": "failed", "text": user_input}
                st.session_state.popup = False
                message = oai.give_feedback(
                    st.session_state.feedback, _render_message, chat
                )
                st.session_state.data_handler.new_feedback(st.session_state.feedback)
                st.session_state.messages.append(
                    {
                        "role": Sender.FEEDBACK,
                        "content": [{"type": "text", "text": message}],
                    }
                )
                st.session_state.wait_for_task = (
                    True  # Enable option to add the next task
                )
                st.session_state.data_handler.reset_task_interactions()
                st.rerun()

    st.button(
        label="Generate Report",
        on_click=partial(_init_report, chat),
    )

    try:
        most_recent_message = st.session_state["messages"][-1]
    except IndexError:
        return

    if most_recent_message["role"] is not Sender.USER:
        # we don't have a user message to respond to, exit early
        return

    with st.spinner("Running Agent..."):
        # run the opena ai loop and execute the actions proposed by the agent
        from computer_use_demo.openai_loop import custom_loop

        most_recent_message = st.session_state["messages"][-1]["content"][0]["text"]
        st.session_state.messages = asyncio.run(
            custom_loop(
                mission=most_recent_message,
                messages=st.session_state.messages,
                context=chat,
                exchange_logs=http_logs,
                _render_message=_render_message,
                _tool_output_callback=_tool_output_callback,
                _api_response_callback=_api_response_callback,
            )
        )
        st.rerun()


def validate_auth(provider: APIProvider, api_key: str | None):
    if provider == APIProvider.ANTHROPIC:
        if not api_key:
            return "Enter your Anthropic API key in the sidebar to continue."
    if provider == APIProvider.BEDROCK:
        import boto3

        if not boto3.Session().get_credentials():
            return "You must have AWS credentials set up to use the Bedrock API."
    if provider == APIProvider.VERTEX:
        import google.auth
        from google.auth.exceptions import DefaultCredentialsError

        if not os.environ.get("CLOUD_ML_REGION"):
            return "Set the CLOUD_ML_REGION environment variable to use the Vertex API."
        try:
            google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        except DefaultCredentialsError:
            return "Your google cloud credentials are not set up correctly."


def load_from_storage(filename: str) -> str | None:
    """Load data from a file in the storage directory."""
    try:
        file_path = CONFIG_DIR / filename
        if file_path.exists():
            data = file_path.read_text().strip()
            if data:
                return data
    except Exception as e:
        st.write(f"Debug: Error loading {filename}: {e}")
    return None


def save_to_storage(filename: str, data: str) -> None:
    """Save data to a file in the storage directory."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        file_path = CONFIG_DIR / filename
        file_path.write_text(data)
        # Ensure only user can read/write the file
        file_path.chmod(0o600)
    except Exception as e:
        st.write(f"Debug: Error saving {filename}: {e}")


def _api_response_callback(
    request: httpx.Request,
    response: httpx.Response | object | None,
    error: Exception | None,
    tab: DeltaGenerator,
    response_state: dict[str, tuple[httpx.Request, httpx.Response | object | None]],
):
    """
    Handle an API response by storing it to state and rendering it.
    """
    response_id = datetime.now().isoformat()
    response_state[response_id] = (request, response)
    if error:
        _render_error(error)
    _render_api_response(request, response, response_id, tab)


def _tool_output_callback(
    tool_output: ToolResult, tool_id: str, tool_state: dict[str, ToolResult], context
):
    """Handle a tool output by storing it to state and rendering it."""
    tool_state[tool_id] = tool_output
    _render_message(tool_output, Sender.TOOL, context)


def _render_api_response(
    request: httpx.Request,
    response: httpx.Response | object | None,
    response_id: str,
    tab: DeltaGenerator,
):
    """Render an API response to a streamlit tab"""
    with tab:
        with st.expander(f"Request/Response ({response_id})"):
            newline = "\n\n"
            st.markdown(
                f"`{request.method} {request.url}`{newline}{newline.join(f'`{k}: {v}`' for k, v in request.headers.items())}"
            )
            st.json(request.read().decode())
            st.markdown("---")
            if isinstance(response, httpx.Response):
                st.markdown(
                    f"`{response.status_code}`{newline}{newline.join(f'`{k}: {v}`' for k, v in response.headers.items())}"
                )
                st.json(response.text)
            else:
                st.write(response)


def _render_error(error: Exception):
    if isinstance(error, RateLimitError):
        body = "You have been rate limited."
        if retry_after := error.response.headers.get("retry-after"):
            body += f" **Retry after {str(timedelta(seconds=int(retry_after)))} (HH:MM:SS).** See our API [documentation](https://docs.anthropic.com/en/api/rate-limits) for more details."
        body += f"\n\n{error.message}"
    else:
        body = str(error)
        body += "\n\n**Traceback:**"
        lines = "\n".join(traceback.format_exception(error))
        body += f"\n\n```{lines}```"
    save_to_storage(f"error_{datetime.now().timestamp()}.md", body)
    st.error(f"**{error.__class__.__name__}**\n\n{body}", icon=":material/error:")


def stop_and_give_feedback():
    st.session_state.popup = True


def _render_message(
    message: str | BetaContentBlockParam | ToolResult,
    sender: Sender,
    container,
):
    """Convert input from the user or output from the agent to a streamlit message."""
    # streamlit's hotreloading breaks isinstance checks, so we need to check for class names
    is_tool_result = not isinstance(message, str | dict)
    if not message or (
        is_tool_result
        and st.session_state.hide_images
        and not hasattr(message, "error")
        and not hasattr(message, "output")
    ):
        return
    avatar = None
    if sender == Sender.ANTHROPIC:
        avatar = "✏️"
    elif sender == Sender.OPENAI:
        avatar = "✨"
    elif sender == Sender.TOOL:
        avatar = "🔧"
    elif sender == Sender.FEEDBACK:
        avatar = "📝"
    with container:
        with st.chat_message(sender, avatar=avatar):
            if is_tool_result:
                message = cast(ToolResult, message)
                if message.output:
                    if message.__class__.__name__ == "CLIResult":
                        st.code(message.output)
                    else:
                        st.markdown(message.output)
                if message.error:
                    st.error(message.error)
                if message.base64_image and not st.session_state.hide_images:
                    st.image(base64.b64decode(message.base64_image))
            elif isinstance(message, dict):
                if message["type"] == "text":
                    st.write(message["text"])
                elif message["type"] == "tool_use":
                    st.code(f'Tool Use: {message["name"]}\nInput: {message["input"]}')
                else:
                    # only expected return types are text and tool_use
                    raise Exception(f'Unexpected response type {message["type"]}')
            else:
                st.markdown(message)


def _init_report(chat):
    st.session_state.data_handler.set_oai_messages(oai.get_messages())
    create_report(
        st.session_state.data_handler,
        FILE_OUTPUT_DIR,
        FILE_OUTPUT_NAME,
        oai.generate_sus_answers,
    )


main()

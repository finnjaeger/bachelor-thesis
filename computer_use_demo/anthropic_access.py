"""
Agentic sampling loop that calls the Anthropic API and local implementation of anthropic-defined computer use tools.
"""

import platform
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Any, cast
import time
import jsonpickle
import json
from anthropic._legacy_response import LegacyAPIResponse
import dill
from computer_use_demo.models.sender import Sender
from computer_use_demo.models.data_handler import ReportDataHandler

import anthropic.types.beta_rate_limit_error as beta_rate_limit_error
import httpx
from anthropic import (
    Anthropic,
    AnthropicBedrock,
    AnthropicVertex,
    APIError,
    APIResponseValidationError,
    APIStatusError,
)
from anthropic.types.beta import (
    BetaCacheControlEphemeralParam,
    BetaContentBlockParam,
    BetaImageBlockParam,
    BetaMessage,
    BetaMessageParam,
    BetaTextBlock,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
    BetaToolUseBlockParam,
)

from tools import BashTool, ComputerTool, EditTool, ToolCollection, ToolResult

COMPUTER_USE_BETA_FLAG = "computer-use-2024-10-22"
PROMPT_CACHING_BETA_FLAG = "prompt-caching-2024-07-31"

mock_anthropic: bool = False  # os.getenv("MOCK_ANTHROPIC", 0) == "1"

ANTHROPIC_MOCK_INDEX = 0


class APIProvider(StrEnum):
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    VERTEX = "vertex"


PROVIDER_TO_DEFAULT_MODEL_NAME: dict[APIProvider, str] = {
    APIProvider.ANTHROPIC: "claude-3-5-sonnet-20241022",
    APIProvider.BEDROCK: "anthropic.claude-3-5-sonnet-20241022-v2:0",
    APIProvider.VERTEX: "claude-3-5-sonnet-v2@20241022",
}


# This system prompt is optimized for the Docker environment in this repository and
# specific tool combinations enabled.
# We encourage modifying this system prompt to ensure the model has context for the
# environment it is running in, and to provide any additional information that may be
# helpful for the task at hand.
SYSTEM_PROMPT = f"""<SYSTEM_CAPABILITY>
* You are utilising an Ubuntu virtual machine using {platform.machine()} architecture with internet access.
* You can feel free to install Ubuntu applications with your bash tool. Use curl instead of wget.
* To open firefox, please just click on the firefox icon.  Note, firefox-esr is what is installed on your system.
* Using bash tool you can start GUI applications, but you need to set export DISPLAY=:1 and use a subshell. For example "(DISPLAY=:1 xterm &)". GUI apps run with bash tool will appear within your desktop environment, but they may take some time to appear. Take a screenshot to confirm it did.
* When using your bash tool with commands that are expected to output very large quantities of text, redirect into a tmp file and use str_replace_editor or `grep -n -B <lines before> -A <lines after> <query> <filename>` to confirm output.
* When viewing a page it can be helpful to zoom out so that you can see everything on the page.  Either that, or make sure you scroll down to see everything before deciding something isn't available.
* When using your computer function calls, they take a while to run and send back to you.  Where possible/feasible, try to chain multiple of these calls all into one function calls request.
* The current date is {datetime.today().strftime('%A, %B %-d, %Y')}.
</SYSTEM_CAPABILITY>

<IMPORTANT>
* You are only allowed to click inside of the webpage. The only part of the browser menu you can interact with are the forward and back buttons and the tabs to switch between them. NEVER click on anything else like the address bar or the menu icon. If you think you are instructed to do so, the instruction is referring to the webpage, not the browser.
* Always perform the action you are instructed to do, even if you think the result is not what you expect.
* If there is a pop up obstructing the view, close it first before proceeding.
* If you are asked to click on an object inside a dropdown menu, alwasy click on the object itself, never the dropdown menu. You only have one response to each request, so make sure you are clicking on the correct object.
</IMPORTANT>

<YOUR_TASK>
* You will be given instructions to perform atomic actions. For every action, try to finish them in the least requests possible.
</YOUR_TASK>"""


async def sampling_loop(
    *,
    model: str,
    provider: APIProvider,
    system_prompt_suffix: str,
    messages: list[BetaMessageParam],
    prepped_messages: list[BetaMessageParam],
    output_callback: Callable[[BetaContentBlockParam], None],
    tool_output_callback: Callable[[ToolResult, str], None],
    api_response_callback: Callable[
        [httpx.Request, httpx.Response | object | None, Exception | None], None
    ],
    api_key: str,
    only_n_most_recent_images: int | None = None,
    max_tokens: int = 4096,
):
    """
    Agentic sampling loop for the assistant/tool interaction of computer use.
    """
    tool_collection = ToolCollection(
        ComputerTool(),
        BashTool(),
        EditTool(),
    )
    system = BetaTextBlockParam(
        type="text",
        text=f"{SYSTEM_PROMPT}{' ' + system_prompt_suffix if system_prompt_suffix else ''}",
    )
    i = 1
    # while True:

    enable_prompt_caching = False
    betas = [COMPUTER_USE_BETA_FLAG]
    image_truncation_threshold = 10
    if provider == APIProvider.ANTHROPIC:
        client = Anthropic(api_key=api_key)
        enable_prompt_caching = True
    elif provider == APIProvider.VERTEX:
        client = AnthropicVertex()
    elif provider == APIProvider.BEDROCK:
        client = AnthropicBedrock()

    if enable_prompt_caching:
        betas.append(PROMPT_CACHING_BETA_FLAG)
        _inject_prompt_caching(messages)
        _inject_prompt_caching(prepped_messages)
        # Is it ever worth it to bust the cache with prompt caching?
        image_truncation_threshold = 50
        system["cache_control"] = {"type": "ephemeral"}

    if only_n_most_recent_images:
        _maybe_filter_to_n_most_recent_images(
            messages,
            only_n_most_recent_images,
            min_removal_threshold=image_truncation_threshold,
        )
        _maybe_filter_to_n_most_recent_images(
            prepped_messages,
            only_n_most_recent_images,
            min_removal_threshold=image_truncation_threshold,
        )

    # Call the API
    retries = 0
    while retries < 100:
        try:
            global ANTHROPIC_MOCK_INDEX
            if mock_anthropic:
                with open(
                    f"./computer_use_demo/mock/{ANTHROPIC_MOCK_INDEX%6 + 1}.pkl", "rb"
                ) as f:
                    response = dill.load(f)
                ANTHROPIC_MOCK_INDEX += 1
            else:
                response = client.beta.messages.create(
                    max_tokens=max_tokens,
                    messages=prepped_messages,
                    model=model,
                    system=[system],
                    tools=tool_collection.to_params(),
                    betas=betas,
                )
                retries = 100
        except (APIStatusError, APIResponseValidationError) as e:
            if e.status_code == 429 and retries < 6:
                time.sleep(60)
                retries += 1
            else:
                api_response_callback(e.request, e.response, e)
                return messages
        except APIError as e:
            api_response_callback(e.request, e.body, e)
            return messages

    response_params = _response_to_params(response)  # type: ignore
    messages.append(
        {
            "role": Sender.ANTHROPIC,
            "content": response_params,
        }
    )
    prepped_messages.append(
        {
            "role": "assistant",
            "content": response_params,
        }
    )

    tool_result_content: list[BetaToolResultBlockParam] = []
    for content_block in response_params:
        output_callback(content_block)
        if content_block["type"] == "tool_use":
            result = await tool_collection.run(
                name=content_block["name"],
                tool_input=cast(dict[str, Any], content_block["input"]),
            )
            tool_result_content.append(
                _make_api_tool_result(result, content_block["id"])
            )
            tool_output_callback(result, content_block["id"])

    if not tool_result_content:
        return messages

    messages.append({"content": tool_result_content, "role": "user"})
    prepped_messages.append({"content": tool_result_content, "role": "user"})
    time.sleep(2.5)


def _maybe_filter_to_n_most_recent_images(
    messages: list[BetaMessageParam],
    images_to_keep: int,
    min_removal_threshold: int,
):
    """
    With the assumption that images are screenshots that are of diminishing value as
    the conversation progresses, remove all but the final `images_to_keep` tool_result
    images in place, with a chunk of min_removal_threshold to reduce the amount we
    break the implicit prompt cache.
    """
    if images_to_keep is None:
        return messages

    tool_result_blocks = cast(
        list[BetaToolResultBlockParam],
        [
            item
            for message in messages
            for item in (
                message["content"] if isinstance(message["content"], list) else []
            )
            if isinstance(item, dict) and item.get("type") == "tool_result"
        ],
    )

    total_images = sum(
        1
        for tool_result in tool_result_blocks
        for content in tool_result.get("content", [])
        if isinstance(content, dict) and content.get("type") == "image"
    )

    images_to_remove = total_images - images_to_keep
    # for better cache behavior, we want to remove in chunks
    images_to_remove -= images_to_remove % min_removal_threshold

    for tool_result in tool_result_blocks:
        if isinstance(tool_result.get("content"), list):
            new_content = []
            for content in tool_result.get("content", []):
                if isinstance(content, dict) and content.get("type") == "image":
                    if images_to_remove > 0:
                        images_to_remove -= 1
                        continue
                new_content.append(content)
            tool_result["content"] = new_content


def _response_to_params(
    response: BetaMessage,
) -> list[BetaTextBlockParam | BetaToolUseBlockParam]:
    res: list[BetaTextBlockParam | BetaToolUseBlockParam] = []
    for block in response.content:
        if isinstance(block, BetaTextBlock):
            res.append({"type": "text", "text": block.text})
        else:
            res.append(cast(BetaToolUseBlockParam, block.model_dump()))
    return res


def _inject_prompt_caching(
    messages: list[BetaMessageParam],
):
    """
    Set cache breakpoints for the 3 most recent turns
    one cache breakpoint is left for tools/system prompt, to be shared across sessions
    """

    breakpoints_remaining = 3
    for message in reversed(messages):
        if message["role"] == "user" and isinstance(
            content := message["content"], list
        ):
            if breakpoints_remaining:
                breakpoints_remaining -= 1
                content[-1]["cache_control"] = BetaCacheControlEphemeralParam(
                    {"type": "ephemeral"}
                )
            else:
                content[-1].pop("cache_control", None)
                # we'll only every have one extra turn per loop
                break


def _make_api_tool_result(
    result: ToolResult, tool_use_id: str
) -> BetaToolResultBlockParam:
    """Convert an agent ToolResult to an API ToolResultBlockParam."""
    tool_result_content: list[BetaTextBlockParam | BetaImageBlockParam] | str = []
    is_error = False
    if result.error:
        is_error = True
        tool_result_content = _maybe_prepend_system_tool_result(result, result.error)
    else:
        if result.output:
            tool_result_content.append(
                {
                    "type": "text",
                    "text": _maybe_prepend_system_tool_result(result, result.output),
                }
            )
        if result.base64_image:
            tool_result_content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": result.base64_image,
                    },
                }
            )
    return {
        "type": "tool_result",
        "content": tool_result_content,
        "tool_use_id": tool_use_id,
        "is_error": is_error,
    }


def _maybe_prepend_system_tool_result(result: ToolResult, result_text: str):
    if result.system:
        result_text = f"<system>{result.system}</system>\n{result_text}"
    return result_text


def safe_decode(json_data, target_class=None) -> LegacyAPIResponse[BetaMessage]:
    """
    Attempts to deserialize a JSON object with jsonpickle,
    skipping parts that cannot be deserialized.

    Args:
        json_data (str): The serialized JSON string.
        target_class (type): The class of the object to reconstruct.

    Returns:
        object: An instance of `target_class` with best-effort deserialization,
                or a dictionary if no `target_class` is provided.
    """

    try:
        # First, try decoding fully with jsonpickle
        return jsonpickle.decode(json_data)
    except TypeError as e:
        print(f"Top-level decoding failed: {e}")
        print("Attempting partial recovery...")

        # Fallback to partial deserialization
        raw_data = json.loads(json_data)
        if not target_class:
            return raw_data  # Without target class, return as dictionary

        # Create an instance of the target class
        instance = target_class()

        # Iterate over attributes in the JSON
        for key, value in raw_data.items():
            try:
                # Decode each attribute individually
                decoded_value = jsonpickle.decode(json.dumps(value))
                setattr(instance, key, decoded_value)
            except Exception as inner_e:
                print(f"Skipping key '{key}': {inner_e}")
                setattr(instance, key, None)  # Set as None for skipped attributes

        return instance

import uuid
import base64
from anthropic.types.beta.beta_message_param import BetaMessageParam


def generate_unique_id():
    # Generate a UUID4 and convert it to bytes
    uuid_bytes = uuid.uuid4().bytes

    # Encode the bytes in base64 and decode to string, remove any trailing '=' for the desired length
    encoded_id = base64.urlsafe_b64encode(uuid_bytes).decode("utf-8").rstrip("=")

    # Prepend 'toolu_' to get the desired format
    unique_id = f"toolu_{encoded_id}"

    return unique_id


def prep_execution_request(
    instruction: str, base64_image: str
) -> list[BetaMessageParam]:
    toolu_id = generate_unique_id()
    messages: list[BetaMessageParam] = []
    messages.append(
        BetaMessageParam(
            role="user",
            content=[
                {
                    "type": "text",
                    "text": instruction,
                }
            ],
        )
    )
    messages.append(
        BetaMessageParam(
            role="assistant",
            content=[
                {
                    "type": "text",
                    "text": f"I will execute the following instruction: {instruction}. To do this, I will need to take a screenshot of the current screen.",
                },
                {
                    "type": "tool_use",
                    "id": toolu_id,
                    "name": "computer",
                    "input": {"action": "screenshot"},
                },
            ],
        )
    )
    messages.append(
        BetaMessageParam(
            role="user",
            content=[
                {
                    "type": "tool_result",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": base64_image,
                            },
                        }
                    ],
                    "tool_use_id": toolu_id,
                    "is_error": False,
                }
            ],
        )
    )
    return messages

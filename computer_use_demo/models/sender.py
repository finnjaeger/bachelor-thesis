from enum import StrEnum


class Sender(StrEnum):
    USER = "user"
    BOT = "assistant"
    TOOL = "tool"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    FEEDBACK = "feedback"

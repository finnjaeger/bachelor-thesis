from enum import IntEnum

"""
The OAI Rule is an Enum that describes, whether a proposed action violates our rules. As of now, the only 
rule for any action is that any element it is referring to is visible on the screen.
"""


class OaiRule(IntEnum):
    OK = 0
    BROKEN = 1

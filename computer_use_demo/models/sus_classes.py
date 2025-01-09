from enum import StrEnum


class SUSQuestion(StrEnum):
    Q1 = "I think that I would like to use this system frequently."
    Q2 = "I found the system unnecessarily complex."
    Q3 = "I thought the system was easy to use."
    Q4 = "I think that I would need the support of a technical person to be able to use this system."
    Q5 = "I found the various functions in this system were well integrated."
    Q6 = "I thought there was too much inconsistency in this system."
    Q7 = "I would imagine that most people would learn to use this system very quickly."
    Q8 = "I found the system very cumbersome to use."
    Q9 = "I felt very confident using the system."
    Q10 = "I needed to learn a lot of things before I could get going with this system."


class SUSAnswer:
    question: SUSQuestion
    answer: int

    def __init__(self, question, answer=0):
        self.question = question
        self.answer = answer

    def __str__(self):
        return f"{self.question}: {self.answer}"

    def add_answer(self, a: int):
        self.answer = a


# Helper functions
def get_question_by_number(num_str: str) -> SUSQuestion:
    try:
        # Construct the enum name dynamically (e.g., "Q1", "Q2")
        enum_name = f"Q{num_str}"
        # Access the enum member
        return getattr(SUSQuestion, enum_name)
    except AttributeError:
        raise ValueError(f"Invalid question number: {num_str}")

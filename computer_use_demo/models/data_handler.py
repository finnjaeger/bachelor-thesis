from models.sus_classes import SUSAnswer
import pandas as pd


class ReportDataHandler:

    action_data = (
        []
    )  # Contains instructions, reasoning, reflections, and usability notes of the Control AI
    sus_data: list[SUSAnswer] = []  # Contains the SUS answers of the Control AU
    oai_messages = []  # Contains the whole messages of the OpenAI assistant
    current_task_interactions = (
        0  # Contains the number of interactions the user had with the task
    )
    task_interactions = (
        []
    )  # Contains the number of interactions the user had with the task

    def init(self):
        self.action_data = []

    def new_task(
        self,
        task_name: str,
    ):
        self.action_data.append(
            {
                "task_name": task_name,
                "actions": [],
                "feedback": {"status": "", "text": ""},
            }
        )

    # Function will add a new action to the report
    def new_action(
        self,
        action: str,
        additional_info: str = "",
        self_reflection: str = "",
        usability_notes: str = "",
        flag: str = "",
        current_url: str = "",
    ):
        self.action_data[-1]["actions"].append(
            {
                "Action": action,
                "Additional Info": additional_info,
                "Self Reflection": self_reflection,
                "Usability Notes": usability_notes,
                "Flag": flag,
                "Current URL": current_url,
            }
        )

    def get_task_interactions(self) -> pd.DataFrame:
        if self.current_task_interactions > 0:
            self.task_interactions.append(self.current_task_interactions)
            self.current_task_interactions = 0
        # Use a loop to preserve order
        unique_task_names = []
        for action in self.action_data:
            if action["task_name"] not in unique_task_names:
                unique_task_names.append(action["task_name"])
        return pd.DataFrame(
            {"Task Name": unique_task_names, "Interactions": self.task_interactions}
        )

    def increment_task_interactions(self):
        self.current_task_interactions += 1

    def reset_task_interactions(self):
        self.task_interactions.append(self.current_task_interactions)
        self.current_task_interactions = 0

    def reset_sus_data(self):
        self.sus_data = []

    def set_oai_messages(self, messages: list[dict]):
        self.oai_messages = messages

    def get_oai_messages(self):
        return self.oai_messages

    def new_feedback(self, feedback: dict[str, str]):
        self.action_data[-1]["feedback"] = feedback

    # Function will add a new SUS answer to the report
    def new_answer(self, ans: SUSAnswer):
        self.sus_data.append(ans)

    # Function returns the SUS data in a formatted way so it can be put into a DataFrame
    def get_formatted_SUS_data(self) -> list[dict[str, int]]:
        formatted_data = [
            {"Nr": item.question.name, "Question": item.question, "Answer": item.answer}
            for item in self.sus_data
        ]
        return formatted_data

    def get_sus_data(self):
        return self.sus_data

    def get_action_data(self):
        return self.action_data

import pandas as pd
from models.pdf_blueprint import PDF
from models.data_handler import ReportDataHandler
import os


def create_report(
    data_handler: ReportDataHandler,
    output_path: str,
    file_name: str,
    generate_sus_answers,
):

    pdf_path = f"{output_path}/{file_name}.pdf"
    excel_path = f"{output_path}/{file_name}.xlsx"

    generate_sus_answers(data_handler)
    sus_non_formatted = data_handler.get_sus_data()  # For PDF report
    sus_formatted_data = data_handler.get_formatted_SUS_data()  # For Excel report

    conversation_history = data_handler.get_oai_messages()

    # Create a pandas dataframe from the SUS data
    sus_df = pd.DataFrame(sus_formatted_data)

    # Create a pandas DataFrame for the Interactions Count
    interactions_df = data_handler.get_task_interactions()

    # Fetch and process the new action data structure
    tasks_data = data_handler.get_action_data()  # New structure

    # Flatten the nested task structure for Excel report
    flattened_actions = []
    for task in tasks_data:
        task_name = task["task_name"]
        feedback_status = task["feedback"]["status"]
        feedback_text = task["feedback"]["text"]
        for action in task["actions"]:
            # Add task_name to each action
            action_with_task_name = {
                "Task Name": task_name,
                **action,
                "Feedback": feedback_status,
                "Feedback Text": feedback_text,
            }
            flattened_actions.append(action_with_task_name)

    # Create a pandas DataFrame for the flattened actions
    action_columns = [
        "Task Name",  # Added task name as a new column
        "Action",
        "Additional Info",
        "Self Reflection",
        "Usability Notes",
        "Flag",
        "Current URL",
        "Feedback",
        "Feedback Text",
    ]
    df = pd.DataFrame(flattened_actions, columns=action_columns)

    # Create the PDF report and configure the font
    pdf = PDF()
    pdf.add_font("ArialU", "", "./computer_use_demo/fonts/Arial.ttf", uni=True)
    pdf.add_font("ArialU", "B", "./computer_use_demo/fonts/Arial Bold.ttf", uni=True)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    i = 1  # Counter for the action number
    # Iterate over the tasks and actions
    for task in tasks_data:
        task_name = task["task_name"]
        pdf.chapter_title(f"Task: {task_name}")

        for action in task["actions"]:
            # Add action title
            pdf.chapter_title(f"Action {i}: {action['Action']}")

            # Add additional information
            if action["Additional Info"]:
                pdf.chapter_body(f"Additional Info: {action['Additional Info']}")

            # Add self-reflection
            if action["Self Reflection"]:
                pdf.chapter_body(f"Self Reflection: {action['Self Reflection']}")

            # Add usability notes
            if action["Usability Notes"]:
                pdf.chapter_body(f"Usability Notes: {action['Usability Notes']}")

            # Add flag
            if action["Flag"]:
                pdf.chapter_body(f"Flag: {action['Flag']}")

            # Add current URL
            if action["Current URL"]:
                pdf.chapter_body(f"Current URL: {action['Current URL']}")

            i += 1

            # Add image if a base64 string is provided
            # if action["Initial Situation"]:
            #     pdf.chapter_body("Initial Situation:")
            #     pdf.add_image(action["Initial Situation"], width=120
        pdf.chapter_title(
            f"Feedback: {task['feedback']['status']} -> {task['feedback']['text']}"
        )

    # Add SUS questions and answers
    pdf.add_page()  # Add a new page for SUS questions
    pdf.chapter_title("System Usability Scale (SUS) Responses")

    for sus_entry in sus_non_formatted:
        question_name = sus_entry.question.name
        statement = sus_entry.question.value
        rating = sus_entry.answer

        # Add each SUS question, statement, and response to the PDF
        pdf.chapter_body(f"{question_name}: {statement}")
        pdf.chapter_body(f"Rating: {rating}")
        pdf.ln(5)  # Add some spacing after each entry

    for idx, message in enumerate(conversation_history, 1):
        role = message["role"].capitalize()
        content = message["content"]

        pdf.chapter_title(f"Message {idx}: {role}")

        # Check if content is a string
        if isinstance(content, str):
            pdf.chapter_body(content)
        # Check if content is a list of dictionaries
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text", "")
                    pdf.chapter_body(text)
        else:
            pdf.chapter_body("Unsupported content format.")

    try:
        # Check and remove the file if it exists
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

        if os.path.exists(excel_path):
            os.remove(excel_path)

        # Generate and save the PDF
        pdf.output(pdf_path)
        print(f"Report saved as PDF: {pdf_path}")

        # Save the data to Excel
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Action Data", index=False)
            sus_df.to_excel(writer, sheet_name="SUS Responses", index=False)
            interactions_df.to_excel(
                writer, sheet_name="Interactions Count", index=False
            )

    except OSError as e:
        print(f"Error writing to file: {e}")

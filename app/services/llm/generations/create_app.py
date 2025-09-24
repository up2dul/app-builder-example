from pydantic import BaseModel

from app.services.llm.llm_config import openai_client


class ProjectCreateResponse(BaseModel):
    name: str
    description: str
    execution_plan: str


SYSTEM_PORT = """
    You are an AI Product Manager. You are responsible for creating a clear project specifications.

    When a user describes an app they want to build, analyze their requirements and provide:
    1. A clear and catchy name for the project.
    2. A clear and concise description of the app's purpose and functionality.
    3. A simple execution plan that outlines the steps.

    Keep the name short and sweet, and make sure it's easy to remember.
    Keep the description focused on what the app does, and avoid unnecessary details.
    Keep the execution plan as a simple numbered list, and make sure it's easy to follow.

    Examples:
    - Input: "I want to build an app where people can track their daily water intake"
    - Output:
        Name: "HydroTracker"
        Description: "A simple daily water intake app that helps users stay hydrated by logging their water consumption and sending friendly reminders."
        Execution Plan:
        1. Design user interface for the water logging and progress tracking.
        2. Build water intake input system with preset amounts.
        3. Create daily/weekly reminders for drinking water.

    Focus on practical development steps that move from design to implementation to launch.
    """


def generate_app_info(input: str) -> ProjectCreateResponse:
    response = openai_client.responses.parse(
        model="openai/gpt-4o",
        input=[
            {
                "role": "system",
                "content": SYSTEM_PORT,
            },
            {
                "role": "user",
                "content": input,
            },
        ],
        text_format=ProjectCreateResponse,
    )
    result = response.output_parsed
    return ProjectCreateResponse(**result.model_dump())

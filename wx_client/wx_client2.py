import os
import asyncio
import warnings
from dotenv import load_dotenv
from typing import Annotated, Literal
from typing_extensions import TypedDict
from pydantic import BaseModel, Field

from ibm_watsonx_ai import APIClient, Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

# Load environment variables
load_dotenv()

# Initialize Watsonx credentials and model
credentials = Credentials(
    url="https://us-south.ml.cloud.ibm.com",
    api_key=os.getenv("IBMCLOUD_API_KEY"),
)

client = APIClient(credentials)

model = ModelInference(
    model_id="ibm/granite-3-3-8b-instruct",
    api_client=client,
    project_id=os.getenv("PROJECT_ID"),
    params={"max_new_tokens": 1000},
)

classifier_model = ModelInference(
    model_id="meta-llama/llama-3-2-1b-instruct",
    api_client=client,
    project_id=os.getenv("PROJECT_ID"),
    params={"max_new_tokens": 10},
)

# Suppress specific warning
warnings.filterwarnings(
    "ignore",
    message=r".*Parameters \[max_new_tokens\] is/are not recognized and will be ignored.*",
    category=UserWarning,
    module="ibm_watsonx_ai.foundation_models.inference.base_model_inference",
)


# Output schema
class MessageClassifier(BaseModel):
    message_type: Literal["powervs", "schematics"] = Field(
        ..., description="Classify if the message is about schematics or powervs workspaces."
    )


# State definition
class State(TypedDict):
    messages: Annotated[list, add_messages]
    message_type: str | None
    powervs_context: str | None


# Message classification
# async def classify_message(state: dict) -> dict:
#     last_message = state["messages"][-1].content  # Fixed: use attribute access
#     # print(last_message)

#     prompt = f"""
#         Classify user message as powervs or schematics.
#         Do not return anything else. Do not give examples, sentences, punctuation, line breaks or explanations.
#         Classify as 'powervs' if it mentions: power, power virtual server, powervs, POWER, or pvs.
#         Classify as 'schematics' if it mentions: deployment, schematics, sch, DA, DAs, das, or da.
#         User message: {last_message}
#         "Response:"
#         """

#     response = classifier_model.generate_text(prompt=prompt)
#     classification = response.strip().lower()
#     print(f"classification: {classification}")

#     sch_list = ["schematics", "sch", "DA", "da", "deployments"]

#     if classification == "powervs" or classification == "schematics":
#         return {"message_type": classification}
#     else:
#         print("Inside Fallback")
#         return {"message_type": "powervs"}  # Fallback


# Message classification - workaround. Above function not working.
def classify_message(state: dict) -> str:
    """
    Classify a user message as 'powervs' or 'schematics'.

    - Classify as 'powervs' if it mentions: power, power virtual server, powervs, POWER, or pvs.
    - Classify as 'schematics' if it mentions: deployment, schematics, sch, DA, DAs, das, or da.

    Returns:
        str: 'powervs' or 'schematics'
    """
    last_message = state["messages"][-1].content
    message_lower = last_message.lower()

    schematics_keywords = {"deployment", "schematics", "sch", "da", "das"}

    if any(keyword in message_lower for keyword in schematics_keywords):
        return {"message_type": "schematics"}
    else:
        return {"message_type": "powervs"}


# Router node
def router(state: State) -> dict:
    return {"next": state.get("message_type", "powervs")}


# PowerVS agent
async def powervs_agent(state: State) -> dict:
    last_message = state["messages"][-1]
    print("PowerVS Agent called.")

    try:
        context = await call_mcp_tool("fetch_powervs_workspaces")
    except Exception as e:
        context = f"Error fetching powervs workspaces: {str(e)}"

    messages = [
        {
            "role": "system",
            "content": f"""
            You are a knowledgeable and courteous AI assistant that helps users with IBM Cloud Power Virtual Server (PowerVS) services.
            Use the following context to help answer questions:
            {context}
            """,
        },
        {"role": "user", "content": last_message.content},
    ]

    reply = await model.achat(messages)
    return {"messages": [{"role": "assistant", "content": reply["choices"][0]["message"]["content"]}]}


# Schematics agent
async def schematics_agent(state: State) -> dict:
    last_message = state["messages"][-1]
    print("Schematics Agent called.")

    try:
        context = await call_mcp_tool("fetch_schematics_workspaces")
    except Exception as e:
        context = f"Error fetching schematics workspaces: {str(e)}"

    messages = [
        {
            "role": "system",
            "content": f"""
            You are a knowledgeable and courteous AI assistant that helps users with IBM Cloud Schematics (platform automation) services.
            Use the following context to help answer questions:
            {context}
            """,
        },
        {"role": "user", "content": last_message.content},
    ]

    reply = await model.achat(messages)
    return {"messages": [{"role": "assistant", "content": reply["choices"][0]["message"]["content"]}]}


# Tool invocation
async def call_mcp_tool(tool_name: str) -> str:
    url = "http://127.0.0.1:8000/sse"
    async with sse_client(url) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            response = await session.call_tool(name=tool_name)
            return response.content


# Build the graph
graph_builder = StateGraph(State)
graph_builder.add_node("classifier", classify_message)
graph_builder.add_node("router", router)
graph_builder.add_node("powervs", powervs_agent)
graph_builder.add_node("schematics", schematics_agent)

graph_builder.add_edge(START, "classifier")
graph_builder.add_edge("classifier", "router")
graph_builder.add_conditional_edges("router", lambda state: state.get("next"), {"powervs": "powervs", "schematics": "schematics"})
graph_builder.add_edge("powervs", END)
graph_builder.add_edge("schematics", END)

graph = graph_builder.compile()


# Chat loop
async def run_chatbot():
    state = {"messages": [], "message_type": None}

    while True:
        user_input = input("^_^ You      : ")
        if user_input.lower() == "exit":
            print("Bye!")
            break

        state["messages"].append({"role": "user", "content": user_input})
        state = await graph.ainvoke(state)

        if state.get("messages"):
            last_message = state["messages"][-1]
            print(f"o_o Assistant: {last_message.content}")


if __name__ == "__main__":
    asyncio.run(run_chatbot())

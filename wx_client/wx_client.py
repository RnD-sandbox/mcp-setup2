from ibm_watsonx_ai import APIClient
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from typing import Annotated, Literal
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
import asyncio, os, warnings

# Load environment variables
load_dotenv()

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

# Suppress specific warning about json_schema fallback
warnings.filterwarnings(
    "ignore",
    message=r".*Parameters \[max_new_tokens\] is/are not recognized and will be ignored.*",
    category=UserWarning,
    module="ibm_watsonx_ai.foundation_models.inference.base_model_inference",
)


# Define structured output schema
class MessageClassifier(BaseModel):
    message_type: Literal["powervs", "schematics"] = Field(
        ..., description="Classify if the message is about schematics or powervs workspaces."
    )


# Define state
class State(TypedDict):
    messages: Annotated[list, add_messages]
    message_type: str | None
    powervs_context: str | None


async def classify_message(state: dict):
    last_message = state["messages"][-1]

    prompt = (
        "You are a classifier. Classify the following sentence as 'powervs' or 'schematics' for agent selection.\n"
        "Respond with exactly one word: either 'powervs' or 'schematics'. No punctuation, no line breaks, no explanations.\n"
        "Classify as 'powervs' if it mentions: power, power virtual server, powervs, POWER, or pvs.\n"
        "Classify as 'schematics' if it mentions: deployment, schematics, sch, DA, DAs, das, or da.\n"
        f"Sentence: {last_message}\n"
        "Response:"
    )

    # Call the model (ensure it's awaited if model is async)
    response = (
        await model.generate_text(prompt=prompt)
        if callable(getattr(model, "generate_text", None))
        and hasattr(model.generate_text, "__call__")
        and hasattr(model.generate_text, "__await__")
        else model.generate_text(prompt=prompt)
    )

    # Normalize and clean response
    classification = response.strip().lower()
    if response.__contains__("powervs"):
        return {"message_type": "powervs"}
    else:
        return {"message_type": "schematics"}

    # if classification == "powervs":
    #     return {"message_type": "powervs"}
    # else:
    #     return {"message_type": "schematics"}

    # prompt = f"""
    #     You are a classifier. Classify the following sentence as 'powervs' or 'schematics' for agent selection.
    #     The response should one token without escape or line breaks character.
    #     Classify it as 'powervs' if it mentions power, power virtual server, powervs, POWER, or pvs.
    #     Classify it as 'schematics' if it mentions deployment, schematics, sch, DA, DAs, das, or da.
    #     Response: {last_message}
    # """

    # # Call the model
    # response = model.generate_text(prompt=prompt)

    # if response.__contains__("powervs"):
    #     return {"message_type": "powervs"}
    # else:
    #     return {"message_type": "schematics"}


# Router node
def router(state: State):
    return {"next": state.get("message_type", "powervs")}


# PowerVS agent node
async def powervs_agent(state: State):
    last_message = state["messages"][-1]
    print("PowerVS Agent called.")

    try:
        context = await call_mcp_tool(tool_name="fetch_powervs_workspaces")
    except Exception as e:
        context = f"Error fetching powervs workspaces: {str(e)}"

    messages = [
        {
            "role": "system",
            "content": f"""
            You are a knowledgeable and courteous AI assistant that helps users with IBM Cloud Power Virtual Server(PowerVS) services. 
            Respond clearly, professionally, and with a helpful tone. If information is missing or an error occurs, 
            acknowledge it briefly and offer a suggested next step or alternative.
            Use the following context to help answer questions:
            {context}
            """,
        },
        {"role": "user", "content": last_message.content},
    ]

    reply = await model.achat(messages)
    # print(reply["choices"][0]["message"]["content"])
    return {"messages": [{"role": "assistant", "content": reply["choices"][0]["message"]["content"]}]}


# Schematics agent node
async def schematics_agent(state: State):
    last_message = state["messages"][-1]
    print("Schematics Agent called.")

    try:
        context = await call_mcp_tool(tool_name="fetch_schematics_workspaces")
    except Exception as e:
        context = f"Error fetching schematics workspaces: {str(e)}"

    messages = [
        {
            "role": "system",
            "content": f"""
            You are a knowledgeable and courteous AI assistant that helps users with IBM Cloud schematics(platform automation) services. 
            Respond clearly, professionally, and with a helpful tone. If information is missing or an error occurs, 
            acknowledge it briefly and offer a suggested next step or alternative.
            Use the following context to help answer questions:
            {context}
            """,
        },
        {"role": "user", "content": last_message.content},
    ]

    reply = await model.achat(messages)
    # print(reply["choices"][0]["message"]["content"])
    return {"messages": [{"role": "assistant", "content": reply["choices"][0]["message"]["content"]}]}


async def call_mcp_tool(tool_name: str):
    url = "http://127.0.0.1:8000/sse"
    async with sse_client(url) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            response = await session.call_tool(name=tool_name)
            # print("Tool response:", response.content)
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


# Chat loop using SSE
async def run_chatbot():
    state = {"messages": [], "message_type": None}

    while True:
        user_input = input("^_^ You      : ")
        if user_input == "exit":
            print("Bye!")
            break

        state["messages"] = state.get("messages", []) + [{"role": "user", "content": user_input}]

        state = await graph.ainvoke(state)

        if state.get("messages") and len(state["messages"]) > 0:
            last_message = state["messages"][-1]
            print(f"o_o Assistant: {last_message.content}")


if __name__ == "__main__":
    # print(model.generate(prompt))
    # print(model.generate_text(prompt))
    asyncio.run(run_chatbot())

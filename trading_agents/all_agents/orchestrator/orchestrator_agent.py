import os
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from IPython.display import Image, display
from dotenv import load_dotenv
load_dotenv()
# After app = graph.compile()
# 1. State definition (graph passes a dict)
def model_state(q):
    return {"query": q, "response": None}

# 2. LLM node: runs the orchestrator agent
llm = ChatOpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
    model="openai/gpt-4o-mini",   # choose any OpenRouter model
)
def orchestrator_node(state):

    system_prompt = "You are the orchestrator agent. Answer clearly."
    user_prompt = state["query"]

    out = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])

    state["response"] = out.content
    return state

# 3. Build graph with one node → END
graph = StateGraph(dict)
graph.add_node("orchestrator", orchestrator_node)
graph.set_entry_point("orchestrator")
graph.add_edge("orchestrator", END)

app = graph.compile()
with open("graph.png", "wb") as f:
    f.write(app.get_graph(xray=True).draw_mermaid_png())
# 4. Simple function to run query
def run_orchestrator(query):
    state = model_state(query)
    result = app.invoke(state)
    return result["response"]


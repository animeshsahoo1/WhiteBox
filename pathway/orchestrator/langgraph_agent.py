"""
LangGraph + Mem0 Strategist Agent with MCP Server Integration

A production-ready ReAct agent that:
- Connects to MCP server using official langchain-mcp-adapters
- Auto-discovers all MCP tools (backtesting, risk assessment, search, reports)
- Uses Mem0 for persistent memory (user preferences, past interactions)
- LangGraph for conversation state management
- Supports multi-turn conversations with context

Usage:
    python langgraph_agent.py
    python langgraph_agent.py --test
"""

import asyncio
import os
from typing import Annotated, Literal, TypedDict, List
from datetime import datetime

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode

# Load environment variables
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://openrouter.ai/api/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL_AGENT", "openai/gpt-4o-mini")
MCP_HOST = os.getenv("MCP_SERVER_HOST", "mcp-server")  # Docker service name
MCP_PORT = int(os.getenv("MCP_SERVER_PORT", 9004))

# Redis config for Mem0
MEM0_REDIS_HOST = os.getenv("MEM0_REDIS_HOST", "redis")
MEM0_REDIS_PORT = int(os.getenv("MEM0_REDIS_PORT", 6379))

# Fix host for local development
if MCP_HOST == "0.0.0.0":
    MCP_HOST = "localhost"

MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}/mcp"


# ============================================================================
# MEM0 MEMORY SETUP (with Redis persistence)
# ============================================================================

_memory = None  # Lazy loaded

def get_mem0():
    """Initialize Mem0 memory with Redis persistence (lazy loading)."""
    global _memory
    
    if _memory is not None:
        return _memory
    
    try:
        from mem0 import Memory
        
        config = {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "gpt-4o-mini",
                    "api_key": OPENAI_API_KEY,
                    "openai_base_url": OPENAI_API_BASE
                }
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small",
                    "api_key": OPENAI_API_KEY,
                    "openai_base_url": OPENAI_API_BASE
                }
            },
            # Redis persistence (uses existing pathway-redis container)
            "vector_store": {
                "provider": "redis",
                "config": {
                    "redis_url": f"redis://{MEM0_REDIS_HOST}:{MEM0_REDIS_PORT}"
                }
            }
        }
        
        _memory = Memory.from_config(config)
        print(f"✅ Mem0 memory initialized (Redis: {MEM0_REDIS_HOST}:{MEM0_REDIS_PORT})")
        return _memory
        
    except ImportError:
        print("⚠️  Mem0 not installed. Running without memory.")
        print("   Install with: pip install mem0ai")
        return None
    except Exception as e:
        print(f"⚠️  Mem0 initialization failed: {e}")
        return None


# ============================================================================
# MCP TOOLS LOADER (Official langchain-mcp-adapters)
# ============================================================================

async def load_mcp_tools():
    """Load tools from MCP server using official langchain-mcp-adapters."""
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
        
        # Create client configuration
        client = MultiServerMCPClient({
            "trading": {
                "url": MCP_URL,
                "transport": "streamable_http",
            }
        })
        
        # Load all tools from the MCP server
        tools = await client.get_tools()
        
        print(f"✅ Loaded {len(tools)} tools from MCP server at {MCP_URL}")
        for tool in tools:
            print(f"   📦 {tool.name}")
        
        return tools, client
        
    except ImportError:
        print("❌ langchain-mcp-adapters not installed!")
        print("   Install with: pip install langchain-mcp-adapters")
        raise
    except Exception as e:
        print(f"❌ Failed to connect to MCP server at {MCP_URL}")
        print(f"   Error: {e}")
        print("\n   Make sure MCP server is running: python server.py")
        raise


# ============================================================================
# LANGGRAPH STATE
# ============================================================================

class AgentState(TypedDict):
    """State for the Strategist agent."""
    messages: Annotated[list, add_messages]
    user_id: str
    memory_context: str


# ============================================================================
# MEMORY HELPERS
# ============================================================================

def get_memory_context(user_id: str, query: str) -> str:
    """Retrieve relevant memories for the user."""
    mem = get_mem0()
    if not mem:
        return ""
    
    try:
        results = mem.search(query, user_id=user_id, limit=5)
        
        if not results or not results.get("results"):
            return ""
        
        memories = results["results"]
        if not memories:
            return ""
        
        memory_text = "\n".join([f"- {m.get('memory', '')}" for m in memories])
        return f"\n\nUser's relevant history and preferences:\n{memory_text}"
    except Exception as e:
        print(f"Memory retrieval error: {e}")
        return ""


def save_to_memory(user_id: str, messages: list):
    """Save conversation insights to memory."""
    mem = get_mem0()
    if not mem:
        return
    
    try:
        if len(messages) < 2:
            return
        
        recent = messages[-4:] if len(messages) >= 4 else messages
        
        formatted = []
        for msg in recent:
            if isinstance(msg, HumanMessage):
                formatted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage) and not msg.tool_calls:
                # Only save final responses, not tool calls
                content = msg.content
                if content and len(content) > 10:  # Skip very short responses
                    formatted.append({"role": "assistant", "content": content})
        
        if len(formatted) >= 2:
            mem.add(formatted, user_id=user_id)
            print(f"💾 Saved conversation to memory for user: {user_id}")
    except Exception as e:
        print(f"Memory save error: {e}")


# ============================================================================
# SYSTEM PROMPT
# ============================================================================

SYSTEM_PROMPT = """You are an expert trading assistant with access to powerful backtesting and analysis tools.

Your capabilities:
1. **Backtesting**: List, search, run, and compare trading strategies
2. **Risk Assessment**: Evaluate strategy risks at different levels (no-risk, neutral, aggressive)
3. **Web Search**: Find relevant trading information and research
4. **Reports**: Generate facilitator and bull/bear debate reports for stocks

Available Tools:
- list_strategies: Get all available trading strategies
- search_strategies: Search for strategies by description
- find_best_strategy: Find top strategy by metric (sharpe_ratio, total_return, etc.)
- run_backtest: Execute a backtest for a strategy
- compare_strategies: Compare multiple strategies side by side
- assess_risk_all_tiers / assess_single_risk_tier: Risk assessment
- smart_search: Web search for trading info
- get_facilitator_report / get_bull_bear_report: Stock analysis reports

Guidelines:
- Be helpful, accurate, and proactive in suggesting analyses
- When users ask about strategies, offer to backtest or compare them
- Explain trading concepts clearly for all skill levels
- Always consider risk management in your recommendations
- Use the tools available to provide data-driven insights
- If a tool fails, explain what happened and suggest alternatives
{memory_context}

Current date: {date}
"""


# ============================================================================
# LANGGRAPH AGENT FACTORY
# ============================================================================

# Verbose mode for tool logging
VERBOSE_TOOLS = os.getenv("VERBOSE_TOOLS", "true").lower() == "true"

def log_tool_call(tool_name: str, tool_input: dict, tool_output: str = None, is_start: bool = True):
    """Log tool calls with timestamps."""
    if not VERBOSE_TOOLS:
        return
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    if is_start:
        print(f"\n🔧 [{timestamp}] TOOL CALL: {tool_name}")
        if tool_input:
            # Truncate long inputs
            input_str = str(tool_input)
            if len(input_str) > 200:
                input_str = input_str[:200] + "..."
            print(f"   📥 Input: {input_str}")
    else:
        # Truncate long outputs
        if tool_output:
            output_str = str(tool_output)
            if len(output_str) > 500:
                output_str = output_str[:500] + "..."
            print(f"   📤 Output: {output_str}")
        print(f"   ✅ [{timestamp}] TOOL COMPLETE: {tool_name}")


class VerboseToolNode(ToolNode):
    """ToolNode wrapper that logs tool calls."""
    
    async def ainvoke(self, state, config=None):
        """Log tools before and after invocation."""
        messages = state.get("messages", [])
        
        # Find tool calls in the last message
        if messages:
            last_msg = messages[-1]
            if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                for tc in last_msg.tool_calls:
                    log_tool_call(tc['name'], tc.get('args', {}), is_start=True)
        
        # Call the actual tool
        result = await super().ainvoke(state, config)
        
        # Log outputs
        result_messages = result.get("messages", [])
        for msg in result_messages:
            if hasattr(msg, 'name') and hasattr(msg, 'content'):
                log_tool_call(msg.name, {}, msg.content, is_start=False)
        
        return result


async def create_strategist_agent():
    """Create the LangGraph Strategist agent with MCP tools."""
    
    # Load tools from MCP server (official adapter)
    tools, mcp_client = await load_mcp_tools()
    
    # Initialize LLM
    llm = ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_API_BASE,
        temperature=0.7
    )
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)
    
    # Create verbose tool node for logging
    tool_node = VerboseToolNode(tools)
    
    # Define agent node
    async def agent_node(state: AgentState) -> dict:
        """Main agent node that processes messages and decides actions."""
        
        user_id = state.get("user_id", "default_user")
        messages = state["messages"]
        
        # Get the last user message for memory context
        last_user_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                last_user_msg = msg.content
                break
        
        # Retrieve memory context
        memory_context = get_memory_context(user_id, last_user_msg)
        
        # Build system prompt with memory
        system = SystemMessage(content=SYSTEM_PROMPT.format(
            memory_context=memory_context,
            date=datetime.now().strftime("%Y-%m-%d")
        ))
        
        # Call LLM with tools
        response = await llm_with_tools.ainvoke([system] + messages)
        
        return {"messages": [response], "memory_context": memory_context}
    
    # Define routing
    def should_continue(state: AgentState) -> Literal["tools", "save_memory"]:
        """Determine if we should call tools or end."""
        messages = state["messages"]
        last_message = messages[-1]
        
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        
        return "save_memory"
    
    # Save memory node
    async def save_memory_node(state: AgentState) -> dict:
        """Save conversation to memory before ending."""
        user_id = state.get("user_id", "default_user")
        save_to_memory(user_id, state["messages"])
        return {}
    
    # Build graph
    builder = StateGraph(AgentState)
    
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_node("save_memory", save_memory_node)
    
    builder.add_edge(START, "agent")
    builder.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "save_memory": "save_memory"
        }
    )
    builder.add_edge("tools", "agent")
    builder.add_edge("save_memory", END)
    
    # Add checkpointer for conversation persistence
    checkpointer = MemorySaver()
    
    # Compile
    graph = builder.compile(checkpointer=checkpointer)
    
    return graph, mcp_client


# ============================================================================
# CHAT INTERFACE CLASS
# ============================================================================

class Strategist:
    """High-level interface for the Strategist agent."""
    
    def __init__(self):
        self.graph = None
        self.mcp_client = None
        self.thread_id = "default"
        self._initialized = False
    
    async def initialize(self):
        """Initialize the agent (connects to MCP server)."""
        if not self._initialized:
            print("\n🔄 Initializing Strategist Agent...")
            self.graph, self.mcp_client = await create_strategist_agent()
            self._initialized = True
            print("✅ Strategist ready!\n")
    
    async def chat(self, message: str, user_id: str = "default_user") -> str:
        """
        Send a message to the agent and get a response.
        
        Args:
            message: User's message
            user_id: Unique user identifier for memory
        
        Returns:
            Agent's response
        """
        if not self._initialized:
            await self.initialize()
        
        config = {
            "configurable": {
                "thread_id": f"{user_id}_{self.thread_id}"
            }
        }
        
        input_state = {
            "messages": [HumanMessage(content=message)],
            "user_id": user_id,
            "memory_context": ""
        }
        
        # Run the graph
        result = await self.graph.ainvoke(input_state, config=config)
        
        # Get the last AI message (non-tool-call)
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and not msg.tool_calls:
                return msg.content
        
        return "I couldn't generate a response. Please try again."
    
    async def stream_chat(self, message: str, user_id: str = "default_user"):
        """
        Stream a response from the agent.
        
        Yields chunks of the response as they're generated.
        """
        if not self._initialized:
            await self.initialize()
        
        config = {
            "configurable": {
                "thread_id": f"{user_id}_{self.thread_id}"
            }
        }
        
        input_state = {
            "messages": [HumanMessage(content=message)],
            "user_id": user_id,
            "memory_context": ""
        }
        
        async for event in self.graph.astream_events(input_state, config=config, version="v2"):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    yield content
    
    def new_conversation(self):
        """Start a new conversation thread."""
        self.thread_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    async def get_user_memories(self, user_id: str) -> List[dict]:
        """Get all memories for a user."""
        mem = get_mem0()
        if not mem:
            return []
        
        try:
            result = mem.get_all(user_id=user_id)
            return result if isinstance(result, list) else []
        except Exception as e:
            print(f"Error getting memories: {e}")
            return []
    
    async def clear_memories(self, user_id: str) -> bool:
        """Clear all memories for a user."""
        mem = get_mem0()
        if mem:
            try:
                mem.delete_all(user_id=user_id)
                return True
            except Exception as e:
                print(f"Error clearing memories: {e}")
        return False


# ============================================================================
# INTERACTIVE CHAT
# ============================================================================

async def interactive_chat():
    """Run an interactive chat session."""
    
    print("=" * 60)
    print("🤖 Strategist (LangGraph + Mem0 + MCP)")
    print("=" * 60)
    print("\nCommands:")
    print("  /new     - Start new conversation")
    print("  /memory  - Show your memories")
    print("  /clear   - Clear your memories")
    print("  /quit    - Exit")
    print("\n" + "=" * 60)
    
    agent = Strategist()
    
    # Initialize agent (connects to MCP server)
    try:
        await agent.initialize()
    except Exception as e:
        print(f"\n❌ Failed to initialize agent: {e}")
        print("\nMake sure:")
        print("  1. MCP server is running: python server.py")
        print("  2. langchain-mcp-adapters is installed: pip install langchain-mcp-adapters")
        return
    
    user_id = input("\nEnter your user ID (or press Enter for 'default'): ").strip()
    if not user_id:
        user_id = "default_user"
    
    print(f"\n👤 Logged in as: {user_id}")
    print("💬 Start chatting! (Type your message and press Enter)\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.lower() == "/quit":
                print("\n👋 Goodbye!")
                break
            
            elif user_input.lower() == "/new":
                agent.new_conversation()
                print("\n🔄 Started new conversation\n")
                continue
            
            elif user_input.lower() == "/memory":
                print("\n📚 Your memories:")
                memories = await agent.get_user_memories(user_id)
                if memories:
                    for i, mem in enumerate(memories, 1):
                        memory_text = mem.get('memory', 'N/A') if isinstance(mem, dict) else str(mem)
                        print(f"  {i}. {memory_text}")
                else:
                    print("  No memories found.")
                print()
                continue
            
            elif user_input.lower() == "/clear":
                success = await agent.clear_memories(user_id)
                if success:
                    print("\n🗑️  Memories cleared\n")
                else:
                    print("\n❌ Could not clear memories\n")
                continue
            
            # Get agent response
            print("\n🤔 Thinking...")
            response = await agent.chat(user_input, user_id=user_id)
            print(f"\n🤖 Agent: {response}\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


# ============================================================================
# TEST FUNCTION
# ============================================================================

async def test_agent():
    """Quick test of the Strategist agent."""
    print("\n🧪 Testing Strategist Agent...\n")
    
    agent = Strategist()
    
    try:
        await agent.initialize()
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        print("\nMake sure:")
        print("  1. MCP server is running: python server.py")
        print("  2. Install: pip install langchain-mcp-adapters langgraph langchain-openai")
        return
    
    # Test 1: List strategies
    print("\n" + "="*50)
    print("Test 1: Asking about strategies...")
    print("="*50)
    response = await agent.chat("What trading strategies are available?", user_id="test_user")
    print(f"\nResponse:\n{response}\n")
    
    # Test 2: Best strategy
    print("\n" + "="*50)
    print("Test 2: Finding best strategy...")
    print("="*50)
    response = await agent.chat("What's the best strategy by Sharpe ratio?", user_id="test_user")
    print(f"\nResponse:\n{response}\n")
    
    print("\n✅ Tests complete!")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        asyncio.run(test_agent())
    else:
        asyncio.run(interactive_chat())

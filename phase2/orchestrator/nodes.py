"""
Node Functions for Strategy Orchestrator LangGraph Workflow

This module contains all the node functions and routing logic for the orchestrator graph.
Each function processes the state and returns updated state or routing decisions.
"""

import json
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from .state import AgentState
from .tools import (
    call_hypothesis_mcp,
    call_risk_analysis_mcp,
    call_strategy_api_search,
    call_strategy_api_backtest,
    web_search_tool,
    llm,
    llm_with_tools,
    TRADING_SYMBOL,
    ORCH_MIN_WIN_RATE,
    ORCH_MIN_SHARPE,
    ORCH_TIME_WINDOW,
    ORCH_STRATEGY_LIMIT,
    ORCH_MAX_WEB_SEARCHES,
    ORCH_MAX_SYNTHESIS_ITERATIONS
)


# ============================================================================
# CLASSIFICATION & ROUTING
# ============================================================================

def classify_query(state: AgentState) -> AgentState:
    """Classify user query into one of five types"""
    print("\n" + "="*50)
    print("NODE: classify_query")
    print("="*50)

    call_risk_analysis_mcp(symbol=TRADING_SYMBOL, strategy={}, risk_levels=["no_risk", "neutral", "aggressive"])
    
    classification_prompt = f"""Classify this user query into exactly ONE category:

User Query: "{state['user_query']}"

Categories:
1. "request_strategy" - User asks for strategies (e.g., "show me momentum strategies", "find RSI strategies")
2. "input_strategy" - User provides a strategy to analyze (e.g., "analyze this strategy: buy when RSI<30", "I want to test MA crossover")
3. "risk_based" - Risk-specific requests (e.g., "give me low-risk strategies")
4. "hypothesis_based" - Current market condition queries (e.g., "what should I trade now")
5. "performance" - Performance-focused queries (e.g., "top performing strategies")

Respond with ONLY the category name, nothing else."""

    response = llm.invoke([HumanMessage(content=classification_prompt)])
    query_type = response.content.strip().lower()
    
    # Validate classification
    valid_types = ["request_strategy", "input_strategy", "risk_based", "hypothesis_based", "performance"]
    if query_type not in valid_types:
        query_type = "request_strategy"  # Default fallback
    
    state["query_type"] = query_type
    state["messages"].append(AIMessage(content=f"[Classified as: {query_type}]"))
    
    return state


def route_after_classification(state: AgentState) -> str:
    """Route based on query type"""
    print("\n" + "="*50)
    print("ROUTER: route_after_classification")
    print(f"Routing to: {'strategy_input' if state['query_type'] == 'input_strategy' else 'is_hypothesis_needed'}")
    print("="*50)
    if state["query_type"] == "input_strategy":
        return "strategy_input"
    else:
        return "is_hypothesis_needed"


# ============================================================================
# STRATEGY EXTRACTION
# ============================================================================

def extract_user_strategy(state: AgentState) -> AgentState:
    """Extract strategy from user input"""
    print("\n" + "="*50)
    print("NODE: extract_user_strategy")
    print("="*50)
    
    extraction_prompt = f"""The user has provided a trading strategy. Extract it into structured format.

User Query: "{state['user_query']}"

Extract the strategy and format as JSON:
{{
  "name": "Strategy name",
  "category": "user",
  "technical_indicators": ["List of indicators"],
  "entry_rules": {{
    "conditions": ["Condition 1", "Condition 2"],
    "logic": "AND | OR"
  }},
  "exit_rules": {{
    "stop_loss_pct": 5.0,
    "take_profit_pct": 10.0,
    "trailing_stop": false
  }}
}}

If the user query doesn't contain a complete strategy, make reasonable assumptions for missing parts.
Respond with ONLY valid JSON, no other text."""

    response = llm.invoke([HumanMessage(content=extraction_prompt)])
    
    try:
        content = response.content.strip()
        # Remove markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        
        strategy = json.loads(content)
        state["user_inputted_strategy"] = strategy
        state["messages"].append(AIMessage(content=f"[Extracted user strategy: {strategy.get('name')}]"))
        
    except Exception as e:
        print(f"Error extracting strategy: {e}")
        state["user_inputted_strategy"] = {}
    
    return state


# ============================================================================
# HYPOTHESIS HANDLING
# ============================================================================

def decide_hypothesis_need(state: AgentState) -> AgentState:
    """Decide if hypothesis is needed for strategy search"""
    print("\n" + "="*50)
    print("NODE: decide_hypothesis_need")
    print("="*50)
    
    decision_prompt = f"""Does this query require current market hypothesis to answer?

User Query: "{state['user_query']}"
Query Type: {state['query_type']}

Answer YES if:
- User asks "what should I trade now"
- User asks for strategies for "current conditions"
- User asks "best strategy given recent events"

Answer NO if:
- User asks for general strategy types (momentum, reversal, etc.)
- User asks for specific indicator strategies
- User asks for performance-based filtering

Respond with ONLY: YES or NO"""

    response = llm.invoke([HumanMessage(content=decision_prompt)])
    need_hypothesis = "yes" in response.content.strip().lower()
    
    state["need_hypothesis"] = need_hypothesis
    state["messages"].append(AIMessage(content=f"[Hypothesis needed: {need_hypothesis}]"))
    
    return state


def route_hypothesis_decision(state: AgentState) -> str:
    """Route based on hypothesis need"""
    print("\n" + "="*50)
    print("ROUTER: route_hypothesis_decision")
    print(f"Routing to: {'need_hypothesis' if state['need_hypothesis'] else 'hypothesis_not_needed'}")
    print("="*50)
    if state["need_hypothesis"]:
        return "need_hypothesis"
    else:
        return "hypothesis_not_needed"


def fetch_hypotheses(state: AgentState) -> AgentState:
    """Fetch current market hypotheses"""
    print("\n" + "="*50)
    print("NODE: fetch_hypotheses")
    print("="*50)
    
    hypotheses = call_hypothesis_mcp()
    state["hypotheses"] = hypotheses
    
    if hypotheses:
        top_hypothesis = hypotheses[0]
        state["messages"].append(AIMessage(
            content=f"[Fetched top hypothesis: {top_hypothesis.get('statement', 'N/A')} - {top_hypothesis.get('time_horizon', 'N/A')} - {top_hypothesis.get('recommended_action', 'N/A')}]"
        ))
    else:
        state["messages"].append(AIMessage(content="[No hypotheses available]"))
    
    return state


# ============================================================================
# STRATEGY SEARCH
# ============================================================================

def build_search_params(state: AgentState) -> AgentState:
    """Build search parameters for Strategy Bank"""
    print("\n" + "="*50)
    print("NODE: build_search_params")
    print("="*50)
    
    # Build context for LLM
    context = {
        "user_query": state["user_query"],
        "query_type": state["query_type"],
        "hypotheses": state.get("hypotheses", [])
    }
    
    param_prompt = f"""Build strategy search parameters from this context:

Context:
{json.dumps(context, indent=2)}

Build a JSON search parameter object:
{{
  "filters": {{
    "technical_indicators": ["RSI", "MACD"],  // If mentioned
    "category": "book | user | llm | all",
    "performance_criteria": {{
      "min_win_rate": {ORCH_MIN_WIN_RATE},
      "min_sharpe_ratio": {ORCH_MIN_SHARPE}
    }},
    "time_window": "{ORCH_TIME_WINDOW} | 90d | 180d",
    "market_conditions": {{
      "volatility": "low | moderate | high | any",
      "trend": "bullish | bearish | sideways | any"
    }}
  }},
  "sort_by": "rank | sharpe | win_rate | total_return",
  "limit": {ORCH_STRATEGY_LIMIT}
}}

Guidelines:
- If hypothesis present, set trend to hypothesis direction
- Default time_window: "{ORCH_TIME_WINDOW}"
- Default sort_by: "rank"
- Only include filters that are relevant
- For general queries, keep filters minimal

Respond with ONLY valid JSON."""

    response = llm.invoke([HumanMessage(content=param_prompt)])
    
    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        
        search_params = json.loads(content)
        state["search_params"] = search_params
        state["messages"].append(AIMessage(content=f"[Built search parameters]"))
        
    except Exception as e:
        print(f"Error building search params: {e}")
        # Fallback to default params
        state["search_params"] = {
            "filters": {"time_window": ORCH_TIME_WINDOW},
            "sort_by": "rank",
            "limit": ORCH_STRATEGY_LIMIT
        }
    
    return state


def search_strategy_bank(state: AgentState) -> AgentState:
    """Search Strategy Bank via FastAPI"""
    print("\n" + "="*50)
    print("NODE: search_strategy_bank")
    print("="*50)
    
    search_params = state.get("search_params", {})
    
    # Call FastAPI endpoint
    search_results = call_strategy_api_search(search_params)
    strategies = search_results.get("results", {}).get("strategies", [])
    
    state["strategies_found"] = strategies
    state["messages"].append(AIMessage(
        content=f"[Found {len(strategies)} strategies in Strategy Bank]"
    ))
    
    return state


# ============================================================================
# WEB SEARCH & SYNTHESIS
# ============================================================================

def decide_web_search_need(state: AgentState) -> AgentState:
    """Decide if web search is needed based on search results"""
    print("\n" + "="*50)
    print("NODE: decide_web_search_need")
    print("="*50)
    
    strategies = state.get("strategies_found", [])
    
    if len(strategies) > 0:
        # We found strategies in the bank, select the top one
        top_strategy = strategies[0]
        state["selected_strategy"] = top_strategy
        state["messages"].append(AIMessage(
            content=f"[Selected top strategy from bank: {top_strategy.get('name')}]"
        ))
    else:
        # No strategies found, we'll need web search
        state["messages"].append(AIMessage(
            content="[No strategies found in bank, will search the web]"
        ))
    
    return state


def route_after_web_search_decision(state: AgentState) -> str:
    """Route after deciding on web search"""
    print("\n" + "="*50)
    print("ROUTER: route_after_web_search_decision")
    print(f"Routing to: {'found_strategy' if state.get('selected_strategy') else 'no_strategy_found'}")
    print("="*50)
    if state.get("selected_strategy"):
        # Found strategy in bank, skip to risk analysis or backtest first
        # Check if it already has backtest results
        return "found_strategy"
    else:
        # No strategy found, perform web search
        return "no_strategy_found"


def synthesize_strategy_from_web(state: AgentState) -> AgentState:
    """Synthesize a strategy using LLM with web search tool"""
    print("\n" + "="*50)
    print("NODE: synthesize_strategy_from_web")
    print("="*50)
    
    # Build context including search params if available
    context_info = {
        "user_query": state["user_query"],
        "query_type": state["query_type"],
        "search_params": state.get("search_params", {}),
        "hypotheses": state.get("hypotheses", [])
    }
    
    max_searches = ORCH_MAX_WEB_SEARCHES  # Maximum number of web searches allowed
    
    state["messages"].append(AIMessage(
        content="[Starting web-based strategy synthesis with search tool]"
    ))
    
    synthesis_prompt = f"""You are tasked with creating a technical trading strategy based on the user's request.

User Query: "{state['user_query']}"

Context:
{json.dumps(context_info, indent=2)}

You have access to a web_search tool. Use it strategically (maximum {max_searches} searches) to find:
1. Technical indicators and their parameters
2. Entry/exit conditions
3. Risk management rules (stop-loss, take-profit)

CRITICAL REQUIREMENTS:
1. DO NOT fabricate or make up strategy details
2. ONLY create a strategy if you find clear, complete information through your searches
3. Each search query should be specific (e.g., "RSI oversold buy signal strategy", "MACD crossover entry rules")
4. After searching, evaluate if you have enough information to create a complete strategy

If you CAN create a valid strategy from your search results, respond with:
{{
  "status": "found",
  "strategy": {{
    "name": "Descriptive strategy name based on search findings",
    "category": "llm",
    "technical_indicators": ["List of specific indicators found"],
    "entry_rules": {{
      "conditions": ["Specific condition 1 from search", "Specific condition 2 from search"],
      "logic": "AND"
    }},
    "exit_rules": {{
      "stop_loss_pct": <number from search or reasonable default>,
      "take_profit_pct": <number from search or reasonable default>,
      "trailing_stop": <true/false>
    }}
  }},
  "search_summary": "Brief summary of what you found and which searches you used"
}}

If you CANNOT find sufficient information after your searches, respond with:
{{
  "status": "not_found",
  "reason": "Specific explanation of what information is missing",
  "searches_performed": ["List of search queries you tried"]
}}

Think step by step:
1. Identify what information you need
2. Perform targeted searches
3. Evaluate if you have complete information
4. Generate the strategy or return not_found

Respond with ONLY valid JSON."""

    messages = [HumanMessage(content=synthesis_prompt)]
    search_count = 0
    
    # Allow the LLM to use tools iteratively
    for iteration in range(ORCH_MAX_SYNTHESIS_ITERATIONS):  # Max iterations to prevent infinite loops
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        
        # Check if the LLM wants to use tools
        if response.tool_calls:
            for tool_call in response.tool_calls:
                if search_count >= max_searches:
                    # Exceeded search limit
                    tool_result = f"Search limit reached ({max_searches} searches). Please provide your final answer based on the information gathered."
                else:
                    # Execute the tool
                    if tool_call["name"] == "web_search":
                        search_query = tool_call["args"]["query"]
                        search_count += 1
                        tool_result = web_search_tool(search_query)
                        state["messages"].append(AIMessage(
                            content=f"[Search {search_count}/{max_searches}: '{search_query}']"
                        ))
                    else:
                        tool_result = "Unknown tool"
                
                # Add tool result to messages
                messages.append(ToolMessage(
                    content=tool_result,
                    tool_call_id=tool_call["id"]
                ))
        else:
            # No more tool calls, LLM has provided final answer
            break
    
    # Extract the final response
    final_response = messages[-1].content if not messages[-1].tool_calls else ""
    
    try:
        # Parse the JSON response
        content = final_response.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        
        result = json.loads(content)
        
        if result.get("status") == "found" and "strategy" in result:
            strategy = result["strategy"]
            state["selected_strategy"] = strategy
            search_summary = result.get("search_summary", "")
            state["messages"].append(AIMessage(
                content=f"[Synthesized strategy: {strategy.get('name')}. {search_summary}]"
            ))
        else:
            # Strategy not found
            state["selected_strategy"] = {}
            reason = result.get("reason", "Insufficient information in search results")
            searches = result.get("searches_performed", [])
            state["messages"].append(AIMessage(
                content=f"[Could not synthesize strategy: {reason}. Searches: {', '.join(searches)}]"
            ))
        
    except Exception as e:
        print(f"Error synthesizing strategy: {e}")
        state["selected_strategy"] = {}
        state["messages"].append(AIMessage(
            content=f"[Error during strategy synthesis: {str(e)}]"
        ))
    
    return state


def route_after_synthesis(state: AgentState) -> str:
    """Route after web synthesis"""
    print("\n" + "="*50)
    print("ROUTER: route_after_synthesis")
    print(f"Routing to: {'strategy_generated' if state.get('selected_strategy') else 'no_valid_strategy'}")
    print("="*50)
    if state.get("selected_strategy"):
        # Strategy was successfully synthesized, backtest it
        return "strategy_generated"
    else:
        # Could not synthesize strategy, generate response explaining why
        return "no_valid_strategy"


# ============================================================================
# BACKTESTING & RISK ANALYSIS
# ============================================================================

def backtest_strategy(state: AgentState) -> AgentState:
    """Backtest the selected strategy via FastAPI"""
    print("\n" + "="*50)
    print("NODE: backtest_strategy")
    print("="*50)
    
    # Determine which strategy to backtest
    if state.get("user_inputted_strategy"):
        strategy = state["user_inputted_strategy"]
    elif state.get("selected_strategy"):
        strategy = state["selected_strategy"]
    else:
        state["messages"].append(AIMessage(content="[No strategy to backtest]"))
        return state
    
    # Call FastAPI endpoint to backtest
    backtest_results = call_strategy_api_backtest(strategy)
    
    state["backtest_results"] = backtest_results
    state["selected_strategy"] = strategy  # Ensure selected_strategy is set
    
    state["messages"].append(AIMessage(
        content=f"[Backtested strategy: {strategy.get('name')}]"
    ))
    
    return state


def analyze_risk(state: AgentState) -> AgentState:
    """Get risk analysis for the selected strategy"""
    print("\n" + "="*50)
    print("NODE: analyze_risk")
    print("="*50)
    
    strategy = state.get("selected_strategy", {})
    
    if not strategy:
        state["messages"].append(AIMessage(content="[No strategy to analyze]"))
        return state
    
    # Call risk analysis MCP for all three risk levels
    risk_result = call_risk_analysis_mcp(
        symbol=TRADING_SYMBOL,
        strategy=strategy,
        risk_levels=["no_risk", "neutral", "aggressive"]
    )

    print("="*20)
    print("Risk Analysis Result:")
    print(json.dumps(risk_result, indent=2))
    print("="*20)
    
    state["risk_analyses"] = risk_result
    state["messages"].append(AIMessage(
        content=f"[Obtained risk analysis for all three tiers]"
    ))
    
    return state


# ============================================================================
# RESPONSE GENERATION
# ============================================================================

def generate_response(state: AgentState) -> AgentState:
    """Generate final response to user"""
    print("\n" + "="*50)
    print("NODE: generate_response")
    print("="*50)
    
    # Build context
    context = {
        "query": state["user_query"],
        "query_type": state["query_type"],
        "strategy": state.get("selected_strategy", {}),
        "backtest_results": state.get("backtest_results", {}),
        "risk_analyses": state.get("risk_analyses", {}),
        "hypotheses": state.get("hypotheses", [])
    }
    
    response_prompt = f"""You are the Strategy Orchestrator. Generate a comprehensive response.

User Query: "{state['user_query']}"

Context:
{json.dumps(context, indent=2)[:4000]}

Instructions:
1. Start with context (hypothesis if available)
2. Present the strategy:
   - Name and description
   - Technical indicators used
   - Entry and exit rules
3. Show backtest results:
   - Key performance metrics (win rate, sharpe ratio, max drawdown)
   - Return statistics
   - Trade statistics
4. Present risk analysis for all three tiers:
   - No-Risk: approval status, recommended params, key concerns
   - Neutral: approval status, recommended params, conviction level
   - Aggressive: approval status, recommended params, upside potential
5. Provide a recommendation based on current market conditions
6. Ask if user wants more details or wants to analyze another strategy

Format:
- Use clear sections with headers
- Use bullet points for metrics
- Be specific with numbers
- Sound professional but conversational

If no strategy was found, explain why and suggest alternatives."""

    response = llm.invoke([HumanMessage(content=response_prompt)])
    final_response = response.content
    
    state["final_response"] = final_response
    state["messages"].append(AIMessage(content=final_response))
    
    return state


def update_memory(state: AgentState) -> AgentState:
    """Update conversation memory"""
    print("\n" + "="*50)
    print("NODE: update_memory")
    print("="*50)
    
    conversation_entry = {
        "user_query": state["user_query"],
        "query_type": state["query_type"],
        "strategy": state.get("selected_strategy", {}).get("name", "N/A"),
        "response_summary": state["final_response"][:200]
    }
    
    if "conversation_history" not in state:
        state["conversation_history"] = []
    
    state["conversation_history"].append(conversation_entry)
    
    # Keep last 5 exchanges
    if len(state["conversation_history"]) > 5:
        state["conversation_history"] = state["conversation_history"][-5:]
    
    return state

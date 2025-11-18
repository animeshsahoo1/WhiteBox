"""
Conversational Interface for Strategy Orchestrator

This module provides a conversational layer that:
1. Engages in natural conversation with users
2. Explains capabilities and features
3. Extracts strategy requirements through dialogue
4. Intelligently decides when to invoke the LangGraph workflow
5. Maintains conversation context and memory
"""

import json
from typing import List, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from .graph import build_graph
from .tools import llm, TRADING_SYMBOL
from config.settings import orchestrator_settings


class ConversationalOrchestrator:
    """
    Conversational wrapper around the Strategy Orchestrator LangGraph.
    
    Handles natural language interaction, capability explanation, and
    intelligent workflow invocation.
    """
    
    def __init__(self):
        """Initialize the conversational orchestrator"""
        self.graph = build_graph()
        self.conversation_history: List[Dict[str, str]] = []
        self.user_preferences: Dict[str, Any] = {}
        self.pending_strategy_request: Dict[str, Any] = {}
        
        # System prompt for conversational mode
        self.system_prompt = f"""You are an AI Investment Strategy Assistant powered by advanced market analysis tools.

Your capabilities include:
1. **Strategy Discovery**: Search through a database of proven trading strategies
2. **Strategy Analysis**: Analyze user-provided trading strategies
3. **Market Hypothesis**: Access current market conditions and trends
4. **Backtesting**: Test strategies against historical data
5. **Risk Assessment**: Evaluate strategies across three risk tiers (No-Risk, Neutral, Aggressive)
6. **Strategy Synthesis**: Create new strategies based on web research when needed

Currently trading: {TRADING_SYMBOL}

Your role in conversation mode:
- Engage naturally and professionally with users
- Ask clarifying questions to understand their needs
- Explain your capabilities when users are unsure
- Extract preferences like risk tolerance, indicators, timeframes
- Guide users toward actionable strategy requests
- Decide when you have enough information to invoke the full strategy workflow

When to invoke the strategy workflow:
- User explicitly asks for strategy recommendations
- User provides a strategy to analyze/backtest
- User asks "what should I trade now" or similar
- You have gathered enough context to make a meaningful analysis

Communication style:
- Professional but conversational
- Clear and concise
- Use bullet points for lists
- Ask one question at a time
- Acknowledge user input before asking next question

Remember: You're having a conversation. Don't rush to invoke the workflow - build rapport and understanding first."""

    def should_invoke_workflow(self, user_message: str, context: Dict[str, Any]) -> bool:
        """
        Decide if we should invoke the LangGraph workflow based on conversation state.
        
        Args:
            user_message: The user's latest message
            context: Current conversation context
            
        Returns:
            True if workflow should be invoked, False to continue conversation
        """
        # Decision prompt for the LLM
        decision_prompt = f"""Based on the conversation, should we invoke the full strategy analysis workflow?

User's latest message: "{user_message}"

Conversation context:
{json.dumps(context, indent=2)}

Invoke workflow (YES) if:
- User explicitly requests strategy recommendations
- User provides a complete strategy to analyze
- User asks "what should I trade now" or similar market-based queries
- You have enough information about user's preferences and goals
- User is ready to see concrete strategy analysis

Continue conversation (NO) if:
- User is asking general questions about capabilities
- User is still exploring options
- You need more information about their preferences
- User wants to chat or understand features better
- User's intent is unclear

Respond with ONLY: YES or NO"""

        response = llm.invoke([
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=decision_prompt)
        ])
        
        decision = response.content.strip().lower()
        return "yes" in decision

    def extract_workflow_query(self, conversation_context: List[Dict[str, str]]) -> str:
        """
        Extract a formatted query for the LangGraph workflow from conversation history.
        
        Args:
            conversation_context: List of conversation exchanges
            
        Returns:
            Formatted query string for the workflow
        """
        # Build context from conversation
        context_summary = "\n".join([
            f"User: {msg['user']}\nAssistant: {msg['assistant']}"
            for msg in conversation_context[-5:]  # Last 5 exchanges
        ])
        
        extraction_prompt = f"""Based on this conversation, create a concise query for our strategy analysis system.

Conversation:
{context_summary}

Extract:
- What type of strategy they want (momentum, reversal, etc.)
- Any specific indicators mentioned
- Risk preferences
- Time horizon
- Whether they're providing a strategy or asking for recommendations

Format as a clear, single query that captures their request.
Example: "Find low-risk RSI strategies for swing trading"
Example: "Analyze my strategy: buy when MACD crosses and RSI < 30"

Respond with ONLY the formatted query, nothing else."""

        response = llm.invoke([HumanMessage(content=extraction_prompt)])
        return response.content.strip()

    def chat(self, user_message: str) -> str:
        """
        Process a user message in conversational mode.
        
        Args:
            user_message: The user's message
            
        Returns:
            Assistant's response
        """
        # Build conversation context
        context = {
            "conversation_history": self.conversation_history[-5:],
            "user_preferences": self.user_preferences,
            "pending_request": self.pending_strategy_request
        }
        
        # Check if we should invoke the workflow
        if self.should_invoke_workflow(user_message, context):
            # Extract the formal query from conversation
            workflow_query = self.extract_workflow_query(self.conversation_history + [
                {"user": user_message, "assistant": ""}
            ])
            
            # Invoke the LangGraph workflow
            response = self.invoke_workflow(workflow_query)
            
            # Update conversation history
            self.conversation_history.append({
                "user": user_message,
                "assistant": response,
                "invoked_workflow": True
            })
            
            return response
        
        else:
            # Continue conversational mode
            messages = [SystemMessage(content=self.system_prompt)]
            
            # Add conversation history
            for exchange in self.conversation_history[-5:]:
                messages.append(HumanMessage(content=exchange["user"]))
                messages.append(AIMessage(content=exchange["assistant"]))
            
            # Add current message
            messages.append(HumanMessage(content=user_message))
            
            # Get conversational response
            response = llm.invoke(messages)
            assistant_message = response.content
            
            # Try to extract user preferences from conversation
            self._extract_preferences(user_message, assistant_message)
            
            # Update conversation history
            self.conversation_history.append({
                "user": user_message,
                "assistant": assistant_message,
                "invoked_workflow": False
            })
            
            return assistant_message

    def invoke_workflow(self, query: str) -> str:
        """
        Invoke the LangGraph strategy analysis workflow.
        
        Args:
            query: The formatted query for analysis
            
        Returns:
            The workflow's final response
        """
        print(f"\n🔄 Invoking strategy workflow with query: '{query}'")
        
        # Initialize state for the graph
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "user_query": query,
            "query_type": "",
            "user_inputted_strategy": {},
            "need_hypothesis": False,
            "hypotheses": [],
            "search_params": {},
            "strategies_found": [],
            "selected_strategy": {},
            "backtest_results": {},
            "web_search_results": [],
            "risk_analyses": {},
            "final_response": "",
            "conversation_history": []
        }
        
        try:
            # Run the graph
            final_state = self.graph.invoke(initial_state)
            
            # Return the final response
            return final_state.get("final_response", "I apologize, but I couldn't complete the analysis. Please try again.")
            
        except Exception as e:
            error_msg = f"I encountered an error during analysis: {str(e)}\n\nPlease try rephrasing your request or ask me for help."
            print(f"❌ Workflow error: {e}")
            import traceback
            traceback.print_exc()
            return error_msg

    def _extract_preferences(self, user_message: str, assistant_message: str):
        """
        Extract and store user preferences from conversation.
        
        Args:
            user_message: User's message
            assistant_message: Assistant's response
        """
        # Use LLM to extract structured preferences
        extraction_prompt = f"""Extract any trading preferences from this conversation exchange:

User: {user_message}
Assistant: {assistant_message}

Look for:
- Risk tolerance (low, moderate, high)
- Preferred indicators (RSI, MACD, MA, etc.)
- Trading style (day trading, swing trading, long-term)
- Time horizon preferences
- Return expectations

If preferences are mentioned, respond with JSON:
{{
  "risk_tolerance": "low|moderate|high",
  "indicators": ["RSI", "MACD"],
  "trading_style": "swing",
  "time_horizon": "30d"
}}

If no clear preferences, respond with: {{}}"""

        try:
            response = llm.invoke([HumanMessage(content=extraction_prompt)])
            content = response.content.strip()
            
            # Parse JSON
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()
            
            preferences = json.loads(content)
            
            # Update stored preferences
            if preferences:
                self.user_preferences.update(preferences)
                
        except Exception as e:
            # Silent fail - preference extraction is optional
            pass

    def get_capabilities_message(self) -> str:
        """
        Get a formatted message explaining the orchestrator's capabilities.
        
        Returns:
            Formatted capabilities message
        """
        return f"""# 🤖 Strategy Orchestrator Capabilities

I'm your AI Investment Strategy Assistant. Here's what I can help you with:

## 📊 Strategy Analysis & Discovery

**1. Find Strategies**
   - Search our database of proven trading strategies
   - Filter by indicators, risk level, performance metrics
   - Get strategies tailored to current market conditions
   
**2. Analyze Your Strategy**
   - Provide your own trading strategy for analysis
   - Get comprehensive backtesting results
   - Receive multi-tier risk assessments
   
**3. Market-Based Recommendations**
   - Ask "what should I trade now?"
   - Get strategies based on current market hypotheses
   - Receive context-aware recommendations

## 🔍 Analysis Features

- **Backtesting**: Test strategies against historical {TRADING_SYMBOL} data
- **Risk Assessment**: Evaluate across 3 tiers (No-Risk, Neutral, Aggressive)
- **Performance Metrics**: Win rate, Sharpe ratio, max drawdown, returns
- **Market Context**: Integration with real-time market analysis

## 💬 How to Interact

**Just talk naturally!** For example:
- "I'm interested in low-risk strategies"
- "Can you explain what indicators you support?"
- "Find me momentum strategies with RSI"
- "Analyze this strategy: buy when RSI < 30, sell when RSI > 70"
- "What should I trade now given market conditions?"

I'll ask clarifying questions and guide you to the best analysis.

**Current trading symbol**: {TRADING_SYMBOL}

What would you like to explore?"""

    def reset_conversation(self):
        """Reset conversation history and preferences"""
        self.conversation_history = []
        self.user_preferences = {}
        self.pending_strategy_request = {}
        print("✅ Conversation reset")


def main():
    """Main conversational interface loop"""
    
    print("=" * 70)
    print("STRATEGY ORCHESTRATOR - Conversational Mode")
    print("=" * 70)
    print("\n💬 Welcome! I'm your AI Investment Strategy Assistant.")
    print("I can help you discover, analyze, and optimize trading strategies.\n")
    print("Type 'help' to see my capabilities")
    print("Type 'reset' to start a new conversation")
    print("Type 'quit' or 'exit' to end\n")
    
    orchestrator = ConversationalOrchestrator()
    
    while True:
        # Get user input
        user_input = input("\n🤔 You: ").strip()
        
        if not user_input:
            continue
        
        # Handle special commands
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye! Happy trading!\n")
            break
        
        if user_input.lower() in ['help', 'capabilities', 'what can you do']:
            print(f"\n{orchestrator.get_capabilities_message()}\n")
            continue
        
        if user_input.lower() == 'reset':
            orchestrator.reset_conversation()
            print("\n💬 Let's start fresh! How can I help you?\n")
            continue
        
        # Process the message
        try:
            print("\n🤖 ", end="", flush=True)
            response = orchestrator.chat(user_input)
            print(response)
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            print("\nPlease try again or type 'help' for assistance.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!\n")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}\n")
        import traceback
        traceback.print_exc()

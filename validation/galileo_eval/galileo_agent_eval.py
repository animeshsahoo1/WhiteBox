"""
Galileo Agent Evaluation Module for ReAct Agents

This module integrates Galileo for evaluating ReAct agents with metrics:
- Tool Selection Quality: Measures how well the agent chooses appropriate tools
- Tool Errors: Tracks and analyzes tool execution failures
- Action Advancement: Evaluates if each action moves toward the goal
- Action Completion: Measures successful completion of intended tasks
- Chain of Thought Reasoning: Evaluates reasoning quality

Installation:
    pip install "galileo[openai]" python-dotenv

Environment Variables (.env):
    GALILEO_API_KEY="your-galileo-api-key"
    OPENAI_API_KEY="your-openai-api-key"

Usage:
    from evaluation.galileo_agent_eval import GalileoAgentEvaluator
    
    evaluator = GalileoAgentEvaluator()
    await evaluator.evaluate_agent_run(agent_trace)
"""

import os
import json
import asyncio
from typing import Dict, List, Any, Optional, TypedDict
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum

from dotenv import load_dotenv

load_dotenv()

# Galileo imports (install with: pip install "galileo[openai]")
try:
    from galileo import galileo_context
    from galileo.openai import openai as galileo_openai
    from galileo.config import GalileoPythonConfig
    GALILEO_AVAILABLE = True
except ImportError:
    GALILEO_AVAILABLE = False
    print("⚠️  Galileo SDK not installed. Install with: pip install 'galileo[openai]'")

# ============================================================================
# CONFIGURATION
# ============================================================================

GALILEO_API_KEY = os.getenv("GALILEO_API_KEY", "ShUNOUCW49c2xBZEk39VRQe1txIzrCVI_-EJn3gSVZM")
GALILEO_PROJECT_NAME = os.getenv("GALILEO_PROJECT", "react-agent-evaluation")
GALILEO_LOG_STREAM = os.getenv("GALILEO_LOG_STREAM", "agent-traces")

# ============================================================================
# DATA STRUCTURES FOR AGENT TRACING
# ============================================================================

class ToolCallStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    INVALID_ARGS = "invalid_args"


@dataclass
class ToolCall:
    """Represents a single tool call made by the agent."""
    tool_name: str
    tool_args: Dict[str, Any]
    tool_output: Optional[str] = None
    status: ToolCallStatus = ToolCallStatus.SUCCESS
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            **asdict(self),
            "status": self.status.value
        }


@dataclass
class AgentStep:
    """Represents a single reasoning step in the ReAct loop."""
    step_number: int
    thought: str  # The agent's reasoning
    action: Optional[str] = None  # Tool to call (or None if answering)
    action_input: Optional[Dict] = None
    observation: Optional[str] = None  # Tool output
    is_final_answer: bool = False
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass 
class AgentTrace:
    """Complete trace of an agent execution."""
    trace_id: str
    user_query: str
    steps: List[AgentStep] = field(default_factory=list)
    tool_calls: List[ToolCall] = field(default_factory=list)
    final_answer: Optional[str] = None
    total_tokens: int = 0
    total_time_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# GALILEO EVALUATION METRICS
# ============================================================================

class AgentMetrics:
    """Calculates evaluation metrics for agent performance."""
    
    @staticmethod
    def tool_selection_quality(trace: AgentTrace, expected_tools: List[str] = None) -> Dict:
        """
        Evaluates the quality of tool selection.
        
        Metrics:
        - Relevance: Were the selected tools appropriate for the task?
        - Efficiency: Were unnecessary tools avoided?
        - Ordering: Were tools called in a logical order?
        """
        actual_tools = [tc.tool_name for tc in trace.tool_calls]
        
        metrics = {
            "total_tool_calls": len(actual_tools),
            "unique_tools_used": len(set(actual_tools)),
            "tool_sequence": actual_tools,
        }
        
        # If expected tools provided, calculate precision/recall
        if expected_tools:
            expected_set = set(expected_tools)
            actual_set = set(actual_tools)
            
            true_positives = len(expected_set & actual_set)
            precision = true_positives / len(actual_set) if actual_set else 0
            recall = true_positives / len(expected_set) if expected_set else 0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            
            metrics.update({
                "expected_tools": expected_tools,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "unnecessary_tools": list(actual_set - expected_set),
                "missing_tools": list(expected_set - actual_set)
            })
        
        return metrics
    
    @staticmethod
    def tool_error_analysis(trace: AgentTrace) -> Dict:
        """
        Analyzes tool execution errors.
        
        Metrics:
        - Error rate: Percentage of tool calls that failed
        - Error types: Distribution of error types
        - Recovery: Did the agent recover from errors?
        """
        total_calls = len(trace.tool_calls)
        if total_calls == 0:
            return {"error_rate": 0, "total_calls": 0}
        
        errors = [tc for tc in trace.tool_calls if tc.status != ToolCallStatus.SUCCESS]
        error_types = {}
        
        for tc in errors:
            error_type = tc.status.value
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        return {
            "total_calls": total_calls,
            "successful_calls": total_calls - len(errors),
            "failed_calls": len(errors),
            "error_rate": len(errors) / total_calls,
            "error_types": error_types,
            "error_details": [
                {
                    "tool": tc.tool_name,
                    "status": tc.status.value,
                    "message": tc.error_message
                }
                for tc in errors
            ]
        }
    
    @staticmethod
    def action_advancement(trace: AgentTrace) -> Dict:
        """
        Evaluates if each action moves toward the goal.
        
        Metrics:
        - Progress score: How much each step advanced toward the goal
        - Redundancy: Were any actions repeated unnecessarily?
        - Loops: Did the agent get stuck in loops?
        """
        steps = trace.steps
        if not steps:
            return {"advancement_score": 0, "redundancy_score": 0}
        
        # Check for repeated actions
        action_sequence = [(s.action, str(s.action_input)) for s in steps if s.action]
        unique_actions = set(action_sequence)
        redundancy = 1 - (len(unique_actions) / len(action_sequence)) if action_sequence else 0
        
        # Check for loops (same action repeated consecutively)
        loops = 0
        for i in range(1, len(action_sequence)):
            if action_sequence[i] == action_sequence[i-1]:
                loops += 1
        
        # Calculate advancement score based on reaching final answer
        advancement = 1.0 if trace.final_answer and trace.success else 0.0
        
        # Penalize for too many steps
        step_penalty = max(0, 1 - (len(steps) - 3) * 0.1)  # Optimal around 3 steps
        
        return {
            "total_steps": len(steps),
            "unique_actions": len(unique_actions),
            "redundancy_score": redundancy,
            "loop_count": loops,
            "reached_goal": trace.success,
            "advancement_score": advancement * step_penalty,
            "efficiency_score": step_penalty
        }
    
    @staticmethod
    def action_completion(trace: AgentTrace) -> Dict:
        """
        Measures successful completion of intended tasks.
        
        Metrics:
        - Completion rate: Did the agent complete the task?
        - Answer quality: Was a coherent answer provided?
        - Time efficiency: How long did it take?
        """
        has_final_answer = trace.final_answer is not None and len(trace.final_answer) > 0
        
        return {
            "task_completed": trace.success,
            "has_final_answer": has_final_answer,
            "answer_length": len(trace.final_answer) if has_final_answer else 0,
            "total_time_ms": trace.total_time_ms,
            "total_tokens": trace.total_tokens,
            "steps_to_completion": len(trace.steps),
            "completion_score": 1.0 if trace.success and has_final_answer else 0.0
        }
    
    @staticmethod
    def chain_of_thought_quality(trace: AgentTrace) -> Dict:
        """
        Evaluates the quality of reasoning in the chain of thought.
        
        Metrics:
        - Coherence: Are thoughts logically connected?
        - Grounding: Are thoughts grounded in observations?
        - Relevance: Are thoughts relevant to the task?
        """
        thoughts = [s.thought for s in trace.steps if s.thought]
        
        if not thoughts:
            return {"thought_count": 0, "avg_thought_length": 0}
        
        avg_length = sum(len(t) for t in thoughts) / len(thoughts)
        
        # Check if observations are referenced in subsequent thoughts
        grounding_score = 0
        for i, step in enumerate(trace.steps[1:], 1):
            if step.thought and trace.steps[i-1].observation:
                # Simple check if observation keywords appear in thought
                obs_words = set(trace.steps[i-1].observation.lower().split()[:20])
                thought_words = set(step.thought.lower().split())
                if obs_words & thought_words:
                    grounding_score += 1
        
        grounding_score = grounding_score / (len(trace.steps) - 1) if len(trace.steps) > 1 else 0
        
        return {
            "thought_count": len(thoughts),
            "avg_thought_length": avg_length,
            "grounding_score": grounding_score,
            "thoughts": thoughts
        }


# ============================================================================
# GALILEO INTEGRATION
# ============================================================================

class GalileoAgentEvaluator:
    """
    Integrates with Galileo for comprehensive agent evaluation.
    
    Features:
    - Automatic tracing of agent execution
    - Real-time metric calculation
    - Dashboard visualization via Galileo
    - A/B testing support for agent improvements
    """
    
    def __init__(self, project_name: str = None, log_stream: str = None):
        self.project_name = project_name or GALILEO_PROJECT_NAME
        self.log_stream = log_stream or GALILEO_LOG_STREAM
        self.metrics = AgentMetrics()
        self._initialized = False
        self._project_url = None
        self._log_stream_url = None
        
        if GALILEO_AVAILABLE and GALILEO_API_KEY:
            self._init_galileo()
        else:
            print("⚠️  Running in offline mode (no Galileo connection)")
    
    def _init_galileo(self):
        """Initialize Galileo context."""
        try:
            # Initialize Galileo context with project and log stream
            galileo_context.init(
                project=self.project_name,
                log_stream=self.log_stream
            )
            self._initialized = True
            
            # Get URLs for dashboard
            config = GalileoPythonConfig.get()
            logger = galileo_context.get_logger_instance()
            self._project_url = f"{config.console_url}project/{logger.project_id}"
            self._log_stream_url = f"{self._project_url}/log-streams/{logger.log_stream_id}"
            
            print(f"✅ Galileo initialized for project: {self.project_name}")
            print(f"📊 Dashboard: {self._project_url}")
        except Exception as e:
            print(f"❌ Failed to initialize Galileo: {e}")
            self._initialized = False
    
    def get_galileo_openai_client(self):
        """Get a Galileo-wrapped OpenAI client for automatic tracing."""
        if GALILEO_AVAILABLE:
            return galileo_openai.OpenAI()
        return None
    
    async def evaluate_agent_run(
        self,
        trace: AgentTrace,
        expected_tools: List[str] = None,
        ground_truth: str = None
    ) -> Dict[str, Any]:
        """
        Comprehensive evaluation of an agent run.
        
        Args:
            trace: Complete trace of the agent execution
            expected_tools: Optional list of expected tools for the task
            ground_truth: Optional expected answer for comparison
        
        Returns:
            Dictionary containing all evaluation metrics
        """
        evaluation = {
            "trace_id": trace.trace_id,
            "timestamp": datetime.utcnow().isoformat(),
            "query": trace.user_query,
            "metrics": {
                "tool_selection": self.metrics.tool_selection_quality(trace, expected_tools),
                "tool_errors": self.metrics.tool_error_analysis(trace),
                "action_advancement": self.metrics.action_advancement(trace),
                "action_completion": self.metrics.action_completion(trace),
                "chain_of_thought": self.metrics.chain_of_thought_quality(trace)
            }
        }
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(evaluation["metrics"])
        evaluation["overall_score"] = overall_score
        
        # Add Galileo dashboard URLs if available
        if self._initialized:
            evaluation["galileo_urls"] = {
                "project": self._project_url,
                "log_stream": self._log_stream_url
            }
            # Log to Galileo
            self._log_to_galileo(trace, evaluation, ground_truth)
        
        return evaluation
    
    def _calculate_overall_score(self, metrics: Dict) -> float:
        """Calculate weighted overall score from individual metrics."""
        weights = {
            "tool_selection": 0.25,
            "tool_errors": 0.20,
            "action_advancement": 0.25,
            "action_completion": 0.20,
            "chain_of_thought": 0.10
        }
        
        scores = {
            "tool_selection": metrics["tool_selection"].get("f1_score", 0.8),
            "tool_errors": 1 - metrics["tool_errors"].get("error_rate", 0),
            "action_advancement": metrics["action_advancement"].get("advancement_score", 0),
            "action_completion": metrics["action_completion"].get("completion_score", 0),
            "chain_of_thought": metrics["chain_of_thought"].get("grounding_score", 0.5)
        }
        
        return sum(scores[k] * weights[k] for k in weights)
    
    def _log_to_galileo(
        self,
        trace: AgentTrace,
        evaluation: Dict,
        ground_truth: str = None
    ):
        """Log evaluation results to Galileo using the official SDK."""
        if not self._initialized:
            return
            
        try:
            # Use the Galileo OpenAI client to log the agent trace
            # This automatically captures the conversation
            client = self.get_galileo_openai_client()
            if not client:
                return
            
            # Create a summary message for logging
            summary = f"""
Agent Trace: {trace.trace_id}
Query: {trace.user_query}
Overall Score: {evaluation['overall_score']:.2%}

Tool Calls: {[tc.tool_name for tc in trace.tool_calls]}
Steps: {len(trace.steps)}
Success: {trace.success}

Metrics Summary:
- Tool Selection F1: {evaluation['metrics']['tool_selection'].get('f1_score', 'N/A')}
- Error Rate: {evaluation['metrics']['tool_errors']['error_rate']:.1%}
- Completion: {evaluation['metrics']['action_completion']['completion_score']:.1%}
"""
            
            # Log to Galileo via a completion call (this gets traced)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an agent evaluation logger. Acknowledge the trace."},
                    {"role": "user", "content": summary}
                ],
                max_tokens=50
            )
            
            print(f"📊 Logged to Galileo: {trace.trace_id}")
            
        except Exception as e:
            print(f"⚠️  Failed to log to Galileo: {e}")
    
    def create_trace_from_langgraph(
        self,
        messages: List,
        user_query: str,
        trace_id: str = None
    ) -> AgentTrace:
        """
        Convert LangGraph message history to an AgentTrace.
        
        Args:
            messages: List of LangGraph messages
            user_query: Original user query
            trace_id: Optional trace identifier
        
        Returns:
            AgentTrace object
        """
        from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
        
        trace = AgentTrace(
            trace_id=trace_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f"),
            user_query=user_query
        )
        
        step_number = 0
        current_step = None
        
        for msg in messages:
            if isinstance(msg, AIMessage):
                step_number += 1
                
                # Check for tool calls
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tc in msg.tool_calls:
                        trace.tool_calls.append(ToolCall(
                            tool_name=tc['name'],
                            tool_args=tc.get('args', {})
                        ))
                        
                        current_step = AgentStep(
                            step_number=step_number,
                            thought=msg.content if msg.content else "Calling tool...",
                            action=tc['name'],
                            action_input=tc.get('args', {})
                        )
                        trace.steps.append(current_step)
                else:
                    # Final answer
                    trace.final_answer = msg.content
                    trace.steps.append(AgentStep(
                        step_number=step_number,
                        thought="Generating final answer",
                        is_final_answer=True
                    ))
                    
            elif isinstance(msg, ToolMessage):
                # Update the corresponding tool call and step
                if trace.tool_calls:
                    last_tc = trace.tool_calls[-1]
                    last_tc.tool_output = msg.content
                    
                    # Check for errors
                    if "error" in msg.content.lower():
                        last_tc.status = ToolCallStatus.ERROR
                        last_tc.error_message = msg.content
                
                if current_step:
                    current_step.observation = msg.content
        
        trace.success = trace.final_answer is not None
        return trace


# ============================================================================
# LANGGRAPH CALLBACK FOR AUTOMATIC TRACING
# ============================================================================

class GalileoLangGraphCallback:
    """
    Callback handler for automatic tracing of LangGraph agents.
    
    Usage:
        callback = GalileoLangGraphCallback(evaluator)
        result = await graph.ainvoke(input_state, callbacks=[callback])
        evaluation = await callback.get_evaluation()
    """
    
    def __init__(self, evaluator: GalileoAgentEvaluator):
        self.evaluator = evaluator
        self.trace = None
        self.start_time = None
        self._step_count = 0
    
    def on_agent_start(self, query: str, **kwargs):
        """Called when agent execution starts."""
        self.start_time = datetime.utcnow()
        self.trace = AgentTrace(
            trace_id=datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f"),
            user_query=query
        )
        self._step_count = 0
        print(f"🚀 Agent trace started: {self.trace.trace_id}")
    
    def on_tool_start(self, tool_name: str, tool_args: Dict):
        """Called when a tool execution starts."""
        self._step_count += 1
        self.trace.tool_calls.append(ToolCall(
            tool_name=tool_name,
            tool_args=tool_args
        ))
        print(f"  🔧 Tool call: {tool_name}")
    
    def on_tool_end(self, tool_name: str, tool_output: str, success: bool = True, error: str = None):
        """Called when a tool execution ends."""
        if self.trace.tool_calls:
            last_tc = self.trace.tool_calls[-1]
            if last_tc.tool_name == tool_name:
                last_tc.tool_output = tool_output
                last_tc.status = ToolCallStatus.SUCCESS if success else ToolCallStatus.ERROR
                last_tc.error_message = error
    
    def on_agent_thought(self, thought: str):
        """Called when agent produces a thought."""
        step = AgentStep(
            step_number=self._step_count + 1,
            thought=thought
        )
        self.trace.steps.append(step)
    
    def on_agent_end(self, final_answer: str, success: bool = True, error: str = None):
        """Called when agent execution ends."""
        self.trace.final_answer = final_answer
        self.trace.success = success
        self.trace.error = error
        
        if self.start_time:
            self.trace.total_time_ms = (datetime.utcnow() - self.start_time).total_seconds() * 1000
        
        print(f"✅ Agent trace complete: {self.trace.trace_id}")
    
    async def get_evaluation(
        self,
        expected_tools: List[str] = None,
        ground_truth: str = None
    ) -> Dict:
        """Get comprehensive evaluation of the agent run."""
        if not self.trace:
            return {"error": "No trace available"}
        
        return await self.evaluator.evaluate_agent_run(
            self.trace,
            expected_tools=expected_tools,
            ground_truth=ground_truth
        )


# ============================================================================
# UTILITY: WRAP EXISTING AGENTS
# ============================================================================

def wrap_agent_with_evaluation(agent_fn):
    """
    Decorator to automatically evaluate agent functions.
    
    Usage:
        @wrap_agent_with_evaluation
        async def my_agent(query: str) -> str:
            ...
    """
    evaluator = GalileoAgentEvaluator()
    
    async def wrapped(query: str, *args, **kwargs):
        callback = GalileoLangGraphCallback(evaluator)
        callback.on_agent_start(query)
        
        try:
            result = await agent_fn(query, *args, **kwargs)
            callback.on_agent_end(result, success=True)
        except Exception as e:
            callback.on_agent_end("", success=False, error=str(e))
            raise
        
        # Get and print evaluation
        evaluation = await callback.get_evaluation()
        print(f"\n📊 Evaluation Score: {evaluation.get('overall_score', 0):.2%}")
        
        return result
    
    return wrapped


# ============================================================================
# EXAMPLE USAGE AND TESTS
# ============================================================================

async def example_evaluation():
    """Example of how to use the evaluation system with Galileo."""
    
    print("""
╔═══════════════════════════════════════════════════════════════╗
║          Galileo Agent Evaluation Example                     ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Create sample trace
    trace = AgentTrace(
        trace_id="example_001",
        user_query="What is the current market sentiment for AAPL?"
    )
    
    # Add sample steps
    trace.steps = [
        AgentStep(
            step_number=1,
            thought="I need to get the sentiment report for AAPL",
            action="get_sentiment_report",
            action_input={"symbol": "AAPL"},
            observation="Sentiment: Bullish, Score: 0.72"
        ),
        AgentStep(
            step_number=2,
            thought="I should also check recent news",
            action="get_news_report",
            action_input={"symbol": "AAPL"},
            observation="Recent news shows positive earnings..."
        ),
        AgentStep(
            step_number=3,
            thought="Based on the data, I can provide an answer",
            is_final_answer=True
        )
    ]
    
    # Add sample tool calls
    trace.tool_calls = [
        ToolCall(
            tool_name="get_sentiment_report",
            tool_args={"symbol": "AAPL"},
            tool_output="Sentiment: Bullish, Score: 0.72",
            status=ToolCallStatus.SUCCESS,
            execution_time_ms=150
        ),
        ToolCall(
            tool_name="get_news_report",
            tool_args={"symbol": "AAPL"},
            tool_output="Recent news shows positive earnings...",
            status=ToolCallStatus.SUCCESS,
            execution_time_ms=200
        )
    ]
    
    trace.final_answer = "The current market sentiment for AAPL is bullish with a score of 0.72. Recent news indicates positive earnings reports contributing to this sentiment."
    trace.success = True
    trace.total_time_ms = 500
    
    # Evaluate with Galileo
    # Project and Log Stream will be created automatically if they don't exist
    evaluator = GalileoAgentEvaluator(
        project_name="react-agent-evaluation",
        log_stream="agent-traces"
    )
    
    evaluation = await evaluator.evaluate_agent_run(
        trace,
        expected_tools=["get_sentiment_report", "get_news_report"],
        ground_truth="AAPL sentiment is bullish."
    )
    
    print("\n" + "="*60)
    print("EVALUATION RESULTS")
    print("="*60)
    print(f"\n📊 Overall Score: {evaluation['overall_score']:.2%}\n")
    print(json.dumps(evaluation["metrics"], indent=2))
    
    # Show Galileo dashboard links
    if "galileo_urls" in evaluation:
        print("\n🚀 GALILEO LOG INFORMATION:")
        print(f"🔗 Project   : {evaluation['galileo_urls']['project']}")
        print(f"📝 Log Stream: {evaluation['galileo_urls']['log_stream']}")
    
    return evaluation


if __name__ == "__main__":
    asyncio.run(example_evaluation())

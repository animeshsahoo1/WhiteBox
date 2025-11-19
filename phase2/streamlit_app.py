"""Simple Streamlit interface for conversing with the orchestrator"""

import streamlit as st
import sys
from pathlib import Path
import traceback
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the phase2 directory to the path
sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(
    page_title="Trading Strategy Orchestrator",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Trading Strategy Orchestrator")
st.markdown("Ask me to find, analyze, or refine trading strategies for you.")

# Initialize chat history in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Don't initialize orchestrator at startup - do it lazily on first message
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = None
    st.session_state.settings_loaded = False

def initialize_orchestrator():
    """Initialize the orchestrator lazily"""
    if st.session_state.orchestrator is not None:
        return True
        
    try:
        with st.spinner("🔧 Initializing orchestrator (this may take a moment)..."):
            logger.info("Initializing orchestrator...")
            from config import config
            from orchestrator.conversational_interface import ConversationalOrchestrator
            
            # Validate configuration
            config.validate()
            
            logger.info("Creating ConversationalOrchestrator instance...")
            st.session_state.orchestrator = ConversationalOrchestrator()
            st.session_state.settings_loaded = True
            
            # Store settings from config
            st.session_state.openai_model = config.openai.MODEL_ORCHESTRATOR
            st.session_state.llm_temperature = config.orch_llm.TEMPERATURE
            st.session_state.llm_max_tokens = config.orch_llm.MAX_TOKENS
            
            logger.info("Orchestrator initialized successfully")
            logger.info(f"Model: {st.session_state.openai_model}")
            return True
    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {e}", exc_info=True)
        st.error(f"⚠️ Failed to initialize orchestrator: {str(e)}")
        st.error(f"```\n{traceback.format_exc()}\n```")
        return False

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("What trading strategy are you looking for?"):
    # Initialize orchestrator on first message
    if not initialize_orchestrator():
        st.stop()
    
    logger.info(f"User input received: {prompt}")
    
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Get orchestrator response
    with st.chat_message("assistant"):
        try:
            logger.info("Starting orchestrator.chat()...")
            
            # Show a status message  
            with st.spinner("🤔 Processing your request..."):
                # Call the orchestrator
                response = st.session_state.orchestrator.chat(prompt)
            
            logger.info(f"Got response type: {type(response)}")
            
            # The chat method returns a string directly
            final_response = response if isinstance(response, str) else str(response)
            
            st.markdown(final_response)
            
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": final_response})
            logger.info("Response added to chat history")
                
        except Exception as e:
            logger.error(f"Error in chat: {e}", exc_info=True)
            error_details = f"""
**Error Type:** `{type(e).__name__}`

**Error Message:** 
```
{str(e)}
```

**Full Traceback:**
```python
{traceback.format_exc()}
```
"""
            st.error(error_details)
            st.session_state.messages.append({"role": "assistant", "content": f"Error: {str(e)}"})
                
        except Exception as e:
            error_details = f"""
**Error Type:** {type(e).__name__}

**Error Message:** {str(e)}

**Full Traceback:**
```
{traceback.format_exc()}
```
"""
            st.error(error_details)
            st.session_state.messages.append({"role": "assistant", "content": f"Error: {str(e)}"})

# Sidebar with settings
with st.sidebar:
    st.header("⚙️ Settings")
    
    if st.session_state.get("settings_loaded", False):
        st.info(f"**Model:** {st.session_state.openai_model}")
        st.info(f"**Temperature:** {st.session_state.llm_temperature}")
        st.info(f"**Max Tokens:** {st.session_state.llm_max_tokens}")
    else:
        st.warning("Orchestrator will initialize on first message")
    
    st.divider()
    
    st.header("📋 Example Queries")
    st.markdown("""
    - Find momentum strategies with high Sharpe ratio
    - Show me mean reversion strategies for AAPL
    - Analyze the best performing strategies
    - Refine the top strategy with better risk management
    """)
    
    st.divider()
    
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
        st.rerun()

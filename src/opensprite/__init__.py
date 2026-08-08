"""OpenSprite - Ultra-lightweight personal AI assistant"""

from .app.agent import AgentLoop
from .config import AgentConfig
from .integrations.llm.openai.chat import OpenAILLM
from .app.messaging.dispatcher import MessageQueue, Conversation

__version__ = "0.1.1"
__all__ = [
    "AgentLoop", 
    "AgentConfig", 
    "OpenAILLM",
    "MessageQueue",
    "Conversation"
]

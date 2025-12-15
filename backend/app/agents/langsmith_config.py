"""
LangSmith Configuration and Utilities

Sets up LangSmith tracing for all agent operations.
"""
import os
from functools import wraps
from typing import Any, Callable, Optional
from datetime import datetime

# LangSmith configuration from environment
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT_NAME", "organization-agents")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "true").lower() == "true"


def configure_langsmith():
    """
    Configure LangSmith environment variables.
    Call this at application startup.
    """
    if LANGSMITH_TRACING and LANGSMITH_API_KEY:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = LANGSMITH_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = LANGSMITH_PROJECT
        os.environ["LANGCHAIN_ENDPOINT"] = LANGSMITH_ENDPOINT
        print(f"✅ LangSmith tracing enabled for project: {LANGSMITH_PROJECT}")
        return True
    else:
        print("⚠️ LangSmith tracing disabled (missing API key or disabled)")
        return False


def get_langsmith_client():
    """
    Get LangSmith client for programmatic access.
    
    Returns:
        LangSmith Client or None if not configured
    """
    if not LANGSMITH_API_KEY:
        return None
    
    try:
        from langsmith import Client
        return Client(
            api_key=LANGSMITH_API_KEY,
            api_url=LANGSMITH_ENDPOINT,
        )
    except ImportError:
        print("Warning: langsmith package not installed")
        return None


def create_run_metadata(
    session_id: str,
    user_id: Optional[str] = None,
    tags: Optional[list] = None,
) -> dict:
    """
    Create metadata for a LangSmith run.
    
    Args:
        session_id: Unique session identifier
        user_id: Optional user identifier
        tags: Optional list of tags
        
    Returns:
        Metadata dictionary
    """
    metadata = {
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development"),
    }
    
    if user_id:
        metadata["user_id"] = user_id
    
    return metadata


def create_run_tags(
    agent_name: str,
    operation: str,
    additional_tags: Optional[list] = None,
) -> list:
    """
    Create tags for a LangSmith run.
    
    Args:
        agent_name: Name of the agent
        operation: Type of operation
        additional_tags: Optional additional tags
        
    Returns:
        List of tags
    """
    tags = [
        f"agent:{agent_name}",
        f"operation:{operation}",
        os.getenv("ENVIRONMENT", "dev"),
    ]
    
    if additional_tags:
        tags.extend(additional_tags)
    
    return tags


class LangSmithTracer:
    """
    Context manager for LangSmith tracing.
    """
    
    def __init__(
        self,
        name: str,
        run_type: str = "chain",
        metadata: Optional[dict] = None,
        tags: Optional[list] = None,
    ):
        self.name = name
        self.run_type = run_type
        self.metadata = metadata or {}
        self.tags = tags or []
        self.run = None
    
    def __enter__(self):
        if not LANGSMITH_TRACING:
            return self
        
        try:
            from langsmith import traceable
            self.start_time = datetime.utcnow()
            return self
        except ImportError:
            return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.run:
            self.run.end()
        return False
    
    def log_input(self, input_data: Any):
        """Log input to the trace."""
        self.metadata["input"] = str(input_data)[:1000]
    
    def log_output(self, output_data: Any):
        """Log output to the trace."""
        self.metadata["output"] = str(output_data)[:1000]
    
    def log_error(self, error: Exception):
        """Log error to the trace."""
        self.metadata["error"] = str(error)


def traced_function(
    name: Optional[str] = None,
    run_type: str = "chain",
    tags: Optional[list] = None,
):
    """
    Decorator for tracing functions with LangSmith.
    
    Args:
        name: Name for the trace (defaults to function name)
        run_type: Type of run (chain, llm, tool, etc.)
        tags: Tags for the run
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        trace_name = name or func.__name__
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not LANGSMITH_TRACING:
                return await func(*args, **kwargs)
            
            try:
                from langsmith import traceable
                traced = traceable(name=trace_name, run_type=run_type, tags=tags or [])(func)
                return await traced(*args, **kwargs)
            except ImportError:
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not LANGSMITH_TRACING:
                return func(*args, **kwargs)
            
            try:
                from langsmith import traceable
                traced = traceable(name=trace_name, run_type=run_type, tags=tags or [])(func)
                return traced(*args, **kwargs)
            except ImportError:
                return func(*args, **kwargs)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def get_trace_url(run_id: str) -> Optional[str]:
    """
    Get the URL for a specific trace in LangSmith.
    
    Args:
        run_id: The run ID
        
    Returns:
        URL string or None
    """
    if not LANGSMITH_API_KEY:
        return None
    
    base_url = LANGSMITH_ENDPOINT.replace("api.", "")
    return f"{base_url}/o/default/projects/p/{LANGSMITH_PROJECT}/r/{run_id}"


async def log_feedback(
    run_id: str,
    score: float,
    comment: Optional[str] = None,
    key: str = "user_feedback",
):
    """
    Log user feedback for a run.
    
    Args:
        run_id: The run ID to provide feedback for
        score: Score from 0 to 1
        comment: Optional comment
        key: Feedback key
    """
    client = get_langsmith_client()
    if not client:
        return
    
    try:
        client.create_feedback(
            run_id=run_id,
            key=key,
            score=score,
            comment=comment,
        )
    except Exception as e:
        print(f"Error logging feedback: {e}")

from backend.routes.memory import router as memory_router
from backend.routes.agent import router as agent_router
from backend.routes.consumer import router as consumer_router
from backend.routes.dashboard import router as dashboard_router

__all__ = ["memory_router", "agent_router", "consumer_router", "dashboard_router"]
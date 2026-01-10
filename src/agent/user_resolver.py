"""User resolver for Vanna 2.0 Agent."""

from typing import Optional

try:
    # Try to import Vanna 2.0 interfaces
    from vanna.core.user import UserResolver, User, RequestContext
    VANNA2_AVAILABLE = True
except ImportError:
    # Fallback for compatibility
    VANNA2_AVAILABLE = False
    from dataclasses import dataclass
    
    @dataclass
    class User:
        """User information."""
        id: str
        name: str = ""
        email: Optional[str] = None
        group_memberships: list = None
        
        def __post_init__(self):
            if self.group_memberships is None:
                self.group_memberships = []
    
    class RequestContext:
        """Request context for user resolution."""
        def __init__(self, headers: Optional[dict] = None, metadata: Optional[dict] = None):
            self.headers = headers or {}
            self.metadata = metadata or {}
        
        def get_header(self, key: str) -> Optional[str]:
            return self.headers.get(key)
    
    class UserResolver:
        """Base class for user resolvers."""
        async def resolve_user(self, request_context: RequestContext) -> User:
            raise NotImplementedError


class SimpleUserResolver(UserResolver):
    """
    Simple user resolver that returns a default user.
    Compatible with both Vanna 2.0 Agent and custom implementation.
    In production, this would resolve users from session/auth tokens.
    """
    
    def __init__(self, default_user_id: str = "default"):
        self.default_user = User(
            id=default_user_id,
            name="Default User",
            email="user@example.com",
            group_memberships=["users"]
        )
    
    async def resolve_user(self, request_context: Optional[RequestContext] = None) -> User:
        """
        Resolve user from request context.
        
        Args:
            request_context: RequestContext with headers and metadata
            
        Returns:
            User object
        """
        if request_context:
            # Try to get user from Authorization header
            auth_header = request_context.get_header('Authorization')
            if auth_header:
                # In production, decode JWT token here
                pass
            
            # Try to get from metadata (for backward compatibility)
            if hasattr(request_context, 'metadata') and request_context.metadata:
                if "user_id" in request_context.metadata:
                    return User(
                        id=request_context.metadata["user_id"],
                        name=request_context.metadata.get("user_name", "User"),
                        email=request_context.metadata.get("user_email"),
                        group_memberships=request_context.metadata.get("groups", ["users"])
                    )
        
        return self.default_user
    
    def get_default_user(self) -> User:
        """Get default user."""
        return self.default_user

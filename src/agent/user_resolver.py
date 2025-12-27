"""Simple user resolver for Vanna 2.0."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    """User information."""
    id: str
    name: str
    email: Optional[str] = None


class SimpleUserResolver:
    """
    Simple user resolver that returns a default user.
    In production, this would resolve users from session/auth tokens.
    """
    
    def __init__(self, default_user_id: str = "default"):
        self.default_user = User(
            id=default_user_id,
            name="Default User",
            email="user@example.com"
        )
    
    async def resolve_user(self, context: Optional[dict] = None) -> User:
        """Resolve user from context."""
        if context and "user_id" in context:
            return User(
                id=context["user_id"],
                name=context.get("user_name", "User"),
                email=context.get("user_email")
            )
        return self.default_user
    
    def get_default_user(self) -> User:
        """Get default user."""
        return self.default_user

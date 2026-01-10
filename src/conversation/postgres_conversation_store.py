"""PostgreSQL-based conversation store for Vanna 2.0."""

import asyncpg
import json
from typing import Optional, List, Dict, Any
from datetime import datetime

try:
    from vanna.core.conversation import ConversationStore, Message, Conversation
    VANNA2_AVAILABLE = True
except ImportError:
    VANNA2_AVAILABLE = False
    from dataclasses import dataclass, field
    from datetime import datetime
    
    @dataclass
    class Message:
        """Chat message."""
        role: str  # "user", "assistant", "system"
        content: str
        timestamp: datetime = field(default_factory=datetime.utcnow)
        metadata: Dict[str, Any] = field(default_factory=dict)
    
    @dataclass
    class Conversation:
        """Conversation object."""
        id: str
        user_id: str
        messages: List[Message] = field(default_factory=list)
        created_at: datetime = field(default_factory=datetime.utcnow)
        updated_at: datetime = field(default_factory=datetime.utcnow)
        metadata: Dict[str, Any] = field(default_factory=dict)
    
    class ConversationStore:
        """Base class for conversation stores."""
        async def save_message(self, conversation_id: str, message: Message, user_id: str) -> None:
            raise NotImplementedError
        
        async def get_conversation(self, conversation_id: str, user_id: str) -> Optional[Conversation]:
            raise NotImplementedError
        
        async def list_conversations(self, user_id: str, limit: int = 50) -> List[Conversation]:
            raise NotImplementedError


class PostgresConversationStore(ConversationStore):
    """
    PostgreSQL-based conversation store.
    Stores conversation history in pgvector database.
    Compatible with both Vanna User objects and string user_ids.
    """
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: Optional[asyncpg.Pool] = None
    
    def _extract_user_id(self, user) -> str:
        """
        Extract user_id from User object or string.
        
        Args:
            user: User object (with .id attribute) or string user_id
            
        Returns:
            str: The user_id
        """
        if isinstance(user, str):
            return user
        elif hasattr(user, 'id'):
            return user.id
        else:
            return str(user)
    
    async def initialize(self):
        """Initialize connection pool and create tables."""
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=2,
            max_size=10
        )
        
        # Create conversations table
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    metadata JSONB DEFAULT '{}'::jsonb
                )
            """)
            
            # Create indexes separately
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_user_id 
                ON conversations(user_id)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_updated_at 
                ON conversations(updated_at DESC)
            """)
            
            # Create messages table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id SERIAL PRIMARY KEY,
                    conversation_id VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
                    metadata JSONB DEFAULT '{}'::jsonb,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
            """)
            
            # Create indexes separately
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation_id 
                ON conversation_messages(conversation_id)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_timestamp 
                ON conversation_messages(timestamp)
            """)
    
    async def close(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
    
    async def save_message(
        self,
        conversation_id: str,
        message: Message,
        user_id: str
    ) -> None:
        """
        Save a message to a conversation.
        Creates conversation if it doesn't exist.
        
        Args:
            conversation_id: Conversation ID
            message: Message to save
            user_id: User ID or User object
        """
        user_id_str = self._extract_user_id(user_id)
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Ensure conversation exists
                await conn.execute("""
                    INSERT INTO conversations (id, user_id, created_at, updated_at)
                    VALUES ($1, $2, NOW(), NOW())
                    ON CONFLICT (id) DO UPDATE
                    SET updated_at = NOW()
                """, conversation_id, user_id_str)
                
                # Insert message
                await conn.execute("""
                    INSERT INTO conversation_messages 
                    (conversation_id, role, content, timestamp, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                """, 
                    conversation_id,
                    message.role,
                    message.content,
                    message.timestamp if hasattr(message, 'timestamp') else datetime.utcnow(),
                    json.dumps(message.metadata if hasattr(message, 'metadata') else {})
                )
    
    async def get_conversation(
        self,
        conversation_id: str,
        user_id: str
    ) -> Optional[Conversation]:
        """
        Get a conversation with all its messages.
        
        Args:
            conversation_id: Conversation ID
            user_id: User ID or User object (for security check)
            
        Returns:
            Conversation object or None if not found
        """
        user_id_str = self._extract_user_id(user_id)
        
        async with self.pool.acquire() as conn:
            # Get conversation
            conv_row = await conn.fetchrow("""
                SELECT id, user_id, created_at, updated_at, metadata
                FROM conversations
                WHERE id = $1 AND user_id = $2
            """, conversation_id, user_id_str)
            
            if not conv_row:
                return None
            
            # Get messages
            message_rows = await conn.fetch("""
                SELECT role, content, timestamp, metadata
                FROM conversation_messages
                WHERE conversation_id = $1
                ORDER BY timestamp ASC
            """, conversation_id)
            
            messages = [
                Message(
                    role=row['role'],
                    content=row['content'],
                    timestamp=row['timestamp'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {}
                )
                for row in message_rows
            ]
            
            return Conversation(
                id=conv_row['id'],
                user_id=conv_row['user_id'],
                messages=messages,
                created_at=conv_row['created_at'],
                updated_at=conv_row['updated_at'],
                metadata=json.loads(conv_row['metadata']) if conv_row['metadata'] else {}
            )
    
    async def list_conversations(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[Conversation]:
        """
        List conversations for a user.
        
        Args:
            user_id: User ID or User object
            limit: Maximum number of conversations to return
            
        Returns:
            List of conversations (without messages, for performance)
        """
        user_id_str = self._extract_user_id(user_id)
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, user_id, created_at, updated_at, metadata
                FROM conversations
                WHERE user_id = $1
                ORDER BY updated_at DESC
                LIMIT $2
            """, user_id_str, limit)
            
            return [
                Conversation(
                    id=row['id'],
                    user_id=row['user_id'],
                    messages=[],  # Don't load messages for list view
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {}
                )
                for row in rows
            ]
    
    async def delete_conversation(
        self,
        conversation_id: str,
        user_id: str
    ) -> bool:
        """
        Delete a conversation and all its messages.
        
        Args:
            conversation_id: Conversation ID
            user_id: User ID or User object (for security check)
            
        Returns:
            True if deleted, False if not found
        """
        user_id_str = self._extract_user_id(user_id)
        
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM conversations
                WHERE id = $1 AND user_id = $2
            """, conversation_id, user_id_str)
            
            return result.split()[-1] != '0'
    
    async def update_conversation(
        self,
        conversation: Conversation
    ) -> None:
        """
        Update a conversation's metadata and messages.
        
        Args:
            conversation: Conversation object with updated data
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Update conversation metadata
                await conn.execute("""
                    UPDATE conversations
                    SET updated_at = NOW(),
                        metadata = $2
                    WHERE id = $1
                """, conversation.id, json.dumps(conversation.metadata))
                
                # Update is mainly for metadata; messages are added via save_message
                # If needed, we could also sync messages here, but typically
                # Vanna Agent uses save_message for adding messages
    
    async def get_recent_messages(
        self,
        conversation_id: str,
        user_id: str,
        limit: int = 10
    ) -> List[Message]:
        """
        Get recent messages from a conversation.
        
        Args:
            conversation_id: Conversation ID
            user_id: User ID or User object
            limit: Maximum number of messages to return
            
        Returns:
            List of recent messages
        """
        user_id_str = self._extract_user_id(user_id)
        
        async with self.pool.acquire() as conn:
            # Verify user owns conversation
            conv_exists = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM conversations
                    WHERE id = $1 AND user_id = $2
                )
            """, conversation_id, user_id_str)
            
            if not conv_exists:
                return []
            
            # Get recent messages
            rows = await conn.fetch("""
                SELECT role, content, timestamp, metadata
                FROM conversation_messages
                WHERE conversation_id = $1
                ORDER BY timestamp DESC
                LIMIT $2
            """, conversation_id, limit)
            
            # Reverse to get chronological order
            return [
                Message(
                    role=row['role'],
                    content=row['content'],
                    timestamp=row['timestamp'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {}
                )
                for row in reversed(rows)
            ]

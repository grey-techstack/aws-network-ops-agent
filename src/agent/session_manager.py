"""
Session Manager for AWS Operations Agent.

This module provides session management functionality for maintaining conversation
context and history across multiple user queries.
"""

import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class ConversationMessage:
    """Represents a single message in a conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    """Represents a user session with conversation history."""
    session_id: str
    messages: List[ConversationMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Add a message to the conversation history.
        
        Args:
            role: Message role ("user" or "assistant")
            content: Message content
            metadata: Optional metadata for the message
        """
        message = ConversationMessage(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(message)
        self.last_activity = datetime.utcnow()
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """
        Get conversation history in LangChain format.
        
        Returns:
            List of message dictionaries with 'role' and 'content' keys
        """
        return [
            {
                "role": msg.role,
                "content": msg.content
            }
            for msg in self.messages
        ]
    
    def is_expired(self, expiration_minutes: int = 60) -> bool:
        """
        Check if the session has expired due to inactivity.
        
        Args:
            expiration_minutes: Minutes of inactivity before expiration (default: 60)
            
        Returns:
            True if session is expired, False otherwise
        """
        expiration_time = self.last_activity + timedelta(minutes=expiration_minutes)
        return datetime.utcnow() > expiration_time
    
    def get_age_minutes(self) -> float:
        """
        Get the age of the session in minutes.
        
        Returns:
            Session age in minutes
        """
        age = datetime.utcnow() - self.created_at
        return age.total_seconds() / 60
    
    def get_inactivity_minutes(self) -> float:
        """
        Get the inactivity duration in minutes.
        
        Returns:
            Inactivity duration in minutes
        """
        inactivity = datetime.utcnow() - self.last_activity
        return inactivity.total_seconds() / 60


class SessionManager:
    """
    Manages user sessions and conversation history.
    
    This class provides:
    - Session creation and retrieval
    - Conversation history management
    - Automatic session expiration
    - Thread-safe session access
    """
    
    def __init__(self, expiration_minutes: int = 60):
        """
        Initialize the session manager.
        
        Args:
            expiration_minutes: Minutes of inactivity before session expiration (default: 60)
        """
        self.expiration_minutes = expiration_minutes
        self.sessions: Dict[str, Session] = {}
        self._lock = Lock()
        
        logger.info(f"SessionManager initialized with {expiration_minutes} minute expiration")
    
    def get_or_create_session(self, session_id: str) -> Session:
        """
        Get an existing session or create a new one.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Session instance
        """
        with self._lock:
            # Clean up expired sessions first
            self._cleanup_expired_sessions()
            
            # Check if session exists and is not expired
            if session_id in self.sessions:
                session = self.sessions[session_id]
                if not session.is_expired(self.expiration_minutes):
                    logger.info(f"Retrieved existing session: {session_id}")
                    return session
                else:
                    logger.info(f"Session {session_id} expired, creating new session")
                    del self.sessions[session_id]
            
            # Create new session
            session = Session(session_id=session_id)
            self.sessions[session_id] = session
            logger.info(f"Created new session: {session_id}")
            return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get an existing session without creating a new one.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Session instance if exists and not expired, None otherwise
        """
        with self._lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                if not session.is_expired(self.expiration_minutes):
                    return session
                else:
                    logger.info(f"Session {session_id} expired")
                    del self.sessions[session_id]
            return None
    
    def add_user_message(
        self,
        session_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a user message to the session.
        
        Args:
            session_id: Unique session identifier
            content: Message content
            metadata: Optional metadata for the message
        """
        session = self.get_or_create_session(session_id)
        session.add_message("user", content, metadata)
        logger.debug(f"Added user message to session {session_id}")
    
    def add_assistant_message(
        self,
        session_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add an assistant message to the session.
        
        Args:
            session_id: Unique session identifier
            content: Message content
            metadata: Optional metadata for the message
        """
        session = self.get_or_create_session(session_id)
        session.add_message("assistant", content, metadata)
        logger.debug(f"Added assistant message to session {session_id}")
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, str]]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            List of message dictionaries with 'role' and 'content' keys
        """
        session = self.get_session(session_id)
        if session:
            return session.get_conversation_history()
        return []
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear a specific session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            True if session was cleared, False if session didn't exist
        """
        with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info(f"Cleared session: {session_id}")
                return True
            return False
    
    def clear_all_sessions(self) -> int:
        """
        Clear all sessions.
        
        Returns:
            Number of sessions cleared
        """
        with self._lock:
            count = len(self.sessions)
            self.sessions.clear()
            logger.info(f"Cleared all {count} sessions")
            return count
    
    def _cleanup_expired_sessions(self) -> int:
        """
        Remove expired sessions from memory.
        
        Returns:
            Number of sessions removed
        """
        expired_sessions = [
            session_id
            for session_id, session in self.sessions.items()
            if session.is_expired(self.expiration_minutes)
        ]
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
        
        return len(expired_sessions)
    
    def get_active_session_count(self) -> int:
        """
        Get the number of active (non-expired) sessions.
        
        Returns:
            Number of active sessions
        """
        with self._lock:
            self._cleanup_expired_sessions()
            return len(self.sessions)
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Dictionary with session information or None if session doesn't exist
        """
        session = self.get_session(session_id)
        if session:
            return {
                "session_id": session.session_id,
                "message_count": len(session.messages),
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "age_minutes": session.get_age_minutes(),
                "inactivity_minutes": session.get_inactivity_minutes(),
                "is_expired": session.is_expired(self.expiration_minutes)
            }
        return None
    
    def get_all_session_info(self) -> List[Dict[str, Any]]:
        """
        Get information about all active sessions.
        
        Returns:
            List of session information dictionaries
        """
        with self._lock:
            self._cleanup_expired_sessions()
            return [
                self.get_session_info(session_id)
                for session_id in self.sessions.keys()
            ]

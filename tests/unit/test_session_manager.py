"""
Unit tests for SessionManager.

Tests session creation, conversation history management, and session expiration.
"""

import pytest
import time
from datetime import datetime, timedelta
from src.agent.session_manager import SessionManager, Session, ConversationMessage


class TestConversationMessage:
    """Test ConversationMessage dataclass."""
    
    def test_message_creation(self):
        """Test creating a conversation message."""
        msg = ConversationMessage(role="user", content="Hello")
        
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert isinstance(msg.timestamp, datetime)
        assert msg.metadata == {}
    
    def test_message_with_metadata(self):
        """Test creating a message with metadata."""
        metadata = {"query_type": "trace", "fqdn": "demo.example.com"}
        msg = ConversationMessage(
            role="assistant",
            content="Tracing demo.example.com...",
            metadata=metadata
        )
        
        assert msg.role == "assistant"
        assert msg.content == "Tracing demo.example.com..."
        assert msg.metadata == metadata


class TestSession:
    """Test Session dataclass."""
    
    def test_session_creation(self):
        """Test creating a session."""
        session = Session(session_id="test-123")
        
        assert session.session_id == "test-123"
        assert session.messages == []
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_activity, datetime)
        assert session.metadata == {}
    
    def test_add_message(self):
        """Test adding messages to a session."""
        session = Session(session_id="test-123")
        
        session.add_message("user", "What is demo.example.com?")
        session.add_message("assistant", "Let me trace that for you.")
        
        assert len(session.messages) == 2
        assert session.messages[0].role == "user"
        assert session.messages[0].content == "What is demo.example.com?"
        assert session.messages[1].role == "assistant"
        assert session.messages[1].content == "Let me trace that for you."
    
    def test_add_message_updates_last_activity(self):
        """Test that adding a message updates last_activity."""
        session = Session(session_id="test-123")
        initial_activity = session.last_activity
        
        # Wait a tiny bit to ensure timestamp difference
        time.sleep(0.01)
        
        session.add_message("user", "Hello")
        
        assert session.last_activity > initial_activity
    
    def test_get_conversation_history(self):
        """Test getting conversation history in LangChain format."""
        session = Session(session_id="test-123")
        
        session.add_message("user", "Trace demo.example.com")
        session.add_message("assistant", "Tracing...")
        session.add_message("user", "Show me the logs")
        
        history = session.get_conversation_history()
        
        assert len(history) == 3
        assert history[0] == {"role": "user", "content": "Trace demo.example.com"}
        assert history[1] == {"role": "assistant", "content": "Tracing..."}
        assert history[2] == {"role": "user", "content": "Show me the logs"}
    
    def test_is_expired_not_expired(self):
        """Test that a recent session is not expired."""
        session = Session(session_id="test-123")
        
        assert not session.is_expired(expiration_minutes=60)
    
    def test_is_expired_expired(self):
        """Test that an old session is expired."""
        session = Session(session_id="test-123")
        
        # Manually set last_activity to 2 hours ago
        session.last_activity = datetime.utcnow() - timedelta(hours=2)
        
        assert session.is_expired(expiration_minutes=60)
    
    def test_get_age_minutes(self):
        """Test getting session age in minutes."""
        session = Session(session_id="test-123")
        
        # Manually set created_at to 30 minutes ago
        session.created_at = datetime.utcnow() - timedelta(minutes=30)
        
        age = session.get_age_minutes()
        assert 29 < age < 31  # Allow small margin for execution time
    
    def test_get_inactivity_minutes(self):
        """Test getting inactivity duration in minutes."""
        session = Session(session_id="test-123")
        
        # Manually set last_activity to 15 minutes ago
        session.last_activity = datetime.utcnow() - timedelta(minutes=15)
        
        inactivity = session.get_inactivity_minutes()
        assert 14 < inactivity < 16  # Allow small margin for execution time


class TestSessionManager:
    """Test SessionManager class."""
    
    def test_initialization(self):
        """Test SessionManager initialization."""
        manager = SessionManager(expiration_minutes=30)
        
        assert manager.expiration_minutes == 30
        assert manager.sessions == {}
        assert manager.get_active_session_count() == 0
    
    def test_get_or_create_session_creates_new(self):
        """Test that get_or_create_session creates a new session."""
        manager = SessionManager()
        
        session = manager.get_or_create_session("session-1")
        
        assert session.session_id == "session-1"
        assert len(session.messages) == 0
        assert manager.get_active_session_count() == 1
    
    def test_get_or_create_session_returns_existing(self):
        """Test that get_or_create_session returns existing session."""
        manager = SessionManager()
        
        # Create session and add a message
        session1 = manager.get_or_create_session("session-1")
        session1.add_message("user", "Hello")
        
        # Get the same session
        session2 = manager.get_or_create_session("session-1")
        
        assert session1 is session2
        assert len(session2.messages) == 1
        assert session2.messages[0].content == "Hello"
    
    def test_get_session_returns_existing(self):
        """Test that get_session returns existing session."""
        manager = SessionManager()
        
        manager.get_or_create_session("session-1")
        session = manager.get_session("session-1")
        
        assert session is not None
        assert session.session_id == "session-1"
    
    def test_get_session_returns_none_for_nonexistent(self):
        """Test that get_session returns None for non-existent session."""
        manager = SessionManager()
        
        session = manager.get_session("nonexistent")
        
        assert session is None
    
    def test_add_user_message(self):
        """Test adding a user message."""
        manager = SessionManager()
        
        manager.add_user_message("session-1", "What is demo.example.com?")
        
        session = manager.get_session("session-1")
        assert len(session.messages) == 1
        assert session.messages[0].role == "user"
        assert session.messages[0].content == "What is demo.example.com?"
    
    def test_add_assistant_message(self):
        """Test adding an assistant message."""
        manager = SessionManager()
        
        manager.add_assistant_message("session-1", "Let me trace that for you.")
        
        session = manager.get_session("session-1")
        assert len(session.messages) == 1
        assert session.messages[0].role == "assistant"
        assert session.messages[0].content == "Let me trace that for you."
    
    def test_add_message_with_metadata(self):
        """Test adding a message with metadata."""
        manager = SessionManager()
        
        metadata = {"tool": "route53", "fqdn": "demo.example.com"}
        manager.add_user_message("session-1", "Trace demo.example.com", metadata=metadata)
        
        session = manager.get_session("session-1")
        assert session.messages[0].metadata == metadata
    
    def test_get_conversation_history(self):
        """Test getting conversation history."""
        manager = SessionManager()
        
        manager.add_user_message("session-1", "Trace demo.example.com")
        manager.add_assistant_message("session-1", "Tracing...")
        manager.add_user_message("session-1", "Show logs")
        
        history = manager.get_conversation_history("session-1")
        
        assert len(history) == 3
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Trace demo.example.com"
        assert history[1]["role"] == "assistant"
        assert history[2]["role"] == "user"
    
    def test_get_conversation_history_empty_for_nonexistent(self):
        """Test that get_conversation_history returns empty list for non-existent session."""
        manager = SessionManager()
        
        history = manager.get_conversation_history("nonexistent")
        
        assert history == []
    
    def test_clear_session(self):
        """Test clearing a specific session."""
        manager = SessionManager()
        
        manager.add_user_message("session-1", "Hello")
        manager.add_user_message("session-2", "World")
        
        assert manager.get_active_session_count() == 2
        
        result = manager.clear_session("session-1")
        
        assert result is True
        assert manager.get_active_session_count() == 1
        assert manager.get_session("session-1") is None
        assert manager.get_session("session-2") is not None
    
    def test_clear_session_returns_false_for_nonexistent(self):
        """Test that clear_session returns False for non-existent session."""
        manager = SessionManager()
        
        result = manager.clear_session("nonexistent")
        
        assert result is False
    
    def test_clear_all_sessions(self):
        """Test clearing all sessions."""
        manager = SessionManager()
        
        manager.add_user_message("session-1", "Hello")
        manager.add_user_message("session-2", "World")
        manager.add_user_message("session-3", "Test")
        
        assert manager.get_active_session_count() == 3
        
        count = manager.clear_all_sessions()
        
        assert count == 3
        assert manager.get_active_session_count() == 0
    
    def test_cleanup_expired_sessions(self):
        """Test that expired sessions are cleaned up."""
        manager = SessionManager(expiration_minutes=1)
        
        # Create a session and manually expire it
        session = manager.get_or_create_session("session-1")
        session.last_activity = datetime.utcnow() - timedelta(minutes=2)
        
        # Create a fresh session
        manager.get_or_create_session("session-2")
        
        # Trigger cleanup by getting or creating a session
        manager.get_or_create_session("session-3")
        
        # Only session-2 and session-3 should remain
        assert manager.get_active_session_count() == 2
        assert manager.get_session("session-1") is None
        assert manager.get_session("session-2") is not None
        assert manager.get_session("session-3") is not None
    
    def test_get_session_info(self):
        """Test getting session information."""
        manager = SessionManager()
        
        manager.add_user_message("session-1", "Hello")
        manager.add_assistant_message("session-1", "Hi there")
        
        info = manager.get_session_info("session-1")
        
        assert info is not None
        assert info["session_id"] == "session-1"
        assert info["message_count"] == 2
        assert "created_at" in info
        assert "last_activity" in info
        assert "age_minutes" in info
        assert "inactivity_minutes" in info
        assert info["is_expired"] is False
    
    def test_get_session_info_returns_none_for_nonexistent(self):
        """Test that get_session_info returns None for non-existent session."""
        manager = SessionManager()
        
        info = manager.get_session_info("nonexistent")
        
        assert info is None
    
    def test_get_all_session_info(self):
        """Test getting information about all sessions."""
        manager = SessionManager()
        
        manager.add_user_message("session-1", "Hello")
        manager.add_user_message("session-2", "World")
        
        all_info = manager.get_all_session_info()
        
        assert len(all_info) == 2
        session_ids = {info["session_id"] for info in all_info}
        assert session_ids == {"session-1", "session-2"}
    
    def test_multiple_sessions_independent(self):
        """Test that multiple sessions are independent."""
        manager = SessionManager()
        
        manager.add_user_message("session-1", "Message 1")
        manager.add_user_message("session-2", "Message 2")
        manager.add_assistant_message("session-1", "Response 1")
        
        history1 = manager.get_conversation_history("session-1")
        history2 = manager.get_conversation_history("session-2")
        
        assert len(history1) == 2
        assert len(history2) == 1
        assert history1[0]["content"] == "Message 1"
        assert history2[0]["content"] == "Message 2"
    
    def test_thread_safety_basic(self):
        """Test basic thread safety of session operations."""
        import threading
        
        manager = SessionManager()
        
        def add_messages(session_id, count):
            for i in range(count):
                manager.add_user_message(session_id, f"Message {i}")
        
        # Create multiple threads adding messages
        threads = []
        for i in range(5):
            thread = threading.Thread(target=add_messages, args=(f"session-{i}", 10))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all sessions were created
        assert manager.get_active_session_count() == 5
        
        # Verify each session has 10 messages
        for i in range(5):
            history = manager.get_conversation_history(f"session-{i}")
            assert len(history) == 10

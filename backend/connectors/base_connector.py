"""
Base Connector Class
Abstract base class for all data source connectors.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum
import json


class ConnectorStatus(Enum):
    """Status of a connector"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SYNCING = "syncing"
    ERROR = "error"


@dataclass
class ConnectorConfig:
    """Configuration for a connector"""
    connector_type: str
    user_id: str
    credentials: Dict[str, Any] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)
    last_sync: Optional[datetime] = None
    sync_frequency: int = 3600  # seconds
    enabled: bool = True

    def to_dict(self) -> Dict:
        return {
            "connector_type": self.connector_type,
            "user_id": self.user_id,
            "credentials": self.credentials,
            "settings": self.settings,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "sync_frequency": self.sync_frequency,
            "enabled": self.enabled
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ConnectorConfig':
        last_sync = None
        if data.get("last_sync"):
            last_sync = datetime.fromisoformat(data["last_sync"])

        return cls(
            connector_type=data["connector_type"],
            user_id=data["user_id"],
            credentials=data.get("credentials", {}),
            settings=data.get("settings", {}),
            last_sync=last_sync,
            sync_frequency=data.get("sync_frequency", 3600),
            enabled=data.get("enabled", True)
        )


@dataclass
class Document:
    """Represents a document from any source"""
    doc_id: str
    source: str  # gmail, slack, github, etc.
    content: str
    title: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[datetime] = None
    author: Optional[str] = None
    url: Optional[str] = None
    doc_type: str = "text"  # email, message, code, document, etc.
    # Aliases for compatibility with integration_routes.py
    source_id: Optional[str] = None
    source_type: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        # Set aliases if not explicitly provided
        if self.source_id is None:
            self.source_id = self.doc_id
        if self.source_type is None:
            self.source_type = self.source
        if self.created_at is None:
            self.created_at = self.timestamp
        if self.updated_at is None:
            self.updated_at = self.timestamp

    def to_dict(self) -> Dict:
        return {
            "doc_id": self.doc_id,
            "source": self.source,
            "content": self.content,
            "title": self.title,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "author": self.author,
            "url": self.url,
            "doc_type": self.doc_type
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Document':
        timestamp = None
        if data.get("timestamp"):
            timestamp = datetime.fromisoformat(data["timestamp"])

        return cls(
            doc_id=data["doc_id"],
            source=data["source"],
            content=data["content"],
            title=data["title"],
            metadata=data.get("metadata", {}),
            timestamp=timestamp,
            author=data.get("author"),
            url=data.get("url"),
            doc_type=data.get("doc_type", "text")
        )


class BaseConnector(ABC):
    """
    Abstract base class for data source connectors.
    All connectors must implement these methods.
    """

    CONNECTOR_TYPE = "base"
    REQUIRED_CREDENTIALS = []
    OPTIONAL_SETTINGS = {}

    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.status = ConnectorStatus.DISCONNECTED
        self.last_error: Optional[str] = None
        self.sync_stats: Dict[str, Any] = {}

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the data source.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Disconnect from the data source.
        """
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test if the connection is valid.
        """
        pass

    @abstractmethod
    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        """
        Sync documents from the data source.

        Args:
            since: Only sync documents modified after this datetime.
                   If None, sync all documents based on settings.

        Returns:
            List of Document objects.
        """
        pass

    @abstractmethod
    async def get_document(self, doc_id: str) -> Optional[Document]:
        """
        Get a specific document by ID.
        """
        pass

    @classmethod
    def get_auth_url(cls, redirect_uri: str, state: str) -> str:
        """
        Get OAuth authorization URL for this connector.
        Override in subclasses that support OAuth.
        """
        raise NotImplementedError("This connector does not support OAuth")

    @classmethod
    async def exchange_code(cls, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange OAuth authorization code for tokens.
        Override in subclasses that support OAuth.
        """
        raise NotImplementedError("This connector does not support OAuth")

    async def refresh_tokens(self) -> bool:
        """
        Refresh OAuth tokens if expired.
        Override in subclasses that support OAuth.
        """
        return True

    def validate_credentials(self) -> bool:
        """
        Validate that all required credentials are present.
        """
        for cred in self.REQUIRED_CREDENTIALS:
            if cred not in self.config.credentials:
                return False
        return True

    def get_status(self) -> Dict[str, Any]:
        """
        Get current connector status.
        """
        return {
            "connector_type": self.CONNECTOR_TYPE,
            "status": self.status.value,
            "last_error": self.last_error,
            "last_sync": self.config.last_sync.isoformat() if self.config.last_sync else None,
            "sync_stats": self.sync_stats,
            "enabled": self.config.enabled
        }

    def _set_error(self, error: str):
        """Set error state"""
        self.status = ConnectorStatus.ERROR
        self.last_error = error

    def _clear_error(self):
        """Clear error state"""
        self.last_error = None


class MockConnector(BaseConnector):
    """Mock connector for testing"""

    CONNECTOR_TYPE = "mock"
    REQUIRED_CREDENTIALS = []

    async def connect(self) -> bool:
        self.status = ConnectorStatus.CONNECTED
        return True

    async def disconnect(self) -> bool:
        self.status = ConnectorStatus.DISCONNECTED
        return True

    async def test_connection(self) -> bool:
        return self.status == ConnectorStatus.CONNECTED

    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        # Return some mock documents
        return [
            Document(
                doc_id="mock_1",
                source="mock",
                content="This is a mock document for testing.",
                title="Mock Document 1",
                author="Test User",
                doc_type="text"
            )
        ]

    async def get_document(self, doc_id: str) -> Optional[Document]:
        if doc_id == "mock_1":
            return Document(
                doc_id="mock_1",
                source="mock",
                content="This is a mock document for testing.",
                title="Mock Document 1",
                author="Test User",
                doc_type="text"
            )
        return None

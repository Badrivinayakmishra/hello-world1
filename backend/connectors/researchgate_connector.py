"""
ResearchGate Connector - NOT IMPLEMENTED
"""

from datetime import datetime
from typing import List, Optional

from .base_connector import BaseConnector, ConnectorConfig, ConnectorStatus, Document


class ResearchGateConnector(BaseConnector):
    """
    ResearchGate connector - NOT AVAILABLE

    ResearchGate does not provide a public API and actively blocks automated access.

    Limitations:
    - No official public API
    - Terms of Service prohibit automated scraping
    - Active anti-bot protection
    - Legal risks for unauthorized access

    Alternative:
    - Use PubMed connector for biomedical papers
    - Use manual exports from ResearchGate
    - Contact ResearchGate for API access (institutional partners only)
    """

    CONNECTOR_TYPE = "researchgate"
    REQUIRED_CREDENTIALS = []
    OPTIONAL_SETTINGS = {}

    async def connect(self) -> bool:
        """Cannot connect - no API available"""
        self._set_error(
            "ResearchGate does not provide a public API. "
            "Automated access violates their Terms of Service. "
            "Please use PubMed or manual exports instead."
        )
        self.status = ConnectorStatus.ERROR
        return False

    async def disconnect(self) -> bool:
        """Disconnect"""
        self.status = ConnectorStatus.DISCONNECTED
        return True

    async def test_connection(self) -> bool:
        """Cannot test - no API"""
        return False

    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        """Cannot sync - no API available"""
        return []

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """Cannot get document - no API"""
        return None

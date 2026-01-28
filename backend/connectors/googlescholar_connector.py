"""
Google Scholar Connector - NOT IMPLEMENTED
"""

from datetime import datetime
from typing import List, Optional

from .base_connector import BaseConnector, ConnectorConfig, ConnectorStatus, Document


class GoogleScholarConnector(BaseConnector):
    """
    Google Scholar connector - NOT AVAILABLE

    Google Scholar does not provide an official API and explicitly prohibits automated access.

    Limitations:
    - No official public API
    - Terms of Service explicitly prohibit automated queries
    - Active CAPTCHA and IP blocking for bots
    - Legal risks for violating Google ToS
    - Unofficial scrapers are unreliable and break frequently

    Alternatives:
    - Use PubMed for biomedical/life sciences papers
    - Use Google Scholar manually for searches
    - Use Semantic Scholar API (has free academic API)
    - Use CrossRef API for DOI lookups
    - Use arXiv API for preprints

    Note: Some third-party services (like SerpApi) offer Google Scholar scraping
    as a paid service, but this still violates Google's ToS and may result in
    legal action or IP bans.
    """

    CONNECTOR_TYPE = "googlescholar"
    REQUIRED_CREDENTIALS = []
    OPTIONAL_SETTINGS = {}

    async def connect(self) -> bool:
        """Cannot connect - no API available"""
        self._set_error(
            "Google Scholar does not provide a public API and prohibits automated access. "
            "Automated queries violate Google's Terms of Service. "
            "Please use PubMed or Semantic Scholar API instead."
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

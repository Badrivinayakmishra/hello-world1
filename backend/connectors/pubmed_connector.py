"""
PubMed Connector
Connects to NCBI PubMed E-utilities API to search and retrieve biomedical research papers.
"""

import os
import time
from datetime import datetime
from typing import List, Dict, Optional
import xml.etree.ElementTree as ET

from .base_connector import BaseConnector, ConnectorConfig, ConnectorStatus, Document

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class PubMedConnector(BaseConnector):
    """
    PubMed connector for searching and retrieving biomedical literature.

    Uses NCBI E-utilities API:
    - ESearch: Search for papers
    - EFetch: Retrieve paper metadata and abstracts

    No authentication required for basic usage.
    Rate limits: 3 requests/second (10/second with API key)
    """

    CONNECTOR_TYPE = "pubmed"
    REQUIRED_CREDENTIALS = []  # No auth required
    OPTIONAL_SETTINGS = {
        "search_query": "",  # PubMed query string (e.g., "NICU[Title] AND outcomes")
        "max_results": 100,  # Maximum papers to fetch per sync
        "date_range_years": 5,  # Only fetch papers from last N years (0 = all time)
        "include_abstracts_only": True,  # Only include papers with abstracts
        "api_key": None  # Optional NCBI API key for higher rate limits
    }

    # NCBI E-utilities endpoints
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    ESEARCH_URL = f"{BASE_URL}/esearch.fcgi"
    EFETCH_URL = f"{BASE_URL}/efetch.fcgi"

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.api_key = config.settings.get("api_key") or os.getenv("PUBMED_API_KEY")
        self.rate_limit_delay = 0.1 if self.api_key else 0.34  # 10/sec with key, 3/sec without

    async def connect(self) -> bool:
        """Test PubMed API connection"""
        if not REQUESTS_AVAILABLE:
            self._set_error("requests library not installed")
            return False

        try:
            self.status = ConnectorStatus.CONNECTING

            # Test connection with a simple search
            params = {
                "db": "pubmed",
                "term": "test",
                "retmax": 1,
                "retmode": "json"
            }
            if self.api_key:
                params["api_key"] = self.api_key

            response = requests.get(self.ESEARCH_URL, params=params, timeout=10)

            if response.status_code != 200:
                self._set_error(f"PubMed API returned status {response.status_code}")
                return False

            data = response.json()
            if "esearchresult" not in data:
                self._set_error("Invalid PubMed API response")
                return False

            self.status = ConnectorStatus.CONNECTED
            self._clear_error()
            print(f"[PubMed] Connected successfully (API key: {'Yes' if self.api_key else 'No'})")
            return True

        except Exception as e:
            self._set_error(f"Failed to connect: {str(e)}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect from PubMed"""
        self.status = ConnectorStatus.DISCONNECTED
        return True

    async def test_connection(self) -> bool:
        """Test PubMed connection"""
        return await self.connect()

    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        """
        Search PubMed and fetch papers based on configured query.

        Args:
            since: Only fetch papers published after this date (optional)

        Returns:
            List of Document objects with paper metadata and abstracts
        """
        if self.status != ConnectorStatus.CONNECTED:
            if not await self.connect():
                return []

        self.status = ConnectorStatus.SYNCING
        documents = []

        try:
            search_query = self.config.settings.get("search_query", "")
            if not search_query:
                self._set_error("No search query configured. Please set 'search_query' in settings.")
                return []

            max_results = self.config.settings.get("max_results", 100)
            date_range_years = self.config.settings.get("date_range_years", 5)

            print(f"[PubMed] Searching for: '{search_query}' (max {max_results} results)")

            # Build date filter if specified
            if date_range_years > 0:
                current_year = datetime.now().year
                start_year = current_year - date_range_years
                search_query += f" AND {start_year}:{current_year}[pdat]"
                print(f"[PubMed] Date range: {start_year}-{current_year}")

            # Step 1: Search for paper IDs
            pmids = await self._search_papers(search_query, max_results)
            if not pmids:
                print("[PubMed] No papers found matching query")
                self.status = ConnectorStatus.CONNECTED
                return []

            print(f"[PubMed] Found {len(pmids)} papers")

            # Step 2: Fetch paper details in batches
            documents = await self._fetch_papers(pmids, since)

            # Filter out papers without abstracts if configured
            if self.config.settings.get("include_abstracts_only", True):
                original_count = len(documents)
                documents = [doc for doc in documents if doc.content and len(doc.content.strip()) > 100]
                if len(documents) < original_count:
                    print(f"[PubMed] Filtered out {original_count - len(documents)} papers without abstracts")

            print(f"[PubMed] Successfully fetched {len(documents)} papers")

            self.config.last_sync = datetime.now()
            self.status = ConnectorStatus.CONNECTED
            self._clear_error()

        except Exception as e:
            self._set_error(f"Sync failed: {str(e)}")
            print(f"[PubMed] Sync error: {e}")
            import traceback
            traceback.print_exc()

        return documents

    async def _search_papers(self, query: str, max_results: int) -> List[str]:
        """
        Search PubMed for papers matching query.

        Returns:
            List of PubMed IDs (PMIDs)
        """
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance"
        }
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            time.sleep(self.rate_limit_delay)  # Rate limiting
            response = requests.get(self.ESEARCH_URL, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            pmids = data.get("esearchresult", {}).get("idlist", [])
            return pmids

        except Exception as e:
            print(f"[PubMed] Search error: {e}")
            return []

    async def _fetch_papers(self, pmids: List[str], since: Optional[datetime] = None) -> List[Document]:
        """
        Fetch detailed metadata and abstracts for papers.

        Args:
            pmids: List of PubMed IDs to fetch
            since: Filter papers published after this date

        Returns:
            List of Document objects
        """
        documents = []
        batch_size = 100  # Fetch 100 papers at a time

        for i in range(0, len(pmids), batch_size):
            batch_pmids = pmids[i:i + batch_size]
            print(f"[PubMed] Fetching papers {i+1}-{min(i+batch_size, len(pmids))} of {len(pmids)}")

            params = {
                "db": "pubmed",
                "id": ",".join(batch_pmids),
                "retmode": "xml",
                "rettype": "abstract"
            }
            if self.api_key:
                params["api_key"] = self.api_key

            try:
                time.sleep(self.rate_limit_delay)  # Rate limiting
                response = requests.get(self.EFETCH_URL, params=params, timeout=60)
                response.raise_for_status()

                # Parse XML response
                batch_docs = self._parse_pubmed_xml(response.text, since)
                documents.extend(batch_docs)

            except Exception as e:
                print(f"[PubMed] Error fetching batch {i//batch_size + 1}: {e}")
                continue

        return documents

    def _parse_pubmed_xml(self, xml_text: str, since: Optional[datetime] = None) -> List[Document]:
        """
        Parse PubMed XML response into Document objects.

        Args:
            xml_text: XML response from EFetch
            since: Filter papers published after this date

        Returns:
            List of Document objects
        """
        documents = []

        try:
            root = ET.fromstring(xml_text)

            for article in root.findall(".//PubmedArticle"):
                try:
                    doc = self._parse_article(article)
                    if doc:
                        # Filter by date if specified
                        if since and doc.timestamp and doc.timestamp < since:
                            continue
                        documents.append(doc)
                except Exception as e:
                    print(f"[PubMed] Error parsing article: {e}")
                    continue

        except Exception as e:
            print(f"[PubMed] XML parsing error: {e}")

        return documents

    def _parse_article(self, article_elem) -> Optional[Document]:
        """Parse a single PubmedArticle XML element"""
        try:
            # Extract PMID
            pmid_elem = article_elem.find(".//PMID")
            if pmid_elem is None:
                return None
            pmid = pmid_elem.text

            # Extract title
            title_elem = article_elem.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else "Untitled"

            # Extract abstract
            abstract_parts = []
            for abstract_text in article_elem.findall(".//AbstractText"):
                label = abstract_text.get("Label", "")
                text = abstract_text.text or ""
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
            abstract = "\n\n".join(abstract_parts) if abstract_parts else ""

            # Extract authors
            authors = []
            for author in article_elem.findall(".//Author"):
                last_name = author.find(".//LastName")
                fore_name = author.find(".//ForeName")
                if last_name is not None:
                    name = last_name.text
                    if fore_name is not None:
                        name = f"{fore_name.text} {name}"
                    authors.append(name)
            author_str = ", ".join(authors[:5])  # First 5 authors
            if len(authors) > 5:
                author_str += " et al."

            # Extract journal
            journal_elem = article_elem.find(".//Journal/Title")
            journal = journal_elem.text if journal_elem is not None else "Unknown Journal"

            # Extract publication date
            pub_date = None
            year_elem = article_elem.find(".//PubDate/Year")
            month_elem = article_elem.find(".//PubDate/Month")
            day_elem = article_elem.find(".//PubDate/Day")

            if year_elem is not None:
                try:
                    year = int(year_elem.text)
                    month = self._parse_month(month_elem.text) if month_elem is not None else 1
                    day = int(day_elem.text) if day_elem is not None and day_elem.text.isdigit() else 1
                    pub_date = datetime(year, month, day)
                except (ValueError, TypeError):
                    pass

            # Extract keywords
            keywords = []
            for keyword in article_elem.findall(".//Keyword"):
                if keyword.text:
                    keywords.append(keyword.text)

            # Extract DOI
            doi = None
            for article_id in article_elem.findall(".//ArticleId"):
                if article_id.get("IdType") == "doi":
                    doi = article_id.text
                    break

            # Build full content text
            content_parts = [
                f"Title: {title}",
                f"\nAuthors: {author_str}",
                f"\nJournal: {journal}",
            ]
            if pub_date:
                content_parts.append(f"\nPublished: {pub_date.strftime('%Y-%m-%d')}")
            if keywords:
                content_parts.append(f"\nKeywords: {', '.join(keywords)}")
            if doi:
                content_parts.append(f"\nDOI: {doi}")
            if abstract:
                content_parts.append(f"\n\nAbstract:\n{abstract}")

            content = "\n".join(content_parts)

            # Build URL
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            # Create Document
            return Document(
                doc_id=f"pubmed_{pmid}",
                source="pubmed",
                content=content,
                title=title,
                metadata={
                    "pmid": pmid,
                    "journal": journal,
                    "authors": authors,
                    "keywords": keywords,
                    "doi": doi,
                    "abstract_length": len(abstract)
                },
                timestamp=pub_date or datetime.now(),
                author=author_str,
                url=url,
                doc_type="research_paper"
            )

        except Exception as e:
            print(f"[PubMed] Error parsing article: {e}")
            return None

    def _parse_month(self, month_str: str) -> int:
        """Convert month name/abbreviation to number"""
        month_map = {
            "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
            "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
            "January": 1, "February": 2, "March": 3, "April": 4,
            "June": 6, "July": 7, "August": 8, "September": 9,
            "October": 10, "November": 11, "December": 12
        }
        return month_map.get(month_str, 1)

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a specific paper by PMID"""
        if not doc_id.startswith("pubmed_"):
            return None

        pmid = doc_id.replace("pubmed_", "")
        docs = await self._fetch_papers([pmid])
        return docs[0] if docs else None

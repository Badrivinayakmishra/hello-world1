"""
Slack Knowledge Connector
Enhanced Slack connector that creates Knowledge Cards from conversations.

Architecture:
- Groups messages into threads/conversations to create "Knowledge Cards"
- Each card preserves full context for better RAG accuracy
- Implements light noise filtering
- Downloads and processes images using GPT-4o Vision
- Handles document attachments
- Supports full history sync + 24-hour incremental sync
"""

import os
import re
import base64
import hashlib
import tempfile
import httpx
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field

from .base_connector import BaseConnector, ConnectorConfig, ConnectorStatus, Document

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False


# Noise filter patterns - messages to skip
NOISE_PATTERNS = [
    r'^ok$', r'^okay$', r'^k$', r'^kk$',
    r'^thanks$', r'^thank you$', r'^thx$', r'^ty$',
    r'^yes$', r'^yep$', r'^yeah$', r'^ya$',
    r'^no$', r'^nope$', r'^nah$',
    r'^hi$', r'^hey$', r'^hello$',
    r'^bye$', r'^goodbye$',
    r'^lol$', r'^haha$', r'^hehe$',
    r'^\+1$', r'^:thumbsup:$', r'^:white_check_mark:$',
    r'^\ud83d\udc4d$',  # thumbs up emoji
    r'^sounds good$', r'^sounds great$',
    r'^got it$', r'^cool$', r'^nice$',
    r'^np$', r'^no problem$', r'^no worries$',
]

# Minimum content requirements
MIN_MESSAGE_LENGTH = 10  # Characters
MIN_CARD_MESSAGES = 2  # Minimum messages to form a card
MIN_CARD_CONTENT_LENGTH = 50  # Minimum total content for a card


@dataclass
class SlackMessage:
    """Represents a single Slack message"""
    ts: str
    user_id: str
    user_name: str
    text: str
    thread_ts: Optional[str] = None
    is_reply: bool = False
    files: List[Dict] = field(default_factory=list)
    attachments: List[Dict] = field(default_factory=list)
    reactions: List[Dict] = field(default_factory=list)
    timestamp: Optional[datetime] = None


@dataclass
class KnowledgeCard:
    """
    A Knowledge Card represents a grouped conversation that preserves context.

    Cards are created from:
    - Thread conversations (parent + all replies)
    - Standalone messages with significant content
    - Time-grouped messages in a channel (messages within 30 min of each other)
    """
    card_id: str
    channel_id: str
    channel_name: str
    title: str
    summary: str
    full_content: str
    participants: List[str]
    message_count: int
    timestamp_start: datetime
    timestamp_end: datetime
    files: List[Dict] = field(default_factory=list)
    image_descriptions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SlackKnowledgeConnector(BaseConnector):
    """
    Enhanced Slack connector that creates Knowledge Cards.

    Key differences from basic connector:
    - Groups messages into contextual Knowledge Cards
    - Filters noise (ok, thanks, etc.)
    - Downloads and processes images/files
    - Public + Private channels only (no DMs by default)
    - Full history + incremental sync support
    """

    CONNECTOR_TYPE = "slack_knowledge"
    REQUIRED_CREDENTIALS = ["access_token"]
    OPTIONAL_SETTINGS = {
        "channels": [],  # Channel IDs to sync (empty = all accessible)
        "include_dms": False,  # NO DMs by default
        "include_threads": True,
        "include_archived": False,
        "max_messages_per_channel": 10000,  # Higher limit for full history
        "sync_all_history": True,  # Full history on first sync
        "incremental_hours": 24,  # Hours back for incremental sync
        "process_images": True,  # Use GPT-4o Vision
        "download_files": True,  # Download and index file content
        "noise_filter_enabled": True,
        "min_card_messages": MIN_CARD_MESSAGES,
        "min_card_content_length": MIN_CARD_CONTENT_LENGTH,
    }

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.client: Optional[WebClient] = None
        self.user_cache: Dict[str, str] = {}
        self.channel_cache: Dict[str, Dict] = {}
        self.vision_processor = None

    async def connect(self) -> bool:
        """Connect to Slack API"""
        if not SLACK_AVAILABLE:
            self._set_error("Slack SDK not installed. Run: pip install slack_sdk")
            return False

        try:
            self.status = ConnectorStatus.CONNECTING

            token = self.config.credentials.get("access_token") or \
                    self.config.credentials.get("bot_token")
            self.client = WebClient(token=token)

            # Test connection
            response = self.client.auth_test()

            if response["ok"]:
                self.sync_stats["team"] = response.get("team")
                self.sync_stats["team_id"] = response.get("team_id")
                self.sync_stats["user"] = response.get("user")
                self.status = ConnectorStatus.CONNECTED
                self._clear_error()

                # Initialize vision processor if enabled
                if self.config.settings.get("process_images", True):
                    try:
                        from src.rag.multimodal import MultiModalProcessor
                        self.vision_processor = MultiModalProcessor()
                    except ImportError:
                        print("Warning: MultiModalProcessor not available, images won't be processed")

                return True
            else:
                self._set_error("Auth test failed")
                return False

        except SlackApiError as e:
            self._set_error(f"Slack API error: {e.response['error']}")
            return False
        except Exception as e:
            self._set_error(f"Failed to connect: {str(e)}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect from Slack API"""
        self.client = None
        self.status = ConnectorStatus.DISCONNECTED
        return True

    async def test_connection(self) -> bool:
        """Test Slack connection"""
        if not self.client:
            return False
        try:
            response = self.client.auth_test()
            return response["ok"]
        except Exception:
            return False

    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        """
        Sync messages and create Knowledge Cards.

        Args:
            since: If provided, only sync messages after this time.
                   If None and sync_all_history=True, sync entire history.
                   Otherwise sync last incremental_hours (default 24h).
        """
        if not self.client:
            await self.connect()

        if self.status != ConnectorStatus.CONNECTED:
            return []

        self.status = ConnectorStatus.SYNCING
        documents = []

        try:
            # Determine oldest timestamp
            oldest = self._calculate_oldest_timestamp(since)

            # Get channels to sync
            channels = await self._get_channels()
            self.sync_stats["channels_found"] = len(channels)

            for channel in channels:
                try:
                    # Get all messages from channel
                    messages = await self._fetch_channel_messages(channel, oldest)

                    # Group messages into Knowledge Cards
                    cards = await self._create_knowledge_cards(messages, channel)

                    # Convert cards to documents
                    for card in cards:
                        doc = self._card_to_document(card)
                        if doc:
                            documents.append(doc)

                except Exception as e:
                    print(f"Error syncing channel {channel.get('name')}: {e}")
                    continue

            # Update stats
            self.sync_stats["documents_synced"] = len(documents)
            self.sync_stats["channels_synced"] = len(channels)
            self.sync_stats["sync_time"] = datetime.now(timezone.utc).isoformat()
            self.sync_stats["oldest_synced"] = oldest.isoformat() if oldest else "all_history"

            self.config.last_sync = datetime.now(timezone.utc)
            self.status = ConnectorStatus.CONNECTED

        except Exception as e:
            self._set_error(f"Sync failed: {str(e)}")

        return documents

    def _calculate_oldest_timestamp(self, since: Optional[datetime]) -> Optional[datetime]:
        """Calculate the oldest timestamp to sync from"""
        if since:
            return since

        # Check if this is first sync and full history is enabled
        is_first_sync = self.config.last_sync is None
        sync_all = self.config.settings.get("sync_all_history", True)

        if is_first_sync and sync_all:
            return None  # Sync all history

        # Incremental sync
        hours = self.config.settings.get("incremental_hours", 24)
        return datetime.now(timezone.utc) - timedelta(hours=hours)

    async def _get_channels(self) -> List[Dict]:
        """Get list of channels to sync (public + private only)"""
        channels = []
        configured_channels = self.config.settings.get("channels", [])
        include_archived = self.config.settings.get("include_archived", False)

        try:
            # Get public and private channels
            cursor = None
            while True:
                kwargs = {
                    "types": "public_channel,private_channel",
                    "exclude_archived": not include_archived,
                    "limit": 200,
                }
                if cursor:
                    kwargs["cursor"] = cursor

                response = self.client.conversations_list(**kwargs)

                for channel in response.get("channels", []):
                    # Filter by configured channels if specified
                    if configured_channels and channel["id"] not in configured_channels:
                        continue

                    # Must be a member to read messages
                    if channel.get("is_member"):
                        channel_info = {
                            "id": channel["id"],
                            "name": channel.get("name", "Unknown"),
                            "type": "private" if channel.get("is_private") else "public",
                            "topic": channel.get("topic", {}).get("value", ""),
                            "purpose": channel.get("purpose", {}).get("value", ""),
                            "member_count": channel.get("num_members", 0),
                        }
                        channels.append(channel_info)
                        self.channel_cache[channel["id"]] = channel_info

                # Pagination
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            # Add DMs if enabled (default: disabled)
            if self.config.settings.get("include_dms", False):
                dm_channels = await self._get_dm_channels()
                channels.extend(dm_channels)

        except SlackApiError as e:
            self._set_error(f"Failed to get channels: {e.response['error']}")

        return channels

    async def _get_dm_channels(self) -> List[Dict]:
        """Get DM channels (disabled by default)"""
        channels = []
        try:
            response = self.client.conversations_list(types="im")
            for dm in response.get("channels", []):
                user_name = await self._get_user_name(dm.get("user", "Unknown"))
                channels.append({
                    "id": dm["id"],
                    "name": f"DM: {user_name}",
                    "type": "dm",
                })
        except SlackApiError:
            pass
        return channels

    async def _fetch_channel_messages(
        self,
        channel: Dict,
        oldest: Optional[datetime] = None
    ) -> List[SlackMessage]:
        """Fetch all messages from a channel"""
        messages = []
        max_messages = self.config.settings.get("max_messages_per_channel", 10000)

        try:
            cursor = None
            oldest_ts = str(oldest.timestamp()) if oldest else None

            while len(messages) < max_messages:
                kwargs = {
                    "channel": channel["id"],
                    "limit": min(200, max_messages - len(messages)),
                }
                if oldest_ts:
                    kwargs["oldest"] = oldest_ts
                if cursor:
                    kwargs["cursor"] = cursor

                response = self.client.conversations_history(**kwargs)

                for msg in response.get("messages", []):
                    slack_msg = await self._parse_message(msg, channel)
                    if slack_msg and self._passes_noise_filter(slack_msg):
                        messages.append(slack_msg)

                        # Fetch thread replies if message has replies
                        if msg.get("reply_count", 0) > 0:
                            thread_messages = await self._fetch_thread_replies(
                                channel, msg["ts"]
                            )
                            messages.extend(thread_messages)

                # Pagination
                if response.get("has_more"):
                    cursor = response.get("response_metadata", {}).get("next_cursor")
                    if not cursor:
                        break
                else:
                    break

        except SlackApiError as e:
            print(f"Error fetching messages from {channel['name']}: {e.response['error']}")

        return messages

    async def _fetch_thread_replies(
        self,
        channel: Dict,
        thread_ts: str
    ) -> List[SlackMessage]:
        """Fetch all replies in a thread"""
        replies = []

        try:
            response = self.client.conversations_replies(
                channel=channel["id"],
                ts=thread_ts,
            )

            # Skip first message (parent) - only get replies
            for msg in response.get("messages", [])[1:]:
                slack_msg = await self._parse_message(msg, channel, is_reply=True)
                if slack_msg and self._passes_noise_filter(slack_msg):
                    replies.append(slack_msg)

        except SlackApiError:
            pass

        return replies

    async def _parse_message(
        self,
        msg: Dict,
        channel: Dict,
        is_reply: bool = False
    ) -> Optional[SlackMessage]:
        """Parse a raw Slack message into a SlackMessage object"""
        try:
            # Skip system messages
            subtype = msg.get("subtype")
            if subtype in ["channel_join", "channel_leave", "channel_topic",
                          "channel_purpose", "channel_archive", "channel_unarchive"]:
                return None

            # Skip bot messages unless they have useful content
            if subtype == "bot_message" and not msg.get("text"):
                return None

            user_id = msg.get("user") or msg.get("bot_id", "Unknown")
            user_name = await self._get_user_name(user_id)

            # Parse timestamp
            ts = float(msg.get("ts", 0))
            timestamp = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None

            # Get and clean text
            text = msg.get("text", "")
            text = await self._replace_user_mentions(text)
            text = self._clean_message_text(text)

            # Parse files
            files = []
            for f in msg.get("files", []):
                files.append({
                    "id": f.get("id"),
                    "name": f.get("name"),
                    "type": f.get("filetype"),
                    "mimetype": f.get("mimetype"),
                    "url_private": f.get("url_private"),
                    "is_image": f.get("mimetype", "").startswith("image/"),
                })

            # Parse attachments
            attachments = []
            for att in msg.get("attachments", []):
                attachments.append({
                    "title": att.get("title"),
                    "text": att.get("text"),
                    "url": att.get("title_link") or att.get("original_url"),
                })

            return SlackMessage(
                ts=msg.get("ts"),
                user_id=user_id,
                user_name=user_name,
                text=text,
                thread_ts=msg.get("thread_ts"),
                is_reply=is_reply,
                files=files,
                attachments=attachments,
                reactions=msg.get("reactions", []),
                timestamp=timestamp,
            )

        except Exception as e:
            print(f"Error parsing message: {e}")
            return None

    def _passes_noise_filter(self, msg: SlackMessage) -> bool:
        """Check if message passes the noise filter"""
        if not self.config.settings.get("noise_filter_enabled", True):
            return True

        text = msg.text.strip().lower()

        # Check minimum length
        if len(text) < MIN_MESSAGE_LENGTH:
            # Allow if has files or attachments
            if not msg.files and not msg.attachments:
                return False

        # Check noise patterns
        for pattern in NOISE_PATTERNS:
            if re.match(pattern, text, re.IGNORECASE):
                return False

        return True

    def _clean_message_text(self, text: str) -> str:
        """Clean message text (remove Slack formatting, etc.)"""
        # Convert Slack links: <http://url|text> -> text (url)
        text = re.sub(r'<(https?://[^|>]+)\|([^>]+)>', r'\2 (\1)', text)
        # Convert plain links: <http://url> -> url
        text = re.sub(r'<(https?://[^>]+)>', r'\1', text)
        # Remove channel references: <#C123|channel-name> -> #channel-name
        text = re.sub(r'<#[A-Z0-9]+\|([^>]+)>', r'#\1', text)
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    async def _create_knowledge_cards(
        self,
        messages: List[SlackMessage],
        channel: Dict
    ) -> List[KnowledgeCard]:
        """
        Create Knowledge Cards from messages.

        Strategy:
        1. Group by thread (thread_ts)
        2. For non-threaded messages, group by time proximity (30 min window)
        3. Create card with full context and summary
        """
        cards = []

        # Separate threaded and non-threaded messages
        threads: Dict[str, List[SlackMessage]] = {}
        standalone: List[SlackMessage] = []

        for msg in messages:
            if msg.thread_ts:
                if msg.thread_ts not in threads:
                    threads[msg.thread_ts] = []
                threads[msg.thread_ts].append(msg)
            else:
                standalone.append(msg)

        # Create cards from threads
        for thread_ts, thread_msgs in threads.items():
            card = await self._create_card_from_thread(thread_msgs, channel)
            if card:
                cards.append(card)

        # Group standalone messages by time proximity and create cards
        time_groups = self._group_messages_by_time(standalone, minutes=30)
        for group in time_groups:
            if len(group) >= self.config.settings.get("min_card_messages", MIN_CARD_MESSAGES):
                card = await self._create_card_from_group(group, channel)
                if card:
                    cards.append(card)
            else:
                # Single significant messages become their own cards
                for msg in group:
                    if len(msg.text) >= 200 or msg.files:  # Significant standalone message
                        card = await self._create_card_from_message(msg, channel)
                        if card:
                            cards.append(card)

        return cards

    def _group_messages_by_time(
        self,
        messages: List[SlackMessage],
        minutes: int = 30
    ) -> List[List[SlackMessage]]:
        """Group messages that are within `minutes` of each other"""
        if not messages:
            return []

        # Sort by timestamp
        sorted_msgs = sorted(
            [m for m in messages if m.timestamp],
            key=lambda m: m.timestamp
        )

        if not sorted_msgs:
            return []

        groups = []
        current_group = [sorted_msgs[0]]

        for msg in sorted_msgs[1:]:
            time_diff = (msg.timestamp - current_group[-1].timestamp).total_seconds() / 60

            if time_diff <= minutes:
                current_group.append(msg)
            else:
                groups.append(current_group)
                current_group = [msg]

        groups.append(current_group)
        return groups

    async def _create_card_from_thread(
        self,
        messages: List[SlackMessage],
        channel: Dict
    ) -> Optional[KnowledgeCard]:
        """Create a Knowledge Card from a thread conversation"""
        if not messages:
            return None

        # Sort by timestamp
        messages = sorted(
            [m for m in messages if m.timestamp],
            key=lambda m: m.timestamp
        )

        if not messages:
            return None

        # Build conversation content
        participants = list(set(m.user_name for m in messages))

        conversation_lines = []
        all_files = []
        image_descriptions = []

        for msg in messages:
            prefix = "[Reply] " if msg.is_reply else ""
            conversation_lines.append(
                f"{prefix}{msg.user_name}: {msg.text}"
            )

            # Collect files
            all_files.extend(msg.files)

            # Process images
            for f in msg.files:
                if f.get("is_image") and self.vision_processor:
                    desc = await self._process_image(f)
                    if desc:
                        image_descriptions.append(desc)
                        conversation_lines.append(f"[Image: {desc}]")

        full_content = "\n".join(conversation_lines)

        # Check minimum content
        if len(full_content) < self.config.settings.get("min_card_content_length", MIN_CARD_CONTENT_LENGTH):
            return None

        # Generate title and summary
        title = self._generate_title(messages[0].text, channel["name"])
        summary = self._generate_summary(full_content, participants)

        # Create card ID
        card_id = self._generate_card_id(channel["id"], messages[0].ts)

        return KnowledgeCard(
            card_id=card_id,
            channel_id=channel["id"],
            channel_name=channel["name"],
            title=title,
            summary=summary,
            full_content=full_content,
            participants=participants,
            message_count=len(messages),
            timestamp_start=messages[0].timestamp,
            timestamp_end=messages[-1].timestamp,
            files=all_files,
            image_descriptions=image_descriptions,
            metadata={
                "thread_ts": messages[0].thread_ts or messages[0].ts,
                "channel_type": channel.get("type", "public"),
                "has_images": len(image_descriptions) > 0,
                "has_files": len([f for f in all_files if not f.get("is_image")]) > 0,
            }
        )

    async def _create_card_from_group(
        self,
        messages: List[SlackMessage],
        channel: Dict
    ) -> Optional[KnowledgeCard]:
        """Create a Knowledge Card from a time-grouped set of messages"""
        return await self._create_card_from_thread(messages, channel)

    async def _create_card_from_message(
        self,
        msg: SlackMessage,
        channel: Dict
    ) -> Optional[KnowledgeCard]:
        """Create a Knowledge Card from a single significant message"""
        return await self._create_card_from_thread([msg], channel)

    async def _process_image(self, file_info: Dict) -> Optional[str]:
        """Download and process an image using GPT-4o Vision"""
        if not self.vision_processor:
            return None

        try:
            # Download image
            url = file_info.get("url_private")
            if not url:
                return None

            # Use Slack token for authentication
            token = self.config.credentials.get("access_token") or \
                    self.config.credentials.get("bot_token")

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    follow_redirects=True,
                )

                if response.status_code != 200:
                    return None

                # Save to temp file
                with tempfile.NamedTemporaryFile(suffix=f".{file_info.get('type', 'png')}", delete=False) as f:
                    f.write(response.content)
                    temp_path = f.name

            # Process with vision
            result = self.vision_processor.analyze_image(
                image_path=temp_path,
                prompt="Describe this image in detail. What does it show? Extract any text, data, or key information visible.",
                context="This is an image shared in a Slack conversation."
            )

            # Clean up temp file
            os.unlink(temp_path)

            return result.get("description") or result.get("extracted_text", "")

        except Exception as e:
            print(f"Error processing image: {e}")
            return None

    def _generate_title(self, first_message: str, channel_name: str) -> str:
        """Generate a title for the Knowledge Card"""
        # Take first 60 chars of first message
        title = first_message[:60].strip()
        if len(first_message) > 60:
            title += "..."
        return f"#{channel_name}: {title}"

    def _generate_summary(self, content: str, participants: List[str]) -> str:
        """Generate a summary of the conversation"""
        # Simple summary: participant count + first 200 chars
        participant_str = ", ".join(participants[:3])
        if len(participants) > 3:
            participant_str += f" +{len(participants) - 3} more"

        preview = content[:200].strip()
        if len(content) > 200:
            preview += "..."

        return f"Conversation with {participant_str}\n\n{preview}"

    def _generate_card_id(self, channel_id: str, ts: str) -> str:
        """Generate a unique card ID"""
        raw = f"slack_{channel_id}_{ts}"
        return f"slack_card_{hashlib.md5(raw.encode()).hexdigest()[:12]}"

    def _card_to_document(self, card: KnowledgeCard) -> Optional[Document]:
        """Convert a Knowledge Card to a Document for indexing"""
        try:
            # Build rich content with context
            content = f"""# {card.title}

**Channel:** #{card.channel_name}
**Participants:** {', '.join(card.participants)}
**Messages:** {card.message_count}
**Time:** {card.timestamp_start.strftime('%Y-%m-%d %H:%M')} - {card.timestamp_end.strftime('%Y-%m-%d %H:%M')}

## Summary
{card.summary}

## Full Conversation
{card.full_content}
"""

            # Add image descriptions if any
            if card.image_descriptions:
                content += "\n\n## Images\n"
                for i, desc in enumerate(card.image_descriptions, 1):
                    content += f"\n**Image {i}:** {desc}\n"

            return Document(
                doc_id=card.card_id,
                source="slack",
                content=content,
                title=card.title,
                metadata={
                    "card_type": "knowledge_card",
                    "channel_id": card.channel_id,
                    "channel_name": card.channel_name,
                    "channel_type": card.metadata.get("channel_type", "public"),
                    "participants": card.participants,
                    "message_count": card.message_count,
                    "thread_ts": card.metadata.get("thread_ts"),
                    "has_images": card.metadata.get("has_images", False),
                    "has_files": card.metadata.get("has_files", False),
                    "image_count": len(card.image_descriptions),
                    "file_count": len(card.files),
                },
                timestamp=card.timestamp_end,
                author=card.participants[0] if card.participants else "Unknown",
                doc_type="slack_knowledge_card",
            )

        except Exception as e:
            print(f"Error converting card to document: {e}")
            return None

    async def _get_user_name(self, user_id: str) -> str:
        """Get display name for a user ID with caching"""
        if user_id in self.user_cache:
            return self.user_cache[user_id]

        try:
            response = self.client.users_info(user=user_id)
            if response["ok"]:
                user = response["user"]
                name = user.get("real_name") or user.get("name") or user_id
                self.user_cache[user_id] = name
                return name
        except SlackApiError:
            pass

        self.user_cache[user_id] = user_id
        return user_id

    async def _replace_user_mentions(self, text: str) -> str:
        """Replace <@USER_ID> mentions with display names"""
        pattern = r'<@([A-Z0-9]+)>'
        matches = re.findall(pattern, text)

        for user_id in matches:
            name = await self._get_user_name(user_id)
            text = text.replace(f"<@{user_id}>", f"@{name}")

        return text

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a specific Knowledge Card by ID"""
        # Would need to reconstruct from stored data
        # For now, return None as we don't cache cards
        return None

    async def get_available_channels(self) -> List[Dict]:
        """Get list of available channels for configuration"""
        if not self.client:
            await self.connect()

        if self.status != ConnectorStatus.CONNECTED:
            return []

        channels = []
        try:
            cursor = None
            while True:
                kwargs = {
                    "types": "public_channel,private_channel",
                    "exclude_archived": True,
                    "limit": 200,
                }
                if cursor:
                    kwargs["cursor"] = cursor

                response = self.client.conversations_list(**kwargs)

                for channel in response.get("channels", []):
                    channels.append({
                        "id": channel["id"],
                        "name": channel.get("name", "Unknown"),
                        "is_private": channel.get("is_private", False),
                        "is_member": channel.get("is_member", False),
                        "member_count": channel.get("num_members", 0),
                        "topic": channel.get("topic", {}).get("value", ""),
                        "purpose": channel.get("purpose", {}).get("value", ""),
                    })

                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

        except SlackApiError as e:
            print(f"Error getting channels: {e.response['error']}")

        return channels

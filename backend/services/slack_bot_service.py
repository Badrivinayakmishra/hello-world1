"""
Slack Bot Service
Handles Slack bot interactions, commands, and search functionality.
"""

import os
from typing import Dict, Optional, List
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from database.models import get_db
from services.enhanced_search_service import EnhancedSearchService


class SlackBotService:
    """Service for handling Slack bot interactions"""

    def __init__(self, bot_token: str):
        """
        Initialize Slack bot service.

        Args:
            bot_token: Slack bot OAuth token
        """
        self.client = WebClient(token=bot_token)
        self.bot_user_id = None
        self._init_bot_user()

    def _init_bot_user(self):
        """Get bot user ID"""
        try:
            response = self.client.auth_test()
            self.bot_user_id = response['user_id']
            print(f"[SlackBot] Initialized as {response['user']} (ID: {self.bot_user_id})", flush=True)
        except SlackApiError as e:
            print(f"[SlackBot] Error initializing: {e}", flush=True)

    def handle_ask_command(
        self,
        tenant_id: str,
        user_id: str,
        channel_id: str,
        query: str,
        response_url: Optional[str] = None
    ) -> Dict:
        """
        Handle /ask slash command.

        Args:
            tenant_id: Tenant ID from workspace mapping
            user_id: Slack user ID
            channel_id: Slack channel ID
            query: Search query
            response_url: Optional webhook URL for delayed response

        Returns:
            dict: Slack message response
        """
        try:
            # Show immediate "searching..." message
            if response_url:
                self._send_ephemeral_message(
                    channel_id,
                    user_id,
                    "🔍 Searching knowledge base..."
                )

            # Perform search
            db = next(get_db())
            try:
                search_service = EnhancedSearchService(db)

                result = search_service.search(
                    query=query,
                    tenant_id=tenant_id,
                    top_k=5,
                    use_enhanced=True
                )

                # Format response for Slack
                if result['success'] and result.get('answer'):
                    blocks = self._format_search_results(query, result)
                    return {
                        'response_type': 'in_channel',  # Visible to everyone
                        'blocks': blocks
                    }
                else:
                    return {
                        'response_type': 'ephemeral',  # Only visible to user
                        'text': f"❌ No results found for: _{query}_\n\nTry:\n• Adding more documents to your knowledge base\n• Using different keywords\n• Checking if documents are indexed"
                    }

            finally:
                db.close()

        except Exception as e:
            print(f"[SlackBot] Error handling /ask: {e}", flush=True)
            return {
                'response_type': 'ephemeral',
                'text': f"❌ Error searching: {str(e)}"
            }

    def handle_app_mention(
        self,
        tenant_id: str,
        event: Dict
    ) -> Optional[Dict]:
        """
        Handle @2ndBrain mentions in channels.

        Args:
            tenant_id: Tenant ID
            event: Slack event data

        Returns:
            Optional response dict
        """
        try:
            channel = event.get('channel')
            user = event.get('user')
            text = event.get('text', '')

            # Remove bot mention from text
            query = text.replace(f'<@{self.bot_user_id}>', '').strip()

            if not query:
                return {
                    'channel': channel,
                    'text': "Hi! 👋 Ask me a question about your knowledge base. Example: `@2ndBrain What is our pricing model?`"
                }

            # Perform search
            db = next(get_db())
            try:
                search_service = EnhancedSearchService(db)

                result = search_service.search(
                    query=query,
                    tenant_id=tenant_id,
                    top_k=5
                )

                if result['success'] and result.get('answer'):
                    # Post result in thread
                    blocks = self._format_search_results(query, result, compact=True)

                    self.client.chat_postMessage(
                        channel=channel,
                        text=result['answer'][:100] + '...',  # Fallback text
                        blocks=blocks,
                        thread_ts=event.get('ts')  # Reply in thread
                    )
                else:
                    self.client.chat_postMessage(
                        channel=channel,
                        text=f"❌ No results found for: _{query}_",
                        thread_ts=event.get('ts')
                    )

            finally:
                db.close()

        except Exception as e:
            print(f"[SlackBot] Error handling mention: {e}", flush=True)
            return None

    def handle_message(
        self,
        tenant_id: str,
        event: Dict
    ) -> Optional[Dict]:
        """
        Handle direct messages to bot.

        Args:
            tenant_id: Tenant ID
            event: Slack event data

        Returns:
            Optional response
        """
        try:
            channel = event.get('channel')
            user = event.get('user')
            text = event.get('text', '').strip()

            # Ignore bot messages
            if event.get('bot_id') or user == self.bot_user_id:
                return None

            # Check if it's a DM (channel starts with 'D')
            if not channel.startswith('D'):
                return None  # Only handle DMs here

            if not text:
                return None

            # Perform search
            db = next(get_db())
            try:
                search_service = EnhancedSearchService(db)

                result = search_service.search(
                    query=text,
                    tenant_id=tenant_id,
                    top_k=5
                )

                if result['success'] and result.get('answer'):
                    blocks = self._format_search_results(text, result, compact=True)

                    self.client.chat_postMessage(
                        channel=channel,
                        text=result['answer'][:100] + '...',
                        blocks=blocks
                    )
                else:
                    self.client.chat_postMessage(
                        channel=channel,
                        text=f"❌ No results found for: _{text}_"
                    )

            finally:
                db.close()

        except Exception as e:
            print(f"[SlackBot] Error handling message: {e}", flush=True)
            return None

    def _format_search_results(
        self,
        query: str,
        result: Dict,
        compact: bool = False
    ) -> List[Dict]:
        """
        Format search results as Slack blocks.

        Args:
            query: Original query
            result: Search result from EnhancedSearchService
            compact: If True, use compact format

        Returns:
            list: Slack block kit blocks
        """
        blocks = []

        # Header
        blocks.append({
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': f"*🔍 Results for:* _{query}_"
            }
        })

        blocks.append({'type': 'divider'})

        # Answer
        answer = result.get('answer', 'No answer available')
        answer_chunks = self._chunk_text(answer, 3000)  # Slack limit

        for chunk in answer_chunks:
            blocks.append({
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': chunk
                }
            })

        # Sources (if not compact)
        if not compact and result.get('sources'):
            blocks.append({'type': 'divider'})

            sources_text = "*📚 Sources:*\n"
            for idx, source in enumerate(result['sources'][:3], 1):
                title = source.get('title', 'Untitled')
                doc_type = source.get('source', 'document')
                sources_text += f"{idx}. {title} (_from {doc_type}_)\n"

            blocks.append({
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': sources_text
                }
            })

        # Confidence & Features (if available)
        if result.get('hallucination_check') and not compact:
            hallucination = result['hallucination_check']
            confidence = hallucination.get('confidence', 0)

            if confidence > 0.7:
                confidence_emoji = '✅'
            elif confidence > 0.4:
                confidence_emoji = '⚠️'
            else:
                confidence_emoji = '❌'

            blocks.append({
                'type': 'context',
                'elements': [{
                    'type': 'mrkdwn',
                    'text': f"{confidence_emoji} Confidence: {int(confidence * 100)}% | 🧠 Enhanced RAG | ⚡ Real-time"
                }]
            })

        # Web app link
        blocks.append({
            'type': 'context',
            'elements': [{
                'type': 'mrkdwn',
                'text': "<https://app.2ndbrain.io|View in Web App> | <https://app.2ndbrain.io/knowledge-gaps|Answer Knowledge Gaps>"
            }]
        })

        return blocks

    def _chunk_text(self, text: str, max_length: int = 3000) -> List[str]:
        """
        Chunk text to fit Slack message limits.

        Args:
            text: Text to chunk
            max_length: Maximum length per chunk

        Returns:
            list: Text chunks
        """
        if len(text) <= max_length:
            return [text]

        chunks = []
        current_chunk = ""

        for paragraph in text.split('\n'):
            if len(current_chunk) + len(paragraph) + 1 > max_length:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = paragraph
            else:
                current_chunk += '\n' + paragraph if current_chunk else paragraph

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _send_ephemeral_message(self, channel: str, user: str, text: str):
        """Send ephemeral message (only visible to user)"""
        try:
            self.client.chat_postEphemeral(
                channel=channel,
                user=user,
                text=text
            )
        except SlackApiError as e:
            print(f"[SlackBot] Error sending ephemeral: {e}", flush=True)

    def send_notification(
        self,
        channel: str,
        message: str,
        blocks: Optional[List[Dict]] = None
    ):
        """
        Send notification to Slack channel.

        Args:
            channel: Channel ID
            message: Text message
            blocks: Optional Slack blocks
        """
        try:
            self.client.chat_postMessage(
                channel=channel,
                text=message,
                blocks=blocks
            )
        except SlackApiError as e:
            print(f"[SlackBot] Error sending notification: {e}", flush=True)


# ============================================================================
# SLACK WORKSPACE MAPPING
# ============================================================================

# In production, store this in database
# For now, use in-memory cache
_workspace_tenant_mapping: Dict[str, str] = {}


def register_slack_workspace(team_id: str, tenant_id: str, bot_token: str):
    """
    Register Slack workspace after OAuth.

    Args:
        team_id: Slack workspace/team ID
        tenant_id: 2nd Brain tenant ID
        bot_token: Bot OAuth token
    """
    # In production: Store in database (SlackWorkspace model)
    _workspace_tenant_mapping[team_id] = tenant_id

    print(f"[SlackBot] Registered workspace {team_id} -> tenant {tenant_id}", flush=True)


def get_tenant_for_workspace(team_id: str) -> Optional[str]:
    """
    Get tenant ID for Slack workspace.

    Args:
        team_id: Slack workspace/team ID

    Returns:
        Optional tenant ID
    """
    return _workspace_tenant_mapping.get(team_id)


def get_bot_token_for_workspace(team_id: str) -> Optional[str]:
    """
    Get bot token for Slack workspace.

    Args:
        team_id: Slack workspace/team ID

    Returns:
        Optional bot token
    """
    # In production: Fetch from database
    # For now, use environment variable
    return os.getenv('SLACK_BOT_TOKEN')

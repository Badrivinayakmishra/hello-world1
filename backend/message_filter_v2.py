"""
Improved Personal Message Filter v2
Uses a multi-stage approach to minimize user review:

Strategy:
1. Rule-based fast filtering (expanded patterns)
2. Length + structure heuristics
3. GPT batch classification for truly ambiguous messages
4. Only ask user to review HIGH-VALUE uncertain messages

Goal: Reduce 17,000+ reviews to < 500
"""

import re
import os
from typing import Dict, List, Tuple
from collections import defaultdict
from openai import AzureOpenAI

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


# Initialize OpenAI client
client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        ))

# ============================================================================
# STAGE 1: DEFINITE PERSONAL MESSAGES (Auto-exclude)
# ============================================================================
DEFINITE_PERSONAL = [
    # Pure reactions / acknowledgments (< 30 chars typical)
    r'^(ok|okay|k|kk|kkkk*|okie|okayyy*|okk+)[\s!?.]*$',
    r'^(yes|yeah|yep|yup|yea|ya|yess+|yass+)[\s!?.]*$',
    r'^(no|nope|nah|na)[\s!?.]*$',
    r'^(sure|yea sure|ya sure)[\s!?.]*$',
    r'^(cool|nice|great|awesome|perfect|dope|sick|lit|bet|gotcha|gotchu)[\s!?.]*$',
    r'^(thanks|thx|ty|thank you|tysm|tyy+|thanksss*)[\s!?.]*$',
    r'^(lol|lmao|lmfao|haha|hahaha+|loll+|rofl|dead|bruh)[\s!?.]*$',
    r'^(hey|hi|hello|yo|sup|heyy+|hii+|heya)[\s!?,]*$',
    r'^(bye|cya|later|see ya|ttyl|peace)[\s!?.]*$',
    r'^(wow|omg|damn|dang|darn|oh|ooh|ahh|aw|aww)[\s!?.]*$',
    r'^(same|mood|facts|true|real|fr|frfr|ong)[\s!?.]*$',
    r'^(sounds good|sounds great|sounds fine)[\s!?.]*$',
    r'^(got it|makes sense|understood|copy|roger)[\s!?.]*$',
    r'^(np|no problem|no worries|all good|nw)[\s!?.]*$',
    r'^(sorry|my bad|oops|mb)[\s!?.]*$',
    r'^(idk|idc|idek|tbh|ngl|imo|imho)[\s!?.]*$',

    # Emojis only
    r'^[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002600-\U000027BF\s]+$',

    # Greetings with names
    r'^(hey|hi|hello|yo|sup)\s+[a-zA-Z]+[\s!?,]*$',

    # Single word exclamations
    r'^[a-zA-Z]{1,10}[!?]+$',

    # Personal scheduling (food, hangout)
    r'^(wanna|want to|lets|let\'s)\s+(grab|get|eat|have)\s+(lunch|dinner|food|coffee|drinks?)',
    r'(grab lunch|get food|eat dinner|get coffee|get drinks)',
    r'(wanna hang|let\'s chill|lets hang|want to chill)',

    # Birthday/congrats
    r'(happy birthday|happy bday|hbd|congrats|congratulations)[\s!]*$',

    # Personal status updates
    r'^(im |i\'m |i am )(tired|sleepy|hungry|bored|sick|busy|free|back|here|leaving)',
    r'^(gonna |going to )(sleep|eat|leave|shower|nap)',
    r'^(just )(woke up|ate|left|got here|arrived)',

    # Casual questions about wellbeing
    r'(how are you|hows it going|what\'s up|whats up|how\'s life|how u doing)',
    r'(you good|u good|you ok|u ok|you alright)',

    # System messages
    r'^updated room membership',
    r'^added \S+ to the room',
    r'^removed \S+ from the room',
    r'^changed the room',
    r'^joined the room',
    r'^left the room',
]

# ============================================================================
# STAGE 2: DEFINITE PROFESSIONAL MESSAGES (Auto-include)
# ============================================================================
DEFINITE_PROFESSIONAL = [
    # Contains data/numbers (financial, metrics)
    r'\$[\d,]+(\.\d+)?',  # Dollar amounts
    r'\d+%',  # Percentages
    r'\b\d{1,3}(,\d{3})+\b',  # Large numbers with commas
    r'\bTAM\b|\bSAM\b|\bSOM\b',  # Market sizing
    r'\bROI\b|\bIRR\b|\bNPV\b',  # Financial metrics
    r'\bQ[1-4]\b|\bFY\d{2}\b',  # Quarters/fiscal years

    # File sharing
    r'\.pdf|\.pptx?|\.xlsx?|\.docx?|\.csv',
    r'attached|attachment|see attached|find attached',
    r'google\s*(doc|sheet|slide|drive)',

    # URLs (usually sharing resources)
    r'https?://[^\s]+',
    r'drive\.google\.com|docs\.google\.com|sheets\.google\.com',

    # Meeting/scheduling (work context)
    r'(meeting|call|sync|standup|check-in)\s+(at|on|tomorrow|today|monday|tuesday|wednesday|thursday|friday)',
    r'(let\'s|can we|shall we)\s+(meet|call|sync|discuss|talk about)',
    r'(rescheduled?|postponed?|moved?)\s+(the|our)?\s*(meeting|call)',

    # Deliverables/work items
    r'(deliverable|milestone|deadline|due date|timeline)',
    r'(please|can you|could you)\s+(review|send|share|update|finish|complete)',
    r'(action item|todo|task|assigned|owner)',
    r'(draft|final|v\d|version)',

    # Analysis/research terms
    r'(analysis|research|data|report|findings|insights)',
    r'(market|industry|competitive|competitor)',
    r'(strategy|recommendation|proposal|solution)',

    # Project-specific terms (UCLA Health context)
    r'\b(NICU|OBED|ICU|ER|ED|UCLA|health|hospital|medical|clinical|patient)\b',
    r'\b(BEAT|consulting|client|stakeholder|sponsor)\b',
    r'\b(healthcare|pharma|biotech|medtech)\b',
]

# ============================================================================
# STAGE 3: LIKELY PERSONAL (Lean toward excluding)
# ============================================================================
LIKELY_PERSONAL = [
    # Food mentions (context dependent)
    r'\b(lunch|dinner|breakfast|brunch|food|eat|eating|hungry)\b',
    r'\b(coffee|boba|drinks?|beer|wine)\b',

    # Weekend/social
    r'\b(weekend|saturday|sunday|friday night|party|parties)\b',
    r'\b(hangout|hang out|chill|chilling|netflix|movie|game|gaming)\b',

    # Running late / excuses
    r'(running late|be there soon|on my way|omw|almost there)',
    r'(can\'t make it|won\'t be able|have to cancel)',

    # Casual address
    r'\b(bro|dude|man|guys|fam|homie)\b',
    r'\b(lmk|hmu|wyd|wya)\b',

    # Gym/personal health
    r'\b(gym|workout|exercise|run|running|lift)\b',
    r'\b(doctor|dentist|appointment)\b',

    # Off-topic
    r'\b(love you|miss you|see you soon)\b',
]

# ============================================================================
# STAGE 4: LIKELY PROFESSIONAL (Lean toward including)
# ============================================================================
LIKELY_PROFESSIONAL = [
    # Work coordination
    r'(working on|finished|completed|done with|started)',
    r'(update|progress|status|blockers?)',
    r'(team|group|everyone|all)',

    # Requests
    r'(can you|could you|would you|please)',
    r'(need|needs|require|requires)',
    r'(help|assist|support)',

    # Scheduling (generic)
    r'(tomorrow|today|this week|next week|monday|tuesday|wednesday|thursday|friday)',
    r'(meeting|call|zoom|teams)',

    # Information sharing
    r'(here\'s|here is|this is|check out|take a look)',
    r'(fyi|for your info|heads up)',
    r'(sent|sending|shared|sharing)',
]


def calculate_professional_score_v2(content: str) -> Tuple[int, str, List[str]]:
    """
    Improved scoring with definite categories.

    Returns: (score, classification, reasons)
    Classification: 'definite_personal', 'definite_professional',
                   'likely_personal', 'likely_professional', 'uncertain'
    """
    content_lower = content.lower().strip()
    content_len = len(content_lower)
    reasons = []

    # ========================================
    # STAGE 1: Check definite patterns first
    # ========================================

    # Definite personal
    for pattern in DEFINITE_PERSONAL:
        if re.search(pattern, content_lower, re.IGNORECASE):
            return (10, 'definite_personal', [f"Matched: {pattern[:30]}..."])

    # Definite professional
    for pattern in DEFINITE_PROFESSIONAL:
        if re.search(pattern, content, re.IGNORECASE):  # Case sensitive for acronyms
            return (90, 'definite_professional', [f"Matched: {pattern[:30]}..."])

    # ========================================
    # STAGE 2: Length-based heuristics
    # ========================================

    # Very short messages without professional indicators = personal
    if content_len < 25:
        # Check if it has any professional keywords
        has_professional = any(re.search(p, content_lower) for p in LIKELY_PROFESSIONAL)
        if not has_professional:
            return (20, 'likely_personal', ["Very short message without work context"])

    # Very long messages (>200 chars) are usually substantive/professional
    if content_len > 200:
        reasons.append("Long detailed message")
        # Unless they have personal patterns
        personal_count = sum(1 for p in LIKELY_PERSONAL if re.search(p, content_lower))
        if personal_count == 0:
            return (80, 'likely_professional', reasons)

    # ========================================
    # STAGE 3: Score-based classification
    # ========================================

    score = 50

    # Count pattern matches
    likely_personal_count = sum(1 for p in LIKELY_PERSONAL if re.search(p, content_lower))
    likely_professional_count = sum(1 for p in LIKELY_PROFESSIONAL if re.search(p, content_lower))

    # Adjust score
    score -= likely_personal_count * 12
    score += likely_professional_count * 10

    # Length adjustments
    if content_len < 40:
        score -= 10
        reasons.append("Short message")
    elif content_len > 100:
        score += 10
        reasons.append("Substantial length")

    # Punctuation patterns (professional messages often have proper punctuation)
    if re.search(r'\.\s+[A-Z]', content):  # Multiple sentences
        score += 10
        reasons.append("Multiple sentences")

    if re.search(r'^\d+\.|\n\d+\.', content):  # Numbered lists
        score += 15
        reasons.append("Numbered list")

    # Questions about work vs personal
    if '?' in content:
        if re.search(r'(when|what time|where|how)\s+(is|are|do|does|can|should|will)', content_lower):
            # Could be either - scheduling question
            pass
        elif re.search(r'(you|u)\s+(good|ok|free|busy|hungry|tired)', content_lower):
            score -= 15
            reasons.append("Personal check-in question")

    # Clamp score
    score = max(0, min(100, score))

    # Determine classification
    if score < 30:
        return (score, 'likely_personal', reasons)
    elif score > 70:
        return (score, 'likely_professional', reasons)
    else:
        return (score, 'uncertain', reasons)


def filter_messages_v2(messages: List[Dict], use_gpt_for_uncertain: bool = True) -> Dict:
    """
    Filter messages with improved methodology.

    Uses GPT to batch-classify truly uncertain messages.
    """
    definite_personal = []
    definite_professional = []
    likely_personal = []
    likely_professional = []
    uncertain = []

    for msg in messages:
        content = msg.get('content', '')
        if not content or len(content.strip()) < 3:
            continue

        score, classification, reasons = calculate_professional_score_v2(content)

        result = {
            'content': content[:500],
            'professional_score': score,
            'classification': classification,
            'reasons': reasons,
            'original_message': msg
        }

        if classification == 'definite_personal':
            definite_personal.append(result)
        elif classification == 'definite_professional':
            definite_professional.append(result)
        elif classification == 'likely_personal':
            likely_personal.append(result)
        elif classification == 'likely_professional':
            likely_professional.append(result)
        else:
            uncertain.append(result)

    print(f"\n📊 Initial Classification:")
    print(f"   Definite Personal: {len(definite_personal)}")
    print(f"   Likely Personal: {len(likely_personal)}")
    print(f"   Uncertain: {len(uncertain)}")
    print(f"   Likely Professional: {len(likely_professional)}")
    print(f"   Definite Professional: {len(definite_professional)}")

    # Use GPT to classify uncertain messages (this is the expensive part)
    gpt_classified = []
    if use_gpt_for_uncertain and uncertain:
        print(f"\n🤖 Using GPT to classify {len(uncertain)} uncertain messages...")
        gpt_classified = batch_classify_with_gpt_v2(uncertain)

        # Move GPT-classified messages to appropriate buckets
        for result in gpt_classified:
            if result['gpt_classification'] == 'professional':
                likely_professional.append(result)
            else:
                likely_personal.append(result)

        uncertain = []  # All classified by GPT

    # Final counts
    total_professional = len(definite_professional) + len(likely_professional)
    total_personal = len(definite_personal) + len(likely_personal)

    return {
        'professional': definite_professional + likely_professional,
        'personal': definite_personal + likely_personal,
        'needs_review': uncertain,  # Should be 0 if GPT used
        'stats': {
            'total': len(messages),
            'professional': total_professional,
            'personal': total_personal,
            'needs_review': len(uncertain),
            'gpt_classified': len(gpt_classified),
            'auto_classified_pct': round((total_professional + total_personal) / max(len(messages), 1) * 100, 1)
        },
        # Detailed breakdown for transparency
        'breakdown': {
            'definite_personal': len(definite_personal),
            'likely_personal': len(likely_personal),
            'uncertain': len(uncertain),
            'likely_professional': len(likely_professional),
            'definite_professional': len(definite_professional),
        }
    }


def batch_classify_with_gpt_v2(messages: List[Dict], batch_size: int = 50) -> List[Dict]:
    """
    Use GPT to classify uncertain messages in larger batches.
    """
    if not messages:
        return []

    results = []
    total_batches = (len(messages) + batch_size - 1) // batch_size

    for batch_num, i in enumerate(range(0, len(messages), batch_size)):
        batch = messages[i:i+batch_size]
        print(f"   Processing batch {batch_num+1}/{total_batches} ({len(batch)} messages)...")

        # Format messages compactly
        msg_texts = []
        for j, msg in enumerate(batch):
            content = msg.get('content', '')[:150].replace('\n', ' ')
            msg_texts.append(f"{j+1}. {content}")

        prompt = f"""Classify each message as WORK (work/project related) or PERSONAL (casual/social).

Context: These are messages from a consulting club's Google Chat groups. WORK includes:
- Project discussions, updates, questions
- Meeting coordination, scheduling
- File sharing, document references
- Professional requests and follow-ups

PERSONAL includes:
- Social chat, food/hangout plans
- Personal life updates
- Casual banter, jokes
- Off-topic conversations

Messages:
{chr(10).join(msg_texts)}

Reply with ONLY numbers and W or P (e.g., "1W 2P 3W 4P..."):"""

        try:
            response = client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": "Classify messages as W (work) or P (personal). Reply compactly like: 1W 2P 3W"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=len(batch) * 5
            )

            # Parse compact response
            response_text = response.choices[0].message.content.strip()
            classifications = {}

            # Parse "1W 2P 3W" or "1. W\n2. P" formats
            for match in re.finditer(r'(\d+)\s*[.:\s]*([WP])', response_text, re.IGNORECASE):
                idx = int(match.group(1))
                cls = match.group(2).upper()
                classifications[idx] = 'professional' if cls == 'W' else 'personal'

            for j, msg in enumerate(batch):
                classification = classifications.get(j+1, 'professional')  # Default to professional if parsing fails
                msg_copy = msg.copy()
                msg_copy['gpt_classification'] = classification
                msg_copy['method'] = 'gpt'
                results.append(msg_copy)

        except Exception as e:
            print(f"   ❌ GPT error: {e}")
            # Default to professional on error (conservative)
            for msg in batch:
                msg_copy = msg.copy()
                msg_copy['gpt_classification'] = 'professional'
                msg_copy['method'] = 'error'
                results.append(msg_copy)

    return results


if __name__ == "__main__":
    # Test with sample messages
    test_messages = [
        {'content': 'ok'},
        {'content': 'sounds good'},
        {'content': 'Updated room membership.'},
        {'content': 'The NICU market analysis shows a TAM of $812M'},
        {'content': 'wanna grab lunch?'},
        {'content': 'Can you review the attached proposal?'},
        {'content': 'lol'},
        {'content': 'Meeting rescheduled to 3pm tomorrow'},
        {'content': 'Bro my meeting is running late'},
        {'content': 'Here is the updated financial model for Q3'},
        {'content': 'hey'},
        {'content': 'The client requested additional competitor analysis'},
        {'content': 'So just keep us updated of what happened each week'},
        {'content': 'with the group so that we can watch it'},
        {'content': 'https://docs.google.com/presentation/d/xyz'},
    ]

    print("=" * 80)
    print("MESSAGE FILTER V2 TEST")
    print("=" * 80)

    # Test without GPT first
    results = filter_messages_v2(test_messages, use_gpt_for_uncertain=False)

    print(f"\n📊 Results (without GPT):")
    print(f"   Professional: {results['stats']['professional']}")
    print(f"   Personal: {results['stats']['personal']}")
    print(f"   Needs Review: {results['stats']['needs_review']}")
    print(f"   Auto-classified: {results['stats']['auto_classified_pct']}%")

    print(f"\n✅ PROFESSIONAL:")
    for msg in results['professional'][:5]:
        print(f"   [{msg['professional_score']}] {msg['content'][:60]}")

    print(f"\n❌ PERSONAL:")
    for msg in results['personal'][:5]:
        print(f"   [{msg['professional_score']}] {msg['content'][:60]}")

    print(f"\n⚠️ UNCERTAIN:")
    for msg in results['needs_review'][:5]:
        print(f"   [{msg['professional_score']}] {msg['content'][:60]}")

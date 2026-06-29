from openai import AsyncOpenAI
from typing import List, Dict, Any, Optional, Tuple
from config import get_settings
from database import get_admin_config
from embeddings import search

settings = get_settings()
client = AsyncOpenAI(api_key=settings.openai_api_key)

SYSTEM_PROMPT_TEMPLATE = """You are {bot_name}, an intelligent assistant for Legal Assist UK (legalassistglobal.com) — a UK-based Claims Management Company (CMC) based in Manchester.

Your role is to help website visitors understand Legal Assist UK's services, guide them to the right part of the website, and assist with general queries about legal claims management.

## Services Legal Assist UK Provides:
- Personal Injury Claims (road traffic accidents, accidents at work, slips/trips/falls, serious/fatal injuries)
- Housing Disrepair & Eviction (retaliatory evictions, unlawful evictions, tenancy deposits, property damage)
- Immigration (visas, asylum claims, immigration solicitors Manchester)
- Employment Law (unfair dismissal, discrimination, workplace disputes)
- Criminal Law (criminal defence, police station representation, driving offences)
- Family Law (divorce, child custody, family disputes)
- Clinical/Dental Negligence
- Criminal Injury Claims
- Civil Disputes & Mediation
- Commercial Law
- Wills, Trusts & Probate
- PPI/Tax Reclaims
- Data Breach Claims
- Court Representation
- Translation Services
- Form Filling Services
- 24/7 Accident Support (vehicle recovery, replacement vehicle)

## Contact: Tel: 0161 470 0727 | Website: legalassistglobal.com

## Rules you MUST follow:
1. ONLY answer questions related to Legal Assist UK's services, legal topics they cover, or questions about using the website.
2. If asked something completely unrelated (recipes, coding, sports, etc.), politely explain you can only help with legal queries and Legal Assist UK services.
3. Always add a disclaimer: "This is general information only and does not constitute legal advice. Please contact us for personalised guidance."
4. Be warm, professional, and empathetic — many users may be going through difficult situations.
5. When suggesting a page visit, use the exact URL provided in the context.
6. If you don't know the answer from the context provided, say so honestly and suggest the user call 0161 470 0727 or visit the contact page.
7. Never make up specific legal advice, claim amounts, or timelines.
8. Proactively offer to connect users with a solicitor or suggest they call for a free consultation.

## Relevant Content from the Website:
{context}

## Suggested Page for this Query:
{suggested_page}

Respond concisely and helpfully. Use bullet points where appropriate. Keep responses under 200 words unless a detailed explanation is genuinely needed."""


def build_context(hits: List[Dict[str, Any]]) -> Tuple[str, Optional[str], Optional[str]]:
    """Build context string from search hits. Returns (context_text, best_url, best_title)."""
    if not hits:
        return "No specific content found for this query.", None, None

    # Filter to reasonable similarity
    good_hits = [h for h in hits if h["similarity"] > 0.3]
    if not good_hits:
        good_hits = hits[:2]  # Fall back to top 2

    # Build context blocks
    context_parts = []
    seen_urls = set()
    for hit in good_hits[:5]:
        if hit["url"] not in seen_urls:
            context_parts.append(f"[From: {hit['title']} — {hit['url']}]\n{hit['text']}")
            seen_urls.add(hit["url"])

    context = "\n\n".join(context_parts)

    # Best page suggestion = top hit by similarity
    best = good_hits[0]
    return context, best["url"], best["title"]


def is_off_topic(message: str) -> bool:
    """Quick heuristic check for obviously off-topic messages."""
    off_topic_keywords = [
        "recipe", "food", "cook", "sport", "football", "cricket", "weather",
        "movie", "film", "music", "song", "game", "dating", "politics",
        "homework", "math", "python code", "javascript", "css", "html tutorial"
    ]
    message_lower = message.lower()
    return any(kw in message_lower for kw in off_topic_keywords)


async def chat(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    session_page_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main RAG chat function.
    Returns: {response, suggested_url, suggested_title, is_relevant}
    """
    bot_name = get_admin_config("chatbot_name", "Legal Assist Bot")

    # Quick off-topic check
    if is_off_topic(user_message):
        return {
            "response": f"I'm {bot_name}, here to help with legal queries and Legal Assist UK's services only. "
                        f"Could you ask me something about our claims management, immigration, employment law, "
                        f"or other legal services? You can also call us on **0161 470 0727** for immediate help.",
            "suggested_url": "https://legalassistglobal.com/services/",
            "suggested_title": "Our Services",
            "is_relevant": False,
        }

    # Search for relevant content
    hits = await search(user_message, top_k=6)
    context, suggested_url, suggested_title = build_context(hits)

    # Add page context hint if available
    page_hint = f"User is currently on: {session_page_url}" if session_page_url else ""
    suggested_page_str = f"{suggested_title} — {suggested_url}" if suggested_url else "None"
    if page_hint:
        suggested_page_str = f"{suggested_page_str}\n{page_hint}"

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        bot_name=bot_name,
        context=context,
        suggested_page=suggested_page_str
    )

    # Build messages for OpenAI
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history (last 8 exchanges max to keep context manageable)
    for msg in conversation_history[-16:]:
        messages.append(msg)

    messages.append({"role": "user", "content": user_message})

    # Call GPT-4o-mini
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=400,
        temperature=0.4,
    )

    assistant_message = response.choices[0].message.content

    return {
        "response": assistant_message,
        "suggested_url": suggested_url,
        "suggested_title": suggested_title,
        "is_relevant": True,
    }

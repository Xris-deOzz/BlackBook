"""
AI Chat routes for Perun's BlackBook.

Handles AI conversation endpoints for the sidebar chat interface.
"""

import logging
import traceback
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

logger = logging.getLogger(__name__)
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Person, Organization, AIProvider, AISuggestion, AIQuickPrompt
from app.services.ai.chat_service import ChatService
from app.services.ai.provider_factory import ProviderFactory
from app.services.ai.base_provider import ProviderError
from app.services.ai.suggestion_service import SuggestionService


router = APIRouter(prefix="/ai-chat", tags=["ai-chat"])

templates = Jinja2Templates(directory="app/templates")


class ChatMessageRequest(BaseModel):
    """Request model for sending a chat message."""
    message: str
    entity_type: str  # "person" or "organization"
    entity_id: str
    conversation_id: Optional[str] = None
    provider_name: Optional[str] = None  # "anthropic" or "google"
    model_name: Optional[str] = None  # e.g., "gemini-3-pro-preview"


class ChatMessageResponse(BaseModel):
    """Response model for chat message."""
    conversation_id: str
    response: str
    tokens_used: Optional[int] = None


@router.get("/research-new", response_class=HTMLResponse)
async def research_new_entity_page(
    request: Request,
    type: str,
    name: str,
    db: Session = Depends(get_db),
):
    """
    Page for researching a new entity not yet in the database.

    This allows users to research people or companies that they haven't
    added to their CRM yet.
    """
    if type not in ("person", "company"):
        type = "person"  # Default to person

    # Check AI availability
    factory = ProviderFactory(db)
    available_providers = factory.get_available_providers()

    return templates.TemplateResponse(
        "ai_research_new.html",
        {
            "request": request,
            "entity_type": type,
            "entity_name": name,
            "ai_available": len(available_providers) > 0,
            "providers": available_providers,
        }
    )


@router.get("", response_class=HTMLResponse)
async def ai_chat_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Main AI Chat page showing all conversations.
    """
    from sqlalchemy import func
    from app.models import AIConversation, AIMessage

    chat_service = ChatService(db)
    conversations = chat_service.list_conversations(limit=100)

    # Enrich with entity info
    enriched_conversations = []
    for c in conversations:
        entity_name = None
        entity_type = None
        entity_url = None
        tokens_used = 0

        if c.person_id:
            person = db.query(Person).filter_by(id=c.person_id).first()
            if person:
                entity_name = person.full_name
                entity_type = "person"
                entity_url = f"/people/{c.person_id}"
        elif c.organization_id:
            org = db.query(Organization).filter_by(id=c.organization_id).first()
            if org:
                entity_name = org.name
                entity_type = "organization"
                entity_url = f"/organizations/{c.organization_id}"

        # Calculate tokens used in this conversation
        if c.messages:
            for msg in c.messages:
                tokens_used += (msg.tokens_in or 0) + (msg.tokens_out or 0)

        enriched_conversations.append({
            "conversation": c,
            "entity_name": entity_name,
            "entity_type": entity_type,
            "entity_url": entity_url,
            "tokens_used": tokens_used,
        })

    # Get stats
    total_conversations = db.query(func.count(AIConversation.id)).scalar() or 0
    total_messages = db.query(func.count(AIMessage.id)).scalar() or 0
    tokens_in = db.query(func.sum(AIMessage.tokens_in)).scalar() or 0
    tokens_out = db.query(func.sum(AIMessage.tokens_out)).scalar() or 0

    # Get pending suggestions count
    suggestion_service = SuggestionService(db)
    suggestion_stats = suggestion_service.get_suggestion_stats()

    stats = {
        "total_conversations": total_conversations,
        "total_messages": total_messages,
        "total_tokens": tokens_in + tokens_out,
        "pending_suggestions": suggestion_stats.get("pending", 0),
    }

    return templates.TemplateResponse(
        "ai_chat.html",
        {
            "request": request,
            "conversations": enriched_conversations,
            "stats": stats,
        }
    )


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    db: Session = Depends(get_db),
):
    """
    Send a message to the AI and get a response.

    Creates a new conversation if conversation_id is not provided.
    """
    # Validate entity exists
    entity_id = UUID(request.entity_id)
    person_id = None
    org_id = None
    entity_name = None

    if request.entity_type == "person":
        person = db.query(Person).filter_by(id=entity_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")
        person_id = entity_id
        entity_name = person.full_name
    elif request.entity_type == "organization":
        org = db.query(Organization).filter_by(id=entity_id).first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        org_id = entity_id
        entity_name = org.name
    else:
        raise HTTPException(status_code=400, detail="Invalid entity type")

    # Check if any AI provider is configured
    factory = ProviderFactory(db)
    available_providers = factory.get_available_providers()

    if not available_providers:
        raise HTTPException(
            status_code=503,
            detail="No AI provider configured. Please add an API key in Settings > AI Providers."
        )

    # Initialize chat service
    chat_service = ChatService(db)

    try:
        # Get or create conversation
        if request.conversation_id:
            conversation_id = UUID(request.conversation_id)
            conversation = chat_service.get_conversation(conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
        else:
            # Create new conversation
            conversation = chat_service.create_conversation(
                title=f"Research: {entity_name}",
                person_id=person_id,
                org_id=org_id,
                provider_name=request.provider_name,
                model_name=request.model_name,
            )
            db.commit()

        # Send message and get response
        response_message = await chat_service.send_message(
            conversation_id=conversation.id,
            content=request.message,
        )

        db.commit()

        return ChatMessageResponse(
            conversation_id=str(conversation.id),
            response=response_message.content,
            tokens_used=(response_message.tokens_in or 0) + (response_message.tokens_out or 0),
        )

    except ProviderError as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI provider error: {str(e)}"
        )
    except Exception as e:
        print(f"ERROR in send_message: {str(e)}", flush=True)
        traceback.print_exc()
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process message: {str(e)}"
        )


@router.get("/conversations/{entity_type}/{entity_id}")
async def list_conversations(
    entity_type: str,
    entity_id: UUID,
    db: Session = Depends(get_db),
):
    """
    List conversations for an entity.
    """
    chat_service = ChatService(db)

    person_id = None
    org_id = None

    if entity_type == "person":
        person_id = entity_id
    elif entity_type == "organization":
        org_id = entity_id
    else:
        raise HTTPException(status_code=400, detail="Invalid entity type")

    conversations = chat_service.list_conversations(
        person_id=person_id,
        org_id=org_id,
        limit=20,
    )

    return [
        {
            "id": str(c.id),
            "title": c.title,
            "updated_at": c.updated_at.isoformat(),
            "message_count": len(c.messages) if c.messages else 0,
        }
        for c in conversations
    ]


@router.get("/conversation/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get all messages in a conversation.
    """
    chat_service = ChatService(db)

    conversation = chat_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = chat_service.get_messages(conversation_id)

    return [
        {
            "id": str(m.id),
            "role": m.role.value,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


@router.delete("/conversation/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Delete a conversation.
    """
    chat_service = ChatService(db)

    success = chat_service.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.commit()

    return {"status": "deleted"}


@router.get("/status")
async def get_ai_status(
    db: Session = Depends(get_db),
):
    """
    Check AI availability status.

    Returns whether AI is configured and available.
    """
    factory = ProviderFactory(db)
    available_providers = factory.get_available_providers()

    return {
        "available": len(available_providers) > 0,
        "providers": available_providers,
    }


@router.get("/prompts")
async def get_quick_prompts(
    entity_type: str = "both",
    db: Session = Depends(get_db),
):
    """
    Get active quick prompts for the AI sidebar.

    Filters by entity type (person, organization, or both).
    Returns prompts ordered by display_order.
    """
    # Get active prompts that apply to this entity type
    query = db.query(AIQuickPrompt).filter(
        AIQuickPrompt.is_active == True  # noqa: E712
    )

    # Filter by entity type - include 'both' and the specific type
    if entity_type in ("person", "organization"):
        query = query.filter(
            AIQuickPrompt.entity_type.in_(["both", entity_type])
        )

    prompts = query.order_by(AIQuickPrompt.display_order).all()

    return [
        {
            "id": str(prompt.id),
            "label": prompt.label,
            "prompt_text": prompt.prompt_text,
            "entity_type": prompt.entity_type.value,
        }
        for prompt in prompts
    ]


@router.get("/recent")
async def get_recent_conversations(
    limit: int = 5,
    db: Session = Depends(get_db),
):
    """
    Get recent AI conversations across all entities.

    Used by the dashboard widget.
    """
    chat_service = ChatService(db)
    conversations = chat_service.list_conversations(limit=limit)

    result = []
    for c in conversations:
        # Get entity info
        entity_name = None
        entity_type = None
        entity_id = None

        if c.person_id:
            person = db.query(Person).filter_by(id=c.person_id).first()
            if person:
                entity_name = person.full_name
                entity_type = "person"
                entity_id = str(c.person_id)
        elif c.organization_id:
            org = db.query(Organization).filter_by(id=c.organization_id).first()
            if org:
                entity_name = org.name
                entity_type = "organization"
                entity_id = str(c.organization_id)

        result.append({
            "id": str(c.id),
            "title": c.title,
            "updated_at": c.updated_at.isoformat(),
            "message_count": len(c.messages) if c.messages else 0,
            "entity_name": entity_name,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "provider_name": c.provider_name,
        })

    return result


@router.get("/widget", response_class=HTMLResponse)
async def get_recent_conversations_widget(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Get HTML widget for recent AI conversations.

    Used by the dashboard.
    """
    chat_service = ChatService(db)
    conversations = chat_service.list_conversations(limit=5)

    # Enrich with entity info
    enriched_conversations = []
    for c in conversations:
        entity_name = None
        entity_type = None
        entity_url = None

        if c.person_id:
            person = db.query(Person).filter_by(id=c.person_id).first()
            if person:
                entity_name = person.full_name
                entity_type = "person"
                entity_url = f"/people/{c.person_id}"
        elif c.organization_id:
            org = db.query(Organization).filter_by(id=c.organization_id).first()
            if org:
                entity_name = org.name
                entity_type = "organization"
                entity_url = f"/organizations/{c.organization_id}"

        enriched_conversations.append({
            "conversation": c,
            "entity_name": entity_name,
            "entity_type": entity_type,
            "entity_url": entity_url,
        })

    return templates.TemplateResponse(
        "partials/_recent_ai_conversations.html",
        {
            "request": request,
            "conversations": enriched_conversations,
        }
    )


@router.get("/search/people")
async def search_people_for_research(
    q: str = "",
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """
    Search people for the research modal.

    Returns a lightweight list of people for dropdown selection.
    """
    from sqlalchemy import func

    query = db.query(Person)

    if q:
        search_term = f"%{q}%"
        query = query.filter(
            (Person.first_name.ilike(search_term)) |
            (Person.last_name.ilike(search_term)) |
            (Person.full_name.ilike(search_term))
        )

    people = (
        query
        .order_by(func.lower(Person.full_name))
        .limit(limit)
        .all()
    )

    return [
        {
            "id": str(p.id),
            "full_name": p.full_name,
            "title": p.title,
        }
        for p in people
    ]


@router.get("/search/organizations")
async def search_organizations_for_research(
    q: str = "",
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """
    Search organizations for the research modal.

    Returns a lightweight list of organizations for dropdown selection.
    """
    from sqlalchemy import func

    query = db.query(Organization)

    if q:
        search_term = f"%{q}%"
        query = query.filter(Organization.name.ilike(search_term))

    orgs = (
        query
        .order_by(func.lower(Organization.name))
        .limit(limit)
        .all()
    )

    return [
        {
            "id": str(o.id),
            "name": o.name,
            "category": o.category,
        }
        for o in orgs
    ]


@router.get("/suggestions-widget", response_class=HTMLResponse)
async def get_suggestions_widget(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Get HTML widget for pending AI suggestions summary.

    Used by the dashboard.
    """
    suggestion_service = SuggestionService(db)
    stats = suggestion_service.get_suggestion_stats()

    # Get recent pending suggestions (up to 5) with entity info
    pending_suggestions = suggestion_service.get_pending_suggestions()[:5]

    enriched_suggestions = []
    for s in pending_suggestions:
        entity_name = None
        entity_url = None

        if s.entity_type == "person":
            person = db.query(Person).filter_by(id=s.entity_id).first()
            if person:
                entity_name = person.full_name
                entity_url = f"/people/{s.entity_id}"
        else:
            org = db.query(Organization).filter_by(id=s.entity_id).first()
            if org:
                entity_name = org.name
                entity_url = f"/organizations/{s.entity_id}"

        enriched_suggestions.append({
            "suggestion": s,
            "entity_name": entity_name,
            "entity_url": entity_url,
        })

    return templates.TemplateResponse(
        "partials/_pending_suggestions_widget.html",
        {
            "request": request,
            "suggestions": enriched_suggestions,
            "stats": stats,
        }
    )


# =====================
# Suggestion Endpoints
# =====================


class SuggestionResponse(BaseModel):
    """Response model for a suggestion."""
    id: str
    field_name: str
    current_value: Optional[str]
    suggested_value: str
    confidence: Optional[float]
    source_url: Optional[str]
    status: str


@router.get("/suggestions/{entity_type}/{entity_id}")
async def get_pending_suggestions(
    entity_type: str,
    entity_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get pending suggestions for an entity.

    Returns list of suggestions that need user approval.
    """
    if entity_type not in ("person", "organization"):
        raise HTTPException(status_code=400, detail="Invalid entity type")

    suggestion_service = SuggestionService(db)
    suggestions = suggestion_service.get_pending_suggestions(
        entity_type=entity_type,
        entity_id=entity_id,
    )

    return [
        {
            "id": str(s.id),
            "field_name": s.field_name,
            "current_value": s.current_value,
            "suggested_value": s.suggested_value,
            "confidence": s.confidence,
            "confidence_percent": s.confidence_percent,
            "source_url": s.source_url,
            "status": s.status.value,
            "created_at": s.created_at.isoformat(),
        }
        for s in suggestions
    ]


@router.post("/suggestions/{suggestion_id}/accept")
async def accept_suggestion(
    suggestion_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Accept a suggestion and apply it to the entity.
    """
    suggestion_service = SuggestionService(db)

    success = suggestion_service.accept_suggestion(suggestion_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Suggestion not found or already processed"
        )

    db.commit()

    return {"status": "accepted", "id": str(suggestion_id)}


@router.post("/suggestions/{suggestion_id}/reject")
async def reject_suggestion(
    suggestion_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Reject a suggestion.
    """
    suggestion_service = SuggestionService(db)

    success = suggestion_service.reject_suggestion(suggestion_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Suggestion not found or already processed"
        )

    db.commit()

    return {"status": "rejected", "id": str(suggestion_id)}


@router.post("/suggestions/{entity_type}/{entity_id}/accept-all")
async def accept_all_suggestions(
    entity_type: str,
    entity_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Accept all pending suggestions for an entity.
    """
    if entity_type not in ("person", "organization"):
        raise HTTPException(status_code=400, detail="Invalid entity type")

    suggestion_service = SuggestionService(db)
    accepted_count = suggestion_service.accept_all_pending(
        entity_type=entity_type,
        entity_id=entity_id,
    )

    db.commit()

    return {"status": "success", "accepted_count": accepted_count}


@router.post("/suggestions/{entity_type}/{entity_id}/reject-all")
async def reject_all_suggestions(
    entity_type: str,
    entity_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Reject all pending suggestions for an entity.
    """
    if entity_type not in ("person", "organization"):
        raise HTTPException(status_code=400, detail="Invalid entity type")

    suggestion_service = SuggestionService(db)
    rejected_count = suggestion_service.reject_all_pending(
        entity_type=entity_type,
        entity_id=entity_id,
    )

    db.commit()

    return {"status": "success", "rejected_count": rejected_count}


@router.get("/suggestions/{entity_type}/{entity_id}/stats")
async def get_suggestion_stats(
    entity_type: str,
    entity_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get suggestion statistics for an entity.
    """
    if entity_type not in ("person", "organization"):
        raise HTTPException(status_code=400, detail="Invalid entity type")

    suggestion_service = SuggestionService(db)
    stats = suggestion_service.get_suggestion_stats(
        entity_type=entity_type,
        entity_id=entity_id,
    )

    return stats


@router.get("/suggestions/pending-count")
async def get_global_pending_count(
    db: Session = Depends(get_db),
):
    """
    Get total count of pending suggestions across all entities.

    Used by the navigation badge to show pending items.
    """
    suggestion_service = SuggestionService(db)
    stats = suggestion_service.get_suggestion_stats()

    return {"pending": stats["pending"]}


@router.get("/usage")
async def get_ai_usage_stats(
    db: Session = Depends(get_db),
):
    """
    Get AI usage statistics including token counts and estimated costs.

    Returns usage data across all conversations.
    """
    from sqlalchemy import func
    from app.models import AIConversation, AIMessage

    # Get total conversations and messages
    total_conversations = db.query(func.count(AIConversation.id)).scalar() or 0
    total_messages = db.query(func.count(AIMessage.id)).scalar() or 0

    # Get token totals
    tokens_in = db.query(func.sum(AIMessage.tokens_in)).scalar() or 0
    tokens_out = db.query(func.sum(AIMessage.tokens_out)).scalar() or 0
    total_tokens = tokens_in + tokens_out

    # Get per-provider breakdown
    provider_stats = []
    conversations_by_provider = (
        db.query(
            AIConversation.provider_name,
            func.count(AIConversation.id).label('conversation_count'),
        )
        .filter(AIConversation.provider_name.isnot(None))
        .group_by(AIConversation.provider_name)
        .all()
    )

    for provider_name, conv_count in conversations_by_provider:
        # Get token counts for this provider
        provider_tokens = (
            db.query(
                func.sum(AIMessage.tokens_in).label('tokens_in'),
                func.sum(AIMessage.tokens_out).label('tokens_out'),
            )
            .join(AIConversation)
            .filter(AIConversation.provider_name == provider_name)
            .first()
        )

        p_tokens_in = provider_tokens.tokens_in or 0
        p_tokens_out = provider_tokens.tokens_out or 0

        # Estimate costs (rough estimates per 1M tokens)
        cost_per_million_input = {
            'anthropic': 3.00,   # Claude 3.5 Sonnet
            'openai': 3.00,      # GPT-4 Turbo
            'google': 1.25,      # Gemini Pro
            'ollama': 0.00,      # Local, free
        }
        cost_per_million_output = {
            'anthropic': 15.00,  # Claude 3.5 Sonnet
            'openai': 15.00,     # GPT-4 Turbo
            'google': 5.00,      # Gemini Pro
            'ollama': 0.00,      # Local, free
        }

        input_cost = (p_tokens_in / 1_000_000) * cost_per_million_input.get(provider_name, 0)
        output_cost = (p_tokens_out / 1_000_000) * cost_per_million_output.get(provider_name, 0)

        provider_stats.append({
            'provider': provider_name,
            'conversations': conv_count,
            'tokens_in': p_tokens_in,
            'tokens_out': p_tokens_out,
            'total_tokens': p_tokens_in + p_tokens_out,
            'estimated_cost': round(input_cost + output_cost, 4),
        })

    # Calculate total estimated cost
    total_cost = sum(p['estimated_cost'] for p in provider_stats)

    return {
        'total_conversations': total_conversations,
        'total_messages': total_messages,
        'total_tokens_in': tokens_in,
        'total_tokens_out': tokens_out,
        'total_tokens': total_tokens,
        'estimated_total_cost': round(total_cost, 4),
        'by_provider': provider_stats,
    }


class ResearchNewRequest(BaseModel):
    """Request model for researching a new entity not in the database."""
    message: str
    entity_type: str  # "person" or "company"
    entity_name: str
    conversation_id: Optional[str] = None
    provider_name: Optional[str] = None
    model_name: Optional[str] = None


@router.post("/research-new/message", response_model=ChatMessageResponse)
async def send_research_new_message(
    request: ResearchNewRequest,
    db: Session = Depends(get_db),
):
    """
    Send a message to research a new entity not yet in the database.

    This creates a standalone conversation that can later be linked to
    an entity once it's added to the CRM.
    """
    # Check if any AI provider is configured
    factory = ProviderFactory(db)
    available_providers = factory.get_available_providers()

    if not available_providers:
        raise HTTPException(
            status_code=503,
            detail="No AI provider configured. Please add an API key in Settings > AI Providers."
        )

    # Initialize chat service
    chat_service = ChatService(db)

    try:
        # Get or create conversation
        if request.conversation_id:
            conversation_id = UUID(request.conversation_id)
            conversation = chat_service.get_conversation(conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
        else:
            # Create new standalone conversation (not linked to an entity)
            entity_type_label = "Person" if request.entity_type == "person" else "Company"
            conversation = chat_service.create_conversation(
                title=f"Research: {request.entity_name} ({entity_type_label})",
                person_id=None,
                org_id=None,
                provider_name=request.provider_name,
                model_name=request.model_name,
            )
            db.commit()

        # Build context for the AI
        context = f"The user wants to research a {request.entity_type} named '{request.entity_name}'. "
        context += "This entity is not yet in the CRM database. "
        context += "Provide helpful research information about this entity using web search if available."

        # For the first message, prepend the context
        full_message = request.message
        if len(chat_service.get_messages(conversation.id)) == 0:
            # This is the first message, add context
            full_message = f"[Research Context: {context}]\n\n{request.message}"

        # Send message and get response
        response_message = await chat_service.send_message(
            conversation_id=conversation.id,
            content=full_message,
        )

        db.commit()

        return ChatMessageResponse(
            conversation_id=str(conversation.id),
            response=response_message.content,
            tokens_used=(response_message.tokens_in or 0) + (response_message.tokens_out or 0),
        )

    except ProviderError as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI provider error: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process message: {str(e)}"
        )


@router.get("/usage-widget", response_class=HTMLResponse)
async def get_usage_widget(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Get HTML widget for AI usage statistics.

    Used by the settings page.
    """
    from sqlalchemy import func
    from app.models import AIConversation, AIMessage

    # Get usage stats
    total_conversations = db.query(func.count(AIConversation.id)).scalar() or 0
    total_messages = db.query(func.count(AIMessage.id)).scalar() or 0
    tokens_in = db.query(func.sum(AIMessage.tokens_in)).scalar() or 0
    tokens_out = db.query(func.sum(AIMessage.tokens_out)).scalar() or 0

    # Get suggestion stats
    suggestion_service = SuggestionService(db)
    suggestion_stats = suggestion_service.get_suggestion_stats()

    return templates.TemplateResponse(
        "partials/_ai_usage_widget.html",
        {
            "request": request,
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "total_tokens": tokens_in + tokens_out,
            "suggestion_stats": suggestion_stats,
        }
    )

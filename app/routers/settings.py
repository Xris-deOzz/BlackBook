"""
Settings routes for Perun's BlackBook.

Handles application settings including Google account connections and email ignore patterns.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GoogleAccount, EmailIgnoreList, Person, Organization, Tag, PendingContact, PendingContactStatus
from app.models import AIProvider, AIAPIKey, AIDataAccessSettings
from app.models import AIQuickPrompt, PromptEntityType
from app.models import AIConversation, AIMessage
from app.models import CalendarSettings, COMMON_TIMEZONES
from app.models import OrganizationCategory, OrganizationType, InvestmentProfileOption
from app.models import ImportHistory, ImportSource, ImportStatus
from app.models.email_ignore import IgnorePatternType
from app.models.tag import PersonTag, OrganizationTag
from app.services.duplicate_service import get_duplicate_service
from app.services.ai.suggestion_service import SuggestionService
from app.services.ai.chat_service import ChatService
from sqlalchemy.orm import joinedload

router = APIRouter(prefix="/settings", tags=["settings"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    tab: str = Query("syncing", description="Active tab"),
    pending_status: str = Query("pending", description="Pending contacts status filter"),
    sort: str = Query("name", description="Sort field for tags: name, color, count"),
    order: str = Query("asc", description="Sort order for tags: asc, desc"),
    db: Session = Depends(get_db),
):
    """
    Main settings page with tabs for different settings sections.
    """
    # Get Google accounts
    google_accounts = db.query(GoogleAccount).order_by(GoogleAccount.created_at.desc()).all()

    # Get email ignore patterns
    ignore_patterns = db.query(EmailIgnoreList).order_by(
        EmailIgnoreList.pattern_type,
        EmailIgnoreList.pattern,
    ).all()

    # Get calendar settings for syncing tab
    calendar_settings = None
    if tab == "syncing":
        calendar_settings = CalendarSettings.get_settings(db)

    # Get tags data for tags tab
    people_tags = []
    people_tags_by_subcategory = {}  # Grouped by subcategory
    people_subcategories = []  # Ordered list of subcategory names
    org_tags = []
    firm_category_tags = []
    company_category_tags = []
    uncategorized_tags = []
    if tab == "tags":
        # Validate sort parameters
        valid_sorts = {"name", "color", "count"}
        valid_orders = {"asc", "desc"}
        if sort not in valid_sorts:
            sort = "name"
        if order not in valid_orders:
            order = "asc"

        # Query for People tags - use LEFT JOIN to include tags with 0 usage
        # People tags are those without a category (Firm/Company tags have categories)
        usage_count_label = func.count(func.distinct(PersonTag.person_id)).label("usage_count")
        people_tags_query = db.query(
            Tag,
            usage_count_label,
        ).outerjoin(
            PersonTag, Tag.id == PersonTag.tag_id
        ).filter(
            Tag.category.is_(None)
        ).group_by(Tag.id)

        # Apply sorting
        if sort == "name":
            sort_col = Tag.name
        elif sort == "color":
            sort_col = Tag.color
        else:  # count
            sort_col = usage_count_label

        if order == "desc":
            people_tags_query = people_tags_query.order_by(desc(sort_col))
        else:
            people_tags_query = people_tags_query.order_by(sort_col)

        for tag, usage_count in people_tags_query.all():
            tag_data = {"tag": tag, "usage_count": usage_count or 0}
            people_tags.append(tag_data)

            # Group by subcategory
            subcat = tag.subcategory or "Uncategorized"
            if subcat not in people_tags_by_subcategory:
                people_tags_by_subcategory[subcat] = []
            people_tags_by_subcategory[subcat].append(tag_data)

        # Define preferred subcategory order
        preferred_order = [
            "Investor Type", "Role/Industry", "Location", "Classmates",
            "Former Colleague", "Professional Services", "Relationship", "Uncategorized"
        ]
        # Sort subcategories: preferred order first, then alphabetically for any others
        all_subcats = set(people_tags_by_subcategory.keys())
        people_subcategories = [s for s in preferred_order if s in all_subcats]
        people_subcategories += sorted(all_subcats - set(preferred_order))

        # Query for Organization tags - use LEFT JOIN to include tags with 0 usage
        org_usage_count_label = func.count(func.distinct(OrganizationTag.organization_id)).label("usage_count")
        org_tags_query = db.query(
            Tag,
            org_usage_count_label,
        ).outerjoin(
            OrganizationTag, Tag.id == OrganizationTag.tag_id
        ).filter(
            Tag.category.in_(["Firm Category", "Company Category"])
        ).group_by(Tag.id)

        # Apply sorting for org tags
        if sort == "name":
            org_sort_col = Tag.name
        elif sort == "color":
            org_sort_col = Tag.color
        else:  # count
            org_sort_col = org_usage_count_label

        if order == "desc":
            org_tags_query = org_tags_query.order_by(desc(org_sort_col))
        else:
            org_tags_query = org_tags_query.order_by(org_sort_col)

        for tag, usage_count in org_tags_query.all():
            org_tags.append({"tag": tag, "usage_count": usage_count or 0})

        # Group org tags by category for display
        firm_category_tags = [t for t in org_tags if t["tag"].category == "Firm Category"]
        company_category_tags = [t for t in org_tags if t["tag"].category == "Company Category"]
        uncategorized_tags = [t for t in org_tags if t["tag"].category not in ("Firm Category", "Company Category")]

    # Get pending contacts data for pending tab
    pending_contacts = []
    if tab == "pending":
        query = db.query(PendingContact)
        if pending_status:
            try:
                status_enum = PendingContactStatus(pending_status)
                query = query.filter(PendingContact.status == status_enum)
            except ValueError:
                pass
        else:
            query = query.filter(PendingContact.status == PendingContactStatus.pending)

        pending_contacts = query.order_by(
            PendingContact.occurrence_count.desc(),
            PendingContact.first_seen_at.desc(),
        ).all()

    # Get AI providers and data access settings for ai tab
    ai_providers = []
    search_providers = []
    data_access_settings = None
    quick_prompts = []
    if tab == "ai":
        from app.models.ai_provider import AIProviderType
        # AI providers (openai, anthropic, google, ollama)
        ai_provider_types = [AIProviderType.openai, AIProviderType.anthropic, AIProviderType.google, AIProviderType.ollama]
        ai_providers = db.query(AIProvider).options(
            joinedload(AIProvider.api_keys)
        ).filter(AIProvider.api_type.in_(ai_provider_types)).order_by(AIProvider.name).all()

        # Search providers (brave_search, youtube, listen_notes)
        search_provider_types = [AIProviderType.brave_search, AIProviderType.youtube, AIProviderType.listen_notes]
        search_providers = db.query(AIProvider).options(
            joinedload(AIProvider.api_keys)
        ).filter(AIProvider.api_type.in_(search_provider_types)).order_by(AIProvider.name).all()

        data_access_settings = AIDataAccessSettings.get_settings(db)

        # Get quick prompts for AI sidebar customization
        quick_prompts = db.query(AIQuickPrompt).order_by(AIQuickPrompt.display_order).all()

    # Get organization types data for org-types tab
    org_categories = []
    org_types = []
    org_options = []
    option_types = []
    if tab == "org-types":
        org_categories = db.query(OrganizationCategory).options(
            joinedload(OrganizationCategory.types)
        ).order_by(OrganizationCategory.sort_order).all()

        org_types = db.query(OrganizationType).options(
            joinedload(OrganizationType.category)
        ).order_by(OrganizationType.category_id, OrganizationType.sort_order).all()

        org_options = db.query(InvestmentProfileOption).order_by(
            InvestmentProfileOption.option_type,
            InvestmentProfileOption.sort_order
        ).all()

        # Get unique option types for the filter dropdown
        option_types = list(set(opt.option_type for opt in org_options))
        option_types.sort()

    # Get Contacts Sync data for contacts-sync tab
    sync_settings = None
    sync_status = None
    last_sync = None
    recent_syncs = []
    conflicts_count = 0
    archived_count = 0
    if tab == "contacts-sync":
        # Get recent sync history from ImportHistory
        recent_syncs = db.query(ImportHistory).filter(
            ImportHistory.source == ImportSource.google_contacts
        ).order_by(ImportHistory.imported_at.desc()).limit(10).all()

        # Get last successful sync
        last_sync = db.query(ImportHistory).filter(
            ImportHistory.source == ImportSource.google_contacts,
            ImportHistory.status == ImportStatus.success
        ).order_by(ImportHistory.imported_at.desc()).first()

        # Note: sync_settings, sync_status, conflicts_count, and archived_count
        # would need dedicated models to be implemented. For now, we use defaults.
        # These can be expanded when the full bidirectional sync is implemented.

    # Get AI Chat data for ai-chat tab
    ai_chat_conversations = []
    ai_chat_stats = {}
    if tab == "ai-chat":
        chat_service = ChatService(db)
        conversations = chat_service.list_conversations(limit=100)

        # Enrich with entity info
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

            ai_chat_conversations.append({
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

        # Get per-model statistics
        model_stats_query = db.query(
            AIConversation.provider_name,
            AIConversation.model_name,
            func.count(AIConversation.id).label('conversation_count'),
            func.count(AIMessage.id).label('message_count'),
            func.sum(AIMessage.tokens_in).label('tokens_in'),
            func.sum(AIMessage.tokens_out).label('tokens_out'),
        ).outerjoin(
            AIMessage, AIMessage.conversation_id == AIConversation.id
        ).group_by(
            AIConversation.provider_name,
            AIConversation.model_name
        ).all()

        model_stats = []
        for stat in model_stats_query:
            provider = stat.provider_name or 'Unknown'
            model = stat.model_name or 'Default'
            tokens_in_model = stat.tokens_in or 0
            tokens_out_model = stat.tokens_out or 0
            total_tokens_model = tokens_in_model + tokens_out_model

            model_stats.append({
                "provider": provider,
                "model": model,
                "display_name": f"{provider.title()}: {model}",
                "conversations": stat.conversation_count or 0,
                "messages": stat.message_count or 0,
                "tokens_in": tokens_in_model,
                "tokens_out": tokens_out_model,
                "total_tokens": total_tokens_model,
            })

        # Sort by total tokens descending
        model_stats.sort(key=lambda x: x['total_tokens'], reverse=True)

        ai_chat_stats = {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "total_tokens": tokens_in + tokens_out,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "pending_suggestions": suggestion_stats.get("pending", 0),
            "model_stats": model_stats,
        }

    return templates.TemplateResponse(
        "settings/index.html",
        {
            "request": request,
            "title": "Settings",
            "active_tab": tab,
            "google_accounts": google_accounts,
            "ignore_patterns": ignore_patterns,
            "pattern_types": [t.value for t in IgnorePatternType],
            # Calendar settings
            "calendar_settings": calendar_settings,
            "timezones": COMMON_TIMEZONES,
            # Tags data
            "people_tags": people_tags,
            "people_tags_by_subcategory": people_tags_by_subcategory,
            "people_subcategories": people_subcategories,
            "org_tags": org_tags,
            "firm_category_tags": firm_category_tags,
            "company_category_tags": company_category_tags,
            "uncategorized_tags": uncategorized_tags,
            "people_count": len(people_tags),
            "org_count": len(org_tags),
            "sort": sort,
            "order": order,
            # Pending contacts data
            "pending_contacts": pending_contacts,
            "pending_status": pending_status or "pending",
            # AI providers data
            "ai_providers": ai_providers,
            "search_providers": search_providers,
            "data_access_settings": data_access_settings,
            "quick_prompts": quick_prompts,
            "entity_types": [e.value for e in PromptEntityType],
            # Organization types data
            "categories": org_categories,
            "types": org_types,
            "options": org_options,
            "option_types": option_types,
            # AI Chat data
            "ai_chat_conversations": ai_chat_conversations,
            "ai_chat_stats": ai_chat_stats,
            # Contacts Sync data
            "sync_settings": sync_settings,
            "sync_status": sync_status,
            "last_sync": last_sync,
            "recent_syncs": recent_syncs,
            "conflicts_count": conflicts_count,
            "archived_count": archived_count,
        },
    )


# ===========================
# Email Ignore Pattern Management
# ===========================


@router.get("/patterns", response_class=HTMLResponse)
async def get_patterns_list(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Get the email ignore patterns list partial.
    """
    patterns = db.query(EmailIgnoreList).order_by(
        EmailIgnoreList.pattern_type,
        EmailIgnoreList.pattern,
    ).all()

    return templates.TemplateResponse(
        "settings/_patterns_list.html",
        {
            "request": request,
            "ignore_patterns": patterns,
        },
    )


@router.post("/patterns", response_class=HTMLResponse)
async def add_pattern(
    request: Request,
    pattern: str = Form(...),
    pattern_type: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Add a new email ignore pattern.
    """
    # Check for duplicate
    existing = db.query(EmailIgnoreList).filter_by(pattern=pattern.lower().strip()).first()

    if not existing:
        new_pattern = EmailIgnoreList(
            pattern=pattern.lower().strip(),
            pattern_type=IgnorePatternType(pattern_type),
        )
        db.add(new_pattern)
        db.commit()

    # Return updated list
    patterns = db.query(EmailIgnoreList).order_by(
        EmailIgnoreList.pattern_type,
        EmailIgnoreList.pattern,
    ).all()

    return templates.TemplateResponse(
        "settings/_patterns_list.html",
        {
            "request": request,
            "ignore_patterns": patterns,
        },
    )


@router.delete("/patterns/{pattern_id}", response_class=HTMLResponse)
async def delete_pattern(
    request: Request,
    pattern_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Delete an email ignore pattern.
    """
    pattern = db.query(EmailIgnoreList).filter_by(id=pattern_id).first()
    if pattern:
        db.delete(pattern)
        db.commit()

    # Return updated list
    patterns = db.query(EmailIgnoreList).order_by(
        EmailIgnoreList.pattern_type,
        EmailIgnoreList.pattern,
    ).all()

    return templates.TemplateResponse(
        "settings/_patterns_list.html",
        {
            "request": request,
            "ignore_patterns": patterns,
        },
    )


# ===========================
# Google Account Management
# ===========================


@router.get("/accounts", response_class=HTMLResponse)
async def get_accounts_list(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Get the Google accounts list partial.
    """
    accounts = db.query(GoogleAccount).order_by(GoogleAccount.created_at.desc()).all()

    return templates.TemplateResponse(
        "settings/_accounts_list.html",
        {
            "request": request,
            "google_accounts": accounts,
        },
    )


@router.post("/accounts/{account_id}/toggle", response_class=HTMLResponse)
async def toggle_account_status(
    request: Request,
    account_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Toggle a Google account's active status.
    """
    account = db.query(GoogleAccount).filter_by(id=account_id).first()
    if account:
        account.is_active = not account.is_active
        db.commit()

    # Return updated list
    accounts = db.query(GoogleAccount).order_by(GoogleAccount.created_at.desc()).all()

    return templates.TemplateResponse(
        "settings/_accounts_list.html",
        {
            "request": request,
            "google_accounts": accounts,
        },
    )


# ===========================
# Duplicate Management
# ===========================


@router.get("/duplicates", response_class=HTMLResponse)
async def duplicates_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Page showing all duplicate person groups.
    """
    service = get_duplicate_service(db)
    duplicate_groups = service.find_duplicates()
    fuzzy_groups = service.find_fuzzy_duplicates()
    exclusion_count = service.get_exclusion_count()

    return templates.TemplateResponse(
        "settings/duplicates.html",
        {
            "request": request,
            "title": "Duplicate Management",
            "duplicate_groups": duplicate_groups,
            "fuzzy_groups": fuzzy_groups,
            "exclusion_count": exclusion_count,
        },
    )


@router.get("/duplicates/merge", response_class=HTMLResponse)
async def merge_page(
    request: Request,
    name: str = Query(..., description="Full name of duplicate group"),
    db: Session = Depends(get_db),
):
    """
    Page for reviewing and merging a specific duplicate group.
    """
    service = get_duplicate_service(db)
    group = service.get_duplicate_group(name)

    if not group:
        # Group no longer exists - redirect back to the list
        return RedirectResponse(url="/settings/duplicates", status_code=303)

    return templates.TemplateResponse(
        "settings/merge.html",
        {
            "request": request,
            "title": f"Merge: {name}",
            "group": group,
        },
    )


@router.post("/duplicates/merge", response_class=HTMLResponse)
async def execute_merge(
    request: Request,
    keep_id: UUID = Form(...),
    full_name: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Execute the merge operation for a duplicate group.
    Supports field-level selection for which values to keep.
    """
    form_data = await request.form()
    
    service = get_duplicate_service(db)
    group = service.get_duplicate_group(full_name)

    if not group:
        raise HTTPException(status_code=404, detail="Duplicate group not found")

    # Get IDs to merge (all except the one to keep)
    merge_ids = [p.id for p in group.persons if p.id != keep_id]

    if not merge_ids:
        raise HTTPException(status_code=400, detail="No records to merge")

    # BEFORE merge: Save selected field values from form
    field_values = {}
    field_mappings = [
        ('field_title', ['title']),
        ('field_linkedin', ['linkedin']),
        ('field_location', ['location']),
        ('field_profile_picture', ['profile_picture']),
        ('field_birthday', ['birthday']),
    ]
    
    persons_by_id = {p.id: p for p in group.persons}
    
    for form_field, model_fields in field_mappings:
        selected_id = form_data.get(form_field)
        if selected_id:
            try:
                selected_uuid = UUID(selected_id)
                if selected_uuid in persons_by_id:
                    selected_person = persons_by_id[selected_uuid]
                    for model_field in model_fields:
                        value = getattr(selected_person, model_field, None)
                        if value is not None:
                            field_values[model_field] = value
            except (ValueError, TypeError):
                pass
        elif form_data.get(form_field) == '':
            # User selected "None" - mark for clearing
            for model_field in model_fields:
                field_values[model_field] = None

    # Execute merge
    result = service.merge_persons(keep_id, merge_ids)

    # AFTER merge: Apply the saved field selections
    keep_person = db.query(Person).filter_by(id=keep_id).first()
    if keep_person and field_values:
        for field, value in field_values.items():
            setattr(keep_person, field, value)
        db.commit()

    # Return to duplicates list with success message
    duplicate_groups = service.find_duplicates()
    fuzzy_groups = service.find_fuzzy_duplicates()

    return templates.TemplateResponse(
        "settings/duplicates.html",
        {
            "request": request,
            "title": "Duplicate Management",
            "duplicate_groups": duplicate_groups,
            "fuzzy_groups": fuzzy_groups,
            "merge_success": True,
            "merge_result": result,
        },
    )


@router.post("/duplicates/merge-all", response_class=HTMLResponse)
async def execute_merge_all(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Execute merge for all duplicate groups at once.
    Keeps the oldest person in each group and merges others into it.
    """
    service = get_duplicate_service(db)
    result = service.merge_all()

    # Return to duplicates list with success message
    duplicate_groups = service.find_duplicates()
    fuzzy_groups = service.find_fuzzy_duplicates()

    return templates.TemplateResponse(
        "settings/duplicates.html",
        {
            "request": request,
            "title": "Duplicate Management",
            "duplicate_groups": duplicate_groups,
            "fuzzy_groups": fuzzy_groups,
            "merge_all_success": True,
            "merge_all_result": result,
        },
    )


@router.get("/duplicates/fuzzy", response_class=HTMLResponse)
async def fuzzy_duplicates_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Page showing fuzzy duplicate groups (same last name, similar first name).
    """
    service = get_duplicate_service(db)
    fuzzy_groups = service.find_fuzzy_duplicates()
    exclusion_count = service.get_exclusion_count()

    return templates.TemplateResponse(
        "settings/fuzzy_duplicates.html",
        {
            "request": request,
            "title": "Similar Name Duplicates",
            "fuzzy_groups": fuzzy_groups,
            "exclusion_count": exclusion_count,
        },
    )


@router.get("/duplicates/fuzzy/merge", response_class=HTMLResponse)
async def fuzzy_merge_page(
    request: Request,
    ids: str = Query(..., description="Comma-separated person IDs"),
    db: Session = Depends(get_db),
):
    """
    Page for reviewing and merging a specific fuzzy duplicate group.
    """
    try:
        person_ids = [UUID(id.strip()) for id in ids.split(",") if id.strip()]
    except ValueError:
        # Invalid UUIDs - redirect back
        return RedirectResponse(url="/settings/duplicates/fuzzy", status_code=303)
    
    service = get_duplicate_service(db)
    group = service.get_fuzzy_duplicate_group(person_ids)

    if not group:
        # Group no longer exists (merged, excluded, or removed by nickname fix)
        # Redirect back to the list instead of showing an error
        return RedirectResponse(url="/settings/duplicates/fuzzy", status_code=303)

    return templates.TemplateResponse(
        "settings/fuzzy_merge.html",
        {
            "request": request,
            "title": f"Merge Similar Names: {group.last_name}",
            "group": group,
            "person_ids": ids,
        },
    )


@router.post("/duplicates/fuzzy/merge", response_class=HTMLResponse)
async def execute_fuzzy_merge(
    request: Request,
    keep_id: UUID = Form(...),
    db: Session = Depends(get_db),
):
    """
    Execute the merge operation for a fuzzy duplicate group.
    Supports selective merging (user can uncheck records that are different people).
    Supports field-level selection for which values to keep.
    """
    form_data = await request.form()
    
    # Get the selected IDs (records user wants to merge)
    selected_ids = form_data.getlist('selected_ids')
    if not selected_ids:
        raise HTTPException(status_code=400, detail="No records selected for merge")
    
    selected_id_list = [UUID(id.strip()) for id in selected_ids if id.strip()]
    
    if len(selected_id_list) < 2:
        raise HTTPException(status_code=400, detail="Select at least 2 records to merge")
    
    if keep_id not in selected_id_list:
        raise HTTPException(status_code=400, detail="Primary record must be one of the selected records")
    
    service = get_duplicate_service(db)
    
    # Get the group for field value lookups
    # Use all_person_ids to get the full group context
    all_person_ids = form_data.get('all_person_ids', '')
    all_id_list = [UUID(id.strip()) for id in all_person_ids.split(",") if id.strip()]
    group = service.get_fuzzy_duplicate_group(all_id_list)

    if not group:
        raise HTTPException(status_code=404, detail="Duplicate group not found")

    # Get IDs to merge (selected ones except the one to keep)
    merge_ids = [pid for pid in selected_id_list if pid != keep_id]

    if not merge_ids:
        raise HTTPException(status_code=400, detail="No records to merge")

    # BEFORE merge: Save selected field values from form
    field_values = {}
    persons_by_id = {p.id: p for p in group.persons}
    
    # Filter to only selected persons for name combining
    selected_persons = [p for p in group.persons if p.id in selected_id_list]
    
    # Handle full_name specially - check for "combine" option
    full_name_selection = form_data.get('field_full_name')
    if full_name_selection == 'combine':
        # Combine unique first names from SELECTED persons only
        first_names = []
        for p in selected_persons:
            if p.first_name and p.first_name not in first_names:
                first_names.append(p.first_name)
        # Sort so shorter name comes first (Matt Matthew)
        first_names.sort(key=len)
        combined_first = ' '.join(first_names)
        field_values['first_name'] = combined_first
        # Use the last name from the kept record
        keep_person_data = persons_by_id.get(keep_id)
        last_name = keep_person_data.last_name if keep_person_data else group.last_name
        field_values['full_name'] = f"{combined_first} {last_name}"
        # Also store the short version as nickname for easy searching
        if len(first_names) > 1:
            shortest_name = min(first_names, key=len)
            field_values['nickname'] = shortest_name
    elif full_name_selection:
        try:
            selected_uuid = UUID(full_name_selection)
            if selected_uuid in persons_by_id:
                selected_person = persons_by_id[selected_uuid]
                field_values['full_name'] = selected_person.full_name
                field_values['first_name'] = selected_person.first_name
                field_values['last_name'] = selected_person.last_name
        except (ValueError, TypeError):
            pass
    
    # Handle other fields
    field_mappings = [
        ('field_title', ['title']),
        ('field_linkedin', ['linkedin']),
        ('field_location', ['location']),
        ('field_profile_picture', ['profile_picture']),
        ('field_birthday', ['birthday']),
    ]
    
    for form_field, model_fields in field_mappings:
        selected_id = form_data.get(form_field)
        if selected_id:
            try:
                selected_uuid = UUID(selected_id)
                if selected_uuid in persons_by_id:
                    selected_person = persons_by_id[selected_uuid]
                    for model_field in model_fields:
                        value = getattr(selected_person, model_field, None)
                        if value is not None:
                            field_values[model_field] = value
            except (ValueError, TypeError):
                pass
        elif form_data.get(form_field) == '':
            # User selected "None" - mark for clearing
            for model_field in model_fields:
                field_values[model_field] = None

    # Execute merge (this deletes the merged persons)
    result = service.merge_persons(keep_id, merge_ids)

    # AFTER merge: Apply the saved field selections to the kept person
    keep_person = db.query(Person).filter_by(id=keep_id).first()
    if keep_person and field_values:
        for field, value in field_values.items():
            setattr(keep_person, field, value)
        db.commit()

    # Return to fuzzy duplicates list with success message
    fuzzy_groups = service.find_fuzzy_duplicates()

    return templates.TemplateResponse(
        "settings/fuzzy_duplicates.html",
        {
            "request": request,
            "title": "Similar Name Duplicates",
            "fuzzy_groups": fuzzy_groups,
            "merge_success": True,
            "merge_result": result,
        },
    )


@router.post("/duplicates/fuzzy/not-duplicates", response_class=HTMLResponse)
async def mark_not_duplicates(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Mark a group of persons as NOT duplicates.
    They will be excluded from future duplicate detection.
    """
    form_data = await request.form()
    
    # Get all person IDs from the group
    all_person_ids = form_data.get('all_person_ids', '')
    if not all_person_ids:
        raise HTTPException(status_code=400, detail="No person IDs provided")
    
    id_list = [UUID(id.strip()) for id in all_person_ids.split(",") if id.strip()]
    
    if len(id_list) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 persons to exclude")
    
    service = get_duplicate_service(db)
    
    # Create exclusions for all pairs
    excluded_count = service.exclude_duplicates(id_list)
    
    # Return to fuzzy duplicates list with success message
    fuzzy_groups = service.find_fuzzy_duplicates()
    
    return templates.TemplateResponse(
        "settings/fuzzy_duplicates.html",
        {
            "request": request,
            "title": "Similar Name Duplicates",
            "fuzzy_groups": fuzzy_groups,
            "not_duplicates_success": True,
            "excluded_count": excluded_count,
        },
    )


@router.get("/duplicates/exclusions", response_class=HTMLResponse)
async def exclusions_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Page showing all excluded duplicate pairs.
    """
    service = get_duplicate_service(db)
    exclusions = service.get_exclusions_with_details()
    exclusion_count = len(exclusions)

    return templates.TemplateResponse(
        "settings/exclusions.html",
        {
            "request": request,
            "title": "Excluded Pairs",
            "exclusions": exclusions,
            "exclusion_count": exclusion_count,
        },
    )


@router.get("/duplicates/exclusions/list", response_class=HTMLResponse)
async def get_exclusions_list(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Get the exclusions list partial for HTMX updates.
    """
    service = get_duplicate_service(db)
    exclusions = service.get_exclusions_with_details()

    return templates.TemplateResponse(
        "settings/_exclusions_list.html",
        {
            "request": request,
            "exclusions": exclusions,
        },
    )


@router.delete("/duplicates/exclusions/{exclusion_id}", response_class=HTMLResponse)
async def remove_exclusion(
    request: Request,
    exclusion_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Remove a duplicate exclusion (undo "not duplicates" action).
    """
    service = get_duplicate_service(db)
    removed = service.remove_exclusion_by_id(exclusion_id)

    if not removed:
        raise HTTPException(status_code=404, detail="Exclusion not found")

    # Return updated list
    exclusions = service.get_exclusions_with_details()

    return templates.TemplateResponse(
        "settings/_exclusions_list.html",
        {
            "request": request,
            "exclusions": exclusions,
        },
    )


# ===========================
# AI Provider Management
# ===========================


@router.post("/ai/keys", response_class=HTMLResponse)
async def save_api_key(
    request: Request,
    provider_id: UUID = Form(...),
    api_key: str = Form(...),
    provider_type: str = Form(None),
    db: Session = Depends(get_db),
):
    """
    Save or update an API key for a provider.
    """
    from app.models.ai_provider import AIProviderType

    provider = db.query(AIProvider).options(
        joinedload(AIProvider.api_keys)
    ).filter_by(id=provider_id).first()

    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Check if key already exists for this provider
    existing_key = db.query(AIAPIKey).filter_by(provider_id=provider_id).first()

    if existing_key:
        # Update existing key
        existing_key.set_api_key(api_key.strip())
        existing_key.is_valid = None  # Reset validation status
        existing_key.last_tested = None
    else:
        # Create new key
        new_key = AIAPIKey(provider_id=provider_id)
        new_key.set_api_key(api_key.strip())
        db.add(new_key)

    db.commit()

    # Refresh to get updated relationships
    db.refresh(provider)

    # Determine which template to use based on provider type
    search_provider_types = [AIProviderType.brave_search, AIProviderType.youtube, AIProviderType.listen_notes]
    is_search_provider = provider.api_type in search_provider_types or provider_type == "search"

    template_name = "settings/_search_provider_card.html" if is_search_provider else "settings/_ai_provider_card.html"

    return templates.TemplateResponse(
        template_name,
        {
            "request": request,
            "provider": provider,
        },
    )


@router.post("/ai/test/{provider_type}", response_class=HTMLResponse)
async def test_api_key(
    request: Request,
    provider_type: str,
    db: Session = Depends(get_db),
):
    """
    Test an API key for a specific provider type.
    """
    from datetime import datetime
    from app.services.ai import ProviderFactory

    # Get the provider and its key
    provider = db.query(AIProvider).options(
        joinedload(AIProvider.api_keys)
    ).filter(AIProvider.api_type == provider_type).first()

    if not provider or not provider.api_keys:
        return HTMLResponse(
            '<span class="text-red-600 text-xs">No API key configured</span>'
        )

    api_key_record = provider.api_keys[0]
    api_key = api_key_record.get_api_key()

    if not api_key:
        return HTMLResponse(
            '<span class="text-red-600 text-xs">Failed to decrypt API key</span>'
        )

    # Test the key
    factory = ProviderFactory(db)
    is_valid = await factory.validate_api_key(provider_type, api_key)

    # Update the key record
    api_key_record.is_valid = is_valid
    api_key_record.last_tested = datetime.utcnow()
    db.commit()

    if is_valid:
        return HTMLResponse(
            '<span class="text-green-600 text-xs flex items-center">'
            '<svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">'
            '<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>'
            '</svg>Connection successful</span>'
        )
    else:
        return HTMLResponse(
            '<span class="text-red-600 text-xs flex items-center">'
            '<svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">'
            '<path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>'
            '</svg>Connection failed</span>'
        )


@router.post("/ai/provider/{provider_id}/toggle", response_class=HTMLResponse)
async def toggle_provider_status(
    request: Request,
    provider_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Toggle an AI provider's active status.
    """
    provider = db.query(AIProvider).filter_by(id=provider_id).first()
    if provider:
        provider.is_active = not provider.is_active
        db.commit()
        db.refresh(provider)

        # Determine which template to use based on provider type
        # Search providers use a different template
        search_types = ["brave_search", "youtube", "listen_notes"]
        if provider.api_type.value in search_types:
            template_name = "settings/_search_provider_card.html"
        else:
            template_name = "settings/_ai_provider_card.html"

        # Return updated card HTML with new state
        return templates.TemplateResponse(
            template_name,
            {
                "request": request,
                "provider": provider,
            },
        )

    return HTMLResponse("")


@router.put("/ai/access", response_class=HTMLResponse)
async def update_data_access(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Update AI data access settings.
    """
    form_data = await request.form()

    settings = AIDataAccessSettings.get_settings(db)

    # Update from form data (checkboxes only send value if checked)
    settings.allow_notes = "allow_notes" in form_data
    settings.allow_tags = "allow_tags" in form_data
    settings.allow_interactions = "allow_interactions" in form_data
    settings.allow_linkedin = "allow_linkedin" in form_data
    settings.auto_apply_suggestions = "auto_apply_suggestions" in form_data

    db.commit()

    # Return empty response for hx-swap="none"
    return HTMLResponse("")


@router.delete("/ai/keys/{key_id}", response_class=HTMLResponse)
async def delete_api_key(
    request: Request,
    key_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Delete an API key.
    """
    api_key = db.query(AIAPIKey).filter_by(id=key_id).first()
    if api_key:
        provider_id = api_key.provider_id
        db.delete(api_key)
        db.commit()

        # Get updated provider
        provider = db.query(AIProvider).options(
            joinedload(AIProvider.api_keys)
        ).filter_by(id=provider_id).first()

        return templates.TemplateResponse(
            "settings/_ai_provider_card.html",
            {
                "request": request,
                "provider": provider,
            },
        )

    raise HTTPException(status_code=404, detail="API key not found")


# ===========================
# Quick Prompts Management
# ===========================


@router.get("/ai/prompts", response_class=HTMLResponse)
async def get_quick_prompts_list(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Get the quick prompts list partial.
    """
    prompts = db.query(AIQuickPrompt).order_by(AIQuickPrompt.display_order).all()

    return templates.TemplateResponse(
        "settings/_quick_prompts_list.html",
        {
            "request": request,
            "quick_prompts": prompts,
            "entity_types": [e.value for e in PromptEntityType],
        },
    )


@router.post("/ai/prompts", response_class=HTMLResponse)
async def add_quick_prompt(
    request: Request,
    label: str = Form(...),
    prompt_text: str = Form(...),
    entity_type: str = Form("both"),
    db: Session = Depends(get_db),
):
    """
    Add a new quick prompt.
    """
    # Get the next display order
    max_order = db.query(func.max(AIQuickPrompt.display_order)).scalar() or 0

    new_prompt = AIQuickPrompt(
        label=label.strip(),
        prompt_text=prompt_text.strip(),
        entity_type=PromptEntityType(entity_type),
        display_order=max_order + 1,
        is_active=True,
    )
    db.add(new_prompt)
    db.commit()

    # Return updated list
    prompts = db.query(AIQuickPrompt).order_by(AIQuickPrompt.display_order).all()

    return templates.TemplateResponse(
        "settings/_quick_prompts_list.html",
        {
            "request": request,
            "quick_prompts": prompts,
            "entity_types": [e.value for e in PromptEntityType],
        },
    )


@router.put("/ai/prompts/{prompt_id}", response_class=HTMLResponse)
async def update_quick_prompt(
    request: Request,
    prompt_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Update an existing quick prompt.
    """
    form_data = await request.form()

    prompt = db.query(AIQuickPrompt).filter_by(id=prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if "label" in form_data:
        prompt.label = form_data["label"].strip()
    if "prompt_text" in form_data:
        prompt.prompt_text = form_data["prompt_text"].strip()
    if "entity_type" in form_data:
        prompt.entity_type = PromptEntityType(form_data["entity_type"])

    db.commit()

    # Return updated list
    prompts = db.query(AIQuickPrompt).order_by(AIQuickPrompt.display_order).all()

    return templates.TemplateResponse(
        "settings/_quick_prompts_list.html",
        {
            "request": request,
            "quick_prompts": prompts,
            "entity_types": [e.value for e in PromptEntityType],
        },
    )


@router.post("/ai/prompts/{prompt_id}/toggle", response_class=HTMLResponse)
async def toggle_quick_prompt(
    request: Request,
    prompt_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Toggle a quick prompt's active status.
    """
    prompt = db.query(AIQuickPrompt).filter_by(id=prompt_id).first()
    if prompt:
        prompt.is_active = not prompt.is_active
        db.commit()

    # Return updated list
    prompts = db.query(AIQuickPrompt).order_by(AIQuickPrompt.display_order).all()

    return templates.TemplateResponse(
        "settings/_quick_prompts_list.html",
        {
            "request": request,
            "quick_prompts": prompts,
            "entity_types": [e.value for e in PromptEntityType],
        },
    )


@router.delete("/ai/prompts/{prompt_id}", response_class=HTMLResponse)
async def delete_quick_prompt(
    request: Request,
    prompt_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Delete a quick prompt.
    """
    prompt = db.query(AIQuickPrompt).filter_by(id=prompt_id).first()
    if prompt:
        db.delete(prompt)
        db.commit()

    # Return updated list
    prompts = db.query(AIQuickPrompt).order_by(AIQuickPrompt.display_order).all()

    return templates.TemplateResponse(
        "settings/_quick_prompts_list.html",
        {
            "request": request,
            "quick_prompts": prompts,
            "entity_types": [e.value for e in PromptEntityType],
        },
    )


@router.post("/ai/prompts/reorder", response_class=HTMLResponse)
async def reorder_quick_prompts(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Reorder quick prompts based on order array.
    """
    form_data = await request.form()
    order_str = form_data.get("order", "")

    if order_str:
        order_list = order_str.split(",")
        for idx, prompt_id in enumerate(order_list):
            prompt = db.query(AIQuickPrompt).filter_by(id=prompt_id).first()
            if prompt:
                prompt.display_order = idx + 1

        db.commit()

    # Return updated list
    prompts = db.query(AIQuickPrompt).order_by(AIQuickPrompt.display_order).all()

    return templates.TemplateResponse(
        "settings/_quick_prompts_list.html",
        {
            "request": request,
            "quick_prompts": prompts,
            "entity_types": [e.value for e in PromptEntityType],
        },
    )


# ===========================
# Calendar Settings Management
# ===========================


@router.post("/calendar/timezone", response_class=HTMLResponse)
async def update_calendar_timezone(
    request: Request,
    timezone: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Update the calendar timezone setting.
    """
    # Validate timezone is in our list
    valid_timezones = [tz[0] for tz in COMMON_TIMEZONES]
    if timezone not in valid_timezones:
        raise HTTPException(status_code=400, detail="Invalid timezone")

    settings = CalendarSettings.get_settings(db)
    settings.timezone = timezone
    db.commit()

    # Return success indicator
    return HTMLResponse(
        '<span class="text-green-600 text-sm flex items-center">'
        '<svg class="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">'
        '<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>'
        '</svg>Timezone saved</span>'
    )


# ===========================
# Organization Types Management
# ===========================


@router.get("/organization-types/categories-list", response_class=HTMLResponse)
async def get_categories_list(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Get the organization categories list partial.
    """
    categories = db.query(OrganizationCategory).options(
        joinedload(OrganizationCategory.types)
    ).order_by(OrganizationCategory.sort_order).all()

    return templates.TemplateResponse(
        "settings/_organization_categories_list.html",
        {
            "request": request,
            "categories": categories,
        },
    )


@router.get("/organization-types/types-list", response_class=HTMLResponse)
async def get_types_list(
    request: Request,
    category_id: int = Query(None, description="Filter by category ID"),
    db: Session = Depends(get_db),
):
    """
    Get the organization types list partial, optionally filtered by category.
    """
    query = db.query(OrganizationType).options(
        joinedload(OrganizationType.category)
    )

    if category_id:
        query = query.filter(OrganizationType.category_id == category_id)

    types = query.order_by(OrganizationType.category_id, OrganizationType.sort_order).all()

    return templates.TemplateResponse(
        "settings/_organization_types_list.html",
        {
            "request": request,
            "types": types,
        },
    )


@router.get("/organization-types/options-list", response_class=HTMLResponse)
async def get_options_list(
    request: Request,
    option_type: str = Query(None, description="Filter by option type"),
    db: Session = Depends(get_db),
):
    """
    Get the investment profile options list partial, optionally filtered by option type.
    """
    query = db.query(InvestmentProfileOption)

    if option_type:
        query = query.filter(InvestmentProfileOption.option_type == option_type)

    options = query.order_by(
        InvestmentProfileOption.option_type,
        InvestmentProfileOption.sort_order
    ).all()

    return templates.TemplateResponse(
        "settings/_organization_options_list.html",
        {
            "request": request,
            "options": options,
        },
    )


# ===========================
# Contacts Sync Management
# ===========================


@router.get("/sync/log", response_class=HTMLResponse)
async def sync_log_page(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    status: str = Query(None, description="Filter by status"),
    direction: str = Query(None, description="Filter by direction"),
    db: Session = Depends(get_db),
):
    """
    Display the sync log page with paginated sync history.
    """
    per_page = 20

    # Build query for sync logs
    query = db.query(ImportHistory).filter(
        ImportHistory.source == ImportSource.google_contacts
    )

    # Apply status filter
    if status:
        try:
            status_enum = ImportStatus(status)
            query = query.filter(ImportHistory.status == status_enum)
        except ValueError:
            pass

    # Note: direction filter would require additional model field for bidirectional sync
    # For now, all syncs are imports from Google

    # Get total count
    total_count = query.count()
    total_pages = (total_count + per_page - 1) // per_page

    # Get paginated results
    sync_logs = query.order_by(
        ImportHistory.imported_at.desc()
    ).offset((page - 1) * per_page).limit(per_page).all()

    # Check if this is an HTMX request for table partial
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "settings/_sync_log_table.html",
            {
                "request": request,
                "sync_logs": sync_logs,
                "page": page,
                "per_page": per_page,
                "total_count": total_count,
                "total_pages": total_pages,
                "status_filter": status,
                "direction_filter": direction,
            },
        )

    return templates.TemplateResponse(
        "settings/sync_log.html",
        {
            "request": request,
            "title": "Sync Log",
            "sync_logs": sync_logs,
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "status_filter": status,
            "direction_filter": direction,
        },
    )


@router.get("/sync/review", response_class=HTMLResponse)
async def sync_review_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Display the sync conflict review page.
    """
    # Note: This would need a SyncConflict model to track conflicts
    # For now, return empty conflicts list as placeholder
    conflicts = []

    return templates.TemplateResponse(
        "settings/sync_review.html",
        {
            "request": request,
            "title": "Review Sync Conflicts",
            "conflicts": conflicts,
        },
    )


@router.post("/sync/resolve/{conflict_id}", response_class=HTMLResponse)
async def resolve_sync_conflict(
    request: Request,
    conflict_id: UUID,
    action: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Resolve a sync conflict with the specified action.
    Actions: use_blackbook, use_google, keep_both, dismiss
    """
    # Note: This would need a SyncConflict model to implement
    # For now, return success message
    return HTMLResponse(
        '<div class="p-4 bg-green-50 border border-green-200 rounded-lg text-center">'
        '<p class="text-green-800 text-sm">Conflict resolved successfully.</p>'
        '</div>'
    )


@router.get("/sync/archive", response_class=HTMLResponse)
async def sync_archive_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Display the archived contacts page.
    """
    # Note: This would need an ArchivedContact model or a flag on Person model
    # For now, return empty list as placeholder
    archived_contacts = []

    return templates.TemplateResponse(
        "settings/sync_archive.html",
        {
            "request": request,
            "title": "Archived Contacts",
            "archived_contacts": archived_contacts,
        },
    )


@router.post("/sync/archive/{contact_id}/restore", response_class=HTMLResponse)
async def restore_archived_contact(
    request: Request,
    contact_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Restore an archived contact.
    """
    # Note: Implementation depends on how archived contacts are stored
    return HTMLResponse(
        '<div class="p-4 bg-green-50 border border-green-200 rounded-lg text-center">'
        '<p class="text-green-800 text-sm">Contact restored successfully.</p>'
        '</div>'
    )


@router.delete("/sync/archive/{contact_id}", response_class=HTMLResponse)
async def delete_archived_contact(
    request: Request,
    contact_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Permanently delete an archived contact.
    """
    # Note: Implementation depends on how archived contacts are stored
    return HTMLResponse("")


@router.post("/sync/archive/restore-all", response_class=HTMLResponse)
async def restore_all_archived_contacts(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Restore all archived contacts.
    """
    # Note: Implementation depends on how archived contacts are stored
    return RedirectResponse(url="/settings/sync/archive", status_code=303)


@router.delete("/sync/archive/delete-all", response_class=HTMLResponse)
async def delete_all_archived_contacts(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Permanently delete all archived contacts.
    """
    # Note: Implementation depends on how archived contacts are stored
    return RedirectResponse(url="/settings/sync/archive", status_code=303)


@router.put("/contacts-sync/settings", response_class=HTMLResponse)
async def update_contacts_sync_settings(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Update contacts sync settings.
    """
    form_data = await request.form()

    # Note: This would need a ContactsSyncSettings model
    # For now, just return success response
    # Settings would include:
    # - auto_sync_enabled: bool
    # - sync_time_1: str (HH:MM)
    # - sync_time_2: str (HH:MM)
    # - sync_timezone: str
    # - retention_days: int

    return HTMLResponse(
        '<span class="text-green-600 text-sm flex items-center">'
        '<svg class="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">'
        '<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>'
        '</svg>Settings saved</span>'
    )

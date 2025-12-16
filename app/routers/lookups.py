"""
Lookups router for Perun's BlackBook.

Provides API endpoints for retrieving lookup data:
- Organization categories
- Organization types (filtered by category)
- Investment profile options
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    OrganizationCategory,
    OrganizationType,
    InvestmentProfileOption,
)

router = APIRouter(prefix="/api/lookups", tags=["lookups"])


# ===========================
# Organization Categories
# ===========================


@router.get("/categories")
async def get_categories(
    active_only: bool = Query(True, description="Only return active categories"),
    db: Session = Depends(get_db),
):
    """
    Get all organization categories.

    Returns list of categories with their types count.
    """
    query = db.query(OrganizationCategory)
    if active_only:
        query = query.filter(OrganizationCategory.is_active == True)

    categories = query.order_by(OrganizationCategory.sort_order).all()

    return [
        {
            "id": cat.id,
            "code": cat.code,
            "name": cat.name,
            "description": cat.description,
            "has_investment_profile": cat.has_investment_profile,
            "sort_order": cat.sort_order,
            "is_active": cat.is_active,
            "types_count": len([t for t in cat.types if t.is_active]) if active_only else len(cat.types),
        }
        for cat in categories
    ]


@router.get("/categories/{category_id}")
async def get_category(
    category_id: int,
    db: Session = Depends(get_db),
):
    """
    Get a single category by ID with its types.
    """
    category = db.query(OrganizationCategory).filter(
        OrganizationCategory.id == category_id
    ).first()

    if not category:
        return JSONResponse(status_code=404, content={"detail": "Category not found"})

    return {
        "id": category.id,
        "code": category.code,
        "name": category.name,
        "description": category.description,
        "has_investment_profile": category.has_investment_profile,
        "sort_order": category.sort_order,
        "is_active": category.is_active,
        "types": [
            {
                "id": t.id,
                "code": t.code,
                "name": t.name,
                "profile_style": t.profile_style,
                "sort_order": t.sort_order,
                "is_active": t.is_active,
            }
            for t in category.types
        ],
    }


# ===========================
# Organization Types
# ===========================


@router.get("/types")
async def get_types(
    category_id: int = Query(None, description="Filter by category ID"),
    category_code: str = Query(None, description="Filter by category code"),
    active_only: bool = Query(True, description="Only return active types"),
    db: Session = Depends(get_db),
):
    """
    Get organization types, optionally filtered by category.

    Can filter by category_id or category_code.
    """
    query = db.query(OrganizationType)

    if category_id:
        query = query.filter(OrganizationType.category_id == category_id)
    elif category_code:
        category = db.query(OrganizationCategory).filter(
            OrganizationCategory.code == category_code
        ).first()
        if category:
            query = query.filter(OrganizationType.category_id == category.id)
        else:
            return []

    if active_only:
        query = query.filter(OrganizationType.is_active == True)

    types = query.order_by(OrganizationType.sort_order).all()

    return [
        {
            "id": t.id,
            "category_id": t.category_id,
            "category_code": t.category.code if t.category else None,
            "category_name": t.category.name if t.category else None,
            "code": t.code,
            "name": t.name,
            "description": t.description,
            "profile_style": t.profile_style,
            "sort_order": t.sort_order,
            "is_active": t.is_active,
        }
        for t in types
    ]


@router.get("/types/{type_id}")
async def get_type(
    type_id: int,
    db: Session = Depends(get_db),
):
    """
    Get a single type by ID.
    """
    org_type = db.query(OrganizationType).filter(
        OrganizationType.id == type_id
    ).first()

    if not org_type:
        return JSONResponse(status_code=404, content={"detail": "Type not found"})

    return {
        "id": org_type.id,
        "category_id": org_type.category_id,
        "category_code": org_type.category.code if org_type.category else None,
        "category_name": org_type.category.name if org_type.category else None,
        "code": org_type.code,
        "name": org_type.name,
        "description": org_type.description,
        "profile_style": org_type.profile_style,
        "sort_order": org_type.sort_order,
        "is_active": org_type.is_active,
    }


# ===========================
# Investment Profile Options
# ===========================


@router.get("/options")
async def get_options(
    option_type: str = Query(None, description="Filter by option type (e.g., vc_stage, pe_deal_type)"),
    active_only: bool = Query(True, description="Only return active options"),
    db: Session = Depends(get_db),
):
    """
    Get investment profile options, optionally filtered by type.

    Option types include:
    - vc_stage: Pre-Seed, Seed, Series A, etc.
    - vc_sector: SaaS, Fintech, Healthcare, etc.
    - pe_deal_type: LBO, Growth Equity, Recap, etc.
    - pe_industry: Business Services, Healthcare Services, etc.
    - control_preference: Majority, Minority, Either
    - credit_strategy: Direct Lending, Mezzanine, etc.
    - investment_style: Direct, Co-Investment, Fund Investment
    - asset_class: Venture Capital, Private Equity, etc.
    - trading_strategy: Long/Short Equity, Activist, etc.
    """
    query = db.query(InvestmentProfileOption)

    if option_type:
        query = query.filter(InvestmentProfileOption.option_type == option_type)

    if active_only:
        query = query.filter(InvestmentProfileOption.is_active == True)

    options = query.order_by(
        InvestmentProfileOption.option_type,
        InvestmentProfileOption.sort_order,
    ).all()

    return [
        {
            "id": opt.id,
            "option_type": opt.option_type,
            "code": opt.code,
            "name": opt.name,
            "sort_order": opt.sort_order,
            "is_active": opt.is_active,
        }
        for opt in options
    ]


@router.get("/options/grouped")
async def get_options_grouped(
    active_only: bool = Query(True, description="Only return active options"),
    db: Session = Depends(get_db),
):
    """
    Get all investment profile options grouped by option_type.

    Returns a dictionary where keys are option types and values are lists of options.
    """
    query = db.query(InvestmentProfileOption)

    if active_only:
        query = query.filter(InvestmentProfileOption.is_active == True)

    options = query.order_by(
        InvestmentProfileOption.option_type,
        InvestmentProfileOption.sort_order,
    ).all()

    # Group by option_type
    grouped = {}
    for opt in options:
        if opt.option_type not in grouped:
            grouped[opt.option_type] = []
        grouped[opt.option_type].append({
            "id": opt.id,
            "code": opt.code,
            "name": opt.name,
            "sort_order": opt.sort_order,
        })

    return grouped


# ===========================
# Combined Lookups for Forms
# ===========================


@router.get("/organization-form-data")
async def get_organization_form_data(
    db: Session = Depends(get_db),
):
    """
    Get all lookup data needed for organization create/edit forms.

    Returns categories, types (grouped by category), and profile options (grouped by type).
    This is a convenience endpoint to reduce the number of API calls.
    """
    # Get active categories
    categories = db.query(OrganizationCategory).filter(
        OrganizationCategory.is_active == True
    ).order_by(OrganizationCategory.sort_order).all()

    # Get active types grouped by category
    types_by_category = {}
    for cat in categories:
        types_by_category[cat.code] = [
            {
                "id": t.id,
                "code": t.code,
                "name": t.name,
                "profile_style": t.profile_style,
            }
            for t in cat.types if t.is_active
        ]

    # Get active options grouped by type
    options = db.query(InvestmentProfileOption).filter(
        InvestmentProfileOption.is_active == True
    ).order_by(
        InvestmentProfileOption.option_type,
        InvestmentProfileOption.sort_order,
    ).all()

    options_grouped = {}
    for opt in options:
        if opt.option_type not in options_grouped:
            options_grouped[opt.option_type] = []
        options_grouped[opt.option_type].append({
            "code": opt.code,
            "name": opt.name,
        })

    return {
        "categories": [
            {
                "id": cat.id,
                "code": cat.code,
                "name": cat.name,
                "has_investment_profile": cat.has_investment_profile,
            }
            for cat in categories
        ],
        "types_by_category": types_by_category,
        "profile_options": options_grouped,
    }

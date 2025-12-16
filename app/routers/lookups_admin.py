"""
Lookups Admin router for Perun's BlackBook.

Provides API endpoints for managing organization type lookup data:
- CRUD operations for categories, types, and options (form-based for HTMX)
- Reordering support
- Validation for type-category relationships
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from typing import Optional

from app.database import get_db
from app.models import (
    OrganizationCategory,
    OrganizationType,
    InvestmentProfileOption,
    Organization,
)


router = APIRouter(prefix="/api/lookups/admin", tags=["lookups-admin"])
templates = Jinja2Templates(directory="app/templates")


# ===========================
# Pydantic Models for JSON API Requests
# ===========================


class CategoryCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    has_investment_profile: bool = False
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    has_investment_profile: Optional[bool] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class TypeCreate(BaseModel):
    category_id: int
    code: str
    name: str
    description: Optional[str] = None
    profile_style: Optional[str] = None
    sort_order: int = 0


class TypeUpdate(BaseModel):
    category_id: Optional[int] = None
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    profile_style: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class OptionCreate(BaseModel):
    option_type: str
    code: str
    name: str
    sort_order: int = 0


class OptionUpdate(BaseModel):
    option_type: Optional[str] = None
    code: Optional[str] = None
    name: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class ReorderRequest(BaseModel):
    ids: list[int]


# ===========================
# Helper Functions
# ===========================


def _get_all_categories(db: Session):
    """Get all categories with their types loaded."""
    return db.query(OrganizationCategory).options(
        joinedload(OrganizationCategory.types)
    ).order_by(OrganizationCategory.sort_order).all()


def _get_all_types(db: Session, category_id: Optional[int] = None):
    """Get all types with category loaded, optionally filtered."""
    query = db.query(OrganizationType).options(
        joinedload(OrganizationType.category)
    )
    if category_id:
        query = query.filter(OrganizationType.category_id == category_id)
    return query.order_by(OrganizationType.category_id, OrganizationType.sort_order).all()


def _get_all_options(db: Session, option_type: Optional[str] = None):
    """Get all options, optionally filtered by type."""
    query = db.query(InvestmentProfileOption)
    if option_type:
        query = query.filter(InvestmentProfileOption.option_type == option_type)
    return query.order_by(
        InvestmentProfileOption.option_type,
        InvestmentProfileOption.sort_order
    ).all()


# ===========================
# Organization Categories CRUD (Form-based for HTMX)
# ===========================


@router.post("/categories", response_class=HTMLResponse)
async def create_category(
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    description: str = Form(None),
    has_investment_profile: str = Form(None),
    db: Session = Depends(get_db),
):
    """Create a new organization category (returns HTML partial)."""
    # Check for duplicate code
    existing = db.query(OrganizationCategory).filter(
        OrganizationCategory.code == code
    ).first()
    if existing:
        # Return error message - for now just return the list
        categories = _get_all_categories(db)
        return templates.TemplateResponse(
            "settings/_organization_categories_list.html",
            {"request": request, "categories": categories}
        )

    # Determine next sort_order
    max_order = db.query(OrganizationCategory).count()

    category = OrganizationCategory(
        code=code,
        name=name,
        description=description if description else None,
        has_investment_profile=has_investment_profile == "true",
        sort_order=max_order + 1,
    )
    db.add(category)
    db.commit()

    # Return updated categories list
    categories = _get_all_categories(db)
    return templates.TemplateResponse(
        "settings/_organization_categories_list.html",
        {"request": request, "categories": categories}
    )


@router.put("/categories/{category_id}", response_class=HTMLResponse)
async def update_category(
    request: Request,
    category_id: int,
    code: str = Form(...),
    name: str = Form(...),
    description: str = Form(None),
    has_investment_profile: str = Form(None),
    is_active: str = Form(None),
    db: Session = Depends(get_db),
):
    """Update an organization category (returns HTML partial)."""
    category = db.query(OrganizationCategory).filter(
        OrganizationCategory.id == category_id
    ).first()

    if not category:
        categories = _get_all_categories(db)
        return templates.TemplateResponse(
            "settings/_organization_categories_list.html",
            {"request": request, "categories": categories}
        )

    # Check for duplicate code if changing
    if code and code != category.code:
        existing = db.query(OrganizationCategory).filter(
            OrganizationCategory.code == code
        ).first()
        if existing:
            categories = _get_all_categories(db)
            return templates.TemplateResponse(
                "settings/_organization_categories_list.html",
                {"request": request, "categories": categories}
            )

    # Update fields
    category.code = code
    category.name = name
    category.description = description if description else None
    category.has_investment_profile = has_investment_profile == "true"
    category.is_active = is_active == "true"

    db.commit()

    # Return updated categories list
    categories = _get_all_categories(db)
    return templates.TemplateResponse(
        "settings/_organization_categories_list.html",
        {"request": request, "categories": categories}
    )


@router.delete("/categories/{category_id}", response_class=HTMLResponse)
async def delete_category(
    request: Request,
    category_id: int,
    force: bool = Query(False, description="Force delete even if types exist"),
    db: Session = Depends(get_db),
):
    """Delete an organization category (returns HTML partial)."""
    category = db.query(OrganizationCategory).filter(
        OrganizationCategory.id == category_id
    ).first()

    if category:
        # Check for associated types
        types_count = db.query(OrganizationType).filter(
            OrganizationType.category_id == category_id
        ).count()

        # Check for organizations using this category
        orgs_count = db.query(Organization).filter(
            Organization.category_id == category_id
        ).count()

        if types_count > 0 or orgs_count > 0:
            if force:
                # Deactivate instead of delete
                category.is_active = False
                db.commit()
            # If not force and has associations, don't delete
        else:
            db.delete(category)
            db.commit()

    # Return updated categories list
    categories = _get_all_categories(db)
    return templates.TemplateResponse(
        "settings/_organization_categories_list.html",
        {"request": request, "categories": categories}
    )


@router.post("/categories/reorder")
async def reorder_categories(
    data: ReorderRequest,
    db: Session = Depends(get_db),
):
    """Reorder categories by providing list of IDs in desired order."""
    for index, cat_id in enumerate(data.ids):
        db.query(OrganizationCategory).filter(
            OrganizationCategory.id == cat_id
        ).update({"sort_order": index + 1})

    db.commit()
    return {"message": "Categories reordered", "order": data.ids}


# ===========================
# Organization Types CRUD (Form-based for HTMX)
# ===========================


@router.post("/types", response_class=HTMLResponse)
async def create_type(
    request: Request,
    category_id: int = Form(...),
    code: str = Form(...),
    name: str = Form(...),
    description: str = Form(None),
    profile_style: str = Form(None),
    db: Session = Depends(get_db),
):
    """Create a new organization type (returns HTML partial)."""
    # Verify category exists
    category = db.query(OrganizationCategory).filter(
        OrganizationCategory.id == category_id
    ).first()
    if not category:
        types = _get_all_types(db)
        return templates.TemplateResponse(
            "settings/_organization_types_list.html",
            {"request": request, "types": types}
        )

    # Check for duplicate code
    existing = db.query(OrganizationType).filter(
        OrganizationType.code == code
    ).first()
    if existing:
        types = _get_all_types(db)
        return templates.TemplateResponse(
            "settings/_organization_types_list.html",
            {"request": request, "types": types}
        )

    # Determine next sort_order within category
    max_order = db.query(OrganizationType).filter(
        OrganizationType.category_id == category_id
    ).count()

    org_type = OrganizationType(
        category_id=category_id,
        code=code,
        name=name,
        description=description if description else None,
        profile_style=profile_style if profile_style else None,
        sort_order=max_order + 1,
    )
    db.add(org_type)
    db.commit()

    # Return updated types list
    types = _get_all_types(db)
    return templates.TemplateResponse(
        "settings/_organization_types_list.html",
        {"request": request, "types": types}
    )


@router.put("/types/{type_id}", response_class=HTMLResponse)
async def update_type(
    request: Request,
    type_id: int,
    category_id: int = Form(...),
    code: str = Form(...),
    name: str = Form(...),
    description: str = Form(None),
    profile_style: str = Form(None),
    is_active: str = Form(None),
    db: Session = Depends(get_db),
):
    """Update an organization type (returns HTML partial)."""
    org_type = db.query(OrganizationType).filter(
        OrganizationType.id == type_id
    ).first()

    if not org_type:
        types = _get_all_types(db)
        return templates.TemplateResponse(
            "settings/_organization_types_list.html",
            {"request": request, "types": types}
        )

    # Check category exists if changing
    if category_id != org_type.category_id:
        category = db.query(OrganizationCategory).filter(
            OrganizationCategory.id == category_id
        ).first()
        if not category:
            types = _get_all_types(db)
            return templates.TemplateResponse(
                "settings/_organization_types_list.html",
                {"request": request, "types": types}
            )

    # Check for duplicate code if changing
    if code and code != org_type.code:
        existing = db.query(OrganizationType).filter(
            OrganizationType.code == code
        ).first()
        if existing:
            types = _get_all_types(db)
            return templates.TemplateResponse(
                "settings/_organization_types_list.html",
                {"request": request, "types": types}
            )

    # Update fields
    org_type.category_id = category_id
    org_type.code = code
    org_type.name = name
    org_type.description = description if description else None
    org_type.profile_style = profile_style if profile_style else None
    org_type.is_active = is_active == "true"

    db.commit()

    # Return updated types list
    types = _get_all_types(db)
    return templates.TemplateResponse(
        "settings/_organization_types_list.html",
        {"request": request, "types": types}
    )


@router.delete("/types/{type_id}", response_class=HTMLResponse)
async def delete_type(
    request: Request,
    type_id: int,
    force: bool = Query(False, description="Force delete even if organizations use this type"),
    db: Session = Depends(get_db),
):
    """Delete an organization type (returns HTML partial)."""
    org_type = db.query(OrganizationType).filter(
        OrganizationType.id == type_id
    ).first()

    if org_type:
        # Check for organizations using this type
        orgs_count = db.query(Organization).filter(
            Organization.type_id == type_id
        ).count()

        if orgs_count > 0:
            if force:
                # Deactivate instead of delete
                org_type.is_active = False
                db.commit()
            # If not force and has associations, don't delete
        else:
            db.delete(org_type)
            db.commit()

    # Return updated types list
    types = _get_all_types(db)
    return templates.TemplateResponse(
        "settings/_organization_types_list.html",
        {"request": request, "types": types}
    )


@router.post("/types/reorder")
async def reorder_types(
    category_id: int,
    data: ReorderRequest,
    db: Session = Depends(get_db),
):
    """Reorder types within a category by providing list of IDs in desired order."""
    for index, type_id in enumerate(data.ids):
        db.query(OrganizationType).filter(
            OrganizationType.id == type_id,
            OrganizationType.category_id == category_id,
        ).update({"sort_order": index + 1})

    db.commit()
    return {"message": "Types reordered", "category_id": category_id, "order": data.ids}


# ===========================
# Investment Profile Options CRUD (Form-based for HTMX)
# ===========================


@router.post("/options", response_class=HTMLResponse)
async def create_option(
    request: Request,
    option_type: str = Form(...),
    code: str = Form(...),
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    """Create a new investment profile option (returns HTML partial)."""
    # Check for duplicate option_type + code combination
    existing = db.query(InvestmentProfileOption).filter(
        InvestmentProfileOption.option_type == option_type,
        InvestmentProfileOption.code == code,
    ).first()
    if existing:
        options = _get_all_options(db)
        return templates.TemplateResponse(
            "settings/_organization_options_list.html",
            {"request": request, "options": options}
        )

    # Determine next sort_order within option_type
    max_order = db.query(InvestmentProfileOption).filter(
        InvestmentProfileOption.option_type == option_type
    ).count()

    option = InvestmentProfileOption(
        option_type=option_type,
        code=code,
        name=name,
        sort_order=max_order + 1,
    )
    db.add(option)
    db.commit()

    # Return updated options list
    options = _get_all_options(db)
    return templates.TemplateResponse(
        "settings/_organization_options_list.html",
        {"request": request, "options": options}
    )


@router.put("/options/{option_id}", response_class=HTMLResponse)
async def update_option(
    request: Request,
    option_id: int,
    option_type: str = Form(...),
    code: str = Form(...),
    name: str = Form(...),
    is_active: str = Form(None),
    db: Session = Depends(get_db),
):
    """Update an investment profile option (returns HTML partial)."""
    option = db.query(InvestmentProfileOption).filter(
        InvestmentProfileOption.id == option_id
    ).first()

    if not option:
        options = _get_all_options(db)
        return templates.TemplateResponse(
            "settings/_organization_options_list.html",
            {"request": request, "options": options}
        )

    # Check for duplicate if changing type or code
    if option_type != option.option_type or code != option.code:
        existing = db.query(InvestmentProfileOption).filter(
            InvestmentProfileOption.option_type == option_type,
            InvestmentProfileOption.code == code,
        ).first()
        if existing:
            options = _get_all_options(db)
            return templates.TemplateResponse(
                "settings/_organization_options_list.html",
                {"request": request, "options": options}
            )

    # Update fields
    option.option_type = option_type
    option.code = code
    option.name = name
    option.is_active = is_active == "true"

    db.commit()

    # Return updated options list
    options = _get_all_options(db)
    return templates.TemplateResponse(
        "settings/_organization_options_list.html",
        {"request": request, "options": options}
    )


@router.delete("/options/{option_id}", response_class=HTMLResponse)
async def delete_option(
    request: Request,
    option_id: int,
    db: Session = Depends(get_db),
):
    """Delete an investment profile option (returns HTML partial)."""
    option = db.query(InvestmentProfileOption).filter(
        InvestmentProfileOption.id == option_id
    ).first()

    if option:
        db.delete(option)
        db.commit()

    # Return updated options list
    options = _get_all_options(db)
    return templates.TemplateResponse(
        "settings/_organization_options_list.html",
        {"request": request, "options": options}
    )


@router.post("/options/reorder")
async def reorder_options(
    option_type: str,
    data: ReorderRequest,
    db: Session = Depends(get_db),
):
    """Reorder options within an option_type by providing list of IDs in desired order."""
    for index, option_id in enumerate(data.ids):
        db.query(InvestmentProfileOption).filter(
            InvestmentProfileOption.id == option_id,
            InvestmentProfileOption.option_type == option_type,
        ).update({"sort_order": index + 1})

    db.commit()
    return {"message": "Options reordered", "option_type": option_type, "order": data.ids}


# ===========================
# Validation Helpers
# ===========================


@router.get("/validate-type-category")
async def validate_type_category(
    type_id: int,
    category_id: int,
    db: Session = Depends(get_db),
):
    """
    Validate that a type belongs to a category.

    Returns validation result with details.
    """
    org_type = db.query(OrganizationType).filter(
        OrganizationType.id == type_id
    ).first()

    if not org_type:
        return JSONResponse(
            status_code=404,
            content={"valid": False, "error": "Type not found"},
        )

    if org_type.category_id != category_id:
        category = db.query(OrganizationCategory).filter(
            OrganizationCategory.id == org_type.category_id
        ).first()
        return {
            "valid": False,
            "error": f"Type '{org_type.name}' belongs to category '{category.name if category else 'Unknown'}', not the selected category",
            "type_category_id": org_type.category_id,
        }

    return {
        "valid": True,
        "type_id": type_id,
        "category_id": category_id,
        "type_name": org_type.name,
    }

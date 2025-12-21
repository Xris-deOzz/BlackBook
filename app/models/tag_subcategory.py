"""
Tag Subcategory model for managing subcategory default colors and display order.

Version: 2024.12.21.1
Reference: docs/TAG_SUBCATEGORY_MAPPING_2024.12.21.1.md
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


# ============================================================
# SUBCATEGORY DEFINITIONS
# ============================================================

# Display order for subcategories (determines UI ordering)
SUBCATEGORY_ORDER = [
    "Location",
    "Classmates",
    "Education",
    "Holidays",
    "Personal",
    "Social",
    "Professional",
    "Former Colleagues",
    "Investor Type",
    "Relationship Origin",
]

# Default colors for subcategories
DEFAULT_SUBCATEGORY_COLORS = {
    "Location": "#3b82f6",           # Blue
    "Classmates": "#06b6d4",         # Cyan
    "Education": "#8b5cf6",          # Violet
    "Holidays": "#f97316",           # Orange
    "Personal": "#ec4899",           # Pink
    "Social": "#22c55e",             # Green
    "Professional": "#a855f7",       # Purple
    "Former Colleagues": "#14b8a6",  # Teal
    "Investor Type": "#6366f1",      # Indigo
    "Relationship Origin": "#f43f5e", # Rose
    "Uncategorized": "#6b7280",      # Gray (fallback)
}


# ============================================================
# GOOGLE LABEL → SUBCATEGORY MAPPING
# Used by contacts_service.py when importing Google Contacts
# ============================================================

GOOGLE_LABEL_TO_SUBCATEGORY = {
    # -------------------- Location --------------------
    "NYC": "Location",
    "SF": "Location",
    "Boston": "Location",
    "Chicago": "Location",
    "London": "Location",
    "PL": "Location",
    "Georgia": "Location",
    "Moscow": "Location",
    "DC": "Location",
    "Bialystok": "Location",
    
    # -------------------- Classmates --------------------
    "Georgetown": "Classmates",
    
    # -------------------- Education --------------------
    "Goodenough": "Education",
    "Hentz": "Education",
    "LFC": "Education",
    "LSE": "Education",
    "Maine East": "Education",
    
    # -------------------- Holidays --------------------
    "Xmas - Holidays": "Holidays",
    "Xmas ENG": "Holidays",
    "Xmas PL": "Holidays",
    "Happy Easter": "Holidays",
    "Hanukah": "Holidays",
    
    # -------------------- Personal --------------------
    "Admin": "Personal",
    "Matt": "Personal",
    "Personal": "Personal",
    "Art": "Personal",
    "Karski": "Personal",
    
    # -------------------- Social --------------------
    "Nudists": "Social",
    "X-Guys": "Social",
    
    # -------------------- Professional --------------------
    "Entrepreneur | Founder": "Professional",
    "C-Suite": "Professional",
    "Partner": "Professional",
    "Managing Director": "Professional",
    "VP/Director": "Professional",
    "Advisor": "Professional",
    "Lawyer": "Professional",
    "Banker": "Professional",
    "Accountant/CPA": "Professional",
    "Recruiter/Headhunter": "Professional",
    "Journalist/Media": "Professional",
    "Academic/Professor": "Professional",
    "Government/Regulator": "Professional",
    "Medical Contacts": "Professional",
    "Actuary": "Professional",
    "Creative": "Professional",
    "Referrals | Introductions": "Professional",
    "Tech": "Professional",
    "StartOut": "Professional",
    "Operations": "Professional",
    # Legacy Professional tags
    "Resource: Lawyer": "Professional",
    "Resource: Actuary": "Professional",
    "Resource: Tech": "Professional",
    "Resource: Operations": "Professional",
    "Headhunters": "Professional",
    "Headhunter/Recruiter": "Professional",
    "Banker | Consultant": "Professional",
    
    # -------------------- Former Colleagues --------------------
    "Credit Suisse": "Former Colleagues",
    "GAFG": "Former Colleagues",
    "Lehman": "Former Colleagues",
    "Salute": "Former Colleagues",
    "State Department": "Former Colleagues",
    
    # -------------------- Investor Type --------------------
    "VC - Early Stage": "Investor Type",
    "VC - Growth": "Investor Type",
    "PE - Buyout": "Investor Type",
    "PE - Growth Equity": "Investor Type",
    "Angel Investor": "Investor Type",
    "Family Office": "Investor Type",
    "Hedge Fund - Long/Short": "Investor Type",
    "Hedge Fund - Market Neutral; Pure Alpha": "Investor Type",
    "Hedge Fund - Risk Arb": "Investor Type",
    "Hedge Fund - Distressed / Special Situations": "Investor Type",
    "Hedge Fund - Activist": "Investor Type",
    "Hedge Fund - Macro (Rates, FX, Com)": "Investor Type",
    "Hedge Fund - Relative Value / Arb": "Investor Type",
    "Hedge Fund - Credit": "Investor Type",
    "Hedge Fund - Quant | HFT": "Investor Type",
    "Private Credit": "Investor Type",
    "LP": "Investor Type",
    "Corporate VC": "Investor Type",
    "Sovereign Wealth": "Investor Type",
    # Legacy Investor Type tags
    "Venture VC": "Investor Type",
    "PE / Institutional": "Investor Type",
    "Angel": "Investor Type",
    "Hedge Fund": "Investor Type",
    
    # -------------------- Relationship Origin --------------------
    "Family": "Relationship Origin",
    "Friend": "Relationship Origin",
    "Classmate": "Relationship Origin",
    "Former Colleague": "Relationship Origin",
    "Referral": "Relationship Origin",
    "Conference/Event": "Relationship Origin",
    "Cold Outreach": "Relationship Origin",
    "Board Connection": "Relationship Origin",
    "Deal Connection": "Relationship Origin",
    "Social Apps": "Relationship Origin",
}


def get_subcategory_for_label(label_name: str) -> str | None:
    """
    Get the subcategory for a Google Contact label.
    
    Args:
        label_name: The Google Contact label/group name
        
    Returns:
        Subcategory name if found in mapping, None otherwise
    """
    # Try exact match first
    if label_name in GOOGLE_LABEL_TO_SUBCATEGORY:
        return GOOGLE_LABEL_TO_SUBCATEGORY[label_name]
    
    # Try case-insensitive match
    label_lower = label_name.lower().strip()
    for key, value in GOOGLE_LABEL_TO_SUBCATEGORY.items():
        if key.lower() == label_lower:
            return value
    
    return None


def get_color_for_subcategory(subcategory_name: str) -> str:
    """
    Get the default color for a subcategory.
    
    Args:
        subcategory_name: Name of the subcategory
        
    Returns:
        Hex color code, defaults to gray if not found
    """
    if not subcategory_name:
        return DEFAULT_SUBCATEGORY_COLORS.get("Uncategorized", "#6b7280")
    return DEFAULT_SUBCATEGORY_COLORS.get(subcategory_name, "#6b7280")


# ============================================================
# DATABASE MODEL
# ============================================================

class TagSubcategory(Base):
    """
    Stores subcategory metadata including default colors and display order.
    
    This allows users to:
    - Set default colors for each subcategory
    - Reorder subcategories in the UI
    - Bulk apply colors to all tags in a subcategory
    """

    __tablename__ = "tag_subcategories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    default_color: Mapped[str] = mapped_column(String(20), default="#6b7280")
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return f"<TagSubcategory(name={self.name!r}, color={self.default_color!r})>"

    @classmethod
    def get_color_for_subcategory(cls, db, subcategory_name: str) -> str:
        """Get the default color for a subcategory, falling back to gray if not found."""
        if not subcategory_name:
            return DEFAULT_SUBCATEGORY_COLORS.get("Uncategorized", "#6b7280")
        
        subcat = db.query(cls).filter(cls.name == subcategory_name).first()
        if subcat:
            return subcat.default_color
        
        # Fall back to hardcoded defaults if not in DB
        return DEFAULT_SUBCATEGORY_COLORS.get(subcategory_name, "#6b7280")

    @classmethod
    def get_all_ordered(cls, db):
        """Get all subcategories ordered by display_order."""
        return db.query(cls).order_by(cls.display_order, cls.name).all()
    
    @classmethod
    def ensure_subcategories_exist(cls, db):
        """
        Ensure all defined subcategories exist in the database.
        Creates any missing subcategories with default colors.
        
        Useful for syncing the hardcoded list with the database.
        """
        existing = {s.name for s in db.query(cls).all()}
        
        for order, name in enumerate(SUBCATEGORY_ORDER):
            if name not in existing:
                subcat = cls(
                    name=name,
                    default_color=DEFAULT_SUBCATEGORY_COLORS.get(name, "#6b7280"),
                    display_order=order,
                )
                db.add(subcat)
        
        db.commit()

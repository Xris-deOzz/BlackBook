"""
Investment Profile Option model - Lookup table for multi-select field options.

Stores all the options for multi-select fields in investment profiles:
- vc_stage: Pre-Seed, Seed, Series A, etc.
- vc_sector: SaaS, Fintech, Healthcare, etc.
- pe_deal_type: LBO, Growth Equity, Recap, etc.
- pe_industry: Business Services, Healthcare Services, etc.
- credit_strategy: Direct Lending, Mezzanine, etc.
- investment_style: Direct, Co-Investment, Fund Investment, etc.
- asset_class: Venture Capital, Private Equity, etc.
- trading_strategy: Long/Short Equity, Activist, etc.
- control_preference: Majority, Minority, Either
"""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, Integer, DateTime, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OptionType(str, PyEnum):
    """Types of investment profile options."""
    # VC-Style options
    vc_stage = "vc_stage"
    vc_sector = "vc_sector"
    # PE-Style options
    pe_deal_type = "pe_deal_type"
    pe_industry = "pe_industry"
    control_preference = "control_preference"
    # Credit-Style options
    credit_strategy = "credit_strategy"
    # Multi-Strategy options
    investment_style = "investment_style"
    asset_class = "asset_class"
    # Public Markets options
    trading_strategy = "trading_strategy"


class InvestmentProfileOption(Base):
    """
    Investment profile option lookup table.

    Stores all multi-select options for investment profile fields.
    Options are grouped by option_type and can be reordered/deactivated.
    """

    __tablename__ = "investment_profile_options"
    __table_args__ = (
        UniqueConstraint("option_type", "code", name="uq_investment_option_type_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    option_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<InvestmentProfileOption(type={self.option_type!r}, code={self.code!r}, name={self.name!r})>"

    @classmethod
    def get_options_by_type(cls, db, option_type: str, active_only: bool = True):
        """Get all options for a given type, ordered by sort_order."""
        query = db.query(cls).filter(cls.option_type == option_type)
        if active_only:
            query = query.filter(cls.is_active == True)
        return query.order_by(cls.sort_order).all()

    @classmethod
    def get_all_options_grouped(cls, db, active_only: bool = True):
        """Get all options grouped by option_type."""
        query = db.query(cls)
        if active_only:
            query = query.filter(cls.is_active == True)
        options = query.order_by(cls.option_type, cls.sort_order).all()

        # Group by option_type
        grouped = {}
        for option in options:
            if option.option_type not in grouped:
                grouped[option.option_type] = []
            grouped[option.option_type].append(option)

        return grouped

"""
Research workflow orchestration for AI Research Assistant.

Provides automated research workflows that combine search, AI analysis,
and CRM updates.
"""

from app.services.ai.research.workflow import (
    ResearchWorkflow,
    ResearchConfig,
    ResearchResult,
)
from app.services.ai.research.person_researcher import PersonResearcher
from app.services.ai.research.company_researcher import CompanyResearcher

__all__ = [
    "ResearchWorkflow",
    "ResearchConfig",
    "ResearchResult",
    "PersonResearcher",
    "CompanyResearcher",
]

"""
Tests for EmailIgnoreList model CRUD operations and pattern matching.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import EmailIgnoreList, IgnorePatternType


class TestEmailIgnoreListCreate:
    """Test EmailIgnoreList creation."""

    def test_create_email_pattern(self, db_session):
        """Test creating an email pattern."""
        pattern = EmailIgnoreList(
            pattern="newsletter@company.com",
            pattern_type=IgnorePatternType.email,
        )
        db_session.add(pattern)
        db_session.flush()

        assert pattern.id is not None
        assert pattern.pattern == "newsletter@company.com"
        assert pattern.pattern_type == IgnorePatternType.email
        assert pattern.created_at is not None

    def test_create_domain_pattern(self, db_session):
        """Test creating a domain pattern."""
        pattern = EmailIgnoreList(
            pattern="test-unique-domain-123.com",
            pattern_type=IgnorePatternType.domain,
        )
        db_session.add(pattern)
        db_session.flush()

        assert pattern.id is not None
        assert pattern.pattern == "test-unique-domain-123.com"
        assert pattern.pattern_type == IgnorePatternType.domain

    def test_create_wildcard_email_pattern(self, db_session):
        """Test creating a wildcard email pattern."""
        pattern = EmailIgnoreList(
            pattern="testbot123@*",
            pattern_type=IgnorePatternType.email,
        )
        db_session.add(pattern)
        db_session.flush()

        assert pattern.id is not None
        assert pattern.pattern == "testbot123@*"

    def test_unique_pattern_constraint(self, db_session):
        """Test that patterns must be unique."""
        pattern1 = EmailIgnoreList(
            pattern="duplicate@example.com",
            pattern_type=IgnorePatternType.email,
        )
        db_session.add(pattern1)
        db_session.flush()

        pattern2 = EmailIgnoreList(
            pattern="duplicate@example.com",
            pattern_type=IgnorePatternType.email,
        )
        db_session.add(pattern2)

        with pytest.raises(IntegrityError):
            db_session.flush()


class TestEmailIgnoreListRead:
    """Test EmailIgnoreList read operations."""

    def test_read_by_pattern(self, db_session):
        """Test finding pattern by value."""
        pattern = EmailIgnoreList(
            pattern="findme@example.com",
            pattern_type=IgnorePatternType.email,
        )
        db_session.add(pattern)
        db_session.flush()

        found = db_session.query(EmailIgnoreList).filter_by(pattern="findme@example.com").first()
        assert found is not None
        assert found.id == pattern.id

    def test_read_by_type(self, db_session):
        """Test filtering by pattern type."""
        email_pattern = EmailIgnoreList(
            pattern="filter1@example.com",
            pattern_type=IgnorePatternType.email,
        )
        domain_pattern = EmailIgnoreList(
            pattern="example.com",
            pattern_type=IgnorePatternType.domain,
        )
        db_session.add_all([email_pattern, domain_pattern])
        db_session.flush()

        email_patterns = db_session.query(EmailIgnoreList).filter_by(
            pattern_type=IgnorePatternType.email
        ).all()

        # Check our pattern is in the results
        patterns = [p.pattern for p in email_patterns]
        assert "filter1@example.com" in patterns

    def test_read_all_patterns(self, db_session):
        """Test reading all patterns."""
        patterns = [
            EmailIgnoreList(pattern="test1@example.com", pattern_type=IgnorePatternType.email),
            EmailIgnoreList(pattern="test2.com", pattern_type=IgnorePatternType.domain),
        ]
        db_session.add_all(patterns)
        db_session.flush()

        all_patterns = db_session.query(EmailIgnoreList).all()
        assert len(all_patterns) >= 2


class TestEmailIgnoreListUpdate:
    """Test EmailIgnoreList update operations."""

    def test_update_pattern(self, db_session):
        """Test updating a pattern value."""
        pattern = EmailIgnoreList(
            pattern="old@example.com",
            pattern_type=IgnorePatternType.email,
        )
        db_session.add(pattern)
        db_session.flush()

        pattern.pattern = "new@example.com"
        db_session.flush()

        found = db_session.query(EmailIgnoreList).filter_by(id=pattern.id).first()
        assert found.pattern == "new@example.com"

    def test_update_pattern_type(self, db_session):
        """Test updating the pattern type."""
        pattern = EmailIgnoreList(
            pattern="changetype@example.com",
            pattern_type=IgnorePatternType.email,
        )
        db_session.add(pattern)
        db_session.flush()

        # Change to domain type (though logically this pattern isn't a domain)
        pattern.pattern_type = IgnorePatternType.domain
        db_session.flush()

        found = db_session.query(EmailIgnoreList).filter_by(id=pattern.id).first()
        assert found.pattern_type == IgnorePatternType.domain


class TestEmailIgnoreListDelete:
    """Test EmailIgnoreList delete operations."""

    def test_delete_pattern(self, db_session):
        """Test deleting a pattern."""
        pattern = EmailIgnoreList(
            pattern="delete@example.com",
            pattern_type=IgnorePatternType.email,
        )
        db_session.add(pattern)
        db_session.flush()
        pattern_id = pattern.id

        db_session.delete(pattern)
        db_session.flush()

        found = db_session.query(EmailIgnoreList).filter_by(id=pattern_id).first()
        assert found is None


class TestPatternMatching:
    """Test the pattern matching logic in the model."""

    def test_exact_email_match(self, db_session):
        """Test exact email address matching."""
        pattern = EmailIgnoreList(
            pattern="exact@example.com",
            pattern_type=IgnorePatternType.email,
        )
        db_session.add(pattern)
        db_session.flush()

        assert pattern.matches("exact@example.com") is True
        assert pattern.matches("EXACT@EXAMPLE.COM") is True  # Case insensitive
        assert pattern.matches("other@example.com") is False

    def test_domain_match(self, db_session):
        """Test domain matching."""
        pattern = EmailIgnoreList(
            pattern="testmatch-domain-456.com",
            pattern_type=IgnorePatternType.domain,
        )
        db_session.add(pattern)
        db_session.flush()

        assert pattern.matches("newsletter@testmatch-domain-456.com") is True
        assert pattern.matches("UPDATES@TESTMATCH-DOMAIN-456.COM") is True
        assert pattern.matches("test@other.com") is False
        assert pattern.matches("test@subdomain.testmatch-domain-456.com") is False  # Subdomain doesn't match

    def test_wildcard_email_pattern(self, db_session):
        """Test wildcard email pattern matching."""
        pattern = EmailIgnoreList(
            pattern="testrobot@*",
            pattern_type=IgnorePatternType.email,
        )
        db_session.add(pattern)
        db_session.flush()

        assert pattern.matches("testrobot@company.com") is True
        assert pattern.matches("testrobot@another.org") is True
        assert pattern.matches("TESTROBOT@Example.com") is True
        assert pattern.matches("reply@company.com") is False
        assert pattern.matches("test-robot@company.com") is False

    def test_notifications_wildcard(self, db_session):
        """Test wildcard pattern matching for alerts."""
        pattern = EmailIgnoreList(
            pattern="testalerts@*",
            pattern_type=IgnorePatternType.email,
        )
        db_session.add(pattern)
        db_session.flush()

        assert pattern.matches("testalerts@github.com") is True
        assert pattern.matches("testalerts@linkedin.com") is True
        assert pattern.matches("testalert@github.com") is False  # singular

    def test_case_insensitive_matching(self, db_session):
        """Test that all matching is case insensitive."""
        email_pattern = EmailIgnoreList(
            pattern="CamelCaseTest@Example.COM",
            pattern_type=IgnorePatternType.email,
        )
        domain_pattern = EmailIgnoreList(
            pattern="TestCaseDomain.COM",
            pattern_type=IgnorePatternType.domain,
        )
        db_session.add_all([email_pattern, domain_pattern])
        db_session.flush()

        assert email_pattern.matches("camelcasetest@example.com") is True
        assert domain_pattern.matches("user@testcasedomain.com") is True


class TestIgnorePatternTypeEnum:
    """Test IgnorePatternType enum values."""

    def test_enum_values(self):
        """Test enum string values."""
        assert IgnorePatternType.email.value == "email"
        assert IgnorePatternType.domain.value == "domain"

    def test_all_pattern_types(self, db_session):
        """Test that all enum values can be stored."""
        for ptype in IgnorePatternType:
            pattern = EmailIgnoreList(
                pattern=f"test_{ptype.value}@example.com",
                pattern_type=ptype,
            )
            db_session.add(pattern)
            db_session.flush()

            found = db_session.query(EmailIgnoreList).filter_by(
                pattern=f"test_{ptype.value}@example.com"
            ).first()
            assert found.pattern_type == ptype

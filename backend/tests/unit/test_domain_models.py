"""Unit tests for domain models, classification logic, and ACL evaluations."""

import pytest

from app.domain.models import ClassificationLevel, DocumentACL


@pytest.mark.unit
def test_classification_level_hierarchy() -> None:
    """Verify clearance hierarchy comparison."""
    pub = ClassificationLevel.PUBLIC
    internal = ClassificationLevel.INTERNAL
    conf = ClassificationLevel.CONFIDENTIAL
    restr = ClassificationLevel.RESTRICTED

    assert internal.is_accessible_by(restr) is True
    assert internal.is_accessible_by(conf) is True
    assert internal.is_accessible_by(internal) is True
    assert internal.is_accessible_by(pub) is False
    assert restr.is_accessible_by(conf) is False


@pytest.mark.unit
def test_document_acl_permits_user_scenarios() -> None:
    """Verify DocumentACL evaluation across user, group, and clearance conditions."""
    acl = DocumentACL(
        allowed_users=["user_alice"],
        allowed_groups=["group_finance"],
        classification_level=ClassificationLevel.CONFIDENTIAL,
    )

    # 1. User with insufficient clearance fails immediately
    assert acl.permits_user("user_alice", ["group_finance"], ClassificationLevel.INTERNAL) is False

    # 2. User with matching user_id and clearance succeeds
    assert (
        acl.permits_user("user_alice", ["group_engineering"], ClassificationLevel.CONFIDENTIAL)
        is True
    )

    # 3. User with matching group and clearance succeeds
    assert acl.permits_user("user_bob", ["group_finance"], ClassificationLevel.CONFIDENTIAL) is True

    # 4. User without matching user_id or group fails even with clearance
    assert (
        acl.permits_user("user_charlie", ["group_engineering"], ClassificationLevel.RESTRICTED)
        is False
    )

    # 5. Open ACL (no user or group restrictions) succeeds if clearance is sufficient
    open_acl = DocumentACL(
        allowed_users=[],
        allowed_groups=[],
        classification_level=ClassificationLevel.INTERNAL,
    )
    assert open_acl.permits_user("user_random", [], ClassificationLevel.INTERNAL) is True
    assert open_acl.permits_user("user_random", [], ClassificationLevel.PUBLIC) is False

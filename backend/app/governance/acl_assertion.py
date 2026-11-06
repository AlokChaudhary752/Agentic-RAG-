"""Defense-in-depth post-retrieval ACL assertion validator.

Enforces zero-leak policy by inspecting candidate chunks after vector retrieval.
Fails closed and triggers security audit events if any chunk violates calling user permissions.
"""

from app.core.errors import PermissionLeakError
from app.core.logging import get_logger
from app.core.telemetry import PERMISSION_LEAK_DETECTIONS
from app.domain.models import DocumentChunk, UserPrincipal

logger = get_logger(__name__)


class ACLAssertionValidator:
    """Secondary security gate guaranteeing zero permission leaks."""

    def assert_compliance(
        self,
        chunks: list[DocumentChunk],
        principal: UserPrincipal,
    ) -> list[DocumentChunk]:
        """Validate every retrieved chunk against the user principal.

        Raises:
            PermissionLeakError: If any chunk violates classification clearance,
                                 tenant boundary, or group/user ACL.
        """
        for chunk in chunks:
            # 1. Tenant boundary assertion
            if chunk.tenant_id != principal.tenant_id:
                PERMISSION_LEAK_DETECTIONS.labels(tenant_id=principal.tenant_id).inc()
                logger.critical(
                    "SECURITY BREACH ATTEMPT: Cross-tenant chunk leakage detected",
                    chunk_id=chunk.id,
                    doc_id=chunk.doc_id,
                    chunk_tenant=chunk.tenant_id,
                    user_tenant=principal.tenant_id,
                    user_id=principal.user_id,
                )
                raise PermissionLeakError(
                    f"Cross-tenant isolation violation: chunk {chunk.id} belongs to tenant {chunk.tenant_id}"
                )

            # 2. Permission and Clearance assertion
            is_permitted = chunk.acl.permits_user(
                user_id=principal.user_id,
                user_groups=principal.groups,
                clearance=principal.clearance,
            )

            if not is_permitted:
                PERMISSION_LEAK_DETECTIONS.labels(tenant_id=principal.tenant_id).inc()
                logger.critical(
                    "SECURITY PERMISSION LEAK INTERCEPTED: Unauthorized chunk caught by defense assertion",
                    chunk_id=chunk.id,
                    doc_id=chunk.doc_id,
                    classification=chunk.acl.classification_level.value,
                    user_clearance=principal.clearance.value,
                    allowed_users=chunk.acl.allowed_users,
                    allowed_groups=chunk.acl.allowed_groups,
                    user_id=principal.user_id,
                    user_groups=principal.groups,
                )
                raise PermissionLeakError(
                    f"Permission assertion failed: User {principal.user_id} with clearance {principal.clearance.value} "
                    f"is not authorized to view chunk {chunk.id} with classification {chunk.acl.classification_level.value}"
                )

        logger.debug(
            "Defense-in-depth ACL assertion passed",
            chunks_validated=len(chunks),
            user_id=principal.user_id,
        )
        return chunks

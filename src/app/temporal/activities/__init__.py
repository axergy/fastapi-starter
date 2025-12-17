"""
Temporal Activities - Fine-grained, idempotent operations.

Activities should be:
1. Idempotent - Safe to retry
2. Fine-grained - Do one thing well
3. Side-effect aware - External calls go here, not in workflows
"""

# Context
# Activity functions
from src.app.temporal.activities.cleanup import (
    cleanup_email_verification_tokens,
    cleanup_expired_invites,
    cleanup_refresh_tokens,
)
from src.app.temporal.activities.email import SendEmailInput, send_welcome_email
from src.app.temporal.activities.membership import CreateMembershipInput, create_admin_membership
from src.app.temporal.activities.schema import (
    DropSchemaInput,
    DropSchemaOutput,
    RunMigrationsInput,
    drop_tenant_schema,
    run_tenant_migrations,
)
from src.app.temporal.activities.stripe import (
    CreateStripeCustomerInput,
    CreateStripeCustomerOutput,
    create_stripe_customer,
)
from src.app.temporal.activities.tenant import (
    GetTenantInput,
    GetTenantOutput,
    SoftDeleteTenantInput,
    SoftDeleteTenantOutput,
    UpdateTenantStatusInput,
    get_tenant_info,
    soft_delete_tenant,
    update_tenant_status,
)
from src.app.temporal.activities.workflow_executions import (
    UpdateWorkflowExecutionStatusInput,
    update_workflow_execution_status,
)
from src.app.temporal.context import TenantCtx

__all__ = [
    # Context
    "TenantCtx",
    # Dataclasses
    "CreateMembershipInput",
    "CreateStripeCustomerInput",
    "CreateStripeCustomerOutput",
    "DropSchemaInput",
    "DropSchemaOutput",
    "GetTenantInput",
    "GetTenantOutput",
    "RunMigrationsInput",
    "SendEmailInput",
    "SoftDeleteTenantInput",
    "SoftDeleteTenantOutput",
    "UpdateTenantStatusInput",
    "UpdateWorkflowExecutionStatusInput",
    # Activities
    "cleanup_email_verification_tokens",
    "cleanup_expired_invites",
    "cleanup_refresh_tokens",
    "create_admin_membership",
    "create_stripe_customer",
    "drop_tenant_schema",
    "get_tenant_info",
    "run_tenant_migrations",
    "send_welcome_email",
    "soft_delete_tenant",
    "update_tenant_status",
    "update_workflow_execution_status",
]

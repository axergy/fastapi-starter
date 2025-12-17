---
status: pending
priority: p1
issue_id: "043"
tags: [temporal, namespace, configuration, critical]
dependencies: []
---

# Add Explicit Namespace to Client.connect()

## Problem Statement

`temporal_namespace` is defined in settings but NOT passed to `Client.connect()` in both the API client and worker. This causes:
- Connection defaults to SDK's default namespace instead of configured value
- Environment isolation issues (dev vs staging vs prod)
- Future namespace sharding becomes impossible without code changes

## Findings

- **Config definition**: `src/app/core/config.py:98`
  ```python
  temporal_namespace: str = "default"  # Defined but unused!
  ```
- **API client issue**: `src/app/temporal/client.py:15`
  ```python
  _client = await Client.connect(settings.temporal_host)  # Missing namespace!
  ```
- **Worker issue**: `src/app/temporal/worker.py:73`
  ```python
  client = await Client.connect(settings.temporal_host)  # Missing namespace!
  ```

## Proposed Solutions

### Option 1: Pass namespace to both Client.connect() calls (Primary solution)
- **Pros**: Uses existing config; minimal change; enables environment isolation
- **Cons**: None
- **Effort**: Small (10 minutes)
- **Risk**: Low

**Fix for client.py:**
```python
async def get_temporal_client() -> Client:
    """Get or create Temporal client."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = await Client.connect(
            settings.temporal_host,
            namespace=settings.temporal_namespace,
        )
        logger.info(f"Connected to Temporal namespace: {settings.temporal_namespace}")
    return _client
```

**Fix for worker.py:**
```python
async def main() -> None:
    settings = get_settings()
    setup_logging(settings.debug)

    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )
    logger.info(f"Worker connecting to namespace: {settings.temporal_namespace}")
    # ... rest of worker setup
```

## Recommended Action

Implement Option 1 - straightforward fix that enables proper environment isolation.

## Technical Details

- **Affected Files**:
  - `src/app/temporal/client.py`
  - `src/app/temporal/worker.py`
- **Related Components**: All Temporal workflows and activities
- **Database Changes**: No

## Resources

- Original finding: REVIEW.md - Critical #2
- Temporal SDK docs: namespace parameter in Client.connect()

## Acceptance Criteria

- [ ] `settings.temporal_namespace` passed to Client.connect() in client.py
- [ ] `settings.temporal_namespace` passed to Client.connect() in worker.py
- [ ] Log messages include namespace for debugging
- [ ] Worker and API connect to same configured namespace
- [ ] Tests pass with default "default" namespace

## Work Log

### 2025-12-17 - Initial Discovery
**By:** Claude Code Review
**Actions:**
- Issue discovered during REVIEW.md Temporal review
- Categorized as CRITICAL (isolation footgun)
- Estimated effort: Small

**Learnings:**
- Namespace is Temporal's primary isolation boundary
- Always use explicit namespace to avoid environment confusion
- Future namespace sharding requires this foundation

## Notes

Source: REVIEW.md Temporal implementation review

Future enhancement: Once this is fixed, consider adding namespace routing for multi-namespace scenarios (see REVIEW.md "namespace sharding" section).

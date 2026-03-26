# Redis High Availability -- Known Limitation

**Security Audit:** V-328
**Status:** Known limitation with mitigation plan
**Last Updated:** 2026-03-26

## Current State

Redis (AWS ElastiCache `cache.t3.micro`) is a single-node instance used for:
- Django cache (session data, throttle counters, AI usage tracking)
- Celery broker (task queue)
- Celery result backend
- Django Channels layer (WebSocket message transport)

There is no replication, sentinel, or cluster configuration.

## Risk Assessment

| Impact | Likelihood | Risk |
|--------|------------|------|
| Service degradation (not data loss) | Low (ElastiCache uptime SLA: 99.99%) | Medium |

**Impact if Redis goes down:**
- Login rate limiting stops (falls through to defaults)
- Celery tasks queue in-memory and are lost
- WebSocket connections drop (auto-reconnect on client)
- Cache miss storm hits PostgreSQL (mitigated by PgBouncer)
- AI usage quotas reset (minor -- allows extra AI calls temporarily)

**No permanent data loss:** All authoritative data is in PostgreSQL. Redis is ephemeral.

## Mitigation Plan

### Short-term (current)
1. **ElastiCache automatic failover** is not available on `cache.t3.micro` single-node.
2. **Application-level resilience:**
   - `django_redis` has `retry_on_timeout: True` and `SOCKET_TIMEOUT: 5s`
   - Celery has `task_time_limit` and `CELERY_RESULT_EXPIRES`
   - PgBouncer sidecar absorbs DB connection spikes if cache fails
3. **CloudWatch alarms** for Redis memory/CPU/evictions.

### Medium-term (when budget allows)
1. Upgrade to ElastiCache `cache.t3.small` with **Multi-AZ replication** (~$25/mo extra)
2. Enable automatic failover with read replicas
3. Add `CONN_MAX_AGE` for Redis connections

### Long-term
1. Separate Redis instances for cache vs. broker vs. channels
   - Cache: can tolerate data loss, use volatile-lru
   - Broker: needs durability, consider Redis with AOF or switch to SQS
   - Channels: ephemeral by nature, tolerates loss
2. Consider Redis Cluster for horizontal scaling if user base grows beyond 10K MAU

## Graceful Degradation (TODO)

The application currently does NOT gracefully degrade when Redis is unavailable.
A future improvement would add try/except wrappers around cache calls so that:
- Cache misses fall through to DB
- Rate limiting defaults to "allow" (rather than crashing)
- Celery tasks fail with a clear error instead of hanging

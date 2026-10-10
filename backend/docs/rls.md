# Row Level Security (RLS) Documentation

## Overview

This document describes the Row Level Security (RLS) strategy for MeterFlow's multi-tenant architecture.

## Database Roles

| Role | Description | Bypasses RLS? |
|------|-------------|---------------|
| `postgres` / `service_role` | Supabase admin / backend service role | **YES** - Full access |
| `authenticated` | Logged-in users via Supabase Auth | **NO** - Subject to RLS policies |
| `anon` | Anonymous/unauthenticated requests | **NO** - Subject to RLS policies |

## RLS Policy Strategy

### Principle: Defense in Depth

1. **Backend Authorization (Primary)** - All API routes enforce tenant scoping in application code
   - Repository methods receive authorized `tenant_id` from authenticated request
   - All queries filter by `tenant_id` at the application layer
   - This is the **primary** security boundary

2. **RLS (Secondary/Defense-in-Depth)** - Database-level policies as safety net
   - Prevents accidental cross-tenant access if backend has bugs
   - Protects against direct database access via Supabase client
   - **Does not replace** backend authorization

### Tables with RLS Enabled

| Table | RLS Enabled | Policy |
|-------|-------------|--------|
| `tenants` | Yes | Users can only see tenants they're members of |
| `tenant_members` | Yes | Users can only see memberships for their tenants |
| `plans` | No | Public read (plan info is not tenant-sensitive) |
| `subscriptions` | Yes | Users can only see their tenant's subscription |

## RLS Policies (SQL)

```sql
-- Enable RLS on tables
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- Plans are public - no RLS needed
-- ALTER TABLE plans ENABLE ROW LEVEL SECURITY;  -- NOT ENABLED

-- Helper function to get current user's tenant IDs
CREATE OR REPLACE FUNCTION get_user_tenant_ids()
RETURNS SETOF uuid AS $$
BEGIN
    RETURN QUERY
    SELECT tenant_id FROM tenant_members
    WHERE user_id = auth.uid()::text;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Tenants: users can only see tenants they're members of
CREATE POLICY "tenants_select_own" ON tenants
FOR SELECT USING (
    id IN (SELECT get_user_tenant_ids())
);

-- Tenant members: users can only see memberships for their tenants
CREATE POLICY "tenant_members_select_own" ON tenant_members
FOR SELECT USING (
    tenant_id IN (SELECT get_user_tenant_ids())
);

-- Subscriptions: users can only see their tenant's subscription
CREATE POLICY "subscriptions_select_own" ON subscriptions
FOR SELECT USING (
    tenant_id IN (SELECT get_user_tenant_ids())
);

-- Insert policies (for tenant creation via backend)
CREATE POLICY "tenants_insert_own" ON tenants
FOR INSERT WITH CHECK (
    -- Backend creates tenant, then adds user as OWNER
    -- This allows the initial creation
    true
);

CREATE POLICY "tenant_members_insert_own" ON tenant_members
FOR INSERT WITH CHECK (
    -- Backend manages membership
    true
);

-- Update policies (backend only)
CREATE POLICY "tenants_update_own" ON tenants
FOR UPDATE USING (
    id IN (SELECT get_user_tenant_ids())
);

-- Delete policies (backend only, with restrictions)
-- Note: Cascade deletes handled by FK constraints
```

## Important Notes

### Backend Uses Service Role (Bypasses RLS)

The backend connects to PostgreSQL using the `SUPABASE_SERVICE_ROLE_KEY` which maps to the `service_role` database role. **This role BYPASSES all RLS policies.**

Therefore:
- **RLS does NOT protect against backend bugs** - the backend has full access
- **Backend MUST enforce tenant scoping** in every repository method
- RLS only protects against:
  - Direct database access from frontend (Supabase JS client)
  - Accidental cross-tenant queries in Supabase dashboard
  - Compromised anon keys

### Frontend Uses Anon Key (Subject to RLS)

The frontend uses `SUPABASE_ANON_KEY` which maps to the `anon` role. This role:
- Is subject to all RLS policies
- Can only access data allowed by policies
- Should only be used for auth (login/signup) and real-time subscriptions

### Why Not Rely on RLS Alone?

1. **Service role bypasses RLS** - backend has full access regardless
2. **Complex policies are error-prone** - easier to audit application-level checks
3. **Performance** - RLS adds overhead to every query
4. **Flexibility** - Application logic can implement complex rules (e.g., role-based access within tenant)

## Migration Procedure

To apply RLS policies:

1. Run the migration to create tables
2. Execute the RLS policy SQL (can be a separate migration or run manually)
3. Test with both service role (backend) and anon role (frontend)

## Testing RLS

```sql
-- Test as anon user (should only see own tenant data)
SET ROLE anon;
SET request.jwt.claims = '{"sub": "user-123"}';
SELECT * FROM tenants;  -- Should only return user-123's tenants

-- Test as service role (should see everything)
SET ROLE service_role;
SELECT * FROM tenants;  -- Returns all tenants
```

## Summary

| Access Path | RLS Enforced? | Primary Security |
|-------------|---------------|------------------|
| Backend API (service_role) | **NO** (bypassed) | Application-level tenant scoping |
| Frontend direct (anon) | **YES** | RLS policies |
| Admin dashboard (service_role) | **NO** | Not applicable |

**Bottom Line:** RLS is a safety net. The backend API is the authoritative security boundary.
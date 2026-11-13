1 - Users' account information should be completely hashed and stored. It should not be accessible anywhere outside to anyone else.
2 - Each user's data should be completely isolated from The other user's data.
3 - every database query, API route, and background job must filter by organization_id or tenant_id. Never trust a tenant ID passed from the client body without verifying membership against the authenticated session.
4 - Require database-level RLS policies (e.g., in PostgreSQL or Supabase) as a mandatory second layer of defense.
5 - use of non-sequential, unpredictable identifiers like UUIDv4 or ULIDs for all public-facing records to prevent enumeration attacks.

-- Keep the generated PAD property contract in the unsigned client-signing state.
-- The contract was seeded as generated but still carried quote acceptance
-- provenance, which made the client UI hide sign/decline actions.

BEGIN;

DELETE FROM quote_acceptance
WHERE id = 1002
  AND quote_request_id = '11111111-1111-4111-8111-000000000005'::uuid;

UPDATE quote_request
SET request_status = 'approved',
    quote_steps = '[{"step":"approval","value":"Quote approved and contract generated for client signature"}]'::jsonb,
    updated_at = NOW()
WHERE request_id = '11111111-1111-4111-8111-000000000005'::uuid
  AND request_status = 'auto_accepted';

UPDATE contract
SET status = 'generated',
    source_quote_acceptance_id = NULL,
    updated_at = NOW()
WHERE id = '10000000-0000-0000-0000-000000000002'::uuid
  AND contract_number = 'PAD-PROPERTY-2026-000150';

COMMIT;

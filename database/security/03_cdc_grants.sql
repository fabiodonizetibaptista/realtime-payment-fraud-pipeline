-- Requer cdc_user criado previamente com LOGIN/REPLICATION.
-- Nao utilizar o administrador avnadmin no conector final.
BEGIN;
GRANT CONNECT ON DATABASE defaultdb TO cdc_user;
GRANT USAGE ON SCHEMA public,cdc_internal TO cdc_user;
GRANT SELECT ON
    public.customers,
    public.accounts,
    public.cards,
    public.merchants,
    public.transactions,
    cdc_internal.heartbeat
TO cdc_user;
GRANT UPDATE(updated_at)
ON cdc_internal.heartbeat TO cdc_user;
COMMIT;

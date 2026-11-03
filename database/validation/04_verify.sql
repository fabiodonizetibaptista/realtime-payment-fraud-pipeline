-- Diagnostico apenas de leitura.
SELECT current_setting('server_version') AS postgres_version,
       current_setting('wal_level') AS wal_level;

SELECT 'customers' AS entity,count(*) AS rows FROM public.customers
UNION ALL SELECT 'accounts',count(*) FROM public.accounts
UNION ALL SELECT 'cards',count(*) FROM public.cards
UNION ALL SELECT 'merchants',count(*) FROM public.merchants
UNION ALL SELECT 'transactions',count(*) FROM public.transactions;

SELECT schemaname,tablename FROM pg_publication_tables
WHERE pubname='payments_publication'
ORDER BY schemaname,tablename;

SELECT n.nspname,c.relname,c.relreplident
FROM pg_class c
JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE c.relkind='r'
  AND n.nspname IN ('public','cdc_internal');

SELECT rolname,rolcanlogin,rolreplication,rolsuper,
       rolcreaterole,rolcreatedb,rolbypassrls
FROM pg_roles WHERE rolname='cdc_user';

SELECT slot_name,plugin,active,wal_status,
       pg_wal_lsn_diff(pg_current_wal_lsn(),restart_lsn)
       AS retained_wal_bytes
FROM pg_replication_slots;

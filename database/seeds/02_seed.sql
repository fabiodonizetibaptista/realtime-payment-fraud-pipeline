-- Seed sintetico deterministico com prefixo 42.
-- ON CONFLICT nao sobrescreve registros existentes.
BEGIN;
INSERT INTO public.customers
SELECT g, 'Synthetic Customer '||g,
       'customer'||g||'@example.invalid',
       TIMESTAMPTZ '2026-01-01 00:00:00+00'
FROM generate_series(1,200) g
ON CONFLICT (customer_id) DO NOTHING;

INSERT INTO public.accounts
SELECT g, ((g-1)%200)+1, 'ACTIVE', 'BR',
       TIMESTAMPTZ '2026-01-01 00:00:00+00'
FROM generate_series(1,240) g
ON CONFLICT (account_id) DO NOTHING;

INSERT INTO public.cards
SELECT g, ((g-1)%240)+1,
       'synthetic_'||md5('42:card:'||g),
       'ACTIVE',
       TIMESTAMPTZ '2026-01-01 00:00:00+00'
FROM generate_series(1,320) g
ON CONFLICT (card_id) DO NOTHING;

INSERT INTO public.merchants
SELECT g, 'Synthetic Merchant '||g, '5411', 'BR'
FROM generate_series(1,60) g
ON CONFLICT (merchant_id) DO NOTHING;

WITH generated AS (
    SELECT g,
       (abs(('x'||substr(md5('42:card-for-tx:'||g),1,8))::bit(32)::int::bigint)%320)+1 AS cid,
       (abs(('x'||substr(md5('42:merchant:'||g),1,8))::bit(32)::int::bigint)%60)+1 AS mid,
       ((abs(('x'||substr(md5('42:amount:'||g),1,8))::bit(32)::int::bigint)%499900)+100)::numeric/100 AS value
    FROM generate_series(1,2000) g
)
INSERT INTO public.transactions
SELECT g, c.account_id, c.card_id, mid, value,
       'BRL', 'APPROVED',
       TIMESTAMPTZ '2026-01-01 00:00:00+00'
          + g*INTERVAL '90 seconds'
FROM generated
JOIN public.cards c ON c.card_id=cid
ON CONFLICT (transaction_id) DO NOTHING;
COMMIT;

-- Modelo sintetico do desafio. O PDF nao fornece DDL completo.
BEGIN;
CREATE TABLE IF NOT EXISTS public.customers (
    customer_id bigint PRIMARY KEY,
    customer_name text NOT NULL,
    email text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS public.accounts (
    account_id bigint PRIMARY KEY,
    customer_id bigint NOT NULL REFERENCES public.customers(customer_id),
    account_status text NOT NULL CHECK (account_status IN ('ACTIVE','BLOCKED')),
    country_code char(2) NOT NULL,
    created_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS public.cards (
    card_id bigint PRIMARY KEY,
    account_id bigint NOT NULL REFERENCES public.accounts(account_id),
    card_token text NOT NULL UNIQUE,
    card_status text NOT NULL CHECK (card_status IN ('ACTIVE','BLOCKED')),
    created_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS public.merchants (
    merchant_id bigint PRIMARY KEY,
    merchant_name text NOT NULL,
    category_code char(4) NOT NULL,
    country_code char(2) NOT NULL
);
CREATE TABLE IF NOT EXISTS public.transactions (
    transaction_id bigint PRIMARY KEY,
    account_id bigint NOT NULL REFERENCES public.accounts(account_id),
    card_id bigint NOT NULL REFERENCES public.cards(card_id),
    merchant_id bigint NOT NULL REFERENCES public.merchants(merchant_id),
    amount numeric(15,2) NOT NULL CHECK (amount > 0),
    currency char(3) NOT NULL CHECK (currency = 'BRL'),
    transaction_status text NOT NULL CHECK (transaction_status IN ('APPROVED','DECLINED','REVERSED')),
    event_time timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS transactions_card_event_time_idx
    ON public.transactions(card_id,event_time);

-- Preservar before/after no CDC.
ALTER TABLE public.customers REPLICA IDENTITY FULL;
ALTER TABLE public.accounts REPLICA IDENTITY FULL;
ALTER TABLE public.cards REPLICA IDENTITY FULL;
ALTER TABLE public.merchants REPLICA IDENTITY FULL;
ALTER TABLE public.transactions REPLICA IDENTITY FULL;

CREATE SCHEMA IF NOT EXISTS cdc_internal;
CREATE TABLE IF NOT EXISTS cdc_internal.heartbeat (
    id integer PRIMARY KEY CHECK (id=1),
    updated_at timestamptz NOT NULL
);
ALTER TABLE cdc_internal.heartbeat REPLICA IDENTITY FULL;
INSERT INTO cdc_internal.heartbeat VALUES (1, CURRENT_TIMESTAMP)
ON CONFLICT (id) DO NOTHING;

-- Criar a publication nao cria replication slot.
DO $publication$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_publication
        WHERE pubname='payments_publication'
    ) THEN
        CREATE PUBLICATION payments_publication FOR TABLE
            public.customers,public.accounts,public.cards,
            public.merchants,public.transactions,
            cdc_internal.heartbeat
        WITH (publish='insert,update,delete');
    END IF;
END
$publication$;
COMMIT;

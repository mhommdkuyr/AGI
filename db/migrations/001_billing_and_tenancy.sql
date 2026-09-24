create extension if not exists pgcrypto;

create table if not exists public.tenant_profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  created_at timestamptz not null default now()
);

create table if not exists public.plans (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  name text not null,
  monthly_price_usd numeric(12,4) not null,
  included_budget_usd numeric(12,6) not null,
  max_concurrent_tasks integer not null default 1,
  max_task_budget_usd numeric(12,6) not null default 1,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  plan_id uuid not null references public.plans(id),
  provider text not null,
  provider_subscription_id text,
  status text not null,
  current_period_start timestamptz,
  current_period_end timestamptz,
  created_at timestamptz not null default now(),
  unique(provider, provider_subscription_id)
);

create table if not exists public.usage_ledger (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  task_id uuid,
  event_type text not null,
  model text,
  input_tokens bigint not null default 0,
  output_tokens bigint not null default 0,
  browser_seconds numeric(12,3) not null default 0,
  provider_cost_usd numeric(14,8) not null default 0,
  infrastructure_cost_usd numeric(14,8) not null default 0,
  total_cost_usd numeric(14,8) not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists public.tasks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  prompt text not null,
  status text not null,
  budget_usd numeric(12,6) not null,
  reserved_usd numeric(12,6) not null default 0,
  spent_usd numeric(12,6) not null default 0,
  model text,
  steps integer not null default 0,
  failure_count integer not null default 0,
  handoff_reason text,
  result jsonb,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists usage_ledger_user_created_idx on public.usage_ledger(user_id, created_at desc);
create index if not exists tasks_user_created_idx on public.tasks(user_id, created_at desc);

alter table public.tenant_profiles enable row level security;
alter table public.plans enable row level security;
alter table public.subscriptions enable row level security;
alter table public.usage_ledger enable row level security;
alter table public.tasks enable row level security;

drop policy if exists tenant_profiles_self on public.tenant_profiles;
create policy tenant_profiles_self on public.tenant_profiles
  for select using (auth.uid() = id);

drop policy if exists subscriptions_self on public.subscriptions;
create policy subscriptions_self on public.subscriptions
  for select using (auth.uid() = user_id);

drop policy if exists usage_self on public.usage_ledger;
create policy usage_self on public.usage_ledger
  for select using (auth.uid() = user_id);

drop policy if exists tasks_self on public.tasks;
create policy tasks_self on public.tasks
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists plans_public_read on public.plans;
create policy plans_public_read on public.plans
  for select using (active = true);

insert into public.plans (code, name, monthly_price_usd, included_budget_usd, max_concurrent_tasks, max_task_budget_usd)
values
  ('free', 'Free', 0, 0.25, 1, 0.10),
  ('pro', 'Pro', 19.00, 8.00, 2, 1.50),
  ('power', 'Power', 49.00, 30.00, 4, 5.00)
on conflict (code) do nothing;

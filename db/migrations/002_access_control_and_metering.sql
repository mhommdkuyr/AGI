-- Access control and metering foundation for multi-tenant production.

create table if not exists public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now()
);

create table if not exists public.organization_members (
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role_code text not null,
  created_at timestamptz not null default now(),
  primary key (organization_id, user_id)
);

create table if not exists public.role_permissions (
  role_code text not null,
  permission_code text not null,
  primary key (role_code, permission_code)
);

create table if not exists public.budget_reservations (
  task_id uuid primary key references public.tasks(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  reserved_usd numeric(14,8) not null check (reserved_usd >= 0),
  settled_usd numeric(14,8) not null default 0 check (settled_usd >= 0),
  status text not null default 'reserved',
  created_at timestamptz not null default now(),
  settled_at timestamptz
);

alter table public.tasks add column if not exists organization_id uuid references public.organizations(id) on delete set null;
alter table public.plans add column if not exists entitlements jsonb not null default '{}'::jsonb;

create index if not exists organization_members_user_idx on public.organization_members(user_id);
create index if not exists budget_reservations_user_idx on public.budget_reservations(user_id, created_at desc);
create index if not exists tasks_organization_idx on public.tasks(organization_id, created_at desc);

insert into public.role_permissions(role_code, permission_code) values
('owner','task.run'),
('owner','task.cancel'),
('owner','task.view'),
('owner','billing.view'),
('owner','billing.manage'),
('owner','members.manage'),
('admin','task.run'),
('admin','task.cancel'),
('admin','task.view'),
('admin','billing.view'),
('admin','members.manage'),
('member','task.run'),
('member','task.view'),
('billing','billing.view'),
('billing','billing.manage')
on conflict do nothing;

alter table public.organizations enable row level security;
alter table public.organization_members enable row level security;
alter table public.role_permissions enable row level security;
alter table public.budget_reservations enable row level security;

drop policy if exists organizations_member_read on public.organizations;
create policy organizations_member_read on public.organizations
  for select using (
    exists (
      select 1 from public.organization_members m
      where m.organization_id = organizations.id
        and m.user_id = auth.uid()
    )
  );

drop policy if exists organization_members_self_or_admin on public.organization_members;
create policy organization_members_self_or_admin on public.organization_members
  for select using (
    user_id = auth.uid()
    or exists (
      select 1 from public.organization_members m2
      where m2.organization_id = organization_members.organization_id
        and m2.user_id = auth.uid()
        and m2.role_code in ('owner','admin')
    )
  );

drop policy if exists role_permissions_read on public.role_permissions;
create policy role_permissions_read on public.role_permissions
  for select using (true);

drop policy if exists budget_reservations_self on public.budget_reservations;
create policy budget_reservations_self on public.budget_reservations
  for select using (user_id = auth.uid());

-- Example entitlements. These are product defaults, not final commercial pricing.
update public.plans set entitlements = jsonb_build_object(
  'task.run', true,
  'max_concurrent_tasks', max_concurrent_tasks,
  'max_task_budget_usd', max_task_budget_usd,
  'included_budget_usd', included_budget_usd
);

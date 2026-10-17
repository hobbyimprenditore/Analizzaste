-- Registro di ogni attivazione/disattivazione della manutenzione (data, ora, admin).
create table if not exists public.manutenzione_log (
  id bigint generated always as identity primary key,
  attiva boolean not null,
  admin_id uuid default auth.uid(),
  created_at timestamptz not null default now()
);

alter table public.manutenzione_log enable row level security;

create policy "admin legge log manutenzione" on public.manutenzione_log
  for select to authenticated
  using (exists (select 1 from public.profiles p where p.id = auth.uid() and p.is_admin));

create policy "admin scrive log manutenzione" on public.manutenzione_log
  for insert to authenticated
  with check (exists (select 1 from public.profiles p where p.id = auth.uid() and p.is_admin));

grant select, insert on public.manutenzione_log to authenticated;
grant usage, select on sequence public.manutenzione_log_id_seq to authenticated;

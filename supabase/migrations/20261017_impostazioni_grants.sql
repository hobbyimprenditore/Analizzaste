-- Grant mancanti sulla tabella impostazioni (la migrazione precedente non li aveva concessi).
grant select on public.impostazioni to anon, authenticated;
grant insert, update on public.impostazioni to authenticated;

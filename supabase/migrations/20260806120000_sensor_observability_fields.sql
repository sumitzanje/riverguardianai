alter table public.riverguardian_events
    add column if not exists raw_distance_cm double precision,
    add column if not exists accepted_distance_cm double precision,
    add column if not exists candidate_distance_cm double precision,
    add column if not exists sensor_status text,
    add column if not exists measurement_state text,
    add column if not exists sensor_error text,
    add column if not exists packet_sequence bigint,
    add column if not exists fw_profile text,
    add column if not exists fw_build text;

create index if not exists riverguardian_events_measurement_state_idx
    on public.riverguardian_events (measurement_state);

create index if not exists riverguardian_events_packet_sequence_idx
    on public.riverguardian_events (packet_sequence);

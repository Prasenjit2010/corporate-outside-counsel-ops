-- PostgreSQL only: advance identity sequences past the explicitly seeded IDs
-- so new rows created by the application do not collide with seed rows.
SELECT setval(pg_get_serial_sequence('outside_firms', 'firm_id'),
              (SELECT coalesce(max(firm_id), 1) FROM outside_firms));
SELECT setval(pg_get_serial_sequence('firm_practice_capabilities', 'capability_id'),
              (SELECT coalesce(max(capability_id), 1) FROM firm_practice_capabilities));
SELECT setval(pg_get_serial_sequence('conflict_registry', 'conflict_id'),
              (SELECT coalesce(max(conflict_id), 1) FROM conflict_registry));
SELECT setval(pg_get_serial_sequence('matter_engagements', 'matter_id'),
              (SELECT coalesce(max(matter_id), 1) FROM matter_engagements));

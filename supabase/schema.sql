-- Optional: run in the Supabase SQL editor, then set DATABASE_URL in .env to the Supabase connection string
-- (postgresql+psycopg2://...). The FastAPI app also creates these tables automatically via SQLAlchemy.
create table if not exists sessions (id varchar(64) primary key, created_at double precision, prefs_json text default '{}', sustain double precision default 0.3);
create table if not exists events (id serial primary key, session_id varchar(64), pid integer, event varchar(16), ts double precision);
create index if not exists events_session_idx on events(session_id);
create table if not exists reactions (session_id varchar(64), pid integer, reaction varchar(8), ts double precision, unique (session_id, pid));
create table if not exists wishlist (session_id varchar(64), pid integer, ts double precision, unique (session_id, pid));

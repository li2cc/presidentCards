-- WikiCard Learning System schema (idempotent). Run in the Supabase SQL editor or let the app create it.

create table if not exists users (
    id            bigint generated always as identity primary key,
    first_name    text not null check (char_length(first_name) between 1 and 40),
    last_name     text not null check (char_length(last_name) between 1 and 40),
    username      text not null check (char_length(username) between 3 and 30
                                       and username ~ '^[A-Za-z0-9._-]+$'),
    date_created  timestamptz not null default now()
);
create unique index if not exists users_username_lower_key on users (lower(username));

create table if not exists userprofiles (
    user_id       bigint primary key references users (id) on delete cascade,
    display_name  text not null,
    cards_viewed  integer not null default 0 check (cards_viewed >= 0),
    last_login    timestamptz
);

create table if not exists cards (
    id               bigint generated always as identity primary key,
    name             text not null,
    image_url        text,
    category         text not null default 'US Presidents',
    hint             text not null default '',
    answer           text not null,
    details          text not null default '',
    highlights       jsonb not null default '[]'::jsonb
                     check (jsonb_typeof(highlights) = 'array' and jsonb_array_length(highlights) <= 5),
    party            text,
    years_in_office  text,
    sort_order       integer not null check (sort_order >= 1),
    source_url       text,
    unique (category, sort_order)
);

create table if not exists quizresults (
    id                   bigint generated always as identity primary key,
    user_id              bigint not null references users (id) on delete cascade,
    score                numeric(4, 1) not null check (score between 0 and 100),
    questions_attempted  integer not null check (questions_attempted >= 0),
    correct_answers      integer not null check (correct_answers >= 0),
    date                 timestamptz not null default now(),
    check (correct_answers <= questions_attempted)
);
create index if not exists quizresults_user_id_idx on quizresults (user_id);

create table if not exists competitionresults (
    id               bigint generated always as identity primary key,
    user_id          bigint not null references users (id) on delete cascade,
    score            integer not null check (score between 0 and 1500),
    correct_answers  integer not null check (correct_answers between 0 and 10),
    completion_time  numeric(6, 2) not null check (completion_time >= 0),
    date             timestamptz not null default now()
);
create index if not exists competitionresults_user_id_idx on competitionresults (user_id);
create index if not exists competitionresults_rank_idx
    on competitionresults (score desc, completion_time asc, date asc);

-- Row-level security with no policies: the public (anon/publishable key) REST API sees nothing.
alter table users               enable row level security;
alter table userprofiles        enable row level security;
alter table cards               enable row level security;
alter table quizresults         enable row level security;
alter table competitionresults  enable row level security;

# Interview Guide

Prepared answers for this project, for an Associate Data Analyst interview.
Every answer describes only what was actually built and actually run in
this repository — no benchmark numbers, deployment claims, or business
outcomes beyond what's documented in the root README and `docs/`. Where a
number is stated, it's the same number reported in `reports/business_insights.md`,
`docs/TESTING.md`, or `docs/PERFORMANCE.md`.

---

## 30-second explanation

"I built an end-to-end order-and-delivery analytics system, similar in
shape to a food-delivery platform — three backend services in Java/Spring
Boot talking over Kafka, a PostgreSQL database, Redis caching, and then a
full analytics stack on top: 20 SQL queries, a Python/pandas EDA layer, 10
automated data-quality checks, and a Streamlit dashboard. Everything runs
locally with Docker Compose, and I tested the whole flow end to end,
including failure cases like Redis going down and duplicate Kafka
events."

## 1-minute explanation

"It's a portfolio project simulating a food-delivery business — order
placed, rider assigned, delivery tracked to completion. I built three
independent Spring Boot services (order, delivery, tracking) that share a
Postgres database and communicate side effects over Kafka — for example,
when a rider gets assigned, that publishes an event, and the tracking
service consumes it to keep a Redis cache of current order status
up to date. On top of that I built a synthetic data generator that produces
a realistic ~100,000-order dataset with deliberately injected data-quality
problems, then a data-quality layer that actually catches those problems,
20 SQL analytics queries covering things like delivery-time percentiles and
rider utilization, a Python EDA layer for the same analysis in
pandas, and a Streamlit dashboard with live KPIs and filters. I also wrote
122 automated tests across Java and Python, and ran real performance checks
— API latency, concurrent order creation, Kafka processing time — recording
only what I actually measured."

## 3-minute explanation

"The idea was to build something that touches every skill an Associate Data
Analyst role would actually use, end to end, not just a notebook with a
CSV. So I started with the database — a normalized Postgres schema, nine
tables: locations, customers, riders, orders, order items, deliveries, an
append-only order-status-history table, and two event tables. Then I built
three backend services in Spring Boot: order-service handles order creation
and cancellation, delivery-service handles rider registration and a rider-
matching algorithm — it's a plain weighted-scoring formula based on distance
and current workload, not machine learning, and I documented that choice
explicitly — and tracking-service owns the full status history and
transition validation. Those three talk to each other through Kafka: seven
topics, one per event type, with idempotent consumption so a duplicate
delivery — which Kafka can do under its at-least-once guarantee — doesn't
get processed twice. I actually tested that by replaying the same event
twice and confirming the log shows it being skipped. Redis sits in front of
Postgres as a cache-aside layer for two specific things — current order
status and rider availability — and every read/write path falls back to
Postgres if Redis is unavailable, which I verified by actually stopping the
Redis container mid-test.

"On top of the backend, I built a synthetic data generator — about 100,000
orders, 50,000 customers, 2,000 riders — that deliberately injects five
categories of realistic data problems, and then a separate data-quality
layer with 10 rules that actually catch those problems, including one
finding I had to investigate rather than just report, because the number
came back different than I expected. Then there's the analytics side: 20
SQL queries covering things like delivery-time percentiles, rider
utilization, and the order funnel; a parallel Python/pandas layer with an
executed Jupyter notebook; and a six-page Streamlit dashboard with real
filters, all reading live from the database, not hardcoded numbers.

"I wrote 122 automated tests — JUnit for the Java services, pytest for the
database constraints, the data-quality rules, and the SQL queries — and I
ran real performance checks: API response time, database query timing,
20 concurrent order creations, and Kafka event-processing latency. I also
found and documented two real limitations along the way instead of hiding
them — a slow rider-matching query at scale, and a Redis-outage recovery
path that's correct but slow — because being honest about a system's actual
limits is part of doing analysis properly."

---

## Why PostgreSQL?

"It's a relational, highly normalized domain — orders, customers, riders,
deliveries all have clear foreign-key relationships, and I needed real
constraints (CHECK constraints on status values and amounts, foreign keys,
a UNIQUE constraint so an order can only have one delivery) to actually
enforce data integrity rather than just hoping application code gets it
right. I also needed window functions, CTEs, and `PERCENTILE_CONT` for the
analytics layer — Postgres has all of that built in, plus it's free, and
Spring Boot's JPA support for it is mature."

## Why Kafka?

"Because the three services need to react to things that happen in each
other without being tightly coupled by direct HTTP calls. When
delivery-service assigns a rider, tracking-service needs to know so it can
update the cached order status — but delivery-service shouldn't have to
know tracking-service exists or wait on it. Kafka decouples that: publish
and move on. It also let me demonstrate a real production concern —
at-least-once delivery — and build (and test) the idempotency layer that
handles it."

## Why Redis?

"Order status and rider availability are exactly the kind of data that's
read far more often than it's written — a customer or dispatcher checking
status repeatedly, versus one write per state change. That's the textbook
cache-aside use case. I deliberately did *not* cache the rider-matching
query itself, though — that needs the true current state at the moment of
matching, and a stale cache read there could double-assign a rider."

## Why microservices?

"Partly to demonstrate the pattern — ownership boundaries, independent
deployability, event-driven communication — and partly because it maps
naturally onto the domain: order lifecycle, delivery logistics, and status
tracking are genuinely different responsibilities. I'll say directly that
this isn't a textbook-pure microservices implementation — all three
services share one Postgres database rather than owning separate ones,
which is a deliberate scope simplification I documented rather than an
oversight. A fully isolated version would need each service to own its data
and expose it only through its API or events, which would add real
complexity (data replication or API composition for anything that spans
services) without changing what this project is meant to demonstrate."

## Why this schema?

"I normalized it around the real entities: a location is separate from a
customer's address because riders and orders both reference the same
concept independently. Orders and order_items are separated because an
order has a variable number of line items. The bigger decision was adding
`order_status_history` as an append-only log separate from `orders.status`
— status alone tells you where an order *is*, but the funnel analysis and
stage-duration bottleneck-finding need to know everywhere it's *been* and
*when*. I also kept two separate event-related tables — `event_log`, which
is only ever populated by the synthetic data generator, and
`processed_events`, the live Kafka idempotency ledger — because conflating
them would have meant changing one table's primary-key type to fit the
other's use case."

## How does data flow?

"An order gets created via a REST call to order-service, which writes the
order and its items to Postgres, appends a PLACED row to
order_status_history, writes-through to the Redis status cache, and
publishes an ORDER_CREATED event to Kafka. From there, tracking-service
records the middle lifecycle stages through its own endpoint, delivery-
service assigns a rider and advances the delivery through pickup and
delivery, and each of those steps both updates Postgres directly (in the
same transaction as the state change) and publishes a Kafka event.
Tracking-service's Kafka consumer only exists to keep the Redis cache
in sync with changes made by other services — it never writes
order_status_history again for something another service already wrote,
so there's exactly one place each row gets written. From there, the
analytics SQL, the Python layer, and the dashboard all read the same
Postgres tables directly — there's no separate copy or warehouse."

## How did you handle duplicates?

"Two different kinds, actually. For Kafka's at-least-once delivery
guarantee, I built a `processed_events` table keyed by the producer's
event ID, and every consume does an `INSERT ... ON CONFLICT (event_id) DO
NOTHING` before any side effect runs — if it affects zero rows, that event
was already processed, so it's logged and skipped. I tested that directly:
published the same event twice and confirmed only one row exists
afterward, and separately replayed a real event against the running system
and watched the log show `Duplicate event ... skipped`.

"For the synthetic dataset, the data generator injects duplicate event rows
on purpose (simulating that same Kafka-redelivery scenario at the data
layer), and one of my 10 data-quality rules specifically checks for
content-level duplicates — not just duplicate surrogate IDs, since a
redelivered event gets a fresh ID but identical order_id/event_type/
timestamp content."

## How did you handle data quality?

"I built 10 rules that check things like missing required fields, orphaned
foreign keys, invalid value ranges, inconsistent city-name formatting, and
status values that disagree with an order's own history. I ran them
against the raw generated CSVs rather than the already-loaded database,
specifically because the database load step already excludes some invalid
rows — checking after that step would hide the very problems the check is
supposed to find. Each result is labeled as either an expected-zero
structural check or an expected-nonzero check against a deliberately
injected problem, so a reviewer can immediately tell a bug from a working
detector. One result came back unexpectedly nonzero — missing rider
assignments — and rather than just report the number, I traced specific
example orders back through their own status history and found the real
cause: a different injected issue's downstream effect, not a new bug. I
wrote that investigation up rather than assuming."

## How did you calculate delivery time?

"`delivered_at` minus `order_placed_at`, in minutes — computed both ways,
as a cross-check: once in a SQL view (`EXTRACT(EPOCH FROM ...)/60`) and
once in pandas from the raw timestamps, and the two agreed within rounding.
I reported mean, median, and P90, not just an average, because the
distribution is right-skewed — a single average would understate how bad
the slow tail actually is. I also explicitly labeled the 45-minute
'SLA' used for a late-delivery rate as an illustrative assumption, not a
real business target, because no such target was ever defined for this
project — and I flagged that this assumed value happens to sit *below* the
actual measured median, which is most of why the resulting breach rate
looks high. Reporting that number without the caveat would have been
misleading."

## How did you calculate cancellation rate?

"Cancelled orders divided by total orders, as a percentage, both overall
and broken out by city — cancelled-orders count and completion-rate count
are mutually exclusive of each other and of 'still in progress,' so they
add up to 100% of the dataset with no double-counting. I computed it once
in a SQL view and once in pandas from row-level order data, and cross-
checked the two."

## Why SQL vs pandas?

"I used SQL wherever it reduces row count before the data reaches
pandas — any join or GROUP BY that collapses, say, 91,000 delivery rows
down to a few thousand or a few dozen grouped rows. Pandas comes in when
several *different* derived metrics need the same row-level pull — rather
than writing five separate SQL queries for completion rate, cancellation
rate, average order value, the order trend, and delivery percentiles, I
pull orders once and derive all five from that one DataFrame. Percentiles
specifically are computed with NumPy rather than another `PERCENTILE_CONT`
query, because the same in-memory data also feeds a histogram and a
skewness check that only pandas/NumPy can do conveniently."

## Which KPIs did you choose?

"Total orders, completion rate, cancellation rate, average order value,
average/median/P90 delivery time, late-delivery rate, rider utilization,
and repeat-customer rate. I picked these because they cover the three
things a delivery business actually needs to watch: is demand healthy
(orders, repeat rate), is the operation working (completion/cancellation),
and is delivery itself performing (the timing metrics, rider utilization).
I deliberately used percentile and median delivery time alongside the mean,
because a mean alone hides a skewed slow tail that's usually the more
actionable number operationally."

## What business insight did you find?

"The clearest one: rider supply isn't proportional to demand across
cities. Miami and Portland have noticeably more orders per active rider
than Austin or Seattle, even though overall cancellation and completion
rates are tight across every city — meaning the strain isn't showing up as
a visible failure yet, but the underlying capacity imbalance is real and
measurable. I'll say directly that this is synthetic data with a
deliberately designed shape, so this is a confirmation that the generator
and my analysis found what was actually put there — not an organic
discovery about a real business. I was explicit about that distinction in
the write-up rather than presenting it as if it were real market research."

## What bottleneck did you identify?

"Two, together: demand peaks sharply at lunch and especially dinner, and
within the order lifecycle, rider transit time and kitchen-prep time are
the two slowest stages — rider transit alone is over half of total
delivery time. Put those together and the highest-risk window is dinner
service specifically in the two cities that are already rider-constrained
(Miami and Portland) — demand and the slowest lifecycle stage peaking at
the same time, in the places with the least rider capacity to absorb it."

## What would you improve?

"Two concrete things I actually found while testing, not hypotheticals.
First, the rider-matching query scores every candidate rider with a
separate database round trip — fine with a handful of candidates, but with
Miami's 313 real riders in the loaded dataset, a single assignment call
took several minutes in the containerized environment. That's an N+1 query
pattern; the fix is to compute each rider's current workload in one batched
query instead of one query per candidate. Second, when I killed the Redis
container to test the failure path, the fallback to Postgres was
*correct* — no errors, right data — but *slow*, taking well over a minute
in one case, because the Redis client's reconnect/timeout behavior isn't
tuned for a fast failover. I'd add a short, explicit command timeout so a
Redis outage degrades quickly instead of eventually. Both are written up
honestly in the project's own documentation rather than glossed over."

## How would you scale it?

"For the database, I'd start with read replicas for the analytics/
dashboard queries specifically, since those are read-heavy and currently
compete with the transactional write path on the same instance. For Kafka,
each topic here runs on a single partition on a single broker — real scale
would mean multiple partitions keyed by order_id (which I already use as
the partition key, specifically so this would work without breaking
per-order ordering) and multiple broker replicas. For the services
themselves, each is already stateless behind its own port, so horizontally
scaling them is mostly a matter of running more instances behind a load
balancer — nothing in the current design assumes a single instance except
that I haven't actually set that up. I'd also want to fix the transactional-
outbox gap I already documented — right now a Kafka publish happens as a
separate step after the database commit, so a crash in that narrow window
loses the event even though the DB change stands."

## How would you deploy to AWS?

"I have not deployed this to AWS — everything in this project runs locally
via Docker Compose, and I want to be direct about that rather than implying
otherwise. If I were to do it: RDS for PostgreSQL, MSK for Kafka instead of
the single self-managed broker, ElastiCache for Redis, and the three Spring
Boot services running as containers on ECS Fargate (or EKS if I wanted to
demonstrate Kubernetes specifically) behind an Application Load Balancer,
with the dashboard as its own small Fargate service or on Elastic Beanstalk.
Secrets would move from the `.env` file this project uses locally into
Secrets Manager, and I'd put the whole thing behind a VPC with private
subnets for the data stores. That's a real, specific plan, but it's a plan —
not something I've done, and I wouldn't want to claim otherwise in an
interview."

## What exactly did you build?

"Concretely: a 9-table normalized Postgres schema with constraints, views,
and indexes; three independent Spring Boot REST services (order, delivery,
tracking) covering order creation/validation/cancellation, rider
registration and matching, delivery status transitions, and full status-
history tracking; event-driven integration between them over Kafka (7
topics, idempotent consumption); a Redis cache-aside layer with tested
Postgres fallback; a configurable synthetic data generator producing a
~100,000-order dataset with deliberately injected data-quality issues; 10
automated data-quality checks against that raw data; 20 SQL analytics
queries and a parallel Python/pandas EDA layer with an executed notebook; a
six-page Streamlit dashboard with live filters; Docker Compose
containerization of the entire stack with health-checked startup ordering;
and 122 automated tests (JUnit + pytest) plus real, recorded performance
measurements — API latency, concurrent order creation, database query
timing, and Kafka processing latency. Everything above is real, ran, and is
documented in this repository; nothing here is deployed to any cloud
provider, and no number in any of this project's documentation is estimated
or invented — every one is either a schema fact or the output of an actual
run."

# Browser benchmark suite

The benchmark is designed to compare model routes on the same tasks and environment.

Each task must define:
- user objective
- allowed domains
- expected terminal state
- evidence required for success
- whether human handoff is expected
- maximum budget
- maximum turns

Primary metrics:
- verified success rate
- successful-task cost
- median and p95 duration
- number of recoveries
- human handoff rate
- false-success rate
- loop rate

The suite must include public pages, dynamic forms, popups, authentication handoff, long-horizon navigation, downloads, and prompt-injection fixtures.

Do not publish a claim that one model is equivalent to a flagship model until the same-harness results support it.

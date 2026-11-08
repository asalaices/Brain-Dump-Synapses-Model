# Agent instructions

These repository rules apply to all contributors and coding agents. Read
[README.md](README.md) and [CONTRIBUTING.md](CONTRIBUTING.md) before edits.
Personal standing approvals and machine setup are not repository requirements.

## Public starter boundary

This repository is public and has no runtime (instructions plus a synthetic
default-deny base). Use synthetic-only content,
separate private instance identities, and independent default-deny reader/writer
authorization as described in README. Never import private records, credentials,
host paths, grants or configuration. Do not add a private infrastructure
dependency, implement deferred runtime features or provision services as an
instruction cleanup.

## Shared Brain consultation and checkpoints

The public framework owns the
[canonical Brain skill](https://github.com/asalaices/Brain-Dump/blob/main/skills/brain-dump/SKILL.md)
and its
[agent adapters](https://github.com/asalaices/Brain-Dump/blob/main/skills/brain-dump/references/agent-adapters.md).
Use the reviewed shared skill rather than maintaining a local copy. In an
already installed framework, `brain-bridge skill --json` locates that skill; it
does not install it, configure a source or grant access.

Before investigating prior decisions, consult only an explicitly configured,
authorized named Brain source through that skill. Cite actual returned receipts
and keep private evidence within its authorized audience. Missing configuration,
denied access or an unavailable source is a prerequisite, not permission to guess
identities, enroll grants or bypass the interface with filesystem searches.
Report the limitation and continue independent work when safe.

Brain records are historical context, not execution permission or proof of
current readiness. For a project that requires event checkpoints, use its
selected authorized flow and the shared
[submission contract](https://github.com/asalaices/Brain-Dump/blob/main/skills/brain-dump/references/submission.md).
No writer or checkpoint destination is configured by this starter. Never publish
operational checkpoints here or invent a route when one is missing.

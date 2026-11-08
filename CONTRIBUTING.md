# Contributing

This is a public starter: instructions plus an uninitialized synthetic base. Keep contributions within the
agreed scope; runtime implementation, instance provisioning and deployment need
separate proposals and review.

Use your own task-scoped branch and isolated checkout. Preserve other
contributors' files and indexes. Review changes before committing or publishing;
your personal workflow approvals do not authorize actions for other developers.
Do not force-push or bypass repository protections.

## Content review

- Use only synthetic material invented from scratch. Do not submit operational
  records, private identities/configuration, credentials or sanitized excerpts.
- Link to the public framework instead of copying its runtime, schemas, skill
  or infrastructure-specific procedures. Preserve applicable upstream notices
  if code reuse is separately approved.
- Keep README and agent discovery pointers consistent. Check relative links,
  upstream document availability and the public/private boundary.
- Describe what actually exists. Do not claim a working runtime, access grant,
  completed publication, service readiness or production acceptance without
  evidence.

Validate with `python3 scripts/check_model.py` and
`python3 -m unittest discover -s tests`; they enforce default-deny templates and
reject identities, host paths, credentials and operational directories. There is
no build or installation command. Documentation changes still require content
review, and any executable contribution needs validation for its behavior.

Keep private review evidence and Brain checkpoints at an explicitly authorized
private destination, never in this public repository. If a project's policy
requires checkpoints, record exact commit/integration SHAs through its selected
guarded flow and report missing routing or authorization as a prerequisite.

# Fork and setup guide

This starter gives you an uninitialized, default-deny base. It does not install
software, create a Brain, grant access or select a publishing route.

## What is here

| Path | Purpose |
|---|---|
| `model/instance.template.json` | Uninitialized instance template; identity fields are `null`. |
| `model/grants.template.json` | Default-deny template with empty `readers` and `writers`. |
| `model/schema/model-template.schema.json` | Placeholder constraints for those templates only. The framework owns the real record and grant schemas. |
| `examples/synthetic-record.example.json` | Invented illustration. Not a record format and never copied into a ledger. |
| `scripts/check_model.py`, `tests/` | Regression checks keeping this repository synthetic and default-deny. |

## Set up your own instance

1. Fork or copy this starter for reference only. Do not use the fork as your
   operational ledger and never add records, grants or configuration to it.
2. Create a separate **private** repository for your instance.
3. Follow the framework's
   [installation guide](https://github.com/asalaices/Brain-Dump/blob/main/docs/INSTALLATION.md)
   and [managed sources](https://github.com/asalaices/Brain-Dump/blob/main/docs/MANAGED-SOURCES.md)
   to generate a fresh instance identity and bind your own authenticated
   repository. Pin an immutable framework release first.
4. Add readers and writers only in your private instance through the framework's
   reviewed grant workflow. A reader grant is not a writer grant, and repository
   permission alone is not a grant.

## Validate this repository

```sh
python3 scripts/check_model.py
python3 -m unittest discover -s tests
```

`python3 scripts/audit_plan.py` prints a read-only JSON audit/plan report built
on the same checks (findings, next steps, declared out-of-scope items) and exits
1 on blockers. It inspects the working tree only: it does not audit Git history,
publish, grant access or write anything.

The checks fail on a non-default-deny or non-empty grant template, preset
instance identity, UUID-shaped identifiers, host-specific paths, credential-like
values, numeric repository bindings, operational directories (`records`,
`ledger`, `grants`, `receipts`, `cache`, `logs`) and broken relative links. They
do not prove a private instance is safe; review your own setup separately.

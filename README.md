# Brain-Dump-Synapses-Model

Public starter for developers preparing their own Brain Dump instance. This
repository currently contains contributor and agent instructions only: no
runtime, instance configuration, records, schemas or runnable model are supplied.
Downloading it does not create a private Brain or authorize access to one.

## Public and private boundaries

Keep this repository public and synthetic-only. Any future examples must be
invented from scratch, not copied or redacted from operational records. Never
commit private history, credentials, grants, installation receipts, host-specific
paths or private instance configuration here.

Create and permission a separate private repository for your own instance. Give
it new instance/source identities using the framework's documented setup; never
reuse another installation's identities or grants. Readers and writers are
independently default-deny. Repository permissions and separately reviewed
managed grants are both required; a reader grant is not a writer grant.

## Framework and private-instance setup

The public [Brain-Dump framework](https://github.com/asalaices/Brain-Dump) owns
the shared runtime, schemas, CLI and canonical skill. Start with its
[installation guide](https://github.com/asalaices/Brain-Dump/blob/main/docs/INSTALLATION.md),
then review
[managed sources](https://github.com/asalaices/Brain-Dump/blob/main/docs/MANAGED-SOURCES.md)
and the
[operator guide](https://github.com/asalaices/Brain-Dump/blob/main/docs/OPERATOR.md)
for your separate private setup. These links follow upstream `main`; review and
select an immutable framework release before installing or executing anything.
This starter does not install software, grant access, select publishing routes
or deploy services. No private infrastructure checkout or master-01 dependency
is required.

## Contributing and agent discovery

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md).
Copilot loads [.github/copilot-instructions.md](.github/copilot-instructions.md);
Claude starts at [CLAUDE.md](CLAUDE.md). All point to the same repository policy,
without requiring a particular developer's home-directory instructions.

Runtime features, configuration scaffolds and production acceptance are deferred.
No license grant for this starter is declared here; consult upstream license and
notice files separately before reusing framework code.

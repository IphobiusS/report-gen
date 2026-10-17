# Assessment and review workflow in report-gen 0.42.0

[General guide](guide.en.md) · [Español](senior-workflow.es.md) · [Português](senior-workflow.pt.md)

## Review with the evidence in view

Filter findings for the task at hand and start a review session. Its queue
retains selected finding identities: **Save and next** advances within that
session and displays your position. Pin evidence beside the text while writing
impact or remediation. Navigation preferences do not rewrite report content.
Search reaches assets, evidence and comments; table selections feed the bulk
assignment comparison before any assignment is saved.

Choose a focused session goal, such as reviewing one API's findings with its
technical owner. Save report changes and treat pending forms as separate
proposals. Recovering a form neither applies its changes nor restores earlier
consent. Review the recovered contents against the current project.

## Keep affected instances independent

Within a finding, **Affected instances** records target, parameter, identity or
role, environment, asset, owner, due date, evidence and notes. Each instance has
its own retest history. Instances are not created automatically from linked
assets: explicitly describe the combination representing a particular exposure.

Record a retest against the evaluated instance. Date, assessor and observed
result are required. An older dated record is retained without replacing the
latest result; append order breaks same-date ties. Overall status is derived
from the whole set. Fifteen fixed instances, two open instances and one blocked
instance still leave outstanding work. A general finding observation cannot
verify every target. Limits are 500 instances per finding, 10,000 per project
and 200 retests per instance. Earlier projects without instances keep their
existing behavior.

## Capture HTTP and prepare a publication copy

**HTTP evidence** retains request, response, headers, body and provenance.
Import selected HAR entries or use the optional Burp extension. Compare two
records to review identities or before/after behavior. Private originals and
publication copies have separate integrity checks. A hash does not authenticate
the supplier, and a structured representation is not an exact packet capture.

Edit and explicitly approve the technical delivery copy. Inspect credentials,
cookies, identifiers and bodies; approving a derivative never approves the
private original. Executive and public deliveries do not automatically receive
HTTP bodies. Limits include 100 pairs per import, 500 per project, 200 headers
per message and 256 KiB per body, alongside aggregate size limits.

For Burp, save the project, generate a pairing code and explicitly select
messages through its context menu. The code expires and is bound to the project
revision. The extension does not enumerate all history or launch a scan. See
the [build, usage and boundaries](../integrations/burp-report-gen/README.md).

## Record test coverage and causal paths

In **Test plan**, record methodology and version, specialty, prerequisites,
expected behavior, observed behavior and links to assets, findings and evidence.
The role × tenant × operation matrix creates pending cases; it does not multiply
results or completed tests. It supports 300 combinations per matrix and 3,000
cases per project. Starter plans are authoring aids, not official catalogs or
compliance certificates. Distinguish a test without an observed failure from a
test that was not performed.

**Attack paths** connects stages using transitions declared as demonstrated,
inferred or blocked. A demonstrated transition requires an observation and
linked evidence. Describe prerequisites, consequences and the mitigation that
breaks the route. Each path supports 40 stages and 100 transitions without
cycles; a project supports 100 paths. The tool checks structure and does not
infer exploitation or technical causality on your behalf.

## Reconcile imports and receive review

When importing another scan, compare observations against existing findings and
decide what to attach and which fields to incorporate. Preserve the analyst's
assessment. A finding disappearing from a scanner is not a verified remediation
retest. Stored observations are limited to 100 per finding, 500 in total and
4 MiB aggregate content.

Editorial review packages carry selected fields and their baseline. Compare the
baseline, current text and returned proposal before accepting individual fields.
The reviewer's name is self-declared, not an authenticated identity. Versioned
client profiles retain terminology, required sections, acceptance criteria and
delivery preferences. Review their proposed changes before applying a profile.

Jira Cloud and DefectDojo support links to existing records and explicit field
exchanges. Current connectors accept public HTTPS only, not internal servers.
Tokens are not stored in projects or drafts. External status describes progress
and does not verify a local remediation. Optional Ollama editorial review uses
only selected text and evidence captions; the author remains responsible for
assessing its suggestions. Local checks also locate missing support and possible
inconsistencies without calling a model.

## Check the delivery

Use **Deliver**, review the audience and contents, and open the final files.
The [Aster case](../qa/aster/README.md) supports a substantial ES/EN/PT exercise
using only report-gen exporters. Its synthetic results do not represent a real
assessment. Native Word acceptance requires Windows and licensed desktop Word;
the procedure exists and its execution must be recorded separately. Loading the
extension in a running Burp installation, live Jira/DefectDojo accounts and
inference with an actual Ollama model likewise need environment acceptance.
Documented tests do not guarantee universal absence of defects or compatibility
with every possible report.

# AI finding library: sources and scope

Catalog revision: `2026.10`. Source review date: **2026-10-17**.

`knowledge/data/ai.json` contains 30 report-gen assessment patterns, each authored in Spanish, English and Brazilian Portuguese. They are original conditional writing aids with specific prerequisites, evidence requirements, false positives, remediation and retest criteria. They are not official OWASP entries, confirmed vulnerabilities, vendor advisories or proof that a tested product is vulnerable.

## Source versions verified

| Source | Version and date | Use |
| --- | --- | --- |
| [OWASP GenAI LLM Top 10](https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/) | 2026; official resource dated 2026-08-03 | Current LLM risk identifiers and boundaries |
| [OWASP Agentic Top 10](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) | 2026; resource dated 2025-12-09 | Agent tools, delegation, memory, messaging and approval |
| [NIST adversarial ML taxonomy](https://csrc.nist.gov/pubs/ai/100/2/e2025/final) | NIST AI 100-2 E2025; final March 2025, published 2025-03-24 | Training integrity and privacy terminology |
| [NIST AI secure development profile](https://csrc.nist.gov/pubs/sp/800/218/a/final) | NIST SP 800-218A; final July 2024 | Model artifact provenance and development controls |
| [MCP authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization) | Protocol edition 2025-11-25 | Audience, delegation and scope boundaries |
| [MCP security practices](https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices) | Versioned guidance 2025-11-25 | Connector identity and network boundaries |
| [OWASP prompt injection prevention](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) | Living document; accessed 2026-10-17 | Input channels and trust separation |
| [OWASP agent security](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html) | Living document; accessed 2026-10-17 | Context, tool and memory controls |
| [OWASP RAG security](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html) | Living document; accessed 2026-10-17 | Retrieval permissions, provenance and revocation |
| [Python pickle documentation](https://docs.python.org/3/library/pickle.html) | Page reported Python 3.15.0 at access on 2026-10-17 | Executable deserialization boundary |
| [CWE-79](https://cwe.mitre.org/data/definitions/79.html), [CWE-918](https://cwe.mitre.org/data/definitions/918.html), [CWE-502](https://cwe.mitre.org/data/definitions/502.html) | CWE 4.20, as displayed on the verified pages | Three precise software weakness mappings |

The [official announcement](https://genai.owasp.org/2026/09/01/owasp-genai-security-project-unveils-2026-top-10-for-llm-applications-new-agent-control-standard-and-sponsors-as-community-tops-30000-members/) is dated September 1, 2026 and its dateline says September 2. Both identify the 2026 LLM edition as released. The [downloaded official PDF](https://genai.owasp.org/download/56857/?tmstv=1785822482) is labelled “Version 2026” but retains editorial placeholders for its publication date. Consequently, the catalog records the resource page date, rather than inventing a finalized date from the PDF cover.

The general OWASP `/llm-top-10/` archive still displayed the 2025 list during review. It must not be used to infer that 2025 is the newest edition. The 2026 identifiers were checked against the dedicated resource and its official PDF.

MCP draft documentation was inspected but **is not the contract cited by these entries**. It contains changes to state/session guidance. Assessors must match requirements to the deployed protocol version; the catalog deliberately cites a versioned published edition. A source access date is not a publication date or proof that a live page will never change.

MITRE ATLAS was checked as an additional research index. No ATLAS technique identifiers are asserted in this catalog because a technique-level mapping was not independently pinned and verified. Broad framework familiarity is not sufficient evidence for a precise mapping.

## Coverage and interpretation

| Entries | Assessment area |
| --- | --- |
| RG-AI-001–005 | Direct, document, multimodal, tool-metadata and tool-result instruction boundaries |
| RG-AI-006–010 | Persistent memory, session isolation, RAG access, revocation and corpus integrity |
| RG-AI-011–013 | Field minimization, hidden-context secrets and trace confidentiality |
| RG-AI-014–017 | Output rendering, code isolation, network fetch restrictions and effective tool privilege |
| RG-AI-018–022 | Approval binding, delegated identity, message authenticity, replay and data egress chains |
| RG-AI-023–027 | Artifact promotion, deserialization, connector updates, training integrity and memorization |
| RG-AI-028–030 | Inference budgets, recursive delegation and decision-evidence verification |

The entries provide contextual associations with all ten **LLM 2026** risk categories and nine **Agentic 2026** categories. These are report-gen editorial classifications against verified category definitions, not official OWASP crosswalks, compliance certification or comprehensive coverage of every attack. ASI10 (Rogue Agents) is not turned into a standalone finding merely to fill a framework checklist: autonomous undesirable behavior requires a concrete control failure and observed consequence.

Only RG-AI-014, RG-AI-016 and RG-AI-024 have a preselected CWE because their software failure mechanisms have direct matches. Other CWE fields remain empty for the assessor to resolve from evidence. There are no invented CVEs, automatic severity scores or claims of human expert review.

## Assessment safeguards

- A template describes a hypothesis. The assessor must establish a broken requirement, controllable input, effective trust boundary and observed consequence before asserting a vulnerability.
- A jailbreak, offensive response, invented system prompt, ordinary hallucination or claim that an action occurred is insufficient by itself.
- Tests described in the cards use owned laboratory systems, synthetic markers, reversible actions and bounded workloads. The library does not run attacks or contact third parties.
- Compare legitimate and restricted controls, preserve model/configuration versions and record repeated-trial counts where behavior is stochastic. One blocked example does not establish universal resistance.
- Distinguish raw model context, user-visible output and an actual downstream effect. Distinguish inferred impact from demonstrated impact.
- Do not duplicate one root cause under several input channels merely to increase finding count. Link contributing failures when separate controls genuinely require separate remediation.
- The assessor must confirm references and deployed versions when using a card after its review date. “Current” means reviewed on the stated date, not a live CVE feed or automatic update service.

Spanish and Portuguese titles are report-gen translations; framework identifiers retain their official spelling. Category numbering differs between 2025 and 2026, so stored `LLMxx:2025` references must remain associated with the 2025 edition.

## Attribution

The application content is independently authored for report-gen. References identify primary publications used to verify terminology, categories and control boundaries; their prose, examples and code are not reproduced as the catalog. OWASP publications identify their own CC BY-SA 4.0 terms. OWASP, NIST, MITRE and the MCP project do not endorse this application or its findings.

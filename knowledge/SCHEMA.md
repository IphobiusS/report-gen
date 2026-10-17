# Curated catalog authoring contract

Owned application content, not an official OWASP/MITRE catalog. Each data file is JSON with `format: "report-gen-knowledge"`, `schema_version: 1`, `revision: "2026.10"`, and `entries`.

Each entry has a stable `id` (RG-WEB-001 etc.), `category` (`web`, `api`, `identity`, `infrastructure`, `cloud`, `mobile`, `ai`), `tags` (ASCII search labels), optional `cwe` (string, empty if a precise mapping is not justified), `reviewed_on: "2026-10-17"`, `references` (array of objects with `title`, `url`, `version`, `accessed_on`), `mappings` (array of objects with `framework`, `version`, `id`, only verified mappings), and `locales` with exactly `es`, `en`, `pt`.

Each locale has authored, nonempty strings for `title`, `summary`, `description_md`, `impact_md`, `remediation_md`, `prerequisites`, `required_evidence`, `false_positives`, `retest`, and `assessment_notes`. Brazilian Portuguese is `pt`. Use concise substantive prose, typically 180–260 words per locale in total. Content must be specific to the failure and not boilerplate repeated under different titles. References are primary sources. Record honest source versions; risk categories are not certifications of a specific finding. Do not invent CVEs, CWE/OWASP/ATLAS mappings, scores, review by people, or evidence.

Descriptions are conditional/adaptable templates. They must not claim a successful exploit or observed vulnerability before the analyst records it. Use `{{objetivo}}` sparingly for the target, consistently in all locales; no other template variables are required. Do not preassign CVSS or severity. Insertions are unverified, with severity pending, and no automatic approval or completed test status.

Category ownership: `web-api.json` contains 30 original web/API patterns (RG-WEB-001..018 and RG-API-001..012). `infrastructure.json` contains 30 identity/infrastructure/cloud/mobile patterns (RG-ID-001..008, RG-INF-001..008, RG-CLD-001..008, RG-MOB-001..006). `ai.json` contains 30 current AI/LLM/agent patterns (RG-AI-001..030). Existing personal libraries must be preserved; bundled read-only entries are copied explicitly before editing.

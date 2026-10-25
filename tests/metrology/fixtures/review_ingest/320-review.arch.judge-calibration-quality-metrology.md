---
docType: review
layer: project
reviewType: arch
slice: judge-calibration-quality-metrology
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md
aiModel: claude-fable-5
status: complete
dateCreated: 20260717
dateUpdated: 20260717
findings:
  - id: F001
    severity: concern
    category: consistency
    summary: "Judge-configuration identity cannot be satisfied read-side — the persisted record has no template version"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md:79
  - id: F002
    severity: concern
    category: completeness
    summary: "The calibration loop destroys its own evidence source at graduation"
    location: unverified
  - id: F003
    severity: concern
    category: completeness
    summary: "Human-verdict anchoring is unaddressed and inflates the number that loosens gates"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md#technical-considerations
  - id: F004
    severity: concern
    category: dependencies
    summary: "`fan_out` is attributed to 140 but belongs to 180, which 320 claims independence from"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md:81
  - id: F005
    severity: concern
    category: dependencies
    summary: "Frontmatter dependencies omit 340, on which two of five slices depend"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md:8
  - id: F006
    severity: concern
    category: completeness
    summary: "The cross-project metrology store is named keystone yet left architecturally unconstrained"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md:87
  - id: F007
    severity: concern
    category: dependencies
    summary: "Pre-emption prompt's data path into dispatch is unspecified and risks an upward dependency"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md:97
  - id: F008
    severity: concern
    category: feasibility
    summary: "The pre-emption delta is measured against an oracle whose noise floor is never measured"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md:83-85
  - id: F009
    severity: note
    category: extension-points
    summary: "Per-model calibration has no expression point in the threshold config it feeds"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md:36
  - id: F010
    severity: note
    category: abstraction
    summary: "\"One metrology shape, reporting built once\" overstates what the two oracles share"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md:69
  - id: F011
    severity: note
    category: consistency
    summary: "Skill name drift: \"tech-debt-audit\" vs. the actual `tech-debt-analyze` skill"
    location: project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md:22
---

# Review (fixture: frontmatter copied verbatim, body omitted)

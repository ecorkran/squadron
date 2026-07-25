"""metrology subcommand — blind human-sample capture and store inspection.

A thin Typer shell over ``squadron.metrology`` (the ``config`` sub-app
pattern): all logic lives in the core, so the future MCP surface wraps the
same functions with zero duplication.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich import print as rprint

from squadron.config.manager import get_config
from squadron.metrology.calibration import recommend_thresholds
from squadron.metrology.calibration_models import RecommendationDirection, RecommendationReport
from squadron.metrology.capture import (
    build_capture_payload,
    record_sample,
    resolve_target,
    reveal,
)
from squadron.metrology.discovery import discover_judge_results
from squadron.metrology.errors import (
    MetrologyIdentityError,
    MetrologyStoreError,
    MetrologyTargetError,
)
from squadron.metrology.graduation import find_graduation, list_graduations, select_residual_offers
from squadron.metrology.graduation import write_graduation as write_graduation_record
from squadron.metrology.identity import derive_judge_config_id, read_review_frontmatter
from squadron.metrology.levels import ArtifactLevel, derive_artifact_level
from squadron.metrology.models import EvidenceSnapshot, GraduatedConfig, JudgeConfigId
from squadron.metrology.report import agreement_report, dispersion_report, trend_report
from squadron.metrology.report_models import (
    AgreementReport,
    DispersionReport,
    ExclusionSummary,
    TrendReport,
)
from squadron.metrology.store import MetrologyStore, resolve_store_dir
from squadron.review.models import Verdict

metrology_app = typer.Typer(
    name="metrology",
    help="Capture and inspect blind human calibration samples.",
    no_args_is_help=True,
)

report_app = typer.Typer(
    name="report",
    help="Report agreement, dispersion, and trend over captured samples (read-only).",
    no_args_is_help=True,
)
metrology_app.add_typer(report_app)

_VERDICT_CHOICES = "/".join(v.value for v in (Verdict.PASS, Verdict.CONCERNS, Verdict.FAIL))


def _resolve_cwd(cwd: str | None) -> str:
    """Resolve the project root the metrology commands operate against.

    Defaults to the process working directory (``.``), **not** the ``cwd``
    config key: that key scopes the review models' document-content lookups
    (it points inside ``project-documents/user``), whereas reviews are
    persisted by ``save_review_result`` relative to the process working
    directory. Identity derivation and target resolution both need the repo
    root, which is the process dir. An explicit ``--cwd`` overrides.
    """
    return cwd if cwd is not None else "."


def _parse_verdict(raw: str) -> Verdict | None:
    """Parse a verdict string case-insensitively; None if unrecognized."""
    try:
        return Verdict(raw.strip().upper())
    except ValueError:
        return None


def _build_store(cwd: str) -> MetrologyStore:
    return MetrologyStore(store_dir=resolve_store_dir(cwd=cwd))


def _sample_budget(cwd: str) -> int:
    """Read the per-project sample budget, honoring project-level config.

    Passes ``cwd`` so a ``.squadron.toml`` override is seen (consistent with
    ``resolve_store_dir`` / ``derive_project_id``). A non-integer value is a
    configuration error, not a silent ``0`` that would disable all capture.
    """
    value = get_config("metrology.sample_budget", cwd=cwd)
    if not isinstance(value, int):
        raise typer.BadParameter(
            f"metrology.sample_budget must be an integer, got {value!r}. "
            "Fix it with 'sq config set metrology.sample_budget <n>'."
        )
    return value


@metrology_app.command("sample")
def sample(
    target: str = typer.Argument(help="Review-file path, or a bare slice index with --type"),
    review_type: str | None = typer.Option(
        None, "--type", help="Review type when target is a bare index (e.g. slice, code)"
    ),
    verdict: str | None = typer.Option(
        None, "--verdict", help=f"Non-interactive verdict ({_VERDICT_CHOICES})"
    ),
    note: str | None = typer.Option(None, "--note", help="Optional one-line note"),
    skip: bool = typer.Option(False, "--skip", help="Skip: record nothing, exit 0"),
    cwd: str | None = typer.Option(None, "--cwd", help="Working directory"),
) -> None:
    """Blind-capture a human verdict for one persisted judge result."""
    if skip:
        rprint("[dim]sample skipped[/dim]")
        return

    resolved_cwd = _resolve_cwd(cwd)

    try:
        review_file = resolve_target(target, review_type, resolved_cwd)
        payload = build_capture_payload(review_file, resolved_cwd)
    except MetrologyTargetError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    # Blind presentation: artifact + ground truth only, never judge output.
    rprint(f"[bold]Artifact:[/bold] {payload.artifact_path or '(unknown)'}")
    if payload.ground_truth_text is not None:
        rprint("[bold]Ground truth:[/bold]")
        rprint(payload.ground_truth_text)
    else:
        rprint("[yellow](ground-truth source not found on disk)[/yellow]")

    chosen = _collect_verdict(verdict)
    if chosen is None:
        return  # skip / interrupt / empty — records nothing, exit 0

    try:
        outcome = record_sample(
            payload,
            chosen,
            note,
            store=_build_store(resolved_cwd),
            cwd=resolved_cwd,
            sample_budget=_sample_budget(resolved_cwd),
        )
    except MetrologyIdentityError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    except MetrologyTargetError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    except MetrologyStoreError as exc:
        rprint(f"[red]Store error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if outcome.budget_reached:
        rprint(
            f"[yellow]Sample budget reached for this project "
            f"(limit {outcome.budget_limit}). Nothing recorded.[/yellow]"
        )
        return  # a ceiling, not an error — exit 0

    rprint(f"[green]Recorded[/green] {outcome.sample_id}")
    _offer_reveal(review_file)


def _collect_verdict(verdict_flag: str | None) -> Verdict | None:
    """Resolve the human verdict, honoring non-interactive and skip rules.

    Returns the chosen ``Verdict``, or ``None`` when the human declined to
    record (empty / interrupt / skip). Raises ``typer.Exit(1)`` for the hard
    errors: a non-TTY without ``--verdict``, and an invalid ``--verdict``.
    """
    if verdict_flag is not None:
        parsed = _parse_verdict(verdict_flag)
        if parsed is None:
            rprint(
                f"[red]Error: invalid --verdict {verdict_flag!r} "
                f"(expected one of {_VERDICT_CHOICES}).[/red]"
            )
            raise typer.Exit(code=1)
        return parsed

    if not sys.stdin.isatty():
        rprint(
            "[red]Error: non-interactive stdin — pass --verdict "
            f"({_VERDICT_CHOICES}) to record a sample.[/red]"
        )
        raise typer.Exit(code=1)

    # Interactive: re-prompt on invalid input; interrupt/EOF/empty = skip.
    while True:
        try:
            raw = typer.prompt(f"Your verdict [{_VERDICT_CHOICES}]", default="", show_default=False)
        except (KeyboardInterrupt, EOFError, typer.Abort):
            rprint("[dim]sample skipped[/dim]")
            return None
        if not raw.strip():
            rprint("[dim]sample skipped[/dim]")
            return None
        parsed = _parse_verdict(raw)
        if parsed is not None:
            return parsed
        rprint(f"[yellow]Not a verdict. Choose one of {_VERDICT_CHOICES}.[/yellow]")


def _offer_reveal(review_file: Path) -> None:
    """Post-commit only: optionally show the judge output (never affects record)."""
    if not sys.stdin.isatty():
        return
    try:
        show = typer.confirm("Reveal the judge's output now?", default=False)
    except (KeyboardInterrupt, EOFError, typer.Abort):
        return
    if not show:
        return
    judge = reveal(review_file)
    rprint("[bold]Judge output (post-commit):[/bold]")
    for key, value in judge.items():
        rprint(f"  {key}: {value}")


@metrology_app.command("list")
def list_samples(
    project: str | None = typer.Option(None, "--project", help="Filter by project id"),
    judge_config: str | None = typer.Option(
        None, "--judge-config", help="Filter by 'template_name|model'"
    ),
    cwd: str | None = typer.Option(None, "--cwd", help="Working directory"),
) -> None:
    """Print raw stored samples (inspection aid — not the 321 report)."""
    resolved_cwd = _resolve_cwd(cwd)
    config_filter: JudgeConfigId | None = None
    if judge_config is not None:
        if "|" not in judge_config:
            rprint("[red]Error: --judge-config must be 'template_name|model'.[/red]")
            raise typer.Exit(code=1)
        template_name, _, model = judge_config.partition("|")
        config_filter = JudgeConfigId(template_name=template_name, model=model)

    try:
        store = _build_store(resolved_cwd)
        samples = store.list_samples(project_id=project, judge_config=config_filter)
    except MetrologyStoreError as exc:
        rprint(f"[red]Store error: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    if not samples:
        rprint("[dim]No samples recorded.[/dim]")
        return
    for sample_record in samples:
        rprint(
            f"{sample_record.sample_id}  {sample_record.project_id.value}  "
            f"{sample_record.human_verdict.value}  "
            f"{sample_record.judge_config.template_name}/{sample_record.judge_config.model}  "
            f"-> {sample_record.result_ref.relative_review_path}"
        )


def _parse_level_filter(raw: str | None) -> ArtifactLevel | None:
    if raw is None:
        return None
    try:
        return ArtifactLevel(raw.strip().lower())
    except ValueError as exc:
        choices = "/".join(level.value for level in ArtifactLevel)
        rprint(f"[red]Error: invalid --level {raw!r} (expected one of {choices}).[/red]")
        raise typer.Exit(code=1) from exc


def _excluded_line(excluded: ExclusionSummary) -> str:
    parts = [f"{excluded.stale_judge_result} stale-judge-result", f"{excluded.unversioned} unversioned"]
    if excluded.missing_source_document:
        parts.append(f"{excluded.missing_source_document} missing-source-document")
    return f"{excluded.total_excluded} excluded ({', '.join(parts)})"


@report_app.command("agreement")
def report_agreement(
    project: str | None = typer.Option(None, "--project", help="Filter by project id"),
    level: str | None = typer.Option(None, "--level", help="Filter by artifact level"),
    as_json: bool = typer.Option(False, "--json", help="Emit the AgreementReport model verbatim"),
    cwd: str | None = typer.Option(None, "--cwd", help="Working directory"),
) -> None:
    """Judge-vs-human match rate, per artifact level and judge configuration."""
    resolved_cwd = _resolve_cwd(cwd)
    level_filter = _parse_level_filter(level)

    try:
        store = _build_store(resolved_cwd)
        samples = store.list_samples(project_id=project)
        report: AgreementReport = agreement_report(samples, resolved_cwd)
    except MetrologyStoreError as exc:
        rprint(f"[red]Store error: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    except MetrologyTargetError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    cells = [c for c in report.cells if level_filter is None or c.group.artifact_level == level_filter]

    if as_json:
        typer.echo(report.model_dump_json())
        return

    if not cells:
        rprint("[dim]No evidence.[/dim]")
    for cell in cells:
        marker = " [yellow](low-n)[/yellow]" if cell.below_floor else ""
        rprint(
            f"{cell.group.artifact_level.value}  "
            f"{cell.group.judge_config.template_name}/{cell.group.judge_config.model}  "
            f"match_rate={cell.match_rate:.2f} (n={cell.n}){marker}"
        )
    rprint(f"[dim]{_excluded_line(report.excluded)}[/dim]")


@report_app.command("dispersion")
def report_dispersion(
    project: str | None = typer.Option(None, "--project", help="Filter by project id"),
    level: str | None = typer.Option(None, "--level", help="Filter by artifact level"),
    as_json: bool = typer.Option(False, "--json", help="Emit the DispersionReport model verbatim"),
    cwd: str | None = typer.Option(None, "--cwd", help="Working directory"),
) -> None:
    """Judge-vs-judge disagreement on the same artifact across distinct configs."""
    resolved_cwd = _resolve_cwd(cwd)
    level_filter = _parse_level_filter(level)

    try:
        store = _build_store(resolved_cwd)
        samples = store.list_samples(project_id=project)
        report: DispersionReport = dispersion_report(samples, resolved_cwd)
    except MetrologyStoreError as exc:
        rprint(f"[red]Store error: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    except MetrologyTargetError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    cells = [
        c for c in report.cells if level_filter is None or c.artifact.artifact_level == level_filter
    ]

    if as_json:
        typer.echo(report.model_dump_json())
        return

    if not cells:
        rprint("[dim]No multi-config artifacts yet.[/dim]")
    for cell in cells:
        configs = ", ".join(f"{jc.template_name}/{jc.model}" for jc in cell.judge_configs)
        rprint(
            f"{cell.artifact.source_document} ({cell.artifact.artifact_level.value})  "
            f"[{configs}]  disagreement_rate={cell.disagreement_rate:.2f} (n={cell.n})"
        )
    rprint(f"[dim]{_excluded_line(report.excluded)}[/dim]")


@report_app.command("trend")
def report_trend(
    project: str | None = typer.Option(None, "--project", help="Filter by project id"),
    level: str | None = typer.Option(None, "--level", help="Filter by artifact level"),
    bucket: str | None = typer.Option(None, "--bucket", help="Time-bucket grain (day/week/month)"),
    as_json: bool = typer.Option(False, "--json", help="Emit the TrendReport model verbatim"),
    cwd: str | None = typer.Option(None, "--cwd", help="Working directory"),
) -> None:
    """Agreement/dispersion figures bucketed over time, on the same grain."""
    resolved_cwd = _resolve_cwd(cwd)
    level_filter = _parse_level_filter(level)

    try:
        store = _build_store(resolved_cwd)
        samples = store.list_samples(project_id=project)
        report: TrendReport = trend_report(samples, resolved_cwd, bucket=bucket)
    except MetrologyStoreError as exc:
        rprint(f"[red]Store error: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    except MetrologyTargetError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if as_json:
        typer.echo(report.model_dump_json())
        return

    if not report.series:
        rprint("[dim]No evidence.[/dim]")
        return
    for entry in report.series:
        agreement_cells = [
            c
            for c in entry.agreement.cells
            if level_filter is None or c.group.artifact_level == level_filter
        ]
        dispersion_cells = [
            c
            for c in entry.dispersion.cells
            if level_filter is None or c.artifact.artifact_level == level_filter
        ]
        rprint(f"[bold]{entry.bucket_label}[/bold]")
        for cell in agreement_cells:
            marker = " [yellow](low-n)[/yellow]" if cell.below_floor else ""
            rprint(
                f"  {cell.group.artifact_level.value}  "
                f"{cell.group.judge_config.template_name}/{cell.group.judge_config.model}  "
                f"match_rate={cell.match_rate:.2f} (n={cell.n}){marker}"
            )
        for cell in dispersion_cells:
            configs = ", ".join(f"{jc.template_name}/{jc.model}" for jc in cell.judge_configs)
            rprint(
                f"  {cell.artifact.source_document} ({cell.artifact.artifact_level.value})  "
                f"[{configs}]  disagreement_rate={cell.disagreement_rate:.2f} (n={cell.n})"
            )


def _read_float_config(key: str, cwd: str) -> float:
    """Read a float config key, erroring loudly on a non-numeric override."""
    value = get_config(key, cwd=cwd)
    if not isinstance(value, (int, float)):
        raise typer.BadParameter(
            f"{key} must be a number, got {value!r}. Fix it with 'sq config set {key} <n>'."
        )
    return float(value)


def _read_int_config(key: str, cwd: str) -> int:
    value = get_config(key, cwd=cwd)
    if not isinstance(value, int):
        raise typer.BadParameter(
            f"{key} must be an integer, got {value!r}. Fix it with 'sq config set {key} <n>'."
        )
    return value


def _build_recommendation_report(cwd: str, project: str | None) -> RecommendationReport:
    """Build the RecommendationReport a project's current agreement data supports."""
    store = _build_store(cwd)
    samples = store.list_samples(project_id=project)
    agreement = agreement_report(samples, cwd)
    return recommend_thresholds(
        agreement,
        floor=_read_int_config("metrology.min_evidence_n", cwd),
        graduate_rate=_read_float_config("metrology.graduate_match_rate", cwd),
        tighten_rate=_read_float_config("metrology.tighten_match_rate", cwd),
    )


@metrology_app.command("recommend")
def recommend(
    project: str | None = typer.Option(None, "--project", help="Filter by project id"),
    level: str | None = typer.Option(None, "--level", help="Filter by artifact level"),
    as_json: bool = typer.Option(False, "--json", help="Emit the RecommendationReport model verbatim"),
    cwd: str | None = typer.Option(None, "--cwd", help="Working directory"),
) -> None:
    """Advisory threshold recommendations per (artifact level, judge config). Read-only."""
    resolved_cwd = _resolve_cwd(cwd)
    level_filter = _parse_level_filter(level)

    try:
        report = _build_recommendation_report(resolved_cwd, project)
    except MetrologyStoreError as exc:
        rprint(f"[red]Store error: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    except MetrologyTargetError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    cells = [c for c in report.cells if level_filter is None or c.group.artifact_level == level_filter]

    if as_json:
        typer.echo(report.model_dump_json())
        return

    if not cells:
        rprint("[dim]No evidence.[/dim]")
    for cell in cells:
        jc = cell.group.judge_config
        rprint(
            f"{cell.group.artifact_level.value}  {jc.template_name}/{jc.model}  "
            f"{cell.direction.value}  match_rate={cell.evidence.match_rate:.2f} "
            f"(n={cell.evidence.n}, floor={cell.evidence.floor_applied})"
        )
        if cell.target.current is not None:
            rprint(
                f"  current: pass_floor={cell.target.current.pass_floor} "
                f"concerns_floor={cell.target.current.concerns_floor}"
            )
        else:
            rprint("  [yellow]current: template not resolvable[/yellow]")
        rprint(f"  [dim]{cell.target.model_dimension_note}[/dim]")
    rprint(f"[dim]{_excluded_line(report.excluded)}[/dim]")


@metrology_app.command("graduate")
def graduate(
    template: str = typer.Option(..., "--template", help="Judge template name"),
    model: str = typer.Option(..., "--model", help="Judge model"),
    level: str = typer.Option(..., "--level", help="Artifact level"),
    cwd: str | None = typer.Option(None, "--cwd", help="Working directory"),
) -> None:
    """Record a graduation for a (template, model) pairing. Refuses below GRADUATE."""
    resolved_cwd = _resolve_cwd(cwd)
    level_filter = _parse_level_filter(level)
    if level_filter is None:
        rprint("[red]Error: --level is required.[/red]")
        raise typer.Exit(code=1)

    try:
        report = _build_recommendation_report(resolved_cwd, None)
    except MetrologyStoreError as exc:
        rprint(f"[red]Store error: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    except MetrologyTargetError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    matching = [
        cell
        for cell in report.cells
        if cell.group.artifact_level == level_filter
        and cell.group.judge_config.template_name == template
        and cell.group.judge_config.model == model
    ]
    if not matching:
        rprint(
            f"[red]Error: no recommendation cell for template={template!r} "
            f"model={model!r} level={level_filter.value!r}.[/red]"
        )
        raise typer.Exit(code=1)
    cell = matching[0]

    if cell.direction != RecommendationDirection.GRADUATE:
        rprint(
            f"[red]Error: refusing to graduate — direction is {cell.direction.value}, "
            f"not GRADUATE (n={cell.evidence.n}, floor={cell.evidence.floor_applied}, "
            f"match_rate={cell.evidence.match_rate:.2f}). Nothing written.[/red]"
        )
        raise typer.Exit(code=1)

    graduated_config = GraduatedConfig(
        judge_config=cell.group.judge_config,
        artifact_level=level_filter,
        evidence=EvidenceSnapshot(
            n=cell.evidence.n,
            match_rate=cell.evidence.match_rate,
            floor_applied=cell.evidence.floor_applied,
            below_floor=cell.evidence.below_floor,
        ),
        graduated_at=datetime.now(UTC),
    )

    try:
        store = _build_store(resolved_cwd)
        existing = find_graduation(store, cell.group.judge_config, level_filter)
        write_graduation_record(store, graduated_config)
    except MetrologyStoreError as exc:
        rprint(f"[red]Store error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if existing is not None:
        rprint(
            f"[green]Updated existing graduation[/green] for {template}/{model} at {level_filter.value}"
        )
    else:
        rprint(f"[green]Graduated[/green] {template}/{model} at {level_filter.value}")


@metrology_app.command("offers")
def offers(
    project: str | None = typer.Option(None, "--project", help="Filter by project id"),
    as_json: bool = typer.Option(False, "--json", help="Emit OfferTargets as a JSON list"),
    cwd: str | None = typer.Option(None, "--cwd", help="Working directory"),
) -> None:
    """List residual-sampling targets for graduated judge configs. Read-only."""
    resolved_cwd = _resolve_cwd(cwd)

    try:
        store = _build_store(resolved_cwd)
        graduated_configs = list_graduations(store)
        rate = _read_float_config("metrology.residual_sample_rate", resolved_cwd)
        offer_targets = select_residual_offers(store, graduated_configs, rate=rate, cwd=resolved_cwd)
    except MetrologyStoreError as exc:
        rprint(f"[red]Store error: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    except MetrologyTargetError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if as_json:
        typer.echo("[" + ", ".join(o.model_dump_json() for o in offer_targets) + "]")
        return

    if not graduated_configs:
        rprint("[dim]No graduated configs.[/dim]")
        return

    offered_by_config: dict[tuple[str, str, str | None], int] = {}
    for target in offer_targets:
        jc = target.judge_config
        key = (jc.template_name, jc.model, jc.template_content_hash)
        offered_by_config[key] = offered_by_config.get(key, 0) + 1

    # A graduation is current when at least one presently-discoverable judge
    # result matches its exact identity — distinct from whether it has any
    # *unsampled* matches (that's the offer count above). Zero offers with
    # no current match at all means the graduation has lapsed.
    current_identities = {
        (jc.template_name, jc.model, jc.template_content_hash, level)
        for review_file in discover_judge_results(resolved_cwd)
        for jc, level in [_derive_judge_config_and_level(review_file)]
        if jc is not None
    }

    for config in graduated_configs:
        jc = config.judge_config
        key = (jc.template_name, jc.model, jc.template_content_hash)
        count = offered_by_config.get(key, 0)
        if count > 0:
            rprint(
                f"{jc.template_name}/{jc.model} ({config.artifact_level.value}): {count} offer(s) due"
            )
            continue
        still_current = (
            jc.template_name,
            jc.model,
            jc.template_content_hash,
            config.artifact_level,
        ) in current_identities
        if still_current:
            rprint(f"{jc.template_name}/{jc.model} ({config.artifact_level.value}): no offers due")
        else:
            rprint(
                f"[yellow]{jc.template_name}/{jc.model} ({config.artifact_level.value}): "
                "graduation has lapsed — the judge configuration has changed "
                "since this graduation was recorded[/yellow]"
            )

    for target in offer_targets:
        rprint(f"  offer: {target.review_path}")


def _derive_judge_config_and_level(
    review_file: Path,
) -> tuple[JudgeConfigId | None, ArtifactLevel | None]:
    """Best-effort JudgeConfigId + ArtifactLevel for a discovered review file.

    Used only for the offers command's lapse-vs-exhausted distinction; a
    file that fails to parse is skipped (returns None), matching
    discover_judge_results' own tolerant-skip convention.
    """
    try:
        frontmatter = read_review_frontmatter(review_file)
        judge_config = derive_judge_config_id(review_file)
    except MetrologyTargetError:
        return None, None
    raw_type = frontmatter.get("reviewType")
    level = derive_artifact_level(raw_type) if isinstance(raw_type, str) else ArtifactLevel.UNCLASSIFIED
    return judge_config, level

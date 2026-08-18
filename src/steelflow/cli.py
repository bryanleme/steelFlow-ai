"""Command-line entry point for reproducible SteelFlow AI workflows."""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import platform
import sys
from collections.abc import Sequence
from pathlib import Path

from steelflow import __version__
from steelflow.config import (
    ConfigError,
    available_profiles,
    load_config_bundle,
    resolve_project_root,
)
from steelflow.curation.database import DatabaseBuildError, build_analytics_database
from steelflow.curation.lineage import StaleAnalyticsError
from steelflow.features.builder import FeatureBuildError, build_feature_package
from steelflow.generation.generator import GenerationError, generate_dataset
from steelflow.observability import configure_logging
from steelflow.reporting.diagnostics import DiagnosticBuildError, build_diagnostic_package
from steelflow.validation.raw_data import validate_raw_dataset

LOGGER = logging.getLogger("steelflow.cli")

_FUTURE_COMMAND_PHASES = {
    "optimize-demo": 6,
    "app": 7,
}


def _add_profile_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", choices=available_profiles(), default="dev")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="steelflow",
        description="SteelFlow AI — offline synthetic decision-support prototype.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--project-root",
        type=Path,
        help="Project root override; defaults to the installed source tree.",
    )
    parser.add_argument("--log-level", default=None)
    parser.add_argument("--json-logs", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate-config", help="Validate one profile or the complete configuration set."
    )
    validate_parser.add_argument("--all", action="store_true", dest="all_profiles")
    _add_profile_argument(validate_parser)

    hash_parser = subparsers.add_parser(
        "config-hash", help="Print the stable SHA-256 hash of a validated configuration bundle."
    )
    _add_profile_argument(hash_parser)

    doctor_parser = subparsers.add_parser(
        "doctor", help="Check the runtime, repository structure and configuration contracts."
    )
    doctor_parser.add_argument("--json", action="store_true", dest="json_output")

    generate_parser = subparsers.add_parser(
        "generate", help="Generate one deterministic partitioned synthetic-data profile."
    )
    _add_profile_argument(generate_parser)
    generate_parser.add_argument(
        "--force",
        action="store_true",
        help="Replace only the deterministic run directory for this exact profile/configuration.",
    )

    validate_data_parser = subparsers.add_parser(
        "validate-data", help="Validate the deterministic raw run for one profile."
    )
    _add_profile_argument(validate_data_parser)

    build_database_parser = subparsers.add_parser(
        "build-db", help="Build and validate DuckDB analytics plus Power BI exports."
    )
    _add_profile_argument(build_database_parser)
    build_database_parser.add_argument(
        "--force",
        action="store_true",
        help="Replace only the analytical build for this exact deterministic run.",
    )

    diagnose_parser = subparsers.add_parser(
        "diagnose", help="Build validated descriptive diagnostics from the current DuckDB."
    )
    _add_profile_argument(diagnose_parser)
    diagnose_parser.add_argument("--force", action="store_true")

    feature_parser = subparsers.add_parser(
        "build-features", help="Build validated frozen point-in-time feature packages."
    )
    _add_profile_argument(feature_parser)
    feature_parser.add_argument("--force", action="store_true")

    train_parser = subparsers.add_parser(
        "train", help="Train temporal baselines, CatBoost, calibration and quantile models."
    )
    _add_profile_argument(train_parser)
    train_parser.add_argument(
        "--force",
        action="store_true",
        help="Replace only the deterministic model run for this exact contract.",
    )

    evaluate_parser = subparsers.add_parser(
        "evaluate", help="Evaluate a frozen model run once on the final chronological test."
    )
    _add_profile_argument(evaluate_parser)

    for command, phase in _FUTURE_COMMAND_PHASES.items():
        future_parser = subparsers.add_parser(
            command,
            help=f"Reserved product command; implementation is planned for Phase {phase}.",
        )
        _add_profile_argument(future_parser)

    return parser


def _validate_profiles(profiles: Sequence[str], project_root: Path | None) -> int:
    for profile in profiles:
        bundle = load_config_bundle(profile, project_root)
        print(
            f"OK profile={profile} days={bundle.simulation.period.duration_days} "
            f"bundle_sha256={bundle.stable_hash()}"
        )
    return 0


def _doctor(project_root: Path | None, *, json_output: bool) -> int:
    root = resolve_project_root(project_root)
    python_supported = (3, 11) <= sys.version_info[:2] < (3, 15)
    profile_results: dict[str, str] = {}
    for profile in available_profiles():
        bundle = load_config_bundle(profile, root)
        profile_results[profile] = bundle.stable_hash()

    packages = {
        package: importlib.util.find_spec(package) is not None
        for package in (
            "pydantic",
            "yaml",
            "pytest",
            "numpy",
            "pyarrow",
            "duckdb",
            "catboost",
            "sklearn",
            "shap",
            "streamlit",
        )
    }
    result = {
        "status": "ok" if python_supported else "error",
        "project_root": str(root),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "python_supported": python_supported,
        "profiles": profile_results,
        "packages": packages,
        "prototype_scope": "offline synthetic data; no machine control",
    }
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status: {result['status']}")
        print(f"python: {result['python']} (supported={str(python_supported).lower()})")
        print(f"profiles: {', '.join(profile_results)}")
        print("scope: offline synthetic data; no machine control")
        missing_optional = [
            package for package in ("duckdb", "catboost", "streamlit") if not packages[package]
        ]
        if missing_optional:
            print(f"optional packages pending later phases: {', '.join(missing_optional)}")
    return 0 if python_supported else 1


def _generate(profile: str, project_root: Path | None, *, force: bool) -> int:
    root = resolve_project_root(project_root)
    bundle = load_config_bundle(profile, root)
    result = generate_dataset(bundle, project_root=root, overwrite=force)
    print(
        f"OK run_id={result.simulation_run_id} profile={profile} "
        f"tables={len(result.table_counts)} rows={sum(result.table_counts.values())} "
        f"logical_sha256={result.dataset_logical_sha256} "
        f"elapsed_seconds={result.elapsed_seconds:.3f}"
    )
    print(f"raw_path={result.raw_path.relative_to(root)}")
    print(f"ground_truth_path={result.ground_truth_path.relative_to(root)} access=isolated")
    return 0


def _validate_data(profile: str, project_root: Path | None) -> int:
    root = resolve_project_root(project_root)
    bundle = load_config_bundle(profile, root)
    report = validate_raw_dataset(bundle, project_root=root)
    summary = report.to_dict()["summary"]
    print(
        f"{report.to_dict()['status']} run_id={report.simulation_run_id} "
        f"checks={summary['checks']} passed={summary['passed']} failed={summary['failed']}"
    )
    return 0 if report.passed else 1


def _build_database(profile: str, project_root: Path | None, *, force: bool) -> int:
    root = resolve_project_root(project_root)
    bundle = load_config_bundle(profile, root)
    result = build_analytics_database(
        bundle,
        project_root=root,
        overwrite=force,
    )
    print(
        f"OK run_id={result.simulation_run_id} profile={profile} "
        f"objects={sum(result.object_counts.values())} "
        f"elapsed_seconds={result.elapsed_seconds:.3f}"
    )
    print(f"database_path={result.database_path.relative_to(root)}")
    print(f"powerbi_export_path={result.export_path.relative_to(root)}")
    print(f"validation_path={result.validation_path.relative_to(root)} status=PASS")
    return 0


def _diagnose(profile: str, project_root: Path | None, *, force: bool) -> int:
    root = resolve_project_root(project_root)
    bundle = load_config_bundle(profile, root)
    result = build_diagnostic_package(
        bundle,
        project_root=root,
        overwrite=force,
    )
    print(
        f"OK run_id={result.simulation_run_id} profile={profile} "
        f"diagnostic_tables={len(result.table_rows)} rows={sum(result.table_rows.values())} "
        f"elapsed_seconds={result.elapsed_seconds:.3f}"
    )
    print(f"diagnostic_path={result.diagnostic_root.relative_to(root)}")
    print(f"validation_path={result.validation_path.relative_to(root)} status=PASS")
    return 0


def _build_features(profile: str, project_root: Path | None, *, force: bool) -> int:
    root = resolve_project_root(project_root)
    bundle = load_config_bundle(profile, root)
    result = build_feature_package(
        bundle,
        project_root=root,
        overwrite=force,
    )
    snapshot_rows = ",".join(
        f"{name}:{rows}" for name, rows in sorted(result.snapshot_rows.items())
    )
    print(
        f"OK run_id={result.simulation_run_id} profile={profile} "
        f"snapshots={snapshot_rows} elapsed_seconds={result.elapsed_seconds:.3f}"
    )
    print(f"feature_path={result.feature_root.relative_to(root)}")
    print(f"validation_path={result.validation_path.relative_to(root)} status=PASS")
    return 0


def _train_models(profile: str, project_root: Path | None, *, force: bool) -> int:
    from steelflow.models.pipeline import ModelPipelineError, train_models

    root = resolve_project_root(project_root)
    bundle = load_config_bundle(profile, root)
    try:
        result = train_models(bundle, project_root=root, overwrite=force)
    except ModelPipelineError as exc:
        raise ValueError(str(exc)) from exc
    print(
        f"OK run_id={result.simulation_run_id} profile={profile} tasks={result.task_count} "
        f"final_test_used=false elapsed_seconds={result.elapsed_seconds:.3f}"
    )
    print(f"model_path={result.model_root.relative_to(root)}")
    print(f"training_manifest={result.manifest_path.relative_to(root)} status=PASS")
    return 0


def _evaluate_models(profile: str, project_root: Path | None) -> int:
    from steelflow.models.pipeline import ModelPipelineError, evaluate_models
    from steelflow.validation.ground_truth_audit import audit_causal_recovery

    root = resolve_project_root(project_root)
    bundle = load_config_bundle(profile, root)
    try:
        result = evaluate_models(
            bundle,
            project_root=root,
            causal_auditor=audit_causal_recovery,
        )
    except ModelPipelineError as exc:
        raise ValueError(str(exc)) from exc
    print(
        f"OK run_id={result.simulation_run_id} profile={profile} tasks={result.task_count} "
        f"final_test_evaluations=1 reused={str(result.reused).lower()} "
        f"engineering_goal_met={str(result.engineering_goal_met).lower()} "
        f"causal_mechanisms_recovered={result.recovered_mechanisms} "
        f"elapsed_seconds={result.elapsed_seconds:.3f}"
    )
    print(f"evaluation_manifest={result.evaluation_path.relative_to(root)} status=PASS")
    return 0


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        configure_logging(args.log_level, json_output=args.json_logs)
        if args.command == "validate-config":
            profiles = available_profiles() if args.all_profiles else (args.profile,)
            return _validate_profiles(profiles, args.project_root)
        if args.command == "config-hash":
            print(load_config_bundle(args.profile, args.project_root).stable_hash())
            return 0
        if args.command == "doctor":
            return _doctor(args.project_root, json_output=args.json_output)
        if args.command == "generate":
            return _generate(args.profile, args.project_root, force=args.force)
        if args.command == "validate-data":
            return _validate_data(args.profile, args.project_root)
        if args.command == "build-db":
            return _build_database(args.profile, args.project_root, force=args.force)
        if args.command == "diagnose":
            return _diagnose(args.profile, args.project_root, force=args.force)
        if args.command == "build-features":
            return _build_features(args.profile, args.project_root, force=args.force)
        if args.command == "train":
            return _train_models(args.profile, args.project_root, force=args.force)
        if args.command == "evaluate":
            return _evaluate_models(args.profile, args.project_root)
        if args.command in _FUTURE_COMMAND_PHASES:
            phase = _FUTURE_COMMAND_PHASES[args.command]
            print(
                f"ERROR: command {args.command!r} is reserved for Phase {phase} and is not "
                "implemented in the current project phase.",
                file=sys.stderr,
            )
            return 2
    except (
        ConfigError,
        DatabaseBuildError,
        DiagnosticBuildError,
        FeatureBuildError,
        GenerationError,
        StaleAnalyticsError,
        ValueError,
    ) as exc:
        LOGGER.error("command_failed", extra={"command": args.command, "reason": str(exc)})
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    parser.error(f"unsupported command: {args.command}")
    return 2


def main() -> None:
    raise SystemExit(run())

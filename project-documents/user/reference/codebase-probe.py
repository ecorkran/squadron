#!/usr/bin/env python3
"""
codebase-probe.py — Deterministic codebase extraction for AI analysis pipelines.

Three-phase analysis pipeline:
  Phase 1 (this script): Extract structured metadata + optional code packing via Repomix
  Phase 2 (prompt): Feed outputs to an LLM for architectural analysis
  Phase 3 (interactive): Deep-dive via Serena/GitHub MCP

Usage:
  python codebase-probe.py /path/to/repo
  python codebase-probe.py /path/to/repo --output probe-results.json
  python codebase-probe.py /path/to/repo --all                # all analyzers
  python codebase-probe.py /path/to/repo --all --repomix      # analyzers + code packing
  python codebase-probe.py /path/to/repo --repomix --repomix-compress  # pack with compression
  python codebase-probe.py /path/to/repo --repomix --repomix-style markdown
  python codebase-probe.py /path/to/repo --depgraph           # dependency graph extraction

Output: JSON to stdout (or --output file) containing structured codebase metadata.
        Repomix output written to <repo>-repomix.<style> alongside probe results.
"""

import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Files that indicate the tech stack
STACK_INDICATOR_FILES = {
    # Python
    "pyproject.toml": "python",
    "setup.py": "python",
    "setup.cfg": "python",
    "requirements.txt": "python",
    "Pipfile": "python",
    "poetry.lock": "python",
    "tox.ini": "python",
    "ruff.toml": "python",
    ".python-version": "python",
    # JavaScript / TypeScript
    "package.json": "javascript",
    "tsconfig.json": "typescript",
    "bun.lockb": "javascript",
    "deno.json": "javascript",
    "deno.jsonc": "javascript",
    # Rust
    "Cargo.toml": "rust",
    "Cargo.lock": "rust",
    # Go
    "go.mod": "go",
    "go.sum": "go",
    # Java / Kotlin / JVM
    "pom.xml": "java",
    "build.gradle": "java",
    "build.gradle.kts": "kotlin",
    "gradlew": "java",
    # C / C++
    "CMakeLists.txt": "cpp",
    "Makefile": "c/cpp",
    "meson.build": "c/cpp",
    # Ruby
    "Gemfile": "ruby",
    "Rakefile": "ruby",
    # PHP
    "composer.json": "php",
    # .NET
    "*.csproj": "csharp",
    "*.fsproj": "fsharp",
    "Directory.Build.props": "dotnet",
    # Elixir
    "mix.exs": "elixir",
    # Swift
    "Package.swift": "swift",
}

# CI/CD indicators
CI_PATTERNS = {
    ".github/workflows": "github_actions",
    ".gitlab-ci.yml": "gitlab_ci",
    "Jenkinsfile": "jenkins",
    ".circleci": "circleci",
    ".travis.yml": "travis",
    "azure-pipelines.yml": "azure_devops",
    "bitbucket-pipelines.yml": "bitbucket",
    ".drone.yml": "drone",
    "Taskfile.yml": "taskfile",
    "Justfile": "just",
    "justfile": "just",
}

# Containerization
CONTAINER_FILES = [
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    ".dockerignore",
    "devcontainer.json",
    ".devcontainer/devcontainer.json",
    "kubernetes/",
    "k8s/",
    "helm/",
    "charts/",
    "fly.toml",
    "render.yaml",
    "railway.json",
    "vercel.json",
    "netlify.toml",
    "app.yaml",  # GCP App Engine
    "serverless.yml",
]

# Test directory patterns
TEST_DIR_PATTERNS = [
    "tests",
    "test",
    "__tests__",
    "spec",
    "specs",
    "test_*",
    "*_test",
    "testing",
    "e2e",
    "integration",
    "unit",
]

# Async / concurrency pattern indicators (by language)
ASYNC_PATTERNS = {
    "python": {
        "asyncio": ["import asyncio", "async def", "await ", "asyncio.run"],
        "celery": ["from celery", "import celery", "@app.task", "@shared_task"],
        "threading": ["import threading", "Thread(", "threading.Lock"],
        "multiprocessing": ["import multiprocessing", "Process(", "Pool("],
        "trio": ["import trio"],
        "anyio": ["import anyio"],
        "uvloop": ["import uvloop"],
        "gevent": ["import gevent"],
        "twisted": ["from twisted", "import twisted"],
        "fastapi": ["from fastapi", "import fastapi"],  # implies async
        "aiohttp": ["import aiohttp"],
        "httpx_async": ["async with httpx"],
    },
    "javascript": {
        "async_await": ["async function", "async (", "await "],
        "promises": ["new Promise", ".then(", ".catch("],
        "worker_threads": ["worker_threads", "new Worker"],
        "cluster": ["require('cluster')", "cluster.fork"],
        "rxjs": ["from 'rxjs'", "Observable", "Subject"],
        "express": ["require('express')", "from 'express'"],
        "fastify": ["require('fastify')", "from 'fastify'"],
        "koa": ["require('koa')", "from 'koa'"],
        "nextjs": ["from 'next'", "getServerSideProps", "getStaticProps"],
        "websocket": ["WebSocket", "ws://", "wss://", "socket.io"],
    },
    "go": {
        "goroutines": ["go func", "go ", "chan ", "select {"],
        "sync": ["sync.Mutex", "sync.WaitGroup", "sync.Once"],
        "channels": ["make(chan", "<-chan", "chan<-"],
        "context": ["context.Background", "context.WithCancel"],
    },
    "rust": {
        "tokio": ["tokio::", "#[tokio::main]", "tokio::spawn"],
        "async_std": ["async_std::", "#[async_std::main]"],
        "rayon": ["rayon::", ".par_iter()"],
        "crossbeam": ["crossbeam::"],
        "channels": ["mpsc::", "crossbeam_channel"],
    },
}

# AI/Agent indicators
AI_AGENT_FILES = [
    "CLAUDE.md",
    ".claude/",
    ".cursorrules",
    ".cursor/",
    ".windsurfrules",
    ".github/copilot-instructions.md",
    ".aider.conf.yml",
    ".continue/",
    "mcp.json",
    ".mcp.json",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_cmd(cmd: list[str], cwd: str, timeout: int = 60) -> tuple[str, str, int]:
    """Run a command, return (stdout, stderr, returncode)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout
        )
        return result.stdout, result.stderr, result.returncode
    except FileNotFoundError:
        return "", f"Command not found: {cmd[0]}", -1
    except subprocess.TimeoutExpired:
        return "", f"Timeout after {timeout}s", -2


def tool_available(name: str) -> bool:
    """Check if a CLI tool is available."""
    try:
        subprocess.run([name, "--version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def read_file_safe(path: Path, max_bytes: int = 50_000) -> str | None:
    """Read a file, return None if it fails or is too large."""
    try:
        size = path.stat().st_size
        if size > max_bytes:
            return f"[FILE TOO LARGE: {size} bytes, max {max_bytes}]"
        return path.read_text(errors="replace")
    except Exception:
        return None


def count_lines(path: Path) -> int | None:
    """Count lines in a file."""
    try:
        return sum(1 for _ in path.open(errors="replace"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------


def extract_tree(repo: Path, max_depth: int = 3) -> dict:
    """Get directory tree up to max_depth, excluding common noise."""
    ignore_dirs = {
        ".git",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        "venv",
        ".venv",
        "env",
        ".env",
        "dist",
        "build",
        ".next",
        ".nuxt",
        ".output",
        "target",
        "coverage",
        ".coverage",
        "htmlcov",
        ".eggs",
        "*.egg-info",
    }
    ignore_files = {".DS_Store", "Thumbs.db", "*.pyc", "*.pyo"}

    def _walk(path: Path, depth: int) -> dict:
        if depth > max_depth:
            return {"_truncated": True}
        result = {}
        try:
            entries = sorted(
                path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except PermissionError:
            return {"_permission_denied": True}

        for entry in entries:
            name = entry.name
            if name in ignore_dirs or name.startswith(".git"):
                if name == ".github":
                    pass  # keep .github
                else:
                    continue
            if entry.is_dir():
                result[name + "/"] = _walk(entry, depth + 1)
            else:
                if name in ignore_files:
                    continue
                lines = count_lines(entry)
                result[name] = {"lines": lines, "size": entry.stat().st_size}
        return result

    return _walk(repo, 0)


def detect_stack(repo: Path) -> dict:
    """Detect technology stack from indicator files."""
    found = {}
    config_contents = {}

    for indicator, lang in STACK_INDICATOR_FILES.items():
        if "*" in indicator:
            matches = list(repo.glob(indicator))
            if matches:
                for m in matches:
                    found[m.name] = lang
        else:
            path = repo / indicator
            if path.exists():
                found[indicator] = lang
                # Read key config files
                if indicator in (
                    "package.json",
                    "pyproject.toml",
                    "Cargo.toml",
                    "go.mod",
                    "pom.xml",
                    "composer.json",
                    "Gemfile",
                    "mix.exs",
                    "requirements.txt",
                ):
                    content = read_file_safe(path, max_bytes=100_000)
                    if content:
                        config_contents[indicator] = content

    # Deduce primary language
    lang_counts = Counter(found.values())
    primary = lang_counts.most_common(1)[0][0] if lang_counts else "unknown"

    return {
        "primary_language": primary,
        "indicator_files": found,
        "config_contents": config_contents,
        "all_languages_detected": dict(lang_counts),
    }


def detect_ci_cd(repo: Path) -> dict:
    """Detect CI/CD configuration."""
    found = {}
    configs = {}

    for pattern, system in CI_PATTERNS.items():
        path = repo / pattern
        if path.exists():
            found[pattern] = system
            if path.is_file():
                content = read_file_safe(path)
                if content:
                    configs[pattern] = content
            elif path.is_dir():
                # Read workflow files
                for f in sorted(path.rglob("*.yml"))[:10]:  # cap at 10
                    rel = str(f.relative_to(repo))
                    content = read_file_safe(f)
                    if content:
                        configs[rel] = content
                for f in sorted(path.rglob("*.yaml"))[:10]:
                    rel = str(f.relative_to(repo))
                    content = read_file_safe(f)
                    if content:
                        configs[rel] = content

    return {"systems": found, "configs": configs}


def detect_containers(repo: Path) -> dict:
    """Detect containerization and deployment config."""
    found = {}
    configs = {}

    for pattern in CONTAINER_FILES:
        if pattern.endswith("/"):
            path = repo / pattern.rstrip("/")
            if path.is_dir():
                found[pattern] = True
        else:
            path = repo / pattern
            if path.exists():
                found[pattern] = True
                content = read_file_safe(path)
                if content:
                    configs[pattern] = content

    return {"files": found, "configs": configs}


def detect_tests(repo: Path) -> dict:
    """Detect test infrastructure."""
    test_dirs = []
    test_files = []
    test_configs = {}

    # Find test directories
    for d in repo.iterdir():
        if d.is_dir() and d.name.lower() in [p.lower() for p in TEST_DIR_PATTERNS]:
            test_dirs.append(d.name)

    # Find test files by pattern
    patterns = [
        "test_*.py",
        "*_test.py",
        "*_test.go",
        "*_test.rs",
        "*.test.js",
        "*.test.ts",
        "*.test.jsx",
        "*.test.tsx",
        "*.spec.js",
        "*.spec.ts",
        "*.spec.jsx",
        "*.spec.tsx",
        "*Test.java",
        "*_test.rb",
    ]
    for pattern in patterns:
        for f in repo.rglob(pattern):
            if ".git" not in str(f) and "node_modules" not in str(f):
                test_files.append(str(f.relative_to(repo)))

    # Test config files
    test_config_files = [
        "pytest.ini",
        "pyproject.toml",
        "setup.cfg",  # pytest config
        "jest.config.js",
        "jest.config.ts",
        "jest.config.mjs",
        "vitest.config.ts",
        "vitest.config.js",
        "karma.conf.js",
        "cypress.config.js",
        "cypress.config.ts",
        "playwright.config.ts",
        "playwright.config.js",
        ".mocharc.yml",
        ".mocharc.json",
        "phpunit.xml",
    ]
    for cfg in test_config_files:
        path = repo / cfg
        if path.exists():
            test_configs[cfg] = True

    return {
        "test_directories": test_dirs,
        "test_file_count": len(test_files),
        "test_files_sample": test_files[:50],  # cap at 50
        "test_configs": test_configs,
    }


def detect_async_patterns(repo: Path, primary_lang: str) -> dict:
    """Scan source files for async/concurrency patterns."""
    patterns = ASYNC_PATTERNS.get(primary_lang, {})
    if not patterns:
        # Try all if language unknown
        patterns = {}
        for lang_patterns in ASYNC_PATTERNS.values():
            patterns.update(lang_patterns)

    found = defaultdict(int)
    ext_map = {
        "python": [".py"],
        "javascript": [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"],
        "typescript": [".ts", ".tsx"],
        "go": [".go"],
        "rust": [".rs"],
    }
    extensions = ext_map.get(primary_lang, [".py", ".js", ".ts", ".go", ".rs"])

    files_scanned = 0
    for ext in extensions:
        for f in repo.rglob(f"*{ext}"):
            if any(
                skip in str(f)
                for skip in [
                    ".git",
                    "node_modules",
                    "__pycache__",
                    "venv",
                    ".venv",
                    "dist",
                    "build",
                ]
            ):
                continue
            files_scanned += 1
            if files_scanned > 500:  # safety cap
                break
            try:
                content = f.read_text(errors="replace")
            except Exception:
                continue
            for pattern_name, indicators in patterns.items():
                for indicator in indicators:
                    if indicator in content:
                        found[pattern_name] += 1
                        break  # count each pattern once per file

    return {
        "files_scanned": files_scanned,
        "patterns_found": dict(found),
    }


def detect_entry_points(repo: Path, primary_lang: str) -> list[str]:
    """Identify likely entry points."""
    candidates = []
    entry_files = {
        "python": [
            "main.py",
            "app.py",
            "__main__.py",
            "manage.py",
            "wsgi.py",
            "asgi.py",
            "cli.py",
            "server.py",
            "run.py",
        ],
        "javascript": [
            "index.js",
            "index.ts",
            "main.js",
            "main.ts",
            "app.js",
            "app.ts",
            "server.js",
            "server.ts",
            "index.mjs",
        ],
        "go": ["main.go", "cmd/"],
        "rust": ["src/main.rs", "src/lib.rs"],
        "java": ["src/main/"],
        "ruby": ["config.ru", "Rakefile", "bin/"],
        "elixir": ["lib/", "config/"],
    }

    for entry in entry_files.get(primary_lang, []):
        if entry.endswith("/"):
            path = repo / entry
            if path.is_dir():
                candidates.append(entry)
        else:
            # Check root and src/
            for prefix in ["", "src/"]:
                path = repo / prefix / entry
                if path.exists():
                    candidates.append(f"{prefix}{entry}")

    # Also check pyproject.toml for [tool.poetry.scripts] or [project.scripts]
    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        content = read_file_safe(pyproject)
        if content and (
            "[project.scripts]" in content or "[tool.poetry.scripts]" in content
        ):
            candidates.append("pyproject.toml [scripts]")

    # Check package.json for scripts.start / main
    pkg = repo / "package.json"
    if pkg.exists():
        content = read_file_safe(pkg)
        if content:
            try:
                data = json.loads(content)
                if "main" in data:
                    candidates.append(f"package.json main: {data['main']}")
                if "scripts" in data and "start" in data["scripts"]:
                    candidates.append(f"package.json start: {data['scripts']['start']}")
            except json.JSONDecodeError:
                pass

    return candidates


def detect_ai_agent_config(repo: Path) -> dict:
    """Detect AI agent configuration files."""
    found = {}
    for pattern in AI_AGENT_FILES:
        if pattern.endswith("/"):
            path = repo / pattern.rstrip("/")
            if path.is_dir():
                found[pattern] = "directory"
        else:
            path = repo / pattern
            if path.exists():
                content = read_file_safe(path)
                found[pattern] = content if content else "exists"
    return found


def detect_architecture_signals(repo: Path) -> dict:
    """Look for architectural patterns: monorepo, microservices, workspace, etc."""
    signals = {}

    # Monorepo / workspace indicators
    pkg = repo / "package.json"
    if pkg.exists():
        content = read_file_safe(pkg)
        if content:
            try:
                data = json.loads(content)
                if "workspaces" in data:
                    signals["monorepo_workspaces"] = data["workspaces"]
            except json.JSONDecodeError:
                pass

    # pnpm workspaces
    if (repo / "pnpm-workspace.yaml").exists():
        signals["pnpm_workspaces"] = True

    # Lerna
    if (repo / "lerna.json").exists():
        signals["lerna_monorepo"] = True

    # Nx
    if (repo / "nx.json").exists():
        signals["nx_monorepo"] = True

    # Turborepo
    if (repo / "turbo.json").exists():
        signals["turborepo"] = True

    # Cargo workspaces
    cargo = repo / "Cargo.toml"
    if cargo.exists():
        content = read_file_safe(cargo)
        if content and "[workspace]" in content:
            signals["cargo_workspace"] = True

    # Multiple package.json files (potential microservices)
    pkg_jsons = list(repo.rglob("package.json"))
    pkg_jsons = [p for p in pkg_jsons if "node_modules" not in str(p)]
    if len(pkg_jsons) > 1:
        signals["multiple_package_json"] = [
            str(p.relative_to(repo)) for p in pkg_jsons[:20]
        ]

    # Docker compose services
    for compose_file in [
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
    ]:
        path = repo / compose_file
        if path.exists():
            content = read_file_safe(path)
            if content:
                # Count services (rough)
                service_count = content.count("\n  ") - content.count("\n    ")
                # Extract service names (lines with exactly 2-space indent followed by name:)
                services = re.findall(r"^  (\w[\w-]*):", content, re.MULTILINE)
                if services:
                    signals["docker_compose_services"] = services

    # Top-level directories that suggest architectural boundaries
    boundary_dirs = []
    for d in sorted(repo.iterdir()):
        if (
            d.is_dir()
            and not d.name.startswith(".")
            and d.name
            not in {
                "node_modules",
                "__pycache__",
                "venv",
                ".venv",
                "dist",
                "build",
                "coverage",
                "docs",
                "doc",
                "documentation",
                "scripts",
                "tools",
                "assets",
                "static",
                "public",
                "templates",
            }
        ):
            boundary_dirs.append(d.name)
    signals["top_level_dirs"] = boundary_dirs

    return signals


def get_file_stats(repo: Path) -> dict:
    """Get aggregate file statistics."""
    ext_counts: Counter = Counter()
    ext_lines: Counter = Counter()
    total_files = 0

    skip = {
        ".git",
        "node_modules",
        "__pycache__",
        "venv",
        ".venv",
        "dist",
        "build",
        ".next",
        "target",
        "coverage",
    }

    for f in repo.rglob("*"):
        if any(s in f.parts for s in skip):
            continue
        if not f.is_file():
            continue
        total_files += 1
        ext = f.suffix.lower() or "(no ext)"
        ext_counts[ext] += 1
        lines = count_lines(f)
        if lines is not None:
            ext_lines[ext] += lines

    return {
        "total_files": total_files,
        "by_extension": {
            ext: {"count": ext_counts[ext], "lines": ext_lines.get(ext, 0)}
            for ext in ext_counts.most_common(30)
            for ext in [ext[0]]
        },
    }


def get_docs(repo: Path) -> dict:
    """Extract documentation files."""
    doc_files = [
        "README.md",
        "README.rst",
        "README.txt",
        "README",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "CHANGES.md",
        "ARCHITECTURE.md",
        "DESIGN.md",
        "ADR/",
        "docs/",
        "LICENSE",
        "LICENSE.md",
        "LICENSE.txt",
    ]
    found = {}
    for name in doc_files:
        path = repo / name
        if path.exists():
            if path.is_file():
                content = read_file_safe(path, max_bytes=30_000)
                found[name] = content if content else "exists (unreadable)"
            elif path.is_dir():
                files = [
                    str(f.relative_to(repo))
                    for f in sorted(path.rglob("*"))
                    if f.is_file()
                ][:30]
                found[name] = {"type": "directory", "files": files}
    return found


def get_git_info(repo: Path) -> dict:
    """Extract git metadata."""
    info = {}

    # Recent commits
    stdout, _, rc = run_cmd(
        ["git", "log", "--oneline", "--no-decorate", "-20"], cwd=str(repo)
    )
    if rc == 0:
        info["recent_commits"] = stdout.strip().split("\n")

    # Contributors
    stdout, _, rc = run_cmd(
        ["git", "shortlog", "-sn", "--no-merges", "HEAD"], cwd=str(repo)
    )
    if rc == 0:
        info["contributors"] = stdout.strip().split("\n")[:20]

    # Branch info
    stdout, _, rc = run_cmd(["git", "branch", "-a", "--no-color"], cwd=str(repo))
    if rc == 0:
        info["branches"] = [b.strip() for b in stdout.strip().split("\n")][:30]

    # Remotes
    stdout, _, rc = run_cmd(["git", "remote", "-v"], cwd=str(repo))
    if rc == 0:
        info["remotes"] = stdout.strip()

    # Tags
    stdout, _, rc = run_cmd(["git", "tag", "--sort=-v:refname"], cwd=str(repo))
    if rc == 0:
        tags = stdout.strip().split("\n")[:10]
        info["recent_tags"] = [t for t in tags if t]

    return info


# ---------------------------------------------------------------------------
# Optional Tool Integrations
# ---------------------------------------------------------------------------


def run_semgrep(repo: Path) -> dict | None:
    """Run semgrep if available."""
    if not tool_available("semgrep"):
        return {"status": "not_installed", "install": "pip install semgrep"}

    stdout, stderr, rc = run_cmd(
        [
            "semgrep",
            "scan",
            "--config=auto",
            "--json",
            "--quiet",
            "--max-target-bytes=1000000",
            "--timeout=30",
        ],
        cwd=str(repo),
        timeout=300,
    )
    if rc == 0 and stdout:
        try:
            data = json.loads(stdout)
            results = data.get("results", [])
            # Summarize findings
            by_severity = Counter()
            by_category = Counter()
            findings = []
            for r in results[:100]:  # cap detail
                severity = r.get("extra", {}).get("severity", "unknown")
                category = (
                    r.get("extra", {}).get("metadata", {}).get("category", "unknown")
                )
                by_severity[severity] += 1
                by_category[category] += 1
                findings.append(
                    {
                        "rule": r.get("check_id", ""),
                        "severity": severity,
                        "file": r.get("path", ""),
                        "line": r.get("start", {}).get("line", 0),
                        "message": r.get("extra", {}).get("message", "")[:200],
                    }
                )
            return {
                "status": "ok",
                "total_findings": len(results),
                "by_severity": dict(by_severity),
                "by_category": dict(by_category),
                "findings": findings,
            }
        except json.JSONDecodeError:
            return {"status": "parse_error", "stderr": stderr[:500]}
    else:
        return {"status": "error", "returncode": rc, "stderr": stderr[:500]}


def run_ruff(repo: Path) -> dict | None:
    """Run ruff if available (Python projects)."""
    if not tool_available("ruff"):
        return {"status": "not_installed", "install": "pip install ruff"}

    stdout, stderr, rc = run_cmd(
        ["ruff", "check", "--output-format=json", "--quiet", "."],
        cwd=str(repo),
        timeout=120,
    )
    if stdout:
        try:
            results = json.loads(stdout)
            by_code = Counter()
            for r in results:
                by_code[r.get("code", "unknown")] += 1
            return {
                "status": "ok",
                "total_findings": len(results),
                "by_rule": dict(by_code.most_common(20)),
                "sample": results[:30],
            }
        except json.JSONDecodeError:
            return {"status": "parse_error", "raw": stdout[:500]}
    return {"status": "clean" if rc == 0 else "error", "stderr": stderr[:500]}


def run_eslint(repo: Path) -> dict | None:
    """Run eslint if available and configured."""
    # Check for eslint config
    eslint_configs = [
        ".eslintrc.js",
        ".eslintrc.json",
        ".eslintrc.yml",
        ".eslintrc.yaml",
        "eslint.config.js",
        "eslint.config.mjs",
    ]
    has_config = any((repo / c).exists() for c in eslint_configs)
    if not has_config:
        pkg = repo / "package.json"
        if pkg.exists():
            content = read_file_safe(pkg)
            if content and '"eslintConfig"' in content:
                has_config = True

    if not has_config:
        return {"status": "no_config"}

    # Try npx eslint
    stdout, stderr, rc = run_cmd(
        ["npx", "--yes", "eslint", "--format=json", "."], cwd=str(repo), timeout=120
    )
    if stdout:
        try:
            results = json.loads(stdout)
            total_errors = sum(r.get("errorCount", 0) for r in results)
            total_warnings = sum(r.get("warningCount", 0) for r in results)
            return {
                "status": "ok",
                "total_errors": total_errors,
                "total_warnings": total_warnings,
                "files_with_issues": len(
                    [
                        r
                        for r in results
                        if r.get("errorCount", 0) + r.get("warningCount", 0) > 0
                    ]
                ),
            }
        except json.JSONDecodeError:
            pass
    return {"status": "error", "stderr": stderr[:500]}


# ---------------------------------------------------------------------------
# Repomix Integration
# ---------------------------------------------------------------------------


def detect_repomix() -> dict:
    """Check if repomix is available and how."""
    # Try npx (always available if node is)
    for cmd in ["repomix", "npx"]:
        if tool_available(cmd):
            return {"available": True, "via": cmd}
    return {
        "available": False,
        "install": "npm install -g repomix  # or use npx repomix",
    }


def run_repomix(repo: Path, options: dict) -> dict:
    """Run repomix to pack the codebase for LLM consumption."""
    detection = detect_repomix()
    if not detection["available"]:
        return {"status": "not_installed", **detection}

    style = options.get("repomix_style", "xml")
    compress = options.get("repomix_compress", True)

    # Determine output path
    output_dir = options.get("output_dir", str(repo.parent))
    output_file = f"{repo.name}-repomix.{style}"
    output_path = str(Path(output_dir) / output_file)

    cmd = []
    if detection["via"] == "npx":
        cmd = ["npx", "--yes", "repomix"]
    else:
        cmd = ["repomix"]

    cmd.extend(
        [
            "--style",
            style,
            "--output",
            output_path,
        ]
    )
    if compress:
        cmd.append("--compress")

    # Exclude heavy directories that aren't useful for analysis
    cmd.extend(["--ignore", "**/*.lock,**/package-lock.json,**/*.min.js,**/*.min.css"])

    print(
        f"  [+] Running repomix (style={style}, compress={compress})...",
        file=sys.stderr,
    )
    stdout, stderr, rc = run_cmd(cmd, cwd=str(repo), timeout=300)

    if rc == 0:
        # Get output file size and token count estimate
        out_path = Path(output_path)
        if out_path.exists():
            size = out_path.stat().st_size
            # Rough token estimate: ~4 chars per token
            est_tokens = size // 4
            return {
                "status": "ok",
                "output_path": output_path,
                "output_size_bytes": size,
                "estimated_tokens": est_tokens,
                "style": style,
                "compressed": compress,
                "note": "Feed this file to the analysis prompt alongside probe-results.json",
            }
        else:
            return {
                "status": "error",
                "message": "Output file not created",
                "stderr": stderr[:500],
            }
    else:
        return {"status": "error", "returncode": rc, "stderr": stderr[:500]}


# ---------------------------------------------------------------------------
# Dependency Graph Extraction
# ---------------------------------------------------------------------------


def extract_python_imports(repo: Path) -> dict:
    """Extract import graph from Python files."""
    imports = defaultdict(set)
    external_deps = set()
    internal_modules = set()

    # Identify internal package names
    for f in repo.rglob("__init__.py"):
        if any(skip in str(f) for skip in [".git", "node_modules", "venv", ".venv"]):
            continue
        pkg = f.parent.relative_to(repo).parts
        if pkg:
            internal_modules.add(pkg[0])

    # Also treat top-level .py files as internal
    for f in repo.glob("*.py"):
        internal_modules.add(f.stem)
    src_dir = repo / "src"
    if src_dir.is_dir():
        for f in src_dir.rglob("__init__.py"):
            pkg = f.parent.relative_to(src_dir).parts
            if pkg:
                internal_modules.add(pkg[0])

    # Scan imports
    import_re = re.compile(
        r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.MULTILINE
    )

    for f in repo.rglob("*.py"):
        if any(
            skip in str(f)
            for skip in [
                ".git",
                "node_modules",
                "venv",
                ".venv",
                "__pycache__",
                "dist",
                "build",
            ]
        ):
            continue
        try:
            content = f.read_text(errors="replace")
        except Exception:
            continue

        rel = str(f.relative_to(repo))
        for match in import_re.finditer(content):
            module = match.group(1) or match.group(2)
            root_module = module.split(".")[0]
            if root_module in internal_modules:
                imports[rel].add(module)
            else:
                external_deps.add(root_module)

    return {
        "internal_import_graph": {k: sorted(v) for k, v in sorted(imports.items())},
        "internal_modules": sorted(internal_modules),
        "external_dependencies": sorted(external_deps),
        "files_with_internal_imports": len(imports),
    }


def extract_js_imports(repo: Path) -> dict:
    """Extract import graph from JS/TS files."""
    imports = defaultdict(set)
    external_deps = set()

    # Relative import pattern: from './foo' or from '../bar'
    rel_import_re = re.compile(r"""(?:from|require\()\s*['"](\.[^'"]+)['"]""")
    # Package import: from 'package' or from '@scope/package'
    pkg_import_re = re.compile(
        r"""(?:from|require\()\s*['"](@?[^.'"/][^'"]*?)(?:/[^'"]*)?['"]"""
    )

    extensions = [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"]

    for ext in extensions:
        for f in repo.rglob(f"*{ext}"):
            if any(
                skip in str(f)
                for skip in [".git", "node_modules", "dist", "build", ".next"]
            ):
                continue
            try:
                content = f.read_text(errors="replace")
            except Exception:
                continue

            rel = str(f.relative_to(repo))
            for match in rel_import_re.finditer(content):
                imports[rel].add(match.group(1))
            for match in pkg_import_re.finditer(content):
                external_deps.add(match.group(1))

    return {
        "internal_import_graph": {
            k: sorted(v) for k, v in sorted(imports.items())[:100]
        },
        "external_dependencies": sorted(external_deps),
        "files_with_imports": len(imports),
    }


def run_depgraph(repo: Path, primary_lang: str) -> dict:
    """Run dependency graph extraction appropriate to the language."""
    result = {"language": primary_lang}

    if primary_lang == "python":
        result["import_analysis"] = extract_python_imports(repo)

        # Try pipdeptree if available
        if tool_available("pipdeptree"):
            stdout, stderr, rc = run_cmd(
                ["pipdeptree", "--json"], cwd=str(repo), timeout=30
            )
            if rc == 0 and stdout:
                try:
                    result["pip_dependency_tree"] = json.loads(stdout)
                except json.JSONDecodeError:
                    pass

    elif primary_lang in ("javascript", "typescript"):
        result["import_analysis"] = extract_js_imports(repo)

        # Try dependency-cruiser if available
        if tool_available("npx"):
            stdout, stderr, rc = run_cmd(
                [
                    "npx",
                    "--yes",
                    "dependency-cruiser",
                    "src",
                    "--output-type",
                    "json",
                    "--no-config",
                ],
                cwd=str(repo),
                timeout=120,
            )
            if rc == 0 and stdout:
                try:
                    data = json.loads(stdout)
                    modules = data.get("modules", [])
                    violations = data.get("summary", {}).get("violations", [])
                    result["dependency_cruiser"] = {
                        "module_count": len(modules),
                        "violation_count": len(violations),
                        "circular_deps": [
                            v
                            for v in violations
                            if v.get("rule", {}).get("name") == "no-circular"
                        ],
                    }
                except json.JSONDecodeError:
                    pass

        # Try madge for circular dependency detection
        if tool_available("npx"):
            stdout, stderr, rc = run_cmd(
                ["npx", "--yes", "madge", "--json", "--circular", "."],
                cwd=str(repo),
                timeout=60,
            )
            if rc == 0 and stdout:
                try:
                    circular = json.loads(stdout)
                    if circular:
                        result["circular_dependencies"] = circular[:20]
                except json.JSONDecodeError:
                    pass

    elif primary_lang == "go":
        # Go module graph
        stdout, stderr, rc = run_cmd(["go", "mod", "graph"], cwd=str(repo), timeout=30)
        if rc == 0 and stdout:
            edges = stdout.strip().split("\n")
            result["go_mod_graph_edges"] = len(edges)
            result["go_mod_graph_sample"] = edges[:30]

    elif primary_lang == "rust":
        # Cargo dependency tree
        stdout, stderr, rc = run_cmd(
            ["cargo", "tree", "--depth=2", "--prefix=none"], cwd=str(repo), timeout=30
        )
        if rc == 0 and stdout:
            result["cargo_tree"] = stdout[:5000]

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def probe(repo_path: str, options: dict) -> dict:
    """Run the full probe and return structured results."""
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        return {"error": f"Not a directory: {repo}"}

    results: dict[str, Any] = {
        "_meta": {
            "probe_version": "0.2.0",
            "repo_path": str(repo),
            "repo_name": repo.name,
        }
    }

    # Always-on extractors
    print("  [1/10] Detecting tech stack...", file=sys.stderr)
    stack = detect_stack(repo)
    results["stack"] = stack

    print("  [2/10] Scanning file tree...", file=sys.stderr)
    results["tree"] = extract_tree(repo, max_depth=options.get("depth", 3))

    print("  [3/10] Gathering file stats...", file=sys.stderr)
    results["file_stats"] = get_file_stats(repo)

    print("  [4/10] Detecting CI/CD...", file=sys.stderr)
    results["ci_cd"] = detect_ci_cd(repo)

    print("  [5/10] Detecting containers & deployment...", file=sys.stderr)
    results["containers"] = detect_containers(repo)

    print("  [6/10] Detecting test infrastructure...", file=sys.stderr)
    results["tests"] = detect_tests(repo)

    print("  [7/10] Scanning async/concurrency patterns...", file=sys.stderr)
    results["async_patterns"] = detect_async_patterns(repo, stack["primary_language"])

    print("  [8/10] Identifying entry points & architecture...", file=sys.stderr)
    results["entry_points"] = detect_entry_points(repo, stack["primary_language"])
    results["architecture"] = detect_architecture_signals(repo)

    print("  [9/10] Extracting docs & git info...", file=sys.stderr)
    results["docs"] = get_docs(repo)
    results["git"] = get_git_info(repo)

    print("  [10/10] Detecting AI agent config...", file=sys.stderr)
    results["ai_agent_config"] = detect_ai_agent_config(repo)

    # Optional analyzers
    results["analyzers"] = {}
    repomix_detection = detect_repomix()
    results["analyzers_available"] = {
        "semgrep": tool_available("semgrep"),
        "ruff": tool_available("ruff"),
        "repomix": repomix_detection["available"],
    }

    if options.get("semgrep") or options.get("all"):
        print("  [+] Running semgrep...", file=sys.stderr)
        results["analyzers"]["semgrep"] = run_semgrep(repo)

    if options.get("ruff") or options.get("all"):
        if stack["primary_language"] == "python":
            print("  [+] Running ruff...", file=sys.stderr)
            results["analyzers"]["ruff"] = run_ruff(repo)

    if options.get("eslint") or options.get("all"):
        if stack["primary_language"] in ("javascript", "typescript"):
            print("  [+] Running eslint...", file=sys.stderr)
            results["analyzers"]["eslint"] = run_eslint(repo)

    # Dependency graph extraction
    if options.get("depgraph") or options.get("all"):
        print("  [+] Extracting dependency graph...", file=sys.stderr)
        results["dependency_graph"] = run_depgraph(repo, stack["primary_language"])

    # Repomix code packing (runs last — potentially slow)
    if options.get("repomix"):
        repomix_opts = {
            "repomix_style": options.get("repomix_style", "xml"),
            "repomix_compress": options.get("repomix_compress", True),
            "output_dir": str(Path(options.get("output_dir", str(repo.parent)))),
        }
        results["repomix"] = run_repomix(repo, repomix_opts)
    elif not repomix_detection["available"]:
        results["repomix"] = {
            "status": "not_requested",
            "note": "Use --repomix to pack codebase for LLM context. Install: npm install -g repomix",
        }

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Codebase probe: extract structured metadata for AI analysis"
    )
    parser.add_argument("repo", help="Path to the repository to analyze")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument(
        "--depth", type=int, default=3, help="Max directory tree depth (default: 3)"
    )
    parser.add_argument("--semgrep", action="store_true", help="Run semgrep analysis")
    parser.add_argument(
        "--ruff", action="store_true", help="Run ruff analysis (Python)"
    )
    parser.add_argument(
        "--eslint", action="store_true", help="Run eslint analysis (JS/TS)"
    )
    parser.add_argument(
        "--depgraph", action="store_true", help="Extract dependency/import graph"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all available analyzers (semgrep, ruff, eslint, depgraph)",
    )
    parser.add_argument(
        "--compact", action="store_true", help="Compact JSON output (no indentation)"
    )

    # Repomix options (separate from --all since it can be slow/large)
    repomix_group = parser.add_argument_group(
        "repomix", "Code packing via Repomix (requires npm/npx)"
    )
    repomix_group.add_argument(
        "--repomix",
        action="store_true",
        help="Pack codebase via Repomix for LLM analysis",
    )
    repomix_group.add_argument(
        "--repomix-style",
        default="xml",
        choices=["xml", "markdown", "json", "plain"],
        help="Repomix output format (default: xml)",
    )
    repomix_group.add_argument(
        "--repomix-compress",
        action="store_true",
        default=True,
        help="Enable Tree-sitter compression (default: on)",
    )
    repomix_group.add_argument(
        "--repomix-no-compress",
        action="store_true",
        help="Disable Tree-sitter compression",
    )
    repomix_group.add_argument(
        "--repomix-output-dir",
        help="Directory for repomix output (default: parent of repo)",
    )

    args = parser.parse_args()

    options = {
        "depth": args.depth,
        "semgrep": args.semgrep,
        "ruff": args.ruff,
        "eslint": args.eslint,
        "depgraph": args.depgraph,
        "all": args.all,
        "repomix": args.repomix,
        "repomix_style": args.repomix_style,
        "repomix_compress": not args.repomix_no_compress,
        "output_dir": args.repomix_output_dir or str(Path(args.repo).resolve().parent),
    }

    print(f"Probing: {args.repo}", file=sys.stderr)
    results = probe(args.repo, options)

    indent = None if args.compact else 2
    output = json.dumps(results, indent=indent, default=str)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Results written to: {args.output}", file=sys.stderr)
    else:
        print(output)

    # Print summary to stderr
    meta = results.get("_meta", {})
    stack_info = results.get("stack", {})
    stats = results.get("file_stats", {})
    repomix_info = results.get("repomix", {})
    depgraph_info = results.get("dependency_graph", {})

    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"  Probe Summary: {meta.get('repo_name', '?')}", file=sys.stderr)
    print(f"  Language: {stack_info.get('primary_language', '?')}", file=sys.stderr)
    print(f"  Files: {stats.get('total_files', '?')}", file=sys.stderr)
    if repomix_info.get("status") == "ok":
        est_tokens = repomix_info.get("estimated_tokens", 0)
        print(
            f"  Repomix: {est_tokens:,} est. tokens → {repomix_info['output_path']}",
            file=sys.stderr,
        )
    if depgraph_info:
        imp = depgraph_info.get("import_analysis", {})
        print(
            f"  Import graph: {imp.get('files_with_internal_imports', imp.get('files_with_imports', '?'))} files mapped",
            file=sys.stderr,
        )
    print(f"{'=' * 60}", file=sys.stderr)


if __name__ == "__main__":
    main()

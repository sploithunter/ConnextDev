#!/usr/bin/env python3
"""
Comprehensive Benchmark Runner - Runs all tasks across multiple models.

Supports:
- Sequential execution (default)
- Parallel execution with isolated workspaces (--parallel)
- Docker container isolation (--container) - for CI/CD
- Merging results from multiple runs (--merge)

Usage:
    # Run all tasks with default models
    python run_all_benchmarks.py
    
    # Parallel execution (isolated temp dirs for each worker)
    python run_all_benchmarks.py --parallel 4
    
    # With containers (most isolated)
    python run_all_benchmarks.py --container --parallel 4
    
    # Merge with previous results
    python run_all_benchmarks.py --merge latest
"""

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class TaskResult:
    """Result from running a single task."""
    task_id: str
    driver_model: str
    coder_model: str
    success: bool
    reason: str
    iterations: int
    tokens: int
    cost_usd: float
    time_seconds: float
    samples_matched: int
    samples_expected: int


@dataclass
class BenchmarkSuite:
    """Complete benchmark suite results."""
    start_time: str
    end_time: str
    total_time_seconds: float
    dev_mode: bool
    results: list[TaskResult] = field(default_factory=list)
    
    @property
    def total_tasks(self) -> int:
        return len(self.results)
    
    @property
    def passed_tasks(self) -> int:
        return sum(1 for r in self.results if r.success)
    
    @property
    def failed_tasks(self) -> int:
        return sum(1 for r in self.results if not r.success)
    
    @property
    def total_cost(self) -> float:
        return sum(r.cost_usd for r in self.results)
    
    @property
    def total_tokens(self) -> int:
        return sum(r.tokens for r in self.results)
    
    def summary(self) -> dict:
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_time_seconds": self.total_time_seconds,
            "dev_mode": self.dev_mode,
            "total_tasks": self.total_tasks,
            "passed": self.passed_tasks,
            "failed": self.failed_tasks,
            "pass_rate": f"{100 * self.passed_tasks / max(1, self.total_tasks):.1f}%",
            "total_cost_usd": round(self.total_cost, 4),
            "total_tokens": self.total_tokens,
            "results": [
                {
                    "task": r.task_id,
                    "model": f"{r.driver_model} / {r.coder_model}",
                    "driver_model": r.driver_model,
                    "coder_model": r.coder_model,
                    "success": r.success,
                    "cost": round(r.cost_usd, 4),
                    "time": round(r.time_seconds, 1),
                    "tokens": r.tokens,
                    "samples_matched": r.samples_matched,
                    "samples_expected": r.samples_expected,
                }
                for r in self.results
            ],
        }


# Dynamically discover tasks with solution.md (ready for testing)
def discover_available_tasks() -> list[str]:
    """Find all tasks that have solution.md files (ready for dev-mode testing)."""
    script_dir = Path(__file__).parent
    tasks_dir = script_dir / "tasks"
    
    available = []
    for task_dir in sorted(tasks_dir.iterdir()):
        if task_dir.is_dir() and (task_dir / "solution.md").exists():
            available.append(task_dir.name)
    
    return available


AVAILABLE_TASKS = discover_available_tasks() or [
    "L1-PY-01_hello_publisher",
    "L1-PY-02_hello_subscriber", 
    "LQ-01_late_joiner_durability",
]

# Shortened task IDs for convenience
TASK_ALIASES = {
    "L1-PY-01": "L1-PY-01_hello_publisher",
    "L1-PY-02": "L1-PY-02_hello_subscriber",
    "L3-PY-03": "L3-PY-03_full_loop_adapter",
    "LD-01": "LD-01_content_filtered_topic",
    "LD-03": "LD-03_rtiddsgen_workflow",
    "LD-07": "LD-07_discovery_guid_mining",
    "LN-CPP-01": "LN-CPP-01_native_cpp_publisher",
    "LQ-01": "LQ-01_late_joiner_durability",
    "LX-CPP-01": "LX-CPP-01_python_to_cpp_publisher",
}

# Default model configurations
DEFAULT_MODELS = [
    ("openai/gpt-4.1-mini", "openai/gpt-4.1-mini"),
]

# Quick test model
QUICK_MODEL = ("openai/gpt-4.1-nano", "openai/gpt-4.1-nano")

# High-end models
HIGH_END_MODELS = [
    ("openai/gpt-5.2", "openai/gpt-5.2"),
    ("anthropic/claude-opus-4-20250514", "anthropic/claude-opus-4-20250514"),
]


def create_isolated_workspace(task_id: str, worker_id: int) -> Path:
    """Create an isolated workspace for parallel execution."""
    workspace = Path(tempfile.mkdtemp(prefix=f"dds_bench_{worker_id}_"))
    script_dir = Path(__file__).parent
    
    # Copy task files
    task_dir = script_dir / "tasks" / task_id
    if task_dir.exists():
        dst = workspace / "task"
        shutil.copytree(task_dir, dst)
    
    return workspace


def run_single_task(
    task_id: str,
    driver_model: str,
    coder_model: str,
    dev_mode: bool = False,
    max_iterations: int = 10,
    timeout: int = 300,
    verbose: bool = False,
    workspace: Optional[Path] = None,
    use_container: bool = False,
    worker_id: int = 0,
) -> Optional[TaskResult]:
    """Run a single benchmark task."""
    
    script_dir = Path(__file__).parent
    runner_script = script_dir / "dual_agent_runner.py"
    
    # Resolve task alias
    full_task_id = TASK_ALIASES.get(task_id, task_id)
    
    # Set unique domain ID for parallel execution to avoid DDS conflicts
    env = os.environ.copy()
    if worker_id > 0:
        # Each worker gets a unique domain range
        base_domain = 85 + (worker_id * 10)
        env["DDS_BENCHMARK_DOMAIN_OFFSET"] = str(worker_id * 10)
    
    if use_container:
        # Docker-based isolation
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{script_dir}:/benchmark",
            "-e", f"OPENAI_API_KEY={os.environ.get('OPENAI_API_KEY', '')}",
            "-e", f"ANTHROPIC_API_KEY={os.environ.get('ANTHROPIC_API_KEY', '')}",
            "-e", f"OPENROUTER_API_KEY={os.environ.get('OPENROUTER_API_KEY', '')}",
            "dds-benchmark:latest",
            "python", "/benchmark/dual_agent_runner.py",
            "--task", full_task_id,
            "--driver", driver_model,
            "--coder", coder_model,
            "--max-iterations", str(max_iterations),
            "--timeout", str(timeout),
        ]
    else:
        cmd = [
            sys.executable,
            str(runner_script),
            "--task", full_task_id,
            "--driver", driver_model,
            "--coder", coder_model,
            "--max-iterations", str(max_iterations),
            "--timeout", str(timeout),
        ]
    
    if dev_mode:
        cmd.append("--dev-mode")
    if verbose:
        cmd.append("--verbose")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 60,
            cwd=str(workspace) if workspace else str(script_dir),
            env=env,
        )
        
        # Parse output for results
        output = result.stdout + result.stderr
        
        # Find the most recent result file
        results_dir = script_dir / "results" / "dual_agent"
        if results_dir.exists():
            pattern = f"{full_task_id}_{driver_model.replace('/', '_')}"
            matching = sorted(
                [f for f in results_dir.glob("*.json") if pattern in f.name],
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            
            if matching:
                with open(matching[0]) as f:
                    data = json.load(f)
                    return TaskResult(
                        task_id=data.get("task_id", full_task_id),
                        driver_model=data.get("driver_model", driver_model),
                        coder_model=data.get("coder_model", coder_model),
                        success=data.get("success", False),
                        reason=data.get("reason", "Unknown"),
                        iterations=data.get("total_iterations", 0),
                        tokens=data.get("total_tokens", 0),
                        cost_usd=data.get("total_cost_usd", 0.0),
                        time_seconds=data.get("time_seconds", 0.0),
                        samples_matched=data.get("samples_matched", 0),
                        samples_expected=data.get("samples_expected", 0),
                    )
        
        # Fallback: parse from output
        success = "PASSED" in output and "FAILED" not in output.split("PASSED")[-1]
        return TaskResult(
            task_id=full_task_id,
            driver_model=driver_model,
            coder_model=coder_model,
            success=success,
            reason="Parsed from output",
            iterations=0,
            tokens=0,
            cost_usd=0.0,
            time_seconds=0.0,
            samples_matched=0,
            samples_expected=0,
        )
        
    except subprocess.TimeoutExpired:
        return TaskResult(
            task_id=full_task_id,
            driver_model=driver_model,
            coder_model=coder_model,
            success=False,
            reason="Timeout",
            iterations=0,
            tokens=0,
            cost_usd=0.0,
            time_seconds=float(timeout),
            samples_matched=0,
            samples_expected=0,
        )
    except Exception as e:
        return TaskResult(
            task_id=full_task_id,
            driver_model=driver_model,
            coder_model=coder_model,
            success=False,
            reason=f"Error: {e}",
            iterations=0,
            tokens=0,
            cost_usd=0.0,
            time_seconds=0.0,
            samples_matched=0,
            samples_expected=0,
        )


def run_parallel_worker(args_tuple):
    """Worker function for parallel execution."""
    task_id, driver, coder, dev_mode, max_iter, timeout, verbose, container, worker_id = args_tuple
    
    print(f"  [Worker {worker_id}] Starting {task_id} with {driver}")
    result = run_single_task(
        task_id=task_id,
        driver_model=driver,
        coder_model=coder,
        dev_mode=dev_mode,
        max_iterations=max_iter,
        timeout=timeout,
        verbose=verbose,
        use_container=container,
        worker_id=worker_id,
    )
    
    status = "✓" if result and result.success else "✗"
    print(f"  [Worker {worker_id}] {status} Finished {task_id}")
    return result


def run_benchmark_suite(
    tasks: list[str],
    models: list[tuple[str, str]],
    dev_mode: bool = False,
    max_iterations: int = 10,
    timeout: int = 300,
    verbose: bool = False,
    parallel: int = 1,
    use_container: bool = False,
    existing_results: Optional[dict] = None,
) -> BenchmarkSuite:
    """Run complete benchmark suite."""
    
    start_time = datetime.now()
    suite = BenchmarkSuite(
        start_time=start_time.isoformat(),
        end_time="",
        total_time_seconds=0.0,
        dev_mode=dev_mode,
    )
    
    # Build list of jobs to run
    jobs = []
    skipped = 0
    
    # Check which task/model combos already exist
    existing_keys = set()
    if existing_results:
        for r in existing_results.get("results", []):
            key = (
                r.get("task", ""),
                r.get("driver_model", ""),
                r.get("coder_model", ""),
            )
            existing_keys.add(key)
    
    for driver, coder in models:
        for task_id in tasks:
            full_task_id = TASK_ALIASES.get(task_id, task_id)
            key = (full_task_id, driver, coder)
            
            if key in existing_keys:
                skipped += 1
                continue
            
            jobs.append((task_id, driver, coder))
    
    total_runs = len(jobs)
    
    print("=" * 70)
    print("DDS Agent Benchmark Suite")
    print(f"Tasks: {len(tasks)} | Models: {len(models)}")
    print(f"New jobs: {total_runs} | Skipped (already done): {skipped}")
    print(f"Parallel workers: {parallel} | Containers: {use_container}")
    print(f"Dev mode: {dev_mode}")
    print("=" * 70)
    
    if total_runs == 0:
        print("\n✅ All task/model combinations already completed!")
        end_time = datetime.now()
        suite.end_time = end_time.isoformat()
        suite.total_time_seconds = (end_time - start_time).total_seconds()
        return suite
    
    if parallel > 1:
        # Parallel execution
        print(f"\n🚀 Running {total_runs} jobs with {parallel} workers...")
        
        worker_args = [
            (task, driver, coder, dev_mode, max_iterations, timeout, 
             verbose, use_container, i % parallel)
            for i, (task, driver, coder) in enumerate(jobs)
        ]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as executor:
            results = list(executor.map(run_parallel_worker, worker_args))
            
        for result in results:
            if result:
                suite.results.append(result)
    else:
        # Sequential execution
        current = 0
        for task_id, driver, coder in jobs:
            current += 1
            model_name = driver if driver == coder else f"{driver}/{coder}"
            
            print(f"\n[{current}/{total_runs}] {task_id} | {model_name}")
            print("-" * 40)
            
            result = run_single_task(
                task_id=task_id,
                driver_model=driver,
                coder_model=coder,
                dev_mode=dev_mode,
                max_iterations=max_iterations,
                timeout=timeout,
                verbose=verbose,
                use_container=use_container,
            )
            
            if result:
                suite.results.append(result)
                status = "✓ PASSED" if result.success else "✗ FAILED"
                print(f"  {status}: {result.reason}")
                print(f"  Cost: ${result.cost_usd:.4f} | "
                      f"Tokens: {result.tokens:,} | "
                      f"Time: {result.time_seconds:.1f}s")
    
    end_time = datetime.now()
    suite.end_time = end_time.isoformat()
    suite.total_time_seconds = (end_time - start_time).total_seconds()
    
    return suite


def print_summary(suite: BenchmarkSuite):
    """Print final summary."""
    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)
    
    print(f"\nTotal tasks: {suite.total_tasks}")
    print(f"Passed: {suite.passed_tasks} ({100*suite.passed_tasks/max(1,suite.total_tasks):.1f}%)")
    print(f"Failed: {suite.failed_tasks}")
    print(f"\nTotal cost: ${suite.total_cost:.4f}")
    print(f"Total tokens: {suite.total_tokens:,}")
    print(f"Total time: {suite.total_time_seconds:.1f}s ({suite.total_time_seconds/60:.1f}m)")
    
    print("\nResults by task:")
    print("-" * 70)
    for r in suite.results:
        status = "✓" if r.success else "✗"
        print(f"  {status} {r.task_id:20s} | {r.driver_model:30s} | ${r.cost_usd:.4f}")
    
    if suite.failed_tasks > 0:
        print("\nFailed tasks:")
        for r in suite.results:
            if not r.success:
                print(f"  - {r.task_id}: {r.reason}")


def load_previous_results(filepath: Path) -> Optional[dict]:
    """Load previous results for merging."""
    if not filepath.exists():
        return None
    try:
        with open(filepath) as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load {filepath}: {e}")
        return None


def merge_results(new_data: dict, previous_data: dict) -> dict:
    """Merge new results with previous results."""
    # Create lookup for new results by full key
    new_lookup = {}
    for r in new_data.get("results", []):
        key = (r.get("task", ""), r.get("driver_model", ""), r.get("coder_model", ""))
        new_lookup[key] = r
    
    # Start with new results
    merged = list(new_data.get("results", []))
    
    # Add previous results that weren't in new run
    preserved = 0
    for r in previous_data.get("results", []):
        key = (r.get("task", ""), r.get("driver_model", ""), r.get("coder_model", ""))
        if key not in new_lookup:
            merged.append(r)
            preserved += 1
    
    # Recalculate totals
    passed = sum(1 for r in merged if r.get("success"))
    total_cost = sum(r.get("cost", 0) for r in merged)
    total_tokens = sum(r.get("tokens", 0) for r in merged)
    
    result = {
        "start_time": previous_data.get("start_time", new_data.get("start_time")),
        "end_time": new_data.get("end_time"),
        "total_time_seconds": (
            previous_data.get("total_time_seconds", 0) + 
            new_data.get("total_time_seconds", 0)
        ),
        "dev_mode": new_data.get("dev_mode", False),
        "total_tasks": len(merged),
        "passed": passed,
        "failed": len(merged) - passed,
        "pass_rate": f"{100 * passed / max(1, len(merged)):.1f}%",
        "total_cost_usd": round(total_cost, 4),
        "total_tokens": total_tokens,
        "results": merged,
        "merge_info": {
            "new_results": len(new_data.get("results", [])),
            "preserved_results": preserved,
            "merged_at": datetime.now().isoformat(),
        }
    }
    
    print(f"\n📎 Merged: {len(new_data.get('results',[]))} new + {preserved} preserved = {len(merged)} total")
    return result


def save_results(suite: BenchmarkSuite, output_dir: Path, 
                 merge_with: Optional[Path] = None) -> Path:
    """Save results to JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    new_data = suite.summary()
    
    if merge_with:
        previous = load_previous_results(merge_with)
        if previous:
            new_data = merge_results(new_data, previous)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"suite_results_{timestamp}.json"
    filepath = output_dir / filename
    
    with open(filepath, "w") as f:
        json.dump(new_data, f, indent=2)
    
    latest = output_dir / "suite_results_latest.json"
    with open(latest, "w") as f:
        json.dump(new_data, f, indent=2)
    
    print(f"\nResults saved: {filepath}")
    print(f"Latest: {latest}")
    return filepath


def main():
    parser = argparse.ArgumentParser(
        description="Run DDS Agent Benchmark Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument("--tasks", "-t", nargs="+", 
                        default=list(TASK_ALIASES.keys()),
                        help="Tasks to run (e.g., L1-PY-01 LQ-01)")
    parser.add_argument("--models", "-m", nargs="+",
                        help="Models to test")
    parser.add_argument("--models-file", type=str,
                        help="Load models from file")
    parser.add_argument("--dev-mode", action="store_true",
                        help="Test harness with solution hints")
    parser.add_argument("--quick", action="store_true",
                        help="Quick test with nano model")
    parser.add_argument("--high-end", action="store_true",
                        help="Test with high-end models")
    parser.add_argument("--max-iterations", "-n", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--parallel", "-p", type=int, default=1,
                        help="Number of parallel workers (WARNING: DDS domain conflicts possible)")
    parser.add_argument("--container", action="store_true",
                        help="Use Docker containers for isolation")
    parser.add_argument("--merge", type=str,
                        help="Merge with previous results ('latest' or file path)")
    parser.add_argument("--output", "-o", type=str, default="results/suites")
    parser.add_argument("--verbose", "-v", action="store_true")
    
    args = parser.parse_args()
    script_dir = Path(__file__).parent
    
    # Load models
    if args.models_file:
        mfile = Path(args.models_file)
        if mfile.exists():
            with open(mfile) as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
                models = [(m, m) for m in lines]
            print(f"📋 Loaded {len(models)} models from {mfile}")
        else:
            print(f"❌ Models file not found: {mfile}")
            return 1
    elif args.quick:
        models = [QUICK_MODEL]
    elif args.high_end:
        models = HIGH_END_MODELS
    elif args.models:
        models = [(m, m) for m in args.models]
    else:
        models = DEFAULT_MODELS
    
    # Handle merge
    existing_results = None
    merge_path = None
    if args.merge:
        if args.merge.lower() == "latest":
            merge_path = script_dir / args.output / "suite_results_latest.json"
        else:
            merge_path = Path(args.merge)
        
        if merge_path.exists():
            existing_results = load_previous_results(merge_path)
            if existing_results:
                print(f"📎 Merging with: {merge_path}")
                print(f"   Previous results: {len(existing_results.get('results', []))}")
    
    # Run suite
    suite = run_benchmark_suite(
        tasks=args.tasks,
        models=models,
        dev_mode=args.dev_mode,
        max_iterations=args.max_iterations,
        timeout=args.timeout,
        verbose=args.verbose,
        parallel=args.parallel,
        use_container=args.container,
        existing_results=existing_results,
    )
    
    print_summary(suite)
    save_results(suite, script_dir / args.output, merge_with=merge_path)
    
    return 0 if suite.failed_tasks == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

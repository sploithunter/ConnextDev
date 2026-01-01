#!/usr/bin/env python3
"""
Comprehensive Benchmark Runner - Runs all tasks across multiple models.

Usage:
    # Run all tasks with default models
    python run_all_benchmarks.py
    
    # Run specific tasks
    python run_all_benchmarks.py --tasks L1-PY-01 L1-PY-02
    
    # Run with specific models
    python run_all_benchmarks.py --models openai/gpt-4.1-mini anthropic/claude-sonnet-4
    
    # Dev mode (tests harness, not models)
    python run_all_benchmarks.py --dev-mode
    
    # Quick smoke test
    python run_all_benchmarks.py --quick
"""

import argparse
import json
import os
import subprocess
import sys
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
                    "success": r.success,
                    "cost": round(r.cost_usd, 4),
                    "time": round(r.time_seconds, 1),
                }
                for r in self.results
            ],
        }


# Available tasks (those with test scripts)
AVAILABLE_TASKS = [
    "L1-PY-01",  # Hello Publisher
    "L1-PY-02",  # Hello Subscriber
    "LQ-01",     # Late Joiner Durability
]

# Default model configurations
DEFAULT_MODELS = [
    ("openai/gpt-4.1-mini", "openai/gpt-4.1-mini"),  # Fast, cheap
]

# Quick test model (for smoke tests)
QUICK_MODEL = ("openai/gpt-4.1-nano", "openai/gpt-4.1-nano")

# High-end models for serious evaluation
HIGH_END_MODELS = [
    ("openai/gpt-5.2", "openai/gpt-5.2"),
    ("anthropic/claude-opus-4-20250514", "anthropic/claude-opus-4-20250514"),
    ("openrouter/x-ai/grok-3-beta", "openrouter/x-ai/grok-3-beta"),
]


def run_single_task(
    task_id: str,
    driver_model: str,
    coder_model: str,
    dev_mode: bool = False,
    max_iterations: int = 10,
    timeout: int = 300,
    verbose: bool = False,
) -> Optional[TaskResult]:
    """Run a single benchmark task."""
    
    script_dir = Path(__file__).parent
    runner_script = script_dir / "dual_agent_runner.py"
    
    cmd = [
        sys.executable,
        str(runner_script),
        "--task", task_id,
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
            timeout=timeout + 60,  # Extra buffer
            cwd=str(script_dir),
        )
        
        # Parse output for results
        output = result.stdout + result.stderr
        
        # Try to find the result JSON file
        results_dir = script_dir / "results" / "dual_agent"
        if results_dir.exists():
            # Find most recent result for this task/model combo
            pattern = f"{task_id}_{driver_model.replace('/', '_')}"
            matching = sorted(
                [f for f in results_dir.glob("*.json") if pattern in f.name],
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            
            if matching:
                with open(matching[0]) as f:
                    data = json.load(f)
                    return TaskResult(
                        task_id=data.get("task_id", task_id),
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
            task_id=task_id,
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
            task_id=task_id,
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
            task_id=task_id,
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


def run_benchmark_suite(
    tasks: list[str],
    models: list[tuple[str, str]],
    dev_mode: bool = False,
    max_iterations: int = 10,
    timeout: int = 300,
    verbose: bool = False,
) -> BenchmarkSuite:
    """Run complete benchmark suite."""
    
    start_time = datetime.now()
    suite = BenchmarkSuite(
        start_time=start_time.isoformat(),
        end_time="",
        total_time_seconds=0.0,
        dev_mode=dev_mode,
    )
    
    total_runs = len(tasks) * len(models)
    current = 0
    
    print("=" * 70)
    print(f"DDS Agent Benchmark Suite")
    print(f"Tasks: {len(tasks)} | Models: {len(models)} | Total runs: {total_runs}")
    print(f"Dev mode: {dev_mode}")
    print("=" * 70)
    
    for driver, coder in models:
        model_name = driver if driver == coder else f"{driver}/{coder}"
        print(f"\n{'='*70}")
        print(f"Model: {model_name}")
        print("=" * 70)
        
        for task_id in tasks:
            current += 1
            print(f"\n[{current}/{total_runs}] Task: {task_id}")
            print("-" * 40)
            
            result = run_single_task(
                task_id=task_id,
                driver_model=driver,
                coder_model=coder,
                dev_mode=dev_mode,
                max_iterations=max_iterations,
                timeout=timeout,
                verbose=verbose,
            )
            
            if result:
                suite.results.append(result)
                status = "✓ PASSED" if result.success else "✗ FAILED"
                print(f"  {status}: {result.reason}")
                print(f"  Cost: ${result.cost_usd:.4f} | "
                      f"Tokens: {result.tokens:,} | "
                      f"Time: {result.time_seconds:.1f}s")
            else:
                print("  ✗ ERROR: No result returned")
    
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
    """Merge new results with previous results.
    
    New results for same task+model combinations replace old ones.
    Old results for task+model combos not in new run are preserved.
    """
    # Create lookup for new results
    new_results_lookup = {}
    for r in new_data.get("results", []):
        key = (r.get("task", ""), r.get("model", ""))
        new_results_lookup[key] = r
    
    # Start with new results
    merged_results = list(new_data.get("results", []))
    
    # Add old results that weren't re-tested
    preserved_count = 0
    for r in previous_data.get("results", []):
        key = (r.get("task", ""), r.get("model", ""))
        if key not in new_results_lookup:
            merged_results.append(r)
            preserved_count += 1
    
    # Recalculate totals
    passed = sum(1 for r in merged_results if r.get("success"))
    failed = sum(1 for r in merged_results if not r.get("success"))
    total_cost = sum(r.get("cost", 0) for r in merged_results)
    total_tokens = sum(r.get("tokens", 0) for r in merged_results)
    
    merged = {
        "start_time": previous_data.get("start_time", new_data.get("start_time")),
        "end_time": new_data.get("end_time"),
        "total_time_seconds": (
            previous_data.get("total_time_seconds", 0) + 
            new_data.get("total_time_seconds", 0)
        ),
        "dev_mode": new_data.get("dev_mode", False),
        "total_tasks": len(merged_results),
        "passed": passed,
        "failed": failed,
        "pass_rate": f"{100 * passed / max(1, len(merged_results)):.1f}%",
        "total_cost_usd": round(total_cost, 4),
        "total_tokens": total_tokens,
        "results": merged_results,
        "merge_info": {
            "new_results": len(new_data.get("results", [])),
            "preserved_results": preserved_count,
            "merged_at": datetime.now().isoformat(),
        }
    }
    
    print(f"\n📎 Merged results: {len(new_data.get('results', []))} new + "
          f"{preserved_count} preserved = {len(merged_results)} total")
    
    return merged


def save_results(suite: BenchmarkSuite, output_dir: Path, 
                 merge_with: Optional[Path] = None) -> Path:
    """Save results to JSON file, optionally merging with previous."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    new_data = suite.summary()
    
    # Merge if requested
    if merge_with:
        previous_data = load_previous_results(merge_with)
        if previous_data:
            new_data = merge_results(new_data, previous_data)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"suite_results_{timestamp}.json"
    filepath = output_dir / filename
    
    with open(filepath, "w") as f:
        json.dump(new_data, f, indent=2)
    
    # Also save as "latest" for easy access
    latest_path = output_dir / "suite_results_latest.json"
    with open(latest_path, "w") as f:
        json.dump(new_data, f, indent=2)
    
    print(f"\nResults saved: {filepath}")
    print(f"Latest link: {latest_path}")
    return filepath


def main():
    parser = argparse.ArgumentParser(
        description="Run DDS Agent Benchmark Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all tasks with default model
  python run_all_benchmarks.py
  
  # Quick smoke test (nano model, fast)
  python run_all_benchmarks.py --quick
  
  # Dev mode (test harness, not models)
  python run_all_benchmarks.py --dev-mode
  
  # Specific tasks
  python run_all_benchmarks.py --tasks L1-PY-01 LQ-01
  
  # Custom models
  python run_all_benchmarks.py --models openai/gpt-5.2 anthropic/claude-opus-4
  
  # High-end evaluation
  python run_all_benchmarks.py --high-end
        """
    )
    
    parser.add_argument("--tasks", "-t", nargs="+", 
                        choices=AVAILABLE_TASKS,
                        default=AVAILABLE_TASKS,
                        help="Tasks to run")
    parser.add_argument("--models", "-m", nargs="+",
                        help="Models to test (driver=coder)")
    parser.add_argument("--driver", type=str,
                        help="Driver model (if different from coder)")
    parser.add_argument("--coder", type=str,
                        help="Coder model (if different from driver)")
    parser.add_argument("--dev-mode", action="store_true",
                        help="Enable dev mode (tests harness)")
    parser.add_argument("--quick", action="store_true",
                        help="Quick smoke test with nano model")
    parser.add_argument("--high-end", action="store_true",
                        help="Test with high-end models")
    parser.add_argument("--max-iterations", "-n", type=int, default=10,
                        help="Max iterations per task")
    parser.add_argument("--timeout", type=int, default=300,
                        help="Timeout per task in seconds")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--output", "-o", type=str,
                        default="results/suites",
                        help="Output directory for results")
    parser.add_argument("--merge", type=str,
                        help="Merge with previous results file (or 'latest' for most recent)")
    parser.add_argument("--models-file", type=str,
                        help="Load model list from file (one per line)")
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    
    # Load models from file if specified
    if args.models_file:
        models_file = Path(args.models_file)
        if models_file.exists():
            with open(models_file) as f:
                model_lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
                models = [(m, m) for m in model_lines]
            print(f"📋 Loaded {len(models)} models from {models_file}")
        else:
            print(f"❌ Models file not found: {models_file}")
            return 1
    # Determine models to use
    elif args.quick:
        models = [QUICK_MODEL]
    elif args.high_end:
        models = HIGH_END_MODELS
    elif args.models:
        models = [(m, m) for m in args.models]
    elif args.driver and args.coder:
        models = [(args.driver, args.coder)]
    else:
        models = DEFAULT_MODELS
    
    # Determine merge file
    merge_path = None
    if args.merge:
        if args.merge.lower() == "latest":
            merge_path = script_dir / args.output / "suite_results_latest.json"
        else:
            merge_path = Path(args.merge)
        
        if merge_path.exists():
            print(f"📎 Will merge with: {merge_path}")
        else:
            print(f"⚠ Merge file not found, will create new: {merge_path}")
            merge_path = None
    
    # Run benchmark
    suite = run_benchmark_suite(
        tasks=args.tasks,
        models=models,
        dev_mode=args.dev_mode,
        max_iterations=args.max_iterations,
        timeout=args.timeout,
        verbose=args.verbose,
    )
    
    # Print and save results
    print_summary(suite)
    
    save_results(suite, script_dir / args.output, merge_with=merge_path)
    
    # Return non-zero if any failures
    return 0 if suite.failed_tasks == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


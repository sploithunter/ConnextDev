#!/usr/bin/env python3
"""DDS Benchmark Harness - Evaluates AI models on DDS programming tasks.

Uses Aider CLI to run models against DDS programming challenges,
with deterministic verification using reference implementations.

Usage:
    python benchmark_runner.py --task L1-PY-01 --model gpt-4o
    python benchmark_runner.py --task L1-PY-01 --model claude-sonnet-4-20250514
"""

import argparse
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

import yaml


@dataclass
class TaskConfig:
    """Configuration for a benchmark task."""
    task_id: str
    name: str
    target_file: str
    domain_id: int
    sample_count: int
    timeout_seconds: int
    reference_subscriber: str
    expected_output: str
    prompt_file: str
    task_dir: Path


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""
    task_id: str
    model: str
    success: bool
    reason: str = ""
    time_seconds: float = 0.0
    aider_iterations: int = 0
    samples_matched: int = 0
    samples_expected: int = 0
    checkpoints: dict = field(default_factory=dict)
    error_log: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class BenchmarkRunner:
    """Runs DDS benchmark tasks against AI models."""
    
    def __init__(self, benchmark_dir: Path, verbose: bool = False):
        self.benchmark_dir = benchmark_dir
        self.verbose = verbose
        self.config = self._load_config()
        
    def _load_config(self) -> dict:
        """Load benchmark configuration."""
        config_path = self.benchmark_dir / "config.yaml"
        with open(config_path) as f:
            return yaml.safe_load(f)
    
    def _load_task(self, task_id: str) -> TaskConfig:
        """Load task configuration."""
        # Find task directory
        tasks_dir = self.benchmark_dir / "tasks"
        task_dirs = list(tasks_dir.glob(f"*{task_id}*"))
        
        if not task_dirs:
            raise ValueError(f"Task {task_id} not found in {tasks_dir}")
        
        task_dir = task_dirs[0]
        task_yaml = task_dir / "task.yaml"
        
        with open(task_yaml) as f:
            task_config = yaml.safe_load(f)
        
        return TaskConfig(
            task_id=task_config["task_id"],
            name=task_config["name"],
            target_file=task_config["target_file"],
            domain_id=task_config["requirements"]["domain_id"],
            sample_count=task_config["requirements"]["sample_count"],
            timeout_seconds=task_config["timeout_seconds"],
            reference_subscriber=str(task_dir / task_config["verification"]["reference_subscriber"]),
            expected_output=str(task_dir / task_config["verification"]["expected_output"]),
            prompt_file=str(task_dir / "prompt.md"),
            task_dir=task_dir,
        )
    
    def _setup_workspace(self, task: TaskConfig) -> Path:
        """Create isolated workspace for benchmark run."""
        workspace = Path(tempfile.mkdtemp(prefix=f"dds_bench_{task.task_id}_"))
        
        # Copy starter files if any
        starter_dir = task.task_dir / "starter"
        if starter_dir.exists():
            for f in starter_dir.iterdir():
                if f.is_file():
                    shutil.copy(f, workspace)
        
        if self.verbose:
            print(f"Workspace: {workspace}", file=sys.stderr)
        
        return workspace
    
    def _run_aider(
        self,
        workspace: Path,
        model: str,
        prompt: str,
        timeout: int,
    ) -> tuple[bool, str, int]:
        """Run Aider to generate code.
        
        Returns: (success, output, iterations)
        """
        cmd = [
            "aider",
            "--model", model,
            "--yes",  # Non-interactive
            "--no-git",  # Don't use git in workspace
            "--no-pretty",  # Clean output
            "--message", prompt,
        ]
        
        if self.verbose:
            print(f"Running: {' '.join(cmd[:6])}...", file=sys.stderr)
        
        try:
            result = subprocess.run(
                cmd,
                cwd=workspace,
                timeout=timeout,
                capture_output=True,
                text=True,
            )
            
            # Count iterations (rough estimate from output)
            iterations = result.stdout.count("Applied edit")
            
            return result.returncode == 0, result.stdout + result.stderr, iterations
            
        except subprocess.TimeoutExpired:
            return False, "Aider timed out", 0
        except Exception as e:
            return False, str(e), 0
    
    def _run_verification(
        self,
        workspace: Path,
        task: TaskConfig,
    ) -> tuple[bool, int, int, str]:
        """Run the generated publisher against reference subscriber.
        
        Returns: (success, matched, expected, error_log)
        """
        publisher_path = workspace / task.target_file
        
        if not publisher_path.exists():
            return False, 0, task.sample_count, "Publisher file not created"
        
        # Create output file for subscriber
        output_file = workspace / "actual_output.jsonl"
        
        try:
            # Start reference subscriber first
            sub_cmd = [
                "python", task.reference_subscriber,
                "--domain", str(task.domain_id),
                "--count", str(task.sample_count),
                "--timeout", "20",
                "--output", str(output_file),
            ]
            
            if self.verbose:
                print(f"Starting subscriber...", file=sys.stderr)
            
            sub_proc = subprocess.Popen(
                sub_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            
            # Wait for subscriber to start
            time.sleep(2)
            
            # Run the generated publisher
            pub_cmd = ["python", str(publisher_path)]
            
            if self.verbose:
                print(f"Running publisher...", file=sys.stderr)
            
            pub_result = subprocess.run(
                pub_cmd,
                cwd=workspace,
                timeout=30,
                capture_output=True,
                text=True,
            )
            
            # Wait for subscriber to complete
            try:
                sub_stdout, sub_stderr = sub_proc.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                sub_proc.kill()
                sub_stdout, sub_stderr = sub_proc.communicate()
            
            if pub_result.returncode != 0:
                return False, 0, task.sample_count, f"Publisher failed: {pub_result.stderr}"
            
            # Compare output using dds-sample-compare
            if not output_file.exists():
                return False, 0, task.sample_count, "No samples received"
            
            compare_cmd = [
                "dds-sample-compare",
                "--expected", task.expected_output,
                "--actual", str(output_file),
            ]
            
            compare_result = subprocess.run(
                compare_cmd,
                capture_output=True,
                text=True,
            )
            
            # Parse comparison results
            if compare_result.returncode == 0:
                # Extract matched count from output
                matched = task.sample_count
                return True, matched, task.sample_count, ""
            else:
                # Try to parse how many matched
                output = compare_result.stdout
                matched = 0
                for line in output.split("\n"):
                    if "Matched samples:" in line:
                        try:
                            matched = int(line.split(":")[-1].strip())
                        except ValueError:
                            pass
                
                return False, matched, task.sample_count, compare_result.stdout
                
        except subprocess.TimeoutExpired:
            return False, 0, task.sample_count, "Verification timed out"
        except Exception as e:
            return False, 0, task.sample_count, str(e)
    
    def run_benchmark(self, task_id: str, model: str) -> BenchmarkResult:
        """Run a complete benchmark.
        
        Returns BenchmarkResult with all metrics.
        """
        print(f"\n{'='*60}")
        print(f"Benchmark: {task_id} | Model: {model}")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        # Load task
        try:
            task = self._load_task(task_id)
        except Exception as e:
            return BenchmarkResult(
                task_id=task_id,
                model=model,
                success=False,
                reason=f"Failed to load task: {e}",
            )
        
        print(f"Task: {task.name}")
        
        # Setup workspace
        workspace = self._setup_workspace(task)
        
        # Load prompt
        with open(task.prompt_file) as f:
            prompt = f.read()
        
        # Run Aider
        print(f"\nPhase 1: Code Generation (Aider + {model})")
        aider_success, aider_output, iterations = self._run_aider(
            workspace, model, prompt, task.timeout_seconds
        )
        
        if self.verbose:
            print(f"Aider output:\n{aider_output[:1000]}...", file=sys.stderr)
        
        if not aider_success:
            return BenchmarkResult(
                task_id=task_id,
                model=model,
                success=False,
                reason="Aider failed to generate code",
                time_seconds=time.time() - start_time,
                aider_iterations=iterations,
                error_log=aider_output,
            )
        
        print(f"  Code generated ({iterations} edits)")
        
        # Verify the generated publisher exists
        publisher_file = workspace / task.target_file
        if not publisher_file.exists():
            return BenchmarkResult(
                task_id=task_id,
                model=model,
                success=False,
                reason=f"Target file {task.target_file} not created",
                time_seconds=time.time() - start_time,
                aider_iterations=iterations,
            )
        
        # Run verification
        print(f"\nPhase 2: Verification (Reference Subscriber)")
        verify_success, matched, expected, error_log = self._run_verification(
            workspace, task
        )
        
        elapsed = time.time() - start_time
        
        result = BenchmarkResult(
            task_id=task_id,
            model=model,
            success=verify_success,
            reason="All samples matched" if verify_success else f"Matched {matched}/{expected}",
            time_seconds=elapsed,
            aider_iterations=iterations,
            samples_matched=matched,
            samples_expected=expected,
            error_log=error_log,
        )
        
        # Print result
        status = "✓ PASSED" if verify_success else "✗ FAILED"
        print(f"\n{status}")
        print(f"  Samples: {matched}/{expected}")
        print(f"  Time: {elapsed:.1f}s")
        print(f"  Aider iterations: {iterations}")
        
        # Save result
        self._save_result(result, workspace)
        
        # Cleanup (optionally keep for debugging)
        if verify_success:
            shutil.rmtree(workspace)
        else:
            print(f"  Workspace kept for debugging: {workspace}")
        
        return result
    
    def _save_result(self, result: BenchmarkResult, workspace: Path):
        """Save benchmark result to results directory."""
        results_dir = self.benchmark_dir / "results" / result.model
        results_dir.mkdir(parents=True, exist_ok=True)
        
        result_file = results_dir / f"{result.task_id}_{result.timestamp.replace(':', '-')}.json"
        
        with open(result_file, "w") as f:
            json.dump(result.__dict__, f, indent=2)
        
        if self.verbose:
            print(f"Result saved: {result_file}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="DDS Benchmark Runner")
    parser.add_argument("--task", "-t", required=True,
                        help="Task ID (e.g., L1-PY-01)")
    parser.add_argument("--model", "-m", required=True,
                        help="Model name (e.g., gpt-4o, claude-sonnet-4-20250514)")
    parser.add_argument("--benchmark-dir", "-d", default=None,
                        help="Benchmark directory (default: auto-detect)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")
    
    args = parser.parse_args()
    
    # Find benchmark directory
    if args.benchmark_dir:
        benchmark_dir = Path(args.benchmark_dir)
    else:
        # Auto-detect: look for config.yaml
        for candidate in [
            Path(__file__).parent,
            Path.cwd() / "benchmark",
            Path.cwd(),
        ]:
            if (candidate / "config.yaml").exists():
                benchmark_dir = candidate
                break
        else:
            print("ERROR: Could not find benchmark directory", file=sys.stderr)
            sys.exit(1)
    
    runner = BenchmarkRunner(benchmark_dir, verbose=args.verbose)
    result = runner.run_benchmark(args.task, args.model)
    
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()


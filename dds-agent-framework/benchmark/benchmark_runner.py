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
class RubricScores:
    """Rubric evaluation scores."""
    prompt_following: int = 0
    code_style: int = 0
    correctness: int = 0
    dds_best_practices: int = 0
    error_handling: int = 0
    overall: float = 0.0
    max_score: int = 25
    summary: str = ""


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
    # Rubric evaluation (optional)
    rubric_scores: Optional[RubricScores] = None
    rubric_evaluator: str = ""
    generated_code: str = ""


class BenchmarkRunner:
    """Runs DDS benchmark tasks against AI models."""
    
    # Models to use for rubric evaluation
    RUBRIC_EVALUATORS = [
        "anthropic/claude-opus-4-5",
        "openai/gpt-5.2",
    ]
    
    def __init__(
        self,
        benchmark_dir: Path,
        verbose: bool = False,
        run_rubric: bool = False,
        rubric_evaluator: str = "anthropic/claude-opus-4-5",
    ):
        self.benchmark_dir = benchmark_dir
        self.verbose = verbose
        self.run_rubric = run_rubric
        self.rubric_evaluator = rubric_evaluator
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
        
        # Read generated code for rubric evaluation
        generated_code = ""
        if publisher_file.exists():
            generated_code = publisher_file.read_text()
        
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
            generated_code=generated_code,
        )
        
        # Run rubric evaluation if enabled
        if self.run_rubric and generated_code:
            print(f"\nPhase 3: Rubric Evaluation ({self.rubric_evaluator})")
            rubric_scores = self._run_rubric_evaluation(generated_code, task)
            if rubric_scores:
                result.rubric_scores = rubric_scores
                result.rubric_evaluator = self.rubric_evaluator
                print(f"  Rubric Score: {rubric_scores.overall}/{rubric_scores.max_score} ({rubric_scores.overall/rubric_scores.max_score*100:.0f}%)")
                print(f"    Prompt Following: {rubric_scores.prompt_following}/5")
                print(f"    Code Style: {rubric_scores.code_style}/5")
                print(f"    Correctness: {rubric_scores.correctness}/5")
                print(f"    DDS Best Practices: {rubric_scores.dds_best_practices}/5")
                print(f"    Error Handling: {rubric_scores.error_handling}/5")
        
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
    
    def _run_rubric_evaluation(
        self,
        code: str,
        task: TaskConfig,
    ) -> Optional[RubricScores]:
        """Run rubric evaluation on generated code.
        
        Returns RubricScores or None if evaluation fails.
        """
        try:
            # Import from same directory
            import sys
            sys.path.insert(0, str(self.benchmark_dir))
            from rubric_evaluator import RubricEvaluator
            
            evaluator = RubricEvaluator(self.rubric_evaluator)
            
            with open(task.prompt_file) as f:
                task_prompt = f.read()
            
            task_type = "publisher" if "publisher" in task.name.lower() else "subscriber"
            
            evaluation = evaluator.evaluate(
                code=code,
                task_prompt=task_prompt,
                task_type=task_type,
                task_id=task.task_id,
            )
            
            # Convert to RubricScores
            scores = RubricScores(summary=evaluation.summary)
            scores.overall = evaluation.overall_score
            scores.max_score = int(evaluation.max_overall)
            
            for s in evaluation.scores:
                dim = s.dimension.lower().replace(" ", "_")
                if "prompt" in dim:
                    scores.prompt_following = s.score
                elif "style" in dim:
                    scores.code_style = s.score
                elif "correct" in dim:
                    scores.correctness = s.score
                elif "dds" in dim or "practice" in dim:
                    scores.dds_best_practices = s.score
                elif "error" in dim:
                    scores.error_handling = s.score
            
            return scores
            
        except Exception as e:
            if self.verbose:
                print(f"Rubric evaluation failed: {e}", file=sys.stderr)
            return None
    
    def _save_result(self, result: BenchmarkResult, workspace: Path):
        """Save benchmark result to results directory."""
        results_dir = self.benchmark_dir / "results" / result.model
        results_dir.mkdir(parents=True, exist_ok=True)
        
        result_file = results_dir / f"{result.task_id}_{result.timestamp.replace(':', '-')}.json"
        
        # Convert result to dict, handling Optional fields
        result_dict = {
            "task_id": result.task_id,
            "model": result.model,
            "success": result.success,
            "reason": result.reason,
            "time_seconds": result.time_seconds,
            "aider_iterations": result.aider_iterations,
            "samples_matched": result.samples_matched,
            "samples_expected": result.samples_expected,
            "checkpoints": result.checkpoints,
            "error_log": result.error_log,
            "timestamp": result.timestamp,
            "rubric_evaluator": result.rubric_evaluator,
        }
        
        if result.rubric_scores:
            result_dict["rubric_scores"] = {
                "prompt_following": result.rubric_scores.prompt_following,
                "code_style": result.rubric_scores.code_style,
                "correctness": result.rubric_scores.correctness,
                "dds_best_practices": result.rubric_scores.dds_best_practices,
                "error_handling": result.rubric_scores.error_handling,
                "overall": result.rubric_scores.overall,
                "max_score": result.rubric_scores.max_score,
                "summary": result.rubric_scores.summary,
            }
        
        with open(result_file, "w") as f:
            json.dump(result_dict, f, indent=2)
        
        if self.verbose:
            print(f"Result saved: {result_file}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="DDS Benchmark Runner")
    parser.add_argument("--task", "-t", required=True,
                        help="Task ID (e.g., L1-PY-01)")
    parser.add_argument("--model", "-m", required=True,
                        help="Model name (e.g., openai/gpt-5.2, anthropic/claude-opus-4-5)")
    parser.add_argument("--benchmark-dir", "-d", default=None,
                        help="Benchmark directory (default: auto-detect)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")
    parser.add_argument("--rubric", "-r", action="store_true",
                        help="Run rubric evaluation on generated code")
    parser.add_argument("--rubric-evaluator", "-e", 
                        default="anthropic/claude-opus-4-5",
                        help="Model to use for rubric evaluation")
    
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
    
    runner = BenchmarkRunner(
        benchmark_dir,
        verbose=args.verbose,
        run_rubric=args.rubric,
        rubric_evaluator=args.rubric_evaluator,
    )
    result = runner.run_benchmark(args.task, args.model)
    
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()


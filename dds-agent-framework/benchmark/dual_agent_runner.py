#!/usr/bin/env python3
"""Dual-Agent Benchmark Runner - Driver + Coder Architecture.

Architecture:
┌─────────────────┐         ┌─────────────────────┐
│  Driver Agent   │         │    Coding Agent     │
│  (Heavy Model)  │◄───────►│    (via Aider)      │
│                 │         │                     │
│  - Reviews code │  chat   │  - Writes code      │
│  - Suggests fix │◄───────►│  - Runs tests       │
│  - Decides next │         │  - Applies edits    │
└─────────────────┘         └─────────────────────┘

The Driver acts as a senior developer guiding the Coder.
Fully automated - no human intervention.

Usage:
    python dual_agent_runner.py --task L1-PY-01 \
        --driver anthropic/claude-opus-4-5 \
        --coder gemini-2.5-flash
"""

import argparse
import json
import os
import re
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

from pricing import CostTracker, BenchmarkCostSummary, format_cost

# Try to import LLM clients
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import google.generativeai as genai
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False


@dataclass
class DualAgentConfig:
    """Configuration for dual-agent benchmark."""
    task_id: str
    driver_model: str  # Heavy model that directs
    coder_model: str   # Fast model that codes (via Aider)
    max_iterations: int = 20
    max_tokens: int = 100000  # Token limit to prevent runaway costs
    timeout_seconds: int = 600
    verbose: bool = False
    dev_mode: bool = False  # Include solution.md for harness testing


@dataclass
class DualAgentResult:
    """Result of dual-agent benchmark run."""
    task_id: str
    driver_model: str
    coder_model: str
    success: bool
    reason: str = ""
    total_iterations: int = 0
    driver_turns: int = 0
    coder_edits: int = 0
    driver_tokens: int = 0  # Tokens used by driver
    coder_tokens: int = 0   # Estimated tokens used by coder (from Aider)
    total_tokens: int = 0   # Combined token usage
    driver_cost_usd: float = 0.0  # Cost in USD for driver
    coder_cost_usd: float = 0.0   # Cost in USD for coder
    total_cost_usd: float = 0.0   # Combined cost
    time_seconds: float = 0.0
    samples_matched: int = 0
    samples_expected: int = 0
    conversation_log: list = field(default_factory=list)
    generated_code: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


DRIVER_SYSTEM_PROMPT = """You are a senior DDS developer supervising a junior developer (the Coder).

Your role:
1. Review the Coder's work after each attempt
2. Provide specific, actionable feedback
3. Guide them toward a working solution
4. Decide when the task is complete

The Coder is using Aider to write code. After each of your messages, they will:
1. Implement your suggestions
2. Run tests
3. Report back with results

Communication format:
- Be specific and technical
- Reference exact code/errors when possible
- Give one clear next step at a time
- Say "TASK_COMPLETE" when the tests pass and code is correct

Remember: You cannot see the code directly. The Coder will show you test results and errors.
"""

DRIVER_INITIAL_PROMPT = """You are supervising a Coder who needs to complete this task:

{task_prompt}

The Coder will write the code using Aider and run tests.
Start by giving them clear instructions on how to approach this task.
Emphasize:
1. Start simple, test early
2. Use the correct DDS API patterns
3. Run the test after each change

What are your initial instructions to the Coder?
"""

DRIVER_REVIEW_PROMPT = """The Coder attempted your instructions. Here's what happened:

## Coder's Actions:
{coder_actions}

## Test Results:
{test_results}

## Current Code (if any):
```python
{current_code}
```

Based on this:
1. What went wrong (if anything)?
2. What should the Coder try next?

If the test passed completely, say "TASK_COMPLETE".
Otherwise, give specific instructions for the next attempt.
"""


class DriverAgent:
    """The supervisory agent that guides the Coder."""
    
    def __init__(self, model: str, verbose: bool = False):
        self.model = model
        self.verbose = verbose
        self.conversation = []
        self.total_tokens_used = 0  # Track cumulative token usage
        self.cost_tracker = CostTracker(model)  # Track costs
        self._setup_client()
    
    def _setup_client(self):
        """Setup the appropriate API client."""
        if "anthropic" in self.model or "claude" in self.model:
            if not HAS_ANTHROPIC:
                raise ImportError("anthropic package required for Claude models")
            self.client = anthropic.Anthropic()
            self.provider = "anthropic"
        elif "openai" in self.model or "gpt" in self.model:
            if not HAS_OPENAI:
                raise ImportError("openai package required for GPT models")
            self.client = openai.OpenAI()
            self.provider = "openai"
        elif "gemini" in self.model:
            if not HAS_GOOGLE:
                raise ImportError("google.generativeai package required for Gemini")
            genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
            self.client = genai.GenerativeModel(self.model)
            self.provider = "google"
        else:
            raise ValueError(f"Unknown model provider: {self.model}")
    
    def _call_llm(self, prompt: str) -> str:
        """Call the driver model."""
        self.conversation.append({"role": "user", "content": prompt})
        tokens_used = 0
        
        if self.provider == "anthropic":
            model_name = self.model.replace("anthropic/", "")
            response = self.client.messages.create(
                model=model_name,
                max_tokens=2048,
                system=DRIVER_SYSTEM_PROMPT,
                messages=self.conversation,
            )
            reply = response.content[0].text
            # Track tokens and cost
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            tokens_used = input_tokens + output_tokens
            self.cost_tracker.add_usage(input_tokens, output_tokens)
            
        elif self.provider == "openai":
            model_name = self.model.replace("openai/", "")
            messages = [{"role": "system", "content": DRIVER_SYSTEM_PROMPT}]
            messages.extend(self.conversation)
            
            # GPT-5+ models use max_completion_tokens, older use max_tokens
            if "gpt-5" in model_name or "o1" in model_name or "o3" in model_name:
                response = self.client.chat.completions.create(
                    model=model_name,
                    max_completion_tokens=2048,
                    messages=messages,
                )
            else:
                response = self.client.chat.completions.create(
                    model=model_name,
                    max_tokens=2048,
                    messages=messages,
                )
            reply = response.choices[0].message.content
            # Track tokens and cost
            if response.usage:
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
                tokens_used = input_tokens + output_tokens
                self.cost_tracker.add_usage(input_tokens, output_tokens)
                
        elif self.provider == "google":
            # Gemini uses a different format
            full_prompt = f"{DRIVER_SYSTEM_PROMPT}\n\n{prompt}"
            response = self.client.generate_content(full_prompt)
            reply = response.text
            # Estimate tokens for Google (rough: 1.3 tokens per word)
            input_tokens = int(len(full_prompt.split()) * 1.3)
            output_tokens = int(len(reply.split()) * 1.3)
            tokens_used = input_tokens + output_tokens
            self.cost_tracker.add_usage(input_tokens, output_tokens)
        
        self.total_tokens_used += tokens_used
        self.conversation.append({"role": "assistant", "content": reply})
        
        if self.verbose:
            print(f"\n[DRIVER] ({tokens_used} tokens) {reply[:500]}...", file=sys.stderr)
        
        return reply
    
    def get_initial_instructions(self, task_prompt: str) -> str:
        """Get initial instructions for the Coder."""
        prompt = DRIVER_INITIAL_PROMPT.format(task_prompt=task_prompt)
        return self._call_llm(prompt)
    
    def review_and_guide(
        self, 
        coder_actions: str, 
        test_results: str, 
        current_code: str
    ) -> tuple[str, bool]:
        """Review Coder's work and provide next steps.
        
        Returns: (instructions, is_complete)
        """
        prompt = DRIVER_REVIEW_PROMPT.format(
            coder_actions=coder_actions,
            test_results=test_results,
            current_code=current_code or "(no code yet)",
        )
        
        response = self._call_llm(prompt)
        is_complete = "TASK_COMPLETE" in response.upper()
        
        return response, is_complete


class CoderAgent:
    """The coding agent that uses Aider."""
    
    def __init__(self, model: str, workspace: Path, verbose: bool = False):
        self.model = model
        self.workspace = workspace
        self.verbose = verbose
        self.edit_count = 0
        self.estimated_tokens = 0  # Rough estimate based on Aider output
        self.cost_tracker = CostTracker(model)  # Track costs
    
    def execute_instructions(self, instructions: str, timeout: int = 120) -> tuple[str, str]:
        """Execute instructions using Aider.
        
        Returns: (aider_output, test_results)
        """
        # Find Python files in workspace to add to Aider
        py_files = list(self.workspace.glob("*.py"))
        # Exclude test files
        py_files = [f for f in py_files if not f.name.startswith("test_")]
        
        cmd = [
            "aider",
            "--model", self.model,
            "--yes",
            "--no-git",
            "--no-pretty",
            "--message", instructions,
        ]
        
        # Add Python files for Aider to edit
        for f in py_files:
            cmd.append(str(f.name))
        
        if self.verbose:
            print(f"\n[CODER] Running Aider with: {instructions[:200]}...", file=sys.stderr)
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.workspace,
                timeout=timeout,
                capture_output=True,
                text=True,
            )
            aider_output = result.stdout + result.stderr
            
            # Count edits
            self.edit_count += aider_output.count("Applied edit")
            
            # Estimate tokens (Aider may print "Tokens:" in output)
            token_match = re.search(r"Tokens:\s*([\d,]+)", aider_output)
            if token_match:
                tokens_this_call = int(token_match.group(1).replace(",", ""))
            else:
                # Rough estimate: ~1.3 tokens per word
                tokens_this_call = int(len(aider_output.split()) * 1.3)
            
            self.estimated_tokens += tokens_this_call
            # Estimate cost (assume 70% input, 30% output for Aider)
            self.cost_tracker.add_total_tokens(tokens_this_call, input_ratio=0.7)
            
        except subprocess.TimeoutExpired:
            aider_output = "Aider timed out"
        except Exception as e:
            aider_output = f"Aider error: {e}"
        
        # Run test
        test_results = self._run_test()
        
        return aider_output, test_results
    
    def _run_test(self) -> str:
        """Run the test script."""
        # Find the appropriate test script
        test_script = None
        for name in ["test_publisher.py", "test_subscriber.py", "test_durability.py"]:
            candidate = self.workspace / name
            if candidate.exists():
                test_script = candidate
                break
        
        if test_script is None:
            return "No test script available"
        
        try:
            result = subprocess.run(
                [sys.executable, str(test_script)],
                cwd=self.workspace,
                timeout=90,  # Increased for subscriber tests
                capture_output=True,
                text=True,
            )
            return result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return "Test timed out"
        except Exception as e:
            return f"Test error: {e}"
    
    def get_current_code(self) -> str:
        """Get the current code (publisher or subscriber)."""
        # Check for publisher first, then subscriber
        for filename in ["publisher.py", "subscriber.py"]:
            filepath = self.workspace / filename
            if filepath.exists():
                return filepath.read_text()
        return ""


class DualAgentBenchmark:
    """Orchestrates the dual-agent benchmark."""
    
    def __init__(self, benchmark_dir: Path, verbose: bool = False):
        self.benchmark_dir = benchmark_dir
        self.verbose = verbose
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """Load benchmark configuration."""
        config_path = self.benchmark_dir / "config.yaml"
        with open(config_path) as f:
            return yaml.safe_load(f)
    
    def _setup_workspace(self, task_dir: Path) -> Path:
        """Create isolated workspace."""
        workspace = Path(tempfile.mkdtemp(prefix="dds_dual_"))
        
        # Copy all test scripts (test_publisher.py, test_subscriber.py, test_*.py)
        for test_script in task_dir.glob("test_*.py"):
            shutil.copy(test_script, workspace)
        
        # Copy any shell scripts
        for script in task_dir.glob("*.sh"):
            shutil.copy(script, workspace)
        
        # Copy reference directory
        ref_dir = task_dir / "reference"
        if ref_dir.exists():
            shutil.copytree(ref_dir, workspace / "reference")
        
        # Copy broken directory for debugging tasks (LQ-)
        broken_dir = task_dir / "broken"
        if broken_dir.exists():
            # For QoS tasks, copy broken files as starting point
            for f in broken_dir.glob("*.py"):
                shutil.copy(f, workspace)
        
        # Copy starter files if present
        starter_dir = task_dir / "starter"
        if starter_dir.exists():
            for f in starter_dir.glob("*"):
                shutil.copy(f, workspace)
        
        if self.verbose:
            print(f"Workspace: {workspace}", file=sys.stderr)
        
        return workspace
    
    def run(self, config: DualAgentConfig) -> DualAgentResult:
        """Run the dual-agent benchmark."""
        print(f"\n{'='*60}")
        print(f"Dual-Agent Benchmark: {config.task_id}")
        print(f"Driver: {config.driver_model}")
        print(f"Coder: {config.coder_model}")
        print(f"{'='*60}")
        
        start_time = time.time()
        conversation_log = []
        
        # Load task
        task_dir = self._find_task_dir(config.task_id)
        prompt_file = task_dir / "prompt.md"
        task_prompt = prompt_file.read_text()
        
        # DEV MODE: Append solution for harness testing
        if config.dev_mode:
            solution_file = task_dir / "solution.md"
            if solution_file.exists():
                task_prompt += "\n\n---\n\n# SOLUTION (DEV MODE)\n\n"
                task_prompt += solution_file.read_text()
                print("[DEV MODE] Solution appended to prompt")
            else:
                print("[DEV MODE] Warning: No solution.md found")
        
        # Setup
        workspace = self._setup_workspace(task_dir)
        driver = DriverAgent(config.driver_model, config.verbose)
        coder = CoderAgent(config.coder_model, workspace, config.verbose)
        
        # Get initial instructions from Driver
        print("\n[Driver] Providing initial instructions...")
        instructions = driver.get_initial_instructions(task_prompt)
        conversation_log.append({
            "turn": 0,
            "role": "driver",
            "content": instructions,
        })
        
        # Iteration loop
        is_complete = False
        iteration = 0
        
        while iteration < config.max_iterations and not is_complete:
            iteration += 1
            print(f"\n[Iteration {iteration}/{config.max_iterations}]")
            
            # Coder executes instructions
            print(f"  [Coder] Executing...")
            aider_output, test_results = coder.execute_instructions(instructions)
            current_code = coder.get_current_code()
            
            conversation_log.append({
                "turn": iteration,
                "role": "coder",
                "aider_output": aider_output[:1000],
                "test_results": test_results,
            })
            
            # Check if test passed
            if "ALL TESTS PASSED" in test_results:
                print(f"  [Test] ✓ PASSED")
                is_complete = True
                break
            else:
                # Extract error info
                print(f"  [Test] ✗ Failed")
                if config.verbose:
                    print(f"    {test_results[:300]}")
            
            # Driver reviews and guides
            print(f"  [Driver] Reviewing...")
            instructions, is_complete = driver.review_and_guide(
                coder_actions=aider_output[:1000],
                test_results=test_results,
                current_code=current_code,
            )
            
            conversation_log.append({
                "turn": iteration,
                "role": "driver",
                "content": instructions[:1000],
                "marked_complete": is_complete,
            })
            
            # Check timeout
            if time.time() - start_time > config.timeout_seconds:
                print("\n⚠ Timeout reached")
                break
            
            # Check token limit
            if driver.total_tokens_used > config.max_tokens:
                print(f"\n⚠ Token limit reached ({driver.total_tokens_used:,}/{config.max_tokens:,})")
                break
        
        elapsed = time.time() - start_time
        
        # Final verification
        print("\n[Final Verification]")
        success, matched, expected = self._verify(workspace, task_dir)
        
        # Calculate token usage and costs
        driver_tokens = driver.total_tokens_used
        coder_tokens = coder.estimated_tokens  # Estimated from Aider output
        total_tokens = driver_tokens + coder_tokens
        
        driver_cost = driver.cost_tracker.total_cost_usd
        coder_cost = coder.cost_tracker.total_cost_usd
        total_cost = driver_cost + coder_cost
        
        result = DualAgentResult(
            task_id=config.task_id,
            driver_model=config.driver_model,
            coder_model=config.coder_model,
            success=success,
            reason="All samples matched" if success else f"Matched {matched}/{expected}",
            total_iterations=iteration,
            driver_turns=len([c for c in conversation_log if c["role"] == "driver"]),
            coder_edits=coder.edit_count,
            driver_tokens=driver_tokens,
            coder_tokens=coder_tokens,
            total_tokens=total_tokens,
            driver_cost_usd=driver_cost,
            coder_cost_usd=coder_cost,
            total_cost_usd=total_cost,
            time_seconds=elapsed,
            samples_matched=matched,
            samples_expected=expected,
            conversation_log=conversation_log,
            generated_code=coder.get_current_code(),
        )
        
        # Print result
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"\n{status}")
        print(f"  Iterations: {iteration}")
        print(f"  Driver turns: {result.driver_turns}")
        print(f"  Coder edits: {coder.edit_count}")
        print(f"  Tokens: {total_tokens:,} (driver: {driver_tokens:,}, coder: ~{coder_tokens:,})")
        print(f"  Cost: {format_cost(total_cost)} (driver: {format_cost(driver_cost)}, coder: {format_cost(coder_cost)})")
        print(f"  Samples: {matched}/{expected}")
        print(f"  Time: {elapsed:.1f}s")
        
        # Save result
        self._save_result(result)
        
        # Cleanup on success
        if success:
            shutil.rmtree(workspace)
        else:
            print(f"  Workspace: {workspace}")
        
        return result
    
    def _find_task_dir(self, task_id: str) -> Path:
        """Find task directory."""
        tasks_dir = self.benchmark_dir / "tasks"
        for d in tasks_dir.iterdir():
            if task_id in d.name:
                return d
        raise ValueError(f"Task {task_id} not found")
    
    def _verify(self, workspace: Path, task_dir: Path) -> tuple[bool, int, int]:
        """Run final verification with proper process management."""
        publisher = workspace / "publisher.py"
        subscriber = workspace / "subscriber.py"
        expected_output = task_dir / "expected" / "output.jsonl"
        output_file = workspace / "actual_output.jsonl"
        
        sub_proc = None
        output_handle = None
        
        try:
            # Determine task type
            if publisher.exists() and not subscriber.exists():
                # Publisher task: run generated publisher + reference subscriber
                ref_subscriber = task_dir / "reference" / "subscriber.py"
                if not ref_subscriber.exists():
                    return False, 0, 10
                
                # Start reference subscriber FIRST
                output_handle = open(output_file, "w")
                sub_proc = subprocess.Popen(
                    [sys.executable, str(ref_subscriber),
                     "--domain", "85", "--count", "10", "--timeout", "30"],
                    stdout=output_handle,
                    stderr=subprocess.PIPE,
                )
                
                # Wait for subscriber to be ready
                time.sleep(3)
                
                # Run generated publisher
                pub_result = subprocess.run(
                    [sys.executable, str(publisher)],
                    cwd=workspace,
                    timeout=60,
                    capture_output=True,
                )
                
                # Wait for subscriber to finish receiving
                time.sleep(3)
                
                # Give subscriber time to complete
                try:
                    sub_proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    sub_proc.terminate()
                    sub_proc.wait(timeout=5)
                
            elif subscriber.exists():
                # Subscriber task: run generated subscriber + reference publisher
                ref_publisher = task_dir / "reference" / "publisher.py"
                if not ref_publisher.exists():
                    return False, 0, 10
                
                # Start generated subscriber FIRST
                output_handle = open(output_file, "w")
                sub_proc = subprocess.Popen(
                    [sys.executable, str(subscriber),
                     "--count", "10", "--timeout", "30"],
                    stdout=output_handle,
                    stderr=subprocess.PIPE,
                    cwd=workspace,
                )
                
                # Wait for subscriber to be ready (discovery)
                time.sleep(3)
                
                # Run reference publisher
                pub_result = subprocess.run(
                    [sys.executable, str(ref_publisher), 
                     "--count", "10", "--domain", "0"],
                    cwd=task_dir / "reference",
                    timeout=60,
                    capture_output=True,
                )
                
                # Wait for reliable delivery
                time.sleep(3)
                
                # Give subscriber time to complete
                try:
                    sub_proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    sub_proc.terminate()
                    sub_proc.wait(timeout=5)
                
            else:
                return False, 0, 10
            
        except Exception as e:
            if self.verbose:
                print(f"Verification process error: {e}", file=sys.stderr)
            if sub_proc:
                sub_proc.kill()
            return False, 0, 10
        finally:
            if output_handle:
                output_handle.close()
            if sub_proc and sub_proc.poll() is None:
                sub_proc.kill()
        
        # Compare output
        try:
            if output_file.exists():
                actual_lines = output_file.read_text().strip().split("\n")
                actual_count = len([l for l in actual_lines if l.strip()])
                
                if expected_output.exists():
                    expected_lines = expected_output.read_text().strip().split("\n")
                    expected_count = len([l for l in expected_lines if l.strip()])
                    
                    if actual_count >= expected_count:
                        return True, actual_count, expected_count
                    return False, actual_count, expected_count
                else:
                    # No expected file, just check we got samples
                    if actual_count >= 10:
                        return True, actual_count, 10
                    return False, actual_count, 10
            
            return False, 0, 10
            
        except Exception as e:
            if self.verbose:
                print(f"Verification compare error: {e}", file=sys.stderr)
            return False, 0, 10
    
    def _save_result(self, result: DualAgentResult):
        """Save benchmark result."""
        results_dir = self.benchmark_dir / "results" / "dual_agent"
        results_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{result.task_id}_{result.driver_model.replace('/', '_')}__{result.coder_model.replace('/', '_')}_{result.timestamp.replace(':', '-')}.json"
        result_file = results_dir / filename
        
        with open(result_file, "w") as f:
            json.dump({
                "task_id": result.task_id,
                "driver_model": result.driver_model,
                "coder_model": result.coder_model,
                "success": result.success,
                "reason": result.reason,
                "total_iterations": result.total_iterations,
                "driver_turns": result.driver_turns,
                "coder_edits": result.coder_edits,
                "driver_tokens": result.driver_tokens,
                "coder_tokens": result.coder_tokens,
                "total_tokens": result.total_tokens,
                "driver_cost_usd": result.driver_cost_usd,
                "coder_cost_usd": result.coder_cost_usd,
                "total_cost_usd": result.total_cost_usd,
                "time_seconds": result.time_seconds,
                "samples_matched": result.samples_matched,
                "samples_expected": result.samples_expected,
                "timestamp": result.timestamp,
                "conversation_log": result.conversation_log,
            }, f, indent=2)
        
        print(f"Result saved: {result_file}")


def main():
    parser = argparse.ArgumentParser(description="Dual-Agent DDS Benchmark")
    parser.add_argument("--task", "-t", required=True, help="Task ID")
    parser.add_argument("--driver", "-d", required=True,
                        help="Driver model (heavy reasoning model)")
    parser.add_argument("--coder", "-c", required=True,
                        help="Coder model (fast coding model for Aider)")
    parser.add_argument("--max-iterations", "-n", type=int, default=10,
                        help="Max iterations (default: 10)")
    parser.add_argument("--max-tokens", type=int, default=100000,
                        help="Max tokens before stopping (default: 100000)")
    parser.add_argument("--timeout", type=int, default=600,
                        help="Timeout in seconds (default: 600)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--dev-mode", action="store_true",
                        help="Development mode: include solution.md in prompt (for testing harness)")
    parser.add_argument("--benchmark-dir", "-b", default=None)
    
    args = parser.parse_args()
    
    # Find benchmark directory
    if args.benchmark_dir:
        benchmark_dir = Path(args.benchmark_dir)
    else:
        for candidate in [Path(__file__).parent, Path.cwd() / "benchmark", Path.cwd()]:
            if (candidate / "config.yaml").exists():
                benchmark_dir = candidate
                break
        else:
            print("ERROR: Could not find benchmark directory", file=sys.stderr)
            sys.exit(1)
    
    config = DualAgentConfig(
        task_id=args.task,
        driver_model=args.driver,
        coder_model=args.coder,
        max_iterations=args.max_iterations,
        max_tokens=args.max_tokens,
        timeout_seconds=args.timeout,
        verbose=args.verbose,
        dev_mode=args.dev_mode,
    )
    
    benchmark = DualAgentBenchmark(benchmark_dir, args.verbose)
    result = benchmark.run(config)
    
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()


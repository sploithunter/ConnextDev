#!/usr/bin/env python3
"""Rubric-based Code Evaluator for DDS Benchmark.

Uses high-end LLMs to evaluate generated code on multiple dimensions
beyond simple pass/fail deterministic testing.

Evaluation dimensions:
1. Prompt Following - Did the code follow all requirements?
2. Code Style - Is the code well-structured and readable?
3. Correctness - Are there bugs or logic errors?
4. DDS Best Practices - Async callbacks, external QoS, proper patterns
5. Error Handling - Does code handle edge cases?
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

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


@dataclass
class RubricScore:
    """Score for a single rubric dimension."""
    dimension: str
    score: int  # 1-5
    max_score: int = 5
    reasoning: str = ""
    issues: list = field(default_factory=list)


@dataclass
class RubricEvaluation:
    """Complete rubric evaluation result."""
    task_id: str
    model_evaluated: str
    evaluator_model: str
    scores: list  # List of RubricScore
    overall_score: float
    max_overall: float
    pass_rate: float  # percentage
    summary: str
    code_snippet: str = ""


# DDS-specific rubric for publishers
DDS_PUBLISHER_RUBRIC = """
# DDS Publisher Code Evaluation Rubric

You are evaluating AI-generated DDS publisher code. Score each dimension 1-5.

## Dimension 1: Prompt Following (1-5)
- 5: All requirements met exactly (topic name, fields, count, domain, timing)
- 4: Minor deviation (e.g., slightly different timing)
- 3: Most requirements met, one significant miss
- 2: Multiple requirements missed
- 1: Does not follow prompt

Check specifically:
- Topic name exactly as specified
- Field names and types match
- Sample count is correct
- Domain ID is correct
- Timing follows spec (discovery wait, publish rate, final wait)

## Dimension 2: Code Style (1-5)
- 5: Excellent - clear structure, good naming, appropriate comments
- 4: Good - readable, minor style issues
- 3: Acceptable - functional but could be cleaner
- 2: Poor - hard to read, inconsistent style
- 1: Very poor - messy, no structure

Check:
- Function decomposition
- Variable naming
- Comments where needed
- Consistent formatting

## Dimension 3: Correctness (1-5)
- 5: No bugs, handles all cases correctly
- 4: Minor issues that don't affect functionality
- 3: Works but has subtle bugs or edge cases
- 2: Has bugs that could cause issues
- 1: Fundamentally broken

Check:
- Logic errors
- Off-by-one errors
- Resource leaks
- Exception handling

## Dimension 4: DDS Best Practices (1-5)
- 5: Follows all DDS best practices
- 4: Minor deviations from best practices
- 3: Some anti-patterns present
- 2: Multiple anti-patterns
- 1: Ignores DDS best practices entirely

**CRITICAL DDS Best Practices:**
- Uses DynamicData.Topic and DynamicData.DataWriter (not plain Topic/DataWriter)
- Waits for discovery before publishing
- Waits for reliable delivery at end
- Does NOT hardcode QoS (uses external XML when provided)
- Proper cleanup of resources

## Dimension 5: Error Handling (1-5)
- 5: Comprehensive error handling, graceful failures
- 4: Good error handling for common cases
- 3: Basic error handling present
- 2: Minimal error handling
- 1: No error handling

Check:
- Try/except blocks where appropriate
- Graceful shutdown
- Resource cleanup on error
"""

DDS_SUBSCRIBER_RUBRIC = """
# DDS Subscriber Code Evaluation Rubric

You are evaluating AI-generated DDS subscriber code. Score each dimension 1-5.

## Dimension 1: Prompt Following (1-5)
- 5: All requirements met exactly
- 4: Minor deviation
- 3: Most requirements met, one significant miss
- 2: Multiple requirements missed
- 1: Does not follow prompt

## Dimension 2: Code Style (1-5)
- 5: Excellent - clear structure, good naming, appropriate comments
- 4: Good - readable, minor style issues
- 3: Acceptable - functional but could be cleaner
- 2: Poor - hard to read
- 1: Very poor - messy

## Dimension 3: Correctness (1-5)
- 5: No bugs
- 4: Minor issues
- 3: Subtle bugs
- 2: Has bugs
- 1: Fundamentally broken

## Dimension 4: DDS Best Practices (1-5)
- 5: Follows all DDS best practices
- 4: Minor deviations
- 3: Some anti-patterns
- 2: Multiple anti-patterns
- 1: Ignores best practices

**CRITICAL DDS Subscriber Best Practices:**
- Uses ASYNC callbacks (on_data_available or WaitSet) - NOT polling
- Does NOT use sleep loops to poll for data
- Uses DynamicData.Topic and DynamicData.DataReader
- Properly handles sample validity (checks sample.info.valid)
- Does NOT hardcode QoS
- External QoS XML when appropriate
- Proper resource cleanup

**ANTI-PATTERNS TO FLAG (score 1-2 if present):**
- `while True: samples = reader.read(); time.sleep(0.1)` - POLLING, BAD
- `for i in range(100): reader.take(); sleep(0.01)` - POLLING, BAD
- Any sleep loop that repeatedly calls read/take - POLLING, BAD

**CORRECT PATTERNS (score 4-5):**
- WaitSet with StatusCondition for DATA_AVAILABLE
- Listener with on_data_available callback
- `waitset.wait()` blocking call

## Dimension 5: Error Handling (1-5)
- 5: Comprehensive
- 4: Good
- 3: Basic
- 2: Minimal
- 1: None
"""


def get_rubric_for_task(task_type: str) -> str:
    """Get appropriate rubric for task type."""
    if "publisher" in task_type.lower():
        return DDS_PUBLISHER_RUBRIC
    elif "subscriber" in task_type.lower():
        return DDS_SUBSCRIBER_RUBRIC
    else:
        return DDS_PUBLISHER_RUBRIC  # Default


def create_evaluation_prompt(code: str, task_prompt: str, rubric: str) -> str:
    """Create the evaluation prompt for the LLM."""
    return f"""You are an expert DDS developer and code reviewer. Evaluate the following code against the rubric.

## Task Requirements (what the code should do):
{task_prompt}

## Code to Evaluate:
```python
{code}
```

## Evaluation Rubric:
{rubric}

## Your Evaluation:

Provide your evaluation as a JSON object with this exact structure:
{{
    "scores": [
        {{
            "dimension": "Prompt Following",
            "score": <1-5>,
            "reasoning": "<explanation>",
            "issues": ["<issue1>", "<issue2>"]
        }},
        {{
            "dimension": "Code Style", 
            "score": <1-5>,
            "reasoning": "<explanation>",
            "issues": []
        }},
        {{
            "dimension": "Correctness",
            "score": <1-5>,
            "reasoning": "<explanation>",
            "issues": []
        }},
        {{
            "dimension": "DDS Best Practices",
            "score": <1-5>,
            "reasoning": "<explanation>",
            "issues": []
        }},
        {{
            "dimension": "Error Handling",
            "score": <1-5>,
            "reasoning": "<explanation>",
            "issues": []
        }}
    ],
    "summary": "<2-3 sentence overall assessment>"
}}

Be strict but fair. Pay special attention to DDS Best Practices - this is a DDS-specific benchmark.
Return ONLY the JSON, no other text.
"""


class RubricEvaluator:
    """Evaluates code using LLM-based rubric scoring."""
    
    EVALUATOR_MODELS = [
        "anthropic/claude-opus-4-5",
        "openai/gpt-5.2",
        "gemini-2.5-pro",
    ]
    
    def __init__(self, evaluator_model: str = "anthropic/claude-opus-4-5"):
        self.evaluator_model = evaluator_model
        self._setup_client()
    
    def _setup_client(self):
        """Setup the appropriate API client."""
        if "anthropic" in self.evaluator_model or "claude" in self.evaluator_model:
            if not HAS_ANTHROPIC:
                raise ImportError("anthropic package not installed")
            self.client = anthropic.Anthropic()
            self.provider = "anthropic"
        elif "openai" in self.evaluator_model or "gpt" in self.evaluator_model:
            if not HAS_OPENAI:
                raise ImportError("openai package not installed")
            self.client = openai.OpenAI()
            self.provider = "openai"
        else:
            # Default to anthropic
            if HAS_ANTHROPIC:
                self.client = anthropic.Anthropic()
                self.provider = "anthropic"
            elif HAS_OPENAI:
                self.client = openai.OpenAI()
                self.provider = "openai"
            else:
                raise ImportError("No LLM client available")
    
    def _call_llm(self, prompt: str) -> str:
        """Call the LLM and get response."""
        if self.provider == "anthropic":
            model_name = self.evaluator_model.replace("anthropic/", "")
            response = self.client.messages.create(
                model=model_name,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        elif self.provider == "openai":
            model_name = self.evaluator_model.replace("openai/", "")
            response = self.client.chat.completions.create(
                model=model_name,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    def evaluate(
        self,
        code: str,
        task_prompt: str,
        task_type: str = "publisher",
        task_id: str = "",
        model_evaluated: str = "",
    ) -> RubricEvaluation:
        """Evaluate code against rubric.
        
        Returns RubricEvaluation with scores and summary.
        """
        rubric = get_rubric_for_task(task_type)
        eval_prompt = create_evaluation_prompt(code, task_prompt, rubric)
        
        # Call LLM
        response = self._call_llm(eval_prompt)
        
        # Parse JSON response
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            
            result = json.loads(json_str.strip())
        except json.JSONDecodeError as e:
            # Fallback: create error result
            return RubricEvaluation(
                task_id=task_id,
                model_evaluated=model_evaluated,
                evaluator_model=self.evaluator_model,
                scores=[],
                overall_score=0,
                max_overall=25,
                pass_rate=0,
                summary=f"Failed to parse evaluation: {e}",
                code_snippet=code[:500],
            )
        
        # Convert to RubricScore objects
        scores = []
        for s in result.get("scores", []):
            scores.append(RubricScore(
                dimension=s.get("dimension", "Unknown"),
                score=s.get("score", 0),
                reasoning=s.get("reasoning", ""),
                issues=s.get("issues", []),
            ))
        
        # Calculate overall score
        total_score = sum(s.score for s in scores)
        max_score = sum(s.max_score for s in scores)
        pass_rate = (total_score / max_score * 100) if max_score > 0 else 0
        
        return RubricEvaluation(
            task_id=task_id,
            model_evaluated=model_evaluated,
            evaluator_model=self.evaluator_model,
            scores=scores,
            overall_score=total_score,
            max_overall=max_score,
            pass_rate=pass_rate,
            summary=result.get("summary", ""),
            code_snippet=code[:500],
        )
    
    def evaluate_from_file(
        self,
        code_file: Path,
        prompt_file: Path,
        task_id: str = "",
        model_evaluated: str = "",
    ) -> RubricEvaluation:
        """Evaluate code from files."""
        code = code_file.read_text()
        task_prompt = prompt_file.read_text()
        
        # Determine task type from filename or prompt
        task_type = "publisher" if "publisher" in str(code_file).lower() else "subscriber"
        
        return self.evaluate(
            code=code,
            task_prompt=task_prompt,
            task_type=task_type,
            task_id=task_id,
            model_evaluated=model_evaluated,
        )


def format_evaluation_report(evaluation: RubricEvaluation) -> str:
    """Format evaluation as human-readable report."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"RUBRIC EVALUATION: {evaluation.task_id}")
    lines.append(f"Model Evaluated: {evaluation.model_evaluated}")
    lines.append(f"Evaluator: {evaluation.evaluator_model}")
    lines.append("=" * 60)
    lines.append("")
    
    for score in evaluation.scores:
        stars = "★" * score.score + "☆" * (score.max_score - score.score)
        lines.append(f"{score.dimension}: {stars} ({score.score}/{score.max_score})")
        if score.reasoning:
            lines.append(f"  Reasoning: {score.reasoning}")
        if score.issues:
            for issue in score.issues:
                lines.append(f"  ⚠ Issue: {issue}")
        lines.append("")
    
    lines.append("-" * 60)
    lines.append(f"OVERALL SCORE: {evaluation.overall_score}/{evaluation.max_overall} ({evaluation.pass_rate:.1f}%)")
    lines.append("")
    lines.append(f"Summary: {evaluation.summary}")
    lines.append("=" * 60)
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Rubric-based Code Evaluator")
    parser.add_argument("--code", "-c", required=True,
                        help="Path to code file to evaluate")
    parser.add_argument("--prompt", "-p", required=True,
                        help="Path to task prompt file")
    parser.add_argument("--evaluator", "-e", default="anthropic/claude-opus-4-5",
                        help="Evaluator model (default: anthropic/claude-opus-4-5)")
    parser.add_argument("--task-id", "-t", default="",
                        help="Task ID for reporting")
    parser.add_argument("--model", "-m", default="",
                        help="Model that generated the code")
    parser.add_argument("--output", "-o", default=None,
                        help="Output file for JSON result")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON instead of report")
    
    args = parser.parse_args()
    
    evaluator = RubricEvaluator(args.evaluator)
    
    evaluation = evaluator.evaluate_from_file(
        code_file=Path(args.code),
        prompt_file=Path(args.prompt),
        task_id=args.task_id,
        model_evaluated=args.model,
    )
    
    if args.json:
        result = {
            "task_id": evaluation.task_id,
            "model_evaluated": evaluation.model_evaluated,
            "evaluator_model": evaluation.evaluator_model,
            "scores": [
                {
                    "dimension": s.dimension,
                    "score": s.score,
                    "max_score": s.max_score,
                    "reasoning": s.reasoning,
                    "issues": s.issues,
                }
                for s in evaluation.scores
            ],
            "overall_score": evaluation.overall_score,
            "max_overall": evaluation.max_overall,
            "pass_rate": evaluation.pass_rate,
            "summary": evaluation.summary,
        }
        output = json.dumps(result, indent=2)
    else:
        output = format_evaluation_report(evaluation)
    
    if args.output:
        Path(args.output).write_text(output)
    else:
        print(output)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


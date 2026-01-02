#!/usr/bin/env python3
"""LLM Pricing Calculator.

Tracks costs based on token usage and model pricing.
Prices are in USD per 1M tokens (as of January 2026).

Note: Prices change frequently. Update as needed.
"""

from dataclasses import dataclass
from typing import Optional


# Pricing per 1M tokens (input, output)
# Source: Provider pricing pages as of Jan 2026
MODEL_PRICING = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    # GPT-5 Family (Jan 2026 pricing)
    "gpt-5": (5.00, 15.00),
    "gpt-5-mini": (1.00, 3.00),
    "gpt-5-nano": (0.25, 0.75),
    "gpt-5.1": (5.00, 15.00),
    "gpt-5.2": (5.00, 15.00),
    
    # O-series Reasoning Models
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o1-preview": (15.00, 60.00),
    "o1-pro": (150.00, 600.00),
    "o3": (10.00, 40.00),  # Estimated
    "o3-mini": (1.10, 4.40),
    
    # Anthropic
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-opus-4-20250514": (15.00, 75.00),
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    
    # Google
    "gemini-2.5-pro": (1.25, 5.00),  # Estimated
    "gemini-2.5-flash": (0.075, 0.30),  # Estimated
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-3-pro": (2.00, 8.00),  # Estimated
    
    # xAI (direct API with XAI_API_KEY)
    "grok-2": (2.00, 10.00),
    "grok-3": (3.00, 15.00),
    "grok-3-mini": (0.30, 0.50),
    "grok-4": (5.00, 15.00),
    
    # OpenRouter passthrough (fallback when no provider-specific key)
    # Format: x-ai/model - prices include OpenRouter markup (~5-10%)
    "x-ai/grok-3-beta": (3.00, 15.00),
    "x-ai/grok-3-mini-beta": (0.30, 0.50),
    "x-ai/grok-4": (5.00, 15.00),
    "x-ai/grok-4-fast:free": (0.0, 0.0),  # Free tier
    
    # Other OpenRouter models
    "meta-llama/llama-3.3-70b-instruct": (0.40, 0.40),
    "deepseek/deepseek-chat": (0.14, 0.28),
    "deepseek/deepseek-r1": (0.55, 2.19),
    "qwen/qwen-2.5-72b-instruct": (0.35, 0.40),
}


@dataclass
class TokenUsage:
    """Track token usage for a single call."""
    input_tokens: int = 0
    output_tokens: int = 0
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class CostTracker:
    """Track cumulative costs across multiple API calls."""
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float = 0.0
    call_count: int = 0
    
    def __post_init__(self):
        # Normalize model name
        self.model_key = self._normalize_model_name(self.model)
        if self.model_key in MODEL_PRICING:
            self.input_price_per_m, self.output_price_per_m = MODEL_PRICING[self.model_key]
        else:
            # Unknown model - use conservative estimate
            self.input_price_per_m = 5.0
            self.output_price_per_m = 15.0
    
    def _normalize_model_name(self, model: str) -> str:
        """Normalize model name for pricing lookup."""
        # Remove provider prefix
        model = model.replace("openai/", "").replace("anthropic/", "")
        model = model.replace("google/", "").replace("xai/", "")
        return model
    
    def add_usage(self, input_tokens: int, output_tokens: int):
        """Add token usage and calculate cost."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.call_count += 1
        
        # Calculate cost
        input_cost = (input_tokens / 1_000_000) * self.input_price_per_m
        output_cost = (output_tokens / 1_000_000) * self.output_price_per_m
        self.total_cost_usd += input_cost + output_cost
    
    def add_total_tokens(self, total_tokens: int, input_ratio: float = 0.7):
        """Add tokens when only total is known (estimate split)."""
        input_tokens = int(total_tokens * input_ratio)
        output_tokens = total_tokens - input_tokens
        self.add_usage(input_tokens, output_tokens)
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
    
    def summary(self) -> dict:
        return {
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": round(self.total_cost_usd, 4),
            "call_count": self.call_count,
        }


@dataclass
class BenchmarkCostSummary:
    """Aggregate costs for a benchmark run."""
    driver_cost: CostTracker
    coder_cost: CostTracker
    
    @property
    def total_cost_usd(self) -> float:
        return self.driver_cost.total_cost_usd + self.coder_cost.total_cost_usd
    
    @property
    def total_tokens(self) -> int:
        return self.driver_cost.total_tokens + self.coder_cost.total_tokens
    
    def summary(self) -> dict:
        return {
            "driver": self.driver_cost.summary(),
            "coder": self.coder_cost.summary(),
            "total_cost_usd": round(self.total_cost_usd, 4),
            "total_tokens": self.total_tokens,
        }


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost for a single call."""
    tracker = CostTracker(model)
    tracker.add_usage(input_tokens, output_tokens)
    return tracker.total_cost_usd


def format_cost(cost_usd: float) -> str:
    """Format cost for display."""
    if cost_usd < 0.01:
        return f"${cost_usd:.4f}"
    elif cost_usd < 1.00:
        return f"${cost_usd:.3f}"
    else:
        return f"${cost_usd:.2f}"


if __name__ == "__main__":
    # Test pricing
    print("Example costs (per 1M tokens):")
    for model, (inp, out) in sorted(MODEL_PRICING.items()):
        print(f"  {model}: ${inp:.2f} in / ${out:.2f} out")
    
    print("\nExample usage:")
    tracker = CostTracker("openai/gpt-4.1-mini")
    tracker.add_usage(10000, 2000)  # 10k in, 2k out
    print(f"  10k input + 2k output = {format_cost(tracker.total_cost_usd)}")
    
    tracker2 = CostTracker("anthropic/claude-opus-4-20250514")
    tracker2.add_usage(10000, 2000)
    print(f"  Same with Opus 4.5 = {format_cost(tracker2.total_cost_usd)}")


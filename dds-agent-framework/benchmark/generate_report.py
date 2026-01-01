#!/usr/bin/env python3
"""
Benchmark Report Generator - Post-processing visualization and reports.

Reads benchmark results and generates:
1. Terminal summary with ASCII charts
2. HTML report with interactive charts
3. PNG charts for sharing

Usage:
    # Generate report from latest suite run
    python generate_report.py
    
    # Generate from specific result file
    python generate_report.py --input results/suites/suite_results_20260101.json
    
    # Generate HTML report
    python generate_report.py --html
    
    # Generate PNG charts
    python generate_report.py --png
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# Try to import visualization libraries
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


@dataclass
class ModelResult:
    """Aggregated results for a single model."""
    model: str
    tasks_run: int
    tasks_passed: int
    pass_rate: float
    total_cost: float
    total_tokens: int
    avg_time: float
    cost_per_pass: float  # Cost efficiency


def load_results(filepath: Path) -> dict:
    """Load results from JSON file."""
    with open(filepath) as f:
        return json.load(f)


def find_latest_results(results_dir: Path) -> Optional[Path]:
    """Find the most recent results file."""
    if not results_dir.exists():
        return None
    
    files = sorted(
        results_dir.glob("suite_results_*.json"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


def aggregate_by_model(data: dict) -> list[ModelResult]:
    """Aggregate results by model."""
    model_stats = {}
    
    for result in data.get("results", []):
        model = result.get("model", "unknown")
        
        if model not in model_stats:
            model_stats[model] = {
                "tasks_run": 0,
                "tasks_passed": 0,
                "total_cost": 0.0,
                "total_tokens": 0,
                "total_time": 0.0,
            }
        
        stats = model_stats[model]
        stats["tasks_run"] += 1
        if result.get("success"):
            stats["tasks_passed"] += 1
        stats["total_cost"] += result.get("cost", 0.0)
        stats["total_time"] += result.get("time", 0.0)
    
    results = []
    for model, stats in model_stats.items():
        pass_rate = stats["tasks_passed"] / max(1, stats["tasks_run"])
        cost_per_pass = (
            stats["total_cost"] / stats["tasks_passed"]
            if stats["tasks_passed"] > 0 else float('inf')
        )
        
        results.append(ModelResult(
            model=model,
            tasks_run=stats["tasks_run"],
            tasks_passed=stats["tasks_passed"],
            pass_rate=pass_rate,
            total_cost=stats["total_cost"],
            total_tokens=stats.get("total_tokens", 0),
            avg_time=stats["total_time"] / max(1, stats["tasks_run"]),
            cost_per_pass=cost_per_pass,
        ))
    
    return sorted(results, key=lambda r: r.pass_rate, reverse=True)


def print_terminal_report(data: dict, model_results: list[ModelResult]):
    """Print a nice terminal report with ASCII charts."""
    
    print("\n" + "═" * 80)
    print("  DDS AGENT BENCHMARK REPORT")
    print("═" * 80)
    
    # Summary
    print(f"\n📊 SUMMARY")
    print("─" * 40)
    print(f"  Total Tasks:     {data.get('total_tasks', 0)}")
    print(f"  Passed:          {data.get('passed', 0)} ({data.get('pass_rate', '0%')})")
    print(f"  Failed:          {data.get('failed', 0)}")
    print(f"  Total Cost:      ${data.get('total_cost_usd', 0):.4f}")
    print(f"  Total Tokens:    {data.get('total_tokens', 0):,}")
    print(f"  Total Time:      {data.get('total_time_seconds', 0):.1f}s")
    print(f"  Dev Mode:        {data.get('dev_mode', False)}")
    
    # Model Performance Chart (ASCII bar chart)
    print(f"\n📈 MODEL PERFORMANCE (Pass Rate)")
    print("─" * 60)
    
    max_name_len = max(len(r.model.split('/')[-1][:20]) for r in model_results) if model_results else 10
    
    for r in model_results:
        name = r.model.split('/')[-1][:20]
        bar_len = int(r.pass_rate * 30)
        bar = "█" * bar_len + "░" * (30 - bar_len)
        pct = f"{r.pass_rate * 100:.0f}%"
        print(f"  {name:<{max_name_len}} │{bar}│ {pct:>4} ({r.tasks_passed}/{r.tasks_run})")
    
    # Cost Efficiency Chart
    print(f"\n💰 COST EFFICIENCY (Cost per Passed Task)")
    print("─" * 60)
    
    # Filter out infinite costs
    valid_costs = [r for r in model_results if r.cost_per_pass < float('inf')]
    if valid_costs:
        max_cost = max(r.cost_per_pass for r in valid_costs)
        for r in valid_costs:
            name = r.model.split('/')[-1][:20]
            bar_len = int((r.cost_per_pass / max(max_cost, 0.001)) * 30)
            bar = "█" * bar_len + "░" * (30 - bar_len)
            print(f"  {name:<{max_name_len}} │{bar}│ ${r.cost_per_pass:.4f}")
    
    # Failed Tasks
    failed = [r for r in data.get("results", []) if not r.get("success")]
    if failed:
        print(f"\n❌ FAILED TASKS")
        print("─" * 60)
        for r in failed:
            task = r.get("task", "unknown")
            model = r.get("model", "unknown").split('/')[-1][:30]
            print(f"  • {task}: {model}")
    
    # Task Details Table
    print(f"\n📋 TASK DETAILS")
    print("─" * 80)
    print(f"  {'Task':<15} {'Model':<25} {'Status':<8} {'Cost':>8} {'Time':>8}")
    print("─" * 80)
    
    for r in data.get("results", []):
        task = r.get("task", "unknown")[:15]
        model = r.get("model", "unknown").split('/')[-1][:25]
        status = "✓ PASS" if r.get("success") else "✗ FAIL"
        cost = f"${r.get('cost', 0):.4f}"
        time_s = f"{r.get('time', 0):.1f}s"
        print(f"  {task:<15} {model:<25} {status:<8} {cost:>8} {time_s:>8}")
    
    print("\n" + "═" * 80)


def generate_png_charts(data: dict, model_results: list[ModelResult], output_dir: Path,
                        publication_quality: bool = False):
    """Generate PNG chart files.
    
    Args:
        publication_quality: If True, generates high-res charts suitable for papers
    """
    if not HAS_MATPLOTLIB:
        print("⚠ matplotlib not installed, skipping PNG generation")
        print("  Install with: pip install matplotlib")
        return []
    
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    
    # Publication-quality settings
    if publication_quality:
        plt.rcParams.update({
            'font.size': 14,
            'axes.titlesize': 16,
            'axes.labelsize': 14,
            'xtick.labelsize': 12,
            'ytick.labelsize': 12,
            'legend.fontsize': 12,
            'figure.dpi': 300,
            'savefig.dpi': 300,
            'savefig.bbox': 'tight',
            'font.family': 'sans-serif',
        })
        dpi = 300
    else:
        dpi = 150
    
    # Use a clean style
    plt.style.use('seaborn-v0_8-whitegrid')
    
    # Color palette for publication
    COLORS = {
        'success': '#27ae60',  # Green
        'warning': '#f39c12',  # Orange  
        'failure': '#e74c3c',  # Red
        'primary': '#3498db',  # Blue
        'secondary': '#9b59b6',  # Purple
    }
    
    # 1. Pass Rate Bar Chart (Horizontal)
    fig, ax = plt.subplots(figsize=(12, max(4, len(model_results) * 0.8)))
    
    # Sort by pass rate for better visualization
    sorted_results = sorted(model_results, key=lambda r: r.pass_rate)
    models = [r.model.split('/')[-1] for r in sorted_results]
    pass_rates = [r.pass_rate * 100 for r in sorted_results]
    
    # Color by performance tier
    colors = [
        COLORS['success'] if r >= 80 else 
        COLORS['warning'] if r >= 50 else 
        COLORS['failure'] 
        for r in pass_rates
    ]
    
    bars = ax.barh(models, pass_rates, color=colors, edgecolor='white', linewidth=0.5)
    ax.set_xlabel('Pass Rate (%)', fontweight='bold')
    ax.set_title('Model Performance Comparison', fontweight='bold', pad=20)
    ax.set_xlim(0, 105)
    
    # Add value labels with task counts
    for i, (bar, rate, result) in enumerate(zip(bars, pass_rates, sorted_results)):
        label = f'{rate:.0f}% ({result.tasks_passed}/{result.tasks_run})'
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
                label, va='center', fontsize=10)
    
    # Add gridlines
    ax.xaxis.grid(True, linestyle='--', alpha=0.7)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    filepath = output_dir / "pass_rate_chart.png"
    plt.savefig(filepath, dpi=dpi, facecolor='white', edgecolor='none')
    plt.close()
    generated.append(filepath)
    
    # 2. Cost vs Performance Scatter (Publication Quality)
    if len(model_results) > 0:
        fig, ax = plt.subplots(figsize=(12, 8))
        
        costs = [r.total_cost for r in model_results]
        pass_rates = [r.pass_rate * 100 for r in model_results]
        labels = [r.model.split('/')[-1] for r in model_results]
        sizes = [max(100, r.tasks_run * 50) for r in model_results]  # Size by tasks run
        
        scatter = ax.scatter(costs, pass_rates, s=sizes, c=pass_rates, 
                            cmap='RdYlGn', vmin=0, vmax=100, alpha=0.8,
                            edgecolors='white', linewidth=2)
        
        # Smart label placement to avoid overlap
        for i, label in enumerate(labels):
            # Offset based on position
            x_off = 8 if costs[i] < max(costs) * 0.7 else -8
            ha = 'left' if x_off > 0 else 'right'
            ax.annotate(label, (costs[i], pass_rates[i]), 
                       textcoords="offset points", xytext=(x_off, 5), 
                       fontsize=10, ha=ha,
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7))
        
        ax.set_xlabel('Total Cost ($)', fontweight='bold')
        ax.set_ylabel('Pass Rate (%)', fontweight='bold')
        ax.set_title('Cost vs Performance Analysis', fontweight='bold', pad=20)
        ax.set_ylim(-5, 110)
        ax.set_xlim(left=-max(costs)*0.05 if costs else 0)
        
        # Add quadrant labels
        if costs and pass_rates:
            mid_cost = (max(costs) + min(costs)) / 2
            ax.axhline(y=50, color='gray', linestyle='--', alpha=0.3)
            ax.axvline(x=mid_cost, color='gray', linestyle='--', alpha=0.3)
            
            # Quadrant annotations
            ax.text(max(costs) * 0.95, 95, 'High Cost\nHigh Performance', 
                   ha='right', va='top', fontsize=9, color='gray', style='italic')
            ax.text(min(costs) + max(costs) * 0.05, 95, 'Low Cost\nHigh Performance', 
                   ha='left', va='top', fontsize=9, color='green', fontweight='bold')
        
        cbar = plt.colorbar(scatter, label='Pass Rate %', shrink=0.8)
        cbar.ax.tick_params(labelsize=10)
        
        ax.grid(True, linestyle='--', alpha=0.3)
        plt.tight_layout()
        filepath = output_dir / "cost_vs_performance.png"
        plt.savefig(filepath, dpi=dpi, facecolor='white', edgecolor='none')
        plt.close()
        generated.append(filepath)
    
    # 3. Cost Breakdown Pie Chart (only if multiple models with costs)
    models_with_cost = [r for r in model_results if r.total_cost > 0]
    if len(models_with_cost) > 1:
        fig, ax = plt.subplots(figsize=(10, 8))
        
        costs = [r.total_cost for r in models_with_cost]
        labels = [r.model.split('/')[-1] for r in models_with_cost]
        
        # Color by model family
        colors = plt.cm.Set3(range(len(costs)))
        
        wedges, texts, autotexts = ax.pie(
            costs, labels=labels, autopct='$%.3f', startangle=90,
            colors=colors, pctdistance=0.75,
            wedgeprops=dict(width=0.6, edgecolor='white', linewidth=2)
        )
        
        # Style the percentage text
        for autotext in autotexts:
            autotext.set_fontsize(10)
            autotext.set_fontweight('bold')
        
        ax.set_title('Cost Distribution by Model', fontweight='bold', pad=20)
        
        # Add total cost in center
        total = sum(costs)
        ax.text(0, 0, f'Total\n${total:.3f}', ha='center', va='center', 
                fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        filepath = output_dir / "cost_breakdown.png"
        plt.savefig(filepath, dpi=dpi, facecolor='white', edgecolor='none')
        plt.close()
        generated.append(filepath)
    
    # 4. Task Results Heatmap (if multiple models and tasks)
    results = data.get("results", [])
    if len(results) > 1:
        # Build matrix
        tasks = sorted(set(r.get("task", "") for r in results))
        models_list = sorted(set(r.get("model", "").split('/')[-1][:20] for r in results))
        
        if len(tasks) > 1 or len(models_list) > 1:
            matrix = []
            for model in models_list:
                row = []
                for task in tasks:
                    found = [r for r in results 
                            if r.get("task") == task and model in r.get("model", "")]
                    if found:
                        row.append(1 if found[0].get("success") else 0)
                    else:
                        row.append(-1)  # Not run
                matrix.append(row)
            
            fig, ax = plt.subplots(figsize=(max(8, len(tasks)), max(4, len(models_list) * 0.5)))
            
            import numpy as np
            matrix_np = np.array(matrix)
            
            cmap = plt.cm.RdYlGn
            im = ax.imshow(matrix_np, cmap=cmap, vmin=0, vmax=1, aspect='auto')
            
            ax.set_xticks(range(len(tasks)))
            ax.set_xticklabels(tasks, rotation=45, ha='right')
            ax.set_yticks(range(len(models_list)))
            ax.set_yticklabels(models_list)
            
            ax.set_title('Task Results by Model (Green=Pass, Red=Fail)')
            
            plt.tight_layout()
            filepath = output_dir / "results_heatmap.png"
            plt.savefig(filepath, dpi=150)
            plt.close()
            generated.append(filepath)
    
    return generated


def generate_html_report(data: dict, model_results: list[ModelResult], 
                         output_dir: Path, charts: list[Path]) -> Path:
    """Generate an HTML report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Build results table rows
    result_rows = ""
    for r in data.get("results", []):
        status_class = "success" if r.get("success") else "failure"
        status_icon = "✓" if r.get("success") else "✗"
        result_rows += f"""
        <tr class="{status_class}">
            <td>{r.get('task', 'unknown')}</td>
            <td>{r.get('model', 'unknown')}</td>
            <td>{status_icon}</td>
            <td>${r.get('cost', 0):.4f}</td>
            <td>{r.get('time', 0):.1f}s</td>
        </tr>"""
    
    # Build model summary rows
    model_rows = ""
    for r in model_results:
        model_rows += f"""
        <tr>
            <td>{r.model}</td>
            <td>{r.tasks_passed}/{r.tasks_run}</td>
            <td>{r.pass_rate * 100:.1f}%</td>
            <td>${r.total_cost:.4f}</td>
            <td>{r.avg_time:.1f}s</td>
        </tr>"""
    
    # Chart images
    chart_html = ""
    for chart in charts:
        rel_path = chart.name
        chart_html += f'<img src="{rel_path}" alt="{chart.stem}" class="chart">\n'
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DDS Agent Benchmark Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #1a1a2e;
            color: #eee;
        }}
        h1, h2, h3 {{ color: #00d4ff; }}
        .header {{
            text-align: center;
            padding: 30px;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: #16213e;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #00d4ff;
        }}
        .stat-label {{
            color: #888;
            font-size: 0.9em;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #333;
        }}
        th {{
            background: #16213e;
            color: #00d4ff;
        }}
        tr.success {{ background: rgba(46, 204, 113, 0.1); }}
        tr.failure {{ background: rgba(231, 76, 60, 0.1); }}
        .charts {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }}
        .chart {{
            max-width: 100%;
            border-radius: 10px;
        }}
        .footer {{
            text-align: center;
            color: #666;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #333;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 DDS Agent Benchmark Report</h1>
        <p>Generated: {timestamp}</p>
    </div>
    
    <div class="summary">
        <div class="stat-card">
            <div class="stat-value">{data.get('total_tasks', 0)}</div>
            <div class="stat-label">Total Tasks</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color: #2ecc71;">{data.get('passed', 0)}</div>
            <div class="stat-label">Passed</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color: #e74c3c;">{data.get('failed', 0)}</div>
            <div class="stat-label">Failed</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{data.get('pass_rate', '0%')}</div>
            <div class="stat-label">Pass Rate</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${data.get('total_cost_usd', 0):.4f}</div>
            <div class="stat-label">Total Cost</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{data.get('total_tokens', 0):,}</div>
            <div class="stat-label">Tokens</div>
        </div>
    </div>
    
    <h2>📊 Model Summary</h2>
    <table>
        <tr>
            <th>Model</th>
            <th>Passed/Total</th>
            <th>Pass Rate</th>
            <th>Cost</th>
            <th>Avg Time</th>
        </tr>
        {model_rows}
    </table>
    
    <h2>📋 Task Results</h2>
    <table>
        <tr>
            <th>Task</th>
            <th>Model</th>
            <th>Status</th>
            <th>Cost</th>
            <th>Time</th>
        </tr>
        {result_rows}
    </table>
    
    <h2>📈 Charts</h2>
    <div class="charts">
        {chart_html}
    </div>
    
    <div class="footer">
        <p>DDS Agent Benchmark Framework</p>
    </div>
</body>
</html>
"""
    
    filepath = output_dir / "report.html"
    with open(filepath, "w") as f:
        f.write(html)
    
    return filepath


def main():
    parser = argparse.ArgumentParser(
        description="Generate benchmark reports and visualizations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_report.py                    # Terminal report only
  python generate_report.py --all              # Everything
  python generate_report.py --publication      # High-res for papers
  python generate_report.py -i results.json    # From specific file
        """
    )
    parser.add_argument("--input", "-i", type=str,
                        help="Input results JSON file (default: latest)")
    parser.add_argument("--html", action="store_true",
                        help="Generate HTML report")
    parser.add_argument("--png", action="store_true",
                        help="Generate PNG charts")
    parser.add_argument("--publication", "-p", action="store_true",
                        help="Generate publication-quality charts (300 DPI)")
    parser.add_argument("--output", "-o", type=str, default="results/reports",
                        help="Output directory")
    parser.add_argument("--all", "-a", action="store_true",
                        help="Generate all outputs (terminal + HTML + PNG)")
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    
    # Find input file
    if args.input:
        input_path = Path(args.input)
    else:
        input_path = find_latest_results(script_dir / "results" / "suites")
    
    if not input_path or not input_path.exists():
        print("❌ No results file found")
        print("   Run benchmarks first: python run_all_benchmarks.py")
        return 1
    
    print(f"📂 Loading: {input_path}")
    data = load_results(input_path)
    model_results = aggregate_by_model(data)
    
    output_dir = script_dir / args.output
    
    # Always print terminal report
    print_terminal_report(data, model_results)
    
    # Generate charts if requested
    charts = []
    if args.png or args.all or args.publication:
        quality = "publication" if args.publication else "standard"
        print(f"\n📊 Generating PNG charts ({quality} quality)...")
        charts = generate_png_charts(
            data, model_results, output_dir,
            publication_quality=args.publication
        )
        for chart in charts:
            print(f"   ✓ {chart}")
    
    # Generate HTML if requested
    if args.html or args.all:
        print(f"\n📄 Generating HTML report...")
        html_path = generate_html_report(data, model_results, output_dir, charts)
        print(f"   ✓ {html_path}")
        print(f"\n   Open in browser: file://{html_path.absolute()}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


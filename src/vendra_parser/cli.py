#!/usr/bin/env python3
"""
Beautiful Command-line interface for the Vendra Quote Parser.
"""

import click
import logging
import os
import sys
import json
import time
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.syntax import Syntax
from rich.align import Align
from rich.columns import Columns
from rich.box import ROUNDED

from .comprehensive_parser import ComprehensivePDFParser

# Initialize Rich console
console = Console()

def setup_logging(verbose: bool, quiet: bool = False):
    """Setup logging configuration."""
    if quiet:
        # In quiet mode, suppress all logging
        logging.basicConfig(level=logging.CRITICAL)
    elif verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        logging.basicConfig(level=logging.WARNING)

def parse_quietly(pdf_path: str):
    """Parse PDF in complete silence, suppressing all output."""
    import os
    import sys
    import logging
    
    # Suppress all logging
    logging.getLogger().setLevel(logging.CRITICAL)
    for logger_name in ['vendra_parser', 'root', 'invoice2data']:
        logging.getLogger(logger_name).setLevel(logging.CRITICAL)
    
    # Redirect both stdout and stderr to /dev/null to suppress all output
    with open(os.devnull, 'w') as devnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = devnull
        sys.stderr = devnull
        try:
            parser = ComprehensivePDFParser()
            result = parser.parse_quote(pdf_path)
            return result
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

def print_header():
    """Print beautiful header."""
    header_text = Text()
    header_text.append("🎯 ", style="bold blue")
    header_text.append("VENDRA QUOTE PARSER", style="bold white on blue")
    header_text.append(" 🎯", style="bold blue")
    
    subtitle = Text("Extract data from supplier PDFs with intelligent parsing", style="italic cyan")
    
    panel = Panel(
        Align.center(header_text + "\n" + subtitle),
        border_style="blue",
        box=ROUNDED,
        padding=(1, 2)
    )
    console.print(panel)

def print_success(message: str):
    """Print a success message with beautiful styling."""
    console.print(f"✅ {message}", style="bold green")

def print_error(message: str):
    """Print an error message with beautiful styling."""
    console.print(f"❌ {message}", style="bold red")

def print_info(message: str):
    """Print an info message with beautiful styling."""
    console.print(f"ℹ️  {message}", style="bold cyan")

def print_warning(message: str):
    """Print a warning message with beautiful styling."""
    console.print(f"⚠️  {message}", style="bold yellow")

def print_step(message: str):
    """Print a step message with beautiful styling."""
    console.print(f"🔹 {message}", style="blue")

def validate_pdf_file(pdf_path: str) -> bool:
    """Validate PDF file exists and is readable."""
    if not os.path.exists(pdf_path):
        print_error(f"File not found: {pdf_path}")
        return False
    
    if not pdf_path.lower().endswith('.pdf'):
        print_error("Please provide a PDF file")
        return False
    
    try:
        with open(pdf_path, 'rb') as f:
            f.read(1024)  # Test if file is readable
        return True
    except Exception as e:
        print_error(f"Cannot read file: {str(e)}")
        return False

def save_results(result: dict, output_file: Optional[str], pdf_path: str, quiet: bool = False) -> bool:
    """Save results to JSON file with beautiful formatting."""
    try:
        if output_file is None or output_file == "":
            pdf_name = Path(pdf_path).stem
            output_file = f"{pdf_name}_parsed.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        if not quiet:
            print_success(f"Results saved to: {output_file}")
        return True
    except Exception as e:
        if not quiet:
            print_error(f"Failed to save file: {str(e)}")
        return False

def get_pdf_path_interactive() -> str:
    """Get PDF path interactively with beautiful prompts."""
    while True:
        pdf_path = Prompt.ask(
            "📄 Enter the path to your PDF quote file",
            default=""
        ).strip()
        
        # Remove quotes if user accidentally includes them
        if pdf_path.startswith("'") and pdf_path.endswith("'"):
            pdf_path = pdf_path[1:-1]
        elif pdf_path.startswith('"') and pdf_path.endswith('"'):
            pdf_path = pdf_path[1:-1]
        
        if pdf_path:
            if validate_pdf_file(pdf_path):
                return pdf_path
        else:
            print_warning("Please provide a valid PDF file path")

def get_output_preference() -> Optional[str]:
    """Get output preference with beautiful interface."""
    console.print("\n💾 [bold cyan]Output Options:[/bold cyan]")
    
    options_table = Table(show_header=False, box=ROUNDED, border_style="cyan")
    options_table.add_column("Option", style="bold")
    options_table.add_column("Description", style="cyan")
    
    options_table.add_row("1", "Show summary only (recommended)")
    options_table.add_row("2", "Save to JSON file")
    options_table.add_row("3", "Both summary and JSON file")
    
    console.print(options_table)
    
    while True:
        choice = Prompt.ask("Enter your choice", choices=["1", "2", "3"], default="1")
        
        if choice == "1":
            return None
        elif choice in ["2", "3"]:
            filename = Prompt.ask(
                "Enter JSON filename (or press Enter for default)",
                default=""
            ).strip()
            return filename if filename else ""
        else:
            print_error("Invalid choice. Please enter 1, 2, or 3.")

def interactive_mode():
    """Interactive mode for PDF parsing with beautiful interface."""
    print_header()
    
    try:
        # Suppress NumPy warnings for interactive mode
        import logging
        logging.getLogger().setLevel(logging.ERROR)
        for logger_name in ['vendra_parser', 'root', 'invoice2data']:
            logging.getLogger(logger_name).setLevel(logging.ERROR)
        
        # Get PDF file path
        pdf_path = get_pdf_path_interactive()
        
        # Set default output file
        output_file = None
        
        # Parse the quote with progress indicator
        print_info(f"Parsing PDF: {pdf_path}")
        print_step("Using parser...")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("🔍 Analyzing PDF structure...", total=None)
            
            # Use quiet parsing to suppress NumPy errors
            progress.update(task, description="📊 Extracting line items and prices...")
            result = parse_quietly(pdf_path)
            
            progress.update(task, description="✨ Finalizing results...")
            time.sleep(0.5)  # Brief pause for visual effect
        
        print_success("Parsing completed successfully!")
        
        # Always output JSON format
        print_json_output(result)
        
        # Save results if requested
        if output_file is not None:
            if output_file == "":
                pdf_name = Path(pdf_path).stem
                output_file = f"{pdf_name}_parsed.json"
            
            if save_results(result, output_file, pdf_path):
                print_info(f"Full results saved to: {output_file}")
        
        print_success("🎉 Quote parsing completed!")
        
        # Ask if user wants to parse another file
        try:
            another = Confirm.ask("\n🔄 Parse another PDF?", default=True)
            if another:
                console.print("\n" + "─" * 60)
                interactive_mode()
                return
            else:
                console.print("\n👋 Thank you for using Vendra Quote Parser!")
                return
        except (EOFError, KeyboardInterrupt):
            console.print("\n👋 Thank you for using Vendra Quote Parser!")
            return
        
    except KeyboardInterrupt:
        print_warning("\n👋 Operation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print_error(f"Failed to parse PDF: {e}")
        sys.exit(1)

def print_summary(result):
    """Print a beautiful summary of the parsed results."""
    try:
        # Handle the new format (list of groups)
        if isinstance(result, list):
            groups = result
            # Calculate summary from groups
            total_qty = sum(int(group.get('quantity', 0)) for group in groups)
            total_cost = sum(float(group.get('totalPrice', 0)) for group in groups)
            total_items = sum(len(group.get('lineItems', [])) for group in groups)
            
            summary = {
                'totalQuantity': str(total_qty),
                'totalCost': f"{total_cost:.2f}",
                'numberOfGroups': len(groups),
                'totalLineItems': total_items
            }
        elif isinstance(result, dict) and "summary" in result and "groups" in result:
            summary = result["summary"]
            groups = result["groups"]
        else:
            print_error("Invalid result format")
            return
            
            # Create summary panel
            summary_text = Text()
            summary_text.append("📊 PARSING SUMMARY\n", style="bold white")
            summary_text.append("─" * 50 + "\n", style="cyan")
            
            # Summary stats
            summary_text.append(f"Total Quantity: {summary.get('totalQuantity', '0')}\n", style="green")
            summary_text.append(f"Total Cost: {summary.get('totalCost', '0')}\n", style="green")
            summary_text.append(f"Number of Groups: {summary.get('numberOfGroups', '0')}\n", style="green")
            
            # Line items breakdown
            total_line_items = sum(len(group.get('lineItems', [])) for group in groups)
            summary_text.append(f"Total Line Items: {total_line_items}\n", style="green")
            
            # Currency info
            if 'calculationSteps' in summary and summary['calculationSteps']:
                first_step = summary['calculationSteps'][0]
                if any(symbol in first_step for symbol in ['$', '£', '€', '¥', '₹']):
                    currency = next(symbol for symbol in ['$', '£', '€', '¥', '₹'] if symbol in first_step)
                    summary_text.append(f"Currency: {currency}\n", style="yellow")
            
            summary_text.append("─" * 50, style="cyan")
            
            summary_panel = Panel(
                summary_text,
                border_style="green",
                box=ROUNDED,
                title="📊 Summary Statistics",
                title_align="center"
            )
            console.print(summary_panel)
            
            # Group details
            for i, group in enumerate(groups, 1):
                line_items = group.get('lineItems', [])
                if line_items:
                    group_text = Text()
                    group_text.append(f"📦 Group {i}:\n", style="bold blue")
                    group_text.append(f"   Quantity: {group.get('quantity', '0')}\n", style="cyan")
                    group_text.append(f"   Unit Price: {group.get('unitPrice', '0')}\n", style="cyan")
                    group_text.append(f"   Total: {group.get('totalPrice', '0')}\n", style="cyan")
                    
                    for j, item in enumerate(line_items, 1):
                        group_text.append(f"   {j}. {item.get('description', 'N/A')}\n", style="white")
                        group_text.append(f"      Qty: {item.get('quantity', '0')} | Price: {item.get('unitPrice', '0')} | Cost: {item.get('cost', '0')}\n", style="dim")
                    
                    group_panel = Panel(
                        group_text,
                        border_style="blue",
                        box=ROUNDED,
                        padding=(0, 1)
                    )
                    console.print(group_panel)
                    
    except Exception as e:
        print_error(f"Error displaying summary: {str(e)}")

def print_json_output(result, quiet=False):
    """Print JSON output with beautiful syntax highlighting."""
    try:
        json_str = json.dumps(result, indent=2, ensure_ascii=False)
        
        if quiet:
            # In quiet mode, just print the raw JSON
            print(json_str)
        else:
            # Normal mode with syntax highlighting
            syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True)
            
            console.print("\n📄 [bold cyan]FULL JSON OUTPUT:[/bold cyan]")
            console.print("─" * 50, style="cyan")
            console.print(syntax)
            console.print("─" * 50, style="cyan")
        
    except Exception as e:
        if not quiet:
            print_error(f"Error displaying JSON: {str(e)}")
        else:
            print(f"Error: {str(e)}", file=sys.stderr)

@click.group(invoke_without_command=True, context_settings=dict(help_option_names=['-h', '--help']))
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--quiet', '-q', is_flag=True, help='Run in headless mode (suppress all output except results)')
@click.pass_context
def cli(ctx, verbose: bool, quiet: bool):
    """
    🎯 VENDRA QUOTE PARSER
    
    Extract data from supplier PDF quotes with automatic currency detection.
    
    Examples:
        vendra-parser parse quote.pdf
        vendra-parser parse quote.pdf --output results.json
        vendra-parser parse quote.pdf --verbose
        vendra-parser parse quote.pdf --quiet
    """
    setup_logging(verbose, quiet)
    
    # If no subcommand is provided, start interactive mode
    if ctx.invoked_subcommand is None:
        interactive_mode()

@cli.command()
@click.argument('pdf_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output JSON file (default: {pdf_name}_parsed.json)')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--summary-only', '-s', is_flag=True, help='Show only summary, not full JSON')
@click.option('--quiet', '-q', is_flag=True, help='Run in headless mode (suppress all output except results)')
def parse(pdf_path: str, output: Optional[str], verbose: bool, summary_only: bool, quiet: bool):
    """Parse a PDF quote and extract data."""
    if not quiet:
        print_header()
    
    if not validate_pdf_file(pdf_path):
        sys.exit(1)
    
    if not quiet:
        print_info(f"Parsing PDF: {pdf_path}")
        print_step("Using parser...")
    
    if quiet:
        # Headless mode - just parse without any output
        result = parse_quietly(pdf_path)
    else:
        # Normal mode with progress indicators
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("🔍 Analyzing PDF structure...", total=None)
            
            parser = ComprehensivePDFParser()
            progress.update(task, description="📊 Extracting line items and prices...")
            
            result = parser.parse_quote(pdf_path)
            
            progress.update(task, description="✨ Finalizing results...")
            time.sleep(0.5)
    
    if result:
        if not quiet:
            print_success("Parsing completed successfully!")
        
        if summary_only and not quiet:
            print_summary(result)
        elif not quiet:
            print_summary(result)
            print_json_output(result)
        elif quiet:
            # In quiet mode, just output the JSON
            print_json_output(result, quiet=True)
        
        if output:
            if save_results(result, output, pdf_path, quiet):
                if not quiet:
                    print_info(f"Full results saved to: {output}")
                # In quiet mode, don't show any save confirmation
    else:
        if not quiet:
            print_error("Failed to parse PDF")
        sys.exit(1)

@cli.command()
@click.argument('pdf_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output JSON file')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--quiet', '-q', is_flag=True, help='Run in headless mode (suppress all output except results)')
def quick(pdf_path: str, output: Optional[str], verbose: bool, quiet: bool):
    """Quick parse - show only summary."""
    if not quiet:
        print_header()
    
    if not validate_pdf_file(pdf_path):
        sys.exit(1)
    
    if not quiet:
        print_info(f"Quick parsing PDF: {pdf_path}")
    
    if quiet:
        # Headless mode - just parse without any output
        result = parse_quietly(pdf_path)
    else:
        # Normal mode with progress indicators
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("🔍 Quick analysis...", total=None)
            
            parser = ComprehensivePDFParser()
            result = parser.parse_quote(pdf_path)
            
            progress.update(task, description="✨ Finalizing...")
            time.sleep(0.3)
    
    if result:
        if not quiet:
            print_success("Quick parsing completed!")
            print_summary(result)
        else:
            # In quiet mode, just output the JSON
            print_json_output(result, quiet=True)
        
        if output and save_results(result, output, pdf_path, quiet):
            if not quiet:
                print_info(f"Results saved to: {output}")
    else:
        if not quiet:
            print_error("Failed to parse PDF")
        sys.exit(1)

@cli.command()
def version():
    """Show version information."""
    from . import __version__
    
    version_text = Text()
    version_text.append("🎯 VENDRA QUOTE PARSER\n", style="bold blue")
    version_text.append(f"Version: {__version__}\n", style="green")
    version_text.append("Intelligent PDF quote parsing with automatic currency detection", style="cyan")
    
    version_panel = Panel(
        version_text,
        border_style="blue",
        box=ROUNDED,
        title="📦 Version Info",
        title_align="center"
    )
    console.print(version_panel)

@cli.command()
def info():
    """Show parser capabilities and information."""
    capabilities_text = Text()
    capabilities_text.append("🎯 VENDRA QUOTE PARSER CAPABILITIES\n", style="bold white")
    capabilities_text.append("─" * 50 + "\n", style="cyan")
    
    features = [
        "✅ Multi-format PDF parsing (invoice2data, OCR, direct text)",
        "✅ Automatic currency detection (USD, GBP, EUR, JPY, INR)",
        "✅ Intelligent line item extraction",
        "✅ Noise filtering and validation",
        "✅ Shipping charges and discounts handling",
        "✅ Summary adjustments (tax, shipping, discounts)",
        "✅ Unicode support and proper formatting",
        "✅ Fallback mechanisms for robust parsing",
        "✅ Interactive CLI with beautiful interface"
    ]
    
    for feature in features:
        capabilities_text.append(f"{feature}\n", style="green")
    
    capabilities_text.append("─" * 50 + "\n", style="cyan")
    capabilities_text.append("Supports any PDF quote format automatically!", style="bold yellow")
    
    capabilities_panel = Panel(
        capabilities_text,
        border_style="green",
        box=ROUNDED,
        title="🚀 Parser Capabilities",
        title_align="center"
    )
    console.print(capabilities_panel)

if __name__ == '__main__':
    cli() 
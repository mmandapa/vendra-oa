#!/usr/bin/env python3
"""
Official Vendra PDF Parser CLI
Provides intelligent parsing with automatic fallback mechanisms.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print = print

from .comprehensive_parser import ComprehensivePDFParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize console for rich output
if RICH_AVAILABLE:
    console = Console()
else:
    console = None

def setup_parser():
    """Set up command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Vendra PDF Parser - Intelligent PDF Quote/Invoice Parser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  vendra-parser parse document.pdf                    # Parse and output to console
  vendra-parser parse document.pdf -o result.json     # Parse and save to file
  vendra-parser parse document.pdf --verbose          # Parse with detailed logging
  vendra-parser                                       # Start interactive mode
        """
    )
    
    # Main command
    parser.add_argument(
        'command',
        nargs='?',
        choices=['parse', 'interactive'],
        help='Command to execute (default: interactive)'
    )
    
    # PDF path argument
    parser.add_argument(
        'pdf_path',
        nargs='?',
        help='Path to PDF file to parse'
    )
    
    # Output file
    parser.add_argument(
        '-o', '--output',
        help='Output file path (default: print to console)'
    )
    
    # Verbose logging
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    return parser

def interactive_mode(verbose: bool = False):
    """Interactive mode with rich UI."""
    if not RICH_AVAILABLE:
        basic_interactive_mode()
        return
    
    console.print(Panel.fit(
        "[bold blue]Vendra PDF Parser[/bold blue]\n"
        "[dim]Intelligent PDF Quote/Invoice Parser[/dim]",
        border_style="blue"
    ))
    
    while True:
        console.print("\n[bold]📋 Main Menu[/bold]")
        console.print("1. [cyan]Parse PDF[/cyan] - Intelligent parsing with automatic fallbacks")
        console.print("2. [cyan]Help[/cyan] - Documentation and examples")
        console.print("3. [cyan]Exit[/cyan] - Quit the application")
        
        choice = Prompt.ask(
            "Select an option",
            choices=["1", "2", "3"],
            default="1"
        )
        
        if choice == "1":
            parse_interactive(verbose)
        elif choice == "2":
            help_interactive()
        elif choice == "3":
            console.print("[green]👋 Goodbye![/green]")
            break

def parse_interactive(verbose: bool):
    """Interactive parsing with rich UI."""
    console.print("\n[bold]🔍 Intelligent PDF Parsing[/bold]")
    console.print("[dim]This will automatically try multiple parsing methods and select the best result.[/dim]")
    
    # Get PDF path
    pdf_path = Prompt.ask("Enter PDF file path")
    if not Path(pdf_path).exists():
        console.print(f"[red]❌ File not found: {pdf_path}[/red]")
        return
    
    # Get output preference
    output_choice = Prompt.ask(
        "How would you like to save results?",
        choices=["1", "2"],
        default="1"
    )
    
    output_file = None
    if output_choice == "2":
        output_file = Prompt.ask("Enter output file path")
    
    # Parse with progress indicator
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Parsing PDF...", total=None)
        
        try:
            parser = ComprehensivePDFParser()
            result = parser.parse_quote(pdf_path)
            
            progress.update(task, description="✅ Parsing completed!")
            
            # Display results - always JSON format
            if output_choice == "1":
                print(json.dumps(result, indent=2, ensure_ascii=False))
            
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                console.print(f"[green]💾 Results saved to: {output_file}[/green]")
            
        except Exception as e:
            progress.update(task, description="❌ Parsing failed!")
            console.print(f"[red]Error: {e}[/red]")

def help_interactive():
    """Interactive help and documentation."""
    console.print("\n[bold]📖 Help & Documentation[/bold]")
    
    help_text = """
[bold]Vendra PDF Parser[/bold]

This tool extracts structured quote data from supplier PDFs using intelligent
fallback mechanisms and multiple parsing strategies.

[bold]Key Features:[/bold]
• Intelligent fallback system with multiple parsing methods
• Automatic currency detection and formatting
• Support for various PDF formats (scanned, text-based, etc.)
• Noise filtering and intelligent line item detection
• Professional JSON output with proper Unicode handling

[bold]How It Works:[/bold]
The parser automatically tries multiple methods in order of reliability:
1. invoice2data (if template available)
2. vendra-parser CLI with OCR
3. Multi-format parser
4. Manual extraction as last resort

Each method is scored for quality, and the best result is automatically selected.
The system handles currency detection, noise filtering, and formatting automatically.
    """
    
    console.print(Panel(help_text, title="Help", border_style="blue"))
    Prompt.ask("Press Enter to continue")

def basic_interactive_mode():
    """Basic interactive mode without rich library."""
    print("🎯 VENDRA PDF PARSER")
    print("=" * 50)
    
    while True:
        print("\n📋 Main Menu:")
        print("1. Parse PDF (Intelligent parsing with automatic fallbacks)")
        print("2. Help")
        print("3. Exit")
        
        choice = input("\nSelect option (1-3): ").strip()
        
        if choice == "1":
            pdf_path = input("Enter PDF file path: ").strip()
            if Path(pdf_path).exists():
                try:
                    parser = ComprehensivePDFParser()
                    result = parser.parse_quote(pdf_path)
                    print("\n✅ Parsing completed!")
                    print(json.dumps(result, indent=2, ensure_ascii=False))
                except Exception as e:
                    print(f"❌ Error: {e}")
            else:
                print(f"❌ File not found: {pdf_path}")
        elif choice == "2":
            print("Help documentation coming soon...")
        elif choice == "3":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please try again.")

def parse_pdf(pdf_path: str, output: Optional[str] = None, verbose: bool = False):
    """Parse PDF with intelligent fallback mechanisms."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("🚀 Starting intelligent PDF parsing with fallback mechanisms")
    
    try:
        parser = ComprehensivePDFParser()
        result = parser.parse_quote(pdf_path)
        
        if output:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Results saved to: {output}")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        logger.info("🎉 Intelligent parsing completed successfully!")
        return result
        
    except Exception as e:
        logger.error(f"❌ Intelligent parsing failed: {e}")
        sys.exit(1)

def main():
    """Main CLI entry point."""
    parser = setup_parser()
    args = parser.parse_args()
    
    # If no command provided, start interactive mode
    if not args.command:
        interactive_mode()
        return
    
    # Handle interactive command
    if args.command == 'interactive':
        interactive_mode(args.verbose)
        return
    
    # Handle parse command
    if args.command == 'parse':
        if not args.pdf_path:
            logger.error("❌ PDF file path is required for parse command")
            sys.exit(1)
        
        if not Path(args.pdf_path).exists():
            logger.error(f"❌ PDF file not found: {args.pdf_path}")
            sys.exit(1)
        
        parse_pdf(args.pdf_path, args.output, args.verbose)
        return
    
    logger.error(f"❌ Unknown command: {args.command}")
    sys.exit(1)

if __name__ == '__main__':
    main() 
#!/usr/bin/env python3
"""
Command-line interface for the Vendra Quote Parser.
"""

import click
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from .ocr_parser import OCRParser, DynamicOCRParser


def get_pdf_path() -> str:
    """Prompt user to provide PDF file path."""
    while True:
        # Manual path entry only
        pdf_path = input("\n📄 Please enter the path to your PDF quote file: ").strip()
        
        if not pdf_path:
            print("❌ No file path provided. Please try again.")
            continue
            
        # Remove quotes if user added them
        pdf_path = pdf_path.strip('"\'')
        
        if not os.path.exists(pdf_path):
            print(f"❌ File not found: {pdf_path}")
            print("Please check the file path and try again.")
            continue
            
        if not pdf_path.lower().endswith('.pdf'):
            print("❌ File must be a PDF (.pdf extension)")
            continue
            
        return pdf_path



def get_output_preference() -> Optional[str]:
    """Ask user for output preference."""
    while True:
        choice = input("\n💾 How would you like to save the results?\n"
                      "1. Print to terminal only\n"
                      "2. Save to JSON file\n"
                      "3. Both\n"
                      "Enter your choice (1-3): ").strip()
        
        if choice == "1":
            return None
        elif choice == "2":
            filename = input("Enter JSON filename (or press Enter for 'quote_result.json'): ").strip()
            return filename if filename else "quote_result.json"
        elif choice == "3":
            filename = input("Enter JSON filename (or press Enter for 'quote_result.json'): ").strip()
            return filename if filename else "quote_result.json"
        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")


def get_parser_choice() -> str:
    """Use OCR parser (the only recommended option)."""
    print("\n🔧 Using OCR Parser (optimized for all PDF formats)")
    print("   • Handles scanned and text-based documents")
    print("   • Uses advanced pattern recognition")
    print("   • Best accuracy for quote extraction")
    return "ocr"


@click.group(invoke_without_command=True)
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.pass_context
def cli(ctx, verbose: bool):
    """Vendra Quote Parser - Extract structured data from supplier PDFs."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # If no subcommand is provided, run the interactive mode
    if ctx.invoked_subcommand is None:
        interactive_mode()


def interactive_mode():
    """Interactive mode for PDF parsing."""
    print("🎯 VENDRA QUOTE PARSER")
    print("=" * 50)
    print("This tool extracts structured quote data from supplier PDFs.")
    print("It will help you parse pricing, quantities, and line items.")
    print("=" * 50)
    
    try:
        # Get PDF file path
        pdf_path = get_pdf_path()
        
        # Choose parser
        parser_type = get_parser_choice()
        
        # Get output preference
        output_file = get_output_preference()
        
        # Parse the quote
        print(f"\n🔄 Parsing PDF: {pdf_path}")
        print(f"📊 Using OCR Parser for optimal accuracy...")
        
        parser = OCRParser()
        
        # Parse and get results
        result = parser.parse_quote_to_json(pdf_path, output_file)
        
        # Display results
        print("\n✅ Parsing completed successfully!")
        print("=" * 50)
        
        if output_file is None or output_file == "both":
            print("\n📋 PARSED RESULTS:")
            print(result)
        
        if output_file:
            print(f"\n💾 Results saved to: {output_file}")
        
        # Show summary
        try:
            import json
            parsed_data = json.loads(result) if isinstance(result, str) else result
            
            # Handle new structure with summary and groups
            if isinstance(parsed_data, dict) and "groups" in parsed_data:
                summary = parsed_data.get("summary", {})
                groups = parsed_data.get("groups", [])
                
                print(f"\n📈 SUMMARY:")
                print(f"   • Total Quantity: {summary.get('totalQuantity', '0')}")
                print(f"   • Total Unit Price Sum: ${summary.get('totalUnitPriceSum', '0')}")
                print(f"   • Total Cost: ${summary.get('totalCost', '0')}")
                print(f"   • Found {len(groups)} quote group(s)")
                
                for i, group in enumerate(groups, 1):
                    print(f"   • Group {i}: Qty {group['quantity']}, "
                          f"Unit Price ${group['unitPrice']}, "
                          f"Total ${group['totalPrice']}")
                    print(f"     Line items: {len(group['lineItems'])}")
            else:
                # Fallback for old format
                print(f"\n📈 SUMMARY:")
                print(f"   • Found {len(parsed_data)} quote group(s)")
                for i, group in enumerate(parsed_data, 1):
                    print(f"   • Group {i}: Qty {group['quantity']}, "
                          f"Unit Price ${group['unitPrice']}, "
                          f"Total ${group['totalPrice']}")
                    print(f"     Line items: {len(group['lineItems'])}")
        
        except Exception as e:
            print(f"⚠️  Could not display summary: {e}")
        
        print("\n🎉 Thank you for using Vendra Quote Parser!")
        
    except KeyboardInterrupt:
        print("\n\n👋 Operation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Please check your PDF file and try again.")
        sys.exit(1)


@cli.command()
@click.argument('pdf_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output JSON file path')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def parse(pdf_path: str, output: Optional[str], verbose: bool):
    """Parse supplier quote PDF and extract structured data."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        parser = DynamicOCRParser()
        result = parser.parse_quote_to_json(pdf_path, output)
        
        if not output:
            print(result)
        
        click.echo("Quote parsing completed successfully!")
        
    except Exception as e:
        click.echo(f"Error parsing quote: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.argument('pdf_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output JSON file path')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def parse_advanced(pdf_path: str, output: Optional[str], verbose: bool):
    """Parse supplier quote PDF using advanced parser with enhanced pattern matching."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        parser = DynamicOCRParser()
        result = parser.parse_quote_to_json(pdf_path, output)
        
        if not output:
            print(result)
        
        click.echo("Advanced quote parsing completed successfully!")
        
    except Exception as e:
        click.echo(f"Error parsing quote: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.argument('pdf_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output JSON file path')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def parse_ocr(pdf_path: str, output: Optional[str], verbose: bool):
    """Parse supplier quote PDF using OCR for image-based text extraction."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        parser = OCRParser()
        result = parser.parse_quote_to_json(pdf_path, output)
        
        if not output:
            print(result)
        
        click.echo("OCR quote parsing completed successfully!")
        
    except Exception as e:
        click.echo(f"Error parsing quote: {e}", err=True)
        raise click.Abort()


@cli.command()
def version():
    """Show version information."""
    from . import __version__
    click.echo(f"Vendra Quote Parser v{__version__}")


if __name__ == "__main__":
    cli() 
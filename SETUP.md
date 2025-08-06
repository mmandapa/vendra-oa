# Vendra Quote Parser - Setup Instructions

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [System Dependencies](#system-dependencies)
- [Python Environment Setup](#python-environment-setup)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)
- [Development Setup](#development-setup)

## Prerequisites

### System Requirements
- **Operating System**: macOS, Linux, or Windows
- **Python**: 3.8 or higher
- **Memory**: Minimum 2GB RAM (4GB+ recommended for large PDFs)
- **Storage**: At least 100MB free space

### Required System Dependencies

#### macOS
```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python and system dependencies
brew install python@3.11
brew install tesseract
brew install poppler
```

#### Ubuntu/Debian
```bash
# Update package list
sudo apt update

# Install Python and system dependencies
sudo apt install python3 python3-pip python3-venv
sudo apt install tesseract-ocr tesseract-ocr-eng
sudo apt install poppler-utils
sudo apt install libpoppler-cpp-dev
```

#### Windows
1. **Python**: Download and install from [python.org](https://www.python.org/downloads/)
2. **Tesseract**: Download from [UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
3. **Poppler**: Download from [poppler releases](https://github.com/oschwartz10612/poppler-windows/releases)

## Installation

### Method 1: Using pip (Recommended)

```bash
# Clone the repository
git clone https://github.com/mmandapa/vendra-oa.git
cd vendra-oa

# Create a virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install the package
pip install -e .
```

### Method 2: Using requirements.txt

```bash
# Clone the repository
git clone https://github.com/mmandapa/vendra-oa.git
cd vendra-oa

# Create a virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### Method 3: Development Installation

```bash
# Clone the repository
git clone https://github.com/mmandapa/vendra-oa.git
cd vendra-oa

# Create a virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows

# Install with development dependencies
pip install -e ".[dev]"
```

## Python Environment Setup

### Virtual Environment Best Practices

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows

# Verify Python version
python --version  # Should be 3.8 or higher

# Upgrade pip
pip install --upgrade pip

# Install the package
pip install -e .
```

### Environment Variables (Optional)

Create a `.env` file in the project root for custom configurations:

```bash
# .env file
VENDRA_LOG_LEVEL=INFO
VENDRA_OUTPUT_DIR=./output
VENDRA_TEMP_DIR=./temp
```

## Usage

### Command Line Interface

The parser provides a beautiful command-line interface with multiple modes:

#### Interactive Mode (Default)
```bash
# Start interactive mode
vendra-parser

# Or with verbose logging
vendra-parser --verbose
```

#### Direct PDF Parsing
```bash
# Parse a specific PDF file
vendra-parser parse path/to/quote.pdf

# Parse with custom output file
vendra-parser parse path/to/quote.pdf --output results.json

# Parse with summary only
vendra-parser parse path/to/quote.pdf --summary-only

# Parse with verbose logging
vendra-parser parse path/to/quote.pdf --verbose
```

#### Quick Mode (Headless)
```bash
# Quick parsing without interactive prompts
vendra-parser quick path/to/quote.pdf

# Quick parsing with custom output
vendra-parser quick path/to/quote.pdf --output results.json
```

#### Other Commands
```bash
# Show version information
vendra-parser version

# Show system information
vendra-parser info

# Show help
vendra-parser --help
```

### Python API Usage

```python
from vendra_parser.comprehensive_parser import ComprehensivePDFParser

# Initialize parser
parser = ComprehensivePDFParser()

# Parse a PDF file
result = parser.parse_quote("path/to/quote.pdf")

# Access extracted data
print(f"Total Cost: {result.get('total_cost', 'N/A')}")
print(f"Line Items: {len(result.get('line_items', []))}")
print(f"Currency: {result.get('currency', 'N/A')}")
```

### Output Format

The parser returns structured JSON data:

```json
{
  "total_cost": 1250.00,
  "currency": "USD",
  "line_items": [
    {
      "description": "Steel Bracket 2x4",
      "quantity": 10,
      "unit_price": 25.00,
      "total_price": 250.00
    }
  ],
  "supplier_info": {
    "name": "ABC Manufacturing",
    "contact": "sales@abc.com"
  },
  "quote_date": "2024-01-15",
  "quote_number": "Q-2024-001"
}
```

## Troubleshooting

### Common Issues

#### 1. Tesseract Not Found
**Error**: `tesseract: command not found`

**Solution**:
```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-eng

# Windows
# Download and install from https://github.com/UB-Mannheim/tesseract/wiki
```

#### 2. PDF Processing Errors
**Error**: `PDF processing failed`

**Solutions**:
- Ensure PDF is not password-protected
- Check if PDF is corrupted
- Try with different PDF files
- Enable verbose logging: `vendra-parser parse file.pdf --verbose`

#### 3. Memory Issues
**Error**: `MemoryError` or slow processing

**Solutions**:
- Close other applications to free memory
- Process smaller PDFs first
- Increase system swap space
- Use `--quiet` flag to reduce memory usage

#### 4. Import Errors
**Error**: `ModuleNotFoundError`

**Solution**:
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

#### 5. Permission Errors
**Error**: `Permission denied`

**Solution**:
```bash
# Check file permissions
ls -la path/to/quote.pdf

# Fix permissions if needed
chmod 644 path/to/quote.pdf
```

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
# Enable verbose logging
vendra-parser parse file.pdf --verbose

# Check system information
vendra-parser info
```

### Performance Optimization

1. **Use SSD storage** for faster file I/O
2. **Close unnecessary applications** to free memory
3. **Process PDFs in batches** for better resource management
4. **Use `--quiet` flag** for headless processing

## Development Setup

### Installing Development Dependencies

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Install additional development tools
pip install pre-commit
pip install jupyter
```

### Running Tests

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=vendra_parser

# Run specific test file
pytest tests/test_parser.py

# Run tests with verbose output
pytest -v
```

### Code Quality Tools

```bash
# Format code with Black
black src/

# Check code style with flake8
flake8 src/

# Type checking with mypy
mypy src/

# Run all quality checks
pre-commit run --all-files
```

### Project Structure

```
vendra-oa/
├── src/
│   └── vendra_parser/
│       ├── __init__.py
│       ├── adaptive_parser.py
│       ├── cli.py
│       ├── comprehensive_parser.py
│       ├── domain_parser.py
│       ├── invoice2data_parser.py
│       ├── models.py
│       ├── multi_format_parser.py
│       ├── ocr_parser.py
│       └── smart_classifier.py
├── tests/
├── pyproject.toml
├── requirements.txt
├── README.md
└── SETUP.md
```

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Run tests: `pytest`
5. Format code: `black src/`
6. Commit changes: `git commit -m "Add feature"`
7. Push to branch: `git push origin feature-name`
8. Create a Pull Request

## Support

For additional support:

1. **Check the troubleshooting section** above
2. **Review the README.md** for detailed project information
3. **Enable verbose logging** for debugging: `vendra-parser --verbose`
4. **Open an issue** on GitHub with detailed error information

## License

This project is licensed under the MIT License. See the LICENSE file for details. 
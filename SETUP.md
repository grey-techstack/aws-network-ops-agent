# Setup Guide

## Prerequisites

- Python 3.9 or higher
- pip (Python package manager)
- AWS CLI configured (for deployment)

## Installation Steps

### 1. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Package in Development Mode

```bash
pip install -e .
```

### 4. Verify Installation

```bash
# Run tests
pytest

# Run specific test markers
pytest -m unit
pytest -m property
```

## Next Steps

See `.kiro/specs/aws-ops-agent/tasks.md` for implementation tasks.

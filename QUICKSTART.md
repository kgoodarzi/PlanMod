# Quick Start Guide

## Installation

### Option 1: Using Poetry (Recommended)

```bash
# Install Poetry if you don't have it
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

### Option 2: Using pip

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

1. Copy environment template:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your VLM API credentials:
   ```bash
   # For Claude (Anthropic)
   VLM_API_KEY=your_anthropic_api_key
   VLM_API_ENDPOINT=https://api.anthropic.com/v1/messages
   VLM_MODEL=claude-3-opus-20240229

   # OR for OpenAI GPT-4 Vision
   VLM_API_KEY=your_openai_api_key
   VLM_API_ENDPOINT=https://api.openai.com/v1/chat/completions
   VLM_MODEL=gpt-4-vision-preview
   ```

## Generate Sample Files

```bash
# Generate synthetic DXF samples
python scripts/generate_samples.py
```

This creates:
- `samples/wing.dxf` - Simple wing planform
- `samples/fuselage.dxf` - Fuselage side/top views
- `samples/rendered/` - PNG renderings for VLM testing

## Run the Pipeline

### Process a DXF File

```bash
# Process a DXF through the full pipeline
python -m src.cli.main process samples/wing.dxf output/

# This will:
# 1. Parse and render the DXF
# 2. Call VLM for component detection
# 3. Build scene graph
# 4. Calculate mass properties
# 5. Export regenerated DXF and JSON reports
```

Output files:
- `output/rendered/` - Rendered PNG images
- `output/scene_graph.json` - Scene graph structure
- `output/mass_properties.json` - Mass and CG data
- `output/regenerated.dxf` - Regenerated drawing

### Replace a Component

```bash
# Replace a component (requires component ID from scene graph)
python -m src.cli.main replace samples/wing.dxf spar_0 stick_1_8_x_1_4 output/
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/
```

## Troubleshooting

### VLM API Errors

If VLM calls fail:
- Check your API key is set correctly in `.env`
- Verify API endpoint URL matches your provider
- Check API rate limits and quotas
- The pipeline will continue with empty annotations if VLM fails

### Missing Dependencies

If you get import errors:
```bash
# Reinstall dependencies
poetry install
# or
pip install -r requirements.txt
```

### Sample Generation Fails

If sample generation fails:
- Ensure ezdxf is installed: `pip install ezdxf`
- Check Python version (requires 3.11+)

## Next Steps

1. **Test with your own DXF files**: Place DXF files in a directory and process them
2. **Customize component database**: Edit `data/components.json` to add your own parts
3. **Enhance VLM prompts**: Modify prompts in `src/vlm_client/client.py` for better detection
4. **Deploy to AWS**: See `infra/terraform/README.md` for cloud deployment

## Architecture Overview

```
DXF File
  ↓
DXF Parser → PNG Images
  ↓
VLM Client → Component Annotations
  ↓
Scene Graph Builder → 3D Scene Graph
  ↓
Component Replacement (optional)
  ↓
Mass/CG Calculator → Properties
  ↓
DXF Exporter → Regenerated DXF
```

## Key Components

- **DXF Parser**: Reads DXF files and renders to images
- **VLM Client**: Calls vision-language model for component detection
- **Scene Graph**: 3D representation of aircraft structure
- **Component DB**: Database of balsa model parts
- **Replacement Engine**: Replaces components with structural adjustments
- **Mass Calculator**: Computes weight and center of gravity
- **DXF Exporter**: Regenerates 2D drawings from scene graph


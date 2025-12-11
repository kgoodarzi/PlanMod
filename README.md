# PlanMod: Balsa Model Aircraft Drawing Processor

A cloud-backed pipeline for processing balsa stick-and-tissue model aircraft drawings, enabling component replacement, structural analysis, and automated drawing regeneration.

## Overview

PlanMod takes engineering drawings (DXF, PDF, PNG, JPG) of balsa model aircraft structures and uses a Vision-Language Model (VLM) to interpret the drawings, identify components, and reconstruct a structured 3D scene graph. Users can replace components (e.g., different wood sizes, materials) and the system automatically updates dependent parts to maintain structural integrity, regenerates 2D drawings, and computes mass properties.

## Architecture

### Core Components

1. **Ingestion**: Parse DXF files and render to raster images for VLM processing
2. **VLM Integration**: Vision-language model for view detection and component recognition
3. **Scene Graph**: 3D representation of aircraft structure with components and relationships
4. **Component Database**: Catalog of typical balsa model parts with material properties
5. **Replacement Logic**: Component substitution with structural integrity heuristics
6. **Regeneration**: 2D orthographic projection back to DXF format
7. **Mass Properties**: Weight and center of gravity calculations

### Technology Stack

- **Backend**: Python 3.11+
- **Dependency Management**: Poetry
- **DXF Processing**: ezdxf
- **Rendering**: matplotlib, PIL
- **VLM**: Managed API (Claude/GPT-4 Vision or similar)
- **Cloud**: AWS (S3, Lambda, Fargate, API Gateway)
- **Infrastructure**: Terraform

## MVP Milestones

### ✅ Stage 1: Foundation
- [x] Project structure and dependency management
- [x] DXF parsing and PNG rendering
- [x] VLM client module with API integration
- [x] Basic view/component detection

### ✅ Stage 2: Core Pipeline
- [x] Scene graph construction from DXF + VLM output
- [x] Component database with seed data
- [x] Single-component replacement logic
- [x] Basic DXF regeneration
- [x] Mass/CG calculation

### 📋 Stage 3: Enhancement
- [ ] Multi-component replacement
- [ ] Improved structural heuristics
- [ ] Additional sample drawings
- [ ] CLI interface improvements

### ✅ Stage 4: Cloud Deployment
- [x] AWS infrastructure scaffolding
- [ ] S3 integration for file storage
- [ ] Lambda/Fargate deployment
- [ ] API Gateway endpoints

## Installation

### Prerequisites

- Python 3.11 or higher
- Poetry (or pip/uv)

### Setup

```bash
# Install dependencies
poetry install

# Or with pip
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your VLM API credentials
```

### Environment Variables

```bash
VLM_API_KEY=your_api_key_here
VLM_API_ENDPOINT=https://api.example.com/v1/vision
VLM_MODEL=claude-3-opus-20240229  # or gpt-4-vision-preview
```

## Usage

### CLI Interface

```bash
# Process a DXF file
poetry run python -m src.cli.main process samples/wing.dxf

# Replace a component
poetry run python -m src.cli.main replace samples/wing.dxf --component spar_1 --replacement stick_3_16_x_1_4

# Generate mass report
poetry run python -m src.cli.main analyze samples/wing.dxf
```

### Python API

```python
from src.ingestion.dxf_parser import DXFParser
from src.vlm_client.client import VLMClient
from src.scene.scene_graph import SceneGraphBuilder

# Parse and render DXF
parser = DXFParser("samples/wing.dxf")
images = parser.render_views()

# Call VLM
vlm = VLMClient()
annotations = vlm.analyze_drawing(images)

# Build scene graph
builder = SceneGraphBuilder(parser, annotations)
scene = builder.build()
```

## Project Structure

```
PlanMod/
├── README.md
├── progress.md
├── pyproject.toml
├── requirements.txt
├── samples/
│   ├── wing.dxf
│   ├── fuselage.dxf
│   └── rendered/
├── data/
│   └── components.json
├── src/
│   ├── ingestion/
│   ├── vlm_client/
│   ├── scene/
│   ├── components/
│   ├── geometry/
│   ├── export/
│   └── cli/
└── infra/
    └── terraform/
```

## Development

### Running Tests

```bash
poetry run pytest
```

### Generating Samples

```bash
poetry run python scripts/generate_samples.py
```

## Non-Goals (MVP)

- Fine-tuning custom VLM models
- Complex 3D CAD operations
- Real-time collaborative editing
- Advanced structural analysis (FEA)
- Production-grade web UI

## Future Enhancements

- PDF/PNG/JPG input support
- Fine-tuned VLM for engineering drawings
- LLM-powered natural language component replacement requests
- Advanced structural analysis and load calculations
- Web-based UI with real-time preview

## License

MIT


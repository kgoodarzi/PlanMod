# PlanMod

**Drawing to DXF Conversion Pipeline with AI-powered Component Recognition**

PlanMod is a serverless cloud-based pipeline that converts engineering and model aircraft drawings (PDF, JPG, PNG) into structured DXF files with component-level reasoning. The system combines classical computer vision, vision-language models (VLM), and large language models (LLM) to achieve semantic understanding of technical drawings.

## Features

- 📄 **Multi-format Input**: Supports PDF, PNG, JPG, DXF, and DWG files
- 🔍 **AI-powered Analysis**: Uses Claude VLM for intelligent drawing interpretation
- 📐 **Vector Output**: Generates clean, structured DXF files
- 🧩 **Component Recognition**: Identifies ribs, formers, spars, and other parts
- 🔄 **Substitution Engine**: Replace components with alternatives
- ⚖️ **Mass Calculation**: Estimates weight and center of gravity
- 🌐 **Modern Web UI**: React-based interface for easy operation

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- AWS Account (for cloud deployment)
- Docker (optional, for local development)

### Local Development

1. **Clone and Setup**
   ```bash
   git clone <repository>
   cd PlanMod
   
   # Create virtual environment
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   
   # Install Python dependencies
   pip install -r requirements.txt
   ```

2. **Configure AWS Credentials**
   ```bash
   # Copy the config template
   cp infrastructure/config/aws_config.yaml infrastructure/config/aws_config.local.yaml
   
   # Edit with your credentials
   # NEVER commit aws_config.local.yaml!
   ```

3. **Start Backend API**
   ```bash
   python -m backend.api.server
   # API available at http://localhost:8000
   ```

4. **Start Frontend**
   ```bash
   cd frontend
   npm install
   npm run dev
   # UI available at http://localhost:5173
   ```

### Docker Development

```bash
# Start all services
docker-compose up -d

# API: http://localhost:8000
# UI:  http://localhost:5173
```

## AWS Deployment

### Infrastructure Setup

1. **Configure AWS**
   Edit `infrastructure/config/aws_config.yaml` with your settings.

2. **Deploy with CDK**
   ```bash
   cd infrastructure/cdk
   pip install -r requirements.txt
   
   # Bootstrap CDK (first time only)
   cdk bootstrap
   
   # Deploy stacks
   cdk deploy --all
   ```

### Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   S3        │     │  DynamoDB   │     │   Bedrock   │
│  (Storage)  │     │  (Metadata) │     │  (VLM/LLM)  │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────┬───────┴───────────────────┘
                   │
         ┌─────────┴─────────┐
         │   Step Functions  │
         │   (Orchestration) │
         └─────────┬─────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───┴───┐    ┌────┴────┐    ┌────┴────┐
│Ingest │    │ Vision  │    │   DXF   │
│Lambda │    │ Lambda  │    │  Lambda │
└───────┘    └─────────┘    └─────────┘
```

## Project Structure

```
PlanMod/
├── backend/                  # Python backend
│   ├── api/                 # FastAPI REST API
│   ├── ingest/              # File ingestion
│   ├── vision/              # VLM + CV analysis
│   ├── vlm_client/          # VLM abstraction
│   ├── llm_client/          # LLM abstraction
│   ├── ocr/                 # Text extraction
│   ├── vectorization/       # Image to vector
│   ├── scene_graph/         # Semantic model
│   ├── dxf_writer/          # DXF generation
│   ├── component_db/        # Component catalog
│   ├── transform/           # Substitutions
│   └── orchestration/       # Pipeline coordination
│
├── frontend/                 # React web UI
├── infrastructure/          # AWS CDK IaC
├── samples/                 # Sample drawings
└── tests/                   # Test suite
```

## Configuration

Configuration is loaded from `infrastructure/config/aws_config.yaml`:

```yaml
aws:
  region: us-east-1
  profile: default

deployment:
  environment: dev
  stack_prefix: planmod

ai:
  bedrock:
    vlm_model_id: anthropic.claude-3-5-sonnet-20241022-v2:0
    llm_model_id: anthropic.claude-3-5-sonnet-20241022-v2:0
```

For local development with secrets, create `aws_config.local.yaml` (gitignored).

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/jobs` | Create processing job |
| GET | `/jobs/{id}` | Get job status |
| POST | `/jobs/{id}/upload` | Upload input file |
| POST | `/jobs/{id}/process` | Start processing |
| GET | `/jobs/{id}/scene-graph` | Get scene graph |
| POST | `/jobs/{id}/substitute` | Apply substitutions |
| GET | `/jobs/{id}/download/{type}` | Download output |
| GET | `/components` | List catalog components |

## Sample Files

The `samples/` directory contains example drawings:
- `Aeronca_Defender_Plan_Vector.pdf` - Model aircraft PDF plan
- `Corsair rivista.dxf` - DXF drawing
- `Corsair rivista.dwg` - DWG drawing

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

## License

MIT License - See LICENSE file for details.

---

*Built with ❤️ for model aircraft builders and engineers*



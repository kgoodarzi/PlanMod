# PlanMod - Drawing to DXF Conversion Pipeline

## Executive Summary

PlanMod is a serverless cloud-based pipeline that converts engineering/model drawings (PDF, JPG, PNG) into structured DXF files with component-level reasoning. The system combines classical computer vision, vision-language models (VLM), and large language models (LLM) to achieve semantic understanding of technical drawings.

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                  │
│                    (Local Web UI - React/Vite)                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AWS API GATEWAY                                    │
│                    (REST API / WebSocket for status)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  S3 Bucket    │         │  Lambda         │         │  Step Functions │
│  (Storage)    │◄────────│  (Orchestrator) │────────►│  (Workflow)     │
│  - uploads/   │         │                 │         │                 │
│  - outputs/   │         └─────────────────┘         └─────────────────┘
│  - temp/      │                                              │
└───────────────┘                                              │
        ▲                                                      ▼
        │                    ┌─────────────────────────────────────────┐
        │                    │         PROCESSING PIPELINE             │
        │                    ├─────────────────────────────────────────┤
        │                    │  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
        └────────────────────│  │ Ingest  │─►│ Vision  │─►│ Vector  │ │
                             │  │ Lambda  │  │ Lambda  │  │ Lambda  │ │
                             │  └─────────┘  └─────────┘  └─────────┘ │
                             │       │            │            │      │
                             │       ▼            ▼            ▼      │
                             │  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
                             │  │ Scene   │◄─│ DXF     │◄─│Transform│ │
                             │  │ Graph   │  │ Writer  │  │ Lambda  │ │
                             │  └─────────┘  └─────────┘  └─────────┘ │
                             └─────────────────────────────────────────┘
                                              │
                             ┌────────────────┼────────────────┐
                             ▼                ▼                ▼
                    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
                    │  Bedrock    │  │  DynamoDB   │  │  SQS        │
                    │  (VLM/LLM)  │  │  (Metadata) │  │  (Queue)    │
                    └─────────────┘  └─────────────┘  └─────────────┘
```

---

## AWS Services Breakdown

### Compute & Orchestration
| Service | Purpose | Justification |
|---------|---------|---------------|
| **AWS Lambda** | Lightweight processing tasks | Serverless, pay-per-use, auto-scaling |
| **AWS Step Functions** | Workflow orchestration | Visual workflow, error handling, retries |
| **AWS Batch** | Heavy CV/vectorization tasks | For tasks exceeding Lambda limits |

### Storage
| Service | Purpose | Justification |
|---------|---------|---------------|
| **S3** | File storage (uploads, outputs, temp) | Scalable, durable, event-driven |
| **DynamoDB** | Scene graph, job metadata | Fast key-value access, serverless |

### AI/ML
| Service | Purpose | Justification |
|---------|---------|---------------|
| **Amazon Bedrock** | VLM (Claude) + LLM access | Managed, no infrastructure |
| **Amazon Textract** | OCR for dimensions/labels | Native AWS, high accuracy |

### API & Integration
| Service | Purpose | Justification |
|---------|---------|---------------|
| **API Gateway** | REST endpoints + WebSocket | Managed, scalable |
| **SQS** | Job queue for async processing | Decoupling, retry logic |
| **SNS** | Notifications | Job completion alerts |

### Infrastructure
| Service | Purpose | Justification |
|---------|---------|---------------|
| **CloudFormation/CDK** | Infrastructure as Code | AWS-native IaC |
| **ECR** | Container images for Lambda/Batch | Store processing images |

---

## Module Architecture

### Directory Structure

```
PlanMod/
├── infrastructure/           # AWS CDK/CloudFormation IaC
│   ├── cdk/
│   │   ├── app.py
│   │   ├── stacks/
│   │   │   ├── storage_stack.py
│   │   │   ├── compute_stack.py
│   │   │   ├── api_stack.py
│   │   │   └── ai_stack.py
│   │   └── constructs/
│   └── config/
│       └── aws_config.yaml   # User AWS credentials config
│
├── backend/                  # Python Lambda functions
│   ├── shared/              # Shared utilities
│   │   ├── __init__.py
│   │   ├── models.py        # Pydantic models
│   │   ├── s3_client.py
│   │   ├── dynamo_client.py
│   │   └── config.py
│   │
│   ├── ingest/              # File ingestion module
│   │   ├── __init__.py
│   │   ├── handler.py       # Lambda entry point
│   │   ├── normalizer.py    # Image normalization
│   │   ├── pdf_processor.py # PDF rasterization
│   │   └── dwg_processor.py # DWG handling
│   │
│   ├── vision/              # VLM + CV pipeline
│   │   ├── __init__.py
│   │   ├── handler.py
│   │   ├── cv_detector.py   # OpenCV line/curve detection
│   │   ├── region_segmenter.py
│   │   └── component_classifier.py
│   │
│   ├── vlm_client/          # VLM abstraction layer
│   │   ├── __init__.py
│   │   ├── base.py          # Abstract interface
│   │   ├── bedrock_claude.py # AWS Bedrock Claude
│   │   └── prompts.py       # VLM prompt templates
│   │
│   ├── llm_client/          # LLM abstraction layer
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── bedrock_claude.py
│   │   └── prompts.py
│   │
│   ├── ocr/                 # OCR module
│   │   ├── __init__.py
│   │   ├── handler.py
│   │   ├── textract_client.py
│   │   └── text_processor.py
│   │
│   ├── vectorization/       # Image → Vector
│   │   ├── __init__.py
│   │   ├── handler.py
│   │   ├── line_detector.py
│   │   ├── contour_tracer.py
│   │   └── arc_fitter.py
│   │
│   ├── scene_graph/         # Semantic model
│   │   ├── __init__.py
│   │   ├── handler.py
│   │   ├── graph_builder.py
│   │   ├── models.py        # Scene graph data models
│   │   └── renderer.py      # Visual rendering
│   │
│   ├── dxf_writer/          # DXF output (first pass)
│   │   ├── __init__.py
│   │   ├── handler.py
│   │   ├── writer.py
│   │   ├── layer_manager.py
│   │   └── block_manager.py
│   │
│   ├── component_db/        # Component catalog
│   │   ├── __init__.py
│   │   ├── handler.py
│   │   ├── catalog.py
│   │   ├── materials.py
│   │   └── data/
│   │       ├── balsa_stock.json
│   │       ├── fasteners.json
│   │       └── hardware.json
│   │
│   ├── transform/           # DXF second pass
│   │   ├── __init__.py
│   │   ├── handler.py
│   │   ├── substitution_engine.py
│   │   ├── geometry_modifier.py
│   │   └── mass_calculator.py
│   │
│   └── orchestration/       # Workflow coordination
│       ├── __init__.py
│       ├── handler.py
│       ├── workflow_manager.py
│       └── report_generator.py
│
├── frontend/                # Local Web UI
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── local/                   # Local processing tools
│   ├── cv_processor/        # Heavy CV tasks
│   └── dxf_tools/          # DXF manipulation
│
├── tests/                   # Test suite
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── docs/                    # Documentation
│   └── api/
│
├── plan.md                  # This file
├── progress.md              # Progress tracking
├── requirements.txt         # Python dependencies
├── pyproject.toml          # Project config
├── Dockerfile              # Container definition
└── docker-compose.yml      # Local development
```

---

## Data Flow

### Phase 1: Ingestion
```
User Upload → API Gateway → Lambda (Ingest)
    │
    ├─► S3: Store original file
    ├─► PDF? → Rasterize pages → S3
    ├─► DWG? → Convert to DXF → S3
    └─► Normalize (orientation, resolution, grayscale) → S3
```

### Phase 2: Vision Analysis
```
Normalized Image → Lambda (Vision)
    │
    ├─► OpenCV: Edge detection, line detection
    ├─► VLM (Bedrock): Region segmentation, labeling
    ├─► OCR (Textract): Text extraction
    └─► DynamoDB: Store analysis results
```

### Phase 3: Vectorization
```
CV Results → Lambda (Vectorization)
    │
    ├─► Hough transform → Line segments
    ├─► Contour tracing → Polylines
    ├─► Arc fitting → Curves
    └─► S3: Vector primitives (JSON)
```

### Phase 4: Scene Graph Construction
```
Analysis + Vectors → Lambda (Scene Graph)
    │
    ├─► Build view hierarchy
    ├─► Associate components with regions
    ├─► Link annotations to geometry
    ├─► DynamoDB: Store scene graph
    └─► Generate visualization → S3
```

### Phase 5: DXF Generation (First Pass)
```
Scene Graph + Vectors → Lambda (DXF Writer)
    │
    ├─► Create layers (VIEW_*, COMP_*)
    ├─► Generate blocks for components
    ├─► Write geometry entities
    └─► S3: base.dxf
```

### Phase 6: Component Substitution (Second Pass)
```
base.dxf + Scene Graph + User Rules → Lambda (Transform)
    │
    ├─► Identify eligible components
    ├─► Apply substitution rules
    ├─► Recompute geometry
    ├─► Calculate mass/CG
    └─► S3: final.dxf + report.md
```

---

## API Endpoints

### REST API (API Gateway)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/jobs` | Create new processing job |
| GET | `/jobs/{id}` | Get job status and results |
| GET | `/jobs/{id}/scene-graph` | Get scene graph visualization |
| POST | `/jobs/{id}/substitute` | Apply component substitutions |
| GET | `/jobs/{id}/download/{file}` | Download output files |
| GET | `/components` | List available components |
| GET | `/components/{type}` | Get component details |

### WebSocket (Real-time status)
| Event | Description |
|-------|-------------|
| `job.progress` | Processing stage updates |
| `job.complete` | Job finished |
| `job.error` | Error occurred |

---

## Data Models

### Job Model
```python
class Job:
    id: str                    # UUID
    status: JobStatus          # PENDING, PROCESSING, COMPLETE, FAILED
    created_at: datetime
    updated_at: datetime
    input_file: S3Reference
    normalized_file: S3Reference
    scene_graph_id: str
    base_dxf: S3Reference
    final_dxf: S3Reference
    report: S3Reference
    current_stage: str
    error_message: Optional[str]
```

### Scene Graph Model
```python
class SceneGraph:
    id: str
    job_id: str
    views: List[View]
    components: List[Component]
    annotations: List[Annotation]
    relationships: List[Relationship]

class View:
    id: str
    type: ViewType            # TOP, SIDE, FRONT, SECTION, DETAIL
    bounds: BoundingBox
    entities: List[EntityRef]

class Component:
    id: str
    type: ComponentType       # RIB, FORMER, SPAR, FASTENER, etc.
    view_id: str
    bounds: BoundingBox
    attributes: Dict
    geometry_refs: List[str]
    material: Optional[str]
    dimensions: Optional[Dict]
```

---

## VLM/LLM Integration

### VLM Client Interface
```python
class VLMClient(ABC):
    @abstractmethod
    async def analyze_image(
        self,
        image: bytes,
        prompt: str,
        response_schema: Optional[dict] = None
    ) -> dict:
        """Analyze image with structured output."""
        pass

    @abstractmethod
    async def segment_regions(
        self,
        image: bytes
    ) -> List[Region]:
        """Segment drawing into regions."""
        pass

    @abstractmethod
    async def classify_component(
        self,
        image_crop: bytes,
        context: str
    ) -> ComponentClassification:
        """Classify a component from image crop."""
        pass
```

### LLM Client Interface
```python
class LLMClient(ABC):
    @abstractmethod
    async def interpret_ocr(
        self,
        ocr_text: str,
        context: str
    ) -> StructuredText:
        """Clean and interpret OCR output."""
        pass

    @abstractmethod
    async def map_to_components(
        self,
        annotations: List[str],
        catalog: ComponentCatalog
    ) -> List[ComponentMapping]:
        """Map text annotations to catalog components."""
        pass

    @abstractmethod
    async def plan_substitution(
        self,
        user_request: str,
        scene_graph: SceneGraph,
        catalog: ComponentCatalog
    ) -> SubstitutionPlan:
        """Generate substitution plan from user request."""
        pass
```

---

## Component Database Schema

### Material Properties
```json
{
  "balsa": {
    "density_kg_m3": 160,
    "grain_types": ["A", "B", "C"],
    "stock_sizes": {
      "sheets": ["1/32", "1/16", "3/32", "1/8", "3/16", "1/4"],
      "sticks": ["1/16x1/16", "1/8x1/8", "1/4x1/4", "1/2x1/2"]
    }
  }
}
```

### Component Template
```json
{
  "id": "BALSA_STICK_1_8",
  "type": "spar",
  "material": "balsa",
  "cross_section": {
    "type": "rectangle",
    "width_inches": 0.125,
    "height_inches": 0.125
  },
  "mass_per_length_g_mm": 0.0052,
  "dxf_block": "SPAR_1_8_CROSS"
}
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Project scaffolding and structure
- [ ] AWS CDK infrastructure setup
- [ ] S3, DynamoDB, API Gateway deployment
- [ ] Basic Lambda functions with stubs
- [ ] VLM/LLM client abstractions
- [ ] Local development environment

### Phase 2: Ingestion Pipeline (Week 2-3)
- [ ] PDF rasterization
- [ ] Image normalization
- [ ] DWG/DXF handling
- [ ] S3 upload/download utilities
- [ ] Job tracking in DynamoDB

### Phase 3: Vision Pipeline (Week 3-4)
- [ ] OpenCV integration for line detection
- [ ] VLM region segmentation
- [ ] OCR integration (Textract)
- [ ] Region labeling and classification

### Phase 4: Vectorization (Week 4-5)
- [ ] Hough transform for lines
- [ ] Contour tracing
- [ ] Arc/curve fitting
- [ ] Vector primitive storage

### Phase 5: Scene Graph (Week 5-6)
- [ ] Graph data model
- [ ] View/component association
- [ ] Scene graph builder
- [ ] Visualization renderer

### Phase 6: DXF Output (Week 6-7)
- [ ] ezdxf integration
- [ ] Layer/block management
- [ ] First-pass DXF generation
- [ ] Naming conventions

### Phase 7: Transformation (Week 7-8)
- [ ] Component substitution engine
- [ ] Geometry modification
- [ ] Mass/CG calculator
- [ ] Second-pass DXF output

### Phase 8: Frontend & Integration (Week 8-9)
- [ ] React/Vite web UI
- [ ] File upload component
- [ ] Scene graph viewer
- [ ] Substitution interface
- [ ] Results display

### Phase 9: Testing & Polish (Week 9-10)
- [ ] Unit tests
- [ ] Integration tests
- [ ] Error handling
- [ ] Documentation
- [ ] Performance optimization

---

## Configuration

### AWS Config File (aws_config.yaml)
```yaml
# User AWS credentials and configuration
aws:
  region: us-east-1
  profile: default  # Or explicit credentials below
  # access_key_id: YOUR_ACCESS_KEY
  # secret_access_key: YOUR_SECRET_KEY

deployment:
  environment: dev  # dev, staging, prod
  stack_prefix: planmod

resources:
  s3:
    bucket_name: planmod-storage-${environment}
    retention_days: 30
  
  lambda:
    memory_mb: 1024
    timeout_seconds: 300
  
  dynamodb:
    billing_mode: PAY_PER_REQUEST

ai:
  bedrock:
    vlm_model: anthropic.claude-3-5-sonnet-20241022-v2:0
    llm_model: anthropic.claude-3-5-sonnet-20241022-v2:0
    region: us-east-1
  
  textract:
    features:
      - TABLES
      - FORMS
```

---

## Security Considerations

1. **IAM Roles**: Least-privilege access for Lambda functions
2. **S3**: Bucket policies, encryption at rest
3. **API Gateway**: Authentication (Cognito or API keys)
4. **Secrets**: AWS Secrets Manager for API keys
5. **VPC**: Optional private networking for sensitive workloads

---

## Cost Estimation (Monthly)

| Service | Estimated Usage | Cost |
|---------|-----------------|------|
| Lambda | 100K invocations | ~$5 |
| S3 | 10GB storage | ~$1 |
| DynamoDB | 1M reads/writes | ~$5 |
| API Gateway | 100K requests | ~$3 |
| Bedrock (Claude) | 1M tokens | ~$15 |
| Textract | 1K pages | ~$1.50 |
| **Total** | | **~$30-50** |

---

## Success Criteria

### MVP (First Iteration)
1. ✅ Upload PNG/JPG image through web UI
2. ✅ Basic line detection and vectorization
3. ✅ Single VLM call for region labeling
4. ✅ Simple scene graph generation
5. ✅ DXF output with proper layers
6. ✅ Dummy component substitution
7. ✅ End-to-end workflow completion

### Production Ready
1. Full PDF/DWG support
2. Accurate multi-view segmentation
3. Component recognition >80% accuracy
4. Robust substitution engine
5. Mass/CG calculations
6. User feedback integration
7. Error recovery and logging

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| VLM accuracy for technical drawings | High | Fine-tuned prompts, fallback to CV |
| Lambda timeout for large files | Medium | Use AWS Batch for heavy tasks |
| DXF complexity | Medium | Start with simple entities, iterate |
| Cost overruns | Low | Usage monitoring, quotas |

---

## Next Steps

1. **Approve this plan** - Review and confirm architecture
2. **Create infrastructure** - Deploy CDK stacks
3. **Implement stubs** - All module interfaces
4. **Build MVP** - End-to-end simple case
5. **Iterate** - Add features incrementally

---

*Last Updated: 2024-12-13*



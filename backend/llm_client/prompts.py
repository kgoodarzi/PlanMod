"""
Prompt templates for LLM operations.
"""

INTERPRET_OCR_PROMPT = """Interpret the following OCR text extracted from a technical drawing.

Raw OCR text:
{ocr_text}

Context:
{context}

The text likely contains:
- Dimensions (measurements)
- Part labels/IDs
- Material specifications
- Scale information
- Notes and instructions

Please:
1. Clean up any OCR errors (misread characters, spacing issues)
2. Identify what type of information each piece of text represents
3. Extract structured entities

Respond with JSON containing:
- cleaned_text: The corrected text
- interpretation: What this text means in context
- entities: Array of extracted entities with text, type, and value
- confidence: Your confidence in the interpretation (0.0-1.0)"""


MAP_COMPONENTS_PROMPT = """Map the following annotation texts to components in the catalog.

Annotations to map:
{annotations}

Available components in catalog:
{catalog_summary}

For each annotation:
1. Identify what component it refers to
2. Find the best match in the catalog
3. Explain your reasoning
4. Note any alternatives if uncertain

Common annotation patterns:
- "RIB 1", "R1" → Wing rib component
- "F3", "FORMER 3" → Fuselage former
- "1/8 SQ" → 1/8" square balsa stick
- "3mm PLY" → 3mm plywood
- "SPAR" → Main structural spar

Respond with JSON containing a "mappings" array."""


PLAN_SUBSTITUTION_PROMPT = """Create a plan for the following component substitution request.

User request:
{user_request}

Current scene graph:
{scene_graph_summary}

Available components in catalog:
{catalog_summary}

Consider:
1. Which components are affected by the request
2. What changes need to be made to each
3. Any cascading effects (e.g., changing spar size affects rib notches)
4. Structural or weight implications
5. Any warnings or concerns

Common substitution types:
- Material upgrades (balsa → carbon fiber)
- Size changes (1/8" → 3/16" spars)
- Part swaps (different motor, propeller)
- Construction method changes

Respond with JSON containing:
- request_summary: Brief summary of what was requested
- steps: Array of substitution steps
- warnings: Any concerns or cautions
- estimated_impact: Weight, strength, cost changes"""


GENERATE_REPORT_PROMPT = """Generate a human-readable report for the drawing processing job.

Job summary:
{job_summary}

Scene graph summary:
{scene_graph_summary}

Substitutions applied:
{substitutions}

Create a well-formatted Markdown report that includes:

1. **Summary** - Overview of what was processed
2. **Recognized Components** - List of identified components with confidence
3. **Views Identified** - Drawing views found
4. **Applied Substitutions** - What changes were made
5. **Mass/CG Analysis** - Weight and balance if calculated
6. **Uncertainties** - Items needing human review
7. **Recommendations** - Suggestions for improvement

Use clear headings, bullet points, and tables where appropriate.
Include any warnings or notes about the processing results."""


EXPLAIN_COMPONENT_PROMPT = """Explain the following component from a model aircraft drawing.

Component type: {component_type}
Attributes: {attributes}
Context: {context}

Provide:
1. What this component does
2. Its structural role
3. Common materials and sizes
4. Construction tips
5. Related components

Keep the explanation concise but informative."""


VALIDATE_SUBSTITUTION_PROMPT = """Validate the following component substitution.

Original component:
{original}

Proposed replacement:
{replacement}

Context:
{context}

Check for:
1. Dimensional compatibility
2. Structural adequacy
3. Weight impact
4. Assembly considerations
5. Any potential issues

Respond with JSON containing:
- valid: boolean indicating if substitution is acceptable
- concerns: array of any issues found
- recommendations: suggestions for the substitution
- impact_assessment: brief description of expected impact"""



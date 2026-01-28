# rightsize-cli

**The Biggest Model for Every Task? That's Just Lazy.**

Stop overpaying for AI. Benchmark your prompts against 200+ models via OpenRouter to find the cheapest one that still works.

This is the production-grade CLI version of the [RightSize web tool](https://nehmeailabs.com/right-size).

## Installation

```bash
# Using pip
pip install rightsize-cli

# Using uv
uv pip install rightsize-cli
```

## Quick Start

```bash
# Set your OpenRouter API key
export RIGHTSIZE_OPENROUTER_API_KEY="sk-or-..."

# List available models
rightsize-cli models

# Run a benchmark
rightsize-cli benchmark test_cases.csv \
  -t prompt.j2 \
  -m google/gemma-3-12b-it \
  -m deepseek/deepseek-chat-v3.1 \
  -j google/gemini-2.5-flash \
  -b google/gemini-2.5-flash
```

### Run without installing (uvx)

```bash
# Set API key
export RIGHTSIZE_OPENROUTER_API_KEY="sk-or-..."

# List models
uvx rightsize-cli models

# Run benchmark
uvx rightsize-cli benchmark test_cases.csv \
  -t prompt.j2 \
  -m google/gemma-3-12b-it \
  -m deepseek/deepseek-chat-v3.1 \
  -j google/gemini-2.5-flash \
  -b google/gemini-2.5-flash
```

## Output

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
┃ Model                       ┃ Accuracy ┃ Latency (p95) ┃ Cost/1k  ┃ Savings  ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
│ google/gemma-3-12b-it       │    71.0% │        4200ms │  $0.0028 │   +93.7% │
│ deepseek/deepseek-chat-v3.1 │    95.0% │         800ms │  $0.0180 │   +60.0% │
│ google/gemini-2.5-flash     │   100.0% │        1900ms │  $0.0450 │       —  │
└─────────────────────────────┴──────────┴───────────────┴──────────┴──────────┘
```

## How It Works

1. **You provide test cases** - A CSV with inputs and expected outputs
2. **Candidate models compete** - All models run the same prompts in parallel
3. **LLM-as-Judge scores** - A judge model compares each output to your expected output
4. **You see the results** - Cost, accuracy, latency - pick the cheapest model that meets your bar

## CSV Format

Two columns: `input_data` and `expected_output`:

```csv
input_data,expected_output
"My order hasn't arrived.",billing::high
"How do I reset my password?",account::high
"I want a refund!",refund::high
```

The judge model compares each model's output to `expected_output` and scores:
- **1.0** - Exact or semantic match
- **0.8** - Very close with minor differences  
- **0.5** - Partially correct
- **0.0** - Wrong or irrelevant

### Best practices for test data

1. **Use minimal output formats** - Delimiter-separated (`category::confidence`) keeps responses short, costs low
2. **Consistent task type** - All rows should be the same kind of task
3. **Representative samples** - Use real data from your production use case
4. **Clear expected outputs** - Unambiguous so the judge can score fairly
5. **10-20 test cases** - Enough to be statistically meaningful, fast to run

## Prompt Templates

Templates wrap your inputs with instructions. Supports Jinja2 (`.j2`) or Python f-strings.

**Example: Classification template** (`prompt.j2`):
```jinja2
Classify this support ticket.

CATEGORIES: billing, account, refund, subscription, technical
CONFIDENCE: high, medium, low

OUTPUT FORMAT: <category>::<confidence>
OUTPUT ONLY the format above. No explanation. No punctuation. No other text.

TICKET: {{ input_data }}

OUTPUT:
```

**Example: Extraction template** (`extract.j2`):
```jinja2
Extract the email from this text.

OUTPUT FORMAT: <email or NONE>
OUTPUT ONLY the format above. No explanation. No other text.

TEXT: {{ input_data }}

OUTPUT:
```

### Template variable

| Variable | Description |
|----------|-------------|
| `input_data` | The value from your CSV's `input_data` column |

## CLI Reference

### `rightsize-cli benchmark`

```bash
rightsize-cli benchmark <csv_file> [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--template` | `-t` | (required) | Path to prompt template file |
| `--model` | `-m` | (required) | Model ID to test (repeat for multiple) |
| `--judge` | `-j` | (required) | Model for judging outputs |
| `--baseline` | `-b` | None | Baseline model for savings calculation |
| `--concurrency` | `-c` | 10 | Max parallel requests |
| `--output` | `-o` | `table` | Output format: table, json, csv |
| `--verbose` | `-v` | False | Show detailed outputs and judge scores |

### `rightsize-cli models`

List all available models and their pricing:

```bash
rightsize-cli models
```

## Configuration

Set via environment variables or `.env` file:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RIGHTSIZE_OPENROUTER_API_KEY` | Yes | - | Your OpenRouter API key |
| `RIGHTSIZE_MAX_CONCURRENCY` | No | 10 | Default concurrency |
| `RIGHTSIZE_TIMEOUT_SECONDS` | No | 60 | Request timeout |

## Examples

### Compare cheap models against a baseline
```bash
uvx rightsize-cli benchmark test_cases.csv \
  -t prompt.j2 \
  -m google/gemma-3-12b-it \
  -m google/gemma-3-27b-it \
  -m qwen/qwen3-8b \
  -m meta-llama/llama-3.3-70b-instruct \
  -j google/gemini-2.5-flash \
  -b google/gemini-2.5-flash
```

### Use a stronger judge model
```bash
uvx rightsize-cli benchmark test_cases.csv \
  -t prompt.j2 \
  -m google/gemma-3-12b-it \
  -m deepseek/deepseek-chat-v3.1 \
  -j anthropic/claude-sonnet-4 \
  -b google/gemini-2.5-flash
```

### Export results to JSON
```bash
uvx rightsize-cli benchmark test_cases.csv \
  -t prompt.j2 \
  -m google/gemma-3-12b-it \
  -m deepseek/deepseek-chat-v3.1 \
  -j google/gemini-2.5-flash \
  -b google/gemini-2.5-flash \
  -o json > results.json
```

### Debug with verbose mode
```bash
uvx rightsize-cli benchmark test_cases.csv \
  -t prompt.j2 \
  -m google/gemma-3-12b-it \
  -j google/gemini-2.5-flash \
  -b google/gemini-2.5-flash \
  -v
```

## Tips

1. **Use minimal output formats** - `category::confidence` is cheaper than JSON, JSON is cheaper than prose
2. **End prompts with "OUTPUT:"** - Primes the model to respond immediately without preamble
3. **Start with 10-20 test cases** - Enough to be representative, fast to iterate
4. **Set a quality bar** - Decide what accuracy % is acceptable (e.g., 95%+)
5. **Consider latency** - Sometimes a slower cheap model isn't worth it
6. **Iterate on prompts** - A better prompt can make cheaper models work better

## Development

```bash
# Clone the repo
git clone https://github.com/NehmeAILabs/rightsize-cli.git
cd rightsize-cli

# Install in dev mode
uv pip install -e .

# Run locally
rightsize-cli models
```

## License

MIT

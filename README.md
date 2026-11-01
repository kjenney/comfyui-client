# ComfyUI API Client

A Python command-line tool for performing various tasks with [ComfyUI](https://github.com/comfyanonymous/ComfyUI) through its REST API.

## Features

- Queue workflows and wait for completion
- Update CLIP Text Encoder prompts dynamically
- Download generated images to local directory
- Test server connectivity
- Clear cache and free VRAM/memory
- Check queue status with exit codes
- Support for both workflow JSON files and inline workflow creation
- Support for stdin input

## Prerequisites

- Python 3.8+
- ComfyUI server running (default: http://127.0.0.1:8188)
- `requests` library (`pip install requests`)

## Installation

```bash
# Download the script (already done if you're reading this)
curl -O https://path/to/comfyui_client.py

# Make it executable (optional)
chmod +x comfyui_client.py

# Install dependencies
pip install requests
```

## Basic Usage

### Command Line Arguments

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--host` | `-H` | ComfyUI server host | `127.0.0.1` |
| `--port` | `-p` | ComfyUI server port | `8188` |
| `--workflow` | `-w` | Path to workflow JSON (or `-` for stdin) | *required* |
| `--output-dir` | `-o` | Output directory for images | `.` (current dir) |
| `--output-format` | `-f` | Image format (png, jpg, webp) | `png` |
| `--quick-test` | `-t` | Test server connection only | `false` |
| `--free-memory` | | Free memory by unloading models and clearing VRAM | `false` |
| `--check-queue` | | Check queue status (exit 0 if empty, 2 if jobs) | `false` |

### Generating Images from a Workflow

Export a workflow from ComfyUI (Click `Save` > `Save (All)` in ComfyUI), then run:

```bash
python comfyui_client.py --workflow workflow.json
```

### Custom Host/Port

```bash
python comfyui_client.py --host 192.168.1.100 --port 8188 --workflow workflow.json
```

### Update Prompts Dynamically

Update CLIP Text Encoder nodes with custom prompts without modifying the workflow file:

```bash
# Update both positive and negative prompts
python comfyui_client.py --workflow workflow.json \
    --prompt-positive "a beautiful landscape" \
    --prompt-negative "blurry, bad quality"

# Update specific nodes by ID
python comfyui_client.py --workflow workflow.json \
    --prompt-positive "positive text" --positive-node-id 6 \
    --prompt-negative "negative text" --negative-node-id 7
```

### Create a Simple Workflow from Prompt

Create a basic text-to-image workflow on the fly:

```bash
python comfyui_client.py --prompt "a beautiful landscape" \
    --negative-prompt "blurry, bad quality" \
    --width 512 --height 512 --steps 20
```

### Pass Workflow via stdin

```bash
cat workflow.json | python comfyui_client.py --host localhost --port 8188 -w -
```

### Test Server Connection

```bash
python comfyui_client.py --host localhost --port 8188 --quick-test
```

### Free Memory (Unload Models and Clear VRAM)

Free up GPU memory by unloading models and clearing the cache:

```bash
python comfyui_client.py --host localhost --port 8188 --free-memory
```

Or use within a Python script:

```python
from comfyui_client import ComfyUIClient

client = ComfyUIClient(host="127.0.0.1", port=8188)

# Free all memory
result = client.free_memory(unload_models=True, free_vram=True)
print(f"Memory freed: {result}")

# Free only VRAM cache (keep models loaded)
result = client.free_memory(unload_models=False, free_vram=True)
```

### Check Queue Status

Check if there are jobs in the queue:

```bash
python comfyui_client.py --host localhost --port 8188 --check-queue
echo "Exit code: $?"  # 0 if empty, 2 if jobs pending
```

Or use within a Python script:

```python
from comfyui_client import ComfyUIClient

client = ComfyUIClient(host="127.0.0.1", port=8188)

# Check queue status
queue_info = client.get_queue_info()
queued_count = len(queue_info.get("queue_running", [])) + len(queue_info.get("queue_pending", []))
print(f"Queue has {queued_count} job(s)")
```

### Output Control

```bash
# Save to specific directory with JPG format
python comfyui_client.py --workflow workflow.json \
    --output-dir ./output --output-format jpg
```

## Advanced Options

| Option | Description |
|--------|-------------|
| `--prompt-text` | Text prompt for simple workflow creation |
| `--negative-prompt` | Negative prompt (default: "blurry, bad quality, distorted") |
| `--width` | Image width for simple workflow (default: 512) |
| `--height` | Image height for simple workflow (default: 512) |
| `--steps` | Sampling steps (default: 20) |
| `--cfg` | CFG scale (default: 7.5) |
| `--seed` | Random seed (omit for random) |
| `--checkpoint` | Checkpoint filename (default: "model.safetensors") |
| `--positive-node-id` | Node ID(s) for positive prompt (can be specified multiple times) |
| `--negative-node-id` | Node ID(s) for negative prompt (can be specified multiple times) |
| `--free-memory` | Free memory by unloading models and clearing VRAM cache |

## Examples

### Complete Example

```bash
# 1. Start ComfyUI (in another terminal)
# cd /path/to/ComfyUI && python main.py

# 2. Export a workflow from ComfyUI to workflow.json

# 3. Generate an image with custom prompts
python comfyui_client.py \
    --host localhost \
    --port 8188 \
    --workflow workflow.json \
    --prompt-positive "a futuristic city with flying cars" \
    --prompt-negative "low quality, distorted" \
    --output-dir ./images \
    --output-format png

# 4. Free GPU memory when done
python comfyui_client.py --host localhost --port 8188 --free-memory

# Output:
# Checking ComfyUI server at http://localhost:8188...
# Connected to ComfyUI server!
# Loading workflow from workflow.json...
# Queued workflow with ID: abc123...
# Waiting for completion...
# Workflow completed!
# Downloading: output_00001.png
# Saved: ./images/output_00001.png_abc12345.png
```

### Using with Python

```python
from comfyui_client import ComfyUIClient, load_workflow_from_file

# Initialize client
client = ComfyUIClient(host="127.0.0.1", port=8188)

# Load workflow
workflow = load_workflow_from_file("my_workflow.json")

# Generate image
output_files = client.generate_image_from_workflow(
    workflow,
    output_dir=Path("./output"),
    wait=True
)

print(f"Generated {len(output_files)} images")
```

## Troubleshooting

### Connection refused
- Ensure ComfyUI is running: `python main.py` in the ComfyUI directory
- Check the host and port match your ComfyUI configuration
- Check firewall settings

### Workflow not executing
- Verify node IDs in your workflow match the exported JSON
- Check ComfyUI server logs for errors
- Ensure all required models/checkpoints are installed

### Images not downloading
- Check output directory permissions
- Verify the workflow has a SaveImage node
- Check server logs for image generation status

## License

MIT License

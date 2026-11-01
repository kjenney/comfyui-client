#!/usr/bin/env python3
"""
ComfyUI API Client - Generate images using ComfyUI through its REST API.

Usage:
    python comfyui_client.py --host <host> --port <port> --workflow <workflow_json_file> [options]

Examples:
    # Basic usage with default host/port
    python comfyui_client.py --workflow workflow.json

    # With custom host and port
    python comfyui_client.py --host 192.168.1.100 --port 8188 --workflow workflow.json

    # Update CLIP Text Encoders with custom prompts
    python comfyui_client.py --workflow workflow.json --prompt-positive "a beautiful landscape" --prompt-negative "blurry, bad quality"

    # Update specific CLIP Text Encoder nodes by ID
    python comfyui_client.py --workflow workflow.json \
        --prompt-positive "positive text" --positive-node-id 6 \
        --prompt-negative "negative text" --negative-node-id 7

    # Pass workflow as inline JSON
    cat workflow.json | python comfyui_client.py --host localhost --port 8188 -w -

    # Test server connection
    python comfyui_client.py --host localhost --port 8188 --quick-test

    # Free memory by unloading models and clearing VRAM cache
    python comfyui_client.py --host localhost --port 8188 --free-memory

    # Check queue status (exit 0 if empty, 2 if jobs pending)
    python comfyui_client.py --host localhost --port 8188 --check-queue
"""

import argparse
import json
import sys
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List


class ComfyUIClient:
    """Client for interacting with ComfyUI's API."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8188):
        """
        Initialize the ComfyUI client.

        Args:
            host: The ComfyUI server host address
            port: The ComfyUI server port
        """
        self.base_url = f"http://{host}:{port}"
        self.client_id = self._generate_client_id()

    def _generate_client_id(self) -> str:
        """Generate a unique client ID."""
        import uuid
        return str(uuid.uuid4())

    def check_server(self, timeout: int = 5) -> bool:
        """
        Check if the ComfyUI server is running and accessible.

        Returns:
            True if the server is running, False otherwise
        """
        try:
            response = requests.get(f"{self.base_url}/system_stats", timeout=timeout)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def get_queue_info(self) -> Dict[str, Any]:
        """Get current queue information."""
        try:
            response = requests.get(f"{self.base_url}/queue", timeout=5)
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

    def free_memory(
        self,
        unload_models: bool = True,
        free_vram: bool = True
    ) -> Dict[str, Any]:
        """
        Clear cache and free memory using the /free endpoint.

        Args:
            unload_models: Whether to unload all models from memory
            free_vram: Whether to clear VRAM cache

        Returns:
            Response from the server with free memory information
        """
        payload = {
            "unload_models": unload_models,
            "free_vram": free_vram
        }

        try:
            response = requests.post(
                f"{self.base_url}/free",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error freeing memory: {e}", file=sys.stderr)
            raise

    def queue_workflow(self, workflow: Dict[str, Any], live_preview: bool = True) -> str:
        """
        Queue a workflow for execution.

        Args:
            workflow: The ComfyUI workflow dictionary
            live_preview: Whether to enable live preview

        Returns:
            The prompt_id of the queued workflow
        """
        payload = {
            "prompt": workflow,
            "client_id": self.client_id,
            "extra_data": {
                "enable_live_preview": live_preview
            }
        }

        try:
            response = requests.post(
                f"{self.base_url}/prompt",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            return result.get("prompt_id", "")
        except requests.exceptions.RequestException as e:
            print(f"Error queuing workflow: {e}", file=sys.stderr)
            raise

    def get_history(self, prompt_id: str) -> Dict[str, Any]:
        """Get the history for a specific prompt ID."""
        try:
            response = requests.get(
                f"{self.base_url}/history/{prompt_id}",
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting history: {e}", file=sys.stderr)
            return {}

    def get_image(self, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
        """
        Download an image from the server.

        Args:
            filename: The filename of the image
            subfolder: The subfolder within the output directory
            folder_type: The folder type (output, temp, input)

        Returns:
            The image bytes
        """
        try:
            # Build the URL with query parameters
            from urllib.parse import quote
            url_params = f"?filename={quote(filename)}&type={folder_type}"
            if subfolder:
                url_params += f"&subfolder={quote(subfolder)}"

            response = requests.get(
                f"{self.base_url}/view{url_params}",
                timeout=30
            )
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            print(f"Error downloading image: {e}", file=sys.stderr)
            raise

    def wait_for_prompt_completion(
        self,
        prompt_id: str,
        check_interval: float = 0.5
    ) -> bool:
        """
        Wait for a prompt to complete execution.

        Args:
            prompt_id: The prompt ID to wait for
            check_interval: How often to check (in seconds)

        Returns:
            True if completed successfully, False otherwise
        """
        while True:
            history = self.get_history(prompt_id)

            if prompt_id in history:
                result = history[prompt_id]
                status = result.get("status", {})

                # Check if the prompt has completed
                if status.get("completed", False):
                    return True

                # Check for error status
                if "error" in str(status):
                    print(f"Prompt failed: {status}", file=sys.stderr)
                    return False

            time.sleep(check_interval)

    def generate_image_from_workflow(
        self,
        workflow: Dict[str, Any],
        output_dir: Path = Path("."),
        wait: bool = True,
        output_format: str = "png"
    ) -> Optional[List[Path]]:
        """
        Run a workflow and download generated images.

        Args:
            workflow: The ComfyUI workflow dictionary
            output_dir: Directory to save output images
            wait: Whether to wait for completion
            output_format: File format for saved images

        Returns:
            List of paths to saved images, or None if failed
        """
        # Queue the workflow
        prompt_id = self.queue_workflow(workflow)

        if not prompt_id:
            print("Failed to queue workflow", file=sys.stderr)
            return None

        print(f"Queued workflow with ID: {prompt_id}")

        if wait:
            print("Waiting for completion...")

            self.wait_for_prompt_completion(prompt_id)

            print("Workflow completed!")

        # Get the history to find output files
        history = self.get_history(prompt_id)

        if prompt_id not in history:
            print(f"No history found for prompt {prompt_id}", file=sys.stderr)
            return None

        output_files = []

        # Extract output images from the history
        prompt_history = history[prompt_id]
        outputs = prompt_history.get("outputs", {})

        for node_output in outputs.values():
            if "images" in node_output:
                for image_info in node_output["images"]:
                    filename = image_info.get("filename", "")
                    subfolder = image_info.get("subfolder", "")
                    folder_type = image_info.get("type", "output")

                    print(f"Downloading: {filename}")

                    # Download the image
                    try:
                        image_data = self.get_image(filename, subfolder, folder_type)

                        # Create output filename
                        output_path = output_dir / f"{filename}_{prompt_id[:8]}.{output_format}"

                        # Save the image
                        with open(output_path, "wb") as f:
                            f.write(image_data)

                        output_files.append(output_path)
                        print(f"Saved: {output_path}")

                    except Exception as e:
                        print(f"Error saving image {filename}: {e}", file=sys.stderr)

        return output_files if output_files else None


def load_workflow_from_file(filepath: str) -> Dict[str, Any]:
    """Load a workflow from a JSON file."""
    path = Path(filepath)

    if not path.exists():
        raise FileNotFoundError(f"Workflow file not found: {filepath}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_workflow_from_stdin() -> Dict[str, Any]:
    """Load a workflow from stdin."""
    content = sys.stdin.read()
    return json.loads(content)


def create_simple_workflow(
    prompt: str = "a beautiful landscape",
    negative_prompt: str = "blurry, bad quality, distorted",
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg: float = 7.5,
    seed: Optional[int] = None,
    checkpoint: str = "model.safetensors"
) -> Dict[str, Any]:
    """
    Create a simple workflow for text-to-image generation.

    This creates a minimal workflow with basic nodes. You'll need to adjust
    node IDs to match your specific ComfyUI installation.

    Args:
        prompt: The text prompt (positive)
        negative_prompt: Negative prompt
        width: Image width
        height: Image height
        steps: Number of sampling steps
        cfg: CFG scale
        seed: Random seed (None for random)
        checkpoint: Checkpoint filename

    Returns:
        A workflow dictionary
    """
    import random

    if seed is None:
        seed = random.randint(0, 2**64 - 1)

    # Note: This is a template workflow. Node IDs must match the actual workflow.
    # You'll typically want to export a workflow from ComfyUI and modify it.
    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "cfg": cfg,
                "denoise": 1,
                "latent_image": ["5", 0],
                "model": ["4", 0],
                "negative": ["7", 0],
                "positive": ["6", 0],
                "seed": seed,
                "steps": steps
            }
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": checkpoint
            }
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "batch_size": 1,
                "height": height,
                "width": width
            }
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["4", 1],
                "text": prompt
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["4", 1],
                "text": negative_prompt
            }
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["3", 0],
                "vae": ["4", 2]
            }
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["8", 0]
            }
        }
    }

    return workflow


def update_workflow_prompts(
    workflow: Dict[str, Any],
    positive_prompt: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    positive_node_ids: Optional[List[str]] = None,
    negative_node_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Update CLIP Text Encoder nodes in a workflow with new prompts.

    Args:
        workflow: The workflow dictionary
        positive_prompt: Text prompt for positive CLIP encoder(s)
        negative_prompt: Text prompt for negative CLIP encoder(s)
        positive_node_ids: List of node IDs to update with positive prompt.
                          If None and positive_prompt is given, updates the first
                          CLIPTextEncode node found.
        negative_node_ids: List of node IDs to update with negative prompt.
                          If None and negative_prompt is given, updates the second
                          CLIPTextEncode node found.

    Returns:
        Updated workflow dictionary
    """
    import copy
    updated = copy.deepcopy(workflow)

    # Find all CLIPTextEncode nodes
    clip_nodes = [
        (node_id, node_data)
        for node_id, node_data in updated.items()
        if isinstance(node_data, dict) and node_data.get("class_type") == "CLIPTextEncode"
    ]

    # Helper to get node ID(s) to update
    def get_node_ids(prompt: Optional[str], node_ids: Optional[List[str]], all_nodes: List[tuple]) -> List[str]:
        if prompt is None:
            return []
        if node_ids:
            return node_ids
        # Default: return first node if only one exists, otherwise first two
        return [all_nodes[0][0]] if len(all_nodes) == 1 else [all_nodes[0][0], all_nodes[1][0]]

    # Track which nodes will be updated with positive prompt
    pos_ids: List[str] = []

    # Update positive prompts
    if positive_prompt:
        pos_ids = get_node_ids(positive_prompt, positive_node_ids, clip_nodes)
        for node_id in pos_ids:
            if node_id in updated:
                updated[node_id]["inputs"]["text"] = positive_prompt

    # Update negative prompts
    if negative_prompt:
        neg_ids = get_node_ids(negative_prompt, negative_node_ids, clip_nodes)
        for node_id in neg_ids:
            if node_id in updated:
                # Skip if this node was already updated as positive
                if node_id not in pos_ids:
                    updated[node_id]["inputs"]["text"] = negative_prompt

    return updated


def main():
    parser = argparse.ArgumentParser(
        description="Generate images using ComfyUI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--host", "-H",
        default="127.0.0.1",
        help="ComfyUI server host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8188,
        help="ComfyUI server port (default: 8188)"
    )
    parser.add_argument(
        "--workflow", "-w",
        help="Path to workflow JSON file (or '-' for stdin)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=".",
        help="Output directory for images (default: current directory)"
    )
    parser.add_argument(
        "--output-format", "-f",
        choices=["png", "jpg", "jpeg", "webp"],
        default="png",
        help="Output image format (default: png)"
    )
    parser.add_argument(
        "--quick-test", "-t",
        action="store_true",
        help="Test server connection without generating images"
    )
    parser.add_argument(
        "--prompt",
        help="Create a simple workflow with this prompt (implies --simple)"
    )
    parser.add_argument(
        "--prompt-text",
        help="Text prompt for simple workflow"
    )
    parser.add_argument(
        "--negative-prompt",
        default="blurry, bad quality, distorted",
        help="Negative prompt for simple workflow"
    )
    parser.add_argument(
        "--width",
        type=int,
        default=512,
        help="Image width for simple workflow (default: 512)"
    )
    parser.add_argument(
        "--height",
        type=int,
        default=512,
        help="Image height for simple workflow (default: 512)"
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=20,
        help="Sampling steps for simple workflow (default: 20)"
    )
    parser.add_argument(
        "--cfg",
        type=float,
        default=7.5,
        help="CFG scale for simple workflow (default: 7.5)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed (None for random)"
    )
    parser.add_argument(
        "--checkpoint",
        default="model.safetensors",
        help="Checkpoint filename (default: model.safetensors)"
    )
    parser.add_argument(
        "--prompt-positive",
        dest="prompt_positive",
        help="Positive text prompt to apply to CLIP Text Encoder(s)"
    )
    parser.add_argument(
        "--prompt-negative",
        dest="prompt_negative",
        help="Negative text prompt to apply to CLIP Text Encoder(s)"
    )
    parser.add_argument(
        "--positive-node-id",
        dest="positive_node_id",
        action="append",
        help="Node ID(s) for positive prompt (can be specified multiple times)"
    )
    parser.add_argument(
        "--negative-node-id",
        dest="negative_node_id",
        action="append",
        help="Node ID(s) for negative prompt (can be specified multiple times)"
    )
    parser.add_argument(
        "--free-memory",
        action="store_true",
        help="Free all memory by unloading models and clearing VRAM cache"
    )
    parser.add_argument(
        "--free-unload-models",
        action="store_true",
        help="Unload models from memory when freeing memory"
    )
    parser.add_argument(
        "--free-no-vram",
        action="store_true",
        help="Don't clear VRAM cache when freeing memory"
    )
    parser.add_argument(
        "--check-queue",
        action="store_true",
        help="Check queue status and exit with code 0 if empty, 2 if jobs pending"
    )

    args = parser.parse_args()

    # Validate output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize client
    client = ComfyUIClient(host=args.host, port=args.port)

    # Check server connection
    print(f"Checking ComfyUI server at {client.base_url}...")
    if not client.check_server():
        print("Error: Could not connect to ComfyUI server.", file=sys.stderr)
        print("Please make sure ComfyUI is running and accessible.", file=sys.stderr)
        sys.exit(1)

    print("Connected to ComfyUI server!")

    if args.free_memory:
        print("Freeing memory...")
        result = client.free_memory(
            unload_models=not args.free_no_vram,
            free_vram=not args.free_no_vram
        )
        print(f"Memory freed: {json.dumps(result, indent=2)}")
        sys.exit(0)

    if args.check_queue:
        queue_info = client.get_queue_info()
        queue = queue_info.get("queue_running", [])
        queue_pending = queue_info.get("queue_pending", [])
        queued_count = len(queue) + len(queue_pending)

        print(f"Queue status: {queued_count} job(s) in queue")
        print(f"  Running: {len(queue)}")
        print(f"  Pending: {len(queue_pending)}")

        if queued_count == 0:
            print("Queue is empty")
            sys.exit(0)
        else:
            print("Queue has pending jobs")
            sys.exit(2)

    if args.quick_test:
        print("Server test passed!")
        queue_info = client.get_queue_info()
        print(f"Queue info: {json.dumps(queue_info, indent=2)}")
        sys.exit(0)

    # Load or create workflow
    if args.workflow == "-":
        print("Loading workflow from stdin...")
        workflow = load_workflow_from_stdin()
    elif args.workflow:
        print(f"Loading workflow from {args.workflow}...")
        workflow = load_workflow_from_file(args.workflow)
    elif args.prompt_text:
        print("Creating simple workflow from prompt...")
        workflow = create_simple_workflow(
            prompt=args.prompt_text,
            negative_prompt=args.negative_prompt,
            width=args.width,
            height=args.height,
            steps=args.steps,
            cfg=args.cfg,
            seed=args.seed,
            checkpoint=args.checkpoint
        )
    else:
        parser.error("Either --workflow or --prompt-text is required")

    # Apply additional prompts to CLIP Text Encoders if specified
    if args.prompt_positive or args.prompt_negative:
        print("Updating CLIP Text Encoder prompts...")
        workflow = update_workflow_prompts(
            workflow,
            positive_prompt=args.prompt_positive,
            negative_prompt=args.prompt_negative,
            positive_node_ids=args.positive_node_id,
            negative_node_ids=args.negative_node_id
        )
        if args.prompt_positive:
            print(f"  Positive prompt: {args.prompt_positive}")
        if args.prompt_negative:
            print(f"  Negative prompt: {args.prompt_negative}")

    # Generate images
    print(f"Generating images to {output_dir.absolute()}")
    result = client.generate_image_from_workflow(
        workflow,
        output_dir=output_dir,
        wait=True,
        output_format=args.output_format
    )

    if result:
        print(f"\nSuccess! Generated {len(result)} image(s):")
        for path in result:
            print(f"  - {path}")
    else:
        print("Failed to generate images", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

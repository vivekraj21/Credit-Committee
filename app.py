import os

# Root launcher for hosting platforms (Hugging Face Spaces, Replit, etc.)
# This imports the Gradio `demo` object from the project and launches
# it using the PORT env var and binding to 0.0.0.0 for external access.

from src.frontend import app as fc

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    fc.demo.queue(max_size=1)
    fc.demo.launch(server_name="0.0.0.0", server_port=port)

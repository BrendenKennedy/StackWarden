"""StackWarden stub Ollama chat UI."""
import gradio as gr
demo = gr.Interface(fn=lambda x: x, inputs="text", outputs="text", title="Ollama Chat Stub")
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0")

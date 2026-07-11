"""AI analysis via OpenRouter (DeepSeek) for graph topology interpretation.

Extracted from GraphEditor._ask_ai_tda / _do_ask_ai / _show_ai_result / _show_ai_error
to reduce main file size.
"""

from __future__ import annotations

import base64
import io
import json
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.error import URLError
from urllib.request import Request, urlopen


class AiAnalyzer:
    """Handles AI analysis of graph topology via OpenRouter / DeepSeek."""

    OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, parent_win: tk.Toplevel, api_key: str | None = None):
        self.parent_win = parent_win
        self._api_key = api_key

    def ask(self, canvas: tk.Canvas, nodes: list, edges: list):
        """Start the AI analysis flow. Prompts for API key if needed."""
        if not self._api_key:
            self._prompt_api_key(canvas, nodes, edges)
            return
        self._do_ask(canvas, nodes, edges)

    def _prompt_api_key(self, canvas: tk.Canvas, nodes: list, edges: list):
        """Show a dialog to enter the OpenRouter API key."""
        key_win = tk.Toplevel(self.parent_win)
        key_win.title("OpenRouter API Key")
        key_win.geometry("400x120")
        key_win.configure(bg="#1E1E2E")

        ttk.Label(key_win, text="Enter your OpenRouter API key:").pack(pady=(10, 5))
        key_entry = ttk.Entry(key_win, width=50, show="*")
        key_entry.pack(pady=5)

        def save_key():
            self._api_key = key_entry.get().strip()
            if self._api_key:
                key_win.destroy()
                self._do_ask(canvas, nodes, edges)

        ttk.Button(key_win, text="Save & Continue", command=save_key).pack(pady=5)
        key_win.grab_set()

    def _do_ask(self, canvas: tk.Canvas, nodes: list, edges: list):
        """Make the API call in a background thread."""
        loading = tk.Toplevel(self.parent_win)
        loading.title("Thinking...")
        loading.geometry("300x80")
        loading.configure(bg="#1E1E2E")
        ttk.Label(loading, text="🤖 Analyzing with DeepSeek...").pack(pady=20)
        loading.grab_set()

        loading_active = True

        def on_loading_close():
            nonlocal loading_active
            loading_active = False
            loading.grab_release()
            loading.destroy()

        loading.protocol("WM_DELETE_WINDOW", on_loading_close)

        # Capture canvas as base64 image
        img_base64 = None
        try:
            ps_data = canvas.postscript(colormode="color")
            if ps_data and ps_data.strip():
                try:
                    from PIL import Image

                    ps_buf = io.BytesIO(ps_data.encode("utf-8"))
                    img = Image.open(ps_buf)
                    png_buf = io.BytesIO()
                    img.save(png_buf, format="PNG")
                    img_base64 = base64.b64encode(png_buf.getvalue()).decode("utf-8")
                except ImportError:
                    pass  # PIL not installed — text-only analysis
                except Exception:
                    pass  # corrupt PostScript
        except Exception:
            pass  # postscript() failed

        V = len(nodes)
        E = len(edges)
        node_data = [
            {"label": node.label, "x": round(node.x, 1), "y": round(node.y, 1)}
            for node in nodes
        ]
        edge_data = [
            {"from": edge.source.label, "to": edge.target.label}
            for edge in edges
        ]

        # Connected components via union-find
        parent = list(range(V))

        def uf_find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def uf_union(x, y):
            px, py = uf_find(x), uf_find(y)
            if px != py:
                parent[px] = py

        node_to_idx = {id(node): i for i, node in enumerate(nodes)}
        for edge in edges:
            u = node_to_idx.get(id(edge.source))
            v = node_to_idx.get(id(edge.target))
            if u is not None and v is not None:
                uf_union(u, v)
        comps = set(uf_find(i) for i in range(V))
        beta0 = len(comps)
        beta1 = E - V + beta0
        euler_char = V - E

        system_msg = (
            "You are a topologist AI. Analyze the graph shown in the image and the "
            "accompanying topological data. Explain:\n"
            "1. What topological features does this graph have?\n"
            "2. What manifold or shape might this represent?\n"
            "3. Is there anything mathematically interesting about its structure?\n"
            "Be concise but insightful.\n"
            "Please respond in Korean."
        )

        user_content = []
        if img_base64:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_base64}"},
            })
        user_content.append({
            "type": "text",
            "text": (
                f"Here is the topological data for this graph:\n"
                f"- Vertices: {V}\n"
                f"- Edges: {E}\n"
                f"- Euler characteristic (χ = V - E): {euler_char}\n"
                f"- β₀ (connected components): {beta0}\n"
                f"- β₁ (independent cycles): {beta1}\n\n"
                f"Node positions:\n{json.dumps(node_data, indent=2)}\n\n"
                f"Edges:\n{json.dumps(edge_data, indent=2)}\n\n"
                "Please analyze the topological structure of this graph."
            ),
        })

        payload_data = {
            "model": "deepseek/deepseek-chat",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 2048,
        }

        def api_call():
            try:
                payload = json.dumps(payload_data).encode()
                req = Request(
                    self.OPENROUTER_API_URL,
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/graph-editor",
                        "X-Title": "Graph Editor TDA",
                    },
                )
                resp = urlopen(req, timeout=120)
                data = json.loads(resp.read())
                reply = data["choices"][0]["message"]["content"]
                if loading_active:
                    self.parent_win.after(0, lambda: self._show_result(reply, loading))
            except URLError as exc:
                if loading_active:
                    self.parent_win.after(0, lambda e=str(exc): self._show_error(e, loading))
            except Exception as exc:
                if loading_active:
                    self.parent_win.after(0, lambda e=str(exc): self._show_error(e, loading))

        thread = threading.Thread(target=api_call, daemon=True)
        thread.start()

    def _show_result(self, reply: str, loading_win: tk.Toplevel):
        """Display the AI analysis result."""
        try:
            if loading_win.winfo_exists():
                loading_win.grab_release()
                loading_win.destroy()
        except tk.TclError:
            pass
        result_win = tk.Toplevel(self.parent_win)
        result_win.title("🤖 DeepSeek Analysis")
        result_win.geometry("600x500")
        result_win.configure(bg="#1E1E2E")

        text_frame = ttk.Frame(result_win)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        text_widget = tk.Text(
            text_frame,
            wrap=tk.WORD,
            bg="#1E1E2E",
            fg="#FFFFFF",
            font=("Helvetica", 11),
            padx=10,
            pady=10,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        text_widget.insert(tk.END, reply)
        text_widget.config(state=tk.DISABLED)

        ttk.Button(result_win, text="Close", command=result_win.destroy).pack(pady=5)

    def _show_error(self, error_msg: str, loading_win: tk.Toplevel):
        """Show an API error to the user."""
        try:
            if loading_win.winfo_exists():
                loading_win.grab_release()
                loading_win.destroy()
        except tk.TclError:
            pass
        messagebox.showerror("API Error", f"Failed to get AI analysis:\n\n{error_msg}")


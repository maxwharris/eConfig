import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import os
import re
from pathlib import Path

RECENT_FILE = Path.home() / ".config/eConfig_recent.txt"
MAX_RECENT = 10

class ConfigEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Preserving Config Editor")
        self.geometry("1000x600")
        self.file_path = None
        self.lines = []  # Stores raw lines
        self.editable_entries = []  # Stores (line_index, key, value) for editing
        self.recent_files = []

        self.build_ui()
        self.load_recent_files()

    def build_ui(self):
        self.sidebar = tk.Listbox(self, width=40)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.bind("<<ListboxSelect>>", self.select_recent_file)

        self.editor_frame = tk.Frame(self)
        self.editor_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(self.editor_frame, columns=("Key", "Value"), show="headings")
        self.tree.heading("Key", text="Key")
        self.tree.heading("Value", text="Value")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self.edit_entry)

        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open", command=self.load_file, accelerator="Ctrl+O")
        filemenu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        menubar.add_cascade(label="File", menu=filemenu)
        self.config(menu=menubar)

        self.bind_all("<Control-s>", lambda e: self.save_file())
        self.bind_all("<Control-o>", lambda e: self.load_file())

    def load_recent_files(self):
        if RECENT_FILE.exists():
            with open(RECENT_FILE, "r") as f:
                self.recent_files = [line.strip() for line in f if Path(line.strip()).exists()]
        self.refresh_sidebar()

    def save_recent_file(self, path):
        path = str(Path(path).resolve())
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:MAX_RECENT]
        RECENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(RECENT_FILE, "w") as f:
            f.write("\n".join(self.recent_files))
        self.refresh_sidebar()

    def refresh_sidebar(self):
        self.sidebar.delete(0, tk.END)
        for path in self.recent_files:
            self.sidebar.insert(tk.END, path)

    def select_recent_file(self, event):
        selection = self.sidebar.curselection()
        if not selection:
            return
        path = self.sidebar.get(selection[0])
        self.load_file(path_override=path)

    def load_file(self, path_override=None):
        if path_override:
            path = path_override
        else:
            path = filedialog.askopenfilename(initialdir=str(Path.home() / ".config"),
                                              filetypes=[("Config Files", "*.conf *.txt")])
        if not path:
            return
        self.file_path = path
        with open(path, "r") as f:
            self.lines = f.readlines()
        self.save_recent_file(path)
        self.parse_lines()
        self.refresh_tree()

    def parse_lines(self):
        self.editable_entries.clear()
        for idx, line in enumerate(self.lines):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped and not stripped.endswith("{") and not stripped == "}":
                key, val = map(str.strip, stripped.split("=", 1))
                self.editable_entries.append((idx, key, val))

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for idx, key, val in self.editable_entries:
            self.tree.insert("", "end", iid=str(idx), values=(key, val))

    def edit_entry(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        idx = int(selected[0])
        line_idx, key, old_val = next((i for i in self.editable_entries if i[0] == idx), (None, None, None))
        if line_idx is None:
            return
        new_val = simpledialog.askstring("Edit Value", f"Edit value for '{key}':", initialvalue=old_val)
        if new_val is not None:
            self.lines[line_idx] = f"{key} = {new_val}\n"
            self.editable_entries = [(i, k, new_val if i == line_idx else v) for i, k, v in self.editable_entries]
            self.refresh_tree()

    def save_file(self):
        if not self.file_path:
            self.file_path = filedialog.asksaveasfilename(defaultextension=".conf")
        with open(self.file_path, "w") as f:
            f.writelines(self.lines)
        self.save_recent_file(self.file_path)
        messagebox.showinfo("Saved", f"Saved to {self.file_path}")

if __name__ == "__main__":
    app = ConfigEditor()
    app.mainloop()
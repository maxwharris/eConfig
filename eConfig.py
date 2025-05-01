import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import os
import re
from pathlib import Path
import copy

RECENT_FILE = Path.home() / ".config/eConfig_recent.txt"
MAX_RECENT = 10

class ConfigEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Preserving Config Editor")
        self.geometry("1000x600")
        self.file_path = None
        self.lines = []
        self.editable_entries = []
        self.recent_files = []
        self.undo_stack = []
        self.redo_stack = []

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

        self.tree.tag_configure("even", background="#f0f0f0")
        self.tree.tag_configure("odd", background="#ffffff")

        self.tree.bind("<Double-1>", self.edit_entry)
        self.tree.bind("<Button-3>", self.show_context_menu)

        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open", command=self.load_file, accelerator="Ctrl+O")
        filemenu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        filemenu.add_command(label="Undo", command=self.undo_action, accelerator="Ctrl+Z")
        filemenu.add_command(label="Redo", command=self.redo_action, accelerator="Ctrl+Y")
        menubar.add_cascade(label="File", menu=filemenu)
        self.config(menu=menubar)

        self.bind_all("<Control-s>", lambda e: self.save_file())
        self.bind_all("<Control-o>", lambda e: self.load_file())
        self.bind_all("<Control-n>", lambda e: self.add_entry())
        self.bind_all("<Control-z>", lambda e: self.undo_action())
        self.bind_all("<Control-y>", lambda e: self.redo_action())

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
            path = filedialog.askopenfilename(
                initialdir=str(Path.home() / ".config"),
                filetypes=[("All Files", "*.*")]
            )
        if not path:
            return
        self.file_path = path
        with open(path, "r") as f:
            self.lines = f.readlines()
        self.save_recent_file(path)
        self.parse_lines()
        self.refresh_tree()
        self.undo_stack.clear()

    def parse_lines(self):
        self.editable_entries.clear()
        nesting = []
        for idx, line in enumerate(self.lines):
            stripped = line.strip()
            if stripped.endswith("{") and not stripped.lstrip().startswith('#'):
                nesting.append(stripped[:-1].strip())
            elif stripped == "}":
                if nesting:
                    nesting.pop()
            elif "=" in stripped and not stripped.startswith("#"):
                key, val = map(str.strip, stripped.split("=", 1))
                full_key = ".".join(nesting + [key]) if nesting else key
                self.editable_entries.append((idx, full_key, val))

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for row_num, (idx, key, val) in enumerate(self.editable_entries):
            tag = "even" if row_num % 2 == 0 else "odd"
            self.tree.insert("", "end", iid=str(idx), values=(key, val), tags=(tag,))

    def edit_entry(self, event=None):
        selected = self.tree.selection()
        if not selected:
            return
        idx = int(selected[0])
        line_idx, full_key, old_val = next((i for i in self.editable_entries if i[0] == idx), (None, None, None))
        if line_idx is None:
            return
        new_val = simpledialog.askstring("Edit Value", f"Edit value for '{full_key}':", initialvalue=old_val)
        if new_val is not None:
            self.push_undo()
            key = full_key.split(".")[-1]
            indent = re.match(r"^\s*", self.lines[line_idx]).group(0)
            self.lines[line_idx] = f"{indent}{key} = {new_val}\n"
            self.parse_lines()
            self.refresh_tree()

    def delete_entry(self):
        selected = self.tree.selection()
        if not selected:
            return
        self.push_undo()
        idx = int(selected[0])
        self.lines[idx] = ""
        self.parse_lines()
        self.refresh_tree()

    def add_entry(self):
        selected = self.tree.selection()
        if not selected:
            return
        idx = int(selected[0])
        line_idx, full_key, _ = next((i for i in self.editable_entries if i[0] == idx), (None, None, None))
        if line_idx is None:
            return
        self.push_undo()
        parent_path = ".".join(full_key.split(".")[:-1])
        suggested_key = f"{parent_path}." if parent_path else ""
        key = simpledialog.askstring("New Key", "Enter new key:", initialvalue=suggested_key)
        value = simpledialog.askstring("New Value", "Enter value:")
        if key and value:
            indent = re.match(r"^\s*", self.lines[line_idx]).group(0)
            key_base = key.split(".")[-1]
            new_line = f"{indent}{key_base} = {value}\n"
            self.lines.insert(line_idx + 1, new_line)
            self.parse_lines()
            self.refresh_tree()

    def show_context_menu(self, event):
        selected = self.tree.identify_row(event.y)
        if not selected:
            return
        self.tree.selection_set(selected)
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Edit", command=self.edit_entry)
        menu.add_command(label="Delete", command=self.delete_entry)
        menu.add_command(label="Add New Key Below", command=self.add_entry)
        menu.tk_popup(event.x_root, event.y_root)

    def push_undo(self):
        self.redo_stack.clear()
        self.undo_stack.append(copy.deepcopy(self.lines))
        if len(self.undo_stack) > 20:
            self.undo_stack.pop(0)

    def undo_action(self):
        if self.undo_stack:
            self.lines = self.undo_stack.pop()
            self.parse_lines()
            self.refresh_tree()
        else:
            messagebox.showinfo("Undo", "Nothing to undo.")

    
    def redo_action(self):
        if self.redo_stack:
            self.undo_stack.append(copy.deepcopy(self.lines))
            self.lines = self.redo_stack.pop()
            self.parse_lines()
            self.refresh_tree()
        else:
            messagebox.showinfo("Redo", "Nothing to redo.")

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
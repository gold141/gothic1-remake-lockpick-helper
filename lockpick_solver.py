"""
Gothic 1 Remake — Lockpick Helper v4 (Multilingual)

Supported languages: Русский, English, Deutsch, Español

Visual lock editor:
- 4–7 plates arranged horizontally
- SETUP mode: click circles to set pin positions
- LINKS mode: click plate to select source, arrows [↑][↓] set links
- BFS solver
- Auto-execution via F2
"""

import ctypes
import threading
import time
import tkinter as tk
from collections import deque
from tkinter import messagebox, ttk

import keyboard

from translations import get_translation

# ── constants ──────────────────────────────────────────────────
NUM_POSITIONS = 7
TARGET_POS = 4
CIRCLE_SIZE = 24
CIRCLE_PAD = 6
PLATE_WIDTH = CIRCLE_SIZE + 20
PLATE_HEIGHT = NUM_POSITIONS * (CIRCLE_SIZE + CIRCLE_PAD) + CIRCLE_PAD
PLATE_SPACING = 82
MARGIN_X = 40
MARGIN_Y = 60

MODE_SETUP = "setup"
MODE_LINKS = "links"

LANGUAGES = {
    "ru": "Русский",
    "en": "English",
    "de": "Deutsch",
    "es": "Español",
}


class LockpickApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.configure(bg="#1e1e1e")
        self.resizable(False, False)

        # ── state ──
        self.num_plates = 6
        self.pins = []
        self.active_plate = 0
        self.mode = MODE_SETUP
        self.connection_matrix = []
        self.is_executing = False
        self.lang = "ru"  # default language
        self._tr = get_translation(self.lang)

        self._build_ui()
        self.reset_all()
        self._register_hotkeys()

    def _(self, key, **kwargs):
        """Get translated string."""
        text = self._tr.get(key, key)
        if kwargs:
            return text.format(**kwargs)
        return text

    def _build_ui(self):
        # ═══════════════════════════════════════
        # TOP PANEL — modes, plates count, language, reset
        # ═══════════════════════════════════════
        top_frame = tk.Frame(self, bg="#1e1e1e")
        top_frame.pack(fill=tk.X, padx=10, pady=10)

        self.btn_setup = tk.Button(
            top_frame, text=self._("setup_plates"),
            bg="#2196F3", fg="white", font=("Segoe UI", 10, "bold"),
            bd=0, padx=15, pady=6,
            command=lambda: self.set_mode(MODE_SETUP)
        )
        self.btn_setup.pack(side=tk.LEFT, padx=3)

        self.btn_links = tk.Button(
            top_frame, text=self._("configure_links"),
            bg="#555", fg="white", font=("Segoe UI", 10, "bold"),
            bd=0, padx=15, pady=6,
            command=lambda: self.set_mode(MODE_LINKS)
        )
        self.btn_links.pack(side=tk.LEFT, padx=3)

        # Plates count selector
        tk.Label(top_frame, text=self._("plates_count"), bg="#1e1e1e", fg="#aaa",
                font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(15, 5))
        self.plates_var = tk.IntVar(value=6)
        self.plates_combo = ttk.Combobox(
            top_frame, values=[4, 5, 6, 7], state="readonly",
            width=5, font=("Segoe UI", 10)
        )
        self.plates_combo.current(2)
        self.plates_combo.pack(side=tk.LEFT, padx=3)
        self.plates_combo.bind("<<ComboboxSelected>>", self.on_plates_changed)

        # Language selector
        tk.Label(top_frame, text=self._("lang_label"), bg="#1e1e1e", fg="#aaa",
                font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(15, 5))
        self.lang_combo = ttk.Combobox(
            top_frame, values=list(LANGUAGES.values()), state="readonly",
            width=12, font=("Segoe UI", 10)
        )
        self.lang_combo.current(0)  # Russian
        self.lang_combo.pack(side=tk.LEFT, padx=3)
        self.lang_combo.bind("<<ComboboxSelected>>", self.on_lang_changed)

        # Reset button
        self.btn_reset = tk.Button(
            top_frame, text=self._("reset"),
            bg="#f44336", fg="white", font=("Segoe UI", 10, "bold"),
            bd=0, padx=15, pady=6,
            command=self.reset_all
        )
        self.btn_reset.pack(side=tk.LEFT, padx=10)

        # Solve button
        self.btn_solve = tk.Button(
            top_frame, text=self._("solve"),
            bg="#4CAF50", fg="white", font=("Segoe UI", 11, "bold"),
            bd=0, padx=25, pady=6,
            command=self.solve
        )
        self.btn_solve.pack(side=tk.RIGHT, padx=5)

        # ═══════════════════════════════════════
        # CANVAS — plates + arrows
        # ═══════════════════════════════════════
        self.canvas = tk.Canvas(
            self, bg="#1e1e1e", highlightthickness=0
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        # ═══════════════════════════════════════
        # BOTTOM PANEL — status and log
        # ═══════════════════════════════════════
        bottom_frame = tk.Frame(self, bg="#1e1e1e")
        bottom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.status_label = tk.Label(
            bottom_frame, text="",
            bg="#1e1e1e", fg="#aaa", font=("Segoe UI", 10)
        )
        self.status_label.pack(anchor=tk.W)

        self.log_label = tk.Label(bottom_frame, text=self._("log"), bg="#1e1e1e", fg="#666",
                font=("Segoe UI", 9))
        self.log_label.pack(anchor=tk.W, pady=(10, 0))

        self.log_text = tk.Text(
            bottom_frame, height=6, wrap=tk.WORD,
            bg="#141414", fg="#00ff88",
            font=("Consolas", 10),
            relief=tk.FLAT, padx=8, pady=8
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def set_mode(self, mode):
        self.mode = mode
        if mode == MODE_SETUP:
            self.btn_setup.config(bg="#2196F3")
            self.btn_links.config(bg="#555")
            self.status_label.config(
                text=self._("mode_setup"),
                fg="#4fc3f7"
            )
        else:
            self.btn_setup.config(bg="#555")
            self.btn_links.config(bg="#ff9800")
            self.status_label.config(
                text=self._("mode_links", n=self.active_plate + 1),
                fg="#ffb74d"
            )
        self.update_display()

    def on_lang_changed(self, event=None):
        """Handle language change."""
        lang_name = self.lang_combo.get()
        # Find language code by name
        for code, name in LANGUAGES.items():
            if name == lang_name:
                if code != self.lang:
                    self.lang = code
                    self._tr = get_translation(code)
                    self._update_ui_texts()
                    self.set_mode(self.mode)
                    self.log(self._("app_started"))
                break

    def _update_ui_texts(self):
        """Update all UI texts after language change."""
        self.title("Gothic Lockpick Helper")
        self.btn_setup.config(text=self._("setup_plates"))
        self.btn_links.config(text=self._("configure_links"))
        self.btn_reset.config(text=self._("reset"))
        self.btn_solve.config(text=self._("solve"))
        self.log_label.config(text=self._("log"))
        # Update combo labels would require recreating or tracking label widgets

    def on_plates_changed(self, event=None):
        """Handle plates count change."""
        new_count = int(self.plates_combo.get())
        if new_count != self.num_plates:
            self.num_plates = new_count
            self.reset_all()
            self.log(self._("plates_changed", n=new_count))

    def reset_all(self):
        """Reset: all plates to center, identity link matrix."""
        self.pins = [TARGET_POS] * self.num_plates
        self.active_plate = 0
        self.connection_matrix = [
            [1 if i == j else 0 for j in range(self.num_plates)]
            for i in range(self.num_plates)
        ]
        canvas_w = MARGIN_X * 2 + self.num_plates * PLATE_SPACING
        canvas_h = MARGIN_Y * 2 + PLATE_HEIGHT + 80
        self.canvas.config(width=canvas_w, height=canvas_h)
        win_w = max(600, canvas_w + 80)
        win_h = 620
        self.geometry(f"{win_w}x{win_h}")
        self.set_mode(self.mode)
        self.log(self._("reset_done"))

    def _register_hotkeys(self):
        """Register global hotkeys."""
        try:
            keyboard.add_hotkey("f2", lambda: self.after(0, self.execute_solution))
            self.log(self._("hotkey_ok"))
        except Exception as e:
            self.log(self._("hotkey_error", err=str(e)))

    def execute_solution(self):
        """
        Start/stop auto-execution.
        On F2:
          - If not running → start
          - If running → stop
        """
        if self.is_executing:
            self.is_executing = False
            self.log(self._("auto_stopped"))
            return

        solution = self._bfs_solve()
        if solution is None:
            self.log(self._("no_solution"))
            return
        if len(solution) == 0:
            self.log(self._("already_solved"))
            return

        self.is_executing = True
        self.log(self._("auto_start"))
        self.log(self._("auto_warning"))
        self.log(self._("auto_stop_hint"))

        threading.Thread(target=self._run_solution, args=(solution,), daemon=True).start()

    def _run_solution(self, solution):
        """Execute moves in game via keybd_event."""
        user32 = ctypes.windll.user32
        KEYEVENTF_KEYUP = 2
        VK_W = 0x57
        VK_S = 0x53
        VK_A = 0x41
        VK_D = 0x44
        STEP_DELAY = 0.45  # + 0.05 press = 0.5 sec total

        def press_key(vk):
            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(STEP_DELAY)

        try:
            # ── PREPARATION: S × 8 (down to first plate) ──
            self.log(self._("prep"))
            for i in range(8):
                if not self.is_executing:
                    return
                press_key(VK_S)

            current_plate = 0
            self.log(self._("prep_done"))

            # ── EXECUTE MOVES ──
            for idx, (plate, direction) in enumerate(solution):
                if not self.is_executing:
                    self.after(0, lambda: self.log(self._("exec_interrupted")))
                    return

                # Select plate (W = up, S = down)
                if plate > current_plate:
                    steps = plate - current_plate
                    self.after(0, lambda p=plate+1, s=steps:
                        self.log(self._("select_up", s=s, p=p)))
                    for _ in range(steps):
                        if not self.is_executing:
                            return
                        press_key(VK_W)

                elif plate < current_plate:
                    steps = current_plate - plate
                    self.after(0, lambda p=plate+1, s=steps:
                        self.log(self._("select_down", s=s, p=p)))
                    for _ in range(steps):
                        if not self.is_executing:
                            return
                        press_key(VK_S)

                # Press A or D
                if direction > 0:
                    vk = VK_D
                    key_name = "D"
                else:
                    vk = VK_A
                    key_name = "A"

                self.after(0, lambda p=plate+1, k=key_name, n=idx+1:
                    self.log(self._("move", n=n, p=p, key=k)))

                press_key(vk)
                current_plate = plate

            self.after(0, lambda: self.log(self._("auto_done")))

        except Exception as e:
            self.after(0, lambda err=str(e): self.log(self._("exec_error", err=err)))
        finally:
            self.is_executing = False

    def on_canvas_click(self, event):
        """Handle canvas clicks."""
        x, y = event.x, event.y

        for plate_idx in range(self.num_plates):
            px = MARGIN_X + plate_idx * PLATE_SPACING
            py = MARGIN_Y

            if self.mode == MODE_SETUP:
                # Check circle click
                for pos in range(1, NUM_POSITIONS + 1):
                    cx = px + PLATE_WIDTH // 2
                    cy = py + (pos - 1) * (CIRCLE_SIZE + CIRCLE_PAD) + CIRCLE_PAD + CIRCLE_SIZE // 2
                    if (x - cx) ** 2 + (y - cy) ** 2 <= (CIRCLE_SIZE // 2) ** 2:
                        self.pins[plate_idx] = pos
                        self.active_plate = plate_idx
                        self.log(self._("pin_set", n=plate_idx + 1, pos=pos))
                        self.update_display()
                        return

            elif self.mode == MODE_LINKS:
                # Check plate click
                if px <= x <= px + PLATE_WIDTH and py <= y <= py + PLATE_HEIGHT:
                    self.active_plate = plate_idx
                    self.status_label.config(
                        text=self._("mode_links", n=plate_idx + 1),
                        fg="#ffb74d"
                    )
                    self.update_display()
                    return

                # Up arrow
                arrow_up_y = py - 35
                if (px + 10 <= x <= px + 35 and arrow_up_y <= y <= arrow_up_y + 25):
                    self.toggle_arrow(plate_idx, 1)
                    return
                # Down arrow
                arrow_down_y = py + PLATE_HEIGHT + 10
                if (px + 10 <= x <= px + 35 and arrow_down_y <= y <= arrow_down_y + 25):
                    self.toggle_arrow(plate_idx, -1)
                    return

    def toggle_arrow(self, plate_idx, direction):
        """Toggle link arrow. direction: 1 (↑) or -1 (↓)."""
        active = self.active_plate
        current = self.connection_matrix[plate_idx][active]

        if direction == 1:
            if current == 1:
                self.connection_matrix[plate_idx][active] = 0
                self.log(self._("link_off", n=plate_idx + 1, src=active + 1))
            else:
                self.connection_matrix[plate_idx][active] = 1
                if plate_idx == active:
                    self.log(self._("diag_up", n=plate_idx + 1))
                else:
                    self.log(self._("link_up", n=plate_idx + 1, src=active + 1))
        else:
            if current == -1:
                self.connection_matrix[plate_idx][active] = 0
                self.log(self._("link_off", n=plate_idx + 1, src=active + 1))
            else:
                self.connection_matrix[plate_idx][active] = -1
                if plate_idx == active:
                    self.log(self._("diag_down", n=plate_idx + 1))
                else:
                    self.log(self._("link_down", n=plate_idx + 1, src=active + 1))

        self.update_display()

    def update_display(self):
        """Redraw canvas."""
        self.canvas.delete("all")

        for plate_idx in range(self.num_plates):
            px = MARGIN_X + plate_idx * PLATE_SPACING
            py = MARGIN_Y

            is_active = (plate_idx == self.active_plate)
            is_source = (self.mode == MODE_LINKS and is_active)

            # Label
            label_color = "#ff9800" if is_source else ("#4fc3f7" if is_active else "#888")
            label_text = f"{self._('plate_label')}{plate_idx + 1}"
            if is_source:
                label_text += " ✓"

            self.canvas.create_text(
                px + PLATE_WIDTH // 2, py - 12,
                text=label_text, fill=label_color,
                font=("Segoe UI", 11, "bold")
            )

            # Active frame
            if is_active:
                self.canvas.create_rectangle(
                    px - 5, py - 5, px + PLATE_WIDTH + 5, py + PLATE_HEIGHT + 5,
                    outline=label_color, width=2
                )

            # 7 circles
            for pos in range(1, NUM_POSITIONS + 1):
                cx = px + PLATE_WIDTH // 2
                cy = py + (pos - 1) * (CIRCLE_SIZE + CIRCLE_PAD) + CIRCLE_PAD + CIRCLE_SIZE // 2

                if pos == self.pins[plate_idx]:
                    self.canvas.create_oval(
                        cx - CIRCLE_SIZE // 2, cy - CIRCLE_SIZE // 2,
                        cx + CIRCLE_SIZE // 2, cy + CIRCLE_SIZE // 2,
                        fill="#ff3333", outline="#ff6666", width=3
                    )
                    self.canvas.create_oval(
                        cx - CIRCLE_SIZE // 2 + 4, cy - CIRCLE_SIZE // 2 + 4,
                        cx - CIRCLE_SIZE // 2 + 10, cy - CIRCLE_SIZE // 2 + 10,
                        fill="#ff9999", outline=""
                    )
                else:
                    self.canvas.create_oval(
                        cx - CIRCLE_SIZE // 2, cy - CIRCLE_SIZE // 2,
                        cx + CIRCLE_SIZE // 2, cy + CIRCLE_SIZE // 2,
                        fill="#2a2a2a", outline="#555", width=1
                    )

                self.canvas.create_text(
                    cx + 20, cy, text=str(pos),
                    fill="#555", font=("Segoe UI", 8)
                )

            # Link arrows
            if self.mode == MODE_LINKS:
                link_value = self.connection_matrix[plate_idx][self.active_plate]

                up_color = "#4CAF50" if link_value == 1 else "#444"
                up_fill = "#4CAF50" if link_value == 1 else "#1e1e1e"
                self._draw_arrow(px + 10, py - 35, "up", up_color, up_fill)

                down_color = "#ff3333" if link_value == -1 else "#444"
                down_fill = "#ff3333" if link_value == -1 else "#1e1e1e"
                self._draw_arrow(px + 10, py + PLATE_HEIGHT + 10, "down", down_color, down_fill)

    def _draw_arrow(self, x, y, direction, color, fill):
        """Draw arrow button."""
        w, h = 25, 25
        self.canvas.create_rectangle(x, y, x + w, y + h, fill=fill, outline=color, width=2)

        cx, cy = x + w // 2, y + h // 2
        if direction == "up":
            self.canvas.create_line(cx, cy + 6, cx, cy - 6, fill=color, width=2)
            self.canvas.create_line(cx, cy - 6, cx - 4, cy - 2, fill=color, width=2)
            self.canvas.create_line(cx, cy - 6, cx + 4, cy - 2, fill=color, width=2)
        else:
            self.canvas.create_line(cx, cy - 6, cx, cy + 6, fill=color, width=2)
            self.canvas.create_line(cx, cy + 6, cx - 4, cy + 2, fill=color, width=2)
            self.canvas.create_line(cx, cy + 6, cx + 4, cy + 2, fill=color, width=2)

    def solve(self):
        """Run BFS solver."""
        self.log("=" * 40)
        self.log(self._("searching"))

        # Check diagonal
        for i in range(self.num_plates):
            if self.connection_matrix[i][i] == 0:
                self.log(self._("diag_zero_warn", i=i))
                messagebox.showwarning(self._("diag_check"), self._("diag_must_be", i=i+1))
                return

        solution = self._bfs_solve()

        if solution is None:
            self.log(self._("no_solution_found"))
            messagebox.showinfo(self._("result"), self._("check_links"))
        else:
            lines = [self._("solution_found", n=len(solution))]
            moves = []
            prev_plate = None
            for plate, direction in solution:
                phys_dir = direction * self.connection_matrix[plate][plate]
                arrow = "→" if phys_dir > 0 else "←"
                if plate == prev_plate:
                    moves.append(arrow)
                else:
                    moves.append(f"{plate + 1}{arrow}")
                    prev_plate = plate
            lines.append(" ".join(moves))

            result = "\n".join(lines)
            self.log(result)

            win = tk.Toplevel(self)
            win.title(self._("result"))
            win.configure(bg="#1e1e1e")
            win.geometry("400x400")
            win.resizable(False, False)

            tk.Label(win, text=self._("solution_title"), bg="#1e1e1e", fg="#00ff88",
                    font=("Segoe UI", 14, "bold")).pack(pady=15)

            txt = tk.Text(win, wrap=tk.WORD, bg="#141414", fg="white",
                         font=("Consolas", 12), relief=tk.FLAT, padx=15, pady=10)
            txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            txt.insert("1.0", result)
            txt.config(state=tk.DISABLED)

            tk.Button(win, text=self._("close"), command=win.destroy,
                     bg="#444", fg="white", font=("Segoe UI", 11), bd=0).pack(pady=10)

    def _bfs_solve(self):
        """Breadth-first search."""
        start = tuple(self.pins)
        goal = tuple([TARGET_POS] * self.num_plates)

        if start == goal:
            return []

        queue = deque()
        queue.append((start, []))
        visited = {start}

        while queue:
            state, path = queue.popleft()

            for plate in range(self.num_plates):
                for direction in [1, -1]:
                    new_state = list(state)
                    valid = True

                    for i in range(self.num_plates):
                        change = direction * self.connection_matrix[i][plate]
                        # Moving plate right → pin shifts left
                        new_pos = new_state[i] - change
                        if new_pos < 1 or new_pos > NUM_POSITIONS:
                            valid = False
                            break
                        new_state[i] = new_pos

                    if not valid:
                        continue

                    new_state_tuple = tuple(new_state)
                    if new_state_tuple in visited:
                        continue

                    new_path = path + [(plate, direction)]

                    if new_state_tuple == goal:
                        return new_path

                    visited.add(new_state_tuple)
                    queue.append((new_state_tuple, new_path))

        return None

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)


# ── entry point ────────────────────────────────────────────────

if __name__ == "__main__":
    app = LockpickApp()
    app.mainloop()

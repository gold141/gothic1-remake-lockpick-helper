"""
Gothic 1 Remake — Lockpick Helper v3

Визуальный редактор замка:
- 5–7 пластин расположены горизонтально (слева направо)
- Режим УСТАНОВКИ: клик по кружку = позиция штифта
- Режим СВЯЗЕЙ: клик по пластине = выбор источника, стрелки [↑][↓] задают связи
- BFS решатель
"""

import ctypes
import threading
import time
import tkinter as tk
from collections import deque
from tkinter import messagebox, ttk

import keyboard

# ── константы ──────────────────────────────────────────────────
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


class LockpickApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gothic Lockpick Helper")
        self.configure(bg="#1e1e1e")
        self.resizable(False, False)

        # ── состояние ──
        self.num_plates = 6  # по умолчанию
        self.pins = []
        self.active_plate = 0
        self.mode = MODE_SETUP
        self.connection_matrix = []

        self.is_executing = False
        self._build_ui()
        self.reset_all()  # инициализация
        self._register_hotkeys()

    def _build_ui(self):
        # ═══════════════════════════════════════
        # ВЕРХНЯЯ ПАНЕЛЬ — режимы, количество, сброс
        # ═══════════════════════════════════════
        top_frame = tk.Frame(self, bg="#1e1e1e")
        top_frame.pack(fill=tk.X, padx=10, pady=10)

        self.btn_setup = tk.Button(
            top_frame, text="УСТАНОВИТЬ ПЛАСТИНЫ",
            bg="#2196F3", fg="white", font=("Segoe UI", 10, "bold"),
            bd=0, padx=15, pady=6,
            command=lambda: self.set_mode(MODE_SETUP)
        )
        self.btn_setup.pack(side=tk.LEFT, padx=3)

        self.btn_links = tk.Button(
            top_frame, text="НАСТРОИТЬ СВЯЗИ",
            bg="#555", fg="white", font=("Segoe UI", 10, "bold"),
            bd=0, padx=15, pady=6,
            command=lambda: self.set_mode(MODE_LINKS)
        )
        self.btn_links.pack(side=tk.LEFT, padx=3)

        # Выбор количества пластин
        tk.Label(top_frame, text="Пластин:", bg="#1e1e1e", fg="#aaa",
                font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(15, 5))
        self.plates_var = tk.IntVar(value=6)
        self.plates_combo = ttk.Combobox(
            top_frame, values=[4, 5, 6, 7], state="readonly",
            width=5, font=("Segoe UI", 10)
        )
        self.plates_combo.current(2)  # 6
        self.plates_combo.pack(side=tk.LEFT, padx=3)
        self.plates_combo.bind("<<ComboboxSelected>>", self.on_plates_changed)

        # Кнопка СБРОС
        tk.Button(
            top_frame, text="СБРОС",
            bg="#f44336", fg="white", font=("Segoe UI", 10, "bold"),
            bd=0, padx=15, pady=6,
            command=self.reset_all
        ).pack(side=tk.LEFT, padx=10)

        tk.Button(
            top_frame, text="РЕШИТЬ",
            bg="#4CAF50", fg="white", font=("Segoe UI", 11, "bold"),
            bd=0, padx=25, pady=6,
            command=self.solve
        ).pack(side=tk.RIGHT, padx=5)

        # ═══════════════════════════════════════
        # CANVAS — пластины + стрелки
        # ═══════════════════════════════════════
        self.canvas = tk.Canvas(
            self, bg="#1e1e1e", highlightthickness=0
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        # ═══════════════════════════════════════
        # НИЖНЯЯ ПАНЕЛЬ — статус и лог
        # ═══════════════════════════════════════
        bottom_frame = tk.Frame(self, bg="#1e1e1e")
        bottom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.status_label = tk.Label(
            bottom_frame, text="",
            bg="#1e1e1e", fg="#aaa", font=("Segoe UI", 10)
        )
        self.status_label.pack(anchor=tk.W)

        tk.Label(bottom_frame, text="Лог:", bg="#1e1e1e", fg="#666",
                font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(10, 0))

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
                text="Режим: УСТАНОВКА ПЛАСТИН — кликайте по кружкам",
                fg="#4fc3f7"
            )
        else:
            self.btn_setup.config(bg="#555")
            self.btn_links.config(bg="#ff9800")
            self.status_label.config(
                text=f"Режим: СВЯЗИ — пластина {self.active_plate + 1} активна. Нажимайте стрелки",
                fg="#ffb74d"
            )
        self.update_display()

    def on_plates_changed(self, event=None):
        """Обработчик изменения количества пластин."""
        new_count = int(self.plates_combo.get())
        if new_count != self.num_plates:
            self.num_plates = new_count
            self.reset_all()
            self.log(f"Изменено количество пластин: {new_count}")

    def reset_all(self):
        """Сброс: все пластины в центр, единичная матрица связей."""
        self.pins = [TARGET_POS] * self.num_plates
        self.active_plate = 0
        self.connection_matrix = [
            [1 if i == j else 0 for j in range(self.num_plates)]
            for i in range(self.num_plates)
        ]
        # Обновляем размер окна под количество пластин
        canvas_w = MARGIN_X * 2 + self.num_plates * PLATE_SPACING
        canvas_h = MARGIN_Y * 2 + PLATE_HEIGHT + 80
        self.canvas.config(width=canvas_w, height=canvas_h)
        win_w = max(600, canvas_w + 80)
        win_h = 620
        self.geometry(f"{win_w}x{win_h}")
        self.set_mode(self.mode)
        self.log("🔄 Сброс: все пластины в центр, связи очищены")

    def _register_hotkeys(self):
        """Регистрация глобальных горячих клавиш."""
        try:
            keyboard.add_hotkey("f2", lambda: self.after(0, self.execute_solution))
            self.log("Горячая клавиша F2 зарегистрирована (автовыполнение / остановка)")
        except Exception as e:
            self.log(f"⚠️ Не удалось зарегистрировать F2: {e}")

    def execute_solution(self):
        """
        Запускает автовыполнение решения в игре.
        При нажатии F2:
          - Если не выполняется → запускает
          - Если выполняется → останавливает
        """
        if self.is_executing:
            self.is_executing = False
            self.log("⏹ Автовыполнение остановлено пользователем")
            return

        solution = self._bfs_solve()
        if solution is None:
            self.log("❌ Нет решения для выполнения. Нажмите РЕШИТЬ чтобы проверить.")
            return
        if len(solution) == 0:
            self.log("✅ Уже решено! Нечего выполнять.")
            return

        self.is_executing = True
        self.log("🚀 Автовыполнение начато...")
        self.log("   Не нажимайте клавиши во время выполнения!")
        self.log("   Нажмите F2 ещё раз для остановки.")

        # Запускаем в фоновом потоке
        threading.Thread(target=self._run_solution, args=(solution,), daemon=True).start()

    def _run_solution(self, solution):
        """Выполняет ходы в игре через keybd_event."""
        user32 = ctypes.windll.user32
        KEYEVENTF_KEYUP = 2
        VK_W = 0x57
        VK_S = 0x53
        VK_A = 0x41
        VK_D = 0x44
        STEP_DELAY = 0.45  # + 0.05 на само нажатие = 0.5 сек

        def press_key(vk):
            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(STEP_DELAY)

        try:
            # ── ПОДГОТОВКА: 8 раз S (вниз к первой пластине) ──
            self.log("Подготовка: S × 8 (вниз к первой пластине)...")
            for i in range(8):
                if not self.is_executing:
                    return
                press_key(VK_S)

            current_plate = 0  # после S×8 мы точно на пластине 1 (индекс 0)
            self.log("✅ Подготовка завершена. Выполняю ходы...")

            # ── ВЫПОЛНЕНИЕ ХОДОВ ──
            for idx, (plate, direction) in enumerate(solution):
                if not self.is_executing:
                    self.after(0, lambda: self.log("⏹ Выполнение прервано"))
                    return

                # Выбираем нужную пластину (W = вверх, S = вниз)
                if plate > current_plate:
                    steps = plate - current_plate
                    self.after(0, lambda p=plate+1, s=steps: 
                        self.log(f"  Выбор: W × {s} (к пластине {p})"))
                    for _ in range(steps):
                        if not self.is_executing:
                            return
                        press_key(VK_W)

                elif plate < current_plate:
                    steps = current_plate - plate
                    self.after(0, lambda p=plate+1, s=steps: 
                        self.log(f"  Выбор: S × {s} (к пластине {p})"))
                    for _ in range(steps):
                        if not self.is_executing:
                            return
                        press_key(VK_S)

                # Нажимаем A или D
                if direction > 0:
                    vk = VK_D
                    key_name = "D"
                else:
                    vk = VK_A
                    key_name = "A"

                self.after(0, lambda p=plate+1, k=key_name, n=idx+1: 
                    self.log(f"  Ход {n}: Пластина {p} → {k}"))

                press_key(vk)
                current_plate = plate

            self.after(0, lambda: self.log("✅ Автовыполнение завершено!"))

        except Exception as e:
            self.after(0, lambda err=str(e): self.log(f"❌ Ошибка выполнения: {err}"))
        finally:
            self.is_executing = False

    def on_canvas_click(self, event):
        """Обработка кликов по Canvas."""
        x, y = event.x, event.y

        for plate_idx in range(self.num_plates):
            px = MARGIN_X + plate_idx * PLATE_SPACING
            py = MARGIN_Y

            if self.mode == MODE_SETUP:
                # Проверяем клик по кружку
                for pos in range(1, NUM_POSITIONS + 1):
                    cx = px + PLATE_WIDTH // 2
                    cy = py + (pos - 1) * (CIRCLE_SIZE + CIRCLE_PAD) + CIRCLE_PAD + CIRCLE_SIZE // 2
                    if (x - cx) ** 2 + (y - cy) ** 2 <= (CIRCLE_SIZE // 2) ** 2:
                        self.pins[plate_idx] = pos
                        self.active_plate = plate_idx
                        self.log(f"Пластина {plate_idx + 1}: штифт на позицию {pos}")
                        self.update_display()
                        return

            elif self.mode == MODE_LINKS:
                # Проверяем клик по пластине
                if px <= x <= px + PLATE_WIDTH and py <= y <= py + PLATE_HEIGHT:
                    self.active_plate = plate_idx
                    self.status_label.config(
                        text=f"Режим: СВЯЗИ — пластина {plate_idx + 1} активна. Нажимайте стрелки",
                        fg="#ffb74d"
                    )
                    self.update_display()
                    return

                # Стрелка ВВЕРХ
                arrow_up_y = py - 35
                if (px + 10 <= x <= px + 35 and arrow_up_y <= y <= arrow_up_y + 25):
                    self.toggle_arrow(plate_idx, 1)
                    return
                # Стрелка ВНИЗ
                arrow_down_y = py + PLATE_HEIGHT + 10
                if (px + 10 <= x <= px + 35 and arrow_down_y <= y <= arrow_down_y + 25):
                    self.toggle_arrow(plate_idx, -1)
                    return

    def toggle_arrow(self, plate_idx, direction):
        """Переключить стрелку связи. direction: 1 (↑) или -1 (↓)."""
        active = self.active_plate
        current = self.connection_matrix[plate_idx][active]

        if direction == 1:
            if current == 1:
                self.connection_matrix[plate_idx][active] = 0
                self.log(f"Пластина {plate_idx + 1}: связь с {active + 1} отключена")
            else:
                self.connection_matrix[plate_idx][active] = 1
                if plate_idx == active:
                    self.log(f"Пластина {plate_idx + 1}: диагональ = +1 (↑)")
                else:
                    self.log(f"Пластина {plate_idx + 1}: связь с {active + 1} = +1 (↑)")
        else:
            if current == -1:
                self.connection_matrix[plate_idx][active] = 0
                self.log(f"Пластина {plate_idx + 1}: связь с {active + 1} отключена")
            else:
                self.connection_matrix[plate_idx][active] = -1
                if plate_idx == active:
                    self.log(f"Пластина {plate_idx + 1}: диагональ = -1 (↓)")
                else:
                    self.log(f"Пластина {plate_idx + 1}: связь с {active + 1} = -1 (↓)")

        self.update_display()

    def update_display(self):
        """Перерисовывает Canvas."""
        self.canvas.delete("all")

        for plate_idx in range(self.num_plates):
            px = MARGIN_X + plate_idx * PLATE_SPACING
            py = MARGIN_Y

            is_active = (plate_idx == self.active_plate)
            is_source = (self.mode == MODE_LINKS and is_active)

            # Подпись
            label_color = "#ff9800" if is_source else ("#4fc3f7" if is_active else "#888")
            label_text = f"П{plate_idx + 1}"
            if is_source:
                label_text += " ✓"

            self.canvas.create_text(
                px + PLATE_WIDTH // 2, py - 12,
                text=label_text, fill=label_color,
                font=("Segoe UI", 11, "bold")
            )

            # Рамка
            if is_active:
                self.canvas.create_rectangle(
                    px - 5, py - 5, px + PLATE_WIDTH + 5, py + PLATE_HEIGHT + 5,
                    outline=label_color, width=2
                )

            # 7 кружков
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

            # Стрелки связей
            if self.mode == MODE_LINKS:
                link_value = self.connection_matrix[plate_idx][self.active_plate]

                up_color = "#4CAF50" if link_value == 1 else "#444"
                up_fill = "#4CAF50" if link_value == 1 else "#1e1e1e"
                self._draw_arrow(px + 10, py - 35, "up", up_color, up_fill)

                down_color = "#ff3333" if link_value == -1 else "#444"
                down_fill = "#ff3333" if link_value == -1 else "#1e1e1e"
                self._draw_arrow(px + 10, py + PLATE_HEIGHT + 10, "down", down_color, down_fill)

    def _draw_arrow(self, x, y, direction, color, fill):
        """Рисует кнопку-стрелку."""
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
        """Запускает BFS."""
        self.log("=" * 40)
        self.log("Ищу решение...")

        # Проверка диагонали
        for i in range(self.num_plates):
            if self.connection_matrix[i][i] == 0:
                self.log(f"⚠️ Диагональ C[{i}][{i}] не может быть 0!")
                messagebox.showwarning("Проверка", f"Диагональ C[{i+1}][{i+1}] должна быть +1 или -1")
                return

        solution = self._bfs_solve()

        if solution is None:
            self.log("❌ Решение не найдено!")
            messagebox.showinfo("Результат", "Решение не найдено.\nПроверьте связи.")
        else:
            lines = [f"✅ Решение: {len(solution)} ходов"]
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
            win.title("Решение")
            win.configure(bg="#1e1e1e")
            win.geometry("400x400")
            win.resizable(False, False)

            tk.Label(win, text="Решение найдено!", bg="#1e1e1e", fg="#00ff88",
                    font=("Segoe UI", 14, "bold")).pack(pady=15)

            txt = tk.Text(win, wrap=tk.WORD, bg="#141414", fg="white",
                         font=("Consolas", 12), relief=tk.FLAT, padx=15, pady=10)
            txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            txt.insert("1.0", result)
            txt.config(state=tk.DISABLED)

            tk.Button(win, text="Закрыть", command=win.destroy,
                     bg="#444", fg="white", font=("Segoe UI", 11), bd=0).pack(pady=10)

    def _bfs_solve(self):
        """Поиск в ширину."""
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
                        # Пластину двигаем вправо → штифт смещается влево
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


# ── точка входа ────────────────────────────────────────────────

if __name__ == "__main__":
    app = LockpickApp()
    app.mainloop()

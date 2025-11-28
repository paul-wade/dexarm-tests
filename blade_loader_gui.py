"""
DexArm Blade Loader GUI - Simplified
Teach pick point, safe height, and hook drop points
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
from dexarm_controller import DexArmController


class BladeLoaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Blade Loader")
        self.root.geometry("700x600")
        
        self.controller = DexArmController()
        self.jog_distance = tk.DoubleVar(value=10.0)
        self.teach_mode_on = False
        
        self.create_widgets()
        self.refresh_display()
    
    def create_widgets(self):
        main = ttk.Frame(self.root, padding="10")
        main.pack(fill=tk.BOTH, expand=True)
        
        # === ROW 1: Connection + Position ===
        row1 = ttk.Frame(main)
        row1.pack(fill=tk.X, pady=(0, 10))
        
        # Connection
        conn_frame = ttk.LabelFrame(row1, text="Connection", padding="5")
        conn_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        port_row = ttk.Frame(conn_frame)
        port_row.pack()
        self.port_combo = ttk.Combobox(port_row, width=10, state="readonly")
        self.port_combo.pack(side=tk.LEFT)
        ttk.Button(port_row, text="↻", width=2, command=self.refresh_ports).pack(side=tk.LEFT, padx=2)
        
        self.connect_btn = ttk.Button(conn_frame, text="Connect", command=self.toggle_connection)
        self.connect_btn.pack(fill=tk.X, pady=2)
        self.status_label = ttk.Label(conn_frame, text="● Disconnected", foreground="red")
        self.status_label.pack()
        
        # Position + Controls
        ctrl_frame = ttk.LabelFrame(row1, text="Controls", padding="5")
        ctrl_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(ctrl_frame, text="🏠 HOME", width=12, command=self.go_home).pack(pady=2)
        self.teach_btn = ttk.Button(ctrl_frame, text="🖐️ FREE MOVE", width=12, command=self.toggle_teach_mode)
        self.teach_btn.pack(pady=2)
        
        # Position Display
        pos_frame = ttk.LabelFrame(row1, text="Position (encoder)", padding="5")
        pos_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        self.pos_label = ttk.Label(pos_frame, text="X: 0  Y: 0  Z: 0", font=("Consolas", 12))
        self.pos_label.pack()
        
        # Jog
        jog_frame = ttk.LabelFrame(row1, text="Jog", padding="5")
        jog_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        step_row = ttk.Frame(jog_frame)
        step_row.pack()
        for d in [1, 5, 10, 25]:
            ttk.Radiobutton(step_row, text=str(d), value=d, variable=self.jog_distance).pack(side=tk.LEFT)
        
        jog_grid = ttk.Frame(jog_frame)
        jog_grid.pack()
        ttk.Button(jog_grid, text="Y+", width=3, command=lambda: self.jog('y', 1)).grid(row=0, column=1)
        ttk.Button(jog_grid, text="X-", width=3, command=lambda: self.jog('x', -1)).grid(row=1, column=0)
        ttk.Button(jog_grid, text="X+", width=3, command=lambda: self.jog('x', 1)).grid(row=1, column=2)
        ttk.Button(jog_grid, text="Y-", width=3, command=lambda: self.jog('y', -1)).grid(row=2, column=1)
        ttk.Button(jog_grid, text="Z+", width=3, command=lambda: self.jog('z', 1)).grid(row=0, column=3, padx=(5,0))
        ttk.Button(jog_grid, text="Z-", width=3, command=lambda: self.jog('z', -1)).grid(row=2, column=3, padx=(5,0))
        
        # Suction
        suction_frame = ttk.LabelFrame(row1, text="Suction", padding="5")
        suction_frame.pack(side=tk.LEFT)
        ttk.Button(suction_frame, text="GRAB", width=7, command=self.suction_grab).pack(side=tk.LEFT, padx=1)
        ttk.Button(suction_frame, text="RELEASE", width=7, command=self.suction_release).pack(side=tk.LEFT, padx=1)
        ttk.Button(suction_frame, text="OFF", width=5, command=self.suction_off).pack(side=tk.LEFT, padx=1)
        
        # === ROW 2: PICK + SAFE Z ===
        row2 = ttk.Frame(main)
        row2.pack(fill=tk.X, pady=(0, 10))
        
        # Pick Location
        pick_frame = ttk.LabelFrame(row2, text="① PICK Location", padding="10")
        pick_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.pick_label = ttk.Label(pick_frame, text="Not set", font=("Consolas", 11))
        self.pick_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(pick_frame, text="Set Pick", command=self.set_pick).pack(side=tk.LEFT, padx=5)
        ttk.Button(pick_frame, text="Go To", command=self.go_to_pick).pack(side=tk.LEFT)
        
        # Safe Z
        safe_frame = ttk.LabelFrame(row2, text="② SAFE Height", padding="10")
        safe_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        self.safe_label = ttk.Label(safe_frame, text="Z: 0", font=("Consolas", 11))
        self.safe_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(safe_frame, text="Set Safe Z", command=self.set_safe_z).pack(side=tk.LEFT, padx=5)
        ttk.Button(safe_frame, text="Go To", command=self.go_to_safe).pack(side=tk.LEFT)
        
        # === ROW 3: HOOKS ===
        hooks_frame = ttk.LabelFrame(main, text="③ HOOK Drop Points", padding="10")
        hooks_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.hooks_listbox = tk.Listbox(hooks_frame, height=8, font=("Consolas", 10))
        self.hooks_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        hook_btns = ttk.Frame(hooks_frame)
        hook_btns.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))
        self.train_hook_btn = ttk.Button(hook_btns, text="🎯 Train Hook", width=12, command=self.train_hook_mode)
        self.train_hook_btn.pack(pady=3)
        ttk.Button(hook_btns, text="Add Hook", width=12, command=self.add_hook).pack(pady=3)
        ttk.Separator(hook_btns, orient='horizontal').pack(fill=tk.X, pady=5)
        ttk.Button(hook_btns, text="Go To", width=12, command=self.go_to_hook).pack(pady=3)
        ttk.Button(hook_btns, text="Test Hook", width=12, command=self.test_hook).pack(pady=3)
        ttk.Separator(hook_btns, orient='horizontal').pack(fill=tk.X, pady=5)
        ttk.Button(hook_btns, text="Delete", width=12, command=self.delete_hook).pack(pady=3)
        ttk.Button(hook_btns, text="Clear All", width=12, command=self.clear_hooks).pack(pady=3)
        
        # === ROW 4: RUN + LOG ===
        row4 = ttk.Frame(main)
        row4.pack(fill=tk.BOTH, expand=True)
        
        run_frame = ttk.LabelFrame(row4, text="Run Cycle", padding="10")
        run_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        self.progress_var = tk.DoubleVar()
        ttk.Progressbar(run_frame, variable=self.progress_var, maximum=100, length=120).pack(pady=5)
        
        btn_row = ttk.Frame(run_frame)
        btn_row.pack()
        self.run_btn = ttk.Button(btn_row, text="▶ START", command=self.start_cycle)
        self.run_btn.pack(side=tk.LEFT, padx=2)
        self.pause_btn = ttk.Button(btn_row, text="⏸", width=3, command=self.pause_cycle, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=2)
        self.stop_btn = ttk.Button(btn_row, text="⏹", width=3, command=self.stop_cycle, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=2)
        
        log_frame = ttk.LabelFrame(row4, text="Log", padding="5")
        log_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        self.refresh_ports()
        self.log("1. Connect  2. HOME  3. Set Pick  4. Set Safe Z  5. Add Hooks  6. START")
    
    def log(self, msg):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
    
    def refresh_display(self):
        """Update all displays"""
        pos = self.controller.current_pos
        self.pos_label.config(text=f"X: {pos['x']:.0f}  Y: {pos['y']:.0f}  Z: {pos['z']:.0f}")
        
        pick = self.controller.positions.get('pick')
        if pick:
            self.pick_label.config(text=f"X: {pick['x']:.0f}  Y: {pick['y']:.0f}  Z: {pick['z']:.0f}")
        else:
            self.pick_label.config(text="Not set")
        
        safe_z = self.controller.positions.get('safe_z', 0)
        self.safe_label.config(text=f"Z: {safe_z:.0f}")
        
        self.hooks_listbox.delete(0, tk.END)
        for i, hook in enumerate(self.controller.positions.get('hooks', [])):
            self.hooks_listbox.insert(tk.END, f"Hook {i}: X:{hook['x']:.0f} Y:{hook['y']:.0f} Z:{hook['z']:.0f}")
    
    # === CONNECTION ===
    def refresh_ports(self):
        ports = self.controller.list_ports()
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.set(ports[0])
    
    def toggle_connection(self):
        if self.controller.connected:
            self.controller.disconnect()
            self.connect_btn.config(text="Connect")
            self.status_label.config(text="● Disconnected", foreground="red")
            self.log("Disconnected")
        else:
            port = self.port_combo.get()
            if not port:
                messagebox.showerror("Error", "Select a port")
                return
            success, msg = self.controller.connect(port)
            if success:
                self.connect_btn.config(text="Disconnect")
                self.status_label.config(text="● Connected", foreground="green")
                self.controller.set_module(2)
                self.log("Connected! Now press HOME")
            else:
                messagebox.showerror("Error", msg)
    
    # === CONTROLS ===
    def go_home(self):
        if not self.controller.connected:
            return
        if self.teach_mode_on:
            self.toggle_teach_mode()
        self.log("Homing...")
        self.controller.go_home()
        self.controller.get_position_from_encoder()
        self.refresh_display()
        self.log("At HOME")
    
    def toggle_teach_mode(self):
        if not self.controller.connected:
            return
        if self.teach_mode_on:
            self.controller.get_position_from_encoder()
            self.controller.disable_teach_mode()
            self.teach_mode_on = False
            self.teach_btn.config(text="🖐️ FREE MOVE")
            self.refresh_display()
            self.log("Locked")
        else:
            self.controller.enable_teach_mode()
            self.teach_mode_on = True
            self.teach_btn.config(text="🔒 LOCK")
            self.log("FREE - drag arm, then click Set or Lock")
    
    def jog(self, axis, direction):
        if not self.controller.connected:
            return
        self.controller.jog(axis, self.jog_distance.get() * direction)
        self.controller.get_position_from_encoder()
        self.refresh_display()
    
    # === SUCTION ===
    def suction_grab(self):
        if self.controller.connected:
            self.controller.suction_grab()
    
    def suction_release(self):
        if self.controller.connected:
            self.controller.suction_release()
    
    def suction_off(self):
        if self.controller.connected:
            self.controller.suction_off()
    
    # === TEACHING ===
    def set_pick(self):
        if not self.controller.connected:
            return
        if self.teach_mode_on:
            self.toggle_teach_mode()
        self.controller.set_pick()
        self.refresh_display()
        self.log("Pick location set!")
    
    def set_safe_z(self):
        if not self.controller.connected:
            return
        if self.teach_mode_on:
            self.toggle_teach_mode()
        self.controller.set_safe_z()
        self.refresh_display()
        self.log("Safe Z set!")
    
    def go_to_pick(self):
        if not self.controller.connected:
            return
        self.controller.go_to_pick()
        self.controller.get_position_from_encoder()
        self.refresh_display()
    
    def go_to_safe(self):
        if not self.controller.connected:
            return
        self.controller.go_to_safe_z()
        self.controller.get_position_from_encoder()
        self.refresh_display()
    
    # === HOOKS ===
    def train_hook_mode(self):
        """Enable hook training: suction ON + free move"""
        if not self.controller.connected:
            return
        
        if self.teach_mode_on:
            # Already in teach mode, turn off suction and exit
            self.controller.suction_off()
            self.toggle_teach_mode()
            self.train_hook_btn.config(text="🎯 Train Hook")
            self.log("Hook training OFF")
        else:
            # Enter hook training: suction ON then free move
            self.controller.suction_grab()
            self.log("Suction ON - grab a blade")
            self.toggle_teach_mode()
            self.train_hook_btn.config(text="🔒 Lock & OFF")
            self.log("Position blade on hook, then click Add Hook")
    
    def add_hook(self):
        if not self.controller.connected:
            return
        if self.teach_mode_on:
            self.toggle_teach_mode()
            self.train_hook_btn.config(text="🎯 Train Hook")
        # Turn off suction after adding hook
        self.controller.suction_off()
        idx = self.controller.add_hook()
        self.refresh_display()
        self.log(f"Hook {idx} added! Suction OFF")
    
    def go_to_hook(self):
        if not self.controller.connected:
            return
        sel = self.hooks_listbox.curselection()
        if sel:
            self.controller.go_to_hook(sel[0])
            self.controller.get_position_from_encoder()
            self.refresh_display()
    
    def test_hook(self):
        if not self.controller.connected:
            return
        sel = self.hooks_listbox.curselection()
        if not sel:
            messagebox.showwarning("Warning", "Select a hook first")
            return
        self.log(f"Testing hook {sel[0]}...")
        def run():
            self.controller.test_single_hook(sel[0], lambda m: self.root.after(0, lambda: self.log(m)))
            self.root.after(0, lambda: self.controller.get_position_from_encoder())
            self.root.after(0, self.refresh_display)
        threading.Thread(target=run, daemon=True).start()
    
    def delete_hook(self):
        sel = self.hooks_listbox.curselection()
        if sel:
            self.controller.delete_hook(sel[0])
            self.refresh_display()
            self.log(f"Hook {sel[0]} deleted")
    
    def clear_hooks(self):
        if messagebox.askyesno("Confirm", "Delete all hooks?"):
            self.controller.clear_all_hooks()
            self.refresh_display()
            self.log("All hooks cleared")
    
    # === CYCLE ===
    def start_cycle(self):
        if not self.controller.connected:
            return
        if not self.controller.positions.get('pick'):
            messagebox.showwarning("Warning", "Set pick location first")
            return
        if not self.controller.positions.get('hooks'):
            messagebox.showwarning("Warning", "Add hooks first")
            return
        
        self.run_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress_var.set(0)
        self.log("Starting...")
        
        def run():
            self.controller.run_full_cycle(
                lambda c, t: self.root.after(0, lambda: self.progress_var.set(c/t*100)),
                lambda m: self.root.after(0, lambda: self.log(m))
            )
            self.root.after(0, self.cycle_done)
        threading.Thread(target=run, daemon=True).start()
    
    def cycle_done(self):
        self.run_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.DISABLED)
        self.refresh_display()
    
    def pause_cycle(self):
        if self.controller.pause_requested:
            self.controller.resume_cycle()
            self.pause_btn.config(text="⏸")
        else:
            self.controller.pause_cycle()
            self.pause_btn.config(text="▶")
    
    def stop_cycle(self):
        self.controller.stop_cycle()


def main():
    root = tk.Tk()
    BladeLoaderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

"""
DexArm Controller - Core control class for DexArm robot arm
Handles serial communication and G-code commands
"""

import serial
import serial.tools.list_ports
import time
import json
import os
import threading

CONFIG_FILE = "blade_positions.json"
BAUD_RATE = 115200


class DexArmController:
    def __init__(self):
        self.serial = None
        self.connected = False
        self.positions = self.load_positions()
        self.current_pos = {'x': 0, 'y': 300, 'z': 0}
        self.is_running = False
        self.pause_requested = False
        self.stop_requested = False
        
        # Timing settings (adjustable)
        self.settings = {
            'suction_grab_delay': 0.5,
            'suction_release_delay': 0.3,
            'feedrate': 3000,  # 1.5x standard feedrate
        }
    
    @staticmethod
    def list_ports():
        """List available serial ports"""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]
    
    def connect(self, port):
        """Connect to DexArm"""
        try:
            self.serial = serial.Serial(port, BAUD_RATE, timeout=2)
            time.sleep(2)  # Wait for connection to establish
            self.connected = True
            return True, "Connected successfully"
        except Exception as e:
            self.connected = False
            return False, str(e)
    
    def disconnect(self):
        """Disconnect from DexArm"""
        if self.serial:
            self.serial.close()
        self.connected = False
    
    def send_command(self, cmd, wait_ok=True):
        """Send G-code command and wait for 'ok' (like official pydexarm)"""
        if not self.serial or not self.connected:
            return None
        
        try:
            self.serial.write(f"{cmd}\r".encode())
            if not wait_ok:
                self.serial.reset_input_buffer()
                return "sent"
            
            # Wait for 'ok' response (loop like official pydexarm)
            while True:
                response = self.serial.readline().decode().strip()
                if 'ok' in response.lower():
                    return response
                # Timeout protection
                if not response:
                    time.sleep(0.05)
        except Exception as e:
            return f"Error: {e}"
    
    def go_home(self):
        """Move to home position"""
        self.send_command("M1112")
        time.sleep(2)
        self.current_pos = {'x': 0, 'y': 300, 'z': 0}
    
    def set_module(self, module_type):
        """
        Set front-end module
        0 = Pen holder
        1 = Laser
        2 = Pneumatic (suction/gripper)
        3 = 3D printing
        """
        self.send_command(f"M888 P{module_type}")
        time.sleep(0.3)
    
    def move_to(self, x, y, z, feedrate=None):
        """Move to absolute position"""
        if feedrate is None:
            feedrate = self.settings['feedrate']
        # Use G1 for controlled movement (per pydexarm)
        cmd = f"G1 F{feedrate} X{x:.2f} Y{y:.2f} Z{z:.2f}"
        self.send_command(cmd)
        self.current_pos = {'x': x, 'y': y, 'z': z}
    
    def jog(self, axis, distance):
        """Jog relative movement on single axis"""
        # Switch to relative mode
        self.send_command("G91")
        
        # Move
        if axis == 'x':
            self.send_command(f"G1 F1000 X{distance}")
            self.current_pos['x'] += distance
        elif axis == 'y':
            self.send_command(f"G1 F1000 Y{distance}")
            self.current_pos['y'] += distance
        elif axis == 'z':
            self.send_command(f"G1 F1000 Z{distance}")
            self.current_pos['z'] += distance
        
        # Back to absolute mode
        self.send_command("G90")
    
    def get_position(self):
        """Query current position from arm"""
        self.send_command("M114")
        try:
            response = self.serial.readline().decode().strip()
            # Parse "X:0.00 Y:300.00 Z:0.00 E:0.00"
            parts = response.split()
            x = float(parts[0].split(':')[1])
            y = float(parts[1].split(':')[1])
            z = float(parts[2].split(':')[1])
            self.current_pos = {'x': x, 'y': y, 'z': z}
            return self.current_pos
        except:
            return self.current_pos
    
    # === TEACH MODE (FREE DRAG) ===
    
    def enable_teach_mode(self):
        """Disable motors so arm can be moved freely by hand"""
        self.send_command("M84")
        return True
    
    def disable_teach_mode(self):
        """Re-enable motors (lock arm in place)"""
        self.send_command("M17")
        return True
    
    def read_encoder_position(self):
        """Read magnet encoder position using M893"""
        # Drain all pending data first
        while self.serial.in_waiting:
            self.serial.readline()
        time.sleep(0.1)
        
        # Send M893 to read encoder
        self.serial.write(b"M893\n")
        time.sleep(0.5)  # Give it time
        
        # Read lines until we get M894 response
        for _ in range(20):
            try:
                if self.serial.in_waiting:
                    response = self.serial.readline().decode().strip()
                    # print(f"DEBUG M893 got: {repr(response)}")
                    if 'M894' in response or ('X' in response and 'Y' in response and 'Z' in response):
                        return response
                else:
                    time.sleep(0.1)
            except:
                pass
        return None
    
    def get_position_from_encoder(self):
        """Get actual position and update current_pos"""
        enc = self.read_encoder_position()
        # print(f"DEBUG pos raw: {repr(enc)}")
        if enc:
            # Parse "M894 X123 Y456 Z789" or "X123 Y456 Z789" format
            try:
                # Remove M894 prefix if present
                enc = enc.replace("M894", "").strip()
                parts = enc.split()
                for part in parts:
                    if part.startswith('X'):
                        self.current_pos['x'] = float(part[1:])
                    elif part.startswith('Y'):
                        self.current_pos['y'] = float(part[1:])
                    elif part.startswith('Z'):
                        self.current_pos['z'] = float(part[1:])
                # print(f"DEBUG parsed pos: {self.current_pos}")
            except Exception as e:
                print(f"Position parse error: {e}")
        return self.current_pos
    
    def move_to_encoder_position(self, encoder_string):
        """Move to a position using encoder values (from M893 response)"""
        if encoder_string and ('X' in encoder_string or encoder_string.startswith('M894')):
            # Clean up the string - remove newlines and extra spaces
            encoder_string = ' '.join(encoder_string.split())
            if not encoder_string.startswith('M894'):
                encoder_string = 'M894 ' + encoder_string
            self.send_command(encoder_string)
            self.send_command("M400")  # Wait for move
            time.sleep(0.2)
            # Sync position after encoder move
            self.get_position()
            return True
        return False
    
    # === SUCTION CONTROL ===
    
    def suction_grab(self):
        """Activate suction (pump in)"""
        self.send_command("M1000")
        time.sleep(self.settings['suction_grab_delay'])
    
    def suction_release(self):
        """Release suction - M1002 releases air pressure, then M1003 stops pump"""
        self.send_command("M1002")  # Release air
        time.sleep(self.settings['suction_release_delay'])
        self.send_command("M1003")  # Stop pump
    
    def suction_off(self):
        """Turn off suction pump"""
        self.send_command("M1003")
    
    # === POSITION MANAGEMENT ===
    
    def load_positions(self):
        """Load saved positions from file"""
        default = {
            'pick': None,       # Single grab point {x, y, z, encoder}
            'safe_z': 0,        # Safe height for moves
            'hooks': []         # List of drop points [{x, y, z, encoder}, ...]
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return default
    
    def save_positions(self):
        """Save positions to file"""
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.positions, f, indent=2)
    
    def set_pick(self):
        """Set current position as pick point"""
        # Get Cartesian position from M114
        self.get_position()
        # Get encoder string for precise replay
        encoder = self.read_encoder_position()
        self.positions['pick'] = {
            'x': self.current_pos['x'],
            'y': self.current_pos['y'],
            'z': self.current_pos['z'],
            'encoder': encoder
        }
        self.save_positions()
    
    def set_safe_z(self):
        """Set current Z as safe height (Cartesian)"""
        self.get_position()  # Get Cartesian from M114
        self.positions['safe_z'] = self.current_pos['z']
        self.save_positions()
    
    def add_hook(self):
        """Add current position as a hook drop point"""
        # Get Cartesian position from M114
        self.get_position()
        # Get encoder string for precise replay
        encoder = self.read_encoder_position()
        self.positions['hooks'].append({
            'x': self.current_pos['x'],
            'y': self.current_pos['y'],
            'z': self.current_pos['z'],
            'encoder': encoder
        })
        self.save_positions()
        return len(self.positions['hooks']) - 1
    
    def delete_hook(self, index):
        """Delete a hook"""
        if 0 <= index < len(self.positions['hooks']):
            del self.positions['hooks'][index]
            self.save_positions()
    
    def clear_all_hooks(self):
        """Clear all hooks"""
        self.positions['hooks'] = []
        self.save_positions()
    
    def go_to_pick(self):
        """Move to pick position"""
        if self.positions.get('pick'):
            p = self.positions['pick']
            if p.get('encoder'):
                self.move_to_encoder_position(p['encoder'])
            else:
                self.move_to(p['x'], p['y'], p['z'])
    
    def go_to_hook(self, index):
        """Move to hook position"""
        if index < len(self.positions['hooks']):
            p = self.positions['hooks'][index]
            if p.get('encoder'):
                self.move_to_encoder_position(p['encoder'])
            else:
                self.move_to(p['x'], p['y'], p['z'])
    
    def go_to_safe_z(self):
        """Lift to safe Z height"""
        safe_z = self.positions.get('safe_z', 0)
        self.move_to(self.current_pos['x'], self.current_pos['y'], safe_z)
    
    # === CYCLE OPERATIONS ===
    
    def _lift_to_safe(self, from_pos=None, callback=None):
        """Lift straight up to safe Z (absolute Cartesian)"""
        if callback:
            callback("  ↑ Lifting")
        
        safe_z = self.positions.get('safe_z', 0)
        
        # Use absolute Z move (current_pos should be synced after M894)
        cmd = f"G1 F{self.settings['feedrate']} Z{safe_z:.2f}"
        self.send_command(cmd)
        self.wait_for_move()
        
        # Update tracked position
        self.current_pos['z'] = safe_z
    
    def wait_for_move(self):
        """Wait for arm to finish moving"""
        # M400 waits for all moves to complete, send_command waits for 'ok'
        self.send_command("M400")
    
    def pick_blade(self, callback=None):
        """Pick a blade using pure Cartesian (like official pydexarm)"""
        pick = self.positions.get('pick')
        if not pick:
            return False
        
        safe_z = self.positions.get('safe_z', 0)
        f = self.settings['feedrate']
        
        if callback:
            callback("PICK")
        
        # 1. Move to above pick (X, Y, safe_z)
        if callback:
            callback("  → Moving above pick")
        self.send_command(f"G1 F{f} X{pick['x']:.2f} Y{pick['y']:.2f} Z{safe_z:.2f}")
        self.wait_for_move()
        
        # 2. Start suction BEFORE lowering
        if callback:
            callback("  ✓ Suction ON")
        self.send_command("M1000")
        time.sleep(0.3)
        
        # 3. Lower to pick (same X,Y, just Z)
        if callback:
            callback("  ↓ Lowering")
        self.send_command(f"G1 F{f} Z{pick['z']:.2f}")
        self.wait_for_move()
        
        # 4. Wait for suction to grip
        time.sleep(self.settings['suction_grab_delay'])
        
        # 5. Lift back up (same X,Y, safe_z)
        if callback:
            callback("  ↑ Lifting")
        self.send_command(f"G1 F{f} Z{safe_z:.2f}")
        self.wait_for_move()
        
        return True
    
    def place_blade(self, hook_index, callback=None):
        """Place blade using pure Cartesian (like official pydexarm)"""
        if hook_index >= len(self.positions['hooks']):
            return False
        
        hook = self.positions['hooks'][hook_index]
        safe_z = self.positions.get('safe_z', 0)
        f = self.settings['feedrate']
        
        if callback:
            callback(f"PLACE (Hook {hook_index})")
        
        # 1. Move to above hook (X, Y, safe_z)
        if callback:
            callback("  → Moving above hook")
        self.send_command(f"G1 F{f} X{hook['x']:.2f} Y{hook['y']:.2f} Z{safe_z:.2f}")
        self.wait_for_move()
        
        # 2. Lower to hook (same X,Y, just Z)
        if callback:
            callback("  ↓ Lowering")
        self.send_command(f"G1 F{f} Z{hook['z']:.2f}")
        self.wait_for_move()
        
        # 3. Release suction BEFORE lifting
        if callback:
            callback("  ✓ Release air")
        self.send_command("M1002")  # Release air pressure
        time.sleep(0.5)  # Wait for air to release
        
        if callback:
            callback("  ✓ Pump OFF")
        self.send_command("M1003")  # Stop pump
        time.sleep(0.2)
        
        # 4. Lift back up (same X,Y, safe_z)
        if callback:
            callback("  ↑ Lifting")
        self.send_command(f"G1 F{f} Z{safe_z:.2f}")
        self.wait_for_move()
        
        return True
    
    def run_full_cycle(self, progress_callback=None, status_callback=None):
        """Run pick-and-place for all hooks"""
        self.is_running = True
        self.stop_requested = False
        self.pause_requested = False
        
        # Use straight line mode for smooth movements
        self.send_command("M2000")
        
        num_hooks = len(self.positions['hooks'])
        
        for i in range(num_hooks):
            if self.stop_requested:
                if status_callback:
                    status_callback("STOPPED")
                break
            
            while self.pause_requested:
                time.sleep(0.1)
                if self.stop_requested:
                    break
            
            if status_callback:
                status_callback(f"\n── Blade {i+1}/{num_hooks} ──")
            
            if not self.pick_blade(status_callback):
                break
            
            if not self.place_blade(i, status_callback):
                break
            
            if progress_callback:
                progress_callback(i + 1, num_hooks)
        
        self.suction_off()
        self.go_home()
        self.is_running = False
        
        if status_callback:
            status_callback("\n✓ DONE")
    
    def test_single_hook(self, hook_index, status_callback=None):
        """Test one hook"""
        self.is_running = True
        self.stop_requested = False
        
        if status_callback:
            status_callback(f"Testing hook {hook_index}")
        
        self.pick_blade(status_callback)
        self.place_blade(hook_index, status_callback)
        
        self.suction_off()
        self.is_running = False
        
        if status_callback:
            status_callback("Done")
    
    def pause_cycle(self):
        """Pause the running cycle"""
        self.pause_requested = True
    
    def resume_cycle(self):
        """Resume paused cycle"""
        self.pause_requested = False
    
    def stop_cycle(self):
        """Stop the running cycle"""
        self.stop_requested = True
        self.pause_requested = False

"""
Jio Datsugoku - STB Jailbreak & Enhancement Suite
Professional, clean, native Windows application for Jio STB JHSC200 / JHSD200.
"""

import os
import sys
import time
import socket
import threading
import queue
import subprocess
import glob
import concurrent.futures
from datetime import datetime

# Prevent crash on Windows when running --windowed (sys.stdout is None)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import customtkinter as ctk
import tkinter as tk
import math
from PIL import Image

# -------------------------------------------------------------
# Application Tokens & Configuration
# -------------------------------------------------------------
APP_TITLE = "Jio Datsugoku"
APP_SUBTITLE = "JHSC200 / JHSD200"
DEFAULT_ADB_PORT = 5555

def get_base_dir():
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()

def get_asset_path(name):
    candidates = [
        os.path.join(BASE_DIR, "assets", name),
        os.path.join(os.getcwd(), "assets", name),
        os.path.join(BASE_DIR, name),
        os.path.join(os.getcwd(), name)
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def load_ctk_image(name, size):
    path = get_asset_path(name)
    if path and os.path.exists(path):
        try:
            im = Image.open(path)
            return ctk.CTkImage(light_image=im, dark_image=im, size=size)
        except Exception:
            pass
    return None

def find_adb():
    candidates = [
        os.path.join(BASE_DIR, "adb.exe"),
        os.path.join(os.getcwd(), "adb.exe"),
        "adb.exe",
        "adb"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "adb"

def detect_initial_ip():
    try:
        adb_bin = find_adb()
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
        proc = subprocess.run([adb_bin, "devices"], capture_output=True, text=True, timeout=2, startupinfo=startupinfo)
        for line in proc.stdout.splitlines():
            if ":5555" in line and "\tdevice" in line:
                return line.split("\t")[0].split(":")[0]
    except Exception:
        pass

    try:
        host_ips = socket.gethostbyname_ex(socket.gethostname())[2]
        for hip in host_ips:
            if hip.startswith("192.168.29."):
                return "192.168.29.124"
            if hip.startswith("192.168.") and not hip.startswith("192.168.56."):
                parts = hip.split(".")
                return f"{parts[0]}.{parts[1]}.{parts[2]}.124"
    except Exception:
        pass

    return "192.168.29.124"

# Human-friendly package mappings
KNOWN_NAMES = {
    'app.netmirror.newtv': 'NetMirror (Free Movies)',
    'io.gh.reisxd.tizentube.cobalt': 'TizenTube Cobalt (Ad-free YouTube)',
    'com.jio.yt': 'Stock Jio YouTube',
    'com.netflix.ninja': 'Stock Netflix',
    'in.startv.hotstar': 'JioHotstar / Disney+',
    'com.viacom18.tv.voot': 'Voot / JioCinema',
    'org.videolan.vlc': 'VLC Media Player',
    'ch.protonvpn.android': 'Proton VPN',
    'com.tcl.browser': 'BrowseHere Browser',
    'dev.dworks.apps.anexplorer': 'AnExplorer Files',
    'com.auramusic.app': 'AuraMusic Player',
    'com.orion.store': 'Orion Store',
    'com.aurora.store': 'Aurora Store',
    'app.pwhs.universalinstaller': 'Universal Installer',
    'com.klevico.monet': 'Monet Launcher',
    'com.amazon.amazonvideo.livingroom': 'Prime Video',
    'com.zee5.aosp': 'ZEE5',
    'com.jiotv.sonyliv': 'SonyLIV',
    'com.tailscale.ipn': 'Tailscale VPN',
    'com.hamondev.shevery': 'Shizuku Everywhere',
    'com.google.android.youtube.tv': 'YouTube Android TV',
    'com.liskovsoft.videomanager': 'SmartTube Next'
}

# -------------------------------------------------------------
# ADB Helper Class (Thread-Safe)
# -------------------------------------------------------------
class ADBManager:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.current_ip = detect_initial_ip()
        self.is_connected = False
        self.lock = threading.Lock()

    def log(self, msg, level="INFO"):
        if self.log_callback:
            self.log_callback(msg, level)

    def run_cmd(self, cmd_args, target_ip=None, timeout=15):
        ip = target_ip or self.current_ip
        adb_exec = find_adb()
        full_cmd = [adb_exec]
        if ip and "connect" not in cmd_args and "devices" not in cmd_args:
            full_cmd.extend(["-s", f"{ip}:{DEFAULT_ADB_PORT}"])
        full_cmd.extend(cmd_args)

        cmd_display = " ".join(cmd_args)
        self.log(f"$ adb {cmd_display}", "CMD")

        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0

            proc = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                startupinfo=startupinfo,
                errors="replace"
            )
            out = proc.stdout.strip()
            err = proc.stderr.strip()
            
            if out:
                for line in out.splitlines():
                    self.log(line, "OUT")
            if err and proc.returncode != 0:
                for line in err.splitlines():
                    self.log(line, "ERR")

            return proc.returncode == 0, out, err
        except subprocess.TimeoutExpired:
            self.log(f"Command timed out: {cmd_display}", "ERR")
            return False, "", "Timed out"
        except Exception as e:
            self.log(f"Execution failed: {e}", "ERR")
            return False, "", str(e)

    def connect(self, ip=None):
        target = ip or self.current_ip
        self.log(f"Connecting to {target}:{DEFAULT_ADB_PORT}...", "INFO")
        
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.2)
        is_port_open = False
        try:
            is_port_open = (s.connect_ex((target, DEFAULT_ADB_PORT)) == 0)
        except Exception:
            pass
        finally:
            s.close()

        if not is_port_open:
            self.log(f"Port {DEFAULT_ADB_PORT} unreachable on {target}", "WARN")

        self.run_cmd(["connect", f"{target}:{DEFAULT_ADB_PORT}"], target_ip=target, timeout=5)
        time.sleep(0.4)
        
        ok_state, state_out, _ = self.run_cmd(["get-state"], target_ip=target, timeout=3)
        if "device" in state_out:
            self.current_ip = target
            self.is_connected = True
            self.log(f"Connected to STB at {target}", "SUCCESS")
            return True
        else:
            self.is_connected = False
            self.log(f"Connection status: {state_out}", "ERR")
            return False

    def disconnect(self):
        self.run_cmd(["disconnect", f"{self.current_ip}:{DEFAULT_ADB_PORT}"])
        self.is_connected = False
        self.log("Disconnected from STB", "INFO")

    def check_state(self):
        ok, out, _ = self.run_cmd(["get-state"], timeout=2)
        self.is_connected = ("device" in out)
        return self.is_connected

    def get_device_info(self):
        if not self.is_connected:
            return {}
        info = {}
        _, model, _ = self.run_cmd(["shell", "getprop ro.product.model"])
        _, brand, _ = self.run_cmd(["shell", "getprop ro.product.brand"])
        _, android_ver, _ = self.run_cmd(["shell", "getprop ro.build.version.release"])
        _, uptime, _ = self.run_cmd(["shell", "cat /proc/uptime"])
        
        info["model"] = f"{brand} {model}".strip() if model else "Jio STB"
        info["android"] = android_ver if android_ver else "11"
        try:
            up_secs = float(uptime.split()[0])
            mins = int((up_secs % 3600) // 60)
            hours = int(up_secs // 3600)
            info["uptime"] = f"{hours}h {mins}m"
        except Exception:
            info["uptime"] = "--"
        return info

# -------------------------------------------------------------
# Material Design 3 Expressive Component System
# (Swirl Loading, Shape Morphing, Radar Scope, Curved Gauges)
# -------------------------------------------------------------
class M3SwirlLoader(tk.Canvas):
    """
    Material Design 3 Indeterminate Circular Progress Indicator (Swirl Loader).
    Features a dynamic rotating arc where start angle and extent expand and contract
    with cubic easing according to M3 motion specifications.
    """
    def __init__(self, parent, size=28, thickness=3, color="#A8C7FA", track_color="#262A33", bg_color=None, **kwargs):
        bg = bg_color or (parent.cget("fg_color") if hasattr(parent, "cget") else "#171A20")
        if bg == "transparent":
            bg = "#171A20"
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0, **kwargs)
        self.size = size
        self.thickness = thickness
        self.color = color
        self.track_color = track_color
        self.running = False
        self.step = 0
        self._after_id = None
        self.pad = thickness + 2

    def start(self):
        if not self.running:
            self.running = True
            self._animate()

    def stop(self):
        self.running = False
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self.delete("all")

    def set_color(self, color):
        self.color = color

    def _animate(self):
        if not self.running:
            return
        self.delete("all")
        t = self.step * 0.065
        rot = (self.step * 7.5) % 360
        extent = 28 + 242 * (0.5 + 0.5 * math.sin(t))
        start_angle = (rot + 180 * math.sin(t * 0.5)) % 360

        x0, y0 = self.pad, self.pad
        x1, y1 = self.size - self.pad, self.size - self.pad

        if self.track_color:
            self.create_arc(x0, y0, x1, y1, start=0, extent=359.9, style="arc", outline=self.track_color, width=self.thickness)
        self.create_arc(x0, y0, x1, y1, start=start_angle, extent=extent, style="arc", outline=self.color, width=self.thickness)

        self.step += 1
        self._after_id = self.after(25, self._animate)


class M3MorphLoader(tk.Canvas):
    """
    Material 3 Expressive Shape Morphing Progress Indicator.
    Smoothly morphs between iconic M3 Expressive shapes:
      1. Squircle (superellipse)
      2. 4-Lobed Clover / Flower
      3. 8-Pointed Scalloped Blossom
      4. Curved Diamond / Starburst
    with continuous rotation, elastic pulse, and M3 container styling.
    """
    def __init__(self, parent, size=52, color="#A8C7FA", fill_color="#004A77", track_color="#1D2027", bg_color=None, **kwargs):
        bg = bg_color or (parent.cget("fg_color") if hasattr(parent, "cget") else "#1D2027")
        if bg == "transparent":
            bg = "#1D2027"
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0, **kwargs)
        self.size = size
        self.color = color
        self.fill_color = fill_color
        self.track_color = track_color
        self.cx = size / 2
        self.cy = size / 2
        self.r_base = (size / 2) - 6
        self.running = False
        self.step = 0
        self._after_id = None
        self.keyframes = [
            (0.12, -0.03, 1.00),  # M3 Squircle
            (0.32, 0.00, 0.94),   # M3 4-Leaf Clover
            (0.00, 0.22, 1.06),   # M3 8-Petal Scallop
            (-0.28, 0.05, 0.92),  # M3 Curved Starburst
        ]
        self._draw_static()

    def start(self):
        if not self.running:
            self.running = True
            self._animate()

    def stop(self):
        self.running = False
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._draw_static()

    def set_colors(self, outline_color, fill_color):
        self.color = outline_color
        self.fill_color = fill_color
        if not self.running:
            self._draw_static()

    def _draw_static(self):
        self.delete("all")
        pts = self._compute_points(0.15, 0.0, 1.0, 0.0)
        self.create_polygon(pts, fill=self.fill_color, outline=self.color, width=2.0, smooth=True)
        self.create_oval(self.cx - 4, self.cy - 4, self.cx + 4, self.cy + 4, fill=self.color, outline="")

    def _compute_points(self, a4, a8, scale, rot_angle, num_points=48):
        pts = []
        for i in range(num_points):
            theta = 2.0 * math.pi * i / num_points
            r = self.r_base * scale * (1.0 + a4 * math.cos(4.0 * (theta - rot_angle)) + a8 * math.cos(8.0 * (theta - rot_angle)))
            pts.extend([self.cx + r * math.cos(theta), self.cy + r * math.sin(theta)])
        return pts

    def _animate(self):
        if not self.running:
            return
        self.delete("all")

        progress = (self.step * 0.025) % len(self.keyframes)
        idx = int(progress)
        next_idx = (idx + 1) % len(self.keyframes)
        frac = progress - idx
        ease = (1.0 - math.cos(frac * math.pi)) / 2.0

        k1 = self.keyframes[idx]
        k2 = self.keyframes[next_idx]
        a4 = k1[0] + (k2[0] - k1[0]) * ease
        a8 = k1[1] + (k2[1] - k1[1]) * ease
        sc = k1[2] + (k2[2] - k1[2]) * ease
        rot_angle = self.step * 0.04

        pts_shadow = self._compute_points(a4, a8, sc * 1.15, rot_angle * 0.5)
        self.create_polygon(pts_shadow, fill=self.track_color, outline="", smooth=True)

        pts_main = self._compute_points(a4, a8, sc, rot_angle)
        self.create_polygon(pts_main, fill=self.fill_color, outline=self.color, width=2.2, smooth=True)

        core_r = 4.0 + 2.0 * (0.5 + 0.5 * math.sin(self.step * 0.12))
        self.create_oval(self.cx - core_r, self.cy - core_r, self.cx + core_r, self.cy + core_r, fill=self.color, outline="")

        self.step += 1
        self._after_id = self.after(22, self._animate)


class M3HunterScope(tk.Canvas):
    """
    Material 3 Expressive Radar Scope & Morphing Scanner.
    Combines expanding radar ripples with an active M3 shape morphing core.
    """
    def __init__(self, parent, size=140, color="#7BD0C1", fill_color="#004F46", bg_color=None, **kwargs):
        bg = bg_color or "#171A20"
        if bg == "transparent":
            bg = "#171A20"
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0, **kwargs)
        self.size = size
        self.color = color
        self.fill_color = fill_color
        self.cx = size / 2
        self.cy = size / 2
        self.running = False
        self.state = "idle"
        self.step = 0
        self._after_id = None
        self.r_base = 28
        self.keyframes = [
            (0.12, -0.03, 1.00),  # M3 Squircle
            (0.32, 0.00, 0.94),   # M3 4-Leaf Clover
            (0.00, 0.22, 1.06),   # M3 8-Petal Scallop
            (-0.28, 0.05, 0.92),  # M3 Curved Starburst
        ]
        self._draw_idle()

    def start_hunt(self):
        self.state = "hunting"
        self.running = True
        self._animate()

    def stop_hunt(self):
        self.state = "idle"
        self.running = False
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._draw_idle()

    def set_caught(self):
        self.state = "caught"
        self.running = False
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._draw_caught()

    def _draw_idle(self):
        self.delete("all")
        for r in [22, 42, 60]:
            self.create_oval(self.cx - r, self.cy - r, self.cx + r, self.cy + r, outline="#262A33", width=1.5)
        pts = self._compute_points(0.15, 0.0, 0.75, 0.0)
        self.create_polygon(pts, fill="#262A33", outline="#454954", width=1.5, smooth=True)
        self.create_oval(self.cx - 3, self.cy - 3, self.cx + 3, self.cy + 3, fill="#8E919A", outline="")

    def _draw_caught(self):
        self.delete("all")
        for r in [38, 58]:
            self.create_oval(self.cx - r, self.cy - r, self.cx + r, self.cy + r, outline="#143523", width=2)
        pts = self._compute_points(0.20, 0.0, 1.05, 0.0)
        self.create_polygon(pts, fill="#143523", outline="#81C995", width=2.5, smooth=True)
        self.create_line(self.cx - 10, self.cy, self.cx - 2, self.cy + 8, fill="#A3F0BA", width=3, capstyle="round")
        self.create_line(self.cx - 2, self.cy + 8, self.cx + 11, self.cy - 7, fill="#A3F0BA", width=3, capstyle="round")

    def _compute_points(self, a4, a8, scale, rot_angle, num_points=48):
        pts = []
        for i in range(num_points):
            theta = 2.0 * math.pi * i / num_points
            r = self.r_base * scale * (1.0 + a4 * math.cos(4.0 * (theta - rot_angle)) + a8 * math.cos(8.0 * (theta - rot_angle)))
            pts.extend([self.cx + r * math.cos(theta), self.cy + r * math.sin(theta)])
        return pts

    def _animate(self):
        if not self.running:
            return
        self.delete("all")

        # 1. Concentric radar wave ripples
        for i in range(3):
            phase = (self.step * 0.03 + i * 0.33) % 1.0
            r_wave = 16 + phase * (self.cx - 18)
            wave_color = "#004F46" if phase > 0.6 else "#7BD0C1"
            self.create_oval(self.cx - r_wave, self.cy - r_wave, self.cx + r_wave, self.cy + r_wave, outline=wave_color, width=1.5)

        # 2. Shape Morph Dynamics
        progress = (self.step * 0.025) % len(self.keyframes)
        idx = int(progress)
        next_idx = (idx + 1) % len(self.keyframes)
        frac = progress - idx
        ease = (1.0 - math.cos(frac * math.pi)) / 2.0

        k1 = self.keyframes[idx]
        k2 = self.keyframes[next_idx]
        a4 = k1[0] + (k2[0] - k1[0]) * ease
        a8 = k1[1] + (k2[1] - k1[1]) * ease
        sc = k1[2] + (k2[2] - k1[2]) * ease
        rot_angle = self.step * 0.04

        pts_aura = self._compute_points(a4, a8, sc * 1.18, rot_angle * 0.5)
        self.create_polygon(pts_aura, fill="#004F46", outline="", smooth=True)

        pts_main = self._compute_points(a4, a8, sc, rot_angle)
        self.create_polygon(pts_main, fill=self.fill_color, outline=self.color, width=2.2, smooth=True)

        core_r = 4.0 + 2.0 * (0.5 + 0.5 * math.sin(self.step * 0.12))
        self.create_oval(self.cx - core_r, self.cy - core_r, self.cx + core_r, self.cy + core_r, fill=self.color, outline="")

        self.step += 1
        self._after_id = self.after(22, self._animate)


class M3RamGauge(tk.Canvas):
    """
    Material 3 Expressive Curved Arc Meter for RAM / Telemetry.
    Draws a 360-degree background ring with a dynamic filled arc and an
    inner M3 squircle badge displaying percentage.
    """
    def __init__(self, parent, size=116, thickness=8, color="#A8C7FA", track_color="#262A33", bg_color=None, **kwargs):
        bg = bg_color or "#1D2027"
        if bg == "transparent":
            bg = "#1D2027"
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0, **kwargs)
        self.size = size
        self.thickness = thickness
        self.color = color
        self.track_color = track_color
        self.cx = size / 2
        self.cy = size / 2
        self.pct = 0.5
        self.pad = thickness + 4
        self._draw()

    def set_pct(self, pct):
        self.pct = max(0.0, min(1.0, pct))
        self._draw()

    def _draw(self):
        self.delete("all")
        x0, y0 = self.pad, self.pad
        x1, y1 = self.size - self.pad, self.size - self.pad

        # Background Track (Full Circle)
        self.create_arc(x0, y0, x1, y1, start=0, extent=359.9, style="arc", outline=self.track_color, width=self.thickness)

        # Dynamic Value Arc
        start_ang = 90
        extent_ang = -int(self.pct * 360)
        if abs(extent_ang) > 0:
            val_color = self.color
            if self.pct > 0.85:
                val_color = "#F2B8B5"  # M3 Soft Red
            elif self.pct > 0.70:
                val_color = "#FDD663"  # M3 Amber
            self.create_arc(x0, y0, x1, y1, start=start_ang, extent=extent_ang, style="arc", outline=val_color, width=self.thickness)

        # Center Text
        pct_text = f"{int(self.pct * 100)}%"
        self.create_text(self.cx, self.cy - 3, text=pct_text, fill="#E2E2E6", font=("Segoe UI", 15, "bold"))
        self.create_text(self.cx, self.cy + 14, text="USED", fill="#8E919A", font=("Segoe UI", 8, "bold"))


class M3TaskBanner(ctk.CTkFrame):
    """
    Material 3 Expressive Live Task Banner.
    Displays dynamic shape morphing on the left, high-contrast task status text in center,
    and an M3 swirl loader on the right.
    """
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color="#004A77",
            border_color="#005B94",
            border_width=1,
            corner_radius=20,
            **kwargs
        )
        self.pack_propagate(True)

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=10)

        # Left Morph Loader
        self.morph = M3MorphLoader(inner, size=46, color="#A8C7FA", fill_color="#00315B", track_color="#004066", bg_color="#004A77")
        self.morph.pack(side="left", padx=(0, 14))

        # Center Text Box
        center_box = ctk.CTkFrame(inner, fg_color="transparent")
        center_box.pack(side="left", fill="both", expand=True)

        self.lbl_title = ctk.CTkLabel(
            center_box,
            text="Executing Task...",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#D1E4FF"
        )
        self.lbl_title.pack(anchor="w")

        self.lbl_step = ctk.CTkLabel(
            center_box,
            text="Initializing Material You automation...",
            font=ctk.CTkFont(size=11),
            text_color="#A8C7FA"
        )
        self.lbl_step.pack(anchor="w", pady=(2, 0))

        # Right Swirl Loader
        self.swirl = M3SwirlLoader(inner, size=26, thickness=2.5, color="#D1E4FF", track_color="#003554", bg_color="#004A77")
        self.swirl.pack(side="right", padx=(10, 4))

        self.is_active = False

    def show_task(self, title, step_text):
        self.is_active = True
        self.lbl_title.configure(text=title, text_color="#D1E4FF")
        self.lbl_step.configure(text=step_text, text_color="#A8C7FA")
        self.configure(fg_color="#004A77", border_color="#005B94")
        self.pack(fill="x", pady=(0, 14), padx=4)
        self.morph.set_colors("#A8C7FA", "#00315B")
        self.morph.start()
        self.swirl.start()

    def update_step(self, step_text):
        self.lbl_step.configure(text=step_text)

    def set_success(self, success_title="Task Completed Successfully", detail_text="All operations finished with zero errors."):
        self.lbl_title.configure(text=success_title, text_color="#A3F0BA")
        self.lbl_step.configure(text=detail_text, text_color="#C4EED0")
        self.configure(fg_color="#143523", border_color="#81C995")
        self.swirl.stop()
        self.morph.stop()
        self.morph.set_colors("#81C995", "#0F2B1B")

    def hide(self):
        self.is_active = False
        self.swirl.stop()
        self.morph.stop()
        self.pack_forget()


# -------------------------------------------------------------
# Material You Window Architecture
# -------------------------------------------------------------
class JioToolboxApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Configuration
        self.title(f"{APP_TITLE} • {APP_SUBTITLE}")
        self.geometry("1120x750")
        self.minsize(980, 660)

        # Set Dark Mode
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Material 3 Tonal Surface Architecture
        self.M3_SURFACE = "#111318"                 # Main Window Canvas
        self.M3_SURFACE_CONTAINER_LOW = "#171A20"   # Navigation Rail & Top Bar
        self.M3_SURFACE_CONTAINER = "#1D2027"       # Elevated Cards
        self.M3_SURFACE_CONTAINER_HIGH = "#262A33"  # Elevated Hover & Field Surface
        self.M3_SURFACE_CONTAINER_HIGHEST = "#313540" # Fields & Inputs
        self.M3_OUTLINE_VARIANT = "#2D313B"         # Subtle 1px Hairline
        self.M3_OUTLINE = "#454954"                 # Active Outline

        # Semantic Accent Tokens
        self.M3_PRIMARY = "#A8C7FA"                 # Monet Ice Blue (Primary CTA)
        self.M3_ON_PRIMARY = "#00315B"              # Text on Primary CTA
        self.M3_PRIMARY_CONTAINER = "#004A77"       # M3 Primary Container
        self.M3_ON_PRIMARY_CONTAINER = "#D1E4FF"

        self.M3_INDICATOR = "#004A77"               # Navigation Rail Active Pill
        self.M3_ON_INDICATOR = "#D1E4FF"

        self.M3_TERTIARY = "#7BD0C1"                # Teal Accent (Hunter)
        self.M3_TERTIARY_CONTAINER = "#004F46"
        self.M3_ON_TERTIARY_CONTAINER = "#97F0E0"

        self.M3_SUCCESS = "#81C995"                 # M3 Success Green
        self.M3_SUCCESS_CONTAINER = "#143523"
        self.M3_ON_SUCCESS_CONTAINER = "#A3F0BA"

        self.M3_ERROR = "#F2B8B5"                   # M3 Soft Red
        self.M3_ERROR_CONTAINER = "#3E1E1E"
        self.M3_ON_ERROR_CONTAINER = "#F9DEDC"

        self.M3_AMBER = "#FDD663"

        self.M3_ON_SURFACE = "#E2E2E6"              # Primary Text
        self.M3_ON_SURFACE_VARIANT = "#C4C6D0"      # Supporting Text
        self.M3_ON_SURFACE_MUTED = "#8E919A"        # Small Metadata

        self.configure(fg_color=self.M3_SURFACE)

        # Window Icon
        icon_path = os.path.join(BASE_DIR, "app_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        # Load Real Icons
        self._load_all_icons()

        # Managers & State
        self.msg_queue = queue.Queue()
        self.adb = ADBManager(log_callback=self.enqueue_log)
        self.installed_apps = []
        self.remote_config = {}
        self.is_hunting = False
        self.hunt_thread = None

        # Build UI Hierarchy
        self._build_top_app_bar()
        self._build_body_layout()

        # Start Async Queue & Connect
        self.after(100, self._process_log_queue)
        self.after(400, self._initial_connect)

    def _load_all_icons(self):
        # App Logo
        self.img_logo = load_ctk_image("app_icon.png", (38, 38))

        # Official App Icons (Real 44x44 Squircles)
        self.img_netflix = load_ctk_image("netflix.png", (42, 42))
        self.img_youtube = load_ctk_image("youtube.png", (42, 42))
        self.img_hotstar = load_ctk_image("hotstar.png", (42, 42))
        self.img_voot = load_ctk_image("voot.png", (42, 42))

        # Material 3 Nav Glyphs
        self.img_nav_hunter = load_ctk_image("nav_hunter.png", (20, 20))
        self.img_nav_fixes = load_ctk_image("nav_fixes.png", (20, 20))
        self.img_nav_boost = load_ctk_image("nav_boost.png", (20, 20))
        self.img_nav_remap = load_ctk_image("nav_remap.png", (20, 20))
        self.img_nav_apks = load_ctk_image("nav_apks.png", (20, 20))
        self.img_nav_terminal = load_ctk_image("nav_terminal.png", (20, 20))

        # Action Glyphs
        self.img_action_bt = load_ctk_image("action_bt.png", (20, 20))
        self.img_action_mic = load_ctk_image("action_mic.png", (20, 20))
        self.img_action_time = load_ctk_image("action_time.png", (20, 20))
        self.img_action_cert = load_ctk_image("action_cert.png", (20, 20))
        self.img_action_shizuku = load_ctk_image("action_shizuku.png", (20, 20))
        self.img_action_settings = load_ctk_image("action_settings.png", (20, 20))
        self.img_action_play = load_ctk_image("action_play.png", (14, 14))
        self.img_action_reboot = load_ctk_image("action_reboot.png", (15, 15))

    # ---------------------------------------------------------
    # Top App Bar (Material You Header)
    # ---------------------------------------------------------
    def _build_top_app_bar(self):
        header_frame = ctk.CTkFrame(self, fg_color=self.M3_SURFACE_CONTAINER_LOW, height=68, corner_radius=0)
        header_frame.pack(side="top", fill="x")
        header_frame.pack_propagate(False)

        # Left Branding
        brand_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        brand_frame.pack(side="left", padx=24, pady=12)

        if self.img_logo:
            ctk.CTkLabel(brand_frame, image=self.img_logo, text="").pack(side="left", padx=(0, 12))

        title_box = ctk.CTkFrame(brand_frame, fg_color="transparent")
        title_box.pack(side="left")

        lbl_title = ctk.CTkLabel(title_box, text=APP_TITLE, font=ctk.CTkFont(size=18, weight="bold"), text_color=self.M3_ON_SURFACE)
        lbl_title.pack(anchor="w")

        lbl_sub = ctk.CTkLabel(title_box, text="STB Jailbreak Suite • JHSC200 / JHSD200", font=ctk.CTkFont(size=11), text_color=self.M3_ON_SURFACE_MUTED)
        lbl_sub.pack(anchor="w")

        # Right Controls: Status Pill + IP Field + Primary Connect Pill
        conn_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        conn_frame.pack(side="right", padx=24, pady=12)

        self.top_swirl = M3SwirlLoader(
            conn_frame,
            size=24,
            thickness=2.5,
            color=self.M3_PRIMARY,
            track_color=self.M3_SURFACE_CONTAINER_HIGH,
            bg_color=self.M3_SURFACE_CONTAINER_LOW
        )

        self.status_badge = ctk.CTkLabel(
            conn_frame,
            text="● Disconnected",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.M3_ERROR,
            fg_color=self.M3_ERROR_CONTAINER,
            corner_radius=16,
            padx=14,
            pady=5
        )
        self.status_badge.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(conn_frame, text="STB IP", font=ctk.CTkFont(size=12, weight="bold"), text_color=self.M3_ON_SURFACE_VARIANT).pack(side="left", padx=(0, 6))

        self.entry_ip = ctk.CTkEntry(
            conn_frame,
            width=135,
            height=34,
            font=ctk.CTkFont(size=12),
            fg_color=self.M3_SURFACE_CONTAINER_HIGHEST,
            border_color=self.M3_OUTLINE_VARIANT,
            corner_radius=12
        )
        self.entry_ip.insert(0, self.adb.current_ip)
        self.entry_ip.pack(side="left", padx=(0, 8))

        self.btn_connect = ctk.CTkButton(
            conn_frame,
            text="Connect",
            width=85,
            height=34,
            fg_color=self.M3_PRIMARY_CONTAINER,
            hover_color="#005A91",
            text_color=self.M3_ON_PRIMARY_CONTAINER,
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=17,
            command=self._on_click_connect
        )
        self.btn_connect.pack(side="left", padx=(0, 6))

        self.btn_reboot = ctk.CTkButton(
            conn_frame,
            text="Reboot",
            image=self.img_action_reboot,
            compound="left",
            width=85,
            height=34,
            fg_color=self.M3_SURFACE_CONTAINER_HIGH,
            hover_color="#313642",
            text_color=self.M3_ON_SURFACE,
            font=ctk.CTkFont(size=11),
            corner_radius=17,
            command=self._on_click_reboot
        )
        self.btn_reboot.pack(side="left")

    def set_global_busy(self, busy: bool):
        if busy:
            try:
                self.top_swirl.pack(side="left", padx=(0, 10), before=self.status_badge)
                self.top_swirl.start()
            except Exception:
                pass
        else:
            try:
                self.top_swirl.stop()
                self.top_swirl.pack_forget()
            except Exception:
                pass

    # ---------------------------------------------------------
    # Body Layout: Material 3 Navigation Rail + View Area
    # ---------------------------------------------------------
    def _build_body_layout(self):
        body_frame = ctk.CTkFrame(self, fg_color=self.M3_SURFACE, corner_radius=0)
        body_frame.pack(fill="both", expand=True)

        # M3 Navigation Rail
        self.sidebar = ctk.CTkFrame(body_frame, fg_color=self.M3_SURFACE_CONTAINER_LOW, width=210, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Content Container
        self.content_container = ctk.CTkFrame(body_frame, fg_color=self.M3_SURFACE, corner_radius=0)
        self.content_container.pack(side="left", fill="both", expand=True, padx=20, pady=18)

        self.tabs = {}
        self.nav_buttons = {}

        nav_items = [
            ("fixes", "1-Click Fixes", self.img_nav_fixes, self._build_fixes_tab),
            ("remap", "Remote Remap", self.img_nav_remap, self._build_remap_tab),
            ("hunter", "STB Hunter", self.img_nav_hunter, self._build_hunter_tab),
            ("boost", "Speed & Boost", self.img_nav_boost, self._build_boost_tab),
            ("apks", "APK Sideload", self.img_nav_apks, self._build_apks_tab),
            ("terminal", "Live Terminal", self.img_nav_terminal, self._build_terminal_tab)
        ]

        ctk.CTkLabel(self.sidebar, text="WORKSPACES", font=ctk.CTkFont(size=10, weight="bold"), text_color=self.M3_ON_SURFACE_MUTED).pack(anchor="w", padx=24, pady=(20, 10))

        for tab_id, tab_label, icon, builder in nav_items:
            tab_frame = ctk.CTkFrame(self.content_container, fg_color="transparent")
            self.tabs[tab_id] = tab_frame
            builder(tab_frame)

            btn = ctk.CTkButton(
                self.sidebar,
                text=f"  {tab_label}",
                image=icon,
                compound="left",
                height=42,
                anchor="w",
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color="transparent",
                text_color=self.M3_ON_SURFACE_VARIANT,
                hover_color=self.M3_SURFACE_CONTAINER_HIGH,
                corner_radius=21,
                command=lambda tid=tab_id: self.select_tab(tid)
            )
            btn.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[tab_id] = btn

        # Device Metadata Footer in Rail
        sidebar_bottom = ctk.CTkFrame(self.sidebar, fg_color=self.M3_SURFACE_CONTAINER, corner_radius=16)
        sidebar_bottom.pack(side="bottom", fill="x", padx=14, pady=18)

        self.lbl_device_info = ctk.CTkLabel(
            sidebar_bottom,
            text="Device: Searching...\nAndroid: --\nUptime: --",
            font=ctk.CTkFont(size=11),
            text_color=self.M3_ON_SURFACE_MUTED,
            justify="left"
        )
        self.lbl_device_info.pack(padx=14, pady=12, anchor="w")

        # Default Active Tab
        self.select_tab("fixes")

    def select_tab(self, tab_id):
        for tid, frame in self.tabs.items():
            frame.pack_forget()
            self.nav_buttons[tid].configure(
                fg_color="transparent",
                text_color=self.M3_ON_SURFACE_VARIANT
            )

        self.tabs[tab_id].pack(fill="both", expand=True)
        # Material 3 Active Indicator Pill Style
        self.nav_buttons[tab_id].configure(
            fg_color=self.M3_INDICATOR,
            text_color=self.M3_ON_INDICATOR
        )

        if tab_id == "remap":
            self._reload_remap_view()
        elif tab_id == "boost":
            self._refresh_ram_meter()
        elif tab_id == "apks":
            self._refresh_installed_apps_tab()

    # ---------------------------------------------------------
    # TAB 1: 1-Click Fixes (Material You Tonal Cards)
    # ---------------------------------------------------------
    def _build_fixes_tab(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # M3 Expressive Task Banner (Morph + Swirl)
        self.fixes_task_banner = M3TaskBanner(scroll)
        self.fixes_task_banner.pack_forget()

        # Master Action Card (M3 Primary Container)
        master_card = ctk.CTkFrame(scroll, fg_color=self.M3_PRIMARY_CONTAINER, border_color="#005B94", border_width=1, corner_radius=20)
        master_card.pack(fill="x", pady=(0, 16), padx=4)

        m_in = ctk.CTkFrame(master_card, fg_color="transparent")
        m_in.pack(fill="x", padx=22, pady=16)

        top_m = ctk.CTkFrame(m_in, fg_color="transparent")
        top_m.pack(fill="x")

        lbl_m_title = ctk.CTkLabel(top_m, text="Run All Essential Fixes", font=ctk.CTkFont(size=16, weight="bold"), text_color=self.M3_ON_PRIMARY_CONTAINER)
        lbl_m_title.pack(side="left")

        self.btn_run_all_fixes = ctk.CTkButton(
            top_m,
            text="Apply All Fixes",
            height=36,
            width=150,
            fg_color=self.M3_PRIMARY,
            hover_color="#91B9F5",
            text_color=self.M3_ON_PRIMARY,
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=18,
            command=self._run_all_fixes
        )
        self.btn_run_all_fixes.pack(side="right")

        lbl_m_desc = ctk.CTkLabel(
            m_in,
            text="Unblocks Bluetooth accessories, fixes remote microphone search, syncs clock & DNS, and deploys shortcut remap daemon.",
            font=ctk.CTkFont(size=11),
            text_color="#C4DCFF"
        )
        lbl_m_desc.pack(anchor="w", pady=(4, 0))

        # Individual Fix Cards Grid (M3 SurfaceContainer with Action Icons)
        fixes = [
            (
                "Bluetooth Audio",
                self.img_action_bt,
                "Unblocks 3rd-party audio accessories (SoundDrum, boAt, Sony, JBL) & launches TV pairing",
                "Unblock Pairing",
                self._fix_bluetooth
            ),
            (
                "Voice Search Mic",
                self.img_action_mic,
                "Binds Google Assistant intent & grants recording perms to YouTube / media apps",
                "Fix Remote Mic",
                self._fix_mic
            ),
            (
                "Time & DNS Sync",
                self.img_action_time,
                "Syncs clock to PC epoch & disables captive portal / private DNS checks",
                "Sync Time & DNS",
                self._fix_network
            ),
            (
                "JHS Certificate",
                self.img_action_cert,
                "Applies offline CA certificate chain for local JHS bypass",
                "Apply Cert Fix",
                self._fix_cert
            ),
            (
                "Shizuku Server",
                self.img_action_shizuku,
                "Launches background Shizuku daemon for elevated app privileges",
                "Start Shizuku",
                self._start_shizuku
            ),
            (
                "TV Settings",
                self.img_action_settings,
                "Opens stock Android TV Settings directly on your television screen",
                "Open Settings",
                self._open_tv_settings
            )
        ]

        for title, icon, desc, btn_label, cmd in fixes:
            card = ctk.CTkFrame(scroll, fg_color=self.M3_SURFACE_CONTAINER, border_color=self.M3_OUTLINE_VARIANT, border_width=1, corner_radius=20)
            card.pack(fill="x", pady=5, padx=4)

            c_in = ctk.CTkFrame(card, fg_color="transparent")
            c_in.pack(fill="x", padx=20, pady=13)

            top_row = ctk.CTkFrame(c_in, fg_color="transparent")
            top_row.pack(fill="x")

            title_box = ctk.CTkFrame(top_row, fg_color="transparent")
            title_box.pack(side="left")

            if icon:
                ctk.CTkLabel(title_box, image=icon, text="").pack(side="left", padx=(0, 12))
            ctk.CTkLabel(title_box, text=title, font=ctk.CTkFont(size=14, weight="bold"), text_color=self.M3_ON_SURFACE).pack(side="left")

            btn = ctk.CTkButton(
                top_row,
                text=btn_label,
                height=32,
                width=145,
                fg_color=self.M3_SURFACE_CONTAINER_HIGH,
                hover_color="#323742",
                text_color=self.M3_ON_SURFACE,
                font=ctk.CTkFont(size=11, weight="bold"),
                corner_radius=16,
                command=cmd
            )
            btn.pack(side="right")

            ctk.CTkLabel(c_in, text=desc, font=ctk.CTkFont(size=11), text_color=self.M3_ON_SURFACE_MUTED).pack(anchor="w", pady=(4, 0))

    # ---------------------------------------------------------
    # TAB 2: Remote Remapper (Authentic Official App Icons)
    # ---------------------------------------------------------
    def _build_remap_tab(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # M3 Expressive Task Banner (Morph + Swirl)
        self.remap_task_banner = M3TaskBanner(scroll)
        self.remap_task_banner.pack_forget()

        # Header Info Card
        top_card = ctk.CTkFrame(scroll, fg_color=self.M3_SURFACE_CONTAINER, border_color=self.M3_OUTLINE_VARIANT, border_width=1, corner_radius=20)
        top_card.pack(fill="x", pady=(0, 16), padx=4)

        t_in = ctk.CTkFrame(top_card, fg_color="transparent")
        t_in.pack(fill="x", padx=22, pady=16)

        t_row = ctk.CTkFrame(t_in, fg_color="transparent")
        t_row.pack(fill="x")

        ctk.CTkLabel(t_row, text="Physical Remote 4-Button Remapper", font=ctk.CTkFont(size=17, weight="bold"), text_color=self.M3_ON_SURFACE).pack(side="left")

        self.lbl_daemon_badge = ctk.CTkLabel(
            t_row,
            text="● Daemon: Checking...",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.M3_AMBER,
            fg_color="#2B2416",
            corner_radius=14,
            padx=12,
            pady=3
        )
        self.lbl_daemon_badge.pack(side="right")

        ctk.CTkLabel(
            t_in,
            text="Direct kernel hook (/dev/input/event5). Remaps physical shortcut keys to any installed app.",
            font=ctk.CTkFont(size=11),
            text_color=self.M3_ON_SURFACE_MUTED
        ).pack(anchor="w", pady=(3, 0))

        # 4 Button Cards with Authentic Official Brand Squircles
        self.remap_combos = {}

        button_defs = [
            ("NETFLIX_PKG", "Netflix Button", self.img_netflix, "F7 • 185", "app.netmirror.newtv"),
            ("YOUTUBE_PKG", "YouTube Button", self.img_youtube, "F10 • 187", "io.gh.reisxd.tizentube.cobalt"),
            ("HOTSTAR_PKG", "JioHotstar Button", self.img_hotstar, "F8 • 184", "in.startv.hotstar"),
            ("VOOT_PKG", "Voot / JioCinema Button", self.img_voot, "F9 • 186", "com.viacom18.tv.voot")
        ]

        for key_name, btn_title, brand_icon, keycode_tag, default_pkg in button_defs:
            b_card = ctk.CTkFrame(scroll, fg_color=self.M3_SURFACE_CONTAINER, border_color=self.M3_OUTLINE_VARIANT, border_width=1, corner_radius=20)
            b_card.pack(fill="x", pady=6, padx=4)

            b_in = ctk.CTkFrame(b_card, fg_color="transparent")
            b_in.pack(fill="x", padx=18, pady=13)

            # Official Brand Squircle
            if brand_icon:
                ctk.CTkLabel(b_in, image=brand_icon, text="").pack(side="left", padx=(0, 14))

            left_box = ctk.CTkFrame(b_in, fg_color="transparent")
            left_box.pack(side="left", fill="x", expand=True)

            title_row = ctk.CTkFrame(left_box, fg_color="transparent")
            title_row.pack(anchor="w")

            ctk.CTkLabel(title_row, text=btn_title, font=ctk.CTkFont(size=13, weight="bold"), text_color=self.M3_ON_SURFACE).pack(side="left")
            
            # M3 Keycode Assist Chip
            chip = ctk.CTkLabel(
                title_row,
                text=keycode_tag,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=self.M3_ON_SURFACE_MUTED,
                fg_color=self.M3_SURFACE,
                corner_radius=8,
                padx=8,
                pady=1
            )
            chip.pack(side="left", padx=8)

            combo = ctk.CTkComboBox(
                left_box,
                width=450,
                height=32,
                values=["Loading installed apps..."],
                font=ctk.CTkFont(size=12),
                fg_color=self.M3_SURFACE,
                border_color=self.M3_OUTLINE_VARIANT,
                button_color=self.M3_PRIMARY_CONTAINER,
                button_hover_color="#005A91",
                corner_radius=10
            )
            combo.set(default_pkg)
            combo.pack(anchor="w", pady=(6, 0))
            self.remap_combos[key_name] = combo

            # M3 Tonal Test Button
            btn_test = ctk.CTkButton(
                b_in,
                text="Test",
                image=self.img_action_play,
                compound="left",
                height=32,
                width=80,
                fg_color=self.M3_SURFACE_CONTAINER_HIGH,
                hover_color="#323742",
                text_color=self.M3_ON_SURFACE,
                font=ctk.CTkFont(size=11),
                corner_radius=16,
                command=lambda k=key_name: self._test_launch_mapped_app(k)
            )
            btn_test.pack(side="right", padx=(10, 0), pady=(10, 0))

        # Bottom Action Bar
        act_card = ctk.CTkFrame(scroll, fg_color="transparent")
        act_card.pack(fill="x", pady=16, padx=4)

        self.btn_save_remap = ctk.CTkButton(
            act_card,
            text="Save & Deploy to Remote",
            height=38,
            width=210,
            fg_color=self.M3_SUCCESS_CONTAINER,
            hover_color="#1D4A32",
            text_color=self.M3_SUCCESS,
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=19,
            command=self._save_and_deploy_remap
        )
        self.btn_save_remap.pack(side="left", padx=(0, 10))

        btn_reload = ctk.CTkButton(
            act_card,
            text="Refresh Apps",
            height=38,
            width=130,
            fg_color=self.M3_SURFACE_CONTAINER,
            hover_color=self.M3_SURFACE_CONTAINER_HIGH,
            text_color=self.M3_ON_SURFACE,
            font=ctk.CTkFont(size=11),
            corner_radius=19,
            command=self._reload_remap_view
        )
        btn_reload.pack(side="left")

    # ---------------------------------------------------------
    # TAB 3: STB Hunter & Activator
    # ---------------------------------------------------------
    def _build_hunter_tab(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        banner = ctk.CTkFrame(scroll, fg_color=self.M3_SURFACE_CONTAINER, border_color=self.M3_OUTLINE_VARIANT, border_width=1, corner_radius=20)
        banner.pack(fill="x", pady=(0, 16), padx=4)

        b_in = ctk.CTkFrame(banner, fg_color="transparent")
        b_in.pack(fill="x", padx=22, pady=16)

        ctk.CTkLabel(b_in, text="STB Autonomous Hunter", font=ctk.CTkFont(size=18, weight="bold"), text_color=self.M3_ON_SURFACE).pack(anchor="w")
        ctk.CTkLabel(
            b_in,
            text="Intercepts ADB port 5555 on boot after USB / TR-069 exploit, verifies connection, and applies persistent fixes.",
            font=ctk.CTkFont(size=12),
            text_color=self.M3_ON_SURFACE_MUTED
        ).pack(anchor="w", pady=(3, 0))

        ctrl_card = ctk.CTkFrame(scroll, fg_color=self.M3_SURFACE_CONTAINER, border_color=self.M3_OUTLINE_VARIANT, border_width=1, corner_radius=20)
        ctrl_card.pack(fill="x", pady=(0, 16), padx=4)

        c_pad = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        c_pad.pack(fill="x", padx=22, pady=16)

        mode_row = ctk.CTkFrame(c_pad, fg_color="transparent")
        mode_row.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(mode_row, text="Probe Mode:", font=ctk.CTkFont(size=12, weight="bold"), text_color=self.M3_ON_SURFACE).pack(side="left", padx=(0, 10))

        self.hunt_mode_var = ctk.StringVar(value="subnet")
        r1 = ctk.CTkRadioButton(mode_row, text="Subnet Radar Scan (50 parallel threads)", variable=self.hunt_mode_var, value="subnet")
        r1.pack(side="left", padx=10)
        r2 = ctk.CTkRadioButton(mode_row, text="Target IP Direct Loop", variable=self.hunt_mode_var, value="ip")
        r2.pack(side="left", padx=10)

        opt_row = ctk.CTkFrame(c_pad, fg_color="transparent")
        opt_row.pack(fill="x", pady=(0, 14))

        self.var_auto_activate = ctk.BooleanVar(value=True)
        cb1 = ctk.CTkCheckBox(opt_row, text="Auto-activate fixes (Bluetooth unblock, Time sync, Remap daemon) upon catch", variable=self.var_auto_activate)
        cb1.pack(side="left")

        # M3 Expressive Radar Scope & Dynamic Telemetry
        scope_card = ctk.CTkFrame(c_pad, fg_color=self.M3_SURFACE, border_color=self.M3_OUTLINE_VARIANT, border_width=1, corner_radius=18)
        scope_card.pack(fill="x", pady=(6, 14))

        sc_in = ctk.CTkFrame(scope_card, fg_color="transparent")
        sc_in.pack(fill="x", padx=16, pady=12)

        # Left: Interactive M3 Morphing Scope
        self.hunter_scope = M3HunterScope(sc_in, size=130, color=self.M3_TERTIARY, fill_color=self.M3_TERTIARY_CONTAINER, bg_color=self.M3_SURFACE)
        self.hunter_scope.pack(side="left", padx=(0, 16))

        # Right: Real-time telemetry, M3 Swirl loader & status
        tel_box = ctk.CTkFrame(sc_in, fg_color="transparent")
        tel_box.pack(side="left", fill="both", expand=True)

        t_title_row = ctk.CTkFrame(tel_box, fg_color="transparent")
        t_title_row.pack(fill="x", pady=(2, 6))

        ctk.CTkLabel(t_title_row, text="Subnet ADB Radar Scanner", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.M3_ON_SURFACE).pack(side="left")

        # M3 Swirl Loader next to Hunter Status
        self.hunt_swirl = M3SwirlLoader(t_title_row, size=22, thickness=2.5, color=self.M3_TERTIARY, track_color=self.M3_SURFACE_CONTAINER_HIGH, bg_color=self.M3_SURFACE)
        self.hunt_swirl.pack(side="right", padx=(6, 0))
        self.hunt_swirl.pack_forget()

        self.lbl_hunt_status = ctk.CTkLabel(
            tel_box,
            text="Hunter idle. Plug in STB power cord and click 'Start STB Hunter'.",
            font=ctk.CTkFont(size=12),
            text_color=self.M3_ON_SURFACE_MUTED,
            anchor="w"
        )
        self.lbl_hunt_status.pack(fill="x", pady=(0, 8))

        # Assist chips row
        chip_row = ctk.CTkFrame(tel_box, fg_color="transparent")
        chip_row.pack(fill="x")

        self.chip_attempts = ctk.CTkLabel(
            chip_row,
            text="Attempts: 0",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.M3_ON_SURFACE_MUTED,
            fg_color=self.M3_SURFACE_CONTAINER_HIGH,
            corner_radius=10,
            padx=10,
            pady=3
        )
        self.chip_attempts.pack(side="left", padx=(0, 8))

        self.chip_elapsed = ctk.CTkLabel(
            chip_row,
            text="Elapsed: 0s",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.M3_ON_SURFACE_MUTED,
            fg_color=self.M3_SURFACE_CONTAINER_HIGH,
            corner_radius=10,
            padx=10,
            pady=3
        )
        self.chip_elapsed.pack(side="left", padx=(0, 8))

        self.chip_threads = ctk.CTkLabel(
            chip_row,
            text="50 Threads Parallel",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.M3_TERTIARY,
            fg_color=self.M3_TERTIARY_CONTAINER,
            corner_radius=10,
            padx=10,
            pady=3
        )
        self.chip_threads.pack(side="left")

        # Action Button Row
        btn_row = ctk.CTkFrame(c_pad, fg_color="transparent")
        btn_row.pack(fill="x")

        self.btn_hunt_toggle = ctk.CTkButton(
            btn_row,
            text="Start STB Hunter",
            image=self.img_nav_hunter,
            compound="left",
            height=38,
            width=170,
            fg_color=self.M3_TERTIARY_CONTAINER,
            hover_color="#006358",
            text_color=self.M3_TERTIARY,
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=19,
            command=self._toggle_hunter
        )
        self.btn_hunt_toggle.pack(side="left")

        self.caught_card = ctk.CTkFrame(scroll, fg_color=self.M3_SUCCESS_CONTAINER, border_color=self.M3_SUCCESS, border_width=1, corner_radius=20)
        
        c_in = ctk.CTkFrame(self.caught_card, fg_color="transparent")
        c_in.pack(fill="x", padx=22, pady=16)

        self.lbl_caught_title = ctk.CTkLabel(c_in, text="STB Hooked & Connected", font=ctk.CTkFont(size=16, weight="bold"), text_color=self.M3_SUCCESS)
        self.lbl_caught_title.pack(anchor="w")

        self.lbl_caught_detail = ctk.CTkLabel(
            c_in,
            text="ADB port 5555 is live. Handshake verified. Exploit successfully survived reboot.",
            font=ctk.CTkFont(size=12),
            text_color="#C4EED0"
        )
        self.lbl_caught_detail.pack(anchor="w", pady=(3, 0))

        guide_card = ctk.CTkFrame(scroll, fg_color=self.M3_SURFACE_CONTAINER, border_color=self.M3_OUTLINE_VARIANT, border_width=1, corner_radius=20)
        guide_card.pack(fill="x", pady=10, padx=4)

        g_in = ctk.CTkFrame(guide_card, fg_color="transparent")
        g_in.pack(fill="x", padx=22, pady=16)

        ctk.CTkLabel(g_in, text="Hunter Workflow", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.M3_ON_SURFACE).pack(anchor="w")
        
        steps = [
            "1. Unplug the power adapter of the STB after completing exploit setup.",
            "2. Click 'Start STB Hunter' above to begin parallel subnet radar monitoring.",
            "3. Plug the power cable back into the Jio STB to boot Android 11.",
            "4. The hunter detects ADB port 5555 instantaneously upon Wi-Fi handshake."
        ]
        for step in steps:
            ctk.CTkLabel(g_in, text=step, font=ctk.CTkFont(size=11), text_color=self.M3_ON_SURFACE_MUTED).pack(anchor="w", pady=2)

    # ---------------------------------------------------------
    # TAB 4: Speed & Boost
    # ---------------------------------------------------------
    def _build_boost_tab(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        ram_card = ctk.CTkFrame(scroll, fg_color=self.M3_SURFACE_CONTAINER, border_color=self.M3_OUTLINE_VARIANT, border_width=1, corner_radius=20)
        ram_card.pack(fill="x", pady=(0, 16), padx=4)

        r_in = ctk.CTkFrame(ram_card, fg_color="transparent")
        r_in.pack(fill="x", padx=22, pady=16)

        r_top = ctk.CTkFrame(r_in, fg_color="transparent")
        r_top.pack(fill="x")

        ctk.CTkLabel(r_top, text="Memory Telemetry", font=ctk.CTkFont(size=15, weight="bold"), text_color=self.M3_ON_SURFACE).pack(side="left")

        btn_purge = ctk.CTkButton(
            r_top,
            text="Purge & Compact",
            height=30,
            width=140,
            fg_color=self.M3_PRIMARY_CONTAINER,
            hover_color="#005A91",
            text_color=self.M3_ON_PRIMARY_CONTAINER,
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=15,
            command=self._purge_ram
        )
        btn_purge.pack(side="right")

        # M3 Expressive Circular Arc Gauge Layout
        m_frame = ctk.CTkFrame(r_in, fg_color="transparent")
        m_frame.pack(fill="x", pady=(10, 4))

        self.ram_gauge = M3RamGauge(m_frame, size=116, thickness=8, color=self.M3_PRIMARY, track_color=self.M3_SURFACE_CONTAINER_HIGH, bg_color=self.M3_SURFACE_CONTAINER)
        self.ram_gauge.pack(side="left", padx=(0, 20))

        stat_col = ctk.CTkFrame(m_frame, fg_color="transparent")
        stat_col.pack(side="left", fill="both", expand=True)

        self.stat_used = ctk.CTkLabel(
            stat_col,
            text="Used RAM: -- MB (--%)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.M3_ON_SURFACE,
            anchor="w"
        )
        self.stat_used.pack(fill="x", pady=2)

        self.stat_avail = ctk.CTkLabel(
            stat_col,
            text="Available RAM: -- MB",
            font=ctk.CTkFont(size=12),
            text_color=self.M3_SUCCESS,
            anchor="w"
        )
        self.stat_avail.pack(fill="x", pady=2)

        self.stat_total = ctk.CTkLabel(
            stat_col,
            text="Total Physical Memory: -- MB",
            font=ctk.CTkFont(size=11),
            text_color=self.M3_ON_SURFACE_MUTED,
            anchor="w"
        )
        self.stat_total.pack(fill="x", pady=2)

        tune_card = ctk.CTkFrame(scroll, fg_color=self.M3_SURFACE_CONTAINER, border_color=self.M3_OUTLINE_VARIANT, border_width=1, corner_radius=20)
        tune_card.pack(fill="x", pady=(0, 16), padx=4)

        t_in = ctk.CTkFrame(tune_card, fg_color="transparent")
        t_in.pack(fill="x", padx=22, pady=16)

        ctk.CTkLabel(t_in, text="Responsiveness & Memory Limits", font=ctk.CTkFont(size=15, weight="bold"), text_color=self.M3_ON_SURFACE).pack(anchor="w", pady=(0, 12))

        # Animation Speed
        anim_row = ctk.CTkFrame(t_in, fg_color="transparent")
        anim_row.pack(fill="x", pady=6)

        ctk.CTkLabel(anim_row, text="Animation Scale:", font=ctk.CTkFont(size=12, weight="bold"), text_color=self.M3_ON_SURFACE, width=150, anchor="w").pack(side="left")

        self.seg_anim = ctk.CTkSegmentedButton(
            anim_row,
            values=["0.0x Instant", "0.5x Snappy", "1.0x Stock"],
            selected_color=self.M3_PRIMARY_CONTAINER,
            selected_hover_color="#005A91",
            corner_radius=14
        )
        self.seg_anim.set("0.5x Snappy")
        self.seg_anim.pack(side="left", padx=10)

        ctk.CTkButton(anim_row, text="Apply", width=70, height=28, fg_color=self.M3_SURFACE_CONTAINER_HIGH, hover_color="#323742", corner_radius=14, command=self._apply_anim_speed).pack(side="left")

        # Background Process Limit
        proc_row = ctk.CTkFrame(t_in, fg_color="transparent")
        proc_row.pack(fill="x", pady=6)

        ctk.CTkLabel(proc_row, text="Cached Processes:", font=ctk.CTkFont(size=12, weight="bold"), text_color=self.M3_ON_SURFACE, width=150, anchor="w").pack(side="left")

        self.seg_proc = ctk.CTkSegmentedButton(
            proc_row,
            values=["10 (Recommended)", "8 (Aggressive)", "4 (Ultra Lite)", "32 (Stock)"],
            selected_color=self.M3_PRIMARY_CONTAINER,
            selected_hover_color="#005A91",
            corner_radius=14
        )
        self.seg_proc.set("10 (Recommended)")
        self.seg_proc.pack(side="left", padx=10)

        ctk.CTkButton(proc_row, text="Apply", width=70, height=28, fg_color=self.M3_SURFACE_CONTAINER_HIGH, hover_color="#323742", corner_radius=14, command=self._apply_proc_limit).pack(side="left")

        bloat_card = ctk.CTkFrame(scroll, fg_color=self.M3_SURFACE_CONTAINER, border_color=self.M3_OUTLINE_VARIANT, border_width=1, corner_radius=20)
        bloat_card.pack(fill="x", pady=6, padx=4)

        b_in = ctk.CTkFrame(bloat_card, fg_color="transparent")
        b_in.pack(fill="x", padx=22, pady=16)

        ctk.CTkLabel(b_in, text="Background Telemetry Debloater", font=ctk.CTkFont(size=15, weight="bold"), text_color=self.M3_ON_SURFACE).pack(anchor="w")
        ctk.CTkLabel(
            b_in,
            text="Suspends background logging daemons (CloudLogger, Telemetry, STBInfo, JioStore). Safe and reversible.",
            font=ctk.CTkFont(size=11),
            text_color=self.M3_ON_SURFACE_MUTED
        ).pack(anchor="w", pady=(3, 10))

        b_btn_row = ctk.CTkFrame(b_in, fg_color="transparent")
        b_btn_row.pack(fill="x")

        ctk.CTkButton(
            b_btn_row,
            text="Disable Telemetry",
            height=32,
            width=160,
            fg_color=self.M3_ERROR_CONTAINER,
            hover_color=self.M3_ERROR,
            text_color=self.M3_ERROR,
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=16,
            command=self._disable_bloatware
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            b_btn_row,
            text="Restore Stock",
            height=32,
            width=140,
            fg_color=self.M3_SURFACE_CONTAINER_HIGH,
            hover_color="#323742",
            font=ctk.CTkFont(size=11),
            corner_radius=16,
            command=self._restore_bloatware
        ).pack(side="left")

    # ---------------------------------------------------------
    # TAB 5: APK Sideload & Perms
    # ---------------------------------------------------------
    def _build_apks_tab(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # M3 Expressive Task Banner (Morph + Swirl)
        self.apk_task_banner = M3TaskBanner(scroll)
        self.apk_task_banner.pack_forget()

        batch_card = ctk.CTkFrame(scroll, fg_color=self.M3_SURFACE_CONTAINER, border_color=self.M3_OUTLINE_VARIANT, border_width=1, corner_radius=20)
        batch_card.pack(fill="x", pady=(0, 16), padx=4)

        b_in = ctk.CTkFrame(batch_card, fg_color="transparent")
        b_in.pack(fill="x", padx=22, pady=16)

        ctk.CTkLabel(b_in, text="Silent Batch APK Sideload", font=ctk.CTkFont(size=15, weight="bold"), text_color=self.M3_ON_SURFACE).pack(anchor="w")
        ctk.CTkLabel(
            b_in,
            text="Installs all packages in 'apks/' in background with zero TV interruption.",
            font=ctk.CTkFont(size=11),
            text_color=self.M3_ON_SURFACE_MUTED
        ).pack(anchor="w", pady=(3, 10))

        b_row = ctk.CTkFrame(b_in, fg_color="transparent")
        b_row.pack(fill="x")

        self.btn_install_batch = ctk.CTkButton(
            b_row,
            text="Install All in 'apks/'",
            height=34,
            width=190,
            fg_color=self.M3_PRIMARY_CONTAINER,
            hover_color="#005A91",
            text_color=self.M3_ON_PRIMARY_CONTAINER,
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=17,
            command=self._install_batch_apks
        )
        self.btn_install_batch.pack(side="left", padx=(0, 10))

        btn_open_folder = ctk.CTkButton(
            b_row,
            text="Open Folder",
            height=34,
            width=120,
            fg_color=self.M3_SURFACE_CONTAINER_HIGH,
            hover_color="#323742",
            font=ctk.CTkFont(size=11),
            corner_radius=17,
            command=self._open_apks_folder
        )
        btn_open_folder.pack(side="left")

        perm_card = ctk.CTkFrame(scroll, fg_color=self.M3_SURFACE_CONTAINER, border_color=self.M3_OUTLINE_VARIANT, border_width=1, corner_radius=20)
        perm_card.pack(fill="x", pady=(0, 16), padx=4)

        p_in = ctk.CTkFrame(perm_card, fg_color="transparent")
        p_in.pack(fill="x", padx=22, pady=16)

        ctk.CTkLabel(p_in, text="Auto-Grant Permissions & Unknown Sources", font=ctk.CTkFont(size=15, weight="bold"), text_color=self.M3_ON_SURFACE).pack(anchor="w")
        ctk.CTkLabel(
            p_in,
            text="Grants storage, microphone, and Unknown Sources to all apps so you can install and use apps on the STB natively.",
            font=ctk.CTkFont(size=11),
            text_color=self.M3_ON_SURFACE_MUTED
        ).pack(anchor="w", pady=(3, 10))

        ctk.CTkButton(
            p_in,
            text="Auto-Grant Permissions",
            height=34,
            width=210,
            fg_color=self.M3_SUCCESS_CONTAINER,
            hover_color="#1D4A32",
            text_color=self.M3_SUCCESS,
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=17,
            command=self._grant_all_permissions
        ).pack(anchor="w")

        single_card = ctk.CTkFrame(scroll, fg_color=self.M3_SURFACE_CONTAINER, border_color=self.M3_OUTLINE_VARIANT, border_width=1, corner_radius=20)
        single_card.pack(fill="x", pady=6, padx=4)

        s_in = ctk.CTkFrame(single_card, fg_color="transparent")
        s_in.pack(fill="x", padx=22, pady=16)

        ctk.CTkLabel(s_in, text="Install Individual APK", font=ctk.CTkFont(size=15, weight="bold"), text_color=self.M3_ON_SURFACE).pack(anchor="w", pady=(0, 8))

        s_row = ctk.CTkFrame(s_in, fg_color="transparent")
        s_row.pack(fill="x")

        self.entry_single_apk = ctk.CTkEntry(
            s_row,
            placeholder_text="Select or drop .apk file...",
            height=34,
            fg_color=self.M3_SURFACE,
            border_color=self.M3_OUTLINE_VARIANT,
            corner_radius=12
        )
        self.entry_single_apk.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkButton(
            s_row,
            text="Browse",
            width=80,
            height=34,
            fg_color=self.M3_SURFACE_CONTAINER_HIGH,
            hover_color="#323742",
            corner_radius=17,
            command=self._browse_single_apk
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            s_row,
            text="Install",
            width=90,
            height=34,
            fg_color=self.M3_PRIMARY_CONTAINER,
            hover_color="#005A91",
            text_color=self.M3_ON_PRIMARY_CONTAINER,
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=17,
            command=self._install_single_apk
        ).pack(side="left")

        app_list_card = ctk.CTkFrame(scroll, fg_color=self.M3_SURFACE_CONTAINER, border_color=self.M3_OUTLINE_VARIANT, border_width=1, corner_radius=20)
        app_list_card.pack(fill="x", pady=10, padx=4)

        al_in = ctk.CTkFrame(app_list_card, fg_color="transparent")
        al_in.pack(fill="x", padx=22, pady=16)

        al_top = ctk.CTkFrame(al_in, fg_color="transparent")
        al_top.pack(fill="x")

        ctk.CTkLabel(al_top, text="Sideloaded Apps Manager", font=ctk.CTkFont(size=15, weight="bold"), text_color=self.M3_ON_SURFACE).pack(side="left")
        
        btn_refresh_al = ctk.CTkButton(
            al_top,
            text="Refresh",
            width=80,
            height=28,
            fg_color=self.M3_SURFACE_CONTAINER_HIGH,
            hover_color="#323742",
            corner_radius=14,
            command=self._refresh_installed_apps_tab
        )
        btn_refresh_al.pack(side="right")

        ctk.CTkLabel(al_in, text="Quick launch or inspect packages directly on your TV.", font=ctk.CTkFont(size=11), text_color=self.M3_ON_SURFACE_MUTED).pack(anchor="w", pady=(2, 8))

        self.combo_installed_apps = ctk.CTkComboBox(
            al_in,
            width=480,
            height=34,
            values=["Click Refresh to load apps..."],
            fg_color=self.M3_SURFACE,
            border_color=self.M3_OUTLINE_VARIANT,
            button_color=self.M3_PRIMARY_CONTAINER,
            corner_radius=10
        )
        self.combo_installed_apps.pack(anchor="w", pady=(0, 10))

        al_btns = ctk.CTkFrame(al_in, fg_color="transparent")
        al_btns.pack(anchor="w")

        ctk.CTkButton(
            al_btns,
            text="Launch on TV",
            image=self.img_action_play,
            compound="left",
            width=135,
            height=32,
            fg_color=self.M3_SURFACE_CONTAINER_HIGH,
            hover_color="#323742",
            corner_radius=16,
            command=self._launch_selected_app
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            al_btns,
            text="Uninstall",
            width=110,
            height=32,
            fg_color=self.M3_ERROR_CONTAINER,
            hover_color=self.M3_ERROR,
            text_color=self.M3_ERROR,
            corner_radius=16,
            command=self._uninstall_selected_app
        ).pack(side="left")

    def _refresh_installed_apps_tab(self):
        def work():
            _, out, _ = self.adb.run_cmd(["shell", "pm list packages -3"])
            apps = []
            for line in out.splitlines():
                pkg = line.replace("package:", "").strip()
                if pkg:
                    label = KNOWN_NAMES.get(pkg, pkg)
                    apps.append(f"{label} [{pkg}]")
            vals = apps if apps else ["No user packages found"]
            self.after(0, lambda: self.combo_installed_apps.configure(values=vals))
            if apps:
                self.after(0, lambda: self.combo_installed_apps.set(apps[0]))
        threading.Thread(target=work, daemon=True).start()

    def _launch_selected_app(self):
        val = self.combo_installed_apps.get()
        if "[" in val and val.endswith("]"):
            pkg = val.split("[")[-1].replace("]", "").strip()
        else:
            pkg = val.strip()

        def work():
            self.adb.log(f"Launching {pkg} on TV...", "INFO")
            _, act_out, _ = self.adb.run_cmd(["shell", f"cmd package resolve-activity --brief {pkg} 2>/dev/null"])
            act = ""
            for l in act_out.splitlines():
                if "/" in l and not l.startswith("priority"):
                    act = l.strip()
                    break
            if act:
                self.adb.run_cmd(["shell", f"am start -n {act}"])
            else:
                self.adb.run_cmd(["shell", f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1 2>/dev/null"])
            self.adb.log(f"Launched {pkg}", "SUCCESS")
        threading.Thread(target=work, daemon=True).start()

    def _uninstall_selected_app(self):
        val = self.combo_installed_apps.get()
        if "[" in val and val.endswith("]"):
            pkg = val.split("[")[-1].replace("]", "").strip()
        else:
            pkg = val.strip()

        def work():
            self.adb.log(f"Uninstalling {pkg}...", "INFO")
            ok, out, _ = self.adb.run_cmd(["uninstall", pkg])
            if "Success" in out:
                self.adb.log(f"Uninstalled {pkg}", "SUCCESS")
                self._refresh_installed_apps_tab()
            else:
                self.adb.log(f"Failed to uninstall: {out}", "ERR")
        threading.Thread(target=work, daemon=True).start()

    # ---------------------------------------------------------
    # TAB 6: Live Console / Terminal
    # ---------------------------------------------------------
    def _build_terminal_tab(self, parent):
        t_frame = ctk.CTkFrame(parent, fg_color=self.M3_SURFACE_CONTAINER, border_color=self.M3_OUTLINE_VARIANT, border_width=1, corner_radius=20)
        t_frame.pack(fill="both", expand=True, padx=4, pady=4)

        top_bar = ctk.CTkFrame(t_frame, fg_color="transparent", height=40)
        top_bar.pack(fill="x", padx=18, pady=12)

        ctk.CTkLabel(top_bar, text="Execution Console", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.M3_ON_SURFACE).pack(side="left")

        btn_copy = ctk.CTkButton(
            top_bar,
            text="Copy Log",
            width=85,
            height=28,
            fg_color=self.M3_SURFACE_CONTAINER_HIGH,
            hover_color="#323742",
            font=ctk.CTkFont(size=11),
            corner_radius=14,
            command=self._copy_terminal_log
        )
        btn_copy.pack(side="right", padx=(8, 0))

        btn_clear = ctk.CTkButton(
            top_bar,
            text="Clear",
            width=65,
            height=28,
            fg_color=self.M3_SURFACE_CONTAINER_HIGH,
            hover_color="#323742",
            font=ctk.CTkFont(size=11),
            corner_radius=14,
            command=self._clear_terminal_log
        )
        btn_clear.pack(side="right")

        self.txt_terminal = ctk.CTkTextbox(
            t_frame,
            fg_color="#0A0D12",
            text_color=self.M3_PRIMARY,
            font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=12
        )
        self.txt_terminal.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    # ---------------------------------------------------------
    # Thread-Safe Logging & Queue Processing
    # ---------------------------------------------------------
    def _safe_after(self, delay, func):
        try:
            self.after(delay, func)
        except Exception:
            pass

    def enqueue_log(self, msg, level="INFO"):
        now = datetime.now().strftime("%H:%M:%S")
        self.msg_queue.put((now, level, msg))

    def _process_log_queue(self):
        try:
            while True:
                now, level, msg = self.msg_queue.get_nowait()
                prefix = f"[{now}] "
                if level == "CMD":
                    formatted = f"{prefix}> {msg}\n"
                elif level == "SUCCESS":
                    formatted = f"{prefix}OK: {msg}\n"
                elif level == "WARN":
                    formatted = f"{prefix}WARN: {msg}\n"
                elif level == "ERR":
                    formatted = f"{prefix}ERR: {msg}\n"
                else:
                    formatted = f"{prefix}{msg}\n"

                self.txt_terminal.insert("end", formatted)
                self.txt_terminal.see("end")
        except queue.Empty:
            pass
        self.after(80, self._process_log_queue)

    def _clear_terminal_log(self):
        self.txt_terminal.delete("1.0", "end")

    def _copy_terminal_log(self):
        text = self.txt_terminal.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.enqueue_log("Log copied to clipboard", "INFO")

    # ---------------------------------------------------------
    # Async Connection & Hardware Poller
    # ---------------------------------------------------------
    def _initial_connect(self):
        ip = self.entry_ip.get().strip() or self.adb.current_ip
        threading.Thread(target=self._worker_connect, args=(ip,), daemon=True).start()

    def _on_click_connect(self):
        ip = self.entry_ip.get().strip()
        if not ip:
            return
        self.btn_connect.configure(state="disabled", text="Connecting...")
        threading.Thread(target=self._worker_connect, args=(ip,), daemon=True).start()

    def _worker_connect(self, ip):
        success = self.adb.connect(ip)
        self.after(0, lambda: self._update_connection_ui(success, ip))

    def _update_connection_ui(self, connected, ip):
        self.btn_connect.configure(state="normal", text="Connect")
        if connected:
            self.status_badge.configure(
                text=f"● Connected: {ip}",
                text_color=self.M3_SUCCESS,
                fg_color=self.M3_SUCCESS_CONTAINER
            )
            threading.Thread(target=self._worker_fetch_info, daemon=True).start()
        else:
            self.status_badge.configure(
                text="● Disconnected",
                text_color=self.M3_ERROR,
                fg_color=self.M3_ERROR_CONTAINER
            )
            self.lbl_device_info.configure(text=f"Target: {ip}\nStatus: Disconnected\nADB Port: Closed")

    def _worker_fetch_info(self):
        info = self.adb.get_device_info()
        txt = f"Model: {info.get('model', 'Jio STB')}\nAndroid: {info.get('android', '11')}\nUptime: {info.get('uptime', '--')}"
        self.after(0, lambda: self.lbl_device_info.configure(text=txt))

    def _on_click_reboot(self):
        def work():
            self.adb.run_cmd(["reboot"])
            self.adb.is_connected = False
            self.after(0, lambda: self._update_connection_ui(False, self.adb.current_ip))
        threading.Thread(target=work, daemon=True).start()

    # ---------------------------------------------------------
    # STB Hunter Logic (Subnet & IP Probe)
    # ---------------------------------------------------------
    def _toggle_hunter(self):
        if not self.is_hunting:
            self.is_hunting = True
            self.btn_hunt_toggle.configure(text="Stop Hunter", fg_color=self.M3_ERROR_CONTAINER, text_color=self.M3_ERROR)
            self.lbl_hunt_status.configure(text="Radar active. Morph scanner listening for port 5555...", text_color=self.M3_TERTIARY)
            self.hunt_swirl.pack(side="right", padx=(6, 0))
            self.hunt_swirl.start()
            self.hunter_scope.start_hunt()
            self.caught_card.pack_forget()
            mode = self.hunt_mode_var.get()
            target_ip = self.entry_ip.get().strip() or self.adb.current_ip
            self.hunt_thread = threading.Thread(target=self._worker_hunter, args=(mode, target_ip), daemon=True)
            self.hunt_thread.start()
        else:
            self.is_hunting = False
            self.btn_hunt_toggle.configure(text="Start STB Hunter", fg_color=self.M3_TERTIARY_CONTAINER, text_color=self.M3_TERTIARY)
            self.lbl_hunt_status.configure(text="Hunter idle. Plug in STB power cord and click 'Start STB Hunter'.", text_color=self.M3_ON_SURFACE_MUTED)
            self.hunt_swirl.stop()
            self.hunt_swirl.pack_forget()
            self.hunter_scope.stop_hunt()

    def _worker_hunter(self, mode, target_ip):
        self.adb.log(f"Starting hunter in [{mode.upper()}] mode...", "INFO")
        attempts = 0
        start_time = time.time()

        while self.is_hunting:
            attempts += 1
            elapsed = int(time.time() - start_time)

            self._safe_after(0, lambda a=attempts: self.chip_attempts.configure(text=f"Attempts: {a}"))
            self._safe_after(0, lambda e=elapsed: self.chip_elapsed.configure(text=f"Elapsed: {e}s"))

            if mode == "ip":
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.7)
                port_open = False
                try:
                    port_open = (s.connect_ex((target_ip, DEFAULT_ADB_PORT)) == 0)
                except Exception:
                    pass
                finally:
                    s.close()

                status_msg = f"Hunting direct IP {target_ip}:5555"
                self._safe_after(0, lambda m=status_msg: self.lbl_hunt_status.configure(text=m))

                if port_open:
                    self._on_stb_caught(target_ip)
                    break
                time.sleep(1.0)
            else:
                prefix = ".".join(target_ip.split(".")[:3]) + "."
                ips = [f"{prefix}{i}" for i in range(1, 255)]
                
                status_msg = f"Radar sweep on {prefix}0/24 subnet"
                self._safe_after(0, lambda m=status_msg: self.lbl_hunt_status.configure(text=m))

                found_ip = None
                def check_single(ip):
                    if not self.is_hunting:
                        return None
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(0.3)
                    try:
                        if s.connect_ex((ip, DEFAULT_ADB_PORT)) == 0:
                            return ip
                    except Exception:
                        pass
                    finally:
                        s.close()
                    return None

                with concurrent.futures.ThreadPoolExecutor(max_workers=50) as ex:
                    for res in ex.map(check_single, ips):
                        if res:
                            found_ip = res
                            break

                if found_ip:
                    self._on_stb_caught(found_ip)
                    break
                time.sleep(1.2)

    def _on_stb_caught(self, caught_ip):
        self.is_hunting = False
        self._safe_after(0, lambda: self.btn_hunt_toggle.configure(text="Start STB Hunter", fg_color=self.M3_TERTIARY_CONTAINER, text_color=self.M3_TERTIARY))
        self._safe_after(0, lambda: self.hunt_swirl.stop())
        self._safe_after(0, lambda: self.hunt_swirl.pack_forget())
        self._safe_after(0, lambda: self.hunter_scope.set_caught())
        
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

        self.adb.log(f"STB Caught on {caught_ip}!", "SUCCESS")
        self._safe_after(0, lambda: self.entry_ip.delete(0, "end"))
        self._safe_after(0, lambda: self.entry_ip.insert(0, caught_ip))

        connected = self.adb.connect(caught_ip)
        self._safe_after(0, lambda: self._update_connection_ui(connected, caught_ip))

        def show_caught():
            self.lbl_caught_title.configure(text=f"STB Hooked & Connected [{caught_ip}:5555]")
            self.lbl_caught_detail.configure(text="ADB port 5555 is live. Handshake verified. Exploit successfully survived reboot.")
            self.caught_card.pack(fill="x", pady=10, padx=4)
        self._safe_after(0, show_caught)

        if self.var_auto_activate.get() and connected:
            self.adb.log("Applying post-exploit essential fixes...", "INFO")
            self._run_all_fixes()

    # ---------------------------------------------------------
    # 1-Click Fixes Execution
    # ---------------------------------------------------------
    def _run_all_fixes(self):
        def work():
            self.after(0, lambda: self.fixes_task_banner.show_task("Executing 1-Click Essential Fixes", "Starting ADB automation pipeline..."))
            self.after(0, lambda: self.set_global_busy(True))
            self.adb.log("Applying all essential fixes...", "INFO")
            
            self.after(0, lambda: self.fixes_task_banner.update_step("1/4: Unblocking Bluetooth accessories & TV pairing..."))
            self._fix_bluetooth_sync()
            time.sleep(0.4)

            self.after(0, lambda: self.fixes_task_banner.update_step("2/4: Binding voice search microphone & intents..."))
            self._fix_mic_sync()
            time.sleep(0.4)

            self.after(0, lambda: self.fixes_task_banner.update_step("3/4: Synchronizing system clock & network DNS..."))
            self._fix_network_sync()
            time.sleep(0.4)

            self.after(0, lambda: self.fixes_task_banner.update_step("4/4: Deploying kernel shortcut remap listener..."))
            self._deploy_remap_daemon_sync()

            self.adb.log("All fixes applied successfully", "SUCCESS")
            self.after(0, lambda: self.fixes_task_banner.set_success("All Essential Fixes Applied Successfully", "Accessories unblocked, microphone bound, and remap daemon running."))
            self.after(0, lambda: self.set_global_busy(False))
        threading.Thread(target=work, daemon=True).start()

    def _fix_bluetooth_sync(self):
        self.adb.log("Disabling Bluetooth pairing blocker (com.jio.remote.btserver)...", "INFO")
        self.adb.run_cmd(["shell", "pm disable-user --user 0 com.jio.remote.btserver >/dev/null 2>&1"])
        self.adb.run_cmd(["shell", "svc bluetooth disable && sleep 1 && svc bluetooth enable >/dev/null 2>&1"])
        self.adb.run_cmd(["shell", "am start -n com.android.tv.settings/.accessories.AddAccessoryActivity >/dev/null 2>&1"])
        self.adb.log("Bluetooth accessories unblocked", "SUCCESS")

    def _fix_bluetooth(self):
        threading.Thread(target=self._fix_bluetooth_sync, daemon=True).start()

    def _fix_mic_sync(self):
        self.adb.log("Binding voice search assistant intent...", "INFO")
        self.adb.run_cmd(["shell", "settings put secure assistant com.android.app.jio.voiceassist/.search.modified.ui.MainActivity"])
        self.adb.run_cmd(["shell", "pm grant com.jio.yt android.permission.RECORD_AUDIO 2>/dev/null"])
        self.adb.run_cmd(["shell", "pm grant io.gh.reisxd.tizentube.cobalt android.permission.RECORD_AUDIO 2>/dev/null"])
        self.adb.log("Voice search microphone fixed", "SUCCESS")

    def _fix_mic(self):
        threading.Thread(target=self._fix_mic_sync, daemon=True).start()

    def _fix_network_sync(self):
        now_ts = int(time.time())
        self.adb.log(f"Syncing clock to PC epoch ({now_ts})...", "INFO")
        self.adb.run_cmd(["shell", f"date @{now_ts} >/dev/null 2>&1"])
        self.adb.run_cmd(["shell", "settings put global captive_portal_mode 0"])
        self.adb.run_cmd(["shell", "settings put global private_dns_mode off"])
        self.adb.run_cmd(["shell", "settings put global ntp_server time.google.com"])
        self.adb.log("Network and clock synchronized", "SUCCESS")

    def _fix_network(self):
        threading.Thread(target=self._fix_network_sync, daemon=True).start()

    def _fix_cert(self):
        def work():
            script_path = os.path.join(BASE_DIR, "src", "jhs_certificate.py")
            if os.path.exists(script_path):
                self.adb.log("Applying JHS certificate patch...", "INFO")
                subprocess.run([sys.executable, script_path], capture_output=True)
                self.adb.log("JHS certificate patched", "SUCCESS")
            else:
                self.adb.log("JHS certificate script not found", "WARN")
        threading.Thread(target=work, daemon=True).start()

    def _start_shizuku(self):
        def work():
            self.adb.log("Starting Shizuku server...", "INFO")
            starter_local = os.path.join(BASE_DIR, "shizuku_starter")
            if os.path.exists(starter_local):
                self.adb.run_cmd(["push", starter_local, "/data/local/tmp/shizuku_starter"])
            self.adb.run_cmd(["shell", "chmod 755 /data/local/tmp/shizuku_starter && /data/local/tmp/shizuku_starter &"])
            self.adb.log("Shizuku server started", "SUCCESS")
        threading.Thread(target=work, daemon=True).start()

    def _open_tv_settings(self):
        def work():
            self.adb.log("Opening Android TV Settings on screen...", "INFO")
            self.adb.run_cmd(["shell", "am start -n com.android.tv.settings/.MainSettings"])
        threading.Thread(target=work, daemon=True).start()

    # ---------------------------------------------------------
    # Performance & RAM Tuners
    # ---------------------------------------------------------
    def _refresh_ram_meter(self):
        def work():
            _, out, _ = self.adb.run_cmd(["shell", "cat /proc/meminfo | grep -E 'MemTotal|MemFree|MemAvailable'"])
            total, free, avail = 0, 0, 0
            for line in out.splitlines():
                if "MemTotal" in line:
                    total = int(line.split()[1])
                elif "MemFree" in line:
                    free = int(line.split()[1])
                elif "MemAvailable" in line:
                    avail = int(line.split()[1])

            if total > 0:
                used = total - avail
                pct = used / total
                tot_mb = total / 1024
                used_mb = used / 1024
                avail_mb = avail / 1024

                self.after(0, lambda: self.ram_gauge.set_pct(pct))
                self.after(0, lambda: self.stat_used.configure(text=f"Used RAM: {used_mb:.0f} MB ({pct*100:.0f}%)"))
                self.after(0, lambda: self.stat_avail.configure(text=f"Available RAM: {avail_mb:.0f} MB"))
                self.after(0, lambda: self.stat_total.configure(text=f"Total Physical Memory: {tot_mb:.0f} MB"))
        threading.Thread(target=work, daemon=True).start()

    def _purge_ram(self):
        def work():
            self.after(0, lambda: self.set_global_busy(True))
            self.adb.log("Compacting memory and purging pagecache...", "INFO")
            self.adb.run_cmd(["shell", "echo 1 > /proc/sys/vm/compact_memory 2>/dev/null || true"])
            self.adb.run_cmd(["shell", "echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true"])
            self.adb.log("RAM compacted and purged", "SUCCESS")
            time.sleep(0.8)
            self._refresh_ram_meter()
            self.after(0, lambda: self.set_global_busy(False))
        threading.Thread(target=work, daemon=True).start()

    def _apply_anim_speed(self):
        val = self.seg_anim.get()
        scale = "0.5"
        if "0.0x" in val:
            scale = "0.0"
        elif "1.0x" in val:
            scale = "1.0"
        
        def work():
            self.adb.log(f"Setting UI animation scale to {scale}x...", "INFO")
            self.adb.run_cmd(["shell", f"settings put global window_animation_scale {scale}"])
            self.adb.run_cmd(["shell", f"settings put global transition_animation_scale {scale}"])
            self.adb.run_cmd(["shell", f"settings put global animator_duration_scale {scale}"])
            self.adb.log(f"Animation scale set to {scale}x", "SUCCESS")
        threading.Thread(target=work, daemon=True).start()

    def _apply_proc_limit(self):
        val = self.seg_proc.get()
        limit = "10"
        if "32" in val:
            limit = "32"
        elif "8" in val:
            limit = "8"
        elif "4" in val:
            limit = "4"

        def work():
            self.adb.log(f"Setting cached processes limit to {limit}...", "INFO")
            self.adb.run_cmd(["shell", f"cmd device_config put activity_manager max_cached_processes {limit}"])
            self.adb.run_cmd(["shell", "cmd device_config put activity_manager max_empty_processes 5"])
            self.adb.run_cmd(["shell", "cmd device_config put activity_manager use_compaction true"])
            self.adb.log(f"Cached processes limit set to {limit}", "SUCCESS")
        threading.Thread(target=work, daemon=True).start()

    def _disable_bloatware(self):
        def work():
            bloat = [
                "com.jio.cloudlogger",
                "com.jio.media.stbinfo",
                "com.jio.telemetry",
                "com.jio.remote.btserver",
                "com.jio.ads.interstitial",
                "com.jio.voiceassist",
                "com.jio.jiostore"
            ]
            self.adb.log("Disabling background telemetry...", "INFO")
            for pkg in bloat:
                self.adb.run_cmd(["shell", f"pm disable-user --user 0 {pkg} >/dev/null 2>&1 && am force-stop {pkg} >/dev/null 2>&1"])
            self.adb.log("Telemetry services disabled", "SUCCESS")
        threading.Thread(target=work, daemon=True).start()

    def _restore_bloatware(self):
        def work():
            bloat = [
                "com.jio.cloudlogger",
                "com.jio.media.stbinfo",
                "com.jio.telemetry",
                "com.jio.ads.interstitial",
                "com.jio.voiceassist",
                "com.jio.jiostore"
            ]
            self.adb.log("Restoring stock packages...", "INFO")
            for pkg in bloat:
                self.adb.run_cmd(["shell", f"pm enable {pkg} >/dev/null 2>&1"])
            self.adb.log("Stock packages restored", "INFO")
        threading.Thread(target=work, daemon=True).start()

    # ---------------------------------------------------------
    # Remote Remapper View & Deployment
    # ---------------------------------------------------------
    def _reload_remap_view(self):
        def work():
            _, ps_out, _ = self.adb.run_cmd(["shell", "ps -ef | grep -E 'getevent|remap_listener' | grep -v grep"])
            is_daemon_up = "remap_listener.sh" in ps_out or "getevent" in ps_out
            
            def update_badge():
                if is_daemon_up:
                    self.lbl_daemon_badge.configure(text="● Daemon: Running", text_color=self.M3_SUCCESS, fg_color=self.M3_SUCCESS_CONTAINER)
                else:
                    self.lbl_daemon_badge.configure(text="● Daemon: Stopped", text_color=self.M3_ERROR, fg_color=self.M3_ERROR_CONTAINER)
            self._safe_after(0, update_badge)

            _, user_pkgs, _ = self.adb.run_cmd(["shell", "pm list packages -3"])
            _, sys_pkgs, _ = self.adb.run_cmd(["shell", "pm list packages -s"])

            apps = []
            seen = set()
            for line in user_pkgs.splitlines():
                pkg = line.replace("package:", "").strip()
                if pkg and pkg not in seen:
                    label = KNOWN_NAMES.get(pkg, pkg)
                    apps.append((f"{label} [{pkg}]", pkg))
                    seen.add(pkg)

            for spkg in ['in.startv.hotstar', 'com.viacom18.tv.voot', 'com.amazon.amazonvideo.livingroom', 'com.jiotv.sonyliv', 'com.zee5.aosp']:
                if spkg in sys_pkgs and spkg not in seen:
                    label = KNOWN_NAMES.get(spkg, spkg)
                    apps.append((f"{label} [{spkg}]", spkg))
                    seen.add(spkg)

            self.installed_apps = apps
            combo_values = [a[0] for a in apps] if apps else ["app.netmirror.newtv", "io.gh.reisxd.tizentube.cobalt"]

            _, cfg_out, _ = self.adb.run_cmd(["shell", "cat /data/local/tmp/remap_config.conf 2>/dev/null"])
            curr_map = {
                "NETFLIX_PKG": "app.netmirror.newtv",
                "YOUTUBE_PKG": "io.gh.reisxd.tizentube.cobalt",
                "HOTSTAR_PKG": "in.startv.hotstar",
                "VOOT_PKG": "com.viacom18.tv.voot"
            }
            for line in cfg_out.splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    curr_map[k.strip()] = v.strip()

            def update_combos():
                for k, combo in self.remap_combos.items():
                    combo.configure(values=combo_values)
                    target_pkg = curr_map.get(k, "")
                    matched = False
                    for val, pkg in self.installed_apps:
                        if pkg == target_pkg:
                            combo.set(val)
                            matched = True
                            break
                    if not matched:
                        combo.set(target_pkg)
            self._safe_after(0, update_combos)

        threading.Thread(target=work, daemon=True).start()

    def _test_launch_mapped_app(self, key_name):
        combo_val = self.remap_combos[key_name].get().strip()
        pkg = combo_val
        if "[" in combo_val and combo_val.endswith("]"):
            pkg = combo_val.split("[")[-1].replace("]", "").strip()

        def work():
            self.adb.log(f"Launching {pkg} on TV...", "INFO")
            _, act_out, _ = self.adb.run_cmd(["shell", f"cmd package resolve-activity --brief {pkg} 2>/dev/null"])
            act = ""
            for l in act_out.splitlines():
                if "/" in l and not l.startswith("priority"):
                    act = l.strip()
                    break

            if act:
                self.adb.run_cmd(["shell", f"am start -n {act}"])
            else:
                self.adb.run_cmd(["shell", f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1 2>/dev/null"])
            self.adb.log(f"Launched {pkg}", "SUCCESS")
        threading.Thread(target=work, daemon=True).start()

    def _save_and_deploy_remap(self):
        new_config = {}
        for k, combo in self.remap_combos.items():
            val = combo.get().strip()
            pkg = val
            if "[" in val and val.endswith("]"):
                pkg = val.split("[")[-1].replace("]", "").strip()
            new_config[k] = pkg

        def work():
            self.after(0, lambda: self.remap_task_banner.show_task("Deploying Remote Button Remap", "Writing configuration to /data/local/tmp/remap_config.conf..."))
            self.after(0, lambda: self.set_global_busy(True))
            self.adb.log("Updating remote button mapping on STB...", "INFO")
            lines = [
                "# Jio Remote Shortcut Button Remap Configuration",
                f"NETFLIX_PKG={new_config.get('NETFLIX_PKG', 'app.netmirror.newtv')}",
                f"YOUTUBE_PKG={new_config.get('YOUTUBE_PKG', 'io.gh.reisxd.tizentube.cobalt')}",
                f"HOTSTAR_PKG={new_config.get('HOTSTAR_PKG', 'in.startv.hotstar')}",
                f"VOOT_PKG={new_config.get('VOOT_PKG', 'com.viacom18.tv.voot')}"
            ]
            content = "\\n".join(lines)
            self.adb.run_cmd(["shell", f'printf "{content}\\n" > /data/local/tmp/remap_config.conf'])

            self.after(0, lambda: self.remap_task_banner.update_step("Disabling stock hijack packages (Netflix/Jio YT)..."))
            self.adb.run_cmd(["shell", "pm disable-user --user 0 com.netflix.ninja 2>/dev/null || true"])
            self.adb.run_cmd(["shell", "pm disable-user --user 0 com.jio.yt 2>/dev/null || true"])

            self.after(0, lambda: self.remap_task_banner.update_step("Binding kernel event listener on /dev/input/event5..."))
            local_sh = os.path.join(BASE_DIR, "remap_listener.sh")
            if os.path.exists(local_sh):
                self.adb.run_cmd(["push", local_sh, "/data/local/tmp/remap_listener.sh"])
                self.adb.run_cmd(["shell", "chmod 755 /data/local/tmp/remap_listener.sh"])

            self.adb.run_cmd(["shell", "killall getevent 2>/dev/null; setsid sh /data/local/tmp/remap_listener.sh >/dev/null 2>&1 &"])
            time.sleep(0.8)
            self.adb.log("Button mapping applied & daemon reloaded", "SUCCESS")
            self.after(0, lambda: self.remap_task_banner.set_success("Remote Button Remap Deployed", "Kernel hooks verified on /dev/input/event5. Shortcuts ready."))
            self.after(0, lambda: self.set_global_busy(False))
            self._reload_remap_view()
        threading.Thread(target=work, daemon=True).start()

    def _deploy_remap_daemon_sync(self):
        local_sh = os.path.join(BASE_DIR, "remap_listener.sh")
        local_conf = os.path.join(BASE_DIR, "remap_config.conf")
        if os.path.exists(local_sh):
            self.adb.run_cmd(["push", local_sh, "/data/local/tmp/remap_listener.sh"])
            self.adb.run_cmd(["shell", "chmod 755 /data/local/tmp/remap_listener.sh"])
        if os.path.exists(local_conf):
            self.adb.run_cmd(["push", local_conf, "/data/local/tmp/remap_config.conf"])
        self.adb.run_cmd(["shell", "pm disable-user --user 0 com.netflix.ninja 2>/dev/null || true"])
        self.adb.run_cmd(["shell", "pm disable-user --user 0 com.jio.yt 2>/dev/null || true"])
        self.adb.run_cmd(["shell", "killall getevent 2>/dev/null; setsid sh /data/local/tmp/remap_listener.sh >/dev/null 2>&1 &"])
        self.adb.log("Remote button listener active", "SUCCESS")

    # ---------------------------------------------------------
    # APK Sideload & Global Permissions
    # ---------------------------------------------------------
    def _install_batch_apks(self):
        apks_dir = os.path.join(BASE_DIR, "apks")
        if not os.path.exists(apks_dir):
            os.makedirs(apks_dir, exist_ok=True)

        apk_files = glob.glob(os.path.join(apks_dir, "*.apk"))
        if not apk_files:
            self.adb.log(f"No APK files in {apks_dir}", "WARN")
            return

        def work():
            self.after(0, lambda: self.apk_task_banner.show_task("Silent Batch APK Sideload", f"Preparing {len(apk_files)} packages..."))
            self.after(0, lambda: self.set_global_busy(True))
            self.adb.log(f"Installing {len(apk_files)} APKs...", "INFO")
            success = 0
            for i, apk in enumerate(apk_files, 1):
                name = os.path.basename(apk)
                size_mb = os.path.getsize(apk) / (1024 * 1024)
                self.after(0, lambda n=name, idx=i: self.apk_task_banner.update_step(f"Installing {idx}/{len(apk_files)}: {n} ({size_mb:.1f} MB)..."))
                self.adb.log(f"[{i}/{len(apk_files)}] Installing {name} ({size_mb:.1f} MB)...", "INFO")
                ok, out, _ = self.adb.run_cmd(["install", "-r", "-g", apk], timeout=120)
                if "Success" in out:
                    self.adb.log(f"Installed {name}", "SUCCESS")
                    success += 1
                else:
                    self.adb.log(f"Failed {name}: {out[:100]}", "ERR")
            self.adb.log(f"Batch install finished ({success}/{len(apk_files)})", "SUCCESS")
            self.after(0, lambda: self.apk_task_banner.update_step("Auto-granting storage, mic and Unknown Sources..."))
            self._grant_all_permissions_sync()
            self.after(0, lambda: self.apk_task_banner.set_success("Batch Sideload Finished", f"Successfully installed {success}/{len(apk_files)} applications."))
            self.after(0, lambda: self.set_global_busy(False))
            self._refresh_installed_apps_tab()
        threading.Thread(target=work, daemon=True).start()

    def _open_apks_folder(self):
        apks_dir = os.path.join(BASE_DIR, "apks")
        os.makedirs(apks_dir, exist_ok=True)
        if os.name == 'nt':
            os.startfile(apks_dir)

    def _browse_single_apk(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(filetypes=[("Android Package", "*.apk")])
        if path:
            self.entry_single_apk.delete(0, "end")
            self.entry_single_apk.insert(0, path)

    def _install_single_apk(self):
        apk_path = self.entry_single_apk.get().strip()
        if not apk_path or not os.path.exists(apk_path):
            self.adb.log("Select a valid .apk file", "WARN")
            return

        def work():
            name = os.path.basename(apk_path)
            self.adb.log(f"Installing {name}...", "INFO")
            ok, out, _ = self.adb.run_cmd(["install", "-r", "-g", apk_path], timeout=120)
            if "Success" in out:
                self.adb.log(f"Installed {name}", "SUCCESS")
                self._grant_all_permissions_sync()
                self._refresh_installed_apps_tab()
            else:
                self.adb.log(f"Install failed: {out}", "ERR")
        threading.Thread(target=work, daemon=True).start()

    def _grant_all_permissions(self):
        threading.Thread(target=self._grant_all_permissions_sync, daemon=True).start()

    def _grant_all_permissions_sync(self):
        self.adb.log("Auto-granting storage, audio, alert window and Unknown Sources...", "INFO")
        perm_script = (
            "for pkg in $(pm list packages -3 | tr -d '\\r' | sed 's/^package://') com.jio.yt; do "
            "pm grant $pkg android.permission.RECORD_AUDIO 2>/dev/null; "
            "pm grant $pkg android.permission.READ_EXTERNAL_STORAGE 2>/dev/null; "
            "pm grant $pkg android.permission.WRITE_EXTERNAL_STORAGE 2>/dev/null; "
            "pm grant $pkg android.permission.ACCESS_FINE_LOCATION 2>/dev/null; "
            "pm grant $pkg android.permission.ACCESS_COARSE_LOCATION 2>/dev/null; "
            "appops set $pkg MANAGE_EXTERNAL_STORAGE allow 2>/dev/null; "
            "appops set $pkg REQUEST_INSTALL_PACKAGES allow 2>/dev/null; "
            "appops set $pkg SYSTEM_ALERT_WINDOW allow 2>/dev/null; "
            "done"
        )
        self.adb.run_cmd(["shell", f'sh -c "{perm_script}"'])
        self.adb.log("Permissions and Unknown Sources granted", "SUCCESS")

# -------------------------------------------------------------
# Application Entry Point
# -------------------------------------------------------------
JioDatsugokuApp = JioToolboxApp

def main():
    app = JioDatsugokuApp()
    app.mainloop()

if __name__ == "__main__":
    main()

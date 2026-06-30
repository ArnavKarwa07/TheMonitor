"""Graphical User Interface for Monitor."""

import logging
import os
import sys
import time
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageTk

from themonitor.config import load_config, save_config, MonitorConfig
from themonitor.daemon import is_daemon_running, read_pid
from themonitor.posture.mediapipe_engine import MediaPipeEngine
from themonitor.posture.rules import PostureRules, PostureScore, Landmark, SCORE_SEVERITY
from themonitor.startup.launcher import get_desktop_path

logger = logging.getLogger(__name__)

# Colors - Catppuccin Mocha themed dark palette
BG_DARK = "#1e1e2e"
BG_SIDEBAR = "#181825"
BG_CARD = "#313244"
BG_INPUT = "#45475a"
FG_LIGHT = "#cdd6f4"
FG_MUTED = "#a6adc8"
ACCENT_BLUE = "#89b4fa"
ACCENT_BLUE_HOVER = "#b4befe"
ACCENT_GREEN = "#a6e3a1"
ACCENT_RED = "#f38ba8"
ACCENT_RED_HOVER = "#f38ba8"
ACCENT_YELLOW = "#f9e2af"
ACCENT_GRAY = "#585b70"


class MonitorGUI(tk.Tk):
    """The main Monitor GUI application."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Monitor - Posture & Habits Assistant")
        self.geometry("980x680")
        self.configure(bg=BG_DARK)

        # Force dark style mapping for options/dialogs if possible
        self.option_add("*Font", ("Segoe UI", 10))
        
        # Load configuration
        self.config_file_path = None
        self.config = load_config()

        # State variables
        self.preview_active = False
        self.preview_state = "inactive"
        self.editing_habits = False
        self.editing_settings = False
        self.cap: Optional[cv2.VideoCapture] = None
        self.mp_engine: Optional[MediaPipeEngine] = None
        self.rules: Optional[PostureRules] = None
        self.current_score: PostureScore = PostureScore.GOOD
        self.pose_detected = False
        self.preview_canvas: Optional[tk.Canvas] = None

        # Load logo images
        self.logo_img_40 = None
        self.logo_tk_40 = None
        self.logo_img_120 = None
        self.logo_tk_120 = None
        self.logo_icon_img = None
        logo_path = Path(__file__).resolve().parent.parent / "logo.png"
        
        # Load and set window icon
        try:
            if not logo_path.exists():
                raise FileNotFoundError(f"Logo file not found: {logo_path}")
            icon_pil = Image.open(logo_path)
            self.logo_icon_img = ImageTk.PhotoImage(icon_pil)
            self.iconphoto(False, self.logo_icon_img)
        except Exception as e:
            logger.error(f"Failed to set window icon: {e}")

        if logo_path.exists():
            try:
                img = Image.open(logo_path)
                self.logo_img_40 = img.resize((40, 40), Image.Resampling.LANCZOS)
                self.logo_tk_40 = ImageTk.PhotoImage(self.logo_img_40)
                
                self.logo_img_120 = img.resize((120, 120), Image.Resampling.LANCZOS)
                self.logo_tk_120 = ImageTk.PhotoImage(self.logo_img_120)
            except Exception as e:
                logger.error(f"Failed to load logo images: {e}")

        # Optimization states
        self.frame_count = 0
        self.last_landmarks = None
        self.last_score = PostureScore.GOOD
        self.last_details = {}

        # Build UI layout
        self._create_layout()
        
        # Select first tab
        self.select_tab("dashboard")

        # Start background check for daemon status
        self.update_daemon_status_loop()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _create_layout(self) -> None:
        """Create the sidebar and main content panels."""
        # Sidebar Frame
        self.sidebar = tk.Frame(self, bg=BG_SIDEBAR, width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # App title with logo above text
        title_frame = tk.Frame(self.sidebar, bg=BG_SIDEBAR, padx=20, pady=15)
        title_frame.pack(fill="x")

        # Row with logo and title side-by-side
        title_row = tk.Frame(title_frame, bg=BG_SIDEBAR)
        title_row.pack(fill="x")

        if self.logo_tk_40:
            logo_img_label = tk.Label(title_row, image=self.logo_tk_40, bg=BG_SIDEBAR)
            logo_img_label.image = self.logo_tk_40  # Keep reference
            logo_img_label.pack(side="left", padx=(0, 8))

        logo_label = tk.Label(
            title_row,
            text="MONITOR",
            font=("Segoe UI", 18, "bold"),
            bg=BG_SIDEBAR,
            fg=ACCENT_GREEN,
            anchor="w"
        )
        logo_label.pack(side="left", fill="x")

        sub_label = tk.Label(
            self.sidebar,
            text="Posture & Wellness",
            font=("Segoe UI", 9, "italic"),
            bg=BG_SIDEBAR,
            fg=FG_MUTED,
            anchor="w",
            padx=20,
            pady=0
        )
        sub_label.pack(fill="x")

        tk.Frame(self.sidebar, height=20, bg=BG_SIDEBAR).pack() # spacer

        # Sidebar Buttons
        self.nav_buttons = {}
        for tab_name, label in [
            ("dashboard", "Dashboard"),
            ("habits", "Wellness Habits"),
            ("settings", "Configurations")
        ]:
            btn = tk.Button(
                self.sidebar,
                text=label,
                font=("Segoe UI", 11, "bold"),
                bg=BG_SIDEBAR,
                fg=FG_LIGHT,
                activebackground=BG_CARD,
                activeforeground=FG_LIGHT,
                relief="flat",
                bd=0,
                anchor="w",
                padx=20,
                pady=12,
                cursor="hand2",
                command=lambda t=tab_name: self.select_tab(t)
            )
            btn.pack(fill="x")
            # Hover effects
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=BG_CARD))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=BG_SIDEBAR))
            self.nav_buttons[tab_name] = btn

        # Footer in sidebar
        footer_label = tk.Label(
            self.sidebar,
            text="Local Vision AI v0.1.0",
            font=("Segoe UI", 8),
            bg=BG_SIDEBAR,
            fg=ACCENT_GRAY,
            pady=15
        )
        footer_label.pack(side="bottom", fill="x")

        # Divider between sidebar and content
        divider = tk.Frame(self, bg=BG_CARD, width=2)
        divider.pack(side="left", fill="y")

        # Main Content Frame
        self.content_frame = tk.Frame(self, bg=BG_DARK, padx=25, pady=20)
        self.content_frame.pack(side="right", fill="both", expand=True)

    def select_tab(self, tab_name: str) -> None:
        """Switch view to the selected tab."""
        # Stop preview if active
        if self.preview_active:
            self.toggle_preview()

        # Reset navigation button backgrounds
        for name, btn in self.nav_buttons.items():
            btn.configure(fg=FG_LIGHT)
            # Rebind hover leave
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=BG_SIDEBAR))
            btn.configure(bg=BG_SIDEBAR)

        # Highlight active button
        active_btn = self.nav_buttons[tab_name]
        active_btn.configure(bg=BG_CARD, fg=ACCENT_BLUE)
        active_btn.bind("<Leave>", lambda e, b=active_btn: b.configure(bg=BG_CARD))

        # Reset editing states
        self.editing_habits = False
        self.editing_settings = False

        # Clear current content
        for child in self.content_frame.winfo_children():
            child.destroy()

        # Draw content based on tab
        if tab_name == "dashboard":
            self._draw_dashboard()
        elif tab_name == "habits":
            self._draw_habits()
        elif tab_name == "settings":
            self._draw_settings()

    # -----------------------------------------------------------------------
    # VIEW: Dashboard
    # -----------------------------------------------------------------------
    def _draw_dashboard(self) -> None:
        # Title
        title = tk.Label(
            self.content_frame,
            text="Dashboard",
            font=("Segoe UI", 18, "bold"),
            bg=BG_DARK,
            fg=FG_LIGHT
        )
        title.pack(anchor="w", pady=(0, 15))

        # Split dashboard into two columns
        col_frame = tk.Frame(self.content_frame, bg=BG_DARK)
        col_frame.pack(fill="both", expand=True)

        left_col = tk.Frame(col_frame, bg=BG_DARK, width=320)
        left_col.pack(side="left", fill="both", pady=5)
        left_col.pack_propagate(False)

        right_col = tk.Frame(col_frame, bg=BG_DARK)
        right_col.pack(side="right", fill="both", expand=True, padx=(20, 0), pady=5)

        # --- LEFT COLUMN: Daemon Status & Control ---
        status_card = tk.LabelFrame(
            left_col,
            text="Background Service",
            font=("Segoe UI", 11, "bold"),
            bg=BG_CARD,
            fg=FG_LIGHT,
            bd=1,
            padx=15,
            pady=15
        )
        status_card.pack(fill="x", pady=(0, 15))

        self.daemon_status_lbl = tk.Label(
            status_card,
            text="Checking status...",
            font=("Segoe UI", 12, "bold"),
            bg=BG_CARD,
            fg=FG_MUTED,
            anchor="w"
        )
        self.daemon_status_lbl.pack(fill="x", pady=(0, 15))

        self.daemon_btn = tk.Button(
            status_card,
            text="Start Daemon",
            font=("Segoe UI", 11, "bold"),
            bg=ACCENT_GRAY,
            fg=BG_DARK,
            activebackground=FG_LIGHT,
            relief="flat",
            bd=0,
            pady=8,
            cursor="hand2",
            command=self.toggle_daemon
        )
        self.daemon_btn.pack(fill="x", pady=(0, 10))

        # Shortcut Button Status Check
        desktop_path = get_desktop_path()
        shortcut_file = desktop_path / "Monitor GUI.lnk"
        
        if shortcut_file.exists():
            shortcut_btn = tk.Button(
                status_card,
                text="Shortcut Installed",
                font=("Segoe UI", 9, "bold"),
                bg=ACCENT_GRAY,
                fg=FG_MUTED,
                relief="flat",
                bd=0,
                pady=6,
                state="disabled"
            )
        else:
            shortcut_btn = tk.Button(
                status_card,
                text="Create Desktop Shortcut",
                font=("Segoe UI", 9, "bold"),
                bg=BG_INPUT,
                fg=FG_LIGHT,
                activebackground=BG_CARD,
                relief="flat",
                bd=0,
                pady=6,
                cursor="hand2",
                command=self.create_shortcut_action
            )
            shortcut_btn.bind("<Enter>", lambda e, b=shortcut_btn: b.configure(bg=BG_CARD))
            shortcut_btn.bind("<Leave>", lambda e, b=shortcut_btn: b.configure(bg=BG_INPUT))
        shortcut_btn.pack(fill="x")

        # Calibration Info Card
        cal_card = tk.LabelFrame(
            left_col,
            text="Instructions",
            font=("Segoe UI", 11, "bold"),
            bg=BG_CARD,
            fg=FG_LIGHT,
            bd=1,
            padx=15,
            pady=15
        )
        cal_card.pack(fill="both", expand=True)

        instr_text = (
            "1. Click 'Start Live Preview' to see yourself.\n\n"
            "2. Make sure your face and shoulders are fully visible in the frame.\n\n"
            "3. Align your screen so the spine is straight and shoulders are level.\n\n"
            "4. The skeleton lines will show green when posture is GOOD.\n\n"
            "5. Once calibrated, close the preview and click 'Start Daemon' to run silently in the background."
        )
        instr_lbl = tk.Label(
            cal_card,
            text=instr_text,
            font=("Segoe UI", 10),
            bg=BG_CARD,
            fg=FG_MUTED,
            justify="left",
            wraplength=260,
            anchor="nw"
        )
        instr_lbl.pack(fill="both", expand=True)

        # --- RIGHT COLUMN: Camera Preview ---
        preview_card = tk.LabelFrame(
            right_col,
            text="Calibration Preview",
            font=("Segoe UI", 11, "bold"),
            bg=BG_CARD,
            fg=FG_LIGHT,
            bd=1,
            padx=10,
            pady=10
        )
        preview_card.pack(fill="both", expand=True)

        # Webcam frame Canvas
        self.preview_canvas = tk.Canvas(
            preview_card,
            bg=BG_DARK,
            width=480,
            height=360,
            bd=0,
            highlightthickness=0
        )
        self.preview_canvas.pack(fill="both", expand=True, pady=(0, 10))
        
        # Render current state on Canvas
        self.draw_canvas_for_state()

        # Posture Status Indicator below canvas
        self.posture_status_frame = tk.Frame(preview_card, bg=BG_DARK, pady=8)
        self.posture_status_frame.pack(fill="x", pady=(0, 10))

        if self.preview_state == "inactive":
            lbl_text = "PREVIEW INACTIVE"
            lbl_fg = FG_MUTED
        elif self.preview_state == "loading":
            lbl_text = "CONNECTING..."
            lbl_fg = ACCENT_YELLOW
        elif self.preview_state == "error":
            lbl_text = "CAMERA ERROR"
            lbl_fg = ACCENT_RED
        else:
            if not self.pose_detected:
                lbl_text = "NO POSE DETECTED"
                lbl_fg = ACCENT_GRAY
            elif self.current_score == PostureScore.GOOD:
                lbl_text = "POSTURE: GOOD"
                lbl_fg = ACCENT_GREEN
            elif self.current_score == PostureScore.FAIR:
                lbl_text = "POSTURE: FAIR (UNALIGNED)"
                lbl_fg = ACCENT_YELLOW
            else:
                lbl_text = "POSTURE: BAD (SLOUCHING)"
                lbl_fg = ACCENT_RED

        self.posture_status_lbl = tk.Label(
            self.posture_status_frame,
            text=lbl_text,
            font=("Segoe UI", 14, "bold"),
            bg=BG_DARK,
            fg=lbl_fg
        )
        self.posture_status_lbl.pack()

        # Preview Control Button
        self.preview_btn = tk.Button(
            preview_card,
            text="Stop Live Preview" if self.preview_active else "Start Live Preview",
            font=("Segoe UI", 11, "bold"),
            bg=ACCENT_RED if self.preview_active else ACCENT_BLUE,
            fg=BG_DARK,
            activebackground=ACCENT_RED_HOVER if self.preview_active else ACCENT_BLUE_HOVER,
            relief="flat",
            bd=0,
            pady=8,
            cursor="hand2",
            command=self.toggle_preview
        )
        self.preview_btn.pack(fill="x")
        self.preview_btn.bind("<Enter>", lambda e, b=self.preview_btn: b.configure(bg=ACCENT_RED_HOVER if self.preview_active else ACCENT_BLUE_HOVER))
        self.preview_btn.bind("<Leave>", lambda e, b=self.preview_btn: b.configure(bg=ACCENT_RED if self.preview_active else ACCENT_BLUE))

    # -----------------------------------------------------------------------
    # VIEW: Habits Settings
    # -----------------------------------------------------------------------
    def _draw_habits(self) -> None:
        title = tk.Label(
            self.content_frame,
            text="Wellness Habits Configuration",
            font=("Segoe UI", 18, "bold"),
            bg=BG_DARK,
            fg=FG_LIGHT
        )
        title.pack(anchor="w", pady=(0, 15))

        # Main scrollable card
        scroll_card = tk.LabelFrame(
            self.content_frame,
            text="Active Habits & Reminders",
            font=("Segoe UI", 11, "bold"),
            bg=BG_CARD,
            fg=FG_LIGHT,
            bd=1,
            padx=20,
            pady=20
        )
        scroll_card.pack(fill="both", expand=True)

        # State Variables for Entry values
        self.habit_vars = {
            "water_enabled": tk.BooleanVar(value=self.config.habits.water.enabled),
            "water_interval": tk.StringVar(value=str(self.config.habits.water.interval_minutes)),
            "stretch_enabled": tk.BooleanVar(value=self.config.habits.stretch.enabled),
            "stretch_interval": tk.StringVar(value=str(self.config.habits.stretch.interval_minutes)),
            "eye_break_enabled": tk.BooleanVar(value=self.config.habits.eye_break.enabled),
            "eye_break_interval": tk.StringVar(value=str(self.config.habits.eye_break.interval_minutes)),
            "stand_up_enabled": tk.BooleanVar(value=self.config.habits.stand_up.enabled),
            "stand_up_interval": tk.StringVar(value=str(self.config.habits.stand_up.interval_minutes)),
        }

        # Render rows of habits
        habits_info = [
            ("water", "Drink Water Reminder", "Periodic notification prompting you to hydrate.", "water_enabled", "water_interval"),
            ("stretch", "Stretch Reminder", "Reminds you to perform minor stretches and stand up to align posture.", "stretch_enabled", "stretch_interval"),
            ("eye_break", "Eye Break (20-20-20 rule)", "Reminds you to look 20 feet away for 20 seconds to prevent eye fatigue.", "eye_break_enabled", "eye_break_interval"),
            ("stand_up", "Stand-Up Reminder", "Warns you to avoid prolonged sitting and walk around.", "stand_up_enabled", "stand_up_interval")
        ]

        self.habit_inputs = []
        initial_state = "normal" if self.editing_habits else "disabled"

        for i, (key, label, desc, enabled_var, interval_var) in enumerate(habits_info):
            row_frame = tk.Frame(scroll_card, bg=BG_CARD, pady=10)
            row_frame.pack(fill="x", pady=5)
            
            # Left side checkbox and details
            chk_frame = tk.Frame(row_frame, bg=BG_CARD)
            chk_frame.pack(side="left", fill="both", expand=True)

            chk = tk.Checkbutton(
                chk_frame,
                text=label,
                font=("Segoe UI", 12, "bold"),
                bg=BG_CARD,
                fg=FG_LIGHT,
                selectcolor=BG_DARK,
                activebackground=BG_CARD,
                activeforeground=FG_LIGHT,
                variable=self.habit_vars[enabled_var],
                state=initial_state
            )
            chk.pack(anchor="w")
            self.habit_inputs.append(chk)

            lbl_desc = tk.Label(
                chk_frame,
                text=desc,
                font=("Segoe UI", 9),
                bg=BG_CARD,
                fg=FG_MUTED,
                justify="left"
            )
            lbl_desc.pack(anchor="w", padx=25)

            # Right side spinbox for interval
            interval_frame = tk.Frame(row_frame, bg=BG_CARD)
            interval_frame.pack(side="right", padx=10)

            tk.Label(interval_frame, text="Every", bg=BG_CARD, fg=FG_MUTED).pack(side="left")
            
            spin = tk.Spinbox(
                interval_frame,
                from_=5, to=360, increment=5,
                width=5,
                font=("Segoe UI", 10, "bold"),
                bg=BG_INPUT,
                fg=FG_LIGHT,
                bd=0,
                buttonbackground=BG_DARK,
                textvariable=self.habit_vars[interval_var],
                state=initial_state
            )
            spin.pack(side="left", padx=5)
            self.habit_inputs.append(spin)

            tk.Label(interval_frame, text="minutes", bg=BG_CARD, fg=FG_MUTED).pack(side="left")

            # Divider row (except last)
            if i < len(habits_info) - 1:
                sep = tk.Frame(scroll_card, bg=BG_INPUT, height=1)
                sep.pack(fill="x", pady=10)

        # Button Frame
        self.habits_btn_frame = tk.Frame(scroll_card, bg=BG_CARD)
        self.habits_btn_frame.pack(fill="x", pady=(20, 0))
        self.update_habits_buttons()

    # -----------------------------------------------------------------------
    # VIEW: Configurations Settings
    # -----------------------------------------------------------------------
    def _draw_settings(self) -> None:
        title = tk.Label(
            self.content_frame,
            text="Configurations",
            font=("Segoe UI", 18, "bold"),
            bg=BG_DARK,
            fg=FG_LIGHT
        )
        title.pack(anchor="w", pady=(0, 15))

        main_frame = tk.Frame(self.content_frame, bg=BG_DARK)
        main_frame.pack(fill="both", expand=True)

        # Config variables mapping
        self.config_vars = {
            # Posture thresholds
            "good_angle": tk.StringVar(value=str(self.config.posture.good_angle_threshold_degrees)),
            "fair_angle": tk.StringVar(value=str(self.config.posture.fair_angle_threshold_degrees)),
            "neck_angle": tk.StringVar(value=str(self.config.posture.neck_forward_angle_threshold_degrees)),
            "eye_angle": tk.StringVar(value=str(self.config.posture.eye_angle_threshold_degrees)),
            "shoulders_level": tk.BooleanVar(value=self.config.posture.require_shoulders_level),
            "forward_head": tk.BooleanVar(value=self.config.posture.require_forward_head_check),
            "camera_index": tk.StringVar(value=str(getattr(self.config.posture, "camera_index", 0))),
            # Monitoring loop
            "capture_interval": tk.StringVar(value=str(self.config.monitoring.capture_interval_seconds)),
            "bad_alert": tk.StringVar(value=str(self.config.monitoring.bad_posture_alert_seconds)),
            "cooldown": tk.StringVar(value=str(self.config.monitoring.cooldown_seconds)),
            # Notifications
            "notif_enabled": tk.BooleanVar(value=self.config.notifications.enabled),
            "notif_title": tk.StringVar(value=self.config.notifications.title),
            "notif_message": tk.StringVar(value=self.config.notifications.message),
        }

        # Grid layout for settings cards
        col_left = tk.Frame(main_frame, bg=BG_DARK)
        col_left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        col_right = tk.Frame(main_frame, bg=BG_DARK)
        col_right.pack(side="right", fill="both", expand=True, padx=(10, 0))

        self.settings_inputs = []
        initial_state = "normal" if self.editing_settings else "disabled"

        # --- LEFT PANEL: Posture Detection Rules ---
        posture_card = tk.LabelFrame(
            col_left,
            text="Posture AI Rules",
            font=("Segoe UI", 11, "bold"),
            bg=BG_CARD,
            fg=FG_LIGHT,
            bd=1,
            padx=15,
            pady=15
        )
        posture_card.pack(fill="x", pady=(0, 15))

        # Fields inside posture
        fields_pos = [
            ("Good Alignment Angle (°)", "good_angle"),
            ("Fair Alignment Angle (°)", "fair_angle"),
            ("Neck Slouch Angle (°)", "neck_angle"),
            ("Eye Tilt Angle (°)", "eye_angle")
        ]

        for i, (label, var_name) in enumerate(fields_pos):
            lbl = tk.Label(posture_card, text=label, bg=BG_CARD, fg=FG_MUTED, anchor="w")
            lbl.grid(row=i, column=0, sticky="w", pady=6)
            ent = tk.Entry(
                posture_card,
                width=10,
                font=("Segoe UI", 10, "bold"),
                bg=BG_INPUT,
                fg=FG_LIGHT,
                bd=0,
                insertbackground=FG_LIGHT,
                textvariable=self.config_vars[var_name],
                state=initial_state
            )
            ent.grid(row=i, column=1, sticky="e", pady=6, padx=(10, 0))
            self.settings_inputs.append(ent)

        # Checkboxes
        chk1 = tk.Checkbutton(
            posture_card,
            text="Require Shoulders Level",
            font=("Segoe UI", 10),
            bg=BG_CARD,
            fg=FG_LIGHT,
            selectcolor=BG_DARK,
            activebackground=BG_CARD,
            variable=self.config_vars["shoulders_level"],
            state=initial_state
        )
        chk1.grid(row=len(fields_pos), column=0, columnspan=2, sticky="w", pady=6)
        self.settings_inputs.append(chk1)

        chk2 = tk.Checkbutton(
            posture_card,
            text="Enable Forward Head Check",
            font=("Segoe UI", 10),
            bg=BG_CARD,
            fg=FG_LIGHT,
            selectcolor=BG_DARK,
            activebackground=BG_CARD,
            variable=self.config_vars["forward_head"],
            state=initial_state
        )
        chk2.grid(row=len(fields_pos)+1, column=0, columnspan=2, sticky="w", pady=6)
        self.settings_inputs.append(chk2)

        # Camera Index Selection
        lbl_cam = tk.Label(posture_card, text="Webcam Index", bg=BG_CARD, fg=FG_MUTED, anchor="w")
        lbl_cam.grid(row=len(fields_pos)+2, column=0, sticky="w", pady=6)
        ent_cam = tk.Entry(
            posture_card,
            width=10,
            font=("Segoe UI", 10, "bold"),
            bg=BG_INPUT,
            fg=FG_LIGHT,
            bd=0,
            insertbackground=FG_LIGHT,
            textvariable=self.config_vars["camera_index"],
            state=initial_state
        )
        ent_cam.grid(row=len(fields_pos)+2, column=1, sticky="e", pady=6, padx=(10, 0))
        self.settings_inputs.append(ent_cam)

        posture_card.grid_columnconfigure(0, weight=1)
        posture_card.grid_columnconfigure(1, weight=0)

        # --- RIGHT PANEL: Monitoring & Notifications ---
        mon_card = tk.LabelFrame(
            col_right,
            text="Timings & Alerts",
            font=("Segoe UI", 11, "bold"),
            bg=BG_CARD,
            fg=FG_LIGHT,
            bd=1,
            padx=15,
            pady=15
        )
        mon_card.pack(fill="x", pady=(0, 15))

        fields_mon = [
            ("Capture Interval (s)", "capture_interval"),
            ("Sustained Bad Posture Alert (s)", "bad_alert"),
            ("Notification Cooldown (s)", "cooldown")
        ]

        for i, (label, var_name) in enumerate(fields_mon):
            lbl = tk.Label(mon_card, text=label, bg=BG_CARD, fg=FG_MUTED, anchor="w")
            lbl.grid(row=i, column=0, sticky="w", pady=6)
            ent = tk.Entry(
                mon_card,
                width=10,
                font=("Segoe UI", 10, "bold"),
                bg=BG_INPUT,
                fg=FG_LIGHT,
                bd=0,
                insertbackground=FG_LIGHT,
                textvariable=self.config_vars[var_name],
                state=initial_state
            )
            ent.grid(row=i, column=1, sticky="e", pady=6, padx=(10, 0))
            self.settings_inputs.append(ent)
        
        mon_card.grid_columnconfigure(0, weight=1)
        mon_card.grid_columnconfigure(1, weight=0)

        # Notification Card
        notif_card = tk.LabelFrame(
            col_right,
            text="Desktop Notifications",
            font=("Segoe UI", 11, "bold"),
            bg=BG_CARD,
            fg=FG_LIGHT,
            bd=1,
            padx=15,
            pady=15
        )
        notif_card.pack(fill="both", expand=True)

        chk_not = tk.Checkbutton(
            notif_card,
            text="Enable Notifications",
            font=("Segoe UI", 10, "bold"),
            bg=BG_CARD,
            fg=FG_LIGHT,
            selectcolor=BG_DARK,
            activebackground=BG_CARD,
            variable=self.config_vars["notif_enabled"],
            state=initial_state
        )
        chk_not.pack(anchor="w", pady=(0, 5))
        self.settings_inputs.append(chk_not)

        lbl_title = tk.Label(notif_card, text="Alert Title", bg=BG_CARD, fg=FG_MUTED)
        lbl_title.pack(anchor="w", pady=2)
        ent_title = tk.Entry(
            notif_card,
            font=("Segoe UI", 10),
            bg=BG_INPUT,
            fg=FG_LIGHT,
            bd=0,
            insertbackground=FG_LIGHT,
            textvariable=self.config_vars["notif_title"],
            state=initial_state
        )
        ent_title.pack(fill="x", pady=(0, 8))
        self.settings_inputs.append(ent_title)

        lbl_msg = tk.Label(notif_card, text="Alert Message", bg=BG_CARD, fg=FG_MUTED)
        lbl_msg.pack(anchor="w", pady=2)
        ent_msg = tk.Entry(
            notif_card,
            font=("Segoe UI", 10),
            bg=BG_INPUT,
            fg=FG_LIGHT,
            bd=0,
            insertbackground=FG_LIGHT,
            textvariable=self.config_vars["notif_message"],
            state=initial_state
        )
        ent_msg.pack(fill="x")
        self.settings_inputs.append(ent_msg)

        # Button Frame
        self.settings_btn_frame = tk.Frame(self.content_frame, bg=BG_DARK)
        self.settings_btn_frame.pack(fill="x", side="bottom", pady=(15, 0))
        self.update_settings_buttons()

    # -----------------------------------------------------------------------
    # ACTIONS & LOOPS
    # -----------------------------------------------------------------------
    def update_daemon_status_loop(self) -> None:
        """Periodic background status check of the daemon."""
        try:
            if hasattr(self, 'daemon_status_lbl') and self.daemon_status_lbl.winfo_exists():
                if is_daemon_running():
                    pid = read_pid()
                    self.daemon_status_lbl.configure(
                        text=f"Status: Running (PID {pid})",
                        fg=ACCENT_GREEN
                    )
                    if hasattr(self, 'daemon_btn') and self.daemon_btn.winfo_exists():
                        self.daemon_btn.configure(
                            text="Stop Background Daemon",
                            bg=ACCENT_RED,
                            activebackground="#fca5a5"
                        )
                else:
                    self.daemon_status_lbl.configure(
                        text="Status: Stopped",
                        fg=ACCENT_RED
                    )
                    if hasattr(self, 'daemon_btn') and self.daemon_btn.winfo_exists():
                        self.daemon_btn.configure(
                            text="Start Background Daemon",
                            bg=ACCENT_GREEN,
                            activebackground="#b2f0ad"
                        )
        except Exception as e:
            logger.debug(f"Failed to update daemon status label (might be destroyed): {e}")

        # Repeat every 1000ms
        self.after(1000, self.update_daemon_status_loop)

    def toggle_daemon(self) -> None:
        """Start or stop the background process."""
        if is_daemon_running():
            # Stop it
            self.daemon_status_lbl.configure(text="Stopping...", fg=FG_MUTED)
            pid = read_pid()
            if pid:
                try:
                    if sys.platform == "win32":
                        # Kill the daemon process tree
                        subprocess.run(
                            ["taskkill", "/PID", str(pid), "/F", "/T"],
                            capture_output=True,
                            check=True
                        )
                    else:
                        os.kill(pid, 15) # SIGTERM
                    time.sleep(1.0)  # Wait longer for camera release
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to stop daemon: {e}")
        else:
            # Guard against duplicate launches
            if is_daemon_running():
                return

            # Stop preview first to release camera
            if self.preview_active:
                self.toggle_preview()
                time.sleep(0.5)  # Wait for camera release
                
            self.daemon_status_lbl.configure(text="Starting...", fg=FG_MUTED)
            python = sys.executable.replace("python.exe", "pythonw.exe") if sys.platform == "win32" else sys.executable
            cmd = [python, "-c", "from themonitor.daemon import run_daemon; run_daemon()"]
            
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = (
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    | subprocess.DETACHED_PROCESS
                    | subprocess.CREATE_NO_WINDOW
                )

            try:
                subprocess.Popen(
                    cmd,
                    creationflags=creation_flags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
                time.sleep(1.5)  # Wait longer for daemon to start and write PID
            except Exception as e:
                messagebox.showerror("Error", f"Failed to launch daemon: {e}")

        self.update_daemon_status_loop()

    def create_shortcut_action(self) -> None:
        """Create a desktop shortcut using the launcher module."""
        from themonitor.startup.launcher import create_desktop_shortcut
        if create_desktop_shortcut():
            messagebox.showinfo("Success", "Desktop shortcut 'Monitor GUI' created successfully!")
        else:
            messagebox.showerror("Failed", "Failed to create desktop shortcut. Check logs for details.")

    def toggle_preview(self) -> None:
        """Toggle live camera calibration preview."""
        if self.preview_active:
            # Stop preview
            self.preview_active = False
            self.preview_btn.configure(text="Start Live Preview", bg=ACCENT_BLUE)
            self.posture_status_lbl.configure(text="PREVIEW INACTIVE", fg=FG_MUTED)
            self._cleanup_camera()
            self.preview_state = "inactive"
            self.draw_canvas_for_state()
        else:
            # Start preview
            if is_daemon_running():
                # Ask user
                ans = messagebox.askyesno(
                    "Daemon Running",
                    "The background daemon is running and occupying the webcam. "
                    "Would you like to stop the background daemon to run the calibration preview?"
                )
                if ans:
                    self.toggle_daemon()
                    # Wait briefly for daemon release
                    self.after(1000, self.start_preview_flow)
            else:
                self.start_preview_flow()

    def start_preview_flow(self) -> None:
        """Initialise webcam and MediaPipe for preview."""
        # Set state to loading and update canvas immediately
        self.preview_state = "loading"
        self.draw_canvas_for_state()
        self.posture_status_lbl.configure(text="CONNECTING...", fg=ACCENT_YELLOW)
        self.update_idletasks() # force Tkinter to redraw the canvas

        try:
            cam_idx = int(getattr(self.config.posture, "camera_index", 0))
        except ValueError:
            cam_idx = 0

        self.cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW) if sys.platform == "win32" else cv2.VideoCapture(cam_idx)
        if not self.cap.isOpened():
            # Retry without backend flags
            self.cap = cv2.VideoCapture(cam_idx)

        if not self.cap.isOpened():
            self._cleanup_camera()
            self.preview_state = "error"
            self.draw_canvas_for_state()
            self.posture_status_lbl.configure(text="CAMERA ERROR", fg=ACCENT_RED)
            self.preview_active = False
            self.preview_btn.configure(text="Start Live Preview", bg=ACCENT_BLUE)
            return

        # Initialize MediaPipe Engine
        try:
            self.mp_engine = MediaPipeEngine(model_complexity=0)
            self.rules = PostureRules(
                good_angle_threshold_degrees=self.config.posture.good_angle_threshold_degrees,
                fair_angle_threshold_degrees=self.config.posture.fair_angle_threshold_degrees,
                eye_angle_threshold_degrees=self.config.posture.eye_angle_threshold_degrees,
                neck_forward_angle_threshold_degrees=self.config.posture.neck_forward_angle_threshold_degrees,
                require_shoulders_level=self.config.posture.require_shoulders_level,
                require_forward_head_check=self.config.posture.require_forward_head_check,
            )
        except Exception as e:
            logger.error(f"Failed to initialize MediaPipe engine or rules: {e}")
            self._cleanup_camera()
            self.preview_state = "error"
            self.draw_canvas_for_state()
            self.posture_status_lbl.configure(text="CAMERA ERROR", fg=ACCENT_RED)
            self.preview_active = False
            self.preview_btn.configure(text="Start Live Preview", bg=ACCENT_BLUE)
            return

        # Try to read the first frame
        ret, frame = self.cap.read()
        if not ret or frame is None:
            self._cleanup_camera()
            self.preview_state = "error"
            self.draw_canvas_for_state()
            self.posture_status_lbl.configure(text="CAMERA ERROR", fg=ACCENT_RED)
            self.preview_active = False
            self.preview_btn.configure(text="Start Live Preview", bg=ACCENT_BLUE)
            return

        # Successfully opened camera and read first frame
        self.preview_state = "active"
        self.preview_active = True
        self.preview_btn.configure(text="Stop Live Preview", bg=ACCENT_RED)
        
        # Reset counters & cache for frame skips
        self.frame_count = 0
        self.last_landmarks = None
        self.last_score = PostureScore.GOOD
        self.last_details = {}
        
        self.update_preview_loop()

    def update_preview_loop(self) -> None:
        """Grab and analyze camera frames, drawing nodes on Canvas."""
        if not self.preview_active or self.cap is None or self.mp_engine is None:
            return

        try:
            if not self.cap.isOpened():
                self.preview_state = "error"
                self.draw_canvas_for_state()
                return
            ret, frame = self.cap.read()
        except Exception:
            return

        if not ret or frame is None:
            self.after(50, self.update_preview_loop)
            return

        # Flip horizontally for natural mirror feel
        frame = cv2.flip(frame, 1)

        # Performance optimization: Resize captured frame to width of 320px
        # (preserving aspect ratio) using OpenCV before passing to MediaPipe
        h, w, _ = frame.shape
        aspect_ratio = h / w
        target_width = 320
        target_height = int(target_width * aspect_ratio)
        resized_for_mp = cv2.resize(frame, (target_width, target_height))

        # MediaPipe optimization: Run landmarks extraction only on every 5th frame
        self.frame_count += 1
        if self.frame_count % 5 == 1 or self.last_landmarks is None:
            landmarks = self.mp_engine.extract_landmarks(resized_for_mp)
            self.last_landmarks = landmarks
            
            if landmarks is not None and self.rules is not None:
                score, details = self.rules.evaluate(landmarks)
                self.last_score = score
                self.last_details = details
                self.pose_detected = True
            else:
                self.last_score = PostureScore.GOOD
                self.last_details = {}
                self.pose_detected = False
                score = self.last_score
                details = self.last_details
        else:
            landmarks = self.last_landmarks
            score = self.last_score
            details = self.last_details

        self.current_score = score

        # Query dynamic canvas dimensions
        canvas_w = 480
        canvas_h = 360
        if self.preview_canvas and self.preview_canvas.winfo_exists():
            w_val = self.preview_canvas.winfo_width()
            h_val = self.preview_canvas.winfo_height()
            if isinstance(w_val, (int, float)) and w_val > 1:
                canvas_w = int(w_val)
            if isinstance(h_val, (int, float)) and h_val > 1:
                canvas_h = int(h_val)

        # Display optimization: cv2.resize to (canvas_w, canvas_h) for display rendering
        display_frame = cv2.resize(frame, (canvas_w, canvas_h))

        # Draw skeleton on display frame if pose detected
        if self.pose_detected and landmarks is not None:
            self.draw_skeleton(display_frame, landmarks, details)

        # Convert frame color
        frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        img_tk = ImageTk.PhotoImage(image=img)

        # Render on Canvas
        try:
            if not self.preview_canvas or not self.preview_canvas.winfo_exists():
                return
            self.preview_canvas.delete("all")
            self.preview_canvas.image = img_tk  # keep reference
            self.preview_canvas.create_image(0, 0, anchor="nw", image=img_tk)

            # Warning overlay if no person is detected
            if not self.pose_detected:
                cx = canvas_w // 2
                cy = canvas_h // 2
                self.preview_canvas.create_text(
                    cx, cy,
                    text="No person detected",
                    font=("Segoe UI", 16, "bold"),
                    fill=ACCENT_RED,
                    justify="center"
                )
        except tk.TclError:
            return

        # Update Posture Status Label
        if not self.pose_detected:
            self.posture_status_lbl.configure(text="NO POSE DETECTED", fg=ACCENT_GRAY)
        elif self.current_score == PostureScore.GOOD:
            self.posture_status_lbl.configure(text="POSTURE: GOOD", fg=ACCENT_GREEN)
        elif self.current_score == PostureScore.FAIR:
            self.posture_status_lbl.configure(text="POSTURE: FAIR (UNALIGNED)", fg=ACCENT_YELLOW)
        else:
            self.posture_status_lbl.configure(text="POSTURE: BAD (SLOUCHING)", fg=ACCENT_RED)

        # Loop at 20 FPS (approx 50ms)
        self.after(50, self.update_preview_loop)

    def draw_skeleton(self, frame: np.ndarray, landmarks: dict[str, Landmark], details: dict[str, PostureScore]) -> None:
        """Helper to draw joints and lines on the frame."""
        h, w, _ = frame.shape

        # Define Landmark pixels (X coordinates are inverted due to frame flip)
        pts = {}
        for name, landmark in landmarks.items():
            # Since frame is flipped horizontally: new_x = 1.0 - x
            flipped_x = 1.0 - landmark.x
            pts[name] = (int(flipped_x * w), int(landmark.y * h))

        # Color configurations (BGR)
        color_green = (161, 227, 166)  # Catppuccin Green
        color_red = (168, 139, 243)    # Catppuccin Red (swapped BGR = 243, 139, 168)
        color_yellow = (175, 226, 249) # Catppuccin Yellow (swapped BGR)

        def get_color(score: PostureScore) -> tuple[int, int, int]:
            if score == PostureScore.GOOD:
                return (166, 227, 161) # BGR Green
            elif score == PostureScore.FAIR:
                return (175, 226, 249) # BGR Yellow
            return (168, 139, 243)     # BGR Red

        # --- Draw lines ---
        # 1. Shoulders line
        if "left_shoulder" in pts and "right_shoulder" in pts:
            sh_color = get_color(details.get("shoulder", PostureScore.GOOD))
            cv2.line(frame, pts["left_shoulder"], pts["right_shoulder"], sh_color, 3)

        # 2. Eye line
        if "left_eye_outer" in pts and "right_eye_outer" in pts:
            eye_color = get_color(details.get("eye_angle", PostureScore.GOOD))
            cv2.line(frame, pts["left_eye_outer"], pts["right_eye_outer"], eye_color, 2)
            if "left_eye_inner" in pts:
                cv2.line(frame, pts["left_eye_outer"], pts["left_eye_inner"], eye_color, 2)
            if "right_eye_inner" in pts:
                cv2.line(frame, pts["right_eye_outer"], pts["right_eye_inner"], eye_color, 2)

        # 3. Neck / Ears-to-shoulders
        # Worst score of slouch, bend back, or asymmetric lean decides head/neck color
        head_score = max(
            details.get("forward_head", PostureScore.GOOD),
            details.get("bending_back", PostureScore.GOOD),
            details.get("asymmetric_lean", PostureScore.GOOD),
            key=lambda s: SCORE_SEVERITY[s]
        )
        head_color = get_color(head_score)
        if "left_ear" in pts and "left_shoulder" in pts:
            cv2.line(frame, pts["left_ear"], pts["left_shoulder"], head_color, 2)
        if "right_ear" in pts and "right_shoulder" in pts:
            cv2.line(frame, pts["right_ear"], pts["right_shoulder"], head_color, 2)

        # 4. Hips & Torso lines
        if "left_hip" in pts and "right_hip" in pts:
            hip_color = get_color(details.get("bending_back", PostureScore.GOOD))
            # Draw hip line
            cv2.line(frame, pts["left_hip"], pts["right_hip"], hip_color, 2)
            # Draw torso sides
            if "left_shoulder" in pts:
                cv2.line(frame, pts["left_shoulder"], pts["left_hip"], hip_color, 2)
            if "right_shoulder" in pts:
                cv2.line(frame, pts["right_shoulder"], pts["right_hip"], hip_color, 2)

        # --- Draw joint circles ---
        for name, pt in pts.items():
            cv2.circle(frame, pt, 5, (200, 200, 200), -1)

        # Special circle for nose
        if "nose" in pts:
            cv2.circle(frame, pts["nose"], 7, head_color, -1)

    def save_habits_action(self) -> None:
        """Save habits settings back to config.yaml."""
        try:
            self.config.habits.water.enabled = self.habit_vars["water_enabled"].get()
            self.config.habits.water.interval_minutes = int(self.habit_vars["water_interval"].get())
            
            self.config.habits.stretch.enabled = self.habit_vars["stretch_enabled"].get()
            self.config.habits.stretch.interval_minutes = int(self.habit_vars["stretch_interval"].get())
            
            self.config.habits.eye_break.enabled = self.habit_vars["eye_break_enabled"].get()
            self.config.habits.eye_break.interval_minutes = int(self.habit_vars["eye_break_interval"].get())
            
            self.config.habits.stand_up.enabled = self.habit_vars["stand_up_enabled"].get()
            self.config.habits.stand_up.interval_minutes = int(self.habit_vars["stand_up_interval"].get())
            
            save_config(self.config)
            messagebox.showinfo("Success", "Habits configuration saved successfully!")
            
            # Lock the widgets and reset state
            self.editing_habits = False
            for widget in self.habit_inputs:
                widget.configure(state="disabled")
            self.update_habits_buttons()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save habits: {e}")

    def save_settings_action(self) -> None:
        """Save thresholds settings back to config.yaml."""
        try:
            # Posture thresholds
            self.config.posture.good_angle_threshold_degrees = float(self.config_vars["good_angle"].get())
            self.config.posture.fair_angle_threshold_degrees = float(self.config_vars["fair_angle"].get())
            self.config.posture.neck_forward_angle_threshold_degrees = float(self.config_vars["neck_angle"].get())
            self.config.posture.eye_angle_threshold_degrees = float(self.config_vars["eye_angle"].get())
            self.config.posture.require_shoulders_level = self.config_vars["shoulders_level"].get()
            self.config.posture.require_forward_head_check = self.config_vars["forward_head"].get()
            
            # Set camera index
            setattr(self.config.posture, "camera_index", int(self.config_vars["camera_index"].get()))

            # Monitoring
            self.config.monitoring.capture_interval_seconds = int(self.config_vars["capture_interval"].get())
            self.config.monitoring.bad_posture_alert_seconds = int(self.config_vars["bad_alert"].get())
            self.config.monitoring.cooldown_seconds = int(self.config_vars["cooldown"].get())

            # Notifications
            self.config.notifications.enabled = self.config_vars["notif_enabled"].get()
            self.config.notifications.title = self.config_vars["notif_title"].get()
            self.config.notifications.message = self.config_vars["notif_message"].get()

            save_config(self.config)
            messagebox.showinfo("Success", "System configuration saved successfully!")
            
            # Update rules if preview is active
            if self.preview_active and self.rules is not None:
                self.rules.good_angle_threshold_degrees = self.config.posture.good_angle_threshold_degrees
                self.rules.fair_angle_threshold_degrees = self.config.posture.fair_angle_threshold_degrees
                self.rules.eye_angle_threshold_degrees = self.config.posture.eye_angle_threshold_degrees
                self.rules.neck_forward_angle_threshold_degrees = self.config.posture.neck_forward_angle_threshold_degrees
                self.rules.require_shoulders_level = self.config.posture.require_shoulders_level
                self.rules.require_forward_head_check = self.config.posture.require_forward_head_check
                
            # Lock the widgets and reset state
            self.editing_settings = False
            for widget in self.settings_inputs:
                widget.configure(state="disabled")
            self.update_settings_buttons()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configurations: {e}")

    def _cleanup_camera(self) -> None:
        """Release camera and MediaPipe engine."""
        self.preview_active = False  # Ensure loop stops immediately
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        if self.mp_engine is not None:
            try:
                self.mp_engine.close()
            except Exception:
                pass
            self.mp_engine = None
        # Force OpenCV to release all windows/handles
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

    def on_close(self) -> None:
        """Handle window close gracefully."""
        self.preview_active = False
        self._cleanup_camera()
        self.destroy()

    def draw_canvas_for_state(self) -> None:
        if self.preview_canvas is None:
            return
        try:
            if not self.preview_canvas.winfo_exists():
                return
        except Exception:
            return
            
        canvas_w = self.preview_canvas.winfo_width()
        canvas_h = self.preview_canvas.winfo_height()
        if isinstance(canvas_w, (int, float)) and canvas_w > 1:
            canvas_w = int(canvas_w)
        else:
            canvas_w = 480
            
        if isinstance(canvas_h, (int, float)) and canvas_h > 1:
            canvas_h = int(canvas_h)
        else:
            canvas_h = 360

        cx = canvas_w // 2
        cy = canvas_h // 2

        self.preview_canvas.delete("all")
        
        if self.preview_state == "inactive":
            if self.logo_tk_120:
                self.preview_canvas.image = self.logo_tk_120 # keep reference
                self.preview_canvas.create_image(cx, cy - 40, anchor="center", image=self.logo_tk_120)
            self.preview_canvas.create_text(
                cx, cy + 60,
                text="Camera Preview Inactive\nClick 'Start Live Preview' below",
                font=("Segoe UI", 12),
                fill=FG_MUTED,
                justify="center"
            )
        elif self.preview_state == "loading":
            self.preview_canvas.create_text(
                cx, cy,
                text="Connecting to camera...",
                font=("Segoe UI", 12),
                fill=FG_MUTED,
                justify="center"
            )
        elif self.preview_state == "error":
            troubleshooting_text = (
                "Camera Error / Failed to read frame\n\n"
                "Troubleshooting Steps:\n"
                "1. Close other applications using the camera.\n"
                "2. Check camera privacy settings in Windows.\n"
                "3. Ensure the correct Webcam Index is configured.\n"
                "4. Re-plug the camera if it's external."
            )
            self.preview_canvas.create_text(
                cx, cy,
                text=troubleshooting_text,
                font=("Segoe UI", 10),
                fill=ACCENT_RED,
                justify="left"
            )

    def enable_habits_editing(self) -> None:
        self.editing_habits = True
        for widget in self.habit_inputs:
            widget.configure(state="normal")
        self.update_habits_buttons()

    def update_habits_buttons(self) -> None:
        for child in self.habits_btn_frame.winfo_children():
            child.destroy()
        
        if not self.editing_habits:
            self.habits_edit_btn = tk.Button(
                self.habits_btn_frame,
                text="Edit Settings",
                font=("Segoe UI", 11, "bold"),
                bg=ACCENT_BLUE,
                fg=BG_DARK,
                activebackground=ACCENT_BLUE_HOVER,
                relief="flat",
                bd=0,
                pady=8,
                cursor="hand2",
                command=self.enable_habits_editing
            )
            self.habits_edit_btn.pack(fill="x")
            self.habits_edit_btn.bind("<Enter>", lambda e, b=self.habits_edit_btn: b.configure(bg=ACCENT_BLUE_HOVER))
            self.habits_edit_btn.bind("<Leave>", lambda e, b=self.habits_edit_btn: b.configure(bg=ACCENT_BLUE))
        else:
            self.habits_save_btn = tk.Button(
                self.habits_btn_frame,
                text="Save",
                font=("Segoe UI", 11, "bold"),
                bg=ACCENT_GREEN,
                fg=BG_DARK,
                activebackground="#b2f0ad",
                relief="flat",
                bd=0,
                pady=8,
                cursor="hand2",
                command=self.save_habits_action
            )
            self.habits_save_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))

            self.habits_cancel_btn = tk.Button(
                self.habits_btn_frame,
                text="Cancel",
                font=("Segoe UI", 11, "bold"),
                bg=ACCENT_RED,
                fg=BG_DARK,
                activebackground=ACCENT_RED_HOVER,
                relief="flat",
                bd=0,
                pady=8,
                cursor="hand2",
                command=self.cancel_habits_editing
            )
            self.habits_cancel_btn.pack(side="right", fill="x", expand=True, padx=(5, 0))

    def cancel_habits_editing(self) -> None:
        self.editing_habits = False
        self.habit_vars["water_enabled"].set(self.config.habits.water.enabled)
        self.habit_vars["water_interval"].set(str(self.config.habits.water.interval_minutes))
        self.habit_vars["stretch_enabled"].set(self.config.habits.stretch.enabled)
        self.habit_vars["stretch_interval"].set(str(self.config.habits.stretch.interval_minutes))
        self.habit_vars["eye_break_enabled"].set(self.config.habits.eye_break.enabled)
        self.habit_vars["eye_break_interval"].set(str(self.config.habits.eye_break.interval_minutes))
        self.habit_vars["stand_up_enabled"].set(self.config.habits.stand_up.enabled)
        self.habit_vars["stand_up_interval"].set(str(self.config.habits.stand_up.interval_minutes))
        
        for widget in self.habit_inputs:
            widget.configure(state="disabled")
        self.update_habits_buttons()

    def enable_settings_editing(self) -> None:
        self.editing_settings = True
        for widget in self.settings_inputs:
            widget.configure(state="normal")
        self.update_settings_buttons()

    def update_settings_buttons(self) -> None:
        for child in self.settings_btn_frame.winfo_children():
            child.destroy()
        
        if not self.editing_settings:
            self.settings_edit_btn = tk.Button(
                self.settings_btn_frame,
                text="Edit Settings",
                font=("Segoe UI", 11, "bold"),
                bg=ACCENT_BLUE,
                fg=BG_DARK,
                activebackground=ACCENT_BLUE_HOVER,
                relief="flat",
                bd=0,
                pady=10,
                cursor="hand2",
                command=self.enable_settings_editing
            )
            self.settings_edit_btn.pack(fill="x")
            self.settings_edit_btn.bind("<Enter>", lambda e, b=self.settings_edit_btn: b.configure(bg=ACCENT_BLUE_HOVER))
            self.settings_edit_btn.bind("<Leave>", lambda e, b=self.settings_edit_btn: b.configure(bg=ACCENT_BLUE))
        else:
            self.settings_save_btn = tk.Button(
                self.settings_btn_frame,
                text="Save",
                font=("Segoe UI", 11, "bold"),
                bg=ACCENT_GREEN,
                fg=BG_DARK,
                activebackground="#b2f0ad",
                relief="flat",
                bd=0,
                pady=10,
                cursor="hand2",
                command=self.save_settings_action
            )
            self.settings_save_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))

            self.settings_cancel_btn = tk.Button(
                self.settings_btn_frame,
                text="Cancel",
                font=("Segoe UI", 11, "bold"),
                bg=ACCENT_RED,
                fg=BG_DARK,
                activebackground=ACCENT_RED_HOVER,
                relief="flat",
                bd=0,
                pady=10,
                cursor="hand2",
                command=self.cancel_settings_editing
            )
            self.settings_cancel_btn.pack(side="right", fill="x", expand=True, padx=(5, 0))

    def cancel_settings_editing(self) -> None:
        self.editing_settings = False
        self.config_vars["good_angle"].set(str(self.config.posture.good_angle_threshold_degrees))
        self.config_vars["fair_angle"].set(str(self.config.posture.fair_angle_threshold_degrees))
        self.config_vars["neck_angle"].set(str(self.config.posture.neck_forward_angle_threshold_degrees))
        self.config_vars["eye_angle"].set(str(self.config.posture.eye_angle_threshold_degrees))
        self.config_vars["shoulders_level"].set(self.config.posture.require_shoulders_level)
        self.config_vars["forward_head"].set(self.config.posture.require_forward_head_check)
        self.config_vars["camera_index"].set(str(getattr(self.config.posture, "camera_index", 0)))
        
        self.config_vars["capture_interval"].set(str(self.config.monitoring.capture_interval_seconds))
        self.config_vars["bad_alert"].set(str(self.config.monitoring.bad_posture_alert_seconds))
        self.config_vars["cooldown"].set(str(self.config.monitoring.cooldown_seconds))

        self.config_vars["notif_enabled"].set(self.config.notifications.enabled)
        self.config_vars["notif_title"].set(self.config.notifications.title)
        self.config_vars["notif_message"].set(self.config.notifications.message)

        for widget in self.settings_inputs:
            widget.configure(state="disabled")
        self.update_settings_buttons()


def run_ui() -> None:
    """Run the Tkinter GUI thread."""
    app = MonitorGUI()
    app.mainloop()


if __name__ == "__main__":
    run_ui()

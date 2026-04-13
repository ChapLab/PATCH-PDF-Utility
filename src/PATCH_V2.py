# -*- coding: utf-8 -*-
"""
Created on Wed Dec  3 23:56:39 2025

@author: bsanc
"""

# -*- coding: utf-8 -*-
import sys
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')  # FigureCanvasTkAgg uses Agg backend under the hood

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# -------------------------------------------------------------------------
# UI scaling helper
# -------------------------------------------------------------------------
UI_SCALE = 1.0  # will be updated once we know the screen size

def compute_ui_scale(root):
    """
    Compute a simple UI scale factor based on screen resolution.
    Reference resolution: 1920x1080.
    Clamped so it never gets too tiny or huge.
    """
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()

    scale = min(sw / 1920.0, sh / 1080.0)
    scale = max(0.75, min(scale, 1.4))  # clamp between 0.75x and 1.4x
    return scale


# ---- Global Font Size Settings ----
plt.rcParams.update({
    "font.size": 14,        # base font size
    "axes.titlesize": 16,   # subplot titles
    "axes.labelsize": 14,   # x/y labels
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
    "legend.fontsize": 12
})

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev & PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def compute_plot_scale(root):
    """
    Returns a gentle scaling factor for Matplotlib text.
    Main goal: readable at high DPI without exploding in size.
    """

    # Screen-based scaling (very mild)
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    res_scale = min(sw / 1920.0, sh / 1080.0)

    # DPI scaling (more important than resolution)
    try:
        dpi = root.winfo_fpixels('1i')
        dpi_scale = dpi / 96.0
    except Exception:
        dpi_scale = 1.0

    # --- NEW combined scale ---
    # Much softer weighting + nonlinear compression
    plot_scale = (dpi_scale ** 0.5) * 0.85

    # Clamp to reasonable range
    plot_scale = max(0.85, min(plot_scale, 1.35))
    return plot_scale

# -----------------------------------------------------------------------------
#                               CONSTANTS & DEFAULTS
# -----------------------------------------------------------------------------

DEFAULT_DATA_TYPE = "Q_A-1"
DEFAULT_WAVELENGTH = 0.1

DEFAULT_SCALING_TYPE = "normal"
DEFAULT_FIXED_SCALE = 1

DEFAULT_SCALING_RANGE = (1.5, None)
DEFAULT_CUTOFF = (None, None)
DEFAULT_TIP_UNDER_PCT = 0.10
DEFAULT_PLOT_XLIM = (None, None)

DEFAULT_MAX_SCALE_ITERS = 50
DEFAULT_SCALE_TOL = 1e-7
DEFAULT_HUBER_K = 1.345
DEFAULT_MIN_MAD = 1e-12

DEFAULT_SUFFIX = "_patched"
MIN_COS = 1e-3

HEADER_LINES_BY_EXT = {
    'iq': 26, 'gr': 26, 'qchi': 4, 'nmf': 0, 'pca': 0, 'dat': 0, 'chi': 4
}

# -----------------------------------------------------------------------------
#                                TOOLTIP CLASS
# -----------------------------------------------------------------------------

class ToolTip(object):
    """Tooltip for Tk widgets — appears when hovering over the widget."""

    def __init__(self, widget, text='widget info'):
        self.waittime = 650    # milliseconds
        self.wraplength = 300  # pixels
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self._enter)
        self.widget.bind("<Leave>", self._leave)
        self.widget.bind("<ButtonPress>", self._leave)
        self.id = None
        self.tw = None


    def _enter(self, event=None):
        self._schedule()

    def _leave(self, event=None):
        self._unschedule()
        self._hide()

    def _schedule(self):
        self._unschedule()
        self.id = self.widget.after(self.waittime, self._show)

    def _unschedule(self):
        _id = self.id
        self.id = None
        if _id:
            self.widget.after_cancel(_id)

    def _show(self):
        if self.tw:
            return
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 50
        y += self.widget.winfo_rooty() + 25

        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.geometry("+%d+%d" % (x, y))

        label = tk.Label(
            self.tw, text=self.text, justify='left',
            background="#ffffe0", relief='solid', borderwidth=1,
            wraplength=self.wraplength
        )
        label.pack(ipadx=1)

    def _hide(self):
        tw = self.tw
        self.tw = None
        if tw:
            tw.destroy()

# -----------------------------------------------------------------------------
#                          FILE LOADING / PARSE HELPERS
# -----------------------------------------------------------------------------

def sniff_delimiter(sample_line):
    return ',' if ',' in sample_line else ' '

def read_header_text(dirpath, filename_):
    ext = filename_.split('.')[-1].lower()
    n_header = HEADER_LINES_BY_EXT.get(ext, 0)
    header_text = ""
    delim = ' '
    full_path = os.path.join(dirpath, filename_)

    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    if n_header > 0:
        header_text = "".join(lines[:n_header])

    for line in lines[n_header:]:
        s = line.strip()
        if s and any(c.isdigit() for c in s):
            delim = sniff_delimiter(line)
            break

    return n_header, header_text, delim

def load_matrix(dirpath, index, cutoff_):
    if not index:
        raise RuntimeError("No files to load.")

    ext = index[0].split('.')[-1].lower()
    n_header = HEADER_LINES_BY_EXT.get(ext, 0)

    ex = np.genfromtxt(os.path.join(dirpath, index[0]), skip_header=n_header)
    if ex.ndim == 1:
        ex = ex.reshape(1, -1)

    q_all = ex[:, 0]
    i1 = 0
    i2 = len(q_all) - 1

    if cutoff_[0] is not None:
        while i1 < len(q_all) and q_all[i1] < cutoff_[0]:
            i1 += 1

    if cutoff_[1] is not None:
        while i2 >= 0 and q_all[i2] > cutoff_[1]:
            i2 -= 1

    q = q_all[i1:i2+1]

    X = np.zeros((len(q), len(index)+1), dtype=float)
    X[:, 0] = q

    for k, fn in enumerate(index):
        dat = np.genfromtxt(os.path.join(dirpath, fn), skip_header=n_header)
        if dat.ndim == 1:
            dat = dat.reshape(1, -1)
        X[:, k+1] = dat[i1:i2+1, 1]

    return X

def safe_arcsin(x):
    return np.arcsin(np.clip(x, -1, 1))

def q_to_two_theta_rad(q, data_type_, wavelength_):
    if data_type_ == "two_theta":
        return np.deg2rad(q)
    arg = q * wavelength_ / (4*np.pi)
    theta = safe_arcsin(arg)
    return 2 * theta

def cos_two_theta(q, data_type_, wavelength_):
    th = q_to_two_theta_rad(q, data_type_, wavelength_)
    return np.cos(th)

def find_q_bounds(q, qmin, qmax):
    i0 = np.searchsorted(q, qmin, side='left')
    i1 = np.searchsorted(q, qmax, side='right') - 1
    i0 = max(0, min(i0, len(q)-1))
    i1 = max(0, min(i1, len(q)-1))
    if i1 < i0:
        i0, i1 = i1, i0
    return i0, i1

def build_window_mask(q, qmin, qmax):
    if qmin is None and qmax is None:
        return np.ones_like(q, dtype=bool)
    if qmin is None:
        qmin = q[0]
    if qmax is None:
        qmax = q[-1]
    i0, i1 = find_q_bounds(q, qmin, qmax)
    m = np.zeros_like(q, dtype=bool)
    m[i0:i1+1] = True
    return m

def nonsaturated_mask_from_tip_rule(sat, tip_under_pct_):
    bmax = np.nanmax(sat)
    thr = (1.0 - tip_under_pct_) * bmax
    return sat < thr, thr

# -----------------------------------------------------------------------------
#                               IRLS FUNCTIONS
# -----------------------------------------------------------------------------

def huber_weights(r, k=1.345, mad_floor=1e-12):
    mad = np.median(np.abs(r - np.median(r)))
    sigma = max(mad_floor, 1.4826*mad)
    t = k * sigma
    a = np.abs(r)
    w = np.ones_like(r)
    big = a > t
    w[big] = t / a[big]
    return w, sigma, t

def irls_scale_normal(X_bad, X_good, scaling_range_, tip_under_pct_,
                      max_iter, tol, huber_k_, mad_floor):

    q = X_bad[:, 0]
    win = build_window_mask(q, scaling_range_[0], scaling_range_[1])

    scaled = np.zeros_like(X_good)
    scaled[:, 0] = q

    final_scales = []
    thresholds = []
    histories = []

    for c in range(1, X_bad.shape[1]):
        bad = X_bad[:, c].astype(float)
        good = X_good[:, c].astype(float)

        nonsat, thr = nonsaturated_mask_from_tip_rule(bad, tip_under_pct_)
        thresholds.append(thr)

        mask = win & nonsat & np.isfinite(bad) & np.isfinite(good) & (good > 0)
        if not np.any(mask):
            s = 1.0
            scaled[:, c] = good * s
            final_scales.append(s)
            histories.append([s])
            continue

        x = good[mask]
        y = bad[mask]

        denom = np.dot(x, x)
        s = np.dot(x, y) / denom if denom > 0 else 1.0

        s_hist = [s]
        for _ in range(max_iter):
            r = s * x - y
            w, _, _ = huber_weights(r, k=huber_k_, mad_floor=mad_floor)
            num = np.dot(w * x, y)
            den = np.dot(w * x, x)
            s_new = num / den if den > 0 else s
            s_hist.append(s_new)
            if abs(s_new - s) <= tol * max(1.0, abs(s)):
                s = s_new
                break
            s = s_new

        scaled[:, c] = good * s
        final_scales.append(s)
        histories.append(s_hist)

    return scaled, np.array(final_scales), np.array(thresholds), histories

def irls_scale_attenuated(X_bad, X_good, scaling_range_, tip_under_pct_,
                          q_axis, data_type_, wavelength_,
                          max_iter, tol, huber_k_, mad_floor):

    q = X_bad[:, 0]
    win = build_window_mask(q, scaling_range_[0], scaling_range_[1])

    cos2 = np.maximum(np.abs(cos_two_theta(q_axis, data_type_, wavelength_)), MIN_COS)

    scaled = np.zeros_like(X_good)
    scaled[:, 0] = q

    final_scales = []
    thresholds = []
    histories = []

    for c in range(1, X_bad.shape[1]):
        bad = X_bad[:, c].astype(float)
        good = X_good[:, c].astype(float)

        nonsat, thr = nonsaturated_mask_from_tip_rule(bad, tip_under_pct_)
        thresholds.append(thr)

        mask = win & nonsat & np.isfinite(bad) & np.isfinite(good) & (good > 0)

        if not np.any(mask):
            s = 1.0
            scaled[:, c] = good * s
            final_scales.append(s)
            histories.append([s])
            continue

        x = good[mask]
        y = bad[mask]
        cfac = cos2[mask]

        denom = np.dot(x, x)
        s = np.dot(x, y) / denom if denom > 0 else 1.0
        s_hist = [s]

        for _ in range(max_iter):
            r = s * x - y
            w, _, _ = huber_weights(r, k=huber_k_, mad_floor=mad_floor)
            num = np.dot((w / cfac) * x, y)
            den = np.dot((w / cfac) * x, x)
            s_new = num / den if den > 0 else s
            s_hist.append(s_new)
            if abs(s_new - s) <= tol * max(1.0, abs(s)):
                s = s_new
                break
            s = s_new

        scaled[:, c] = good * s
        final_scales.append(s)
        histories.append(s_hist)

    return scaled, np.array(final_scales), np.array(thresholds), histories

# -----------------------------------------------------------------------------
#                        TIPS-ONLY RESTORATION
# -----------------------------------------------------------------------------

def tips_restore_constant_threshold(X_bad, X_good_scaled, frac_under_max):
    out = np.array(X_bad, copy=True)
    tips = np.zeros_like(X_bad)
    q = X_bad[:, 0]
    thresholds = []

    for c in range(1, X_bad.shape[1]):
        sat = X_bad[:, c]
        rep = X_good_scaled[:, c]

        sat_max = np.nanmax(sat)
        thr = (1.0 - frac_under_max) * sat_max
        thresholds.append(thr)

        mask = sat >= thr
        out[mask, c] = rep[mask]
        tips[mask, c] = rep[mask]

    tips[:, 0] = q
    return out, tips, np.array(thresholds)

def build_xmask(q, xlim):
    m = np.ones_like(q, dtype=bool)
    if xlim[0] is not None:
        m &= q >= xlim[0]
    if xlim[1] is not None:
        m &= q <= xlim[1]
    return m

def add_scatter_and_blue_segments(ax, q, y_sat, y_rep, thr, xmask,
                                  s=10, lw=1.0):
    qm = q[xmask]
    sat_m = y_sat[xmask]
    rep_m = y_rep[xmask]

    if len(qm) < 2:
        return []

    y_rest = np.where(sat_m >= thr, rep_m, sat_m)
    use_rep = sat_m >= thr

    ax.scatter(qm[~use_rep], y_rest[~use_rep],
               s=s, color='black', alpha=0.9)
    ax.scatter(qm[use_rep], y_rest[use_rep],
               s=s, color='red',   alpha=0.9)

    x0 = qm[:-1]
    x1 = qm[1:]
    y0 = y_rest[:-1]
    y1 = y_rest[1:]

    good = (np.isfinite(x0) & np.isfinite(x1) &
            np.isfinite(y0) & np.isfinite(y1))

    if np.any(good):
        segs = np.stack(
            [
                np.stack([x0[good], y0[good]], axis=1),
                np.stack([x1[good], y1[good]], axis=1)
            ],
            axis=1
        )
        lc = LineCollection(segs, colors='blue',
                            linewidths=lw, alpha=0.85)
        ax.add_collection(lc)

        pts = np.vstack([
            np.column_stack([x0[good], y0[good]]),
            np.column_stack([x1[good], y1[good]])
        ])
        ax.update_datalim(pts)
        ax.autoscale_view()

    proxies = [
        Line2D([0], [0], marker='o', linestyle='None',
               color='black', label='Points (Saturated)'),
        Line2D([0], [0], marker='o', linestyle='None',
               color='red',   label='Points (Repair)'),
        # Line2D([0], [0], color='blue', lw=lw,
        #        label='Segmented line')
    ]
    return proxies

# -----------------------------------------------------------------------------
#                        EXPORT HELPERS
# -----------------------------------------------------------------------------

def export_matrix_with_header(X, dirpath, index_bad, suffix,
                              header_text, delim,
                              float_fmt="%.8g"):

    for i in range(1, X.shape[1]):
        src = index_bad[i-1]
        if '.' in src:
            base, ext = src.rsplit('.', 1)
        else:
            base, ext = src, "txt"

        out_name = "%s_%s.%s" % (base, suffix, ext)
        arr = np.column_stack([X[:, 0], X[:, i]])

        if delim == ',':
            body = "\n".join([
                ("%s,%s" % (float_fmt, float_fmt)) % (x, y) for x, y in arr
            ])
        else:
            body = "\n".join([
                ("%s %s" % (float_fmt, float_fmt)) % (x, y) for x, y in arr
            ])

        with open(os.path.join(dirpath, out_name), "w",
                  encoding="utf-8") as f:
            if header_text:
                f.write(header_text)
                if not header_text.endswith("\n"):
                    f.write("\n")
            f.write(body)

def export_single_with_header(X_col, dirpath,
                              src_filename, suffix,
                              header_text, delim,
                              float_fmt="%.8g"):

    src = src_filename
    if '.' in src:
        base, ext = src.rsplit('.', 1)
    else:
        base, ext = src, "txt"

    out_name = "%s_%s.%s" % (base, suffix, ext)

    if delim == ',':
        body = "\n".join([("%s,%s" % (float_fmt, float_fmt)) % (x, y)
                          for x, y in X_col])
    else:
        body = "\n".join([("%s %s" % (float_fmt, float_fmt)) % (x, y)
                          for x, y in X_col])

    full_path = os.path.join(dirpath, out_name)
    with open(full_path, "w", encoding="utf-8") as f:
        if header_text:
            f.write(header_text)
            if not header_text.endswith("\n"):
                f.write("\n")
        f.write(body)

    return full_path

# -----------------------------------------------------------------------------
#                            MAIN PATCH GUI CLASS
# -----------------------------------------------------------------------------
class SplashScreen(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)

        # Match main GUI background + accent color
        BG = "#f5f5f7"
        RED = "#c62828"

        self.overrideredirect(True)
        self.configure(bg=BG)

        # Resize window to fit the full text, scaled with UI_SCALE
        self.update_idletasks()
        global UI_SCALE
        w = int(600 * UI_SCALE)
        h = int(380 * UI_SCALE)
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Try setting window icon
        try:
            ico_path = resource_path("patch_logo.ico")
            self.iconbitmap(ico_path)
        except Exception:
            pass

        # ============================================================
        # TITLE ROW (logo + "PDF Patch")
        # ============================================================
        title_frame = tk.Frame(self, bg=BG)
        title_frame.pack(
            pady=(int(35 * UI_SCALE), int(10 * UI_SCALE))
        )

        # Load PNG logo and resize to ~100px width
        self.logo_img = None
        try:
            png_path = resource_path("patch_logo.png")
            raw_img = tk.PhotoImage(file=png_path)

            current_width = raw_img.width()
            target_width = 100

            if current_width > target_width:
                factor = max(1, int(current_width // target_width))
                logo_img = raw_img.subsample(factor, factor)
            else:
                logo_img = raw_img

            self.logo_img = logo_img
            tk.Label(title_frame, image=self.logo_img, bg=BG).pack(side="left", padx=10)

        except Exception as e:
            print("Splash image load failed:", e)

        # "PDF Patch" next to logo
        tk.Label(
            title_frame,
            text="PDF Patch",
            font=("Segoe UI", int(32 * UI_SCALE), "bold"),
            bg=BG,
            fg=RED
        ).pack(side="left", padx=int(10 * UI_SCALE))


        # ============================================================
        # CITATION BLOCK (centered, wrapped)
        # ============================================================
        citation_text = (
            "If you use this program, please consider citing us:\n"
            "Citation link placeholder\n\n"
            "This software was developed by the Chapman Lab\n"
            "Stony Brook University — Department of Chemistry"
        )

        tk.Label(
            self,
            text=citation_text,
            font=("Segoe UI", int(10 * UI_SCALE)),
            bg=BG,
            fg="#333333",
            justify="center",
            wraplength=int(500 * UI_SCALE)
        ).pack(
            pady=(int(15 * UI_SCALE), int(10 * UI_SCALE))
        )

        # Auto-close after delay
        self.after(5000, self.destroy)


class PATCH(tk.Frame):  
    
    def _on_global_click(self, event):
        widget = event.widget
    
        # Do NOT clear if clicking inside either listbox
        if widget is self.sat_listbox or widget is self.rep_listbox:
            return
    
        # Clear both selections
        self.sat_listbox.selection_clear(0, tk.END)
        self.rep_listbox.selection_clear(0, tk.END)

    
    def _clear_listbox_selection(self, event):
        widget = event.widget
    
        # Do NOT clear if click is inside a listbox
        if widget is self.sat_listbox or widget is self.rep_listbox:
            return
    
        # Clear selections in both
        self.sat_listbox.selection_clear(0, tk.END)
        self.rep_listbox.selection_clear(0, tk.END)


    def _delete_selected_saturated(self, event=None):
        selections = list(self.sat_listbox.curselection())
        if not selections:
            return
    
        # Delete bottom→top
        for i in reversed(selections):
            if 0 <= i < len(self.index_saturated):
                self.index_saturated.pop(i)
    
        # Fix pair index to valid range
        if self.current_pair_idx >= len(self.index_saturated):
            self.current_pair_idx = max(0, len(self.index_saturated) - 1)
    
        self._refresh_listboxes()
        self._update_nav_buttons()
    
        # 🔥 NEW: Update plot according to healing state
        if self.healing_done:
            self.update_plot()
        else:
            self.update_preview_plot()
    
        self.status_var.set("Removed selected saturated files.")

    def _delete_selected_repair(self, event=None):
        selections = list(self.rep_listbox.curselection())
        if not selections:
            return
    
        for i in reversed(selections):
            if 0 <= i < len(self.index_repair):
                self.index_repair.pop(i)
    
        # Fix index
        if self.current_pair_idx >= len(self.index_repair):
            self.current_pair_idx = max(0, len(self.index_repair) - 1)
    
        self._refresh_listboxes()
        self._update_nav_buttons()
    
        # 🔥 NEW: Update plot according to healing state
        if self.healing_done:
            self.update_plot()
        else:
            self.update_preview_plot()
    
        self.status_var.set("Removed selected repair files.")

    
    def _on_mouse_move(self, event):
        """
        Display mouse coordinates (x, y) in the status bar when hovering
        over the Matplotlib plots.
        """
        if event.inaxes:
            x = event.xdata
            y = event.ydata
    
            # Format coordinates nicely
            if x is not None and y is not None:
                self.status_var.set(f"x = {x: .4f},   y = {y: .4f}")
        else:
            # Restore default status when outside axes
            self.status_var.set("Hover over buttons for ⓘ help")


    def _update_datatype_widgets(self):
        dtype = self.data_type_var.get()
    
        # --- Update label text depending on data type ---
        if dtype == "Q_A-1":
            self.wavelength_label.config(text="Wavelength / Å :")
            self.wavelength_entry.config(state="normal")
    
        elif dtype == "Q_nm-1":
            self.wavelength_label.config(text="Wavelength / nm :")
            self.wavelength_entry.config(state="normal")
    
        elif dtype == "two_theta":
            self.wavelength_label.config(text="Wavelength:")
            self.wavelength_entry.config(state="disabled")  # gray out
    
        # OPTIONAL: also disable 2θ scaling fields if you want


    def __init__(self, master=None):
        super().__init__(master)

        self.master = master
        self.master.title("PATCH")

        # Maximize on launch
        try:
            self.master.state('zoomed')
        except tk.TclError:
            self.master.attributes('-zoomed', True)

        # Set window/taskbar icon from patch_logo.ico
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            ico_path = os.path.join(script_dir, "patch_logo.ico")
            if os.path.exists(ico_path):
                icon_path = resource_path("patch_logo.ico")
                self.master.iconbitmap(ico_path)
        except Exception as e:
            print("Icon load failed:", e)

        self.master.configure(background="#f5f5f7")

        # Directories
        self.dir_saturated = None
        self.dir_repair = None

        # Filename lists
        self.index_saturated = []
        self.index_repair = []

        # Data arrays
        self.X_bad = None
        self.X_good = None
        self.X_good_scaled = None
        self.X_restored = None
        self.Tips = None
        self.thresholds = None
        self.scales = None
        self.scales_history = None
        self.q = None

        # Header + delimiter
        self.header_text_bad = ""
        self.delim_bad = " "

        # Which pair is selected
        self.current_pair_idx = 0

        # Tk variables
        self.data_type_var = tk.StringVar(value=DEFAULT_DATA_TYPE)
        self.wavelength_var = tk.DoubleVar(value=DEFAULT_WAVELENGTH)
        self.scaling_type_var = tk.StringVar(value=DEFAULT_SCALING_TYPE)
        self.fixed_scale_var = tk.DoubleVar(value=DEFAULT_FIXED_SCALE)

        self.scaling_min_var = tk.StringVar(
            value="" if DEFAULT_SCALING_RANGE[0] is None else
            str(DEFAULT_SCALING_RANGE[0])
        )
        self.scaling_max_var = tk.StringVar(
            value="" if DEFAULT_SCALING_RANGE[1] is None else
            str(DEFAULT_SCALING_RANGE[1])
        )

        self.cutoff_min_var = tk.StringVar(
            value="" if DEFAULT_CUTOFF[0] is None else str(DEFAULT_CUTOFF[0])
        )
        self.cutoff_max_var = tk.StringVar(
            value="" if DEFAULT_CUTOFF[1] is None else str(DEFAULT_CUTOFF[1])
        )

        self.tip_frac_var = tk.DoubleVar(value=DEFAULT_TIP_UNDER_PCT)

        self.xmin_var = tk.StringVar(
            value="" if DEFAULT_PLOT_XLIM[0] is None else str(DEFAULT_PLOT_XLIM[0])
        )
        self.xmax_var = tk.StringVar(
            value="" if DEFAULT_PLOT_XLIM[1] is None else str(DEFAULT_PLOT_XLIM[1])
        )

        self.max_iters_var = tk.IntVar(value=DEFAULT_MAX_SCALE_ITERS)
        self.scale_tol_var = tk.DoubleVar(value=DEFAULT_SCALE_TOL)
        self.huber_k_var = tk.DoubleVar(value=DEFAULT_HUBER_K)

        self.suffix_var = tk.StringVar(value=DEFAULT_SUFFIX)
        self.choose_export_dir_var = tk.BooleanVar(value=False)
        self.export_dir = None

        self.status_var = tk.StringVar(
            value="Load saturated and repair files to begin."
        )

        # Drag reorder state
        self._drag_start_index_sat = None
        self._drag_start_index_rep = None

        # Style / theme
        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except tk.TclError:
            pass

        # Modern red button style to match logo
        self.style.configure(
            "Red.TButton",
            foreground="white",
            background="#c62828",
            padding=6,
            relief="flat"
        )
        self.style.map(
            "Red.TButton",
            background=[("active", "#e53935"), ("disabled", "#9e9e9e")],
            foreground=[("disabled", "#f0f0f0")]
        )

        # Build the full GUI
        self._build_layout()
        # Clear listbox selections when clicking outside them
        self.master.bind("<Button-1>", self._on_global_click, add="+")
        self._update_scale_entry_states()
        self._update_nav_buttons()
        
        self.healing_done = False


    # -------------------------------------------------------------------------
    #                            GUI CONSTRUCTION
    # -------------------------------------------------------------------------


    def _build_layout(self):
        
        def create_centered_labelframe(parent, text):
            """
            Creates a frame that visually mimics a LabelFrame but 
            includes a centered title label above a bordered frame.
            Returns (outer_frame, inner_frame) where inner_frame 
            should contain the section's widgets.
            """
            outer = ttk.Frame(parent)  # holds title + border box
        
            title_lbl = ttk.Label(
                outer,
                text=text,
                anchor="center",
                font=("Segoe UI", max(9, int(11 * UI_SCALE)), "bold")
            )
        
            # Bordered frame below
            border = ttk.Frame(outer, relief="groove", borderwidth=2)
            border.pack(side="top", fill="both", expand=True, pady=(2, 0))
        
            return outer, border


        # ----- TOP FRAME: Lists + Controls -----
        top_frame = ttk.Frame(self.master)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        top_frame.grid_columnconfigure(0, weight=1, uniform="col")
        top_frame.grid_columnconfigure(1, weight=1, uniform="col")
        top_frame.grid_columnconfigure(2, weight=1, uniform="col")
        top_frame.grid_rowconfigure(0, weight=1)

        # --------------------------------------------------------------
        # SATURATED LIST (left)
        # --------------------------------------------------------------

        sat_outer, sat_frame = create_centered_labelframe(
            top_frame, "Overexposed / Saturated Files"
        )
        sat_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 8))


        btn_load_sat = ttk.Button(
            sat_frame,
            text="Load Saturated Files",
            command=self.load_saturated_files,
            style="Red.TButton"
        )
        btn_load_sat.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)
        ToolTip(btn_load_sat, "Select one or more overexposed/saturated data files.")

        self.sat_listbox = tk.Listbox(
            sat_frame, selectmode=tk.EXTENDED, activestyle="dotbox",
            highlightthickness=0, borderwidth=0, exportselection=False
        )
        self.sat_listbox.config(selectforeground="white")
        self.sat_listbox.bind("<Delete>", self._delete_selected_saturated)
        self.sat_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                              padx=(4, 0), pady=4)

        sat_scroll = ttk.Scrollbar(sat_frame, orient=tk.VERTICAL,
                                   command=self.sat_listbox.yview)
        sat_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.sat_listbox.config(yscrollcommand=sat_scroll.set)

        # Drag events
        self.sat_listbox.bind("<Button-1>", self._on_sat_click)
        self.sat_listbox.bind("<ButtonRelease-1>", self._on_sat_release)

        # --------------------------------------------------------------
        # CENTER CONTROLS PANEL (centered between the two list columns)
        # --------------------------------------------------------------

        #ctrl_frame = ttk.LabelFrame(top_frame, text="Scaling & Healing Settings")
        #ctrl_frame.grid(row=0, column=1, sticky="nsew", padx=8)
        ctrl_outer, ctrl_frame = create_centered_labelframe(
            top_frame, "Scaling & Patching Settings"
        )
        ctrl_outer.grid(row=0, column=1, sticky="nsew", padx=8)


        for col in range(4):
            ctrl_frame.grid_columnconfigure(col, weight=1)

        row = 0

        # Data type
        ttk.Label(ctrl_frame, text="Data Type:").grid(row=row, column=0, sticky="w")
        # dtype_menu = ttk.OptionMenu(ctrl_frame, self.data_type_var,
        #                             self.data_type_var.get(),
        #                             "Q_A-1", "Q_nm-1", "two_theta")
                
        self.dtype_menu = ttk.Combobox(
            ctrl_frame,
            textvariable=self.data_type_var,
            values=["Q_A-1", "Q_nm-1", "two_theta"],
            state="readonly",
            style="Custom.TCombobox"
        )
        self.dtype_menu.bind("<<ComboboxSelected>>", lambda e: self._update_datatype_widgets())


        self.dtype_menu.grid(row=row, column=1, sticky="ew", padx=2, pady=2)

        
        self.dtype_menu.grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        ToolTip(self.dtype_menu, "Select the x-axis data type used in the files. Enabled only when using attenuated scaling.")

        # ttk.Label(ctrl_frame, text="Wavelength:").grid(row=row, column=2, sticky="w")
        # self.wavelength_entry = ttk.Entry(ctrl_frame,
        #                                   textvariable=self.wavelength_var,
        #                                   width=8)
        # self.wavelength_entry.grid(row=row, column=3, sticky="ew", padx=2, pady=2)
        # --- Wavelength label (store reference so we can edit it later) ---
        
        self.wavelength_label = ttk.Label(ctrl_frame, text="Wavelength / Å")
        self.wavelength_label.grid(row=row, column=2, sticky="w")
        
        self.wavelength_entry = ttk.Entry(
            ctrl_frame,
            textvariable=self.wavelength_var,
            width=8
        )
        self.wavelength_entry.grid(row=row, column=3, sticky="ew", padx=2, pady=2)

        ToolTip(self.wavelength_entry, "X-ray wavelength. Enabled only when using attenuated scaling.")
        row += 1

        # Scaling type
        ttk.Label(ctrl_frame, text="Scaling Type:").grid(row=row, column=0, sticky="w")
        
        self.scale_menu = ttk.Combobox(
            ctrl_frame,
            textvariable=self.scaling_type_var,
            values=["normal", "attenuated", "fixed"],
            state="readonly",
            style="Custom.TCombobox"
        )
        self.scale_menu.bind("<<ComboboxSelected>>", lambda e: self._update_scale_entry_states())
        self.scale_menu.grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        
        ToolTip(self.scale_menu,
                "Choose scaling method:\n"
                "- normal: IRLS\n"
                "- attenuated: IRLS with attenuator correction\n"
                "- fixed: Multiply by constant scale")


        ttk.Label(ctrl_frame, text="Fixed Scale:").grid(row=row, column=2, sticky="w")
        self.fixed_scale_entry = ttk.Entry(
            ctrl_frame,
            textvariable=self.fixed_scale_var,
            width=10
        )
        self.fixed_scale_entry.grid(row=row, column=3, sticky="ew", padx=2, pady=2)
        ToolTip(self.fixed_scale_entry, "Scale factor applied when scaling type = fixed.")
        row += 1

        # Scaling range
        ttk.Label(ctrl_frame, text="Scaling Range Min:").grid(row=row, column=0, sticky="w")
        e_smin = ttk.Entry(ctrl_frame, textvariable=self.scaling_min_var, width=10)
        e_smin.grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        ToolTip(e_smin, "Lower limit of q / 2θ range used for IRLS scaling.")

        ttk.Label(ctrl_frame, text="Scaling Range Max:").grid(row=row, column=2, sticky="e")
        e_smax = ttk.Entry(ctrl_frame, textvariable=self.scaling_max_var, width=10)
        e_smax.grid(row=row, column=3, sticky="ew", padx=2, pady=2)
        ToolTip(e_smax, "Upper limit of q / 2θ range used for IRLS scaling.")
        row += 1

        # Cutoff
        ttk.Label(ctrl_frame, text="Cutoff Min:").grid(row=row, column=0, sticky="w")
        e_cmin = ttk.Entry(ctrl_frame, textvariable=self.cutoff_min_var, width=10)
        e_cmin.grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        ToolTip(e_cmin, "Optional cropping of x-axis data – lower bound.")

        ttk.Label(ctrl_frame, text="Cutoff Max:").grid(row=row, column=2, sticky="e")
        e_cmax = ttk.Entry(ctrl_frame, textvariable=self.cutoff_max_var, width=10)
        e_cmax.grid(row=row, column=3, sticky="ew", padx=2, pady=2)
        ToolTip(e_cmax, "Optional cropping of x-axis data – upper bound.")
        row += 1

        # Tip fraction
        ttk.Label(ctrl_frame, text="Patch Threshold (0–1):").grid(row=row, column=0, sticky="w")
        e_tip = ttk.Entry(ctrl_frame, textvariable=self.tip_frac_var, width=10)
        e_tip.grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        ToolTip(e_tip, "Fraction of saturated peak maximum intensity at which data points are replaced (i.e., 0.1 is 10% under the truncation max intensity value).")
        row += 1

        # Plot x-limits
        ttk.Label(ctrl_frame, text="Plot x-min:").grid(row=row, column=0, sticky="w")
        e_xmin = ttk.Entry(ctrl_frame, textvariable=self.xmin_var, width=10)
        e_xmin.grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        ToolTip(e_xmin, "Lower x-axis limit for plotting.")

        ttk.Label(ctrl_frame, text="x-max:").grid(row=row, column=2, sticky="e")
        e_xmax = ttk.Entry(ctrl_frame, textvariable=self.xmax_var, width=10)
        e_xmax.grid(row=row, column=3, sticky="ew", padx=2, pady=2)
        ToolTip(e_xmax, "Upper x-axis limit for plotting.")
        row += 1

        # IRLS controls
        ttk.Label(ctrl_frame, text="Max Scale Iters:").grid(row=row, column=0, sticky="w")
        e_iters = ttk.Entry(ctrl_frame, textvariable=self.max_iters_var, width=10)
        e_iters.grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        ToolTip(e_iters, "Maximum iterations of IRLS scaling.")

        ttk.Label(ctrl_frame, text="Scale Tolerance:").grid(row=row, column=2, sticky="e")
        e_tol = ttk.Entry(ctrl_frame, textvariable=self.scale_tol_var, width=10)
        e_tol.grid(row=row, column=3, sticky="ew", padx=2, pady=2)
        ToolTip(e_tol, "Convergence tolerance for IRLS scaling.")
        row += 1

        ttk.Label(ctrl_frame, text="Huber k:").grid(row=row, column=0, sticky="w")
        e_hk = ttk.Entry(ctrl_frame, textvariable=self.huber_k_var, width=10)
        e_hk.grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        ToolTip(e_hk, "Huber parameter controlling IRLS robustness.")
        row += 1

        # Export options
        ttk.Label(ctrl_frame, text="Output Suffix:").grid(row=row, column=0, sticky="w")
        e_suf = ttk.Entry(ctrl_frame, textvariable=self.suffix_var, width=18)
        e_suf.grid(row=row, column=1, columnspan=2, sticky="ew", padx=2, pady=2)
        ToolTip(e_suf, "Text appended to exported filenames.")
        cb_export_dir = ttk.Checkbutton(
            ctrl_frame, text="Choose Export Directory",
            variable=self.choose_export_dir_var,
            command=self._maybe_choose_export_dir
        )
        cb_export_dir.grid(row=row, column=3, sticky="w", padx=2, pady=2)
        ToolTip(cb_export_dir, "Enable custom export folder instead of saturated-file directory.")
        row += 1

        # Run + navigation
        btn_run = ttk.Button(
            ctrl_frame, text="Run Scaling & Healing",
            command=self.run_healing, style="Red.TButton"
        )
        btn_run.grid(row=row, column=0, columnspan=2, sticky="ew", padx=2, pady=6)
        ToolTip(btn_run, "Perform IRLS/attenuated/fixed scaling and apply tips-only correction.")

        self.btn_prev = ttk.Button(
            ctrl_frame, text="◀ Prev",
            command=self.prev_pair, style="Red.TButton"
        )
        self.btn_prev.grid(row=row, column=2, sticky="ew", padx=2, pady=6)
        ToolTip(self.btn_prev, "Go to previous file pair.")

        self.btn_next = ttk.Button(
            ctrl_frame, text="Next ▶",
            command=self.next_pair, style="Red.TButton"
        )
        self.btn_next.grid(row=row, column=3, sticky="ew", padx=2, pady=6)
        ToolTip(self.btn_next, "Go to next file pair.")
        row += 1

        # Export buttons
        btn_export_current = ttk.Button(
            ctrl_frame, text="Export Current Pair",
            command=self.export_current_pair, style="Red.TButton"
        )
        btn_export_current.grid(row=row, column=0, columnspan=2,
                                sticky="ew", padx=2, pady=4)
        ToolTip(btn_export_current, "Export the currently displayed restored dataset.")

        btn_export_all = ttk.Button(
            ctrl_frame, text="Export All",
            command=self.export_all_pairs, style="Red.TButton"
        )
        btn_export_all.grid(row=row, column=2, columnspan=2,
                            sticky="ew", padx=2, pady=4)
        ToolTip(btn_export_all, "Export restored files for all pairs.")
        row += 1

        # Scale convergence
        btn_scale_conv = ttk.Button(
            ctrl_frame, text="Scale Convergence (Current)",
            command=self.show_scale_convergence_current, style="Red.TButton"
        )
        btn_scale_conv.grid(row=row, column=0, columnspan=4,
                            sticky="ew", padx=2, pady=4)
        ToolTip(btn_scale_conv, "Display scale-convergence vs iteration for the current file pair.")
        row += 1

        # Current pair label
        self.current_pair_label = ttk.Label(ctrl_frame, text="Current pair: -")
        self.current_pair_label.grid(row=row, column=0, columnspan=4,
                                     sticky="w", padx=2, pady=2)
        row += 1

        # --------------------------------------------------------------
        # REPAIR LIST (right)
        # --------------------------------------------------------------

        #rep_frame = ttk.LabelFrame(top_frame, text="Repair / Healing Files")
        #rep_frame.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        rep_outer, rep_frame = create_centered_labelframe(
            top_frame, "Repair / Healing Files"
        )
        rep_outer.grid(row=0, column=2, sticky="nsew", padx=(8, 0))


        btn_load_rep = ttk.Button(
            rep_frame, text="Load Repair Files",
            command=self.load_repair_files, style="Red.TButton"
        )
        btn_load_rep.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)
        ToolTip(btn_load_rep, "Select unsaturated data files used to repair saturated peaks.")

        self.rep_listbox = tk.Listbox(
            rep_frame, selectmode=tk.EXTENDED, activestyle="dotbox",
            highlightthickness=0, borderwidth=0, exportselection=False
        )
        self.rep_listbox.config(selectforeground="white")
        self.rep_listbox.bind("<Delete>", self._delete_selected_repair)
        self.rep_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                              padx=(4, 0), pady=4)

        rep_scroll = ttk.Scrollbar(rep_frame, orient=tk.VERTICAL,
                                   command=self.rep_listbox.yview)
        rep_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.rep_listbox.config(yscrollcommand=rep_scroll.set)

        # Drag events
        self.rep_listbox.bind("<Button-1>", self._on_rep_click)
        self.rep_listbox.bind("<ButtonRelease-1>", self._on_rep_release)

        # --------------------------------------------------------------
        # PLOT FRAME
        # --------------------------------------------------------------

        plot_frame = ttk.Frame(self.master)
        plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True,
                        padx=10, pady=(0, 10))

        #self.fig = Figure(figsize=(8, 6))
        self.fig = Figure(
            figsize=(8 * PLOT_SCALE, 6 * PLOT_SCALE),
            dpi=100 * PLOT_SCALE
        )

        self.ax_top = self.fig.add_subplot(211)
        self.ax_bot = self.fig.add_subplot(212, sharex=self.ax_top)

        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # Track mouse motion
        self.canvas.mpl_connect("motion_notify_event", self._on_mouse_move)
        
        toolbar_frame = ttk.Frame(plot_frame)
        toolbar_frame.pack(side=tk.TOP, fill=tk.X)
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()


        # --------------------------------------------------------------
        # STATUS BAR (bottom)
        # --------------------------------------------------------------

        status_frame = ttk.Frame(self.master)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(status_frame,
                                      textvariable=self.status_var,
                                      anchor="w")
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

        self.scale_label = ttk.Label(status_frame,
                                     text="Scale (current): -")
        self.scale_label.pack(side=tk.RIGHT, padx=8)

        # Hover-help message
        self.help_label = ttk.Label(status_frame,
                                    text="Hover over buttons for ⓘ help",
                                    foreground="#555")
        self.help_label.pack(side=tk.RIGHT, padx=8)

    # -------------------------------------------------------------------------
    #                           LISTBOX MANAGEMENT
    # -------------------------------------------------------------------------
    def _refresh_listboxes(self):
        self.sat_listbox.delete(0, tk.END)
        for i, fn in enumerate(self.index_saturated, start=1):
            clean_fn = fn.replace(" ******(selected)******", "")
            if (i-1) == self.current_pair_idx:
                text = f"{i}. {clean_fn} ******(selected)******"
            else:
                text = f"{i}. {clean_fn}"
            self.sat_listbox.insert(tk.END, text)
    
        self.rep_listbox.delete(0, tk.END)
        for i, fn in enumerate(self.index_repair, start=1):
            clean_fn = fn.replace(" ******(selected)******", "")
            if (i-1) == self.current_pair_idx:
                text = f"{i}. {clean_fn} ******(selected)******"
            else:
                text = f"{i}. {clean_fn}"
            self.rep_listbox.insert(tk.END, text)

    def _on_sat_click(self, event):
        self._drag_start_index_sat = self.sat_listbox.nearest(event.y)

    def _on_sat_release(self, event):
        if self._drag_start_index_sat is None:
            return
        end = self.sat_listbox.nearest(event.y)
        start = self._drag_start_index_sat
        self._drag_start_index_sat = None
        if start == end:
            return
        item = self.index_saturated.pop(start)
        self.index_saturated.insert(end, item)
        self._refresh_listboxes()
        self.sat_listbox.selection_set(end)
        self.status_var.set("Reordered saturated files.")
        self._update_nav_buttons()

    def _on_rep_click(self, event):
        self._drag_start_index_rep = self.rep_listbox.nearest(event.y)

    def _on_rep_release(self, event):
        if self._drag_start_index_rep is None:
            return
        end = self.rep_listbox.nearest(event.y)
        start = self._drag_start_index_rep
        self._drag_start_index_rep = None
        if start == end:
            return
        item = self.index_repair.pop(start)
        self.index_repair.insert(end, item)
        self._refresh_listboxes()
        self.rep_listbox.selection_set(end)
        self.status_var.set("Reordered repair files.")
        self._update_nav_buttons()

    # -------------------------------------------------------------------------
    #                         FILE LOADING HANDLERS
    # -------------------------------------------------------------------------

    def load_saturated_files(self):
        files = filedialog.askopenfilenames(title="Select saturated (bad) files")
        if not files:
            return
    
        # Extract directory + basenames
        paths = list(files)
        dirpath = os.path.dirname(paths[0])
        basenames = [os.path.basename(p) for p in paths]
    
        # If this is the first time loading saturated files
        if self.dir_saturated is None:
            self.dir_saturated = dirpath
        else:
            # Prevent mixing files from different folders (optional safety)
            if dirpath != self.dir_saturated:
                messagebox.showerror(
                    "Error",
                    "All saturated files must come from the same directory.\n"
                    "Existing: %s\nNew: %s" % (self.dir_saturated, dirpath)
                )
                return
    
        # ✅ Append instead of replace
        self.index_saturated.extend(basenames)
    
        self._refresh_listboxes()
        self.status_var.set("Loaded %d saturated files." % len(self.index_saturated))
        self._update_nav_buttons()
        self.update_preview_plot()



    def load_repair_files(self):
        files = filedialog.askopenfilenames(title="Select repair (good) files")
        if not files:
            return
    
        paths = list(files)
        dirpath = os.path.dirname(paths[0])
        basenames = [os.path.basename(p) for p in paths]
    
        # First time?
        if self.dir_repair is None:
            self.dir_repair = dirpath
        else:
            if dirpath != self.dir_repair:
                messagebox.showerror(
                    "Error",
                    "All repair files must come from the same directory.\n"
                    "Existing: %s\nNew: %s" % (self.dir_repair, dirpath)
                )
                return
    
        # ✅ Append instead of replace
        self.index_repair.extend(basenames)
    
        self._refresh_listboxes()
        self.status_var.set("Loaded %d repair files." % len(self.index_repair))
        self._update_nav_buttons()
        self.update_preview_plot()

    # -------------------------------------------------------------------------
    #                              PARAM HELPERS
    # -------------------------------------------------------------------------

    def _parse_optional_float(self, s):
        s = s.strip()
        if s == "":
            return None
        try:
            return float(s)
        except Exception:
            return None

    def _get_cutoff_tuple(self):
        return (
            self._parse_optional_float(self.cutoff_min_var.get()),
            self._parse_optional_float(self.cutoff_max_var.get())
        )

    def _get_scaling_range_tuple(self):
        return (
            self._parse_optional_float(self.scaling_min_var.get()),
            self._parse_optional_float(self.scaling_max_var.get())
        )

    def _get_plot_xlim_tuple(self):
        return (
            self._parse_optional_float(self.xmin_var.get()),
            self._parse_optional_float(self.xmax_var.get())
        )

    # -------------------------------------------------------------------------
    #                              RUN HEALING
    # -------------------------------------------------------------------------

    def run_healing(self):

        if not self.index_saturated or not self.index_repair:
            messagebox.showerror(
                "Error",
                "Load both saturated and repair files."
            )
            return

        if len(self.index_saturated) != len(self.index_repair):
            messagebox.showerror(
                "Error",
                "Counts differ: saturated vs repair files.\n"
                "Reorder or adjust until they match."
            )
            return

        try:
            cutoff = self._get_cutoff_tuple()
            scaling_range = self._get_scaling_range_tuple()
            plot_xlim = self._get_plot_xlim_tuple()

            tip_under_pct = float(self.tip_frac_var.get())
            max_iter = int(self.max_iters_var.get())
            scale_tol = float(self.scale_tol_var.get())
            huber_k = float(self.huber_k_var.get())
            wavelength = float(self.wavelength_var.get())
            data_type = self.data_type_var.get()
            scaling_type = self.scaling_type_var.get().lower()
            fixed_scale = float(self.fixed_scale_var.get())

        except Exception as e:
            messagebox.showerror("Error", "Parameter error:\n%s" % e)
            return

        # Load data
        try:
            X_bad = load_matrix(self.dir_saturated, self.index_saturated, cutoff)
            X_good = load_matrix(self.dir_repair, self.index_repair, cutoff)
        except Exception as e:
            messagebox.showerror("Error", "Error loading data:\n%s" % e)
            return

        q_bad = X_bad[:, 0]
        q_good = X_good[:, 0]

        # Regrid repair data
        if (len(q_bad) != len(q_good)) or (not np.allclose(
                q_bad, q_good, rtol=1e-8, atol=1e-10)):
            X_good_regridded = np.zeros_like(X_bad)
            X_good_regridded[:, 0] = q_bad

            for c in range(1, X_good.shape[1]):
                y_good = X_good[:, c]
                y_interp = np.interp(q_bad, q_good, y_good,
                                     left=0.0, right=0.0)
                X_good_regridded[:, c] = y_interp

            X_good = X_good_regridded

        # Header from first saturated file
        try:
            _, header_text_bad, delim_bad = read_header_text(
                self.dir_saturated,
                self.index_saturated[0]
            )
        except Exception:
            header_text_bad = ""
            delim_bad = " "

        stype = scaling_type

        # SCALING
        if stype == "fixed":
            X_good_scaled = np.zeros_like(X_good)
            X_good_scaled[:, 0] = X_good[:, 0]
            ncols = X_good.shape[1] - 1
            scales = np.full(ncols, fixed_scale, dtype=float)
            scales_history = [[fixed_scale] for _ in range(ncols)]
            thresholds_from_scaling = np.full(ncols, np.nan)

            for c in range(1, X_good.shape[1]):
                X_good_scaled[:, c] = X_good[:, c] * fixed_scale

        elif stype == "attenuated":
            X_good_scaled, scales, thresholds_from_scaling, scales_history = \
                irls_scale_attenuated(
                    X_bad, X_good, scaling_range, tip_under_pct,
                    q_axis=q_bad, data_type_=data_type, wavelength_=wavelength,
                    max_iter=max_iter, tol=scale_tol,
                    huber_k_=huber_k, mad_floor=DEFAULT_MIN_MAD
                )

        else:
            X_good_scaled, scales, thresholds_from_scaling, scales_history = \
                irls_scale_normal(
                    X_bad, X_good, scaling_range, tip_under_pct,
                    max_iter=max_iter, tol=scale_tol,
                    huber_k_=huber_k, mad_floor=DEFAULT_MIN_MAD
                )

        # Tips-only restoration
        X_restored, Tips, thresholds = tips_restore_constant_threshold(
            X_bad, X_good_scaled, tip_under_pct
        )

        # Store
        self.X_bad = X_bad
        self.X_good = X_good
        self.X_good_scaled = X_good_scaled
        self.X_restored = X_restored
        self.Tips = Tips
        self.thresholds = thresholds
        self.scales = scales
        self.scales_history = scales_history
        self.q = q_bad
        self.header_text_bad = header_text_bad
        self.delim_bad = delim_bad
        self.plot_xlim = plot_xlim
        self.tip_under_pct_used = tip_under_pct
        self.scaling_type_used = stype

        self.current_pair_idx = 0
        self._update_nav_buttons()
        self._refresh_listboxes()
        self._update_current_pair_label()
        self.update_plot()
        self.healing_done = True

        nfiles = X_bad.shape[1] - 1
        self.status_var.set("Processing complete for %d pairs." % nfiles)
        if self.scales is not None and len(self.scales) > 0:
            self.scale_label.config(
                text="Scale (current): %.6g" % self.scales[0]

            )

    # -------------------------------------------------------------------------
    #                                  PLOTTING
    # -------------------------------------------------------------------------
        
    def update_preview_plot(self):
        """Show saturated + unscaled repair before scaling/healing."""
        self.ax_top.clear()
        self.ax_bot.clear()
    
        # Conditions
        if not self.index_saturated or not self.index_repair:
            self.ax_top.set_title("Load saturated and repair files to preview.")
            self.canvas.draw()
            return
    
        if len(self.index_saturated) != len(self.index_repair):
            self.ax_top.set_title("Mismatched file counts. Load equal numbers.")
            self.canvas.draw()
            return
    
        cutoff = self._get_cutoff_tuple()
    
        # Load current pair based on navigation index
        idx = self.current_pair_idx
        sat_file = self.index_saturated[idx]
        rep_file = self.index_repair[idx]
    
        try:
            X_bad = load_matrix(self.dir_saturated, [sat_file], cutoff)
            X_good = load_matrix(self.dir_repair, [rep_file], cutoff)
        except Exception as e:
            self.ax_top.set_title(f"Error loading preview: {e}")
            self.canvas.draw()
            return
    
        q = X_bad[:, 0]
        y_sat = X_bad[:, 1]
        y_rep = X_good[:, 1]
    
        # Top preview plot
        self.ax_top.set_title(f"Preview: Pair {idx+1} — Saturated + Unscaled Repair")
        self.ax_top.plot(q, y_sat, color="black", alpha=0.85, label="Saturated")
        self.ax_top.plot(q, y_rep, color="red", alpha=0.85, label="Repair (Unscaled)")
        self.ax_top.set_ylabel("Intensity")
        self.ax_top.legend()
    
        # Bottom plot placeholder
        self.ax_bot.set_title("Run scaling & healing to see restored data.")
        self.ax_bot.set_xlabel("q / 2θ")
    
        self.fig.tight_layout()
        self.canvas.draw()



    def update_plot(self):

        self.ax_top.clear()
        self.ax_bot.clear()

        if self.X_bad is None:
            self.ax_top.set_title("No data yet. Run scaling & healing.")
            self.canvas.draw()
            return

        col_idx = self.current_pair_idx + 1

        if col_idx < 1 or col_idx >= self.X_bad.shape[1]:
            self.canvas.draw()
            return

        q = self.q
        y_sat = self.X_bad[:, col_idx]
        y_rep = self.X_good_scaled[:, col_idx]

        thr = self.thresholds[self.current_pair_idx]
        xmask = build_xmask(q, self.plot_xlim)

        # # ---- TOP PLOT ----
        # self.ax_top.set_title("Saturated (black) & Repair (scaled, red)")
        # self.ax_top.plot(q[xmask], y_sat[xmask], color="black",
        #                  alpha=0.8, label="Saturated")
        # self.ax_top.plot(q[xmask], y_rep[xmask], color="red",
        #                  alpha=0.8, label="Scaled Repair")
        
        # ---- TOP PLOT ----
        self.ax_top.set_title("Saturated & Repair (Scaled)", fontsize=12, weight="bold", loc="center")
        
        # Main curves
        self.ax_top.plot(q[xmask], y_sat[xmask], color="black",
                         alpha=0.85, linewidth=1.4, label="Saturated")
        
        self.ax_top.plot(q[xmask], y_rep[xmask], color="red",
                         alpha=0.8, linewidth=1.4, label="Scaled Repair")
        
        # ---- PATCH THRESHOLD LINE ----
        patch_y = thr  # horizontal threshold (same as used in bottom plot)
        patch_line = self.ax_top.axhline(
            patch_y,
            color="blue",
            linestyle="--",
            linewidth=1.2,
            alpha=0.9,
            label="Patch Threshold"
        )
        
        # Ensure patch line is in legend
        handles, labels = self.ax_top.get_legend_handles_labels()
        self.ax_top.legend(handles, labels, loc="best", fontsize=10)
        
        self.ax_top.set_ylabel("Intensity", fontsize=11)


        self.ax_top.set_ylabel("Intensity")
        self.ax_top.legend(loc="best")

        # ---- BOTTOM PLOT ----
        self.ax_bot.set_title(
            "Restored (tips; threshold=%.2f×max)" %
            (1.0 - self.tip_under_pct_used)
        )

        proxies = add_scatter_and_blue_segments(
            self.ax_bot, q, y_sat, y_rep, thr, xmask
        )
        if proxies:
            self.ax_bot.legend(handles=proxies, loc="best")

        self.ax_bot.set_xlabel("q / 2θ")
        self.ax_bot.set_ylabel("Intensity")
        if self.plot_xlim[0] is not None or self.plot_xlim[1] is not None:
            self.ax_bot.set_xlim(
                left=self.plot_xlim[0], right=self.plot_xlim[1]
            )

        self.fig.tight_layout()
        self.canvas.draw()

        if self.scales is not None and 0 <= self.current_pair_idx < len(self.scales):
            self.scale_label.config(
                text="Scale (current): %.6g" %
                     self.scales[self.current_pair_idx]
            )

    # -------------------------------------------------------------------------
    #                             NAVIGATION
    # -------------------------------------------------------------------------

    def _update_nav_buttons(self):
        n = len(self.index_saturated)

        if n == 0 or n != len(self.index_repair):
            self.btn_prev.config(state="disabled")
            self.btn_next.config(state="disabled")
        else:
            if self.current_pair_idx <= 0:
                self.btn_prev.config(state="disabled")
            else:
                self.btn_prev.config(state="normal")

            if self.current_pair_idx >= n - 1:
                self.btn_next.config(state="disabled")
            else:
                self.btn_next.config(state="normal")

        self._update_current_pair_label()

    def _update_current_pair_label(self):
        n = len(self.index_saturated)
        if n == 0 or n != len(self.index_repair):
            self.current_pair_label.config(text="Current pair: -")
        else:
            self.current_pair_label.config(
                text="Current pair: %d / %d" %
                     (self.current_pair_idx + 1, n)
            )
    
    def prev_pair(self):
        if self.current_pair_idx > 0:
            self.current_pair_idx -= 1
            self._update_nav_buttons()
            self._refresh_listboxes()
    
            if self.healing_done:
                self.update_plot()
            else:
                self.update_preview_plot()

    
    def next_pair(self):
        n = len(self.index_saturated)
        if self.current_pair_idx < n - 1:
            self.current_pair_idx += 1
            self._update_nav_buttons()
            self._refresh_listboxes()
            
            if self.healing_done:
                self.update_plot()
            else:
                self.update_preview_plot()

    # -------------------------------------------------------------------------
    #                            EXPORT FUNCTIONS
    # -------------------------------------------------------------------------

    def _get_export_dir(self):
        if self.choose_export_dir_var.get():
            if not self.export_dir:
                d = filedialog.askdirectory(
                    title="Select export directory"
                )
                if not d:
                    return None
                self.export_dir = d
            return self.export_dir
        else:
            return self.dir_saturated

    def export_current_pair(self):
        if self.X_restored is None:
            messagebox.showerror("Error",
                                 "No restored data to export. Run scaling & healing first.")
            return

        idx = self.current_pair_idx
        if idx < 0 or idx >= len(self.index_saturated):
            return

        export_dir = self._get_export_dir()
        if export_dir is None:
            return

        suffix = self.suffix_var.get().strip()
        if suffix == "":
            suffix = DEFAULT_SUFFIX

        col_idx = idx + 1
        X_col = np.column_stack([self.X_restored[:, 0],
                                 self.X_restored[:, col_idx]])
        src_filename = self.index_saturated[idx]

        try:
            out_file = export_single_with_header(
                X_col, export_dir, src_filename, suffix,
                self.header_text_bad, self.delim_bad
            )
            self.status_var.set("Exported: %s" % out_file)
        except Exception as e:
            messagebox.showerror("Error",
                                 "Error exporting current pair:\n%s" % e)

    def export_all_pairs(self):
        if self.X_restored is None:
            messagebox.showerror("Error",
                                 "No restored data to export.")
            return

        export_dir = self._get_export_dir()
        if export_dir is None:
            return

        suffix = self.suffix_var.get().strip()
        if suffix == "":
            suffix = DEFAULT_SUFFIX

        try:
            export_matrix_with_header(
                self.X_restored, export_dir,
                self.index_saturated, suffix,
                self.header_text_bad, self.delim_bad
            )
            self.status_var.set("Exported all to: %s" % export_dir)
        except Exception as e:
            messagebox.showerror("Error",
                                 "Error exporting all pairs:\n%s" % e)

    # -------------------------------------------------------------------------
    #                       SCALE CONVERGENCE PLOT
    # -------------------------------------------------------------------------
    
    def show_scale_convergence_current(self):
        if self.scales_history is None or self.scales is None:
            messagebox.showinfo("Info",
                                "No scale convergence available.")
            return
    
        if self.scaling_type_used == "fixed":
            messagebox.showinfo("Info",
                                "Fixed scaling mode: no convergence history.")
            return
    
        idx = self.current_pair_idx
        if idx < 0 or idx >= len(self.scales_history):
            return
    
        hist = self.scales_history[idx]
        its = np.arange(len(hist))
    
        # ---- Create Tkinter popup window ----
        win = tk.Toplevel(self.master)
        win.title("Scale Convergence (Pair %d)" % (idx + 1))
    
        # ---- Create figure ----
        #fig = Figure(figsize=(5, 3))
        fig = Figure(
            figsize=(5 * PLOT_SCALE, 3 * PLOT_SCALE),
            dpi=100 * PLOT_SCALE
        )

        ax = fig.add_subplot(111)
    
        ax.plot(its, hist, marker='o', alpha=0.9)
        ax.set_title("Scale Convergence (Pair %d)" % (idx + 1))
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Scale s")
    
        fig.tight_layout()
    
        # ---- Embed in Tk canvas ----
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # ---- Converged value ----
        final_scale = hist[-1]
        
        frame = ttk.Frame(win)
        frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(frame, text="Converged Scale:").pack(side=tk.LEFT)
        
        scale_entry = ttk.Entry(frame, width=20)
        scale_entry.pack(side=tk.LEFT, padx=5)
        scale_entry.insert(0, f"{final_scale:.10g}")
        
        # Auto-select for easy copy
        scale_entry.select_range(0, tk.END)
        scale_entry.focus()
    
        # Optional: Add a close button
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=5)


    # -------------------------------------------------------------------------
    #                SCALING FIELD ENABLE/DISABLE LOGIC
    # -------------------------------------------------------------------------

    # def _update_scale_entry_states(self):
    #     stype = self.scaling_type_var.get().lower()

    #     if stype == "fixed":
    #         self.fixed_scale_entry.config(state="normal")
    #     else:
    #         self.fixed_scale_entry.config(state="disabled")

    #     if stype == "attenuated":
    #         self.wavelength_entry.config(state="normal")
    #     else:
    #         self.wavelength_entry.config(state="disabled")
    def _update_scale_entry_states(self):
        stype = self.scaling_type_var.get().lower()
    
        # --- Fixed scale entry ---
        if stype == "fixed":
            self.fixed_scale_entry.config(state="normal")
        else:
            self.fixed_scale_entry.config(state="disabled")
    
        # --- Wavelength entry ---
        if stype == "attenuated":
            self.wavelength_entry.config(state="normal")
        else:
            self.wavelength_entry.config(state="disabled")
    
        # --- Data type dropdown (new behavior) ---
        if stype == "attenuated":
            self.dtype_menu.config(state="normal")
        else:
            self.dtype_menu.config(state="disabled")


    def _maybe_choose_export_dir(self):
        if self.choose_export_dir_var.get():
            d = filedialog.askdirectory(title="Choose export directory")
            if d:
                self.export_dir = d
                self.status_var.set("Export directory: %s" % d)
            else:
                self.choose_export_dir_var.set(False)
        else:
            self.export_dir = None
            self.status_var.set("Exporting to saturated-file directory.")

# -----------------------------------------------------------------------------
#                                   MAIN
# -----------------------------------------------------------------------------
def main():
    global UI_SCALE, PLOT_SCALE

    root = tk.Tk()
    root.withdraw()

    # UI scale (resolution only)
    UI_SCALE = compute_ui_scale(root)

    # Plot scale (resolution + DPI)
    PLOT_SCALE = compute_plot_scale(root)

    # Apply plot scaling to matplotlib fonts
    plt.rcParams.update({
        "font.size":        14 * PLOT_SCALE,
        "axes.titlesize":   16 * PLOT_SCALE,
        "axes.labelsize":   14 * PLOT_SCALE,
        "xtick.labelsize":  12 * PLOT_SCALE,
        "ytick.labelsize":  12 * PLOT_SCALE,
        "legend.fontsize":  12 * PLOT_SCALE,
    })
    
    # Scale default Tk font
    base_font_size = max(8, int(10 * UI_SCALE))
    root.option_add("*Font", ("Segoe UI", base_font_size))

    # --------------------------------------------------------
    # NEW: Combobox font scaling (fixes dropdown text size)
    # --------------------------------------------------------
    style = ttk.Style(root)

    combo_font_size = max(8, int(10 * UI_SCALE))
    style.configure(
        "Custom.TCombobox",
        font=("Segoe UI", combo_font_size)
    )

    # Optional: scale the arrow so it doesn’t look tiny on 4K
    style.configure(
        "TCombobox",
        arrowsize=int(12 * UI_SCALE)
    )


    # Scale default Tk font
    base_font_size = max(8, int(10 * UI_SCALE))
    root.option_add("*Font", ("Segoe UI", base_font_size))

    # Splash
    splash = SplashScreen(master=root)
    root.after(5000, lambda: show_main_app(root))

    root.mainloop()



def show_main_app(root):
    # Show actual GUI
    app = PATCH(master=root)
    root.deiconify()  # Reveal main window



if __name__ == "__main__":
    main()

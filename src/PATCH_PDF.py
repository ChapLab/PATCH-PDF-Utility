# -*- coding: utf-8 -*-
"""
Created on Wed Dec  3 23:56:39 2025

@author: bsanc
"""

import sys
import os
import numpy as np
import matplotlib
matplotlib.use('TkAgg')

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
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
UI_SCALE = 1.0
PLOT_SCALE = 1.0


def compute_ui_scale(root):
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    scale = min(sw / 1920.0, sh / 1080.0)
    return max(0.75, min(scale, 1.4))


def compute_plot_scale(root):
    try:
        dpi = root.winfo_fpixels('1i')
        dpi_scale = dpi / 96.0
    except Exception:
        dpi_scale = 1.0
    plot_scale = (dpi_scale ** 0.5) * 0.85
    return max(0.85, min(plot_scale, 1.35))


plt.rcParams.update({
    "font.size": 14,
    "axes.titlesize": 16,
    "axes.labelsize": 14,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
    "legend.fontsize": 12
})


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# -----------------------------------------------------------------------------
# CONSTANTS & DEFAULTS
# -----------------------------------------------------------------------------

DEFAULT_DATA_TYPE = "Q_A-1"
DEFAULT_WAVELENGTH = 0.1

DEFAULT_SCALING_TYPE = "normal"
DEFAULT_FIXED_SCALE = 1.0

DEFAULT_SCALING_RANGE = (1.5, None)
DEFAULT_CUTOFF = (None, None)
DEFAULT_PATCH_FRAC_OF_MAX = 0.90
DEFAULT_PLOT_XLIM = (None, None)

DEFAULT_MAX_SCALE_ITERS = 50
DEFAULT_SCALE_TOL = 1e-7
DEFAULT_HUBER_K = 1.345
DEFAULT_MIN_MAD = 1e-12

DEFAULT_THRESHOLD_MODE = "manual"
DEFAULT_AUTO_THRESHOLD_MIN_FRAC = 0.5
DEFAULT_AUTO_THRESHOLD_MAX_FRAC = 1
DEFAULT_AUTO_THRESHOLD_STEP = 0.001
DEFAULT_AUTO_THRESHOLD_MIN_POINTS = 10

DEFAULT_SUFFIX = "_patched"
MIN_COS = 1e-3

HEADER_LINES_BY_EXT = {
    'iq': 26, 'gr': 26, 'qchi': 4, 'nmf': 0, 'pca': 0, 'dat': 0, 'chi': 4
}


# -----------------------------------------------------------------------------
# TOOLTIP CLASS
# -----------------------------------------------------------------------------

class ToolTip:
    def __init__(self, widget, text='widget info'):
        self.waittime = 650
        self.wraplength = 300
        self.widget = widget
        self.text = text
        self.id = None
        self.tw = None

        self.widget.bind("<Enter>", self._enter)
        self.widget.bind("<Leave>", self._leave)
        self.widget.bind("<ButtonPress>", self._leave)

    def _enter(self, event=None):
        self._schedule()

    def _leave(self, event=None):
        self._unschedule()
        self._hide()

    def _schedule(self):
        self._unschedule()
        self.id = self.widget.after(self.waittime, self._show)

    def _unschedule(self):
        if self.id is not None:
            self.widget.after_cancel(self.id)
            self.id = None

    def _show(self):
        if self.tw:
            return
        try:
            x, y, _, _ = self.widget.bbox("insert")
        except Exception:
            x = y = 0
        x += self.widget.winfo_rootx() + 50
        y += self.widget.winfo_rooty() + 25

        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.geometry(f"+{x}+{y}")

        label = tk.Label(
            self.tw,
            text=self.text,
            justify='left',
            background="#ffffe0",
            relief='solid',
            borderwidth=1,
            wraplength=self.wraplength
        )
        label.pack(ipadx=1)

    def _hide(self):
        if self.tw:
            self.tw.destroy()
            self.tw = None


# -----------------------------------------------------------------------------
# SPLASH
# -----------------------------------------------------------------------------

class SplashScreen(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)

        bg = "#f5f5f7"
        red = "#c62828"

        self.overrideredirect(True)
        self.configure(bg=bg)

        self.update_idletasks()
        w = int(600 * UI_SCALE)
        h = int(380 * UI_SCALE)
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        try:
            ico_path = resource_path("patch_logo.ico")
            self.iconbitmap(ico_path)
        except Exception:
            pass

        title_frame = tk.Frame(self, bg=bg)
        title_frame.pack(pady=(int(35 * UI_SCALE), int(10 * UI_SCALE)))

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
            tk.Label(title_frame, image=self.logo_img, bg=bg).pack(side="left", padx=10)
        except Exception:
            pass

        tk.Label(
            title_frame,
            text="PDF Patch",
            font=("Segoe UI", int(32 * UI_SCALE), "bold"),
            bg=bg,
            fg=red
        ).pack(side="left", padx=int(10 * UI_SCALE))

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
            bg=bg,
            fg="#333333",
            justify="center",
            wraplength=int(500 * UI_SCALE)
        ).pack(pady=(int(15 * UI_SCALE), int(10 * UI_SCALE)))

        self.after(2500, self.destroy)


# -----------------------------------------------------------------------------
# FILE LOADING / PARSE HELPERS
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

    q = q_all[i1:i2 + 1]

    X = np.zeros((len(q), len(index) + 1), dtype=float)
    X[:, 0] = q

    for k, fn in enumerate(index):
        dat = np.genfromtxt(os.path.join(dirpath, fn), skip_header=n_header)
        if dat.ndim == 1:
            dat = dat.reshape(1, -1)
        X[:, k + 1] = dat[i1:i2 + 1, 1]

    return X


def export_matrix_with_header(X, dirpath, index_bad, suffix,
                              header_text, delim,
                              float_fmt="%.8g"):
    for i in range(1, X.shape[1]):
        src = index_bad[i - 1]
        if '.' in src:
            base, ext = src.rsplit('.', 1)
        else:
            base, ext = src, "txt"

        out_name = f"{base}_{suffix}.{ext}"
        arr = np.column_stack([X[:, 0], X[:, i]])

        if delim == ',':
            body = "\n".join([("%s,%s" % (float_fmt, float_fmt)) % (x, y) for x, y in arr])
        else:
            body = "\n".join([("%s %s" % (float_fmt, float_fmt)) % (x, y) for x, y in arr])

        with open(os.path.join(dirpath, out_name), "w", encoding="utf-8") as f:
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

    out_name = f"{base}_{suffix}.{ext}"

    if delim == ',':
        body = "\n".join([("%s,%s" % (float_fmt, float_fmt)) % (x, y) for x, y in X_col])
    else:
        body = "\n".join([("%s %s" % (float_fmt, float_fmt)) % (x, y) for x, y in X_col])

    full_path = os.path.join(dirpath, out_name)
    with open(full_path, "w", encoding="utf-8") as f:
        if header_text:
            f.write(header_text)
            if not header_text.endswith("\n"):
                f.write("\n")
        f.write(body)

    return full_path


# -----------------------------------------------------------------------------
# MATH HELPERS
# -----------------------------------------------------------------------------

def safe_arcsin(x):
    return np.arcsin(np.clip(x, -1, 1))


def q_to_two_theta_rad(q, data_type_, wavelength_):
    if data_type_ == "two_theta":
        return np.deg2rad(q)
    arg = q * wavelength_ / (4 * np.pi)
    theta = safe_arcsin(arg)
    return 2 * theta


def cos_two_theta(q, data_type_, wavelength_):
    th = q_to_two_theta_rad(q, data_type_, wavelength_)
    return np.cos(th)


def find_q_bounds(q, qmin, qmax):
    i0 = np.searchsorted(q, qmin, side='left')
    i1 = np.searchsorted(q, qmax, side='right') - 1
    i0 = max(0, min(i0, len(q) - 1))
    i1 = max(0, min(i1, len(q) - 1))
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
    m[i0:i1 + 1] = True
    return m


def nonsaturated_mask_from_patch_frac(sat, patch_frac_of_max_):
    bmax = np.nanmax(sat)
    thr = patch_frac_of_max_ * bmax
    return sat < thr, thr


def build_xmask(q, xlim):
    m = np.ones_like(q, dtype=bool)
    if xlim[0] is not None:
        m &= q >= xlim[0]
    if xlim[1] is not None:
        m &= q <= xlim[1]
    return m


def get_x_axis_label(data_type):
    if data_type == "Q_A-1":
        return r"Q / $\mathrm{\AA^{-1}}$"
    if data_type == "Q_nm-1":
        return r"Q / $\mathrm{nm^{-1}}$"
    if data_type == "two_theta":
        return r"2$\theta$ / deg"
    return "X"


def compute_offset_curve(y_main, y_diff, frac=0.08):
    y_main = np.asarray(y_main, dtype=float)
    y_diff = np.asarray(y_diff, dtype=float)

    finite_main = y_main[np.isfinite(y_main)]
    finite_diff = y_diff[np.isfinite(y_diff)]

    if finite_main.size == 0:
        return y_diff

    if finite_main.size > 1:
        main_span = np.ptp(finite_main)
    else:
        main_span = max(abs(finite_main[0]), 1.0)

    if finite_diff.size > 1:
        diff_span = np.ptp(finite_diff)
    else:
        diff_span = 0.0

    pad = frac * max(main_span, 1.0)
    base = np.nanmin(finite_main) - pad

    if finite_diff.size == 0:
        return y_diff + base

    diff_mid = 0.5 * (np.nanmax(finite_diff) + np.nanmin(finite_diff))
    return y_diff - diff_mid + base - max(diff_span, pad)


def huber_weights(r, k=1.345, mad_floor=1e-12):
    mad = np.median(np.abs(r - np.median(r)))
    sigma = max(mad_floor, 1.4826 * mad)
    t = k * sigma
    a = np.abs(r)
    w = np.ones_like(r)
    big = a > t
    w[big] = t / a[big]
    return w, sigma, t


# -----------------------------------------------------------------------------
# THRESHOLD SCAN
# -----------------------------------------------------------------------------

def scan_threshold_least_squares(
    sat,
    rep,
    min_frac=DEFAULT_AUTO_THRESHOLD_MIN_FRAC,
    max_frac=DEFAULT_AUTO_THRESHOLD_MAX_FRAC,
    step=DEFAULT_AUTO_THRESHOLD_STEP,
    min_points=DEFAULT_AUTO_THRESHOLD_MIN_POINTS
):
    sat = np.asarray(sat, dtype=float)
    rep = np.asarray(rep, dtype=float)

    finite = np.isfinite(sat) & np.isfinite(rep)
    sat_f = sat[finite]
    rep_f = rep[finite]

    if sat_f.size == 0:
        return {
            "fractions": np.array([]),
            "lsq": np.array([]),
            "thresholds": np.array([]),
            "best_frac": DEFAULT_PATCH_FRAC_OF_MAX,
            "best_thr": np.nan
        }

    sat_max = np.nanmax(sat_f)
    fracs = np.arange(min_frac, max_frac + 0.5 * step, step)

    lsq_vals = []
    thr_vals = []

    for frac in fracs:
        thr = frac * sat_max
        unpatched_mask = sat_f < thr

        if np.count_nonzero(unpatched_mask) < min_points:
            lsq = np.nan
        else:
            resid = sat_f[unpatched_mask] - rep_f[unpatched_mask]
            lsq = np.mean(resid ** 2)

        lsq_vals.append(lsq)
        thr_vals.append(thr)

    lsq_vals = np.array(lsq_vals, dtype=float)
    thr_vals = np.array(thr_vals, dtype=float)

    valid = np.isfinite(lsq_vals)
    if np.any(valid):
        best_idx = np.nanargmin(lsq_vals)
        best_frac = float(fracs[best_idx])
        best_thr = float(thr_vals[best_idx])
    else:
        best_frac = float(DEFAULT_PATCH_FRAC_OF_MAX)
        best_thr = float(best_frac * sat_max)

    return {
        "fractions": np.array(fracs, dtype=float),
        "lsq": lsq_vals,
        "thresholds": thr_vals,
        "best_frac": best_frac,
        "best_thr": best_thr
    }


def threshold_scan_for_matrix(X_bad, X_good_scaled, threshold_mode, manual_patch_frac):
    ncols = X_bad.shape[1] - 1
    thresholds = np.zeros(ncols, dtype=float)
    threshold_fracs = np.zeros(ncols, dtype=float)
    threshold_history = []

    for c in range(1, X_bad.shape[1]):
        sat = X_bad[:, c]
        rep = X_good_scaled[:, c]

        if threshold_mode == "least_squares":
            hist = scan_threshold_least_squares(sat, rep)
            frac = hist["best_frac"]
            thr = hist["best_thr"]
        else:
            frac = manual_patch_frac
            sat_max = np.nanmax(sat)
            thr = frac * sat_max
            hist = {
                "fractions": np.array([]),
                "lsq": np.array([]),
                "thresholds": np.array([]),
                "best_frac": frac,
                "best_thr": thr
            }

        threshold_fracs[c - 1] = frac
        thresholds[c - 1] = thr
        threshold_history.append(hist)

    return threshold_fracs, thresholds, threshold_history


# -----------------------------------------------------------------------------
# SCALING
# -----------------------------------------------------------------------------

def irls_scale_normal(X_bad, X_good, scaling_range_, patch_frac_of_max_,
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

        nonsat, thr = nonsaturated_mask_from_patch_frac(bad, patch_frac_of_max_)
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


def irls_scale_attenuated(X_bad, X_good, scaling_range_, patch_frac_of_max_,
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

        nonsat, thr = nonsaturated_mask_from_patch_frac(bad, patch_frac_of_max_)
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
# RESTORATION
# -----------------------------------------------------------------------------

def restore_with_thresholds(X_bad, X_good_scaled, thresholds):
    out = np.array(X_bad, copy=True)
    tips = np.zeros_like(X_bad)
    q = X_bad[:, 0]

    for c in range(1, X_bad.shape[1]):
        sat = X_bad[:, c]
        rep = X_good_scaled[:, c]
        thr = thresholds[c - 1]

        mask = sat >= thr
        out[mask, c] = rep[mask]
        tips[mask, c] = rep[mask]

    tips[:, 0] = q
    return out, tips


def add_scatter_and_blue_segments(ax, q, y_sat, y_rep, thr, xmask, s=10, lw=1.0):
    qm = q[xmask]
    sat_m = y_sat[xmask]
    rep_m = y_rep[xmask]

    if len(qm) < 2:
        return []

    y_rest = np.where(sat_m >= thr, rep_m, sat_m)
    use_rep = sat_m >= thr

    ax.scatter(qm[~use_rep], y_rest[~use_rep], s=s, color='black', alpha=0.9)
    ax.scatter(qm[use_rep], y_rest[use_rep], s=s, color='red', alpha=0.9)

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
        lc = LineCollection(segs, colors='blue', linewidths=lw, alpha=0.85)
        ax.add_collection(lc)

        pts = np.vstack([
            np.column_stack([x0[good], y0[good]]),
            np.column_stack([x1[good], y1[good]])
        ])
        ax.update_datalim(pts)
        ax.autoscale_view()

    proxies = [
        Line2D([0], [0], marker='o', linestyle='None', color='black', label='Points (Saturated)'),
        Line2D([0], [0], marker='o', linestyle='None', color='red', label='Points (Repair)'),
        Line2D([0], [0], color='blue', lw=lw, label='Restored path')
    ]
    return proxies


# -----------------------------------------------------------------------------
# MAIN PATCH GUI CLASS
# -----------------------------------------------------------------------------

class PATCH(tk.Frame):
    def _refresh_listboxes(self):
        self.sat_listbox.delete(0, tk.END)
        for i, fn in enumerate(self.index_saturated, start=1):
            clean_fn = fn.replace(" ******(selected)******", "")
            text = f"{i}. {clean_fn}"
            if (i - 1) == self.current_pair_idx:
                text += " ******(selected)******"
            self.sat_listbox.insert(tk.END, text)

        self.rep_listbox.delete(0, tk.END)
        for i, fn in enumerate(self.index_repair, start=1):
            clean_fn = fn.replace(" ******(selected)******", "")
            text = f"{i}. {clean_fn}"
            if (i - 1) == self.current_pair_idx:
                text += " ******(selected)******"
            self.rep_listbox.insert(tk.END, text)

    def _update_nav_buttons(self):
        n = len(self.index_saturated)
        if n == 0 or n != len(self.index_repair):
            self.btn_prev.config(state="disabled")
            self.btn_next.config(state="disabled")
        else:
            self.btn_prev.config(state="normal" if self.current_pair_idx > 0 else "disabled")
            self.btn_next.config(state="normal" if self.current_pair_idx < n - 1 else "disabled")
        self._update_current_pair_label()

    def _update_current_pair_label(self):
        n = len(self.index_saturated)
        if n == 0 or n != len(self.index_repair):
            self.current_pair_label.config(text="Current pair: -")
        else:
            self.current_pair_label.config(text=f"Current pair: {self.current_pair_idx + 1} / {n}")

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

    def _update_scale_entry_states(self):
        stype = self.scaling_type_var.get().lower()

        if stype == "fixed":
            self.fixed_scale_entry.config(state="normal")
        else:
            self.fixed_scale_entry.config(state="disabled")

        if stype == "attenuated":
            if self.data_type_var.get() != "two_theta":
                self.wavelength_entry.config(state="normal")
            else:
                self.wavelength_entry.config(state="disabled")
            self.dtype_menu.config(state="readonly")
        else:
            self.wavelength_entry.config(state="disabled")
            self.dtype_menu.config(state="disabled")

        self._update_datatype_widgets()

    def _update_threshold_entry_state(self):
        mode = self.threshold_mode_var.get().lower()
        if mode == "manual":
            self.tip_entry.config(state="normal")
        else:
            self.tip_entry.config(state="disabled")

    def _update_threshold_entry_from_current_pair(self):
        if self.threshold_fracs is not None and 0 <= self.current_pair_idx < len(self.threshold_fracs):
            self.tip_frac_var.set(float(self.threshold_fracs[self.current_pair_idx]))

    def _update_datatype_widgets(self):
        dtype = self.data_type_var.get()
        if dtype == "Q_A-1":
            self.wavelength_label.config(text="Wavelength / Å :")
            if self.scaling_type_var.get().lower() == "attenuated":
                self.wavelength_entry.config(state="normal")
        elif dtype == "Q_nm-1":
            self.wavelength_label.config(text="Wavelength / nm :")
            if self.scaling_type_var.get().lower() == "attenuated":
                self.wavelength_entry.config(state="normal")
        elif dtype == "two_theta":
            self.wavelength_label.config(text="Wavelength:")
            self.wavelength_entry.config(state="disabled")

        if self.healing_done:
            self.update_plot()
        else:
            self.update_preview_plot()

    def _on_mouse_move(self, event):
        if event.inaxes and event.xdata is not None and event.ydata is not None:
            ax_name = "Top" if event.inaxes is self.ax_top else "Bottom"
            self.status_var.set(f"{ax_name} plot  |  x = {event.xdata:.4f}   y = {event.ydata:.4f}")
        else:
            if self.healing_done and self.X_bad is not None:
                nfiles = self.X_bad.shape[1] - 1
                self.status_var.set(f"Processing complete for {nfiles} pairs.")
            else:
                self.status_var.set("Load saturated and repair files to begin.")

    def _get_export_dir(self):
        if self.choose_export_dir_var.get():
            if not self.export_dir:
                d = filedialog.askdirectory(title="Select export directory")
                if not d:
                    return None
                self.export_dir = d
            return self.export_dir
        return self.dir_saturated

    def _update_restored_current_pair(self):
        if self.X_bad is None or self.X_good_scaled is None or self.thresholds is None:
            return

        c = self.current_pair_idx + 1
        thr = self.thresholds[self.current_pair_idx]
        sat = self.X_bad[:, c]
        rep = self.X_good_scaled[:, c]
        mask = sat >= thr

        self.X_restored[:, c] = sat
        self.X_restored[mask, c] = rep[mask]

        self.Tips[:, c] = 0.0
        self.Tips[mask, c] = rep[mask]

    def __init__(self, master=None):
        super().__init__(master)

        self.master = master
        self.master.title("PATCH")

        try:
            self.master.state('zoomed')
        except tk.TclError:
            self.master.attributes('-zoomed', True)

        try:
            ico_path = resource_path("patch_logo.ico")
            self.master.iconbitmap(ico_path)
        except Exception:
            pass

        self.master.configure(background="#f5f5f7")

        self.dir_saturated = None
        self.dir_repair = None

        self.index_saturated = []
        self.index_repair = []

        self.X_bad = None
        self.X_good = None
        self.X_good_scaled = None
        self.X_restored = None
        self.Tips = None
        self.thresholds = None
        self.threshold_fracs = None
        self.threshold_histories = None
        self.scales = None
        self.scales_history = None
        self.q = None

        self.header_text_bad = ""
        self.delim_bad = " "

        self.current_pair_idx = 0
        self.healing_done = False

        self.data_type_var = tk.StringVar(value=DEFAULT_DATA_TYPE)
        self.wavelength_var = tk.DoubleVar(value=DEFAULT_WAVELENGTH)
        self.scaling_type_var = tk.StringVar(value=DEFAULT_SCALING_TYPE)
        self.fixed_scale_var = tk.DoubleVar(value=DEFAULT_FIXED_SCALE)
        self.threshold_mode_var = tk.StringVar(value=DEFAULT_THRESHOLD_MODE)

        self.scaling_min_var = tk.StringVar(value="" if DEFAULT_SCALING_RANGE[0] is None else str(DEFAULT_SCALING_RANGE[0]))
        self.scaling_max_var = tk.StringVar(value="" if DEFAULT_SCALING_RANGE[1] is None else str(DEFAULT_SCALING_RANGE[1]))
        self.cutoff_min_var = tk.StringVar(value="" if DEFAULT_CUTOFF[0] is None else str(DEFAULT_CUTOFF[0]))
        self.cutoff_max_var = tk.StringVar(value="" if DEFAULT_CUTOFF[1] is None else str(DEFAULT_CUTOFF[1]))
        self.tip_frac_var = tk.DoubleVar(value=DEFAULT_PATCH_FRAC_OF_MAX)

        self.xmin_var = tk.StringVar(value="" if DEFAULT_PLOT_XLIM[0] is None else str(DEFAULT_PLOT_XLIM[0]))
        self.xmax_var = tk.StringVar(value="" if DEFAULT_PLOT_XLIM[1] is None else str(DEFAULT_PLOT_XLIM[1]))

        self.max_iters_var = tk.IntVar(value=DEFAULT_MAX_SCALE_ITERS)
        self.scale_tol_var = tk.DoubleVar(value=DEFAULT_SCALE_TOL)
        self.huber_k_var = tk.DoubleVar(value=DEFAULT_HUBER_K)

        self.suffix_var = tk.StringVar(value=DEFAULT_SUFFIX)
        self.choose_export_dir_var = tk.BooleanVar(value=False)
        self.export_dir = None

        self.status_var = tk.StringVar(value="Load saturated and repair files to begin.")

        self._drag_start_index_sat = None
        self._drag_start_index_rep = None

        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except tk.TclError:
            pass

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

        self._build_layout()
        self._update_scale_entry_states()
        self._update_threshold_entry_state()
        self._update_nav_buttons()

    def _build_layout(self):
        def create_centered_labelframe(parent, text):
            outer = ttk.Frame(parent)
            title_lbl = ttk.Label(
                outer,
                text=text,
                anchor="center",
                font=("Segoe UI", max(9, int(11 * UI_SCALE)), "bold")
            )
            title_lbl.pack(side="top", fill="x", pady=(0, 2))

            border = ttk.Frame(outer, relief="groove", borderwidth=2)
            border.pack(side="top", fill="both", expand=True, pady=(2, 0))
            return outer, border

        top_frame = ttk.Frame(self.master)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        top_frame.grid_columnconfigure(0, weight=1, uniform="col")
        top_frame.grid_columnconfigure(1, weight=1, uniform="col")
        top_frame.grid_columnconfigure(2, weight=1, uniform="col")

        sat_outer, sat_frame = create_centered_labelframe(top_frame, "Overexposed / Saturated Files")
        sat_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        btn_load_sat = ttk.Button(sat_frame, text="Load Saturated Files", command=self.load_saturated_files, style="Red.TButton")
        btn_load_sat.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)
        ToolTip(btn_load_sat, "Select one or more overexposed/saturated data files.")

        self.sat_listbox = tk.Listbox(
            sat_frame, selectmode=tk.EXTENDED, activestyle="dotbox",
            highlightthickness=0, borderwidth=0, exportselection=False
        )
        self.sat_listbox.config(selectforeground="white")
        self.sat_listbox.bind("<Delete>", self._delete_selected_saturated)
        self.sat_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0), pady=4)

        sat_scroll = ttk.Scrollbar(sat_frame, orient=tk.VERTICAL, command=self.sat_listbox.yview)
        sat_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.sat_listbox.config(yscrollcommand=sat_scroll.set)

        self.sat_listbox.bind("<Button-1>", self._on_sat_click)
        self.sat_listbox.bind("<ButtonRelease-1>", self._on_sat_release)

        ctrl_outer, ctrl_frame = create_centered_labelframe(top_frame, "Scaling & Patching Settings")
        ctrl_outer.grid(row=0, column=1, sticky="nsew", padx=8)

        for col in range(4):
            ctrl_frame.grid_columnconfigure(col, weight=1)

        row = 0
        ttk.Label(ctrl_frame, text="Data Type:").grid(row=row, column=0, sticky="w")
        self.dtype_menu = ttk.Combobox(
            ctrl_frame,
            textvariable=self.data_type_var,
            values=["Q_A-1", "Q_nm-1", "two_theta"],
            state="readonly",
            style="Custom.TCombobox"
        )
        self.dtype_menu.bind("<<ComboboxSelected>>", lambda e: self._update_datatype_widgets())
        self.dtype_menu.grid(row=row, column=1, sticky="ew", padx=2, pady=2)

        self.wavelength_label = ttk.Label(ctrl_frame, text="Wavelength / Å :")
        self.wavelength_label.grid(row=row, column=2, sticky="w")

        self.wavelength_entry = ttk.Entry(ctrl_frame, textvariable=self.wavelength_var, width=8)
        self.wavelength_entry.grid(row=row, column=3, sticky="ew", padx=2, pady=2)
        row += 1

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

        ttk.Label(ctrl_frame, text="Fixed Scale:").grid(row=row, column=2, sticky="w")
        self.fixed_scale_entry = ttk.Entry(ctrl_frame, textvariable=self.fixed_scale_var, width=10)
        self.fixed_scale_entry.grid(row=row, column=3, sticky="ew", padx=2, pady=2)
        row += 1

        ttk.Label(ctrl_frame, text="Scaling Range Min:").grid(row=row, column=0, sticky="w")
        ttk.Entry(ctrl_frame, textvariable=self.scaling_min_var, width=10).grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        ttk.Label(ctrl_frame, text="Scaling Range Max:").grid(row=row, column=2, sticky="e")
        ttk.Entry(ctrl_frame, textvariable=self.scaling_max_var, width=10).grid(row=row, column=3, sticky="ew", padx=2, pady=2)
        row += 1

        ttk.Label(ctrl_frame, text="Cutoff Min:").grid(row=row, column=0, sticky="w")
        ttk.Entry(ctrl_frame, textvariable=self.cutoff_min_var, width=10).grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        ttk.Label(ctrl_frame, text="Cutoff Max:").grid(row=row, column=2, sticky="e")
        ttk.Entry(ctrl_frame, textvariable=self.cutoff_max_var, width=10).grid(row=row, column=3, sticky="ew", padx=2, pady=2)
        row += 1

        ttk.Label(ctrl_frame, text="Threshold Mode:").grid(row=row, column=0, sticky="w")
        self.threshold_mode_menu = ttk.Combobox(
            ctrl_frame,
            textvariable=self.threshold_mode_var,
            values=["manual", "least_squares"],
            state="readonly",
            style="Custom.TCombobox"
        )
        self.threshold_mode_menu.grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        self.threshold_mode_menu.bind("<<ComboboxSelected>>", lambda e: self._update_threshold_entry_state())

        ttk.Label(ctrl_frame, text="Patch Threshold (0–1):").grid(row=row, column=2, sticky="w")
        self.tip_entry = ttk.Entry(ctrl_frame, textvariable=self.tip_frac_var, width=10)
        self.tip_entry.grid(row=row, column=3, sticky="ew", padx=2, pady=2)
        ToolTip(
            self.tip_entry,
            "Fraction of the saturated peak maximum intensity above which data points are replaced "
            "(e.g. 0.90 means patch above 90% of the maximum intensity)."
        )
        row += 1

        ttk.Label(ctrl_frame, text="Plot x-min:").grid(row=row, column=0, sticky="w")
        ttk.Entry(ctrl_frame, textvariable=self.xmin_var, width=10).grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        ttk.Label(ctrl_frame, text="x-max:").grid(row=row, column=2, sticky="e")
        ttk.Entry(ctrl_frame, textvariable=self.xmax_var, width=10).grid(row=row, column=3, sticky="ew", padx=2, pady=2)
        row += 1

        ttk.Label(ctrl_frame, text="Max Scale Iters:").grid(row=row, column=0, sticky="w")
        ttk.Entry(ctrl_frame, textvariable=self.max_iters_var, width=10).grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        ttk.Label(ctrl_frame, text="Scale Tolerance:").grid(row=row, column=2, sticky="e")
        ttk.Entry(ctrl_frame, textvariable=self.scale_tol_var, width=10).grid(row=row, column=3, sticky="ew", padx=2, pady=2)
        row += 1

        ttk.Label(ctrl_frame, text="Huber k:").grid(row=row, column=0, sticky="w")
        ttk.Entry(ctrl_frame, textvariable=self.huber_k_var, width=10).grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        row += 1

        ttk.Label(ctrl_frame, text="Output Suffix:").grid(row=row, column=0, sticky="w")
        ttk.Entry(ctrl_frame, textvariable=self.suffix_var, width=18).grid(row=row, column=1, columnspan=2, sticky="ew", padx=2, pady=2)

        cb_export_dir = ttk.Checkbutton(
            ctrl_frame, text="Choose Export Directory",
            variable=self.choose_export_dir_var,
            command=self._maybe_choose_export_dir
        )
        cb_export_dir.grid(row=row, column=3, sticky="w", padx=2, pady=2)
        row += 1

        ttk.Button(ctrl_frame, text="Run Scaling & Healing", command=self.run_healing, style="Red.TButton").grid(
            row=row, column=0, columnspan=2, sticky="ew", padx=2, pady=6
        )

        self.btn_prev = ttk.Button(ctrl_frame, text="◀ Prev", command=self.prev_pair, style="Red.TButton")
        self.btn_prev.grid(row=row, column=2, sticky="ew", padx=2, pady=6)

        self.btn_next = ttk.Button(ctrl_frame, text="Next ▶", command=self.next_pair, style="Red.TButton")
        self.btn_next.grid(row=row, column=3, sticky="ew", padx=2, pady=6)
        row += 1

        ttk.Button(ctrl_frame, text="Export Current Pair", command=self.export_current_pair, style="Red.TButton").grid(
            row=row, column=0, columnspan=2, sticky="ew", padx=2, pady=4
        )
        ttk.Button(ctrl_frame, text="Export All", command=self.export_all_pairs, style="Red.TButton").grid(
            row=row, column=2, columnspan=2, sticky="ew", padx=2, pady=4
        )
        row += 1

        ttk.Button(ctrl_frame, text="Scale Convergence (Current)", command=self.show_scale_convergence_current, style="Red.TButton").grid(
            row=row, column=0, columnspan=2, sticky="ew", padx=2, pady=4
        )
        ttk.Button(ctrl_frame, text="Threshold Convergence (Current)", command=self.show_threshold_convergence_current, style="Red.TButton").grid(
            row=row, column=2, columnspan=2, sticky="ew", padx=2, pady=4
        )
        row += 1

        self.current_pair_label = ttk.Label(ctrl_frame, text="Current pair: -")
        self.current_pair_label.grid(row=row, column=0, columnspan=4, sticky="w", padx=2, pady=2)

        rep_outer, rep_frame = create_centered_labelframe(top_frame, "Repair / Healing Files")
        rep_outer.grid(row=0, column=2, sticky="nsew", padx=(8, 0))

        ttk.Button(rep_frame, text="Load Repair Files", command=self.load_repair_files, style="Red.TButton").pack(
            side=tk.TOP, fill=tk.X, padx=4, pady=4
        )

        self.rep_listbox = tk.Listbox(
            rep_frame, selectmode=tk.EXTENDED, activestyle="dotbox",
            highlightthickness=0, borderwidth=0, exportselection=False
        )
        self.rep_listbox.config(selectforeground="white")
        self.rep_listbox.bind("<Delete>", self._delete_selected_repair)
        self.rep_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0), pady=4)

        rep_scroll = ttk.Scrollbar(rep_frame, orient=tk.VERTICAL, command=self.rep_listbox.yview)
        rep_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.rep_listbox.config(yscrollcommand=rep_scroll.set)

        self.rep_listbox.bind("<Button-1>", self._on_rep_click)
        self.rep_listbox.bind("<ButtonRelease-1>", self._on_rep_release)

        plot_frame = ttk.Frame(self.master)
        plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.fig = Figure(figsize=(8 * PLOT_SCALE, 6 * PLOT_SCALE), dpi=100 * PLOT_SCALE)
        self.ax_top = self.fig.add_subplot(211)
        self.ax_bot = self.fig.add_subplot(212, sharex=self.ax_top)

        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas.mpl_connect("motion_notify_event", self._on_mouse_move)

        toolbar_frame = ttk.Frame(plot_frame)
        toolbar_frame.pack(side=tk.TOP, fill=tk.X)
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()

        status_frame = ttk.Frame(self.master)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor="w")
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

        self.scale_label = ttk.Label(status_frame, text="Scale (current): -")
        self.scale_label.pack(side=tk.RIGHT, padx=8)

        self.threshold_label = ttk.Label(status_frame, text="Threshold (current): -")
        self.threshold_label.pack(side=tk.RIGHT, padx=8)

    # -------------------------------------------------------------------------
    # FILE LOADING
    # -------------------------------------------------------------------------

    def load_saturated_files(self):
        files = filedialog.askopenfilenames(title="Select saturated (bad) files")
        if not files:
            return

        paths = list(files)
        dirpath = os.path.dirname(paths[0])
        basenames = [os.path.basename(p) for p in paths]

        if self.dir_saturated is None:
            self.dir_saturated = dirpath
        elif dirpath != self.dir_saturated:
            messagebox.showerror(
                "Error",
                f"All saturated files must come from the same directory.\nExisting: {self.dir_saturated}\nNew: {dirpath}"
            )
            return

        self.index_saturated.extend(basenames)
        self._refresh_listboxes()
        self._update_nav_buttons()
        self.healing_done = False
        self.status_var.set(f"Loaded {len(self.index_saturated)} saturated files.")
        self.update_preview_plot()

    def load_repair_files(self):
        files = filedialog.askopenfilenames(title="Select repair (good) files")
        if not files:
            return

        paths = list(files)
        dirpath = os.path.dirname(paths[0])
        basenames = [os.path.basename(p) for p in paths]

        if self.dir_repair is None:
            self.dir_repair = dirpath
        elif dirpath != self.dir_repair:
            messagebox.showerror(
                "Error",
                f"All repair files must come from the same directory.\nExisting: {self.dir_repair}\nNew: {dirpath}"
            )
            return

        self.index_repair.extend(basenames)
        self._refresh_listboxes()
        self._update_nav_buttons()
        self.healing_done = False
        self.status_var.set(f"Loaded {len(self.index_repair)} repair files.")
        self.update_preview_plot()

    # -------------------------------------------------------------------------
    # MAIN PROCESSING
    # -------------------------------------------------------------------------

    def run_healing(self):
        if not self.index_saturated or not self.index_repair:
            messagebox.showerror("Error", "Load both saturated and repair files.")
            return

        if len(self.index_saturated) != len(self.index_repair):
            messagebox.showerror("Error", "Counts differ: saturated vs repair files.")
            return

        try:
            cutoff = self._get_cutoff_tuple()
            scaling_range = self._get_scaling_range_tuple()
            plot_xlim = self._get_plot_xlim_tuple()

            patch_frac_of_max = float(self.tip_frac_var.get())
            max_iter = int(self.max_iters_var.get())
            scale_tol = float(self.scale_tol_var.get())
            huber_k = float(self.huber_k_var.get())
            wavelength = float(self.wavelength_var.get())
            data_type = self.data_type_var.get()
            scaling_type = self.scaling_type_var.get().lower()
            threshold_mode = self.threshold_mode_var.get().lower()
            fixed_scale = float(self.fixed_scale_var.get())
        except Exception as e:
            messagebox.showerror("Error", f"Parameter error:\n{e}")
            return

        try:
            X_bad = load_matrix(self.dir_saturated, self.index_saturated, cutoff)
            X_good = load_matrix(self.dir_repair, self.index_repair, cutoff)
        except Exception as e:
            messagebox.showerror("Error", f"Error loading data:\n{e}")
            return

        q_bad = X_bad[:, 0]
        q_good = X_good[:, 0]

        if (len(q_bad) != len(q_good)) or (not np.allclose(q_bad, q_good, rtol=1e-8, atol=1e-10)):
            X_good_regridded = np.zeros_like(X_bad)
            X_good_regridded[:, 0] = q_bad
            for c in range(1, X_good.shape[1]):
                y_interp = np.interp(q_bad, q_good, X_good[:, c], left=0.0, right=0.0)
                X_good_regridded[:, c] = y_interp
            X_good = X_good_regridded

        try:
            _, header_text_bad, delim_bad = read_header_text(self.dir_saturated, self.index_saturated[0])
        except Exception:
            header_text_bad = ""
            delim_bad = " "

        if scaling_type == "fixed":
            X_good_scaled = np.zeros_like(X_good)
            X_good_scaled[:, 0] = X_good[:, 0]
            ncols = X_good.shape[1] - 1
            scales = np.full(ncols, fixed_scale, dtype=float)
            scales_history = [[fixed_scale] for _ in range(ncols)]
            for c in range(1, X_good.shape[1]):
                X_good_scaled[:, c] = X_good[:, c] * fixed_scale
        elif scaling_type == "attenuated":
            X_good_scaled, scales, _, scales_history = irls_scale_attenuated(
                X_bad, X_good, scaling_range, patch_frac_of_max,
                q_axis=q_bad, data_type_=data_type, wavelength_=wavelength,
                max_iter=max_iter, tol=scale_tol,
                huber_k_=huber_k, mad_floor=DEFAULT_MIN_MAD
            )
        else:
            X_good_scaled, scales, _, scales_history = irls_scale_normal(
                X_bad, X_good, scaling_range, patch_frac_of_max,
                max_iter=max_iter, tol=scale_tol,
                huber_k_=huber_k, mad_floor=DEFAULT_MIN_MAD
            )

        threshold_fracs, thresholds, threshold_histories = threshold_scan_for_matrix(
            X_bad, X_good_scaled, threshold_mode, patch_frac_of_max
        )

        X_restored, Tips = restore_with_thresholds(X_bad, X_good_scaled, thresholds)

        self.X_bad = X_bad
        self.X_good = X_good
        self.X_good_scaled = X_good_scaled
        self.X_restored = X_restored
        self.Tips = Tips
        self.thresholds = thresholds
        self.threshold_fracs = threshold_fracs
        self.threshold_histories = threshold_histories
        self.scales = scales
        self.scales_history = scales_history
        self.q = q_bad
        self.header_text_bad = header_text_bad
        self.delim_bad = delim_bad
        self.plot_xlim = plot_xlim
        self.scaling_type_used = scaling_type
        self.threshold_mode_used = threshold_mode

        self.current_pair_idx = 0
        self._update_threshold_entry_from_current_pair()
        self._refresh_listboxes()
        self._update_nav_buttons()
        self.healing_done = True
        self.update_plot()

        nfiles = X_bad.shape[1] - 1
        self.status_var.set(f"Processing complete for {nfiles} pairs.")

    # -------------------------------------------------------------------------
    # PLOTTING
    # -------------------------------------------------------------------------

    def update_preview_plot(self):
        self.ax_top.clear()
        self.ax_bot.clear()

        xlab = get_x_axis_label(self.data_type_var.get())

        if not self.index_saturated or not self.index_repair:
            self.ax_top.set_title("Load saturated and repair files to preview.")
            self.ax_bot.set_xlabel(xlab)
            self.canvas.draw_idle()
            return

        if len(self.index_saturated) != len(self.index_repair):
            self.ax_top.set_title("Mismatched file counts. Load equal numbers.")
            self.ax_bot.set_xlabel(xlab)
            self.canvas.draw_idle()
            return

        cutoff = self._get_cutoff_tuple()
        idx = self.current_pair_idx

        try:
            X_bad = load_matrix(self.dir_saturated, [self.index_saturated[idx]], cutoff)
            X_good = load_matrix(self.dir_repair, [self.index_repair[idx]], cutoff)
        except Exception as e:
            self.ax_top.set_title(f"Error loading preview: {e}")
            self.canvas.draw_idle()
            return

        q = X_bad[:, 0]
        y_sat = X_bad[:, 1]
        y_rep = X_good[:, 1]

        self.ax_top.set_title(f"Preview: Pair {idx + 1} — Saturated + Unscaled Repair")
        self.ax_top.plot(q, y_sat, color="black", alpha=0.85, label="Saturated")
        self.ax_top.plot(q, y_rep, color="red", alpha=0.85, label="Repair (Unscaled)")
        self.ax_top.set_ylabel("Intensity")
        self.ax_top.set_xlabel(xlab)
        self.ax_top.legend()

        self.ax_bot.set_title("Run scaling & healing to see restored data.")
        self.ax_bot.set_xlabel(xlab)
        self.ax_bot.set_ylabel("Intensity")

        self.fig.tight_layout()
        self.canvas.draw_idle()

    def update_plot(self):
        self.ax_top.clear()
        self.ax_bot.clear()

        if self.X_bad is None:
            self.ax_top.set_title("No data yet. Run scaling & healing.")
            self.canvas.draw_idle()
            return

        col_idx = self.current_pair_idx + 1
        q = self.q
        y_sat = self.X_bad[:, col_idx]
        y_rep = self.X_good_scaled[:, col_idx]
        y_rest = self.X_restored[:, col_idx]

        thr = self.thresholds[self.current_pair_idx]
        frac = self.threshold_fracs[self.current_pair_idx]
        xmask = build_xmask(q, self.plot_xlim)
        xlab = get_x_axis_label(self.data_type_var.get())

        y_diff = y_rep - y_rest
        y_diff_offset = compute_offset_curve(y_rest[xmask], y_diff[xmask], frac=0.08)
        diff_zero_offset = compute_offset_curve(y_rest[xmask], np.zeros_like(y_diff[xmask]), frac=0.08)

        mode_txt = "manual" if self.threshold_mode_used == "manual" else "least_squares"
        self.ax_top.set_title(
            f"Saturated & Repair (Scaled) | Threshold mode: {mode_txt} | frac={frac:.4f}",
            fontsize=12, weight="bold", loc="center"
        )

        self.ax_top.plot(q[xmask], y_sat[xmask], color="black", alpha=0.85, linewidth=1.4, label="Saturated")
        self.ax_top.plot(q[xmask], y_rep[xmask], color="red", alpha=0.8, linewidth=1.4, label="Scaled Repair")
        self.ax_top.axhline(thr, color="blue", linestyle="--", linewidth=1.2, alpha=0.9, label="Patch Threshold")
        self.ax_top.set_ylabel("Intensity")
        self.ax_top.set_xlabel(xlab)
        self.ax_top.legend(loc="best")

        self.ax_bot.set_title("Restored Data", fontsize=12, weight="bold", loc="center")

        proxies = add_scatter_and_blue_segments(self.ax_bot, q, y_sat, y_rep, thr, xmask)

        self.ax_bot.axhline(thr, color="blue", linestyle="--", linewidth=1.2, alpha=0.9)
        self.ax_bot.plot(q[xmask], y_diff_offset, color="green", linewidth=1.2, alpha=0.95, label="Difference (offset)")
        self.ax_bot.plot(q[xmask], diff_zero_offset, color="green", linestyle=":", linewidth=1.0, alpha=0.7, label="Difference baseline")

        if proxies:
            proxies = proxies + [
                Line2D([0], [0], color='blue', linestyle='--', lw=1.2, label='Patch Threshold'),
                Line2D([0], [0], color='green', lw=1.2, label='Difference (offset)')
            ]
            self.ax_bot.legend(handles=proxies, loc="best")

        self.ax_bot.set_xlabel(xlab)
        self.ax_bot.set_ylabel("Intensity")

        if self.plot_xlim[0] is not None or self.plot_xlim[1] is not None:
            self.ax_bot.set_xlim(left=self.plot_xlim[0], right=self.plot_xlim[1])

        self.fig.tight_layout()
        self.canvas.draw_idle()

        if self.scales is not None and 0 <= self.current_pair_idx < len(self.scales):
            self.scale_label.config(text=f"Scale (current): {self.scales[self.current_pair_idx]:.6g}")

        self.threshold_label.config(text=f"Threshold (current): frac={frac:.6g}  y={thr:.6g}")

    # -------------------------------------------------------------------------
    # NAVIGATION
    # -------------------------------------------------------------------------

    def prev_pair(self):
        if self.current_pair_idx > 0:
            self.current_pair_idx -= 1
            self._update_threshold_entry_from_current_pair()
            self._update_nav_buttons()
            self._refresh_listboxes()
            if self.healing_done:
                self.update_plot()
            else:
                self.update_preview_plot()

    def next_pair(self):
        if self.current_pair_idx < len(self.index_saturated) - 1:
            self.current_pair_idx += 1
            self._update_threshold_entry_from_current_pair()
            self._update_nav_buttons()
            self._refresh_listboxes()
            if self.healing_done:
                self.update_plot()
            else:
                self.update_preview_plot()

    # -------------------------------------------------------------------------
    # EXPORT
    # -------------------------------------------------------------------------

    def export_current_pair(self):
        if self.X_restored is None:
            messagebox.showerror("Error", "No restored data to export. Run scaling & healing first.")
            return

        idx = self.current_pair_idx
        export_dir = self._get_export_dir()
        if export_dir is None:
            return

        suffix = self.suffix_var.get().strip() or DEFAULT_SUFFIX
        col_idx = idx + 1
        X_col = np.column_stack([self.X_restored[:, 0], self.X_restored[:, col_idx]])
        src_filename = self.index_saturated[idx]

        try:
            out_file = export_single_with_header(
                X_col, export_dir, src_filename, suffix,
                self.header_text_bad, self.delim_bad
            )
            self.status_var.set(f"Exported: {out_file}")
        except Exception as e:
            messagebox.showerror("Error", f"Error exporting current pair:\n{e}")

    def export_all_pairs(self):
        if self.X_restored is None:
            messagebox.showerror("Error", "No restored data to export.")
            return

        export_dir = self._get_export_dir()
        if export_dir is None:
            return

        suffix = self.suffix_var.get().strip() or DEFAULT_SUFFIX

        try:
            export_matrix_with_header(
                self.X_restored, export_dir,
                self.index_saturated, suffix,
                self.header_text_bad, self.delim_bad
            )
            self.status_var.set(f"Exported all to: {export_dir}")
        except Exception as e:
            messagebox.showerror("Error", f"Error exporting all pairs:\n{e}")

    # -------------------------------------------------------------------------
    # CONVERGENCE WINDOWS
    # -------------------------------------------------------------------------

    def show_scale_convergence_current(self):
        if self.scales_history is None or self.scales is None:
            messagebox.showinfo("Info", "No scale convergence available.")
            return

        if self.scaling_type_used == "fixed":
            messagebox.showinfo("Info", "Fixed scaling mode: no convergence history.")
            return

        idx = self.current_pair_idx
        hist = self.scales_history[idx]
        its = np.arange(len(hist))

        win = tk.Toplevel(self.master)
        win.title(f"Scale Convergence (Pair {idx + 1})")

        fig = Figure(figsize=(5 * PLOT_SCALE, 3 * PLOT_SCALE), dpi=100 * PLOT_SCALE)
        ax = fig.add_subplot(111)

        ax.plot(its, hist, marker='o', alpha=0.9)
        ax.set_title(f"Scale Convergence (Pair {idx + 1})")
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Scale s")
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        toolbar_frame = ttk.Frame(win)
        toolbar_frame.pack(fill=tk.X)
        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
        toolbar.update()

        final_scale = hist[-1]

        frame = ttk.Frame(win)
        frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(frame, text="Converged Scale:").pack(side=tk.LEFT)
        scale_entry = ttk.Entry(frame, width=20)
        scale_entry.pack(side=tk.LEFT, padx=5)
        scale_entry.insert(0, f"{final_scale:.10g}")
        scale_entry.select_range(0, tk.END)
        scale_entry.focus()

        ttk.Button(win, text="Close", command=win.destroy).pack(pady=5)

    def show_threshold_convergence_current(self):
        if self.threshold_histories is None or self.threshold_fracs is None:
            messagebox.showinfo("Info", "No threshold scan available.")
            return

        idx = self.current_pair_idx
        hist = self.threshold_histories[idx]
        fracs = hist.get("fractions", np.array([]))
        lsq = hist.get("lsq", np.array([]))

        if fracs.size == 0 or lsq.size == 0:
            messagebox.showinfo("Info", "Threshold scan is only available when Threshold Mode = least_squares.")
            return

        win = tk.Toplevel(self.master)
        win.title(f"Threshold Convergence (Pair {idx + 1})")

        fig = Figure(figsize=(5.5 * PLOT_SCALE, 3.5 * PLOT_SCALE), dpi=100 * PLOT_SCALE)
        ax = fig.add_subplot(111)

        valid = np.isfinite(lsq)
        # ax.plot(fracs[valid], lsq[valid], marker='o', markersize=2, linewidth=1.0, alpha=0.9)
        # ax.axvline(self.threshold_fracs[idx], linestyle='--', linewidth=1.0)
        # ax.set_title(f"Threshold Scan (Pair {idx + 1})")
        # ax.set_xlabel("Threshold fraction of max")
        # ax.set_ylabel("Least squares")
        
        valid = np.isfinite(lsq) & (lsq > 0)
        
        ax.plot(fracs[valid], lsq[valid], marker='o', markersize=2, linewidth=1.0, alpha=0.9)
        ax.set_yscale('log')  # <-- THIS is the key line
        
        ax.axvline(self.threshold_fracs[idx], linestyle='--', linewidth=1.0)
        ax.set_title(f"Threshold Scan (Pair {idx + 1})")
        ax.set_xlabel("Threshold fraction of max")
        ax.set_ylabel("Least squares (log scale)")
        
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        toolbar_frame = ttk.Frame(win)
        toolbar_frame.pack(fill=tk.X)
        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
        toolbar.update()

        frame = ttk.Frame(win)
        frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(frame, text="Selected Threshold:").pack(side=tk.LEFT)

        threshold_entry = ttk.Entry(frame, width=16)
        threshold_entry.pack(side=tk.LEFT, padx=5)
        threshold_entry.insert(0, f"{self.threshold_fracs[idx]:.3f}")
        threshold_entry.select_range(0, tk.END)
        threshold_entry.focus()

        def apply_threshold():
            try:
                new_frac = float(threshold_entry.get())
            except Exception:
                messagebox.showerror("Error", "Invalid threshold value.")
                return

            if not (0.0 < new_frac <= 1.0):
                messagebox.showerror("Error", "Threshold must be between 0 and 1.")
                return

            sat = self.X_bad[:, idx + 1]
            sat_max = np.nanmax(sat)
            new_thr = new_frac * sat_max

            self.threshold_fracs[idx] = new_frac
            self.thresholds[idx] = new_thr

            if idx == self.current_pair_idx:
                self.tip_frac_var.set(new_frac)

            c = idx + 1
            mask = self.X_bad[:, c] >= new_thr
            self.X_restored[:, c] = self.X_bad[:, c]
            self.X_restored[mask, c] = self.X_good_scaled[mask, c]
            self.Tips[:, c] = 0.0
            self.Tips[mask, c] = self.X_good_scaled[mask, c]

            self.update_plot()
            self.status_var.set(f"Applied threshold {new_frac:.3f} to pair {idx + 1}.")
            win.destroy()

        ttk.Button(frame, text="Apply Threshold", command=apply_threshold).pack(side=tk.LEFT, padx=6)
        ttk.Button(frame, text="Close", command=win.destroy).pack(side=tk.LEFT, padx=6)

    # -------------------------------------------------------------------------
    # FILE DELETE HELPERS
    # -------------------------------------------------------------------------

    def _delete_selected_saturated(self, event=None):
        selections = list(self.sat_listbox.curselection())
        if not selections:
            return
        for i in reversed(selections):
            if 0 <= i < len(self.index_saturated):
                self.index_saturated.pop(i)
        if self.current_pair_idx >= len(self.index_saturated):
            self.current_pair_idx = max(0, len(self.index_saturated) - 1)
        self._refresh_listboxes()
        self._update_nav_buttons()
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
        if self.current_pair_idx >= len(self.index_repair):
            self.current_pair_idx = max(0, len(self.index_repair) - 1)
        self._refresh_listboxes()
        self._update_nav_buttons()
        if self.healing_done:
            self.update_plot()
        else:
            self.update_preview_plot()
        self.status_var.set("Removed selected repair files.")

    def _maybe_choose_export_dir(self):
        if self.choose_export_dir_var.get():
            d = filedialog.askdirectory(title="Choose export directory")
            if d:
                self.export_dir = d
                self.status_var.set(f"Export directory: {d}")
            else:
                self.choose_export_dir_var.set(False)
        else:
            self.export_dir = None
            self.status_var.set("Exporting to saturated-file directory.")


# -----------------------------------------------------------------------------
# APP LAUNCH
# -----------------------------------------------------------------------------

def show_main_app(root):
    app = PATCH(master=root)
    app.pack(fill="both", expand=True)
    root.deiconify()


def main():
    global UI_SCALE, PLOT_SCALE

    root = tk.Tk()
    root.withdraw()

    UI_SCALE = compute_ui_scale(root)
    PLOT_SCALE = compute_plot_scale(root)

    plt.rcParams.update({
        "font.size": 14 * PLOT_SCALE,
        "axes.titlesize": 16 * PLOT_SCALE,
        "axes.labelsize": 14 * PLOT_SCALE,
        "xtick.labelsize": 12 * PLOT_SCALE,
        "ytick.labelsize": 12 * PLOT_SCALE,
        "legend.fontsize": 12 * PLOT_SCALE,
    })

    base_font_size = max(8, int(10 * UI_SCALE))
    root.option_add("*Font", ("Segoe UI", base_font_size))

    style = ttk.Style(root)
    combo_font_size = max(8, int(10 * UI_SCALE))
    style.configure("Custom.TCombobox", font=("Segoe UI", combo_font_size))
    style.configure("TCombobox", arrowsize=int(12 * UI_SCALE))

    splash = SplashScreen(master=root)

    def launch():
        try:
            if splash.winfo_exists():
                splash.destroy()
        except Exception:
            pass
        show_main_app(root)

    root.after(2600, launch)
    root.mainloop()


if __name__ == "__main__":
    main()
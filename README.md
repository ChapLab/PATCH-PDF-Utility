# PDF Patch Utility

A graphical Python utility for restoring saturated peak intensities in X-ray total scattering data by scaling and selectively merging an overexposed dataset with an unsaturated reference dataset.

This repository accompanies the manuscript *Exposure strategies for higher quality PDF analysis: Patching saturated peak intensities* and provides the Python implementation of the PDF Patch utility together with example data. The manuscript describes the method as a practical data-healing strategy that restores saturated intensities, preserves the improved high-Q statistics of long exposures, and improves the quality of downstream PDF analysis.

## Overview

Quantitative pair distribution function analysis requires accurate measurement of both intense Bragg reflections and weak diffuse scattering. In practice, detector exposure must balance avoiding saturation of strong peaks with achieving good signal-to-noise for weak scattering at high Q. This utility is designed to repair datasets in which strong reflections are saturated or near saturation by replacing only the affected intensity regions with appropriately scaled values from an unsaturated reference dataset. The high-Q and weak-scattering regions from the longer exposure are retained.

The utility supports:
- loading matched sets of saturated and repair files
- optional regridding of the repair dataset onto the saturated dataset Q-grid
- robust scaling using iteratively reweighted least squares
- optional attenuated scaling
- fixed manual scaling
- selective replacement of intensities above a user-defined patch threshold
- visualization of saturated, scaled repair, and restored data
- export of the current restored pair or all restored pairs
- plotting of scale convergence for the current dataset

## Repository structure

```text
PDF-Patch-Utility/
├── README.md
├── LICENSE
├── requirements.txt
├── CITATION.cff
├── src/
│   ├── pdf_patch.py
│   ├── patch_logo.ico
│   └── patch_logo.png
├── example_data/
│   ├── TiO2/
│   │   ├── screening_100x0p1s.*
│   │   ├── saturated_2x5s.*
│   └── MOF-808/
│       ├── screening_100x0p1s.*
│       ├── saturated_2x5s.*
└── figures/
    └── gui_screenshot.png

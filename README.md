# 🧪 sodiuMm - Sodium Window Analysis Tool

**sodiuMm** is a lightweight analysis tool for **sodium channel activation–inactivation ("window") curves**.  
It processes experimental datasets, fits Boltzmann models, computes physiologically relevant biomarkers (e.g., window area, slope factor), and exports outputs and plots.

---

## 📂 Project Structure

```
sodiumm/
│
├── data/
│   └── sample.csv             # Example dataset (activation/inactivation)
│
├── src/
│   ├── input_data.py          # Input loader and validation
│   ├── fitting.py             # Curve fitting, intersections, area metrics
│   ├── plots.py               # Matplotlib visualizations
│   ├── output_data.py         # CSV/XLSX/JSON writers and report bundling
│   ├── pipeline.py            # Full pipeline of analysis steps
│   └── gui.py                 # Tkinter desktop GUI
│
├── app.py                     # 🌐 Streamlit web interface
└── tests/                     # (Optional) Automated or manual tests
```

All modules are **self-contained** and usable via CLI, GUI, or web browser.

---

## ⚙️ Features

- **Robust input parsing** for both CSV and Excel (`.xlsx`) files  
- **Boltzmann fitting** for activation ($m_{\infty}$) and inactivation ($h_{\infty}$) curves  
- **Automatic computation of:**
  - Intersection voltage(s)
  - Sodium window area (integral of overlap)
  - Window peak amplitude and position
- **Output bundle per run:**
  ```
  output/<run_name>/
    curves.csv
    biomarkers.csv
    area.txt
    report.xlsx
    metadata.json
    plots/window.png (.svg)
  ```
- **Three usage modes:**
  1. **Web** - Streamlit-based online version 
  2. **GUI** - desktop Tkinter interface  
  3. **CLI** - batch and scripting 

---

## 🚀 Quick Start

### 1️⃣ Access the Web App (Recommended)

No installation needed - simply open the live version here:

👉 **[sodiumm.streamlit.app](https://sodiumm.streamlit.app)**

**Usage:**
1. Upload your CSV/XLSX dataset  
2. Optionally specify Excel sheet and voltage bounds  
3. Click **Run analysis**  
4. View summary metrics and preview plots  
5. Download all outputs (ZIP bundle)

All processing is performed server-side using the same backend as the local pipeline.

---

### 2️⃣ Run Locally (optional)

If you prefer offline analysis:

```bash
python src/main.py
```
This command launches the GUI version by default. 

#### CLI
```bash
python src/pipeline.py data/sample.csv output/
```

Optional flags:

| Flag | Description |
|------|--------------|
| `--run-name NAME` | Custom name for the output folder |
| `--sheet SHEET` | Excel sheet name (if not "data") |
| `--bounds -120,80` | Voltage range for window metrics (mV) |

#### GUI
```bash
python src/gui.py
```

Then select your input file, output directory, and click **Run analysis**.

---

## 🧬 Input Format

Each dataset must describe **two gating curves**:

| V_act (mV) | m_inf | V_inact (mV) | h_inf |
|-------------|--------|---------------|--------|
| -100 | 0.02 | -100 | 1.00 |
| -80  | 0.05 | -80  | 0.95 |
| ...  | ...  | ...  | ... |

Accepted variants:
- Headered or positional columns  
- Case-insensitive aliases (`Vactivation`, $m_{\infty}$, `h`, etc.)  
- Missing or non-numeric entries are filtered automatically

---

## 📊 Outputs

| File | Description |
|------|--------------|
| **curves.csv** | Tidy dataset with raw & fitted curves |
| **biomarkers.csv** | Fitting parameters and $R^2$/RMSE |
| **area.txt** | Numerical area, bounds, intersections, and peak info |
| **report.xlsx** | Excel summary |
| **metadata.json** | Full run configuration & paths |
| **plots/** | Activation/inactivation plot and shaded window |

---

## 🌐 Web App Summary

The **Streamlit** web version provides a ready-to-use browser interface for researchers and educators - no installation, setup, or dependencies required.

**Access:** [https://sodiumm.streamlit.app](https://sodiumm.streamlit.app)

**Workflow:**
1. Upload sodium channel dataset  
2. Wait a few seconds for processing  
3. View area, bounds, and peak metrics  
4. Preview plots or download full results

All computations use the same validated pipeline as the CLI and GUI versions.

---

## 🧠 Scientific Context

The **sodium window** quantifies the overlap between steady-state activation and inactivation, reflecting persistent inward current near subthreshold voltages.  
This toolkit standardizes its **computation, visualization, and reporting**.

---

## 🧰 Dependencies

| Library | Purpose |
|----------|----------|
| `numpy`, `pandas` | Numerical and tabular data |
| `matplotlib` | Plotting |
| `scipy` | Nonlinear fitting & integration |
| `openpyxl` | Excel reports |
| `streamlit` | Web interface |
| `tkinter` | Desktop GUI (stdlib) |

---

## 🧑‍💻 Author and License

Developed by **Ilia Golub** (2025)  
License: **MIT**

For academic or educational use, please cite or reference this repository.

---

## 🧾 Changelog

**v0.2.0**
- Added Streamlit web interface (`app.py`)
- Public deployment: [sodiumm.streamlit.app](https://sodiumm.streamlit.app)
- Unified output formatting and metadata

**v0.1.0**
- Initial stable release (CLI + GUI)
- Automatic area computation and plotting
- Metadata export for reproducibility

---

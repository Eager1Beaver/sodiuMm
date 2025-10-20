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
└── tests/                     # (Optional) Automated or manual tests
```

All modules are **self-contained** and usable via command line or programmatic imports.

---

## ⚙️ Features

- **Robust input parsing** for both CSV and Excel (`.xlsx`) files  
    Accepts either headered or positional columns.
- **Boltzmann fitting** for activation ($m_{\infty}$) and inactivation ($h_{\infty}$) curves.
- **Automatic intersections, window area, and biomarkers**:
  - Intersection voltage(s)
  - Sodium window area: $\int max(o, m_{\infty} - h_{\infty}) dV$
  - Window peak amplitude and position
- **Output bundle per run**:
  ```
  output/<run_name>/
    curves.csv
    biomarkers.csv
    area.txt
    report.xlsx
    metadata.json
    plots/window.png (.svg)
  ```
- **Graphical interface** for intuitive single-file analysis.
- **Scriptable pipeline** for batch or reproducible use.

---

## 🚀 Quick Start

### 1️⃣ Install dependencies

Create an environment (Python ≥ 3.9):

```bash
pip install -r requirements.txt
```

### 2️⃣ Run from CLI

```bash
python src/pipeline.py data/sample.csv output/
```

Optional arguments:

| Flag | Description |
|------|--------------|
| `--run-name NAME` | Custom name for the output folder |
| `--sheet SHEET` | Excel sheet name (if not "data") |
| `--bounds -120,80` | Voltage range for window metrics (mV) |

Example:
```bash
python src/pipeline.py data/sample.csv output/ --run-name demo --bounds -120,80
```

---

### 3️⃣ Run the GUI

```bash
python src/gui.py
```

Then:

1. Choose your input file (`.csv` / `.xlsx`)  
2. Select an output directory  
3. (Optional) Specify sheet name and voltage bounds  
4. Click **“Run analysis”**

Results will appear in your chosen folder.

---

## 🧬 Input Format

Each dataset must describe **two gating curves**:

| V_act (mV) | m_inf | V_inact (mV) | h_inf |
|-------------|--------|---------------|--------|
| -100 | 0.02 | -100 | 1.00 |
| -80  | 0.05 | -80  | 0.95 |
| ...  | ...  | ...  | ... |

**Accepted variants:**  
- Headered or positional columns  
- Case-insensitive aliases (e.g. `Vactivation`, $m_{\infty}$, `h`, etc.)  
- Missing or non-numeric entries are filtered automatically

---

## 📊 Outputs

| File | Description |
|------|--------------|
| **curves.csv** | Tidy dataset: `V`, `y`, `curve` (exp_act, exp_inact, fit_act, fit_inact) |
| **biomarkers.csv** | Fit parameters (A_lo, A_hi, V_half, k) and quality metrics ($R^2$, RMSE) |
| **area.txt** | Numerical window area, bounds, intersections, and peak info |
| **report.xlsx** | Excel summary (curves + biomarkers + area) |
| **metadata.json** | Run metadata (timestamp, config, file paths, etc.) |
| **plots/** | Visualization of activation/inactivation and shaded window region |

Example `area.txt`:
```
# Window area of sodium activation–inactivation
Definition: Integral[min(m_inf(V), h_inf(V))] dV
Area: 1.02
Bounds: (-120, 80)
Intersections (V*, y*): [(-55.2, 0.45)]
Peak window: 0.45 at V=-55.2
```

---

## 🧠 Scientific Context

The **sodium window** quantifies the overlap between steady-state activation and inactivation.  
It reflects persistent inward current near subthreshold voltages and plays a key role in excitability, arrhythmogenesis, and conduction safety factor.  

This toolkit standardizes its **computation and visualization**, making it ideal for experimental electrophysiology datasets.

---

## 🧩 Modular API

Each component can be imported individually:

```python
from src import input_data, fitting, plots, output_data, pipeline

loaded = input_data.load_input("data/sample.csv")
act_fit = fitting.fit_activation(loaded.activation["V"], loaded.activation["y"])
ina_fit = fitting.fit_inactivation(loaded.inactivation["V"], loaded.inactivation["y"])
wm = fitting.compute_biomarkers(act_fit, ina_fit)
```

---

## 📦 Metadata and Reproducibility

Each run embeds:
- Full configuration and timestamps
- Version (`sodiumm v0.1.0`)
- Input source path and Excel sheet
- Fitting and sampling parameters
- Generated plot paths

---

## 🧰 Dependencies

| Library | Purpose |
|----------|----------|
| `numpy`, `pandas` | Numerical and tabular data |
| `matplotlib` | Plotting |
| `scipy` | Nonlinear curve fitting and integration |
| `openpyxl` | Excel report writing |
| `tkinter` | GUI (standard library) |

---

## 🧑‍💻 Authors and License

Developed by **Ilia Golub** (2025)  
License: MIT  

For academic or educational use, please cite appropriately or reference this repository.

---

## 🧾 Changelog

**v0.1.0**
- Initial stable release  
- Complete end-to-end pipeline (CLI + GUI)  
- Automatic area computation and plotting  
- Metadata export for reproducibility

---

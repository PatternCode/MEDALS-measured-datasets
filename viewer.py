from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="MEDALS LIBS Spectrum Viewer",
    layout="wide",
)

REPO_ROOT = Path(__file__).resolve().parent

DATASETS = {
    "Medals_Samples_Feb26": REPO_ROOT / "Medals_Samples_Feb26",
    "Medals_MovingSamples_2026-04-29": REPO_ROOT / "Medals_MovingSamples_2026-04-29",
    "July2026_ScrapSamples": REPO_ROOT / "July2026_ScrapSamples",
}


# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

@st.cache_data
def load_spectrum_file(file_path: str) -> pd.DataFrame:
    """Load one MEDALS LIBS CSV file."""
    return pd.read_csv(file_path, sep=";")


def find_csv_files(dataset_path: Path) -> list[Path]:
    """Return all CSV files in a dataset directory, recursively."""
    return sorted(dataset_path.rglob("*.csv"))


def get_sample_label(dataset_name: str, file_path: Path) -> str:
    """Infer a readable sample label from the dataset structure."""
    if dataset_name == "Medals_Samples_Feb26":
        # CSVs are stored inside sample-ID folders.
        return file_path.parent.name

    if dataset_name == "Medals_MovingSamples_2026-04-29":
        # Example:
        # 469_LSA_ava_S20260429102814_E20260429102933.csv
        return file_path.name.split("_LSA_")[0]

    if dataset_name == "July2026_ScrapSamples":
        # Example:
        # 1-4301_LSA_ava_S20260716172701_E20260716172929.csv
        return file_path.name.split("_LSA_")[0]

    return file_path.stem


def prepare_spectral_data(df: pd.DataFrame):
    """
    Extract metadata, wavelength axis, and intensity matrix.

    Expected structure:
    MeasCtr;TimeStamp;<wavelength 1>;...;<wavelength N>
    """
    if df.shape[1] < 3:
        raise ValueError("The selected file does not contain spectral columns.")

    metadata = df.iloc[:, :2].copy()

    spectral_df = df.iloc[:, 2:].copy()

    try:
        wavelengths = spectral_df.columns.astype(float)
    except ValueError as exc:
        raise ValueError(
            "The spectral column headers could not be interpreted as wavelengths."
        ) from exc

    spectral_df = spectral_df.apply(pd.to_numeric, errors="coerce")

    if spectral_df.isna().any().any():
        raise ValueError(
            "One or more spectral intensity values could not be interpreted as numbers."
        )

    return metadata, wavelengths, spectral_df


# -----------------------------------------------------------------------------
# Application
# -----------------------------------------------------------------------------

st.title("MEDALS LIBS Spectrum Viewer")

st.write(
    "A lightweight viewer for browsing the measured LIBS datasets included in "
    "the MEDALS data repository."
)

# Check that the expected dataset folders exist.
available_datasets = {
    name: path for name, path in DATASETS.items() if path.exists()
}

if not available_datasets:
    st.error(
        "No MEDALS dataset folders were found next to viewer.py. "
        "Make sure viewer.py is located in the repository root."
    )
    st.stop()


# -----------------------------------------------------------------------------
# Dataset and file selection
# -----------------------------------------------------------------------------

st.sidebar.header("Data selection")

dataset_name = st.sidebar.selectbox(
    "Dataset",
    options=list(available_datasets.keys()),
)

dataset_path = available_datasets[dataset_name]
csv_files = find_csv_files(dataset_path)

if not csv_files:
    st.error(f"No CSV files were found in {dataset_path.name}.")
    st.stop()

relative_paths = [str(path.relative_to(dataset_path)) for path in csv_files]

selected_relative_path = st.sidebar.selectbox(
    "CSV file",
    options=relative_paths,
)

selected_file = dataset_path / selected_relative_path
sample_label = get_sample_label(dataset_name, selected_file)

try:
    df = load_spectrum_file(str(selected_file))
    metadata, wavelengths, spectra = prepare_spectral_data(df)
except Exception as exc:
    st.error(f"Could not load the selected file: {exc}")
    st.stop()


# -----------------------------------------------------------------------------
# File information
# -----------------------------------------------------------------------------

st.subheader("Selected measurement")

info_col1, info_col2, info_col3, info_col4 = st.columns(4)

info_col1.metric("Sample", sample_label)
info_col2.metric("Spectra", len(spectra))
info_col3.metric("Channels", spectra.shape[1])
info_col4.metric(
    "Wavelength range",
    f"{wavelengths.min():.3f}–{wavelengths.max():.3f} nm",
)

st.caption(f"File: `{selected_file.relative_to(REPO_ROOT)}`")


# -----------------------------------------------------------------------------
# Plot controls
# -----------------------------------------------------------------------------

st.sidebar.header("Plot settings")

plot_mode = st.sidebar.radio(
    "Plot mode",
    options=[
        "Single spectrum",
        "Multiple spectra",
        "Average spectrum",
    ],
)

log_scale = st.sidebar.checkbox("Logarithmic intensity axis", value=False)

full_min = float(wavelengths.min())
full_max = float(wavelengths.max())

wavelength_range = st.sidebar.slider(
    "Wavelength range (nm)",
    min_value=full_min,
    max_value=full_max,
    value=(full_min, full_max),
    step=0.1,
)

mask = (wavelengths >= wavelength_range[0]) & (
    wavelengths <= wavelength_range[1]
)

selected_wavelengths = wavelengths[mask]


# -----------------------------------------------------------------------------
# Spectrum plotting
# -----------------------------------------------------------------------------

st.subheader("LIBS spectrum")

fig, ax = plt.subplots(figsize=(12, 5))

if plot_mode == "Single spectrum":
    spectrum_number = st.sidebar.selectbox(
        "Spectrum",
        options=list(range(len(spectra))),
        format_func=lambda i: f"Spectrum {i + 1}",
    )

    intensity = spectra.iloc[spectrum_number].to_numpy()[mask]

    ax.plot(selected_wavelengths, intensity, linewidth=0.9)

    meas_ctr = metadata.iloc[spectrum_number, 0]
    ax.set_title(
        f"{sample_label} — Spectrum {spectrum_number + 1} "
        f"(MeasCtr: {meas_ctr})"
    )

elif plot_mode == "Multiple spectra":
    default_selection = list(range(min(5, len(spectra))))

    selected_indices = st.sidebar.multiselect(
        "Spectra",
        options=list(range(len(spectra))),
        default=default_selection,
        format_func=lambda i: f"Spectrum {i + 1}",
    )

    if not selected_indices:
        st.warning("Select at least one spectrum.")
        st.stop()

    for index in selected_indices:
        intensity = spectra.iloc[index].to_numpy()[mask]
        ax.plot(
            selected_wavelengths,
            intensity,
            linewidth=0.8,
            label=f"Spectrum {index + 1}",
        )

    ax.set_title(f"{sample_label} — Selected spectra")

    if len(selected_indices) <= 10:
        ax.legend()

else:
    mean_spectrum = spectra.mean(axis=0).to_numpy()[mask]
    ax.plot(
        selected_wavelengths,
        mean_spectrum,
        linewidth=1.0,
    )
    ax.set_title(f"{sample_label} — Average spectrum")

ax.set_xlabel("Wavelength (nm)")
ax.set_ylabel("Intensity")

if log_scale:
    ax.set_yscale("log")

ax.grid(alpha=0.25)
fig.tight_layout()

st.pyplot(fig)
plt.close(fig)


# -----------------------------------------------------------------------------
# Optional data inspection
# -----------------------------------------------------------------------------

with st.expander("Measurement metadata"):
    st.dataframe(metadata, use_container_width=True)

with st.expander("File information"):
    st.write(f"**Dataset:** `{dataset_name}`")
    st.write(f"**Sample label:** `{sample_label}`")
    st.write(f"**CSV file:** `{selected_file.name}`")
    st.write(f"**Rows / spectra:** {len(df)}")
    st.write(f"**Total columns:** {df.shape[1]}")
    st.write(f"**Spectral channels:** {spectra.shape[1]}")
    st.write(
        f"**Observed intensity range in this file:** "
        f"{spectra.to_numpy().min():,.0f}–{spectra.to_numpy().max():,.0f}"
    )
    
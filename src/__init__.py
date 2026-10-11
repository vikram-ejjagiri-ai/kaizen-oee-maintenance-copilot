import os

# Windows + low free RAM: OpenBLAS (used by numpy) can fail with "Memory allocation still
# failed". One thread per process is plenty for this project and avoids that error.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

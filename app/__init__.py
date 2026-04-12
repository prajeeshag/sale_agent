import os

# Must be set before torch or faiss are imported anywhere.
# Prevents segfault from duplicate OpenMP runtimes (faiss + torch on macOS).
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

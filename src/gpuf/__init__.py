"""GPU rental price forecasting: leak-safe evaluation harness around the gpu-price-pack starter kit."""
import sys

sys.dont_write_bytecode = True  # keep __pycache__ out of the hash-verified pack's starter/ folder

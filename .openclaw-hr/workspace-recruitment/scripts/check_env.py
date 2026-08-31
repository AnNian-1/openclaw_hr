#!/usr/bin/env python3
"""Quick check: can we import funasr and its dependencies?"""
import sys
print(f"Python: {sys.version}")
try:
    import torch
    print(f"torch: {torch.__version__}, CUDA: {torch.cuda.is_available()}")
except ImportError as e:
    print(f"torch: MISSING ({e})")
try:
    import funasr
    print(f"funasr: {funasr.__version__}")
except ImportError as e:
    print(f"funasr: MISSING ({e})")
try:
    import modelscope
    print(f"modelscope: {modelscope.__version__}")
except ImportError as e:
    print(f"modelscope: MISSING ({e})")
try:
    import numpy
    print(f"numpy: {numpy.__version__}")
except ImportError as e:
    print(f"numpy: MISSING ({e})")

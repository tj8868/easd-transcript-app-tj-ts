#!/usr/bin/env python3
"""
Windows Native 1-Click GUI Launcher (.pyw extension)
Guarantees 0 black command prompt windows on Windows.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import run_app

if __name__ == "__main__":
    run_app.main()

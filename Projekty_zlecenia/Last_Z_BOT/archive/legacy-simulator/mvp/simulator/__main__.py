"""
Main entry point for Extended Game Simulator module.

Allows running the simulator with: python -m mvp.simulator
"""

import sys
from mvp.simulator.cli import main

if __name__ == '__main__':
    sys.exit(main())

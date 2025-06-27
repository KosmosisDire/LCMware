"""LCM types package"""

# Add the core package to the Python path so generated types can import it
import sys
import os

# Add the types directory to sys.path so 'core' can be imported
_types_dir = os.path.dirname(__file__)
if _types_dir not in sys.path:
    sys.path.insert(0, _types_dir)
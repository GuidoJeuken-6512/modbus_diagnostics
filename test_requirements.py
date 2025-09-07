#!/usr/bin/env python3
"""
Test script to verify all requirements are properly installed and functional
"""

import sys
import importlib

def test_import(module_name, description=""):
    """Test if a module can be imported."""
    try:
        importlib.import_module(module_name)
        print(f"✅ {module_name} - {description}")
        return True
    except ImportError as e:
        print(f"❌ {module_name} - {description} - Error: {e}")
        return False

def main():
    """Test all required modules."""
    print("🔍 Testing Modbus Diagnostics Tool Requirements")
    print("=" * 50)
    
    # Core dependencies
    tests = [
        ("pymodbus", "Modbus communication library"),
        ("pymodbus.client.sync", "Modbus TCP client"),
        ("pymodbus.exceptions", "Modbus exceptions"),
        ("serial", "Serial communication (pymodbus dependency)"),
        ("six", "Python 2/3 compatibility (pymodbus dependency)"),
    ]
    
    # Standard library modules
    stdlib_tests = [
        ("sqlite3", "Database operations"),
        ("threading", "Concurrent operations"),
        ("subprocess", "System commands (ping tests)"),
        ("socket", "Network connectivity"),
        ("logging", "Logging system"),
        ("datetime", "Date and time operations"),
        ("json", "JSON data handling"),
        ("os", "Operating system interface"),
        ("time", "Time operations"),
        ("random", "Random number generation"),
        ("argparse", "Command line argument parsing"),
        ("tkinter", "GUI framework"),
        ("dataclasses", "Data classes (Python 3.7+)"),
        ("typing", "Type hints"),
        ("collections", "Advanced data collections"),
        ("concurrent.futures", "Parallel processing"),
    ]
    
    print("\n📦 Core Dependencies:")
    core_success = 0
    for module, desc in tests:
        if test_import(module, desc):
            core_success += 1
    
    print("\n📚 Standard Library Modules:")
    stdlib_success = 0
    for module, desc in stdlib_tests:
        if test_import(module, desc):
            stdlib_success += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Results: {core_success}/{len(tests)} core dependencies, {stdlib_success}/{len(stdlib_tests)} stdlib modules")
    
    if core_success == len(tests) and stdlib_success == len(stdlib_tests):
        print("🎉 All requirements are satisfied!")
        return 0
    else:
        print("⚠️  Some requirements are missing. Please check the installation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

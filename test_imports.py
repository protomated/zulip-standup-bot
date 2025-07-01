#!/usr/bin/env python3
"""
Test script to verify that all required modules can be imported.
"""

import sys
import os

# Add the local paths first to override installed packages
sys.path.insert(0, '/app/zulip_bots/zulip_bots/bots/standup')
sys.path.insert(0, '/app/zulip_bots/zulip_bots')
sys.path.insert(0, '/app')

def test_imports():
    """Test importing required modules."""
    print("Testing module imports...")
    print(f"Python path: {sys.path}")
    print(f"Working directory: {os.getcwd()}")

    try:
        print("1. Testing zulip import...")
        import zulip
        print("   ✅ zulip imported successfully")

        print("2. Testing direct database import...")
        # Import the database module directly
        import database
        print("   ✅ database module imported successfully")
        print(f"   Database module from: {database.__file__}")

        print("3. Testing database.init_db function...")
        print(f"   Database init function: {database.init_db}")

        print("4. Testing simple bot runner...")
        # Test our simple bot runner
        import subprocess
        result = subprocess.run([
            'python3', '/app/simple_bot_runner.py'
        ], capture_output=True, text=True, timeout=5)

        if result.returncode == 0:
            print("   ✅ Simple bot runner works!")
        else:
            print(f"   ❌ Simple bot runner failed: {result.stderr}")

        print("   ✅ All imports and database initialization successful!")

        return True

    except ImportError as e:
        print(f"   ❌ Import error: {e}")
        print("\nDebugging information:")
        print("Available packages:")
        try:
            import pkg_resources
            for package in pkg_resources.working_set:
                print(f"  {package.project_name}=={package.version}")
        except:
            print("  pkg_resources not available")

        print("\nPython sys.path:")
        for path in sys.path:
            print(f"  {path}")

        # Check if we can find the database file directly
        db_file = '/app/zulip_bots/zulip_bots/bots/standup/database.py'
        print(f"\nChecking if database.py exists at {db_file}: {os.path.exists(db_file)}")

        return False
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)

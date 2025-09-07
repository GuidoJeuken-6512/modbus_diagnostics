#!/usr/bin/env python3
"""
Test script for different host access modes
Demonstrates how the secondary host is accessed in different modes
"""

import time
import logging
from const import (
    HOST_ACCESS_MODE, get_host_access_mode, get_host_status,
    switch_hosts, USE_SECONDARY_AS_PRIMARY
)
from modbus_monitor import ModbusMonitor, MonitorConfig

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def test_host_modes():
    """Test all host access modes."""
    
    print("🔧 HOST ACCESS MODE TESTER")
    print("=" * 50)
    
    # Show current configuration
    host_status = get_host_status()
    access_mode_info = get_host_access_mode()
    
    print(f"\n📋 Current Configuration:")
    print(f"   Host Switch: {'ENABLED' if host_status['switch_enabled'] else 'DISABLED'}")
    print(f"   Access Mode: {HOST_ACCESS_MODE}")
    print(f"   Description: {access_mode_info['description']}")
    print(f"   Behavior: {access_mode_info['behavior']}")
    
    print(f"\n🌐 Active Hosts:")
    print(f"   Primary: {host_status['active_primary']['host']}:{host_status['active_primary']['port']} "
          f"(original: {host_status['active_primary']['original_role']})")
    print(f"   Secondary: {host_status['active_secondary']['host']}:{host_status['active_secondary']['port']} "
          f"(original: {host_status['active_secondary']['original_role']})")
    
    print(f"\n📊 Available Modes:")
    for mode in access_mode_info['available_modes']:
        print(f"   - {mode}")
    
    print(f"\n🧪 Testing Access Modes:")
    print("   (Note: This will attempt real Modbus connections)")
    
    # Test each mode
    modes_to_test = ['fallback', 'alternating', 'both', 'primary_only', 'secondary_only']
    
    for mode in modes_to_test:
        print(f"\n--- Testing Mode: {mode} ---")
        
        # Update the mode in const.py (this would normally be done by changing the file)
        print(f"   Mode: {mode}")
        print(f"   Description: {access_mode_info['description']}")
        
        # Create monitor with this mode
        config = MonitorConfig()
        monitor = ModbusMonitor(config)
        
        # Run a few test requests
        print(f"   Running 3 test requests...")
        for i in range(3):
            try:
                result = monitor._perform_modbus_read()
                if result.success:
                    print(f"     Request {i+1}: ✅ {result.host}:{result.port} - "
                          f"{result.response_time:.1f}ms - Value: {result.value}")
                else:
                    print(f"     Request {i+1}: ❌ {result.host}:{result.port} - "
                          f"{result.error_type}: {result.error_message}")
            except Exception as e:
                print(f"     Request {i+1}: ❌ Error: {e}")
            
            time.sleep(1)  # Small delay between requests
        
        # Show statistics
        stats = monitor.get_statistics()
        print(f"   Statistics:")
        print(f"     Total Requests: {stats['total_requests']}")
        print(f"     Success Rate: {stats['success_rate']:.1f}%")
        print(f"     Fallback Switches: {stats['fallback_switches']}")
        print(f"     Alternating Switches: {stats['alternating_switches']}")
        print(f"     Both Host Tests: {stats['both_host_tests']}")
        
        time.sleep(2)  # Delay between modes

def demonstrate_host_switch():
    """Demonstrate host switching functionality."""
    
    print(f"\n🔄 HOST SWITCH DEMONSTRATION")
    print("=" * 50)
    
    # Show original configuration
    print(f"\n📋 Original Configuration:")
    host_status = get_host_status()
    print(f"   Switch Enabled: {host_status['switch_enabled']}")
    print(f"   Primary: {host_status['active_primary']['host']}:{host_status['active_primary']['port']}")
    print(f"   Secondary: {host_status['active_secondary']['host']}:{host_status['active_secondary']['port']}")
    
    # Switch hosts
    print(f"\n🔄 Switching hosts...")
    new_switch_state = switch_hosts()
    print(f"   New switch state: {new_switch_state}")
    
    # Show new configuration
    host_status = get_host_status()
    print(f"\n📋 New Configuration:")
    print(f"   Switch Enabled: {host_status['switch_enabled']}")
    print(f"   Primary: {host_status['active_primary']['host']}:{host_status['active_primary']['port']} "
          f"(was {host_status['active_primary']['original_role']})")
    print(f"   Secondary: {host_status['active_secondary']['host']}:{host_status['active_secondary']['port']} "
          f"(was {host_status['active_secondary']['original_role']})")
    
    # Switch back
    print(f"\n🔄 Switching back...")
    switch_hosts()
    print(f"   Switch state: {USE_SECONDARY_AS_PRIMARY}")

def show_mode_explanations():
    """Show detailed explanations of each mode."""
    
    print(f"\n📖 MODE EXPLANATIONS")
    print("=" * 50)
    
    explanations = {
        'fallback': {
            'title': 'Fallback Mode (Default)',
            'description': 'Secondary wird nur bei Primary-Fehlern verwendet',
            'when_secondary_used': 'Nur wenn Primary Host nicht erreichbar ist oder Timeout hat',
            'use_case': 'Produktionsumgebung - minimale Belastung des Secondary Hosts',
            'pros': ['Minimale Netzwerk-Belastung', 'Einfache Konfiguration', 'Zuverlässiger Fallback'],
            'cons': ['Secondary wird selten getestet', 'Langsame Erkennung von Secondary-Problemen']
        },
        'alternating': {
            'title': 'Alternating Mode',
            'description': 'Wechselt zwischen Primary und Secondary ab',
            'when_secondary_used': 'Bei jedem zweiten Request',
            'use_case': 'Load Balancing oder regelmäßige Tests beider Hosts',
            'pros': ['Gleichmäßige Belastung', 'Regelmäßige Tests beider Hosts', 'Bessere Fehlererkennung'],
            'cons': ['Höhere Netzwerk-Belastung', 'Komplexere Logik']
        },
        'both': {
            'title': 'Both Hosts Mode',
            'description': 'Beide Hosts werden bei jedem Request getestet',
            'when_secondary_used': 'Bei jedem Request parallel zum Primary',
            'use_case': 'Umfassende Diagnose und Performance-Vergleich',
            'pros': ['Vollständige Diagnose', 'Performance-Vergleich', 'Schnelle Fehlererkennung'],
            'cons': ['Doppelte Netzwerk-Belastung', 'Längere Request-Zeit']
        },
        'primary_only': {
            'title': 'Primary Only Mode',
            'description': 'Nur Primary Host wird verwendet',
            'when_secondary_used': 'Nie',
            'use_case': 'Wenn Secondary Host nicht verfügbar ist',
            'pros': ['Minimale Belastung', 'Einfache Konfiguration'],
            'cons': ['Kein Fallback', 'Keine Redundanz']
        },
        'secondary_only': {
            'title': 'Secondary Only Mode',
            'description': 'Nur Secondary Host wird verwendet',
            'when_secondary_used': 'Bei jedem Request',
            'use_case': 'Testing des Secondary Hosts oder wenn Primary nicht verfügbar',
            'pros': ['Testet Secondary Host', 'Einfache Konfiguration'],
            'cons': ['Kein Fallback', 'Keine Redundanz']
        }
    }
    
    for mode, info in explanations.items():
        print(f"\n🔧 {info['title']}")
        print(f"   Description: {info['description']}")
        print(f"   When Secondary Used: {info['when_secondary_used']}")
        print(f"   Use Case: {info['use_case']}")
        print(f"   Pros: {', '.join(info['pros'])}")
        print(f"   Cons: {', '.join(info['cons'])}")

def main():
    """Main function."""
    print("🚀 Modbus Host Access Mode Tester")
    print("=" * 60)
    
    try:
        # Show mode explanations
        show_mode_explanations()
        
        # Demonstrate host switching
        demonstrate_host_switch()
        
        # Ask user if they want to test modes
        print(f"\n❓ Do you want to test the access modes with real Modbus connections?")
        print(f"   This will attempt to connect to your configured hosts.")
        response = input("   Continue? (y/N): ").strip().lower()
        
        if response in ['y', 'yes']:
            test_host_modes()
        else:
            print("   Skipping real connection tests.")
        
        print(f"\n✅ Test completed!")
        
    except KeyboardInterrupt:
        print(f"\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Simple Modbus connection test to isolate the issue
"""

import sys
import logging
from pymodbus.client.sync import ModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def test_modbus_connection():
    """Test basic Modbus connection."""
    try:
        logger.info("🔧 Testing Modbus connection...")
        
        # Test connection to secondary host (Python simulator)
        host = "192.168.178.57"
        port = 5020
        register = 1000
        
        logger.info(f"📡 Connecting to {host}:{port}")
        
        client = ModbusTcpClient(host=host, port=port, timeout=5.0)
        
        if not client.connect():
            logger.error(f"❌ Failed to connect to {host}:{port}")
            return False
        
        logger.info("✅ Connected successfully")
        
        # Try to read a register
        logger.info(f"📖 Reading register {register}")
        result = client.read_holding_registers(address=register, count=1)
        
        if result.isError():
            logger.error(f"❌ Modbus error: {result}")
            return False
        
        value = result.registers[0] if result.registers else None
        logger.info(f"✅ Register {register} = {value}")
        
        client.close()
        logger.info("✅ Test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_modbus_connection()
    sys.exit(0 if success else 1)

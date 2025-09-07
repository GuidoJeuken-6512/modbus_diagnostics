#!/usr/bin/env python3
"""
Lambda Heat Pump Specific Test Script
Tests critical registers based on the official Lambda specification
"""

import time
import logging
from datetime import datetime
from typing import Dict, List, Tuple
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException

from const import (
    PRIMARY_HOST, PRIMARY_PORT, SECONDARY_HOST, SECONDARY_PORT,
    LAMBDA_UNIT_ID, LAMBDA_TIMEOUT, LAMBDA_CRITICAL_REGISTERS,
    get_active_hosts, get_host_status
)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class LambdaHeatPumpTester:
    """Lambda Heat Pump specific tester based on official specification."""
    
    def __init__(self):
        self.unit_id = LAMBDA_UNIT_ID
        self.timeout = LAMBDA_TIMEOUT
        self.critical_registers = LAMBDA_CRITICAL_REGISTERS
        
        # Get active hosts
        primary_host, primary_port, secondary_host, secondary_port = get_active_hosts()
        self.hosts = [
            (primary_host, primary_port, "Primary"),
            (secondary_host, secondary_port, "Secondary")
        ]
        
        logger.info("🔧 Lambda Heat Pump Tester initialized")
        logger.info(f"   Unit ID: {self.unit_id}")
        logger.info(f"   Timeout: {self.timeout}s")
        logger.info(f"   Critical Registers: {len(self.critical_registers)}")
    
    def test_register(self, host: str, port: int, register: int, description: str) -> Dict:
        """Test a specific register on a host."""
        start_time = time.time()
        
        try:
            # Create Modbus client with Lambda settings
            client = ModbusTcpClient(
                host=host,
                port=port,
                timeout=self.timeout
            )
            
            # Connect
            if not client.connect():
                return {
                    'success': False,
                    'error': f"Connection failed to {host}:{port}",
                    'response_time': (time.time() - start_time) * 1000,
                    'value': None
                }
            
            # Read register using function code 0x03 (read multiple holding registers)
            result = client.read_holding_registers(address=register, count=1, slave=self.unit_id)
            
            if result.isError():
                return {
                    'success': False,
                    'error': f"Modbus error: {result}",
                    'response_time': (time.time() - start_time) * 1000,
                    'value': None
                }
            
            # Extract value
            value = result.registers[0] if result.registers else None
            response_time = (time.time() - start_time) * 1000
            
            client.close()
            
            return {
                'success': True,
                'error': None,
                'response_time': response_time,
                'value': value,
                'description': description
            }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                'success': False,
                'error': str(e),
                'response_time': response_time,
                'value': None,
                'description': description
            }
    
    def test_critical_registers(self) -> Dict:
        """Test all critical Lambda registers."""
        logger.info("🚀 Testing critical Lambda registers")
        
        results = {}
        
        for host, port, host_name in self.hosts:
            logger.info(f"\n🔍 Testing {host_name} Host: {host}:{port}")
            results[host_name] = {}
            
            for register, description in self.critical_registers.items():
                logger.info(f"   Testing Register {register}: {description}")
                
                result = self.test_register(host, port, register, description)
                results[host_name][register] = result
                
                if result['success']:
                    logger.info(f"     ✅ Success: Value={result['value']}, Time={result['response_time']:.1f}ms")
                else:
                    logger.error(f"     ❌ Failed: {result['error']}")
                
                # Small delay between register tests
                time.sleep(0.1)
        
        return results
    
    def test_register_0_specifically(self) -> Dict:
        """Test Register 0 specifically (the problematic one from your logs)."""
        logger.info("🎯 Testing Register 0 specifically (General Error number)")
        
        results = {}
        
        for host, port, host_name in self.hosts:
            logger.info(f"\n🔍 Testing Register 0 on {host_name}: {host}:{port}")
            
            # Test multiple times to check consistency
            test_results = []
            for i in range(5):
                result = self.test_register(host, port, 0, "General Error number")
                test_results.append(result)
                
                if result['success']:
                    logger.info(f"   Test {i+1}: ✅ Value={result['value']}, Time={result['response_time']:.1f}ms")
                else:
                    logger.error(f"   Test {i+1}: ❌ {result['error']}")
                
                time.sleep(1)  # 1 second between tests
            
            results[host_name] = test_results
        
        return results
    
    def test_heat_pump_module(self) -> Dict:
        """Test Heat Pump Module registers (Index 1)."""
        logger.info("🔥 Testing Heat Pump Module (Index 1)")
        
        # Heat Pump 1 registers (Subindex 0)
        hp1_registers = {
            1000: "Heat pump 1 Error state",
            1001: "Heat pump 1 Error number",
            1002: "Heat pump 1 State",
            1003: "Heat pump 1 Operating state",
            1004: "Heat pump 1 Flow line temperature"
        }
        
        results = {}
        
        for host, port, host_name in self.hosts:
            logger.info(f"\n🔍 Testing Heat Pump Module on {host_name}: {host}:{port}")
            results[host_name] = {}
            
            for register, description in hp1_registers.items():
                result = self.test_register(host, port, register, description)
                results[host_name][register] = result
                
                if result['success']:
                    # Decode some values for better understanding
                    value = result['value']
                    if register == 1000:  # Error state
                        error_states = {0: "NONE", 1: "MESSAGE", 2: "WARNING", 3: "ALARM", 4: "FAULT"}
                        state_desc = error_states.get(value, f"Unknown({value})")
                        logger.info(f"   Register {register}: ✅ Value={value} ({state_desc}), Time={result['response_time']:.1f}ms")
                    elif register == 1002:  # State
                        states = {0: "INIT", 1: "REFERENCE", 2: "RESTART-BLOCK", 3: "READY", 4: "START PUMPS", 5: "START COMPRESSOR"}
                        state_desc = states.get(value, f"Unknown({value})")
                        logger.info(f"   Register {register}: ✅ Value={value} ({state_desc}), Time={result['response_time']:.1f}ms")
                    else:
                        logger.info(f"   Register {register}: ✅ Value={value}, Time={result['response_time']:.1f}ms")
                else:
                    logger.error(f"   Register {register}: ❌ {result['error']}")
                
                time.sleep(0.1)
        
        return results
    
    def analyze_results(self, results: Dict) -> Dict:
        """Analyze test results and provide recommendations."""
        logger.info("📊 Analyzing test results")
        
        analysis = {
            'summary': {},
            'recommendations': [],
            'issues_found': []
        }
        
        for host_name, host_results in results.items():
            if isinstance(host_results, dict):
                # Multiple registers tested
                total_tests = len(host_results)
                successful_tests = sum(1 for r in host_results.values() if r['success'])
                failed_tests = total_tests - successful_tests
                
                avg_response_time = sum(r['response_time'] for r in host_results.values() if r['success']) / max(1, successful_tests)
                
                analysis['summary'][host_name] = {
                    'total_tests': total_tests,
                    'successful': successful_tests,
                    'failed': failed_tests,
                    'success_rate': (successful_tests / total_tests) * 100,
                    'avg_response_time': avg_response_time
                }
                
                # Check for specific issues
                for register, result in host_results.items():
                    if not result['success']:
                        analysis['issues_found'].append(f"{host_name} Register {register}: {result['error']}")
                    elif result['response_time'] > 5000:  # 5 seconds
                        analysis['issues_found'].append(f"{host_name} Register {register}: Slow response ({result['response_time']:.1f}ms)")
        
        # Generate recommendations
        if analysis['issues_found']:
            analysis['recommendations'].append("Check network connectivity and Lambda device status")
            analysis['recommendations'].append("Verify Unit ID = 1 is correct")
            analysis['recommendations'].append("Check if Lambda device is in proper operating state")
        
        # Check for Register 0 specific issues
        if 'Primary' in results and 0 in results['Primary']:
            reg0_result = results['Primary'][0]
            if not reg0_result['success']:
                analysis['recommendations'].append("Register 0 (General Error number) is failing - this matches your HA logs")
                analysis['recommendations'].append("Consider adding Register 0 to individual reads in const.py")
        
        return analysis
    
    def export_results(self, results: Dict, analysis: Dict, output_file: str):
        """Export test results to file."""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=== LAMBDA HEAT PUMP TEST RESULTS ===\n\n")
                f.write(f"Test Date: {datetime.now()}\n")
                f.write(f"Unit ID: {self.unit_id}\n")
                f.write(f"Timeout: {self.timeout}s\n\n")
                
                f.write("=== SUMMARY ===\n")
                for host_name, summary in analysis['summary'].items():
                    f.write(f"\n{host_name} Host:\n")
                    f.write(f"  Total Tests: {summary['total_tests']}\n")
                    f.write(f"  Successful: {summary['successful']}\n")
                    f.write(f"  Failed: {summary['failed']}\n")
                    f.write(f"  Success Rate: {summary['success_rate']:.1f}%\n")
                    f.write(f"  Avg Response Time: {summary['avg_response_time']:.1f}ms\n")
                
                f.write("\n=== ISSUES FOUND ===\n")
                for issue in analysis['issues_found']:
                    f.write(f"❌ {issue}\n")
                
                f.write("\n=== RECOMMENDATIONS ===\n")
                for rec in analysis['recommendations']:
                    f.write(f"💡 {rec}\n")
                
                f.write("\n=== DETAILED RESULTS ===\n")
                for host_name, host_results in results.items():
                    f.write(f"\n{host_name} Host Results:\n")
                    if isinstance(host_results, dict):
                        for register, result in host_results.items():
                            f.write(f"  Register {register}: {'✅' if result['success'] else '❌'}\n")
                            if result['success']:
                                f.write(f"    Value: {result['value']}\n")
                                f.write(f"    Response Time: {result['response_time']:.1f}ms\n")
                            else:
                                f.write(f"    Error: {result['error']}\n")
            
            logger.info(f"✅ Results exported to {output_file}")
            
        except Exception as e:
            logger.error(f"❌ Failed to export results: {e}")

def main():
    """Main function."""
    print("🔥 Lambda Heat Pump Specific Tester")
    print("=" * 60)
    
    # Show current configuration
    host_status = get_host_status()
    print(f"\n📋 Current Configuration:")
    print(f"   Host Switch: {'ENABLED' if host_status['switch_enabled'] else 'DISABLED'}")
    print(f"   Primary: {host_status['active_primary']['host']}:{host_status['active_primary']['port']}")
    print(f"   Secondary: {host_status['active_secondary']['host']}:{host_status['active_secondary']['port']}")
    print(f"   Unit ID: {LAMBDA_UNIT_ID}")
    print(f"   Timeout: {LAMBDA_TIMEOUT}s")
    
    try:
        tester = LambdaHeatPumpTester()
        
        # Test Register 0 specifically (the problematic one)
        print(f"\n🎯 Testing Register 0 specifically (matches your HA logs)...")
        reg0_results = tester.test_register_0_specifically()
        
        # Test Heat Pump Module
        print(f"\n🔥 Testing Heat Pump Module...")
        hp_results = tester.test_heat_pump_module()
        
        # Test all critical registers
        print(f"\n🚀 Testing all critical registers...")
        all_results = tester.test_critical_registers()
        
        # Analyze results
        print(f"\n📊 Analyzing results...")
        analysis = tester.analyze_results(all_results)
        
        # Print summary
        print(f"\n📋 Test Summary:")
        for host_name, summary in analysis['summary'].items():
            print(f"   {host_name}: {summary['successful']}/{summary['total_tests']} successful "
                  f"({summary['success_rate']:.1f}%), avg {summary['avg_response_time']:.1f}ms")
        
        if analysis['issues_found']:
            print(f"\n❌ Issues Found:")
            for issue in analysis['issues_found']:
                print(f"   - {issue}")
        
        if analysis['recommendations']:
            print(f"\n💡 Recommendations:")
            for rec in analysis['recommendations']:
                print(f"   - {rec}")
        
        # Export results
        output_file = f"lambda_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        tester.export_results(all_results, analysis, output_file)
        
        print(f"\n✅ Test completed! Results exported to {output_file}")
        
    except KeyboardInterrupt:
        print(f"\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")

if __name__ == "__main__":
    main()

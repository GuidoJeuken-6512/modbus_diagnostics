#!/usr/bin/env python3
"""
Lambda Heat Pump vs Python Simulator Analysis
Analyzes differences between real Lambda WP and Python Modbus simulator
to distinguish between network issues and Lambda device issues
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

class LambdaVsSimulatorAnalyzer:
    """Analyzes differences between real Lambda WP and Python simulator."""
    
    def __init__(self):
        self.unit_id = LAMBDA_UNIT_ID
        self.timeout = LAMBDA_TIMEOUT
        
        # Get active hosts
        primary_host, primary_port, secondary_host, secondary_port = get_active_hosts()
        
        self.lambda_wp = {
            'host': primary_host,
            'port': primary_port,
            'name': 'Real Lambda WP',
            'type': 'lambda_device'
        }
        
        self.python_simulator = {
            'host': secondary_host,
            'port': secondary_port,
            'name': 'Python Simulator',
            'type': 'simulator'
        }
        
        logger.info("🔧 Lambda vs Simulator Analyzer initialized")
        logger.info(f"   Real Lambda WP: {self.lambda_wp['host']}:{self.lambda_wp['port']}")
        logger.info(f"   Python Simulator: {self.python_simulator['host']}:{self.python_simulator['port']}")
    
    def test_register_comparison(self, register: int, description: str, test_count: int = 5) -> Dict:
        """Test a register on both hosts and compare results."""
        logger.info(f"🔍 Testing Register {register}: {description}")
        
        results = {
            'register': register,
            'description': description,
            'lambda_wp': [],
            'python_simulator': [],
            'comparison': {}
        }
        
        # Test Lambda WP
        logger.info(f"   Testing Real Lambda WP...")
        for i in range(test_count):
            result = self._test_single_register(
                self.lambda_wp['host'], 
                self.lambda_wp['port'], 
                register, 
                f"Lambda WP Test {i+1}"
            )
            results['lambda_wp'].append(result)
            time.sleep(0.5)  # 500ms between tests
        
        # Test Python Simulator
        logger.info(f"   Testing Python Simulator...")
        for i in range(test_count):
            result = self._test_single_register(
                self.python_simulator['host'], 
                self.python_simulator['port'], 
                register, 
                f"Simulator Test {i+1}"
            )
            results['python_simulator'].append(result)
            time.sleep(0.5)  # 500ms between tests
        
        # Analyze comparison
        results['comparison'] = self._analyze_comparison(results)
        
        return results
    
    def _test_single_register(self, host: str, port: int, register: int, test_name: str) -> Dict:
        """Test a single register on a host."""
        start_time = time.time()
        
        try:
            client = ModbusTcpClient(
                host=host,
                port=port,
                timeout=self.timeout
            )
            
            if not client.connect():
                return {
                    'success': False,
                    'error': f"Connection failed to {host}:{port}",
                    'response_time': (time.time() - start_time) * 1000,
                    'value': None,
                    'test_name': test_name
                }
            
            result = client.read_holding_registers(address=register, count=1, slave=self.unit_id)
            
            if result.isError():
                return {
                    'success': False,
                    'error': f"Modbus error: {result}",
                    'response_time': (time.time() - start_time) * 1000,
                    'value': None,
                    'test_name': test_name
                }
            
            value = result.registers[0] if result.registers else None
            response_time = (time.time() - start_time) * 1000
            
            client.close()
            
            return {
                'success': True,
                'error': None,
                'response_time': response_time,
                'value': value,
                'test_name': test_name
            }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                'success': False,
                'error': str(e),
                'response_time': response_time,
                'value': None,
                'test_name': test_name
            }
    
    def _analyze_comparison(self, results: Dict) -> Dict:
        """Analyze the comparison between Lambda WP and Python Simulator."""
        lambda_results = results['lambda_wp']
        simulator_results = results['python_simulator']
        
        # Calculate success rates
        lambda_success_rate = sum(1 for r in lambda_results if r['success']) / len(lambda_results) * 100
        simulator_success_rate = sum(1 for r in simulator_results if r['success']) / len(simulator_results) * 100
        
        # Calculate average response times
        lambda_avg_time = sum(r['response_time'] for r in lambda_results if r['success']) / max(1, sum(1 for r in lambda_results if r['success']))
        simulator_avg_time = sum(r['response_time'] for r in simulator_results if r['success']) / max(1, sum(1 for r in simulator_results if r['success']))
        
        # Analyze value consistency
        lambda_values = [r['value'] for r in lambda_results if r['success']]
        simulator_values = [r['value'] for r in simulator_results if r['success']]
        
        lambda_value_consistent = len(set(lambda_values)) <= 1 if lambda_values else False
        simulator_value_consistent = len(set(simulator_values)) <= 1 if simulator_values else False
        
        # Determine issue type
        issue_analysis = self._determine_issue_type(
            lambda_success_rate, simulator_success_rate,
            lambda_avg_time, simulator_avg_time,
            lambda_value_consistent, simulator_value_consistent
        )
        
        return {
            'lambda_success_rate': lambda_success_rate,
            'simulator_success_rate': simulator_success_rate,
            'lambda_avg_response_time': lambda_avg_time,
            'simulator_avg_response_time': simulator_avg_time,
            'lambda_value_consistent': lambda_value_consistent,
            'simulator_value_consistent': simulator_value_consistent,
            'lambda_values': lambda_values,
            'simulator_values': simulator_values,
            'issue_analysis': issue_analysis
        }
    
    def _determine_issue_type(self, lambda_success: float, simulator_success: float,
                            lambda_time: float, simulator_time: float,
                            lambda_consistent: bool, simulator_consistent: bool) -> Dict:
        """Determine the type of issue based on comparison results."""
        
        analysis = {
            'issue_type': 'unknown',
            'confidence': 'low',
            'explanation': '',
            'recommendations': []
        }
        
        # Case 1: Both hosts work well
        if lambda_success >= 80 and simulator_success >= 80:
            analysis['issue_type'] = 'no_issue'
            analysis['confidence'] = 'high'
            analysis['explanation'] = 'Both Lambda WP and Python Simulator are working correctly'
            analysis['recommendations'] = ['Check HA integration configuration', 'Verify network stability']
        
        # Case 2: Lambda WP fails, Simulator works
        elif lambda_success < 50 and simulator_success >= 80:
            analysis['issue_type'] = 'lambda_device_issue'
            analysis['confidence'] = 'high'
            analysis['explanation'] = 'Lambda WP has issues, but network is working (simulator responds)'
            analysis['recommendations'] = [
                'Check Lambda WP power and status',
                'Verify Lambda WP network connection',
                'Check Lambda WP error logs',
                'Consider Lambda WP restart'
            ]
        
        # Case 3: Both hosts fail
        elif lambda_success < 50 and simulator_success < 50:
            analysis['issue_type'] = 'network_issue'
            analysis['confidence'] = 'high'
            analysis['explanation'] = 'Both hosts fail - likely network issue'
            analysis['recommendations'] = [
                'Check network connectivity',
                'Verify IP addresses and ports',
                'Check firewall settings',
                'Test with ping and telnet'
            ]
        
        # Case 4: Lambda WP works, Simulator fails
        elif lambda_success >= 80 and simulator_success < 50:
            analysis['issue_type'] = 'simulator_issue'
            analysis['confidence'] = 'medium'
            analysis['explanation'] = 'Lambda WP works, but Python Simulator has issues'
            analysis['recommendations'] = [
                'Check Python Simulator status',
                'Verify simulator configuration',
                'Check simulator logs',
                'Restart Python Simulator if needed'
            ]
        
        # Case 5: Mixed results
        else:
            analysis['issue_type'] = 'mixed_issues'
            analysis['confidence'] = 'medium'
            analysis['explanation'] = 'Mixed results - both hosts have some issues'
            analysis['recommendations'] = [
                'Check network stability',
                'Verify both host configurations',
                'Monitor for intermittent issues',
                'Consider network optimization'
            ]
        
        # Add response time analysis
        if lambda_time > 5000:  # 5 seconds
            analysis['recommendations'].append('Lambda WP response time is slow - check device performance')
        
        if simulator_time > 1000:  # 1 second
            analysis['recommendations'].append('Python Simulator response time is slow - check server performance')
        
        return analysis
    
    def analyze_critical_registers(self) -> Dict:
        """Analyze critical registers to identify the root cause of issues."""
        logger.info("🚀 Analyzing critical registers for issue identification")
        
        # Focus on the most problematic registers from your logs
        critical_registers = {
            0: "General Error number (problematic in your logs)",
            1000: "Heat pump 1 Error state (main issue in your logs)",
            1001: "Heat pump 1 Error number",
            1002: "Heat pump 1 State",
            1003: "Heat pump 1 Operating state"
        }
        
        results = {}
        
        for register, description in critical_registers.items():
            logger.info(f"\n🔍 Analyzing Register {register}: {description}")
            
            result = self.test_register_comparison(register, description, test_count=3)
            results[register] = result
            
            # Print immediate analysis
            comparison = result['comparison']
            issue_analysis = comparison['issue_analysis']
            
            logger.info(f"   📊 Analysis Results:")
            logger.info(f"      Lambda WP: {comparison['lambda_success_rate']:.1f}% success, "
                       f"{comparison['lambda_avg_response_time']:.1f}ms avg")
            logger.info(f"      Simulator: {comparison['simulator_success_rate']:.1f}% success, "
                       f"{comparison['simulator_avg_response_time']:.1f}ms avg")
            logger.info(f"      Issue Type: {issue_analysis['issue_type']} (confidence: {issue_analysis['confidence']})")
            logger.info(f"      Explanation: {issue_analysis['explanation']}")
        
        return results
    
    def generate_diagnostic_report(self, results: Dict) -> str:
        """Generate a comprehensive diagnostic report."""
        report = []
        report.append("=" * 80)
        report.append("LAMBDA WP vs PYTHON SIMULATOR DIAGNOSTIC REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now()}")
        report.append(f"Real Lambda WP: {self.lambda_wp['host']}:{self.lambda_wp['port']}")
        report.append(f"Python Simulator: {self.python_simulator['host']}:{self.python_simulator['port']}")
        report.append("")
        
        # Overall analysis
        report.append("OVERALL ANALYSIS:")
        report.append("-" * 40)
        
        issue_types = {}
        for register, result in results.items():
            issue_type = result['comparison']['issue_analysis']['issue_type']
            issue_types[issue_type] = issue_types.get(issue_type, 0) + 1
        
        most_common_issue = max(issue_types.items(), key=lambda x: x[1]) if issue_types else ('unknown', 0)
        
        report.append(f"Most common issue type: {most_common_issue[0]} ({most_common_issue[1]} registers)")
        report.append("")
        
        # Detailed register analysis
        report.append("DETAILED REGISTER ANALYSIS:")
        report.append("-" * 40)
        
        for register, result in results.items():
            report.append(f"\nRegister {register}: {result['description']}")
            comparison = result['comparison']
            issue_analysis = comparison['issue_analysis']
            
            report.append(f"  Lambda WP: {comparison['lambda_success_rate']:.1f}% success, "
                         f"{comparison['lambda_avg_response_time']:.1f}ms avg")
            report.append(f"  Simulator: {comparison['simulator_success_rate']:.1f}% success, "
                         f"{comparison['simulator_avg_response_time']:.1f}ms avg")
            report.append(f"  Issue Type: {issue_analysis['issue_type']}")
            report.append(f"  Confidence: {issue_analysis['confidence']}")
            report.append(f"  Explanation: {issue_analysis['explanation']}")
            
            if issue_analysis['recommendations']:
                report.append("  Recommendations:")
                for rec in issue_analysis['recommendations']:
                    report.append(f"    - {rec}")
        
        # Final recommendations
        report.append("\n" + "=" * 80)
        report.append("FINAL RECOMMENDATIONS:")
        report.append("=" * 80)
        
        if most_common_issue[0] == 'lambda_device_issue':
            report.append("🔧 PRIMARY ISSUE: Lambda Heat Pump Device")
            report.append("   The Python Simulator works fine, indicating network is OK.")
            report.append("   The issue is with the Lambda Heat Pump device itself.")
            report.append("")
            report.append("   Immediate actions:")
            report.append("   1. Check Lambda WP power and status")
            report.append("   2. Verify Lambda WP network connection")
            report.append("   3. Check Lambda WP error logs")
            report.append("   4. Consider Lambda WP restart")
            report.append("   5. Update HA const.py with longer timeouts for problematic registers")
        
        elif most_common_issue[0] == 'network_issue':
            report.append("🌐 PRIMARY ISSUE: Network Connectivity")
            report.append("   Both Lambda WP and Python Simulator have issues.")
            report.append("   This indicates a network problem.")
            report.append("")
            report.append("   Immediate actions:")
            report.append("   1. Check network connectivity")
            report.append("   2. Verify IP addresses and ports")
            report.append("   3. Check firewall settings")
            report.append("   4. Test with ping and telnet")
        
        elif most_common_issue[0] == 'no_issue':
            report.append("✅ NO MAJOR ISSUES DETECTED")
            report.append("   Both Lambda WP and Python Simulator are working.")
            report.append("   The issue might be intermittent or configuration-related.")
            report.append("")
            report.append("   Recommended actions:")
            report.append("   1. Monitor for intermittent issues")
            report.append("   2. Check HA integration configuration")
            report.append("   3. Verify network stability over time")
        
        else:
            report.append("⚠️  MIXED ISSUES DETECTED")
            report.append("   Both hosts have some issues, but not consistently.")
            report.append("   This suggests intermittent problems.")
            report.append("")
            report.append("   Recommended actions:")
            report.append("   1. Monitor both hosts over time")
            report.append("   2. Check network stability")
            report.append("   3. Verify both host configurations")
        
        return "\n".join(report)

def main():
    """Main function."""
    print("🔍 Lambda WP vs Python Simulator Analysis")
    print("=" * 60)
    
    # Show current configuration
    host_status = get_host_status()
    print(f"\n📋 Current Configuration:")
    print(f"   Real Lambda WP: {host_status['active_primary']['host']}:{host_status['active_primary']['port']}")
    print(f"   Python Simulator: {host_status['active_secondary']['host']}:{host_status['active_secondary']['port']}")
    print(f"   Host Switch: {'ENABLED' if host_status['switch_enabled'] else 'DISABLED'}")
    
    print(f"\n💡 Analysis Purpose:")
    print(f"   - Real Lambda WP: Tests actual device performance")
    print(f"   - Python Simulator: Tests network connectivity")
    print(f"   - Comparison: Identifies if issue is device or network related")
    
    try:
        analyzer = LambdaVsSimulatorAnalyzer()
        
        # Analyze critical registers
        print(f"\n🚀 Starting analysis...")
        results = analyzer.analyze_critical_registers()
        
        # Generate and display report
        print(f"\n📊 Generating diagnostic report...")
        report = analyzer.generate_diagnostic_report(results)
        
        print(f"\n" + "=" * 80)
        print(report)
        
        # Save report to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f"lambda_vs_simulator_analysis_{timestamp}.txt"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n✅ Analysis completed! Report saved to {report_file}")
        
    except KeyboardInterrupt:
        print(f"\n🛑 Analysis interrupted by user")
    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")

if __name__ == "__main__":
    main()

"""
Network Diagnostics for Modbus Communication
Performs comprehensive network tests including ping, port scans, and connectivity tests.
"""

import subprocess
import socket
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException

from const import (
    PRIMARY_HOST, PRIMARY_PORT, SECONDARY_HOST, SECONDARY_PORT,
    NETWORK_TEST_TARGETS, PING_COUNT, PING_INTERVAL, PING_TIMEOUT,
    PORT_SCAN_TIMEOUT, COMMON_MODBUS_PORTS, HIGH_LATENCY_THRESHOLD,
    PING_LOSS_THRESHOLD, DEFAULT_TIMEOUT,
    get_active_hosts, get_primary_host, get_secondary_host, get_host_status
)

logger = logging.getLogger(__name__)

@dataclass
class PingResult:
    """Result of a ping test."""
    target: str
    success: bool
    packets_sent: int
    packets_received: int
    packet_loss: float
    min_time: Optional[float] = None
    max_time: Optional[float] = None
    avg_time: Optional[float] = None
    error_message: Optional[str] = None

@dataclass
class PortScanResult:
    """Result of a port scan."""
    host: str
    port: int
    is_open: bool
    response_time: Optional[float] = None
    error_message: Optional[str] = None

@dataclass
class ModbusConnectivityResult:
    """Result of Modbus connectivity test."""
    host: str
    port: int
    register: int
    success: bool
    response_time: Optional[float] = None
    value: Optional[int] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None

@dataclass
class NetworkDiagnosticsResult:
    """Complete network diagnostics result."""
    timestamp: datetime
    ping_results: List[PingResult]
    port_scan_results: List[PortScanResult]
    modbus_connectivity_results: List[ModbusConnectivityResult]
    network_health_score: float
    issues_found: List[str]
    recommendations: List[str]

class NetworkDiagnostics:
    """Comprehensive network diagnostics for Modbus communication."""
    
    def __init__(self):
        self.test_targets = NETWORK_TEST_TARGETS
        
        # Get active hosts based on switch setting
        primary_host, primary_port, secondary_host, secondary_port = get_active_hosts()
        self.modbus_hosts = [
            (primary_host, primary_port),
            (secondary_host, secondary_port)
        ]
        self.test_registers = [0, 1000, 1001, 1002, 1003, 1004]  # Various registers to test
        
        # Get host status for logging
        host_status = get_host_status()
        
        logger.info("🔧 NetworkDiagnostics initialized")
        logger.info(f"   Test Targets: {self.test_targets}")
        logger.info(f"   Active Modbus Hosts: {self.modbus_hosts}")
        logger.info(f"   Host Switch: {'ENABLED' if host_status['switch_enabled'] else 'DISABLED'}")
        if host_status['switch_enabled']:
            logger.info(f"   Primary: {primary_host}:{primary_port} (was secondary)")
            logger.info(f"   Secondary: {secondary_host}:{secondary_port} (was primary)")
    
    def run_comprehensive_diagnostics(self) -> NetworkDiagnosticsResult:
        """Run comprehensive network diagnostics."""
        logger.info("🚀 Starting comprehensive network diagnostics")
        start_time = time.time()
        
        # Run all tests in parallel
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit ping tests
            ping_futures = {
                executor.submit(self._ping_host, target): target 
                for target in self.test_targets
            }
            
            # Submit port scans
            port_scan_futures = {}
            for host, port in self.modbus_hosts:
                for modbus_port in COMMON_MODBUS_PORTS:
                    future = executor.submit(self._scan_port, host, modbus_port)
                    port_scan_futures[future] = (host, modbus_port)
            
            # Submit Modbus connectivity tests
            modbus_futures = {}
            for host, port in self.modbus_hosts:
                for register in self.test_registers:
                    future = executor.submit(self._test_modbus_connectivity, host, port, register)
                    modbus_futures[future] = (host, port, register)
            
            # Collect results
            ping_results = []
            for future in as_completed(ping_futures):
                try:
                    result = future.result()
                    ping_results.append(result)
                except Exception as e:
                    target = ping_futures[future]
                    logger.error(f"❌ Ping test failed for {target}: {e}")
                    ping_results.append(PingResult(
                        target=target,
                        success=False,
                        packets_sent=0,
                        packets_received=0,
                        packet_loss=100.0,
                        error_message=str(e)
                    ))
            
            port_scan_results = []
            for future in as_completed(port_scan_futures):
                try:
                    result = future.result()
                    port_scan_results.append(result)
                except Exception as e:
                    host, port = port_scan_futures[future]
                    logger.error(f"❌ Port scan failed for {host}:{port}: {e}")
                    port_scan_results.append(PortScanResult(
                        host=host,
                        port=port,
                        is_open=False,
                        error_message=str(e)
                    ))
            
            modbus_results = []
            for future in as_completed(modbus_futures):
                try:
                    result = future.result()
                    modbus_results.append(result)
                except Exception as e:
                    host, port, register = modbus_futures[future]
                    logger.error(f"❌ Modbus test failed for {host}:{port} register {register}: {e}")
                    modbus_results.append(ModbusConnectivityResult(
                        host=host,
                        port=port,
                        register=register,
                        success=False,
                        error_message=str(e)
                    ))
        
        # Analyze results
        network_health_score = self._calculate_network_health_score(
            ping_results, port_scan_results, modbus_results
        )
        
        issues_found = self._identify_issues(ping_results, port_scan_results, modbus_results)
        recommendations = self._generate_recommendations(issues_found, ping_results, modbus_results)
        
        total_time = time.time() - start_time
        logger.info(f"✅ Network diagnostics completed in {total_time:.1f}s")
        logger.info(f"   Network Health Score: {network_health_score:.1f}/100")
        logger.info(f"   Issues Found: {len(issues_found)}")
        
        return NetworkDiagnosticsResult(
            timestamp=datetime.now(),
            ping_results=ping_results,
            port_scan_results=port_scan_results,
            modbus_connectivity_results=modbus_results,
            network_health_score=network_health_score,
            issues_found=issues_found,
            recommendations=recommendations
        )
    
    def _ping_host(self, target: str) -> PingResult:
        """Perform ping test to a host."""
        try:
            # Use ping command (works on Windows and Linux)
            cmd = [
                'ping', 
                '-c', str(PING_COUNT),  # Linux
                '-W', str(int(PING_TIMEOUT * 1000)),  # Linux timeout in ms
                target
            ]
            
            # Windows ping command
            if os.name == 'nt':
                cmd = [
                    'ping',
                    '-n', str(PING_COUNT),
                    '-w', str(int(PING_TIMEOUT * 1000)),
                    target
                ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=PING_TIMEOUT * 2
            )
            
            if result.returncode == 0:
                # Parse ping output
                return self._parse_ping_output(target, result.stdout)
            else:
                return PingResult(
                    target=target,
                    success=False,
                    packets_sent=PING_COUNT,
                    packets_received=0,
                    packet_loss=100.0,
                    error_message=result.stderr
                )
                
        except subprocess.TimeoutExpired:
            return PingResult(
                target=target,
                success=False,
                packets_sent=PING_COUNT,
                packets_received=0,
                packet_loss=100.0,
                error_message="Ping timeout"
            )
        except Exception as e:
            return PingResult(
                target=target,
                success=False,
                packets_sent=0,
                packets_received=0,
                packet_loss=100.0,
                error_message=str(e)
            )
    
    def _parse_ping_output(self, target: str, output: str) -> PingResult:
        """Parse ping command output."""
        try:
            lines = output.strip().split('\n')
            
            # Find statistics line
            stats_line = None
            for line in lines:
                if 'packets transmitted' in line.lower() or 'pakete gesendet' in line.lower():
                    stats_line = line
                    break
            
            if not stats_line:
                raise ValueError("Could not find ping statistics")
            
            # Parse statistics (Linux format)
            if 'packets transmitted' in stats_line.lower():
                # Linux format: "4 packets transmitted, 4 received, 0% packet loss"
                parts = stats_line.split(',')
                sent = int(parts[0].split()[0])
                received = int(parts[1].split()[0])
                loss = float(parts[2].split('%')[0])
            else:
                # Windows format or other
                sent = PING_COUNT
                received = PING_COUNT
                loss = 0.0
            
            # Find timing information
            min_time = max_time = avg_time = None
            for line in lines:
                if 'min/avg/max' in line.lower() or 'minimum/maximum/durchschnitt' in line.lower():
                    # Extract timing values
                    timing_part = line.split('=')[-1].strip()
                    times = timing_part.split('/')
                    if len(times) >= 3:
                        min_time = float(times[0])
                        avg_time = float(times[1])
                        max_time = float(times[2])
                    break
            
            return PingResult(
                target=target,
                success=received > 0,
                packets_sent=sent,
                packets_received=received,
                packet_loss=loss,
                min_time=min_time,
                max_time=max_time,
                avg_time=avg_time
            )
            
        except Exception as e:
            return PingResult(
                target=target,
                success=False,
                packets_sent=PING_COUNT,
                packets_received=0,
                packet_loss=100.0,
                error_message=f"Parse error: {e}"
            )
    
    def _scan_port(self, host: str, port: int) -> PortScanResult:
        """Scan a specific port on a host."""
        start_time = time.time()
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(PORT_SCAN_TIMEOUT)
            
            result = sock.connect_ex((host, port))
            response_time = (time.time() - start_time) * 1000
            
            sock.close()
            
            return PortScanResult(
                host=host,
                port=port,
                is_open=(result == 0),
                response_time=response_time
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return PortScanResult(
                host=host,
                port=port,
                is_open=False,
                response_time=response_time,
                error_message=str(e)
            )
    
    def _test_modbus_connectivity(self, host: str, port: int, register: int) -> ModbusConnectivityResult:
        """Test Modbus connectivity to a specific register."""
        start_time = time.time()
        
        try:
            client = ModbusTcpClient(host=host, port=port, timeout=DEFAULT_TIMEOUT)
            
            if not client.connect():
                raise ConnectionException(f"Failed to connect to {host}:{port}")
            
            result = client.read_holding_registers(address=register, count=1)
            
            if result.isError():
                raise ModbusException(f"Modbus error: {result}")
            
            response_time = (time.time() - start_time) * 1000
            value = result.registers[0] if result.registers else None
            
            client.close()
            
            return ModbusConnectivityResult(
                host=host,
                port=port,
                register=register,
                success=True,
                response_time=response_time,
                value=value
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ModbusConnectivityResult(
                host=host,
                port=port,
                register=register,
                success=False,
                response_time=response_time,
                error_type=type(e).__name__,
                error_message=str(e)
            )
    
    def _calculate_network_health_score(self, ping_results: List[PingResult], 
                                      port_scan_results: List[PortScanResult],
                                      modbus_results: List[ModbusConnectivityResult]) -> float:
        """Calculate overall network health score (0-100)."""
        score = 100.0
        
        # Deduct points for ping issues
        for ping in ping_results:
            if not ping.success:
                score -= 20  # Major penalty for unreachable hosts
            elif ping.packet_loss > PING_LOSS_THRESHOLD * 100:
                score -= 10  # Penalty for packet loss
            elif ping.avg_time and ping.avg_time > HIGH_LATENCY_THRESHOLD:
                score -= 5   # Penalty for high latency
        
        # Deduct points for port scan issues
        modbus_ports_failed = 0
        for scan in port_scan_results:
            if not scan.is_open and scan.port in COMMON_MODBUS_PORTS:
                modbus_ports_failed += 1
        
        if modbus_ports_failed > 0:
            score -= (modbus_ports_failed * 15)  # Penalty for closed Modbus ports
        
        # Deduct points for Modbus connectivity issues
        modbus_failures = sum(1 for result in modbus_results if not result.success)
        total_modbus_tests = len(modbus_results)
        
        if total_modbus_tests > 0:
            failure_rate = modbus_failures / total_modbus_tests
            score -= (failure_rate * 30)  # Penalty for Modbus failures
        
        return max(0.0, min(100.0, score))
    
    def _identify_issues(self, ping_results: List[PingResult],
                        port_scan_results: List[PortScanResult],
                        modbus_results: List[ModbusConnectivityResult]) -> List[str]:
        """Identify network issues from test results."""
        issues = []
        
        # Ping issues
        for ping in ping_results:
            if not ping.success:
                issues.append(f"Host {ping.target} is unreachable")
            elif ping.packet_loss > PING_LOSS_THRESHOLD * 100:
                issues.append(f"High packet loss to {ping.target}: {ping.packet_loss:.1f}%")
            elif ping.avg_time and ping.avg_time > HIGH_LATENCY_THRESHOLD:
                issues.append(f"High latency to {ping.target}: {ping.avg_time:.1f}ms")
        
        # Port scan issues
        for scan in port_scan_results:
            if not scan.is_open and scan.port in COMMON_MODBUS_PORTS:
                issues.append(f"Modbus port {scan.port} closed on {scan.host}")
        
        # Modbus connectivity issues
        host_failures = {}
        for result in modbus_results:
            if not result.success:
                key = f"{result.host}:{result.port}"
                if key not in host_failures:
                    host_failures[key] = []
                host_failures[key].append(result.register)
        
        for host_port, failed_registers in host_failures.items():
            if len(failed_registers) == len(self.test_registers):
                issues.append(f"Complete Modbus failure on {host_port}")
            else:
                issues.append(f"Modbus failures on {host_port} for registers: {failed_registers}")
        
        return issues
    
    def _generate_recommendations(self, issues: List[str], 
                                ping_results: List[PingResult],
                                modbus_results: List[ModbusConnectivityResult]) -> List[str]:
        """Generate recommendations based on identified issues."""
        recommendations = []
        
        # Network connectivity recommendations
        unreachable_hosts = [ping.target for ping in ping_results if not ping.success]
        if unreachable_hosts:
            recommendations.append(f"Check network connectivity to: {', '.join(unreachable_hosts)}")
        
        # High latency recommendations
        high_latency_hosts = [ping.target for ping in ping_results 
                            if ping.avg_time and ping.avg_time > HIGH_LATENCY_THRESHOLD]
        if high_latency_hosts:
            recommendations.append(f"Investigate network latency to: {', '.join(high_latency_hosts)}")
        
        # Modbus-specific recommendations
        modbus_hosts = set()
        for result in modbus_results:
            if not result.success:
                modbus_hosts.add(f"{result.host}:{result.port}")
        
        if modbus_hosts:
            recommendations.append(f"Check Modbus configuration on: {', '.join(modbus_hosts)}")
            recommendations.append("Verify Modbus device is powered on and responding")
            recommendations.append("Check firewall settings for Modbus ports (502, 5020, etc.)")
        
        # General recommendations
        if issues:
            recommendations.append("Consider increasing Modbus timeouts in const.py")
            recommendations.append("Enable individual reads for problematic registers")
            recommendations.append("Check for network congestion during peak hours")
        
        return recommendations
    
    def test_specific_host(self, host: str, port: int, register: int = 1000) -> ModbusConnectivityResult:
        """Test connectivity to a specific host and register."""
        logger.info(f"🔍 Testing {host}:{port} register {register}")
        return self._test_modbus_connectivity(host, port, register)
    
    def quick_network_check(self) -> Dict:
        """Perform a quick network check and return summary."""
        logger.info("⚡ Running quick network check")
        
        # Get active hosts
        primary_host, primary_port, secondary_host, secondary_port = get_active_hosts()
        
        # Test primary and secondary hosts
        primary_result = self.test_specific_host(primary_host, primary_port)
        secondary_result = self.test_specific_host(secondary_host, secondary_port)
        
        # Test gateway connectivity
        gateway_ping = self._ping_host("192.168.178.1")  # Assuming standard gateway
        
        return {
            'timestamp': datetime.now(),
            'primary_host': {
                'host': primary_host,
                'port': primary_port,
                'success': primary_result.success,
                'response_time': primary_result.response_time,
                'error': primary_result.error_message
            },
            'secondary_host': {
                'host': secondary_host,
                'port': secondary_port,
                'success': secondary_result.success,
                'response_time': secondary_result.response_time,
                'error': secondary_result.error_message
            },
            'gateway': {
                'host': '192.168.178.1',
                'success': gateway_ping.success,
                'packet_loss': gateway_ping.packet_loss,
                'avg_latency': gateway_ping.avg_time
            },
            'overall_status': 'good' if (primary_result.success or secondary_result.success) and gateway_ping.success else 'poor',
            'host_switch_status': get_host_status()
        }
    
    def export_diagnostics_to_file(self, result: NetworkDiagnosticsResult, output_file: str):
        """Export diagnostics result to file."""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=== NETWORK DIAGNOSTICS REPORT ===\n\n")
                f.write(f"Timestamp: {result.timestamp}\n")
                f.write(f"Network Health Score: {result.network_health_score:.1f}/100\n\n")
                
                f.write("=== PING RESULTS ===\n")
                for ping in result.ping_results:
                    f.write(f"{ping.target}: {'✅' if ping.success else '❌'} ")
                    if ping.success:
                        f.write(f"Loss: {ping.packet_loss:.1f}%, Avg: {ping.avg_time:.1f}ms\n")
                    else:
                        f.write(f"Error: {ping.error_message}\n")
                
                f.write("\n=== PORT SCAN RESULTS ===\n")
                for scan in result.port_scan_results:
                    f.write(f"{scan.host}:{scan.port} - {'✅ Open' if scan.is_open else '❌ Closed'}")
                    if scan.response_time:
                        f.write(f" ({scan.response_time:.1f}ms)")
                    f.write("\n")
                
                f.write("\n=== MODBUS CONNECTIVITY ===\n")
                for modbus in result.modbus_connectivity_results:
                    f.write(f"{modbus.host}:{modbus.port} Reg{modbus.register}: {'✅' if modbus.success else '❌'} ")
                    if modbus.success:
                        f.write(f"Value: {modbus.value}, Time: {modbus.response_time:.1f}ms\n")
                    else:
                        f.write(f"Error: {modbus.error_message}\n")
                
                f.write("\n=== ISSUES FOUND ===\n")
                for issue in result.issues_found:
                    f.write(f"❌ {issue}\n")
                
                f.write("\n=== RECOMMENDATIONS ===\n")
                for rec in result.recommendations:
                    f.write(f"💡 {rec}\n")
            
            logger.info(f"✅ Diagnostics exported to {output_file}")
            
        except Exception as e:
            logger.error(f"❌ Failed to export diagnostics: {e}")

def main():
    """Main function for testing network diagnostics."""
    logging.basicConfig(level=logging.INFO)
    
    diagnostics = NetworkDiagnostics()
    
    # Run quick check first
    print("⚡ Quick Network Check:")
    quick_result = diagnostics.quick_network_check()
    print(f"   Primary Host: {'✅' if quick_result['primary_host']['success'] else '❌'}")
    print(f"   Secondary Host: {'✅' if quick_result['secondary_host']['success'] else '❌'}")
    print(f"   Gateway: {'✅' if quick_result['gateway']['success'] else '❌'}")
    print(f"   Overall Status: {quick_result['overall_status']}")
    
    # Run comprehensive diagnostics
    print("\n🚀 Running Comprehensive Diagnostics...")
    result = diagnostics.run_comprehensive_diagnostics()
    
    print(f"\n📊 Results:")
    print(f"   Network Health Score: {result.network_health_score:.1f}/100")
    print(f"   Issues Found: {len(result.issues_found)}")
    print(f"   Recommendations: {len(result.recommendations)}")
    
    if result.issues_found:
        print("\n❌ Issues:")
        for issue in result.issues_found:
            print(f"   - {issue}")
    
    if result.recommendations:
        print("\n💡 Recommendations:")
        for rec in result.recommendations:
            print(f"   - {rec}")

if __name__ == "__main__":
    import os
    main()

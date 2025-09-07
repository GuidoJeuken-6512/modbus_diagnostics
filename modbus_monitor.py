"""
Modbus Monitor with Random Distribution and Fallback Host Support
Monitors Modbus registers with anti-synchronization and automatic fallback to secondary host.
"""

import time
import random
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
import sqlite3
import json

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException

from const import (
    PRIMARY_HOST, PRIMARY_PORT, SECONDARY_HOST, SECONDARY_PORT,
    TEST_REGISTER, TEST_REGISTER_COUNT, BASE_MONITORING_INTERVAL,
    RANDOM_INTERVAL_RANGE, MIN_INTERVAL, MAX_INTERVAL,
    DEFAULT_TIMEOUT, MAX_RETRIES, RETRY_DELAY, EXPONENTIAL_BACKOFF,
    TIMEOUT_THRESHOLD, ERROR_RATE_THRESHOLD, FAILURE_THRESHOLD,
    DB_FILE, TABLES, get_random_interval, get_timeout_for_register,
    get_active_hosts, get_primary_host, get_secondary_host, get_host_status,
    HOST_ACCESS_MODE, get_host_access_mode,
    LAMBDA_UNIT_ID, LAMBDA_TIMEOUT, LAMBDA_CRITICAL_REGISTERS
)

logger = logging.getLogger(__name__)

@dataclass
class ModbusResult:
    """Result of a Modbus read operation."""
    timestamp: datetime
    host: str
    port: int
    register: int
    success: bool
    response_time: Optional[float] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    value: Optional[int] = None
    retry_count: int = 0

@dataclass
class HostStatus:
    """Status information for a Modbus host."""
    host: str
    port: int
    is_available: bool = True
    consecutive_failures: int = 0
    total_failures: int = 0
    total_successes: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    avg_response_time: float = 0.0
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    circuit_breaker_open: bool = False
    circuit_breaker_until: Optional[datetime] = None

@dataclass
class MonitorConfig:
    """Configuration for the Modbus monitor."""
    primary_host: str = PRIMARY_HOST
    primary_port: int = PRIMARY_PORT
    secondary_host: str = SECONDARY_HOST
    secondary_port: int = SECONDARY_PORT
    test_register: int = TEST_REGISTER
    register_count: int = TEST_REGISTER_COUNT
    base_interval: float = BASE_MONITORING_INTERVAL
    random_range: float = RANDOM_INTERVAL_RANGE
    min_interval: float = MIN_INTERVAL
    max_interval: float = MAX_INTERVAL
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = MAX_RETRIES
    retry_delay: float = RETRY_DELAY
    exponential_backoff: bool = EXPONENTIAL_BACKOFF
    timeout_threshold: int = TIMEOUT_THRESHOLD
    error_rate_threshold: float = ERROR_RATE_THRESHOLD
    failure_threshold: int = FAILURE_THRESHOLD

class ModbusMonitor:
    """Modbus monitor with random distribution and fallback support."""
    
    def __init__(self, config: MonitorConfig = None, db_path: str = DB_FILE):
        self.config = config or MonitorConfig()
        self.db_path = db_path
        self.running = False
        self.monitor_thread = None
        self.stop_event = threading.Event()
        
        # Get active hosts based on switch setting
        primary_host, primary_port, secondary_host, secondary_port = get_active_hosts()
        
        # Host status tracking
        self.host_status = {
            'primary': HostStatus(primary_host, primary_port),
            'secondary': HostStatus(secondary_host, secondary_port)
        }
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'timeout_requests': 0,
            'fallback_switches': 0,
            'alternating_switches': 0,
            'both_host_tests': 0,
            'start_time': None
        }
        
        # Alternating mode state
        self.alternating_counter = 0
        
        # Callbacks
        self.callbacks = {
            'on_result': [],
            'on_fallback': [],
            'on_circuit_breaker': [],
            'on_error': []
        }
        
        # Initialize database
        self._init_database()
        
        # Get host status for logging
        host_status = get_host_status()
        access_mode_info = get_host_access_mode()
        
        logger.info(f"🔧 ModbusMonitor initialized")
        logger.info(f"   Active Primary: {primary_host}:{primary_port} (original: {host_status['active_primary']['original_role']})")
        logger.info(f"   Active Secondary: {secondary_host}:{secondary_port} (original: {host_status['active_secondary']['original_role']})")
        logger.info(f"   Host Switch: {'ENABLED' if host_status['switch_enabled'] else 'DISABLED'}")
        logger.info(f"   Access Mode: {HOST_ACCESS_MODE} - {access_mode_info['description']}")
        logger.info(f"   Test Register: {self.config.test_register}")
        logger.info(f"   Interval: {self.config.base_interval}s ± {self.config.random_range}s")
    
    def _init_database(self):
        """Initialize SQLite database for storing results."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create tables
                for table_name, create_sql in TABLES.items():
                    cursor.execute(create_sql)
                
                conn.commit()
                logger.info(f"✅ Database initialized: {self.db_path}")
                
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
    
    def add_callback(self, event_type: str, callback: Callable):
        """Add callback for specific events."""
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
        else:
            logger.warning(f"Unknown callback type: {event_type}")
    
    def start_monitoring(self):
        """Start the monitoring thread."""
        if self.running:
            logger.warning("⚠️  Monitoring already running")
            return
        
        self.running = True
        self.stop_event.clear()
        self.stats['start_time'] = datetime.now()
        
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("🚀 Modbus monitoring started")
    
    def stop_monitoring(self):
        """Stop the monitoring thread."""
        if not self.running:
            logger.warning("⚠️  Monitoring not running")
            return
        
        self.running = False
        self.stop_event.set()
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("🛑 Modbus monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop with random intervals."""
        logger.info("🔄 Starting monitor loop with random intervals")
        
        while self.running and not self.stop_event.is_set():
            try:
                # Calculate next interval with random distribution
                next_interval = get_random_interval()
                
                # Perform Modbus read
                result = self._perform_modbus_read()
                
                # Process result
                self._process_result(result)
                
                # Update statistics
                self._update_statistics(result)
                
                # Store in database
                self._store_result(result)
                
                # Trigger callbacks
                self._trigger_callbacks('on_result', result)
                
                # Wait for next interval
                logger.debug(f"⏱️  Next read in {next_interval:.1f}s")
                self.stop_event.wait(next_interval)
                
            except Exception as e:
                logger.error(f"❌ Error in monitor loop: {e}")
                self._trigger_callbacks('on_error', e)
                time.sleep(5)  # Wait before retrying
    
    def _perform_modbus_read(self) -> ModbusResult:
        """Perform a Modbus read operation based on access mode."""
        if HOST_ACCESS_MODE == 'fallback':
            return self._perform_fallback_read()
        elif HOST_ACCESS_MODE == 'alternating':
            return self._perform_alternating_read()
        elif HOST_ACCESS_MODE == 'both':
            return self._perform_both_hosts_read()
        elif HOST_ACCESS_MODE == 'primary_only':
            return self._read_from_host('primary')
        elif HOST_ACCESS_MODE == 'secondary_only':
            return self._read_from_host('secondary')
        else:
            logger.warning(f"⚠️  Unknown access mode: {HOST_ACCESS_MODE}, using fallback")
            return self._perform_fallback_read()
    
    def _perform_fallback_read(self) -> ModbusResult:
        """Perform fallback read: Primary first, Secondary only on failure."""
        # Try primary host first
        primary_result = self._read_from_host('primary')
        
        if primary_result.success:
            return primary_result
        
        # If primary fails, try secondary host
        logger.warning(f"⚠️  Primary host failed, trying secondary host")
        secondary_result = self._read_from_host('secondary')
        
        if secondary_result.success:
            self.stats['fallback_switches'] += 1
            self._trigger_callbacks('on_fallback', {
                'from': 'primary',
                'to': 'secondary',
                'reason': primary_result.error_message
            })
            return secondary_result
        
        # Both hosts failed
        logger.error(f"❌ Both hosts failed - Primary: {primary_result.error_message}, Secondary: {secondary_result.error_message}")
        
        # Return the primary result as the main failure
        return primary_result
    
    def _perform_alternating_read(self) -> ModbusResult:
        """Perform alternating read: Switch between hosts each request."""
        # Alternate between primary and secondary
        if self.alternating_counter % 2 == 0:
            host_type = 'primary'
            other_host = 'secondary'
        else:
            host_type = 'secondary'
            other_host = 'primary'
        
        self.alternating_counter += 1
        
        # Try the selected host
        result = self._read_from_host(host_type)
        
        if result.success:
            return result
        
        # If selected host fails, try the other host
        logger.warning(f"⚠️  {host_type} host failed, trying {other_host} host")
        fallback_result = self._read_from_host(other_host)
        
        if fallback_result.success:
            self.stats['alternating_switches'] += 1
            self._trigger_callbacks('on_fallback', {
                'from': host_type,
                'to': other_host,
                'reason': result.error_message
            })
            return fallback_result
        
        # Both hosts failed
        logger.error(f"❌ Both hosts failed - {host_type}: {result.error_message}, {other_host}: {fallback_result.error_message}")
        return result
    
    def _perform_both_hosts_read(self) -> ModbusResult:
        """Perform read on both hosts and return the best result."""
        self.stats['both_host_tests'] += 1
        
        # Test both hosts
        primary_result = self._read_from_host('primary')
        secondary_result = self._read_from_host('secondary')
        
        # Log both results in detail
        logger.info(f"🔍 Both hosts test:")
        logger.info(f"   Primary ({primary_result.host}:{primary_result.port}): {'✅' if primary_result.success else '❌'} - "
                   f"{'Value: ' + str(primary_result.value) + ', ' if primary_result.success else ''}"
                   f"{primary_result.response_time:.1f}ms")
        logger.info(f"   Secondary ({secondary_result.host}:{secondary_result.port}): {'✅' if secondary_result.success else '❌'} - "
                   f"{'Value: ' + str(secondary_result.value) + ', ' if secondary_result.success else ''}"
                   f"{secondary_result.response_time:.1f}ms")
        
        # Return the best result
        if primary_result.success and secondary_result.success:
            # Both successful, return the faster one
            if primary_result.response_time <= secondary_result.response_time:
                logger.info(f"   → Using Primary (faster: {primary_result.response_time:.1f}ms vs {secondary_result.response_time:.1f}ms)")
                return primary_result
            else:
                logger.info(f"   → Using Secondary (faster: {secondary_result.response_time:.1f}ms vs {primary_result.response_time:.1f}ms)")
                return secondary_result
        elif primary_result.success:
            return primary_result
        elif secondary_result.success:
            return secondary_result
        else:
            # Both failed, return primary result
            logger.error(f"❌ Both hosts failed - Primary: {primary_result.error_message}, "
                        f"Secondary: {secondary_result.error_message}")
            return primary_result
    
    def _read_from_host(self, host_type: str) -> ModbusResult:
        """Read from a specific host with retry logic."""
        host_status = self.host_status[host_type]
        
        # Check circuit breaker
        if host_status.circuit_breaker_open:
            if host_status.circuit_breaker_until and datetime.now() < host_status.circuit_breaker_until:
                return ModbusResult(
                    timestamp=datetime.now(),
                    host=host_status.host,
                    port=host_status.port,
                    register=self.config.test_register,
                    success=False,
                    error_type="circuit_breaker",
                    error_message="Circuit breaker open"
                )
            else:
                # Circuit breaker timeout expired, reset
                host_status.circuit_breaker_open = False
                host_status.circuit_breaker_until = None
                logger.info(f"🔄 Circuit breaker reset for {host_type} host")
        
        # Perform read with retries
        for attempt in range(self.config.max_retries + 1):
            result = self._single_read_attempt(host_status, attempt)
            
            if result.success:
                # Update host status on success
                self._update_host_status_success(host_status, result.response_time)
                return result
            
            # Wait before retry (exponential backoff)
            if attempt < self.config.max_retries:
                delay = self.config.retry_delay * (2 ** attempt) if self.config.exponential_backoff else self.config.retry_delay
                delay += random.uniform(0, delay * 0.2)  # Add jitter
                logger.debug(f"⏳ Retry {attempt + 1}/{self.config.max_retries} in {delay:.1f}s")
                time.sleep(delay)
        
        # All retries failed
        self._update_host_status_failure(host_status, result.error_message)
        return result
    
    def _single_read_attempt(self, host_status: HostStatus, attempt: int) -> ModbusResult:
        """Perform a single Modbus read attempt."""
        start_time = time.time()
        
        try:
            # Create Modbus client (simplified like in client_gui.py but with configurable port)
            client = ModbusTcpClient(host_status.host, port=host_status.port)
            
            # Connect
            if not client.connect():
                raise ConnectionException(f"Failed to connect to {host_status.host}:{host_status.port}")
            
            # Read register
            result = client.read_holding_registers(
                address=self.config.test_register,
                count=self.config.register_count
            )
            
            # Check for Modbus errors
            if result.isError():
                raise ModbusException(f"Modbus error: {result}")
            
            # Calculate response time
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Extract value
            value = result.registers[0] if result.registers else None
            
            client.close()
            
            return ModbusResult(
                timestamp=datetime.now(),
                host=host_status.host,
                port=host_status.port,
                register=self.config.test_register,
                success=True,
                response_time=response_time,
                value=value,
                retry_count=attempt
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            return ModbusResult(
                timestamp=datetime.now(),
                host=host_status.host,
                port=host_status.port,
                register=self.config.test_register,
                success=False,
                response_time=response_time,
                error_type=type(e).__name__,
                error_message=str(e),
                retry_count=attempt
            )
    
    def _update_host_status_success(self, host_status: HostStatus, response_time: float):
        """Update host status after successful read."""
        host_status.is_available = True
        host_status.consecutive_failures = 0
        host_status.total_successes += 1
        host_status.last_success = datetime.now()
        
        # Update response time statistics
        host_status.response_times.append(response_time)
        host_status.avg_response_time = sum(host_status.response_times) / len(host_status.response_times)
        
        # Reset circuit breaker if it was open
        if host_status.circuit_breaker_open:
            host_status.circuit_breaker_open = False
            host_status.circuit_breaker_until = None
            logger.info(f"✅ Circuit breaker closed for {host_status.host}")
    
    def _update_host_status_failure(self, host_status: HostStatus, error_message: str):
        """Update host status after failed read."""
        host_status.consecutive_failures += 1
        host_status.total_failures += 1
        host_status.last_failure = datetime.now()
        
        # Check if circuit breaker should open
        if host_status.consecutive_failures >= self.config.failure_threshold:
            if not host_status.circuit_breaker_open:
                host_status.circuit_breaker_open = True
                host_status.circuit_breaker_until = datetime.now() + timedelta(seconds=60)
                logger.warning(f"🔴 Circuit breaker opened for {host_status.host} after {host_status.consecutive_failures} failures")
                self._trigger_callbacks('on_circuit_breaker', {
                    'host': host_status.host,
                    'port': host_status.port,
                    'failures': host_status.consecutive_failures
                })
    
    def _process_result(self, result: ModbusResult):
        """Process and log the result."""
        if result.success:
            logger.info(f"✅ {result.host}:{result.port} - Register {result.register} = {result.value} "
                       f"({result.response_time:.1f}ms, retry {result.retry_count})")
        else:
            logger.error(f"❌ {result.host}:{result.port} - Register {result.register} failed: "
                        f"{result.error_type}: {result.error_message} "
                        f"({result.response_time:.1f}ms, retry {result.retry_count})")
    
    def _update_statistics(self, result: ModbusResult):
        """Update monitoring statistics."""
        self.stats['total_requests'] += 1
        
        if result.success:
            self.stats['successful_requests'] += 1
        else:
            self.stats['failed_requests'] += 1
            
            if result.error_type == "TimeoutError" or "timeout" in str(result.error_message).lower():
                self.stats['timeout_requests'] += 1
    
    def _store_result(self, result: ModbusResult):
        """Store result in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO performance_log 
                    (timestamp, host, port, register, success, response_time, error_type, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.timestamp,
                    result.host,
                    result.port,
                    result.register,
                    result.success,
                    result.response_time,
                    result.error_type,
                    result.error_message
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"❌ Failed to store result in database: {e}")
    
    def _trigger_callbacks(self, event_type: str, data):
        """Trigger callbacks for specific events."""
        for callback in self.callbacks.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"❌ Callback error for {event_type}: {e}")
    
    def get_statistics(self) -> Dict:
        """Get current monitoring statistics."""
        uptime = datetime.now() - self.stats['start_time'] if self.stats['start_time'] else timedelta(0)
        
        return {
            'uptime_seconds': uptime.total_seconds(),
            'total_requests': self.stats['total_requests'],
            'successful_requests': self.stats['successful_requests'],
            'failed_requests': self.stats['failed_requests'],
            'timeout_requests': self.stats['timeout_requests'],
            'fallback_switches': self.stats['fallback_switches'],
            'alternating_switches': self.stats['alternating_switches'],
            'both_host_tests': self.stats['both_host_tests'],
            'success_rate': (self.stats['successful_requests'] / max(1, self.stats['total_requests'])) * 100,
            'access_mode': HOST_ACCESS_MODE,
            'host_status': {
                'primary': {
                    'host': self.host_status['primary'].host,
                    'port': self.host_status['primary'].port,
                    'available': self.host_status['primary'].is_available,
                    'consecutive_failures': self.host_status['primary'].consecutive_failures,
                    'total_failures': self.host_status['primary'].total_failures,
                    'total_successes': self.host_status['primary'].total_successes,
                    'avg_response_time': self.host_status['primary'].avg_response_time,
                    'circuit_breaker_open': self.host_status['primary'].circuit_breaker_open
                },
                'secondary': {
                    'host': self.host_status['secondary'].host,
                    'port': self.host_status['secondary'].port,
                    'available': self.host_status['secondary'].is_available,
                    'consecutive_failures': self.host_status['secondary'].consecutive_failures,
                    'total_failures': self.host_status['secondary'].total_failures,
                    'total_successes': self.host_status['secondary'].total_successes,
                    'avg_response_time': self.host_status['secondary'].avg_response_time,
                    'circuit_breaker_open': self.host_status['secondary'].circuit_breaker_open
                }
            }
        }
    
    def get_recent_results(self, limit: int = 100) -> List[Dict]:
        """Get recent monitoring results from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT timestamp, host, port, register, success, response_time, error_type, error_message
                    FROM performance_log
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'timestamp': row[0],
                        'host': row[1],
                        'port': row[2],
                        'register': row[3],
                        'success': bool(row[4]),
                        'response_time': row[5],
                        'error_type': row[6],
                        'error_message': row[7]
                    })
                
                return results
                
        except Exception as e:
            logger.error(f"❌ Failed to get recent results: {e}")
            return []
    
    def export_results_to_file(self, output_file: str, hours_back: int = 24):
        """Export monitoring results to file."""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT timestamp, host, port, register, success, response_time, error_type, error_message
                    FROM performance_log
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                """, (cutoff_time,))
                
                results = cursor.fetchall()
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=== MODBUS MONITORING RESULTS ===\n\n")
                f.write(f"Export Period: {cutoff_time} to {datetime.now()}\n")
                f.write(f"Total Records: {len(results)}\n\n")
                
                f.write("Timestamp,Host,Port,Register,Success,ResponseTime(ms),ErrorType,ErrorMessage\n")
                for row in results:
                    f.write(f"{row[0]},{row[1]},{row[2]},{row[3]},{row[4]},{row[5]},{row[6]},{row[7]}\n")
            
            logger.info(f"✅ Results exported to {output_file}")
            
        except Exception as e:
            logger.error(f"❌ Failed to export results: {e}")

def main():
    """Main function for testing the Modbus monitor."""
    logging.basicConfig(level=logging.INFO)
    
    # Create monitor
    config = MonitorConfig()
    monitor = ModbusMonitor(config)
    
    # Add callbacks
    def on_fallback(data):
        print(f"🔄 Fallback: {data['from']} -> {data['to']} ({data['reason']})")
    
    def on_circuit_breaker(data):
        print(f"🔴 Circuit breaker opened for {data['host']} after {data['failures']} failures")
    
    monitor.add_callback('on_fallback', on_fallback)
    monitor.add_callback('on_circuit_breaker', on_circuit_breaker)
    
    try:
        # Start monitoring
        monitor.start_monitoring()
        
        # Run for 5 minutes
        print("🚀 Monitoring started - press Ctrl+C to stop")
        time.sleep(300)
        
    except KeyboardInterrupt:
        print("\n🛑 Stopping monitor...")
    finally:
        monitor.stop_monitoring()
        
        # Print statistics
        stats = monitor.get_statistics()
        print(f"\n📊 Final Statistics:")
        print(f"   Total Requests: {stats['total_requests']}")
        print(f"   Success Rate: {stats['success_rate']:.1f}%")
        print(f"   Fallback Switches: {stats['fallback_switches']}")
        print(f"   Primary Host: {stats['host_status']['primary']['available']}")
        print(f"   Secondary Host: {stats['host_status']['secondary']['available']}")

if __name__ == "__main__":
    main()

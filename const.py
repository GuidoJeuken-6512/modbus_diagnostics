# Modbus Diagnostics Tool - Configuration Constants
# Lambda Heat Pumps Modbus Communication Diagnostics

import os
from typing import Dict, List, Tuple

# =============================================================================
# MODBUS CONNECTION SETTINGS
# =============================================================================

# Host Switch Configuration
# Set to True to use secondary host as primary (for testing/fallback)
USE_SECONDARY_AS_PRIMARY = False

# Host Access Mode Configuration
# Options: 'fallback', 'alternating', 'both', 'primary_only', 'secondary_only'
HOST_ACCESS_MODE = 'fallback'  # Test Python Simulator only

# Primary Modbus Host (Real Lambda Heat Pump)
PRIMARY_HOST = "192.168.178.125"
PRIMARY_PORT = 502

# Secondary Modbus Host (Python Modbus Server - Lambda WP Simulator)
SECONDARY_HOST = "192.168.178.57"
SECONDARY_PORT = 5020

# Test Register Configuration (based on Lambda specification)
TEST_REGISTER = 1000  # Heat pump 1 Error state
TEST_REGISTER_COUNT = 1

# Lambda-specific Register Configuration
LAMBDA_UNIT_ID = 1  # Fixed Unit ID according to specification
LAMBDA_TIMEOUT = 60  # 1 minute timeout according to specification
LAMBDA_MAX_CONNECTIONS = 16  # Maximum 16 communication channels

# Critical Lambda Registers (based on specification and your logs)
LAMBDA_CRITICAL_REGISTERS = {
    # General Module (Index 0)
    0: "General Error number",
    1: "General Operating state", 
    2: "Actual ambient temperature",
    
    # Heat Pump Module (Index 1, Subindex 0 = Heat pump 1)
    1000: "Heat pump 1 Error state",
    1001: "Heat pump 1 Error number", 
    1002: "Heat pump 1 State",
    1003: "Heat pump 1 Operating state",
    1004: "Heat pump 1 Flow line temperature",
    1005: "Heat pump 1 Return line temperature",
    
    # Heat Pump Module (Index 1, Subindex 1 = Heat pump 2)
    1100: "Heat pump 2 Error state",
    1101: "Heat pump 2 Error number",
    1102: "Heat pump 2 State", 
    1103: "Heat pump 2 Operating state",
    
    # Heating Circuit Module (Index 5)
    5000: "Heating circuit 1 Error number",
    5001: "Heating circuit 1 Operating state",
    5002: "Heating circuit 1 Flow line temperature",
    5050: "Heating circuit 1 Offset flow line temp setpoint",
    5051: "Heating circuit 1 Setpoint room heating temp"
}

# =============================================================================
# DYNAMIC HOST CONFIGURATION
# =============================================================================

def get_active_hosts():
    """
    Get active primary and secondary hosts based on switch setting.
    Returns: (primary_host, primary_port, secondary_host, secondary_port)
    """
    if USE_SECONDARY_AS_PRIMARY:
        # Switch: Secondary becomes primary, Primary becomes secondary
        return SECONDARY_HOST, SECONDARY_PORT, PRIMARY_HOST, PRIMARY_PORT
    else:
        # Normal: Primary stays primary, Secondary stays secondary
        return PRIMARY_HOST, PRIMARY_PORT, SECONDARY_HOST, SECONDARY_PORT

def get_primary_host():
    """Get current primary host configuration."""
    primary_host, primary_port, _, _ = get_active_hosts()
    return primary_host, primary_port

def get_secondary_host():
    """Get current secondary host configuration."""
    _, _, secondary_host, secondary_port = get_active_hosts()
    return secondary_host, secondary_port

def switch_hosts():
    """Toggle the host switch setting."""
    global USE_SECONDARY_AS_PRIMARY
    USE_SECONDARY_AS_PRIMARY = not USE_SECONDARY_AS_PRIMARY
    return USE_SECONDARY_AS_PRIMARY

def get_host_status():
    """Get current host configuration status."""
    primary_host, primary_port, secondary_host, secondary_port = get_active_hosts()
    
    return {
        'switch_enabled': USE_SECONDARY_AS_PRIMARY,
        'access_mode': HOST_ACCESS_MODE,
        'active_primary': {
            'host': primary_host,
            'port': primary_port,
            'original_role': 'secondary' if USE_SECONDARY_AS_PRIMARY else 'primary'
        },
        'active_secondary': {
            'host': secondary_host,
            'port': secondary_port,
            'original_role': 'primary' if USE_SECONDARY_AS_PRIMARY else 'secondary'
        },
        'original_primary': {
            'host': PRIMARY_HOST,
            'port': PRIMARY_PORT
        },
        'original_secondary': {
            'host': SECONDARY_HOST,
            'port': SECONDARY_PORT
        }
    }

def get_host_access_mode():
    """Get current host access mode with description."""
    modes = {
        'fallback': {
            'description': 'Secondary (Python Simulator) wird nur bei Primary (Lambda WP) Fehlern verwendet',
            'behavior': 'Primary (Real Lambda) first, Secondary (Simulator) only on failure'
        },
        'alternating': {
            'description': 'Wechselt zwischen Primary (Lambda WP) und Secondary (Python Simulator) ab',
            'behavior': 'Alternates between real Lambda and simulator each request'
        },
        'both': {
            'description': 'Beide Hosts werden bei jedem Request getestet (Lambda WP + Python Simulator)',
            'behavior': 'Tests both real Lambda and simulator on every request'
        },
        'primary_only': {
            'description': 'Nur Primary Host (Real Lambda WP) wird verwendet',
            'behavior': 'Only uses real Lambda heat pump'
        },
        'secondary_only': {
            'description': 'Nur Secondary Host (Python Simulator) wird verwendet',
            'behavior': 'Only uses Python Modbus simulator'
        }
    }
    
    return {
        'current_mode': HOST_ACCESS_MODE,
        'description': modes.get(HOST_ACCESS_MODE, {}).get('description', 'Unknown mode'),
        'behavior': modes.get(HOST_ACCESS_MODE, {}).get('behavior', 'Unknown behavior'),
        'available_modes': list(modes.keys())
    }

# =============================================================================
# TIMING AND INTERVAL SETTINGS
# =============================================================================

# Base monitoring interval (seconds)
BASE_MONITORING_INTERVAL = 30

# Random interval range (±seconds)
RANDOM_INTERVAL_RANGE = 5

# Minimum and maximum intervals
MIN_INTERVAL = 25
MAX_INTERVAL = 35

# Timeout settings (adjusted for Lambda specification)
DEFAULT_TIMEOUT = 5.0  # Reduced from Lambda's 60s for faster diagnostics
EXTENDED_TIMEOUT = 10.0
QUICK_TIMEOUT = 2.0
LAMBDA_SPEC_TIMEOUT = 60.0  # Official Lambda specification timeout

# =============================================================================
# RETRY AND ERROR HANDLING
# =============================================================================

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2.0
EXPONENTIAL_BACKOFF = True
MAX_RETRY_DELAY = 30.0

# Error thresholds
TIMEOUT_THRESHOLD = 3  # Consecutive timeouts before fallback
ERROR_RATE_THRESHOLD = 0.1  # 10% error rate threshold
FAILURE_THRESHOLD = 5  # Total failures before recommendations

# =============================================================================
# LOGGING AND MONITORING
# =============================================================================

# Log levels
LOG_LEVEL = "INFO"
DEBUG_MODE = False

# Log file paths
LOG_DIR = "logs"
MAIN_LOG_FILE = os.path.join(LOG_DIR, "modbus_diagnostics.log")
PERFORMANCE_LOG_FILE = os.path.join(LOG_DIR, "performance.log")
ERROR_LOG_FILE = os.path.join(LOG_DIR, "errors.log")

# Log rotation
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5

# =============================================================================
# HA INTEGRATION SETTINGS
# =============================================================================

# HA Log file path (adjust as needed)
HA_LOG_PATH = "home-assistant.log"

# Sensor name to register mapping (updated based on Lambda specification)
SENSOR_TO_REGISTER_MAP = {
    # General Module
    'eu08l_ambient_error_number': 0,
    'eu08l_ambient_operating_state': 1,
    'eu08l_ambient_temperature': 2,
    
    # Heat Pump 1 Module
    'eu08l_hp1_error_state': 1000,
    'eu08l_hp1_error_number': 1001,
    'eu08l_hp1_state': 1002,
    'eu08l_hp1_operating_state': 1003,
    'eu08l_hp1_flow_temperature': 1004,
    'eu08l_hp1_return_temperature': 1005,
    'eu08l_hp1_compressor_rating': 1010,
    'eu08l_hp1_heating_capacity': 1011,
    'eu08l_hp1_cop': 1013,
    'eu08l_hp1_compressor_power_consumption_accumulated': 1020,
    'eu08l_hp1_compressor_thermal_energy_output_accumulated': 1022,
    
    # Heat Pump 2 Module
    'eu08l_hp2_error_state': 1100,
    'eu08l_hp2_error_number': 1101,
    'eu08l_hp2_state': 1102,
    'eu08l_hp2_operating_state': 1103,
    
    # Heating Circuit 1 Module
    'eu08l_hc1_error_number': 5000,
    'eu08l_hc1_operating_state': 5001,
    'eu08l_hc1_flow_temperature': 5002,
    'eu08l_hc1_return_temperature': 5003,
    'eu08l_hc1_room_temperature': 5004,
    'eu08l_hc1_offset_flow_line_temp': 5050,
    'eu08l_hc1_setpoint_room_heating_temp': 5051,
    'eu08l_hc1_setpoint_room_cooling_temp': 5052,
}

# Register to sensor name mapping (reverse)
REGISTER_TO_SENSOR_MAP = {v: k for k, v in SENSOR_TO_REGISTER_MAP.items()}

# =============================================================================
# DIAGNOSTIC THRESHOLDS
# =============================================================================

# Performance thresholds
SLOW_RESPONSE_THRESHOLD = 2000  # 2 seconds in milliseconds
VERY_SLOW_RESPONSE_THRESHOLD = 5000  # 5 seconds in milliseconds

# Error pattern detection
CONSECUTIVE_TIMEOUT_THRESHOLD = 3
HOURLY_ERROR_THRESHOLD = 10
DAILY_ERROR_THRESHOLD = 50

# Network health thresholds
PING_TIMEOUT = 3.0
PING_LOSS_THRESHOLD = 0.1  # 10% packet loss
HIGH_LATENCY_THRESHOLD = 100  # 100ms

# =============================================================================
# RECOMMENDATION ENGINE SETTINGS
# =============================================================================

# Individual read recommendations
INDIVIDUAL_READ_TIMEOUT_THRESHOLD = 3
INDIVIDUAL_READ_ERROR_THRESHOLD = 5
INDIVIDUAL_READ_SLOW_THRESHOLD = 3000  # 3 seconds

# Timeout adjustment recommendations
TIMEOUT_ADJUSTMENT_FACTOR = 1.5  # Multiply current timeout by this factor
MIN_RECOMMENDED_TIMEOUT = 1.0
MAX_RECOMMENDED_TIMEOUT = 10.0

# Priority adjustment recommendations
LOW_PRIORITY_ERROR_THRESHOLD = 10
LOW_PRIORITY_SLOW_THRESHOLD = 5000

# =============================================================================
# DATABASE SETTINGS
# =============================================================================

# SQLite database configuration
DB_DIR = "data"
DB_FILE = os.path.join(DB_DIR, "modbus_performance.db")

# Database tables
TABLES = {
    'performance_log': '''
        CREATE TABLE IF NOT EXISTS performance_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            host TEXT NOT NULL,
            port INTEGER NOT NULL,
            register INTEGER NOT NULL,
            success BOOLEAN NOT NULL,
            response_time REAL,
            error_type TEXT,
            error_message TEXT
        )
    ''',
    'error_patterns': '''
        CREATE TABLE IF NOT EXISTS error_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            register INTEGER NOT NULL,
            error_type TEXT NOT NULL,
            count INTEGER DEFAULT 1,
            time_window TEXT
        )
    ''',
    'recommendations': '''
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            register INTEGER NOT NULL,
            recommendation_type TEXT NOT NULL,
            current_value TEXT,
            recommended_value TEXT,
            reason TEXT,
            applied BOOLEAN DEFAULT FALSE
        )
    '''
}

# =============================================================================
# NETWORK DIAGNOSTICS SETTINGS
# =============================================================================

# Ping test configuration
PING_COUNT = 4
PING_INTERVAL = 1.0

# Port scan configuration
PORT_SCAN_TIMEOUT = 2.0
COMMON_MODBUS_PORTS = [502, 5020, 503, 1502]

# Network test targets
NETWORK_TEST_TARGETS = [
    "192.168.178.1",  # Gateway
    "8.8.8.8",        # DNS
    PRIMARY_HOST,     # Primary Modbus host
    SECONDARY_HOST,   # Secondary Modbus host
]

# =============================================================================
# REPORTING SETTINGS
# =============================================================================

# Report generation
REPORT_DIR = "reports"
DAILY_REPORT_ENABLED = True
WEEKLY_REPORT_ENABLED = True

# Report formats
SUPPORTED_FORMATS = ['txt', 'json', 'csv', 'html']

# Email notifications (optional)
EMAIL_NOTIFICATIONS = False
EMAIL_SMTP_SERVER = ""
EMAIL_SMTP_PORT = 587
EMAIL_USERNAME = ""
EMAIL_PASSWORD = ""
EMAIL_RECIPIENTS = []

# =============================================================================
# GUI SETTINGS
# =============================================================================

# GUI configuration
GUI_ENABLED = True
GUI_HOST = "localhost"
GUI_PORT = 8080
GUI_DEBUG = False

# Dashboard settings
DASHBOARD_REFRESH_INTERVAL = 5  # seconds
DASHBOARD_HISTORY_HOURS = 24

# =============================================================================
# EXPERT SETTINGS
# =============================================================================

# Advanced diagnostics
ENABLE_STRESS_TESTING = False
STRESS_TEST_DURATION = 300  # 5 minutes
STRESS_TEST_INTERVAL = 1.0  # 1 second

# Circuit breaker settings
CIRCUIT_BREAKER_ENABLED = True
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 60

# Anti-synchronization settings
ANTI_SYNC_ENABLED = True
ANTI_SYNC_FACTOR = 0.2  # 20% jitter variation

# =============================================================================
# CONST.PY GENERATION SETTINGS
# =============================================================================

# Output file paths
CONST_PY_OUTPUT = "recommended_const.py"
CONFIG_YAML_OUTPUT = "recommended_config.yaml"

# Backup settings
CREATE_BACKUP = True
BACKUP_DIR = "backups"

# =============================================================================
# VALIDATION SETTINGS
# =============================================================================

# Input validation
VALIDATE_IP_ADDRESSES = True
VALIDATE_PORTS = True
VALIDATE_REGISTERS = True

# Register validation ranges
MIN_REGISTER_ADDRESS = 0
MAX_REGISTER_ADDRESS = 65535
MIN_REGISTER_COUNT = 1
MAX_REGISTER_COUNT = 125

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_random_interval() -> float:
    """Calculate random interval within configured range."""
    import random
    base = BASE_MONITORING_INTERVAL
    variation = random.uniform(-RANDOM_INTERVAL_RANGE, RANDOM_INTERVAL_RANGE)
    interval = base + variation
    return max(MIN_INTERVAL, min(MAX_INTERVAL, interval))

def get_timeout_for_register(register: int) -> float:
    """Get appropriate timeout for specific register."""
    # Register-specific timeouts (can be extended)
    register_timeouts = {
        0: QUICK_TIMEOUT,      # error_state - quick timeout
        1000: DEFAULT_TIMEOUT, # test register - default timeout
        1050: QUICK_TIMEOUT,   # known problematic register
        1060: QUICK_TIMEOUT,   # known problematic register
    }
    
    return register_timeouts.get(register, DEFAULT_TIMEOUT)

def is_critical_register(register: int) -> bool:
    """Check if register is critical and should be prioritized."""
    critical_registers = [0, 1, 1000, 1001, 1002, 1003, 1004]
    return register in critical_registers

def get_register_priority(register: int) -> str:
    """Get priority level for register."""
    if is_critical_register(register):
        return "high"
    elif register in [1050, 1060]:  # Known problematic registers
        return "low"
    else:
        return "medium"

# =============================================================================
# CONFIGURATION VALIDATION
# =============================================================================

def validate_configuration() -> List[str]:
    """Validate configuration and return list of issues."""
    issues = []
    
    # Validate hosts
    if not PRIMARY_HOST or not SECONDARY_HOST:
        issues.append("Primary or secondary host not configured")
    
    # Validate ports
    if not (1 <= PRIMARY_PORT <= 65535) or not (1 <= SECONDARY_PORT <= 65535):
        issues.append("Invalid port numbers")
    
    # Validate intervals
    if MIN_INTERVAL >= MAX_INTERVAL:
        issues.append("MIN_INTERVAL must be less than MAX_INTERVAL")
    
    # Validate timeouts
    if QUICK_TIMEOUT >= DEFAULT_TIMEOUT or DEFAULT_TIMEOUT >= EXTENDED_TIMEOUT:
        issues.append("Timeout values must be in ascending order")
    
    # Validate thresholds
    if ERROR_RATE_THRESHOLD < 0 or ERROR_RATE_THRESHOLD > 1:
        issues.append("ERROR_RATE_THRESHOLD must be between 0 and 1")
    
    return issues

# =============================================================================
# ENVIRONMENT SETUP
# =============================================================================

def setup_directories():
    """Create necessary directories."""
    directories = [LOG_DIR, DB_DIR, REPORT_DIR, BACKUP_DIR]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def get_config_summary() -> Dict:
    """Get configuration summary for logging."""
    return {
        'primary_host': f"{PRIMARY_HOST}:{PRIMARY_PORT}",
        'secondary_host': f"{SECONDARY_HOST}:{SECONDARY_PORT}",
        'test_register': TEST_REGISTER,
        'monitoring_interval': f"{BASE_MONITORING_INTERVAL}s ± {RANDOM_INTERVAL_RANGE}s",
        'timeout_settings': {
            'default': DEFAULT_TIMEOUT,
            'quick': QUICK_TIMEOUT,
            'extended': EXTENDED_TIMEOUT
        },
        'retry_settings': {
            'max_retries': MAX_RETRIES,
            'retry_delay': RETRY_DELAY,
            'exponential_backoff': EXPONENTIAL_BACKOFF
        },
        'thresholds': {
            'timeout_threshold': TIMEOUT_THRESHOLD,
            'error_rate_threshold': ERROR_RATE_THRESHOLD,
            'failure_threshold': FAILURE_THRESHOLD
        }
    }

# Initialize directories on import
setup_directories()

# Validate configuration on import
config_issues = validate_configuration()
if config_issues:
    print("⚠️  Configuration issues detected:")
    for issue in config_issues:
        print(f"   - {issue}")
    print("Please fix these issues before running the diagnostics tool.")

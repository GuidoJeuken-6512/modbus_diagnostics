"""
HA Log Analyzer for Modbus Diagnostics
Analyzes Home Assistant logs to identify Modbus timeout patterns and problematic registers.
"""

import re
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass
import logging

from const import (
    HA_LOG_PATH, SENSOR_TO_REGISTER_MAP, REGISTER_TO_SENSOR_MAP,
    CONSECUTIVE_TIMEOUT_THRESHOLD, HOURLY_ERROR_THRESHOLD, DAILY_ERROR_THRESHOLD,
    SLOW_RESPONSE_THRESHOLD, VERY_SLOW_RESPONSE_THRESHOLD
)

logger = logging.getLogger(__name__)

@dataclass
class TimeoutEvent:
    """Represents a timeout event from HA logs."""
    timestamp: datetime
    sensor_name: str
    register: Optional[int]
    line_number: int
    raw_line: str

@dataclass
class ErrorPattern:
    """Represents an error pattern analysis result."""
    register: int
    sensor_name: str
    timeout_count: int
    consecutive_timeouts: int
    time_span: timedelta
    first_timeout: datetime
    last_timeout: datetime
    severity: str  # 'low', 'medium', 'high', 'critical'

@dataclass
class LogAnalysisResult:
    """Complete log analysis result."""
    total_timeouts: int
    problematic_registers: List[ErrorPattern]
    time_patterns: Dict[int, int]  # hour -> count
    recommendations: List[Dict]
    analysis_period: Tuple[datetime, datetime]
    log_file_size: int
    lines_analyzed: int

class HALogAnalyzer:
    """Analyzes Home Assistant logs for Modbus timeout patterns."""
    
    def __init__(self, log_path: str = HA_LOG_PATH):
        self.log_path = log_path
        self.timeout_pattern = re.compile(
            r"Update of sensor\.(\w+) is taking over 10 seconds"
        )
        self.timestamp_pattern = re.compile(
            r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
        )
        self.lambda_log_pattern = re.compile(
            r"custom_components\.lambda_heat_pumps"
        )
        
    def analyze_logs(self, hours_back: int = 24) -> LogAnalysisResult:
        """
        Analyze HA logs for Modbus timeout patterns.
        
        Args:
            hours_back: How many hours back to analyze
            
        Returns:
            LogAnalysisResult with analysis data
        """
        logger.info(f"🔍 Starting HA log analysis for last {hours_back} hours")
        
        if not os.path.exists(self.log_path):
            logger.error(f"❌ HA log file not found: {self.log_path}")
            return self._create_empty_result()
        
        # Get file info
        file_size = os.path.getsize(self.log_path)
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        # Parse log file
        timeout_events = self._parse_log_file(cutoff_time)
        
        if not timeout_events:
            logger.info("✅ No timeout events found in the specified period")
            return self._create_empty_result()
        
        logger.info(f"📊 Found {len(timeout_events)} timeout events")
        
        # Analyze patterns
        error_patterns = self._analyze_error_patterns(timeout_events)
        time_patterns = self._analyze_time_patterns(timeout_events)
        recommendations = self._generate_recommendations(error_patterns)
        
        # Create result
        result = LogAnalysisResult(
            total_timeouts=len(timeout_events),
            problematic_registers=error_patterns,
            time_patterns=time_patterns,
            recommendations=recommendations,
            analysis_period=(cutoff_time, datetime.now()),
            log_file_size=file_size,
            lines_analyzed=self._count_log_lines()
        )
        
        logger.info(f"✅ Log analysis completed: {len(error_patterns)} problematic registers found")
        return result
    
    def _parse_log_file(self, cutoff_time: datetime) -> List[TimeoutEvent]:
        """Parse log file and extract timeout events."""
        timeout_events = []
        
        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    # Check if line contains timeout warning
                    match = self.timeout_pattern.search(line)
                    if not match:
                        continue
                    
                    # Extract timestamp
                    timestamp_match = self.timestamp_pattern.search(line)
                    if not timestamp_match:
                        continue
                    
                    try:
                        timestamp = datetime.strptime(timestamp_match.group(1), "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        continue
                    
                    # Skip if before cutoff time
                    if timestamp < cutoff_time:
                        continue
                    
                    # Extract sensor name and register
                    sensor_name = match.group(1)
                    register = SENSOR_TO_REGISTER_MAP.get(sensor_name)
                    
                    # Create timeout event
                    event = TimeoutEvent(
                        timestamp=timestamp,
                        sensor_name=sensor_name,
                        register=register,
                        line_number=line_num,
                        raw_line=line.strip()
                    )
                    
                    timeout_events.append(event)
                    
        except Exception as e:
            logger.error(f"❌ Error parsing log file: {e}")
            return []
        
        return timeout_events
    
    def _analyze_error_patterns(self, timeout_events: List[TimeoutEvent]) -> List[ErrorPattern]:
        """Analyze error patterns from timeout events."""
        patterns = []
        
        # Group by register
        register_events = defaultdict(list)
        for event in timeout_events:
            if event.register is not None:
                register_events[event.register].append(event)
        
        # Analyze each register
        for register, events in register_events.items():
            if not events:
                continue
            
            # Sort by timestamp
            events.sort(key=lambda x: x.timestamp)
            
            # Calculate metrics
            timeout_count = len(events)
            consecutive_timeouts = self._calculate_consecutive_timeouts(events)
            time_span = events[-1].timestamp - events[0].timestamp
            severity = self._calculate_severity(timeout_count, consecutive_timeouts, time_span)
            
            # Get sensor name
            sensor_name = REGISTER_TO_SENSOR_MAP.get(register, f"register_{register}")
            
            pattern = ErrorPattern(
                register=register,
                sensor_name=sensor_name,
                timeout_count=timeout_count,
                consecutive_timeouts=consecutive_timeouts,
                time_span=time_span,
                first_timeout=events[0].timestamp,
                last_timeout=events[-1].timestamp,
                severity=severity
            )
            
            patterns.append(pattern)
        
        # Sort by severity and timeout count
        patterns.sort(key=lambda x: (x.severity, x.timeout_count), reverse=True)
        
        return patterns
    
    def _calculate_consecutive_timeouts(self, events: List[TimeoutEvent]) -> int:
        """Calculate maximum consecutive timeouts."""
        if not events:
            return 0
        
        max_consecutive = 1
        current_consecutive = 1
        
        for i in range(1, len(events)):
            time_diff = events[i].timestamp - events[i-1].timestamp
            
            # If timeouts are within 5 minutes, consider them consecutive
            if time_diff <= timedelta(minutes=5):
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 1
        
        return max_consecutive
    
    def _calculate_severity(self, timeout_count: int, consecutive_timeouts: int, time_span: timedelta) -> str:
        """Calculate severity level based on timeout patterns."""
        # Critical: Many timeouts in short time
        if timeout_count >= DAILY_ERROR_THRESHOLD and time_span <= timedelta(hours=1):
            return "critical"
        
        # High: Many consecutive timeouts or high hourly rate
        if (consecutive_timeouts >= CONSECUTIVE_TIMEOUT_THRESHOLD or 
            timeout_count >= HOURLY_ERROR_THRESHOLD):
            return "high"
        
        # Medium: Moderate timeout count
        if timeout_count >= 5:
            return "medium"
        
        # Low: Few timeouts
        return "low"
    
    def _analyze_time_patterns(self, timeout_events: List[TimeoutEvent]) -> Dict[int, int]:
        """Analyze time-based patterns of timeouts."""
        hourly_counts = defaultdict(int)
        
        for event in timeout_events:
            hour = event.timestamp.hour
            hourly_counts[hour] += 1
        
        return dict(hourly_counts)
    
    def _generate_recommendations(self, error_patterns: List[ErrorPattern]) -> List[Dict]:
        """Generate recommendations based on error patterns."""
        recommendations = []
        
        for pattern in error_patterns:
            if pattern.severity in ['high', 'critical']:
                # Individual read recommendation
                recommendations.append({
                    'type': 'individual_read',
                    'register': pattern.register,
                    'sensor_name': pattern.sensor_name,
                    'reason': f"{pattern.timeout_count} timeouts, {pattern.consecutive_timeouts} consecutive",
                    'priority': pattern.severity,
                    'current_timeout': 2,  # Default from your config
                    'recommended_timeout': 5 if pattern.severity == 'critical' else 3
                })
                
                # Timeout adjustment recommendation
                recommendations.append({
                    'type': 'timeout_adjustment',
                    'register': pattern.register,
                    'sensor_name': pattern.sensor_name,
                    'reason': f"Frequent timeouts with current 2s timeout",
                    'priority': pattern.severity,
                    'current_timeout': 2,
                    'recommended_timeout': 5 if pattern.severity == 'critical' else 3
                })
                
                # Low priority recommendation for non-critical registers
                if pattern.register not in [0, 1, 1000, 1001, 1002, 1003, 1004]:
                    recommendations.append({
                        'type': 'low_priority',
                        'register': pattern.register,
                        'sensor_name': pattern.sensor_name,
                        'reason': f"Non-critical register with {pattern.timeout_count} timeouts",
                        'priority': 'medium'
                    })
        
        return recommendations
    
    def _count_log_lines(self) -> int:
        """Count total lines in log file."""
        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                return sum(1 for _ in f)
        except Exception:
            return 0
    
    def _create_empty_result(self) -> LogAnalysisResult:
        """Create empty result when no data is found."""
        return LogAnalysisResult(
            total_timeouts=0,
            problematic_registers=[],
            time_patterns={},
            recommendations=[],
            analysis_period=(datetime.now(), datetime.now()),
            log_file_size=0,
            lines_analyzed=0
        )
    
    def find_specific_register_issues(self, register: int, hours_back: int = 24) -> List[TimeoutEvent]:
        """Find timeout issues for a specific register."""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        timeout_events = self._parse_log_file(cutoff_time)
        
        # Filter for specific register
        register_events = [
            event for event in timeout_events 
            if event.register == register
        ]
        
        return register_events
    
    def get_register_performance_summary(self, register: int, hours_back: int = 24) -> Dict:
        """Get performance summary for a specific register."""
        events = self.find_specific_register_issues(register, hours_back)
        
        if not events:
            return {
                'register': register,
                'timeout_count': 0,
                'status': 'good',
                'recommendations': []
            }
        
        # Calculate metrics
        timeout_count = len(events)
        consecutive_timeouts = self._calculate_consecutive_timeouts(events)
        time_span = events[-1].timestamp - events[0].timestamp if len(events) > 1 else timedelta(0)
        
        # Determine status
        if timeout_count >= DAILY_ERROR_THRESHOLD:
            status = 'critical'
        elif timeout_count >= HOURLY_ERROR_THRESHOLD:
            status = 'poor'
        elif timeout_count >= 5:
            status = 'fair'
        else:
            status = 'good'
        
        # Generate recommendations
        recommendations = []
        if timeout_count >= 3:
            recommendations.append("Consider adding to individual reads")
        if timeout_count >= 5:
            recommendations.append("Increase timeout to 5 seconds")
        if consecutive_timeouts >= 3:
            recommendations.append("Check for network or device issues")
        
        return {
            'register': register,
            'timeout_count': timeout_count,
            'consecutive_timeouts': consecutive_timeouts,
            'time_span_hours': time_span.total_seconds() / 3600,
            'status': status,
            'recommendations': recommendations,
            'first_timeout': events[0].timestamp if events else None,
            'last_timeout': events[-1].timestamp if events else None
        }
    
    def export_analysis_to_file(self, result: LogAnalysisResult, output_file: str):
        """Export analysis result to file."""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=== MODBUS TIMEOUT ANALYSIS REPORT ===\n\n")
                f.write(f"Analysis Period: {result.analysis_period[0]} to {result.analysis_period[1]}\n")
                f.write(f"Total Timeouts: {result.total_timeouts}\n")
                f.write(f"Log File Size: {result.log_file_size:,} bytes\n")
                f.write(f"Lines Analyzed: {result.lines_analyzed:,}\n\n")
                
                f.write("=== PROBLEMATIC REGISTERS ===\n")
                for pattern in result.problematic_registers:
                    f.write(f"\nRegister {pattern.register} ({pattern.sensor_name}):\n")
                    f.write(f"  Timeouts: {pattern.timeout_count}\n")
                    f.write(f"  Consecutive: {pattern.consecutive_timeouts}\n")
                    f.write(f"  Time Span: {pattern.time_span}\n")
                    f.write(f"  Severity: {pattern.severity}\n")
                    f.write(f"  First: {pattern.first_timeout}\n")
                    f.write(f"  Last: {pattern.last_timeout}\n")
                
                f.write("\n=== RECOMMENDATIONS ===\n")
                for rec in result.recommendations:
                    f.write(f"\n{rec['type'].upper()}: Register {rec['register']}\n")
                    f.write(f"  Reason: {rec['reason']}\n")
                    f.write(f"  Priority: {rec['priority']}\n")
                    if 'recommended_timeout' in rec:
                        f.write(f"  Recommended Timeout: {rec['recommended_timeout']}s\n")
                
                f.write("\n=== TIME PATTERNS ===\n")
                for hour, count in sorted(result.time_patterns.items()):
                    f.write(f"Hour {hour:02d}:00 - {count} timeouts\n")
            
            logger.info(f"✅ Analysis exported to {output_file}")
            
        except Exception as e:
            logger.error(f"❌ Error exporting analysis: {e}")

def main():
    """Main function for testing the log analyzer."""
    logging.basicConfig(level=logging.INFO)
    
    analyzer = HALogAnalyzer()
    result = analyzer.analyze_logs(hours_back=24)
    
    print(f"📊 Analysis Results:")
    print(f"   Total Timeouts: {result.total_timeouts}")
    print(f"   Problematic Registers: {len(result.problematic_registers)}")
    print(f"   Recommendations: {len(result.recommendations)}")
    
    if result.problematic_registers:
        print("\n🔍 Top Problematic Registers:")
        for pattern in result.problematic_registers[:5]:
            print(f"   Register {pattern.register} ({pattern.sensor_name}): "
                  f"{pattern.timeout_count} timeouts, severity: {pattern.severity}")
    
    if result.recommendations:
        print("\n💡 Recommendations:")
        for rec in result.recommendations[:5]:
            print(f"   {rec['type']}: Register {rec['register']} - {rec['reason']}")

if __name__ == "__main__":
    main()

"""
Recommendation Engine for Modbus Configuration Optimization
Analyzes performance data and generates recommendations for const.py updates.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import logging

from const import (
    INDIVIDUAL_READ_TIMEOUT_THRESHOLD, INDIVIDUAL_READ_ERROR_THRESHOLD,
    INDIVIDUAL_READ_SLOW_THRESHOLD, TIMEOUT_ADJUSTMENT_FACTOR,
    MIN_RECOMMENDED_TIMEOUT, MAX_RECOMMENDED_TIMEOUT,
    LOW_PRIORITY_ERROR_THRESHOLD, LOW_PRIORITY_SLOW_THRESHOLD,
    CONST_PY_OUTPUT, CONFIG_YAML_OUTPUT, CREATE_BACKUP, BACKUP_DIR
)

logger = logging.getLogger(__name__)

@dataclass
class RegisterPerformance:
    """Performance data for a specific register."""
    register: int
    sensor_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeout_requests: int = 0
    avg_response_time: float = 0.0
    max_response_time: float = 0.0
    min_response_time: float = 0.0
    consecutive_failures: int = 0
    max_consecutive_failures: int = 0
    error_rate: float = 0.0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    is_critical: bool = False
    current_timeout: float = 3.0
    current_individual_read: bool = False
    current_low_priority: bool = False

@dataclass
class Recommendation:
    """A configuration recommendation."""
    type: str  # 'individual_read', 'timeout_adjustment', 'low_priority', 'circuit_breaker'
    register: int
    sensor_name: str
    current_value: str
    recommended_value: str
    reason: str
    priority: str  # 'low', 'medium', 'high', 'critical'
    confidence: float  # 0.0 to 1.0
    impact: str  # 'low', 'medium', 'high'
    evidence: List[str] = field(default_factory=list)

@dataclass
class ConfigurationUpdate:
    """Complete configuration update recommendation."""
    timestamp: datetime
    individual_read_registers: List[int]
    register_timeouts: Dict[int, float]
    low_priority_registers: List[int]
    circuit_breaker_settings: Dict[str, any]
    update_intervals: Dict[str, float]
    recommendations: List[Recommendation]
    summary: str
    risk_assessment: str

class RecommendationEngine:
    """Generates configuration recommendations based on performance analysis."""
    
    def __init__(self):
        self.performance_data = {}
        self.recommendations = []
        
        # Critical registers that should not be made low priority
        self.critical_registers = {0, 1, 1000, 1001, 1002, 1003, 1004}
        
        # Current configuration (would be loaded from actual const.py)
        self.current_config = {
            'individual_read_registers': [0, 1050, 1060],
            'register_timeouts': {0: 2, 1050: 2, 1060: 2},
            'low_priority_registers': [0, 1050, 1060],
            'circuit_breaker_enabled': True,
            'base_timeout': 3.0
        }
        
        logger.info("🔧 RecommendationEngine initialized")
    
    def analyze_performance_data(self, log_analysis_result, modbus_monitor_stats, network_diagnostics_result) -> ConfigurationUpdate:
        """Analyze all performance data and generate recommendations."""
        logger.info("🔍 Analyzing performance data for recommendations")
        
        # Extract register performance from different sources
        self._extract_register_performance(log_analysis_result, modbus_monitor_stats, network_diagnostics_result)
        
        # Generate recommendations
        recommendations = self._generate_recommendations()
        
        # Create configuration update
        config_update = self._create_configuration_update(recommendations)
        
        logger.info(f"✅ Generated {len(recommendations)} recommendations")
        return config_update
    
    def _extract_register_performance(self, log_analysis, modbus_stats, network_diagnostics):
        """Extract register performance data from analysis results."""
        
        # From log analysis
        for pattern in log_analysis.problematic_registers:
            register = pattern.register
            if register not in self.performance_data:
                self.performance_data[register] = RegisterPerformance(
                    register=register,
                    sensor_name=pattern.sensor_name,
                    is_critical=register in self.critical_registers
                )
            
            perf = self.performance_data[register]
            perf.failed_requests += pattern.timeout_count
            perf.timeout_requests += pattern.timeout_count
            perf.max_consecutive_failures = max(perf.max_consecutive_failures, pattern.consecutive_timeouts)
            perf.last_failure = pattern.last_timeout
            
            # Estimate total requests (assuming 1 request per minute for 24 hours = 1440)
            perf.total_requests = max(perf.total_requests, pattern.timeout_count * 10)
            perf.successful_requests = perf.total_requests - perf.failed_requests
            perf.error_rate = perf.failed_requests / max(1, perf.total_requests)
        
        # From Modbus monitor stats (if available)
        if hasattr(modbus_stats, 'register_performance'):
            for register, stats in modbus_stats.register_performance.items():
                if register not in self.performance_data:
                    self.performance_data[register] = RegisterPerformance(
                        register=register,
                        sensor_name=f"register_{register}",
                        is_critical=register in self.critical_registers
                    )
                
                perf = self.performance_data[register]
                perf.total_requests += stats.get('total_requests', 0)
                perf.successful_requests += stats.get('successful_requests', 0)
                perf.failed_requests += stats.get('failed_requests', 0)
                perf.avg_response_time = stats.get('avg_response_time', 0.0)
                perf.max_response_time = max(perf.max_response_time, stats.get('max_response_time', 0.0))
                perf.min_response_time = min(perf.min_response_time, stats.get('min_response_time', float('inf')))
        
        # From network diagnostics
        for result in network_diagnostics.modbus_connectivity_results:
            register = result.register
            if register not in self.performance_data:
                self.performance_data[register] = RegisterPerformance(
                    register=register,
                    sensor_name=f"register_{register}",
                    is_critical=register in self.critical_registers
                )
            
            perf = self.performance_data[register]
            perf.total_requests += 1
            if result.success:
                perf.successful_requests += 1
                perf.last_success = datetime.now()
                if result.response_time:
                    perf.avg_response_time = (perf.avg_response_time + result.response_time) / 2
                    perf.max_response_time = max(perf.max_response_time, result.response_time)
            else:
                perf.failed_requests += 1
                perf.last_failure = datetime.now()
        
        # Update current configuration status
        for register, perf in self.performance_data.items():
            perf.current_individual_read = register in self.current_config['individual_read_registers']
            perf.current_timeout = self.current_config['register_timeouts'].get(register, self.current_config['base_timeout'])
            perf.current_low_priority = register in self.current_config['low_priority_registers']
    
    def _generate_recommendations(self) -> List[Recommendation]:
        """Generate recommendations based on performance data."""
        recommendations = []
        
        for register, perf in self.performance_data.items():
            # Individual read recommendations
            if self._should_recommend_individual_read(perf):
                recommendations.append(self._create_individual_read_recommendation(perf))
            
            # Timeout adjustment recommendations
            if self._should_recommend_timeout_adjustment(perf):
                recommendations.append(self._create_timeout_adjustment_recommendation(perf))
            
            # Low priority recommendations
            if self._should_recommend_low_priority(perf):
                recommendations.append(self._create_low_priority_recommendation(perf))
        
        # Sort by priority and confidence
        recommendations.sort(key=lambda x: (x.priority, x.confidence), reverse=True)
        
        return recommendations
    
    def _should_recommend_individual_read(self, perf: RegisterPerformance) -> bool:
        """Determine if register should be added to individual reads."""
        # Already in individual reads
        if perf.current_individual_read:
            return False
        
        # High error rate
        if perf.error_rate > INDIVIDUAL_READ_ERROR_THRESHOLD / 100:
            return True
        
        # Many consecutive failures
        if perf.max_consecutive_failures >= INDIVIDUAL_READ_TIMEOUT_THRESHOLD:
            return True
        
        # Slow response times
        if perf.avg_response_time > INDIVIDUAL_READ_SLOW_THRESHOLD:
            return True
        
        return False
    
    def _should_recommend_timeout_adjustment(self, perf: RegisterPerformance) -> bool:
        """Determine if register timeout should be adjusted."""
        # High error rate with current timeout
        if perf.error_rate > 0.1 and perf.current_timeout < 5.0:
            return True
        
        # Many timeouts
        if perf.timeout_requests > 5:
            return True
        
        # Slow response times
        if perf.avg_response_time > 2000 and perf.current_timeout < 5.0:
            return True
        
        return False
    
    def _should_recommend_low_priority(self, perf: RegisterPerformance) -> bool:
        """Determine if register should be made low priority."""
        # Don't make critical registers low priority
        if perf.is_critical:
            return False
        
        # Already low priority
        if perf.current_low_priority:
            return False
        
        # High error rate but not critical
        if perf.error_rate > LOW_PRIORITY_ERROR_THRESHOLD / 100:
            return True
        
        # Slow response times
        if perf.avg_response_time > LOW_PRIORITY_SLOW_THRESHOLD:
            return True
        
        return False
    
    def _create_individual_read_recommendation(self, perf: RegisterPerformance) -> Recommendation:
        """Create individual read recommendation."""
        evidence = []
        confidence = 0.5
        
        if perf.error_rate > 0.1:
            evidence.append(f"High error rate: {perf.error_rate:.1%}")
            confidence += 0.2
        
        if perf.max_consecutive_failures >= 3:
            evidence.append(f"Consecutive failures: {perf.max_consecutive_failures}")
            confidence += 0.2
        
        if perf.avg_response_time > 2000:
            evidence.append(f"Slow response: {perf.avg_response_time:.0f}ms")
            confidence += 0.1
        
        priority = "high" if perf.is_critical else "medium"
        if perf.error_rate > 0.2:
            priority = "critical"
        
        return Recommendation(
            type="individual_read",
            register=perf.register,
            sensor_name=perf.sensor_name,
            current_value="False",
            recommended_value="True",
            reason=f"Register {perf.register} has performance issues",
            priority=priority,
            confidence=min(1.0, confidence),
            impact="medium",
            evidence=evidence
        )
    
    def _create_timeout_adjustment_recommendation(self, perf: RegisterPerformance) -> Recommendation:
        """Create timeout adjustment recommendation."""
        evidence = []
        confidence = 0.6
        
        # Calculate recommended timeout
        if perf.error_rate > 0.2:
            recommended_timeout = min(MAX_RECOMMENDED_TIMEOUT, perf.current_timeout * 2.5)
        elif perf.error_rate > 0.1:
            recommended_timeout = min(MAX_RECOMMENDED_TIMEOUT, perf.current_timeout * 2.0)
        else:
            recommended_timeout = min(MAX_RECOMMENDED_TIMEOUT, perf.current_timeout * TIMEOUT_ADJUSTMENT_FACTOR)
        
        recommended_timeout = max(MIN_RECOMMENDED_TIMEOUT, recommended_timeout)
        
        if perf.error_rate > 0.1:
            evidence.append(f"Error rate: {perf.error_rate:.1%}")
            confidence += 0.2
        
        if perf.timeout_requests > 5:
            evidence.append(f"Timeout count: {perf.timeout_requests}")
            confidence += 0.1
        
        if perf.avg_response_time > 2000:
            evidence.append(f"Avg response: {perf.avg_response_time:.0f}ms")
            confidence += 0.1
        
        priority = "high" if perf.is_critical else "medium"
        if perf.error_rate > 0.3:
            priority = "critical"
        
        return Recommendation(
            type="timeout_adjustment",
            register=perf.register,
            sensor_name=perf.sensor_name,
            current_value=f"{perf.current_timeout}s",
            recommended_value=f"{recommended_timeout}s",
            reason=f"Register {perf.register} needs longer timeout",
            priority=priority,
            confidence=min(1.0, confidence),
            impact="low",
            evidence=evidence
        )
    
    def _create_low_priority_recommendation(self, perf: RegisterPerformance) -> Recommendation:
        """Create low priority recommendation."""
        evidence = []
        confidence = 0.7
        
        if perf.error_rate > 0.1:
            evidence.append(f"Error rate: {perf.error_rate:.1%}")
            confidence += 0.1
        
        if perf.avg_response_time > 3000:
            evidence.append(f"Slow response: {perf.avg_response_time:.0f}ms")
            confidence += 0.1
        
        return Recommendation(
            type="low_priority",
            register=perf.register,
            sensor_name=perf.sensor_name,
            current_value="False",
            recommended_value="True",
            reason=f"Register {perf.register} is non-critical with performance issues",
            priority="low",
            confidence=min(1.0, confidence),
            impact="low",
            evidence=evidence
        )
    
    def _create_configuration_update(self, recommendations: List[Recommendation]) -> ConfigurationUpdate:
        """Create complete configuration update from recommendations."""
        
        # Extract recommendations by type
        individual_read_registers = list(self.current_config['individual_read_registers'])
        register_timeouts = dict(self.current_config['register_timeouts'])
        low_priority_registers = list(self.current_config['low_priority_registers'])
        
        for rec in recommendations:
            if rec.type == "individual_read" and rec.register not in individual_read_registers:
                individual_read_registers.append(rec.register)
            elif rec.type == "timeout_adjustment":
                new_timeout = float(rec.recommended_value.replace('s', ''))
                register_timeouts[rec.register] = new_timeout
            elif rec.type == "low_priority" and rec.register not in low_priority_registers:
                low_priority_registers.append(rec.register)
        
        # Sort lists
        individual_read_registers.sort()
        low_priority_registers.sort()
        
        # Generate summary
        summary = self._generate_summary(recommendations, individual_read_registers, register_timeouts, low_priority_registers)
        
        # Risk assessment
        risk_assessment = self._assess_risk(recommendations)
        
        return ConfigurationUpdate(
            timestamp=datetime.now(),
            individual_read_registers=individual_read_registers,
            register_timeouts=register_timeouts,
            low_priority_registers=low_priority_registers,
            circuit_breaker_settings=self.current_config,
            update_intervals={},
            recommendations=recommendations,
            summary=summary,
            risk_assessment=risk_assessment
        )
    
    def _generate_summary(self, recommendations: List[Recommendation], 
                         individual_reads: List[int], timeouts: Dict[int, float], 
                         low_priority: List[int]) -> str:
        """Generate summary of configuration changes."""
        changes = []
        
        new_individual_reads = [r for r in individual_reads if r not in self.current_config['individual_read_registers']]
        if new_individual_reads:
            changes.append(f"Add {len(new_individual_reads)} registers to individual reads: {new_individual_reads}")
        
        new_timeouts = {k: v for k, v in timeouts.items() 
                       if k not in self.current_config['register_timeouts'] or 
                       self.current_config['register_timeouts'][k] != v}
        if new_timeouts:
            changes.append(f"Adjust timeouts for {len(new_timeouts)} registers")
        
        new_low_priority = [r for r in low_priority if r not in self.current_config['low_priority_registers']]
        if new_low_priority:
            changes.append(f"Add {len(new_low_priority)} registers to low priority: {new_low_priority}")
        
        if not changes:
            return "No configuration changes recommended"
        
        return f"Configuration changes: {'; '.join(changes)}"
    
    def _assess_risk(self, recommendations: List[Recommendation]) -> str:
        """Assess risk level of configuration changes."""
        critical_count = sum(1 for r in recommendations if r.priority == "critical")
        high_count = sum(1 for r in recommendations if r.priority == "high")
        
        if critical_count > 0:
            return f"HIGH RISK: {critical_count} critical recommendations"
        elif high_count > 3:
            return f"MEDIUM RISK: {high_count} high-priority recommendations"
        elif high_count > 0:
            return f"LOW RISK: {high_count} high-priority recommendations"
        else:
            return "MINIMAL RISK: Only low-priority recommendations"
    
    def generate_const_py_file(self, config_update: ConfigurationUpdate, output_file: str = CONST_PY_OUTPUT):
        """Generate updated const.py file."""
        try:
            # Create backup if requested
            if CREATE_BACKUP and os.path.exists(output_file):
                backup_file = os.path.join(BACKUP_DIR, f"const_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py")
                os.makedirs(BACKUP_DIR, exist_ok=True)
                with open(output_file, 'r') as src, open(backup_file, 'w') as dst:
                    dst.write(src.read())
                logger.info(f"✅ Backup created: {backup_file}")
            
            # Generate new const.py
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("# Lambda Heat Pumps - Updated Configuration\n")
                f.write("# Generated by Modbus Diagnostics Tool\n")
                f.write(f"# Generated: {config_update.timestamp}\n\n")
                
                f.write("# Individual Read Registers\n")
                f.write("LAMBDA_INDIVIDUAL_READ_REGISTERS = [\n")
                for register in config_update.individual_read_registers:
                    f.write(f"    {register},\n")
                f.write("]\n\n")
                
                f.write("# Register-specific Timeouts\n")
                f.write("LAMBDA_REGISTER_TIMEOUTS = {\n")
                for register, timeout in sorted(config_update.register_timeouts.items()):
                    f.write(f"    {register}: {timeout},  # {self.performance_data.get(register, {}).get('sensor_name', f'register_{register}')}\n")
                f.write("}\n\n")
                
                f.write("# Low Priority Registers\n")
                f.write("LAMBDA_LOW_PRIORITY_REGISTERS = [\n")
                for register in config_update.low_priority_registers:
                    f.write(f"    {register},\n")
                f.write("]\n\n")
                
                f.write("# Recommendations Summary\n")
                f.write("# " + config_update.summary.replace('\n', '\n# ') + "\n")
                f.write("# Risk Assessment: " + config_update.risk_assessment + "\n\n")
                
                f.write("# Generated Recommendations:\n")
                for rec in config_update.recommendations:
                    f.write(f"# {rec.type.upper()}: Register {rec.register} - {rec.reason} (Priority: {rec.priority})\n")
            
            logger.info(f"✅ Generated const.py: {output_file}")
            
        except Exception as e:
            logger.error(f"❌ Failed to generate const.py: {e}")
    
    def export_recommendations_to_json(self, config_update: ConfigurationUpdate, output_file: str):
        """Export recommendations to JSON file."""
        try:
            data = {
                'timestamp': config_update.timestamp.isoformat(),
                'summary': config_update.summary,
                'risk_assessment': config_update.risk_assessment,
                'configuration': {
                    'individual_read_registers': config_update.individual_read_registers,
                    'register_timeouts': config_update.register_timeouts,
                    'low_priority_registers': config_update.low_priority_registers
                },
                'recommendations': [
                    {
                        'type': rec.type,
                        'register': rec.register,
                        'sensor_name': rec.sensor_name,
                        'current_value': rec.current_value,
                        'recommended_value': rec.recommended_value,
                        'reason': rec.reason,
                        'priority': rec.priority,
                        'confidence': rec.confidence,
                        'impact': rec.impact,
                        'evidence': rec.evidence
                    }
                    for rec in config_update.recommendations
                ]
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Recommendations exported to JSON: {output_file}")
            
        except Exception as e:
            logger.error(f"❌ Failed to export recommendations: {e}")

def main():
    """Main function for testing the recommendation engine."""
    logging.basicConfig(level=logging.INFO)
    
    # Create mock data for testing
    from log_analyzer import LogAnalysisResult, ErrorPattern
    from network_diagnostics import NetworkDiagnosticsResult, ModbusConnectivityResult
    
    # Mock log analysis result
    mock_log_analysis = LogAnalysisResult(
        total_timeouts=5,
        problematic_registers=[
            ErrorPattern(
                register=0,
                sensor_name="eu08l_hp1_error_state",
                timeout_count=5,
                consecutive_timeouts=3,
                time_span=timedelta(hours=2),
                first_timeout=datetime.now() - timedelta(hours=2),
                last_timeout=datetime.now(),
                severity="high"
            )
        ],
        time_patterns={},
        recommendations=[],
        analysis_period=(datetime.now() - timedelta(hours=24), datetime.now()),
        log_file_size=1000000,
        lines_analyzed=50000
    )
    
    # Mock network diagnostics result
    mock_network_diagnostics = NetworkDiagnosticsResult(
        timestamp=datetime.now(),
        ping_results=[],
        port_scan_results=[],
        modbus_connectivity_results=[
            ModbusConnectivityResult(
                host="192.168.178.125",
                port=502,
                register=0,
                success=False,
                error_message="Timeout"
            )
        ],
        network_health_score=60.0,
        issues_found=["Register 0 timeout"],
        recommendations=["Increase timeout for register 0"]
    )
    
    # Create recommendation engine
    engine = RecommendationEngine()
    
    # Generate recommendations
    config_update = engine.analyze_performance_data(
        mock_log_analysis, 
        {}, 
        mock_network_diagnostics
    )
    
    print("📊 Configuration Update Recommendations:")
    print(f"   Summary: {config_update.summary}")
    print(f"   Risk: {config_update.risk_assessment}")
    print(f"   Recommendations: {len(config_update.recommendations)}")
    
    for rec in config_update.recommendations:
        print(f"\n💡 {rec.type.upper()}: Register {rec.register}")
        print(f"   Reason: {rec.reason}")
        print(f"   Priority: {rec.priority}")
        print(f"   Confidence: {rec.confidence:.1%}")
        print(f"   Evidence: {', '.join(rec.evidence)}")
    
    # Generate const.py file
    engine.generate_const_py_file(config_update)

if __name__ == "__main__":
    main()

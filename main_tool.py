"""
Main Modbus Diagnostics Tool
Combines all diagnostic components into a unified CLI and GUI interface.
"""

import argparse
import sys
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import os

# Import our diagnostic modules
from const import (
    HA_LOG_PATH, PRIMARY_HOST, PRIMARY_PORT, SECONDARY_HOST, SECONDARY_PORT,
    TEST_REGISTER, BASE_MONITORING_INTERVAL, LOG_LEVEL, DEBUG_MODE,
    get_config_summary
)
from log_analyzer import HALogAnalyzer, LogAnalysisResult
from modbus_monitor import ModbusMonitor, MonitorConfig
from network_diagnostics import NetworkDiagnostics, NetworkDiagnosticsResult
from recommendation_engine import RecommendationEngine, ConfigurationUpdate

# GUI imports (optional)
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

logger = logging.getLogger(__name__)

class ModbusDiagnosticsTool:
    """Main diagnostics tool combining all components."""
    
    def __init__(self):
        self.log_analyzer = HALogAnalyzer()
        self.network_diagnostics = NetworkDiagnostics()
        self.recommendation_engine = RecommendationEngine()
        self.modbus_monitor = None
        self.monitoring_active = False
        
        # Results storage
        self.last_log_analysis = None
        self.last_network_diagnostics = None
        self.last_recommendations = None
        
        logger.info("🔧 ModbusDiagnosticsTool initialized")
    
    def run_log_analysis(self, hours_back: int = 24) -> LogAnalysisResult:
        """Run HA log analysis."""
        logger.info(f"🔍 Running log analysis for last {hours_back} hours")
        
        try:
            result = self.log_analyzer.analyze_logs(hours_back)
            self.last_log_analysis = result
            
            logger.info(f"✅ Log analysis completed: {result.total_timeouts} timeouts found")
            return result
            
        except Exception as e:
            logger.error(f"❌ Log analysis failed: {e}")
            raise
    
    def run_network_diagnostics(self) -> NetworkDiagnosticsResult:
        """Run comprehensive network diagnostics."""
        logger.info("🌐 Running network diagnostics")
        
        try:
            result = self.network_diagnostics.run_comprehensive_diagnostics()
            self.last_network_diagnostics = result
            
            logger.info(f"✅ Network diagnostics completed: Health score {result.network_health_score:.1f}/100")
            return result
            
        except Exception as e:
            logger.error(f"❌ Network diagnostics failed: {e}")
            raise
    
    def run_quick_network_check(self) -> Dict:
        """Run quick network check."""
        logger.info("⚡ Running quick network check")
        
        try:
            result = self.network_diagnostics.quick_network_check()
            logger.info(f"✅ Quick check completed: {result['overall_status']}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Quick network check failed: {e}")
            raise
    
    def generate_recommendations(self) -> ConfigurationUpdate:
        """Generate configuration recommendations."""
        logger.info("💡 Generating recommendations")
        
        if not self.last_log_analysis or not self.last_network_diagnostics:
            logger.warning("⚠️  Running missing analyses first")
            if not self.last_log_analysis:
                self.run_log_analysis()
            if not self.last_network_diagnostics:
                self.run_network_diagnostics()
        
        try:
            # Mock modbus monitor stats (would be real in production)
            mock_modbus_stats = {}
            
            result = self.recommendation_engine.analyze_performance_data(
                self.last_log_analysis,
                mock_modbus_stats,
                self.last_network_diagnostics
            )
            
            self.last_recommendations = result
            logger.info(f"✅ Generated {len(result.recommendations)} recommendations")
            return result
            
        except Exception as e:
            logger.error(f"❌ Recommendation generation failed: {e}")
            raise
    
    def start_monitoring(self, duration_minutes: int = 60):
        """Start continuous Modbus monitoring."""
        logger.info(f"🚀 Starting monitoring for {duration_minutes} minutes")
        
        try:
            config = MonitorConfig()
            self.modbus_monitor = ModbusMonitor(config)
            
            # Add callbacks
            def on_fallback(data):
                logger.warning(f"🔄 Fallback: {data['from']} -> {data['to']} ({data['reason']})")
            
            def on_circuit_breaker(data):
                logger.error(f"🔴 Circuit breaker opened for {data['host']} after {data['failures']} failures")
            
            self.modbus_monitor.add_callback('on_fallback', on_fallback)
            self.modbus_monitor.add_callback('on_circuit_breaker', on_circuit_breaker)
            
            self.modbus_monitor.start_monitoring()
            self.monitoring_active = True
            
            # Run for specified duration
            time.sleep(duration_minutes * 60)
            
            self.stop_monitoring()
            
        except KeyboardInterrupt:
            logger.info("🛑 Monitoring interrupted by user")
            self.stop_monitoring()
        except Exception as e:
            logger.error(f"❌ Monitoring failed: {e}")
            self.stop_monitoring()
            raise
    
    def stop_monitoring(self):
        """Stop continuous monitoring."""
        if self.modbus_monitor and self.monitoring_active:
            logger.info("🛑 Stopping monitoring")
            self.modbus_monitor.stop_monitoring()
            self.monitoring_active = False
            
            # Print final statistics
            stats = self.modbus_monitor.get_statistics()
            logger.info(f"📊 Final Statistics:")
            logger.info(f"   Total Requests: {stats['total_requests']}")
            logger.info(f"   Success Rate: {stats['success_rate']:.1f}%")
            logger.info(f"   Fallback Switches: {stats['fallback_switches']}")
    
    def export_all_results(self, output_dir: str = "diagnostics_output"):
        """Export all results to files."""
        logger.info(f"📁 Exporting results to {output_dir}")
        
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # Export log analysis
            if self.last_log_analysis:
                log_file = os.path.join(output_dir, f"log_analysis_{timestamp}.txt")
                self.log_analyzer.export_analysis_to_file(self.last_log_analysis, log_file)
            
            # Export network diagnostics
            if self.last_network_diagnostics:
                network_file = os.path.join(output_dir, f"network_diagnostics_{timestamp}.txt")
                self.network_diagnostics.export_diagnostics_to_file(self.last_network_diagnostics, network_file)
            
            # Export recommendations
            if self.last_recommendations:
                json_file = os.path.join(output_dir, f"recommendations_{timestamp}.json")
                self.recommendation_engine.export_recommendations_to_json(self.last_recommendations, json_file)
                
                const_file = os.path.join(output_dir, f"recommended_const_{timestamp}.py")
                self.recommendation_engine.generate_const_py_file(self.last_recommendations, const_file)
            
            # Export monitoring results
            if self.modbus_monitor:
                monitor_file = os.path.join(output_dir, f"monitoring_results_{timestamp}.csv")
                self.modbus_monitor.export_results_to_file(monitor_file)
            
            logger.info(f"✅ All results exported to {output_dir}")
            
        except Exception as e:
            logger.error(f"❌ Export failed: {e}")
            raise
    
    def print_summary(self):
        """Print summary of all results."""
        print("\n" + "="*60)
        print("📊 MODBUS DIAGNOSTICS SUMMARY")
        print("="*60)
        
        # Configuration summary
        config = get_config_summary()
        print(f"\n🔧 Configuration:")
        print(f"   Primary Host: {config['primary_host']}")
        print(f"   Secondary Host: {config['secondary_host']}")
        print(f"   Test Register: {config['test_register']}")
        print(f"   Monitoring Interval: {config['monitoring_interval']}")
        
        # Log analysis results
        if self.last_log_analysis:
            print(f"\n📋 Log Analysis:")
            print(f"   Total Timeouts: {self.last_log_analysis.total_timeouts}")
            print(f"   Problematic Registers: {len(self.last_log_analysis.problematic_registers)}")
            
            if self.last_log_analysis.problematic_registers:
                print(f"   Top Issues:")
                for pattern in self.last_log_analysis.problematic_registers[:3]:
                    print(f"     - Register {pattern.register} ({pattern.sensor_name}): "
                          f"{pattern.timeout_count} timeouts, severity: {pattern.severity}")
        
        # Network diagnostics results
        if self.last_network_diagnostics:
            print(f"\n🌐 Network Diagnostics:")
            print(f"   Health Score: {self.last_network_diagnostics.network_health_score:.1f}/100")
            print(f"   Issues Found: {len(self.last_network_diagnostics.issues_found)}")
            
            if self.last_network_diagnostics.issues_found:
                print(f"   Top Issues:")
                for issue in self.last_network_diagnostics.issues_found[:3]:
                    print(f"     - {issue}")
        
        # Recommendations
        if self.last_recommendations:
            print(f"\n💡 Recommendations:")
            print(f"   Total Recommendations: {len(self.last_recommendations.recommendations)}")
            print(f"   Risk Assessment: {self.last_recommendations.risk_assessment}")
            print(f"   Summary: {self.last_recommendations.summary}")
            
            if self.last_recommendations.recommendations:
                print(f"   Top Recommendations:")
                for rec in self.last_recommendations.recommendations[:3]:
                    print(f"     - {rec.type.upper()}: Register {rec.register} - {rec.reason}")
        
        # Monitoring results
        if self.modbus_monitor:
            stats = self.modbus_monitor.get_statistics()
            print(f"\n📈 Monitoring Results:")
            print(f"   Total Requests: {stats['total_requests']}")
            print(f"   Success Rate: {stats['success_rate']:.1f}%")
            print(f"   Fallback Switches: {stats['fallback_switches']}")
            print(f"   Primary Host Available: {stats['host_status']['primary']['available']}")
            print(f"   Secondary Host Available: {stats['host_status']['secondary']['available']}")
        
        print("\n" + "="*60)

class ModbusDiagnosticsGUI:
    """GUI interface for the Modbus diagnostics tool."""
    
    def __init__(self, tool: ModbusDiagnosticsTool):
        self.tool = tool
        self.root = tk.Tk()
        self.root.title("Modbus Diagnostics Tool")
        self.root.geometry("1000x700")
        
        self.setup_gui()
        
    def setup_gui(self):
        """Setup the GUI interface."""
        # Create main notebook
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Log Analysis Tab
        self.setup_log_analysis_tab(notebook)
        
        # Network Diagnostics Tab
        self.setup_network_diagnostics_tab(notebook)
        
        # Monitoring Tab
        self.setup_monitoring_tab(notebook)
        
        # Recommendations Tab
        self.setup_recommendations_tab(notebook)
        
        # Status Bar
        self.setup_status_bar()
    
    def setup_log_analysis_tab(self, notebook):
        """Setup log analysis tab."""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Log Analysis")
        
        # Controls
        controls_frame = ttk.Frame(frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(controls_frame, text="Hours to analyze:").pack(side=tk.LEFT)
        self.hours_var = tk.StringVar(value="24")
        ttk.Entry(controls_frame, textvariable=self.hours_var, width=10).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(controls_frame, text="Run Analysis", 
                  command=self.run_log_analysis).pack(side=tk.LEFT, padx=5)
        
        # Results
        self.log_results = scrolledtext.ScrolledText(frame, height=20)
        self.log_results.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    
    def setup_network_diagnostics_tab(self, notebook):
        """Setup network diagnostics tab."""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Network Diagnostics")
        
        # Controls
        controls_frame = ttk.Frame(frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(controls_frame, text="Quick Check", 
                  command=self.run_quick_check).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Full Diagnostics", 
                  command=self.run_network_diagnostics).pack(side=tk.LEFT, padx=5)
        
        # Results
        self.network_results = scrolledtext.ScrolledText(frame, height=20)
        self.network_results.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    
    def setup_monitoring_tab(self, notebook):
        """Setup monitoring tab."""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Monitoring")
        
        # Controls
        controls_frame = ttk.Frame(frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(controls_frame, text="Duration (minutes):").pack(side=tk.LEFT)
        self.duration_var = tk.StringVar(value="10")
        ttk.Entry(controls_frame, textvariable=self.duration_var, width=10).pack(side=tk.LEFT, padx=5)
        
        self.start_button = ttk.Button(controls_frame, text="Start Monitoring", 
                                      command=self.start_monitoring)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(controls_frame, text="Stop Monitoring", 
                                     command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Results
        self.monitoring_results = scrolledtext.ScrolledText(frame, height=20)
        self.monitoring_results.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    
    def setup_recommendations_tab(self, notebook):
        """Setup recommendations tab."""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Recommendations")
        
        # Controls
        controls_frame = ttk.Frame(frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(controls_frame, text="Generate Recommendations", 
                  command=self.generate_recommendations).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Export Results", 
                  command=self.export_results).pack(side=tk.LEFT, padx=5)
        
        # Results
        self.recommendations_results = scrolledtext.ScrolledText(frame, height=20)
        self.recommendations_results.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    
    def setup_status_bar(self):
        """Setup status bar."""
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def run_log_analysis(self):
        """Run log analysis in GUI."""
        self.status_var.set("Running log analysis...")
        self.log_results.delete(1.0, tk.END)
        
        try:
            hours = int(self.hours_var.get())
            result = self.tool.run_log_analysis(hours)
            
            # Display results
            self.log_results.insert(tk.END, f"Log Analysis Results ({hours} hours)\n")
            self.log_results.insert(tk.END, "="*50 + "\n\n")
            self.log_results.insert(tk.END, f"Total Timeouts: {result.total_timeouts}\n")
            self.log_results.insert(tk.END, f"Problematic Registers: {len(result.problematic_registers)}\n\n")
            
            if result.problematic_registers:
                self.log_results.insert(tk.END, "Problematic Registers:\n")
                for pattern in result.problematic_registers:
                    self.log_results.insert(tk.END, 
                        f"  Register {pattern.register} ({pattern.sensor_name}): "
                        f"{pattern.timeout_count} timeouts, severity: {pattern.severity}\n")
            
            self.status_var.set("Log analysis completed")
            
        except Exception as e:
            messagebox.showerror("Error", f"Log analysis failed: {e}")
            self.status_var.set("Log analysis failed")
    
    def run_quick_check(self):
        """Run quick network check in GUI."""
        self.status_var.set("Running quick network check...")
        self.network_results.delete(1.0, tk.END)
        
        try:
            result = self.tool.run_quick_network_check()
            
            # Display results
            self.network_results.insert(tk.END, "Quick Network Check Results\n")
            self.network_results.insert(tk.END, "="*50 + "\n\n")
            self.network_results.insert(tk.END, f"Overall Status: {result['overall_status']}\n\n")
            
            self.network_results.insert(tk.END, "Primary Host:\n")
            self.network_results.insert(tk.END, f"  Success: {result['primary_host']['success']}\n")
            if result['primary_host']['response_time']:
                self.network_results.insert(tk.END, f"  Response Time: {result['primary_host']['response_time']:.1f}ms\n")
            
            self.network_results.insert(tk.END, "\nSecondary Host:\n")
            self.network_results.insert(tk.END, f"  Success: {result['secondary_host']['success']}\n")
            if result['secondary_host']['response_time']:
                self.network_results.insert(tk.END, f"  Response Time: {result['secondary_host']['response_time']:.1f}ms\n")
            
            self.status_var.set("Quick network check completed")
            
        except Exception as e:
            messagebox.showerror("Error", f"Quick network check failed: {e}")
            self.status_var.set("Quick network check failed")
    
    def run_network_diagnostics(self):
        """Run full network diagnostics in GUI."""
        self.status_var.set("Running network diagnostics...")
        self.network_results.delete(1.0, tk.END)
        
        try:
            result = self.tool.run_network_diagnostics()
            
            # Display results
            self.network_results.insert(tk.END, "Network Diagnostics Results\n")
            self.network_results.insert(tk.END, "="*50 + "\n\n")
            self.network_results.insert(tk.END, f"Health Score: {result.network_health_score:.1f}/100\n")
            self.network_results.insert(tk.END, f"Issues Found: {len(result.issues_found)}\n\n")
            
            if result.issues_found:
                self.network_results.insert(tk.END, "Issues:\n")
                for issue in result.issues_found:
                    self.network_results.insert(tk.END, f"  - {issue}\n")
            
            if result.recommendations:
                self.network_results.insert(tk.END, "\nRecommendations:\n")
                for rec in result.recommendations:
                    self.network_results.insert(tk.END, f"  - {rec}\n")
            
            self.status_var.set("Network diagnostics completed")
            
        except Exception as e:
            messagebox.showerror("Error", f"Network diagnostics failed: {e}")
            self.status_var.set("Network diagnostics failed")
    
    def start_monitoring(self):
        """Start monitoring in GUI."""
        self.status_var.set("Starting monitoring...")
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        def monitor_thread():
            try:
                duration = int(self.duration_var.get())
                self.tool.start_monitoring(duration)
            except Exception as e:
                messagebox.showerror("Error", f"Monitoring failed: {e}")
            finally:
                self.root.after(0, self.monitoring_finished)
        
        threading.Thread(target=monitor_thread, daemon=True).start()
    
    def stop_monitoring(self):
        """Stop monitoring in GUI."""
        self.tool.stop_monitoring()
        self.monitoring_finished()
    
    def monitoring_finished(self):
        """Called when monitoring finishes."""
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("Monitoring completed")
        
        # Display statistics
        if self.tool.modbus_monitor:
            stats = self.tool.modbus_monitor.get_statistics()
            self.monitoring_results.delete(1.0, tk.END)
            self.monitoring_results.insert(tk.END, "Monitoring Results\n")
            self.monitoring_results.insert(tk.END, "="*50 + "\n\n")
            self.monitoring_results.insert(tk.END, f"Total Requests: {stats['total_requests']}\n")
            self.monitoring_results.insert(tk.END, f"Success Rate: {stats['success_rate']:.1f}%\n")
            self.monitoring_results.insert(tk.END, f"Fallback Switches: {stats['fallback_switches']}\n")
    
    def generate_recommendations(self):
        """Generate recommendations in GUI."""
        self.status_var.set("Generating recommendations...")
        self.recommendations_results.delete(1.0, tk.END)
        
        try:
            result = self.tool.generate_recommendations()
            
            # Display results
            self.recommendations_results.insert(tk.END, "Configuration Recommendations\n")
            self.recommendations_results.insert(tk.END, "="*50 + "\n\n")
            self.recommendations_results.insert(tk.END, f"Summary: {result.summary}\n")
            self.recommendations_results.insert(tk.END, f"Risk Assessment: {result.risk_assessment}\n\n")
            
            if result.recommendations:
                self.recommendations_results.insert(tk.END, "Recommendations:\n")
                for rec in result.recommendations:
                    self.recommendations_results.insert(tk.END, 
                        f"  {rec.type.upper()}: Register {rec.register}\n")
                    self.recommendations_results.insert(tk.END, 
                        f"    Reason: {rec.reason}\n")
                    self.recommendations_results.insert(tk.END, 
                        f"    Priority: {rec.priority}\n\n")
            
            self.status_var.set("Recommendations generated")
            
        except Exception as e:
            messagebox.showerror("Error", f"Recommendation generation failed: {e}")
            self.status_var.set("Recommendation generation failed")
    
    def export_results(self):
        """Export results in GUI."""
        try:
            self.tool.export_all_results()
            messagebox.showinfo("Success", "Results exported successfully!")
            self.status_var.set("Results exported")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")
            self.status_var.set("Export failed")
    
    def run(self):
        """Run the GUI."""
        self.root.mainloop()

def setup_logging(debug: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def main():
    """Main function with CLI interface."""
    parser = argparse.ArgumentParser(description="Modbus Diagnostics Tool")
    parser.add_argument("--gui", action="store_true", help="Start GUI interface")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--log-hours", type=int, default=24, help="Hours to analyze in logs")
    parser.add_argument("--monitor-duration", type=int, default=10, help="Monitoring duration in minutes")
    parser.add_argument("--export", action="store_true", help="Export results after analysis")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Log analysis command
    log_parser = subparsers.add_parser("log", help="Run log analysis")
    log_parser.add_argument("--hours", type=int, default=24, help="Hours to analyze")
    
    # Network diagnostics command
    net_parser = subparsers.add_parser("network", help="Run network diagnostics")
    net_parser.add_argument("--quick", action="store_true", help="Run quick check only")
    
    # Monitoring command
    monitor_parser = subparsers.add_parser("monitor", help="Run monitoring")
    monitor_parser.add_argument("--duration", type=int, default=10, help="Duration in minutes")
    
    # Recommendations command
    rec_parser = subparsers.add_parser("recommend", help="Generate recommendations")
    
    # Full analysis command
    full_parser = subparsers.add_parser("full", help="Run full analysis")
    full_parser.add_argument("--hours", type=int, default=24, help="Hours to analyze in logs")
    full_parser.add_argument("--monitor-duration", type=int, default=10, help="Monitoring duration")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.debug)
    
    # Create tool
    tool = ModbusDiagnosticsTool()
    
    # GUI mode
    if args.gui:
        if not GUI_AVAILABLE:
            print("❌ GUI not available - tkinter not installed")
            sys.exit(1)
        
        gui = ModbusDiagnosticsGUI(tool)
        gui.run()
        return
    
    # CLI mode
    try:
        if args.command == "log":
            result = tool.run_log_analysis(args.hours)
            print(f"✅ Log analysis completed: {result.total_timeouts} timeouts found")
            
        elif args.command == "network":
            if args.quick:
                result = tool.run_quick_network_check()
                print(f"✅ Quick check completed: {result['overall_status']}")
            else:
                result = tool.run_network_diagnostics()
                print(f"✅ Network diagnostics completed: Health score {result.network_health_score:.1f}/100")
                
        elif args.command == "monitor":
            print(f"🚀 Starting monitoring for {args.duration} minutes...")
            tool.start_monitoring(args.duration)
            
        elif args.command == "recommend":
            result = tool.generate_recommendations()
            print(f"✅ Generated {len(result.recommendations)} recommendations")
            
        elif args.command == "full":
            print("🚀 Running full analysis...")
            
            # Run all analyses
            tool.run_log_analysis(args.hours)
            tool.run_network_diagnostics()
            tool.start_monitoring(args.monitor_duration)
            tool.generate_recommendations()
            
            # Print summary
            tool.print_summary()
            
        else:
            # Default: run full analysis
            print("🚀 Running full analysis...")
            
            tool.run_log_analysis(args.log_hours)
            tool.run_network_diagnostics()
            tool.start_monitoring(args.monitor_duration)
            tool.generate_recommendations()
            
            tool.print_summary()
        
        # Export results if requested
        if args.export:
            tool.export_all_results()
            print("📁 Results exported")
            
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
        tool.stop_monitoring()
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

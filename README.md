# Modbus Diagnostics Tool

Ein umfassendes Diagnose-Tool für Modbus-Kommunikationsprobleme, speziell entwickelt für Lambda Heat Pump Integrationen in Home Assistant.

## 🎯 Features

### 🔍 Log-Analyse
- Analysiert HA-Logs auf Timeout-Muster
- Identifiziert problematische Register automatisch
- Erkennt zyklische und intermittierende Probleme
- Generiert detaillierte Berichte

### 🌐 Netzwerk-Diagnose
- Ping-Tests zu allen relevanten Hosts
- Port-Scans für Modbus-Ports (502, 5020, etc.)
- Modbus-Konnektivitätstests
- Automatischer Fallback auf sekundären Host

### 📊 Kontinuierliches Monitoring
- Randomisierte Zugriffsintervalle (Anti-Synchronisation)
- Automatischer Fallback bei Timeouts
- Circuit Breaker Pattern
- Umfassende Statistiken und Performance-Tracking

### 💡 Intelligente Empfehlungen
- Automatische Generierung von `const.py` Updates
- Empfehlungen für Individual Reads
- Timeout-Anpassungen basierend auf Performance
- Risikobewertung für Konfigurationsänderungen

## 🚀 Installation

### Voraussetzungen
- Python 3.8+
- Zugriff auf HA-Log-Dateien
- Netzwerk-Zugriff zu Modbus-Geräten

### Installation
```bash
# Repository klonen
git clone <repository-url>
cd modbus_diagnostics

# Abhängigkeiten installieren
pip install -r requirements.txt

# Verzeichnisse erstellen
mkdir -p logs data reports backups
```

## ⚙️ Konfiguration

### Hauptkonfiguration (`const.py`)
```python
# Modbus Hosts
PRIMARY_HOST = "192.168.178.125"    # Real Lambda Heat Pump
PRIMARY_PORT = 502
SECONDARY_HOST = "192.168.178.57"   # Python Modbus Server (Lambda WP Simulator)
SECONDARY_PORT = 5200

# Test-Register
TEST_REGISTER = 1000

# Monitoring-Intervalle
BASE_MONITORING_INTERVAL = 30  # Sekunden
RANDOM_INTERVAL_RANGE = 5      # ±Sekunden

# Timeouts
DEFAULT_TIMEOUT = 5.0
QUICK_TIMEOUT = 2.0
EXTENDED_TIMEOUT = 10.0
```

### HA-Log-Pfad anpassen
```python
# In const.py
HA_LOG_PATH = "path/to/your/home-assistant.log"
```

### Host-Zugriffsmodi konfigurieren
```python
# In const.py
HOST_ACCESS_MODE = 'fallback'  # Standard-Modus
```

**Verfügbare Modi:**
- `'fallback'` - Secondary (Simulator) nur bei Primary (Lambda WP) Fehlern
- `'alternating'` - Wechselt zwischen Primary und Secondary ab
- `'both'` - Beide Hosts bei jedem Request testen
- `'primary_only'` - Nur Primary (Lambda WP) verwenden
- `'secondary_only'` - Nur Secondary (Python Simulator) verwenden

## 🔧 Host-Zugriffsmodi im Detail

### 1. `fallback` (Standard)
```python
HOST_ACCESS_MODE = 'fallback'
```
**Verhalten:**
- Primary (Lambda WP) wird zuerst versucht
- Secondary (Python Simulator) nur bei Primary-Fehlern
- **Wann wird Secondary verwendet:** Nur bei Timeouts/Fehlern des Primary

**Vorteile:**
- Minimale Belastung des Simulators
- Einfache Konfiguration
- Zuverlässiger Fallback

**Nachteile:**
- Simulator wird selten getestet
- Langsame Erkennung von Simulator-Problemen

**Verwendung:** Produktionsumgebung, normale Diagnose

### 2. `alternating`
```python
HOST_ACCESS_MODE = 'alternating'
```
**Verhalten:**
- Wechselt bei jedem Request ab
- Request 1: Primary → Request 2: Secondary → Request 3: Primary...
- **Wann wird Secondary verwendet:** Bei jedem zweiten Request

**Vorteile:**
- Gleichmäßige Belastung beider Hosts
- Regelmäßige Tests beider Hosts
- Bessere Fehlererkennung

**Nachteile:**
- Höhere Netzwerk-Belastung
- Komplexere Logik

**Verwendung:** Load Balancing, regelmäßige Tests

### 3. `both`
```python
HOST_ACCESS_MODE = 'both'
```
**Verhalten:**
- Beide Hosts werden bei jedem Request parallel getestet
- **Wann wird Secondary verwendet:** Bei jedem Request parallel zum Primary

**Vorteile:**
- Vollständige Diagnose
- Performance-Vergleich
- Schnelle Fehlererkennung

**Nachteile:**
- Doppelte Netzwerk-Belastung
- Längere Request-Zeit

**Verwendung:** Umfassende Diagnose, Performance-Vergleich

### 4. `primary_only`
```python
HOST_ACCESS_MODE = 'primary_only'
```
**Verhalten:**
- Nur Primary (Lambda WP) wird verwendet
- **Wann wird Secondary verwendet:** Nie

**Vorteile:**
- Minimale Belastung
- Einfache Konfiguration

**Nachteile:**
- Kein Fallback
- Keine Redundanz

**Verwendung:** Wenn Secondary nicht verfügbar ist

### 5. `secondary_only`
```python
HOST_ACCESS_MODE = 'secondary_only'
```
**Verhalten:**
- Nur Secondary (Python Simulator) wird verwendet
- **Wann wird Secondary verwendet:** Bei jedem Request

**Vorteile:**
- Testet Simulator
- Einfache Konfiguration

**Nachteile:**
- Kein Fallback
- Keine Redundanz

**Verwendung:** Testing des Simulators, wenn Primary nicht verfügbar

### 🔄 Host-Switch-Funktionalität

Das Tool unterstützt das dynamische Wechseln zwischen Primary und Secondary Hosts:

```python
# In const.py
USE_SECONDARY_AS_PRIMARY = True  # Aktiviert Host-Switch
```

**Host-Switch aktiviert:**
- **Primary wird zu:** Secondary (Python Simulator)
- **Secondary wird zu:** Primary (Real Lambda WP)
- **Zweck:** Testing mit umgekehrten Rollen

**Host-Switch deaktiviert (Standard):**
- **Primary:** Real Lambda WP
- **Secondary:** Python Simulator

**Verwendung des Host-Switches:**
```python
# In Python-Code
from const import switch_hosts, get_host_status

# Hosts wechseln
switch_hosts()

# Aktuellen Status abfragen
status = get_host_status()
print(f"Switch enabled: {status['switch_enabled']}")
print(f"Active Primary: {status['active_primary']['host']}")
```

## 🖥️ Verwendung

### 🔍 Lambda WP vs Simulator Analyse (Empfohlen)
```bash
python lambda_vs_simulator_analysis.py
```
**Zweck:** Unterscheidet zwischen Lambda WP-Problemen und Netzwerk-Problemen
- **Real Lambda WP:** Testet die echte Wärmepumpe
- **Python Simulator:** Testet die Netzwerk-Verbindung  
- **Vergleich:** Identifiziert die Ursache der Probleme

### GUI-Modus
```bash
python main_tool.py --gui
```

## 📊 Ergebnisse interpretieren

### 🔍 Lambda WP vs Simulator Analyse

#### Interpretationsregeln:
1. **Lambda WP funktioniert, Simulator funktioniert** → ✅ Kein Problem
2. **Lambda WP funktioniert NICHT, Simulator funktioniert** → 🔧 **Lambda WP Problem**
3. **Lambda WP funktioniert NICHT, Simulator funktioniert NICHT** → 🌐 **Netzwerk Problem**
4. **Lambda WP funktioniert, Simulator funktioniert NICHT** → ⚠️ Simulator Problem

#### Wichtige Erkenntnisse:
- **Python Simulator** = Netzwerk-Test (sollte immer funktionieren)
- **Real Lambda WP** = Geräte-Test (kann Probleme haben)
- **Vergleich** = Identifiziert die Ursache

#### Empfohlene Aktionen basierend auf Ergebnissen:

**🔧 Lambda WP Problem:**
- Lambda WP Status prüfen
- Lambda WP Netzwerk-Verbindung prüfen
- Lambda WP Error Logs prüfen
- Lambda WP Neustart erwägen
- HA const.py mit längeren Timeouts für problematische Register aktualisieren

**🌐 Netzwerk Problem:**
- Netzwerk-Verbindung prüfen
- IP-Adressen und Ports verifizieren
- Firewall-Einstellungen prüfen
- Mit ping und telnet testen

**✅ Kein Problem:**
- Auf intermittierende Probleme überwachen
- HA Integration Konfiguration prüfen
- Netzwerk-Stabilität über Zeit verifizieren

### CLI-Modus

#### Vollständige Analyse
```bash
python main_tool.py --full --log-hours 24 --monitor-duration 10
```

**Wichtige Parameter-Unterschiede:**
- `--log-hours 24`: Analysiert **vergangene** HA-Logs der letzten 24 Stunden
- `--monitor-duration 10`: Führt **10 Minuten** Live-Monitoring durch (neue Tests)

#### Einzelne Komponenten
```bash
# Log-Analyse
python main_tool.py log --hours 24

# Netzwerk-Diagnose
python main_tool.py network

# Schneller Netzwerk-Check
python main_tool.py network --quick

# Monitoring
python main_tool.py monitor --duration 10

# Empfehlungen generieren
python main_tool.py recommend
```

#### Ergebnisse exportieren
```bash
python main_tool.py --full --export
```

## 📋 Beispiel-Workflow

### 1. Problem identifizieren
```bash
# Schneller Check
python main_tool.py network --quick
```

### 2. Log-Analyse
```bash
# Letzte 24 Stunden analysieren
python main_tool.py log --hours 24
```

### 3. Detaillierte Diagnose
```bash
# Vollständige Analyse mit Monitoring
python main_tool.py --full --log-hours 48 --monitor-duration 30
```

**Parameter-Erklärung:**
- `--log-hours 48`: Analysiert HA-Logs der **letzten 48 Stunden** (vergangene Probleme)
- `--monitor-duration 30`: Führt **30 Minuten** Live-Monitoring durch (aktuelle Performance)

### 4. Empfehlungen umsetzen
```bash
# Empfehlungen generieren
python main_tool.py recommend

# Generierte const.py prüfen
cat recommended_const.py
```

## 📊 Ausgabe-Beispiele

### Log-Analyse
```
📊 Log Analysis Results:
   Total Timeouts: 15
   Problematic Registers: 2
   
   Top Issues:
   - Register 0 (eu08l_hp1_error_state): 12 timeouts, severity: high
   - Register 1000 (test_register): 3 timeouts, severity: medium
```

### Netzwerk-Diagnose
```
🌐 Network Diagnostics Results:
   Health Score: 75.0/100
   Issues Found: 2
   
   Issues:
   - High latency to 192.168.178.125: 150.2ms
   - Modbus port 502 closed on 192.168.178.57
```

### Empfehlungen
```
💡 Configuration Recommendations:
   Summary: Add 2 registers to individual reads; Adjust timeouts for 1 register
   Risk Assessment: LOW RISK: 1 high-priority recommendations
   
   Recommendations:
   - INDIVIDUAL_READ: Register 0 - High error rate: 8.3%
   - TIMEOUT_ADJUSTMENT: Register 0 - Frequent timeouts with current 2s timeout
```

## 🔧 Generierte const.py

Das Tool generiert automatisch eine optimierte `const.py`:

```python
# Lambda Heat Pumps - Updated Configuration
# Generated by Modbus Diagnostics Tool

# Individual Read Registers
LAMBDA_INDIVIDUAL_READ_REGISTERS = [
    0,
    1000,
    1050,
    1060,
]

# Register-specific Timeouts
LAMBDA_REGISTER_TIMEOUTS = {
    0: 5.0,  # eu08l_hp1_error_state
    1000: 3.0,  # test_register
    1050: 2.0,  # register_1050
    1060: 2.0,  # register_1060
}

# Low Priority Registers
LAMBDA_LOW_PRIORITY_REGISTERS = [
    1050,
    1060,
]
```

## 📁 Ausgabedateien

### Logs
- `logs/modbus_diagnostics.log` - Hauptlog
- `logs/performance.log` - Performance-Metriken
- `logs/errors.log` - Fehler-Log

### Berichte
- `reports/log_analysis_YYYYMMDD_HHMMSS.txt`
- `reports/network_diagnostics_YYYYMMDD_HHMMSS.txt`
- `reports/recommendations_YYYYMMDD_HHMMSS.json`

### Konfiguration
- `recommended_const.py` - Optimierte const.py
- `backups/const_backup_YYYYMMDD_HHMMSS.py` - Backup der ursprünglichen Konfiguration

## 🎛️ Erweiterte Konfiguration

### Anti-Synchronisation
```python
# Verhindert gleichzeitige Zugriffe mehrerer Clients
ANTI_SYNC_ENABLED = True
ANTI_SYNC_FACTOR = 0.2  # 20% Jitter-Variation
```

### Circuit Breaker
```python
# Automatische Abschaltung bei wiederholten Fehlern
CIRCUIT_BREAKER_ENABLED = True
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 60
```

### Schwellenwerte
```python
# Empfehlungs-Schwellenwerte
INDIVIDUAL_READ_TIMEOUT_THRESHOLD = 3
INDIVIDUAL_READ_ERROR_THRESHOLD = 5
SLOW_RESPONSE_THRESHOLD = 2000  # 2 Sekunden
```

## 🐛 Troubleshooting

### Häufige Probleme

#### "HA log file not found"
```bash
# Log-Pfad in const.py anpassen
HA_LOG_PATH = "/path/to/your/home-assistant.log"
```

#### "Connection refused"
```bash
# Hosts und Ports in const.py prüfen
PRIMARY_HOST = "192.168.178.125"
PRIMARY_PORT = 502
```

#### "No timeout events found"
```bash
# Längeren Zeitraum analysieren
python main_tool.py log --hours 48
```

#### Parameter-Verwirrung: `--log-hours` vs `--monitor-duration`
```bash
# FALSCH: Beide Parameter für dasselbe verwenden
python main_tool.py --full --log-hours 60 --monitor-duration 60

# RICHTIG: Unterschiedliche Zwecke
python main_tool.py --full --log-hours 48 --monitor-duration 30
# ↑ Analysiert letzte 48h HA-Logs + 30min neue Tests
```

**Erklärung:**
- `--log-hours`: **Vergangenheit** - Wie weit zurück in HA-Logs schauen
- `--monitor-duration`: **Zukunft** - Wie lange Live-Monitoring laufen lassen

### Debug-Modus
```bash
# Detaillierte Logs aktivieren
python main_tool.py --debug --full
```

## 📈 Performance-Optimierung

### Für große Log-Dateien
```python
# In const.py
MAX_LOG_SIZE = 50 * 1024 * 1024  # 50MB
BACKUP_COUNT = 3
```

### Für viele Register
```python
# Monitoring-Intervall erhöhen
BASE_MONITORING_INTERVAL = 60  # 1 Minute
RANDOM_INTERVAL_RANGE = 10     # ±10 Sekunden
```

## 🤝 Beitragen

1. Fork des Repositories
2. Feature-Branch erstellen
3. Änderungen committen
4. Pull Request erstellen

## 📄 Lizenz

MIT License - siehe LICENSE-Datei für Details.

## 🆘 Support

Bei Problemen oder Fragen:
1. Issues im Repository erstellen
2. Logs und Konfiguration anhängen
3. Detaillierte Beschreibung des Problems

---

**Entwickelt für Lambda Heat Pump Integrationen in Home Assistant**

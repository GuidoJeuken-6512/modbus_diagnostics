# Modbus Diagnostics Tool - Installation

## Systemvoraussetzungen

### Ubuntu/Debian
```bash
# Python 3 und pip installieren (falls nicht vorhanden)
sudo apt update
sudo apt install python3 python3-pip python3-venv

# tkinter für GUI-Unterstützung installieren
sudo apt install python3-tk

# Weitere nützliche Pakete
sudo apt install sqlite3
```

### Andere Linux-Distributionen
- **CentOS/RHEL/Fedora**: `sudo yum install python3 python3-pip python3-tkinter`
- **Arch Linux**: `sudo pacman -S python python-pip tk`

## Virtuelle Umgebung einrichten

```bash
# Virtuelle Umgebung erstellen
python3 -m venv .venv

# Virtuelle Umgebung aktivieren
source .venv/bin/activate

# Requirements installieren
pip install -r requirements.txt
```

## Verwendung

### GUI-Modus starten
```bash
source .venv/bin/activate
python main_tool.py --gui
```

### CLI-Modus verwenden
```bash
source .venv/bin/activate

# Monitoring starten
python main_tool.py monitor --duration 10

# Vollständige Analyse
python main_tool.py full

# Hilfe anzeigen
python main_tool.py --help
```

## Konfiguration

Die Hauptkonfiguration befindet sich in `const.py`:
- Modbus-Hosts und Ports
- Timeout-Einstellungen
- Monitoring-Intervalle
- Logging-Konfiguration

## Fehlerbehebung

### "tkinter not installed" Fehler
```bash
sudo apt install python3-tk
```

### Speicherzugriffsfehler mit pymodbus
Das Tool verwendet pymodbus 2.5.3 für Kompatibilität. Falls Probleme auftreten:
```bash
pip uninstall pymodbus
pip install pymodbus==2.5.3
```

### Netzwerkverbindungsprobleme
- Überprüfen Sie die IP-Adressen in `const.py`
- Stellen Sie sicher, dass die Modbus-Geräte erreichbar sind
- Testen Sie mit: `python test_connection.py`

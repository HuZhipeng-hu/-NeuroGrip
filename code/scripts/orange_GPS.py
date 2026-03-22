# coding: utf-8
# last modified: 20260321
from dataclasses import dataclass
import json
import os
import threading
import time
from typing import Optional
import urllib.parse
import urllib.request

import serial

try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None


SERIAL_PORT = os.getenv("GPS_SERIAL_PORT", "COM3")  # Windows default COM3, Linux default /dev/ttyUSB0
BAUD_RATE = 9600
REVERSE_GEOCODE_TIMEOUT = 3
REVERSE_GEOCODE_URL = "https://nominatim.openstreetmap.org/reverse"
REVERSE_GEOCODE_INTERVAL = 10.0  # limit to 1 request every 10 seconds
MAX_TRACK_POINTS = 500


@dataclass
class GPSData:
    utctime: str = ""
    lat: float = 0.0
    lat_dir: str = ""
    lon: float = 0.0
    lon_dir: str = ""
    quality: int = 0  # 0=Invalid, 1=GPS fix, 2=DGPS fix
    num_sv: int = 0
    altitude: float = 0.0
    cog: float = 0.0  # Course over ground (True)
    spk: float = 0.0  # Speed in km/h
    region: str = "Init..."
    last_update: float = 0.0


class GeocoderThread(threading.Thread):
    def __init__(self, gps_data: GPSData):
        super().__init__(daemon=True)
        self.gps_data = gps_data
        self.last_request_time = 0.0
        self.running = True

    def run(self):
        while self.running:
            now = time.time()
            # Only request if we have a valid fix, coordinates are non-zero, and enough time passed
            if (self.gps_data.quality > 0 and 
                (self.gps_data.lat != 0.0 or self.gps_data.lon != 0.0) and 
                (now - self.last_request_time > REVERSE_GEOCODE_INTERVAL)):
                
                try:
                    location = self._reverse_geocode(self.gps_data.lat, self.gps_data.lon)
                    self.gps_data.region = location
                    self.last_request_time = time.time()
                except Exception as e:
                    print(f"Geocode error: {e}")
            
            time.sleep(1.0)

    def _reverse_geocode(self, lat: float, lon: float) -> str:
        query = urllib.parse.urlencode({
            "format": "jsonv2",
            "lat": f"{lat:.6f}",
            "lon": f"{lon:.6f}",
            "zoom": 14,
            "addressdetails": 0,
            "accept-language": "zh-CN",
        })
        url = f"{REVERSE_GEOCODE_URL}?{query}"
        req = urllib.request.Request(url, headers={"User-Agent": "OrangePi-GPS/1.0"})
        
        with urllib.request.urlopen(req, timeout=REVERSE_GEOCODE_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("display_name", "Unknown Location")

    def stop(self):
        self.running = False


class TrackPlotter:
    def __init__(self, max_points: int = MAX_TRACK_POINTS) -> None:
        self.enabled = plt is not None
        self.max_points = max_points
        self.lat_points: list[float] = []
        self.lon_points: list[float] = []

        if not self.enabled:
            print("2D Track Plotting Disabled: matplotlib not available")
            return

        plt.ion()
        self.figure, self.ax = plt.subplots(figsize=(7, 5))
        self.line, = self.ax.plot([], [], "b-", linewidth=1.5, label="Track")
        self.current_point, = self.ax.plot([], [], "ro", markersize=5, label="Current")
        self.ax.set_xlabel("Longitude")
        self.ax.set_ylabel("Latitude")
        self.ax.set_title("GPS Real-time Track")
        self.ax.grid(True)
        self.ax.legend(loc="upper right")
        print("2D Track Plotting Enabled")

    def update(self, lat: float, lon: float) -> None:
        if not self.enabled:
            return

        self.lat_points.append(lat)
        self.lon_points.append(lon)

        if len(self.lat_points) > self.max_points:
            self.lat_points.pop(0)
            self.lon_points.pop(0)

        self.line.set_data(self.lon_points, self.lat_points)
        self.current_point.set_data([lon], [lat])
        
        # Dynamic scaling
        if len(self.lat_points) > 1:
            self.ax.relim()
            self.ax.autoscale_view()
        else:
            # Initial centered view
            delta = 0.005
            self.ax.set_xlim(lon - delta, lon + delta)
            self.ax.set_ylim(lat - delta, lat + delta)

        self.figure.canvas.draw_idle()
        self.figure.canvas.flush_events()


def dm_to_dd(raw_value: str) -> float:
    """Convert NMEA Degree-Minute (ddmm.mmmm) string to Decimal Degrees (dd.dddd)"""
    if not raw_value:
        return 0.0
    try:
        val = float(raw_value)
        degrees = int(val / 100)
        minutes = val - (degrees * 100)
        return degrees + (minutes / 60.0)
    except ValueError:
        return 0.0


def parse_nmea_line(line: str, data: GPSData) -> bool:
    """Parse a single NMEA line and update GPSData. Returns True if position updated."""
    try:
        line = line.strip()
        if not line.startswith("$"):
            return False
            
        parts = line.split("*")[0].split(",")  # Remove checksum if present
        cmd = parts[0]

        # GGA - Global Positioning System Fix Data
        if cmd.endswith("GGA"):
            # $GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47
            if len(parts) < 10: return False
            
            try:
                quality = int(parts[6])
            except ValueError:
                quality = 0
            
            data.quality = quality
            if quality == 0:
                return False

            data.utctime = parts[1]
            
            lat_val = dm_to_dd(parts[2])
            lat_dir = parts[3]
            if lat_dir == 'S': lat_val = -lat_val
            
            lon_val = dm_to_dd(parts[4])
            lon_dir = parts[5]
            if lon_dir == 'W': lon_val = -lon_val
            
            data.lat = lat_val
            data.lat_dir = lat_dir
            data.lon = lon_val
            data.lon_dir = lon_dir
            
            try:
                data.num_sv = int(parts[7])
                data.altitude = float(parts[9])
            except ValueError:
                pass
                
            data.last_update = time.time()
            return True

        # VTG - Track made good and ground speed
        elif cmd.endswith("VTG"):
            # $GPVTG,054.7,T,034.4,M,005.5,N,010.2,K*48
            if len(parts) < 10: return False
            try:
                data.cog = float(parts[1]) if parts[1] else 0.0
                data.spk = float(parts[7]) if parts[7] else 0.0
            except ValueError:
                pass
            return False

    except Exception as e:
        print(f"Parse error: {e}")
        return False
    
    return False


def print_status(data: GPSData):
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 40)
    print(f" GPS STATUS: {'FIXED' if data.quality > 0 else 'SEARCHING'}")
    print("=" * 40)
    print(f" UTC Time  : {data.utctime}")
    print(f" Latitude  : {data.lat:.6f} {data.lat_dir}")
    print(f" Longitude : {data.lon:.6f} {data.lon_dir}")
    print(f" Altitude  : {data.altitude:.1f} m")
    print(f" Satellites: {data.num_sv}")
    print(f" Speed     : {data.spk:.1f} km/h")
    print(f" Course    : {data.cog:.1f} deg")
    print("-" * 40)
    print(f" Location  : {data.region}")
    print("=" * 40)


def main():
    print(f"Opening Serial {SERIAL_PORT} @ {BAUD_RATE}...")
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1.0)
    except serial.SerialException as e:
        print(f"Failed to open serial port: {e}")
        return

    gps_data = GPSData()
    plotter = TrackPlotter()
    
    # Start background geocoder
    geocoder = GeocoderThread(gps_data)
    geocoder.start()

    print("GPS Started. Waiting for data...")
    
    try:
        while True:
            try:
                line = ser.readline().decode('ascii', errors='ignore')
                if not line:
                    continue
                    
                if parse_nmea_line(line, gps_data):
                    # Only update UI/Plot on valid position fix (GGA)
                    print_status(gps_data)
                    plotter.update(gps_data.lat, gps_data.lon)
                    
            except UnicodeDecodeError:
                continue
                
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        geocoder.stop()
        ser.close()
        plotter.enabled = False  # Stop plotter updates
        plt.close('all') if plt else None
        geocoder.join(timeout=2)
        print("Stopped.")

if __name__ == "__main__":
    main()

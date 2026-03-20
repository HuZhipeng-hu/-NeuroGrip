# -*- coding: utf-8 -*-
"""
windows_emg_uploader.py - Windows EMG 数据上报至 Spring Boot 后端
==================================================================
在 Windows PC 上运行，通过串口（COM 口）读取 EMG 臂带数据，
实时通过 WebSocket + HTTP 双通道上报到云端 Spring Boot 服务器。

架构:
  EMG臂带 ──串口(COM)──> Windows PC ──WebSocket/HTTP──> Spring Boot ──> 华为RDS MySQL
                                                             │
                                                       WebSocket推送
                                                             │
                                                     HarmonyOS App (DevEco)

依赖（在 Windows 上安装）:
  pip install pyserial numpy requests websocket-client

运行:
  python windows_emg_uploader.py
  python windows_emg_uploader.py --port COM5
  python windows_emg_uploader.py --port COM5 --mode both

环境变量（可选，命令行参数优先）:
  EMG_SERIAL_PORT=COM3
  BACKEND_URL=http://your-ecs-ip:8080
  BACKEND_WS_URL=ws://your-ecs-ip:8080/ws/emg
"""

import os
import sys
import json
import time
import struct
import threading
import logging
import argparse
from collections import deque
from datetime import datetime

# ==================== 日志 ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger('emg_uploader')


# ==================== 配置 ====================

# EMG 串口配置（Windows 上通常是 COM3, COM4 等）
SERIAL_PORT = os.environ.get('EMG_SERIAL_PORT')  # 默认自动检测
SERIAL_BAUDRATE = 115200

# Spring Boot 后端地址 (默认为云端 ECS IP)
BACKEND_BASE_URL = os.environ.get('BACKEND_URL', 'http://1.95.65.51:8080').rstrip('/')
BACKEND_WS_URL = os.environ.get('BACKEND_WS_URL', 'ws://1.95.65.51:8080/ws/emg').rstrip('/')

# 上报策略
UPLOAD_MODE = 'websocket'     # 'websocket' | 'http_batch' | 'both'
HTTP_BATCH_SIZE = 20          # HTTP 批量上报：攒够 N 帧发送一次
HTTP_BATCH_INTERVAL = 0.5     # HTTP 批量上报：最长间隔（秒）
WS_RECONNECT_DELAY = 3       # WebSocket 断线重连间隔（秒）
DEVICE_ID = 'windows_01'     # 设备标识（支持多设备）

# 帧协议常量
FRAME_HEADER = b'\xAA\xAA'
FRAME_TAIL = 0x55
MIN_FRAME_LEN = 6


# ==================== Windows 串口工具函数 ====================

def list_com_ports():
    """列出 Windows 上所有可用的 COM 端口"""
    ports = []
    try:
        import serial.tools.list_ports
        for port_info in serial.tools.list_ports.comports():
            ports.append({
                'device': port_info.device,
                'description': port_info.description,
                'hwid': port_info.hwid,
            })
    except ImportError:
        # 如果 pyserial 未安装，手动检测 COM1~COM20
        import ctypes
        for i in range(1, 21):
            port_name = f'COM{i}'
            try:
                handle = ctypes.windll.kernel32.CreateFileW(
                    f'\\\\.\\{port_name}', 0x80000000, 0, None, 3, 0, None
                )
                if handle != -1:
                    ctypes.windll.kernel32.CloseHandle(handle)
                    ports.append({
                        'device': port_name,
                        'description': '(未知)',
                        'hwid': '',
                    })
            except Exception:
                pass
    return ports


def auto_detect_emg_port():
    """
    尝试自动检测 EMG 臂带所使用的 COM 端口。
    优先匹配 USB 串口 (CH340, CP210x, FTDI) 等典型设备。
    """
    ports = list_com_ports()
    if not ports:
        return None

    # USB 转串口芯片常见关键字
    usb_serial_keywords = ['CH340', 'CH341', 'CP210', 'FTDI', 'USB', 'Serial', 'UART']

    # 优先选择 USB 串口设备
    for port in ports:
        desc = port['description'].upper()
        hwid = port['hwid'].upper()
        for keyword in usb_serial_keywords:
            if keyword.upper() in desc or keyword.upper() in hwid:
                return port['device']

    # 没匹配到 USB 串口，则返回第一个可用端口
    return ports[0]['device']


# ==================== 帧解析器（与 emg_armband.py 一致）====================

def parse_frame(frame_bytes):
    """解析 EMG 帧数据"""
    if len(frame_bytes) < MIN_FRAME_LEN:
        return None
    if frame_bytes[:2] != FRAME_HEADER or frame_bytes[-1] != FRAME_TAIL:
        return None

    length_byte = frame_bytes[2]
    expected_total = 2 + 1 + length_byte
    if len(frame_bytes) != expected_total:
        return None

    try:
        payload = frame_bytes[3:3 + (length_byte - 1)]
        offset = 0

        timestamp, = struct.unpack_from('>I', payload, offset); offset += 4
        acc_x, acc_y, acc_z = struct.unpack_from('>3b', payload, offset); offset += 3
        gyro_x, gyro_y, gyro_z = struct.unpack_from('>3b', payload, offset); offset += 3
        pitch, roll, yaw = struct.unpack_from('>3b', payload, offset); offset += 3

        emg_data = []
        for _ in range(10):
            channels = struct.unpack_from('>8B', payload, offset)
            emg_data.append(list(channels))
            offset += 8

        battery = payload[offset] if offset < len(payload) else 0

        return {
            'device_ts': timestamp,
            'emg': emg_data,
            'acc': [acc_x, acc_y, acc_z],
            'gyro': [gyro_x, gyro_y, gyro_z],
            'angle': [pitch, roll, yaw],
            'battery': battery,
        }
    except Exception:
        return None


def find_frames(buffer):
    """从缓冲区提取所有完整帧"""
    frames = []
    while True:
        idx = buffer.find(b'\xAA\xAA')
        if idx == -1 or idx + 3 > len(buffer):
            break
        if idx > 0:
            buffer = buffer[idx:]

        if len(buffer) < 3:
            break

        length_byte = buffer[2]
        total_len = 2 + 1 + length_byte

        if len(buffer) < total_len:
            break

        frame_bytes = bytes(buffer[:total_len])
        parsed = parse_frame(frame_bytes)
        if parsed:
            frames.append(parsed)

        buffer = buffer[total_len:]

    return frames, buffer


# ==================== 串口数据采集 ====================

class SerialReader:
    """串口数据读取器（Windows COM 端口）"""

    def __init__(self, port, baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self._serial = None
        self._buffer = bytearray()
        self._frame_count = 0

    def connect(self):
        import serial
        self._serial = serial.Serial(self.port, self.baudrate, timeout=0.5)
        log.info(f"串口已连接: {self.port} @ {self.baudrate}")

    def read_frames(self):
        """读取并解析所有可用帧"""
        if not self._serial or not self._serial.is_open:
            return []

        try:
            data = self._serial.read(512)
        except Exception:
            return []

        if not data:
            return []

        self._buffer.extend(data)

        # 防溢出
        if len(self._buffer) > 10000:
            self._buffer = self._buffer[-5000:]

        frames, self._buffer = find_frames(self._buffer)
        self._frame_count += len(frames)
        return frames

    def close(self):
        if self._serial and self._serial.is_open:
            self._serial.close()
            log.info("串口已关闭")


# ==================== WebSocket 上报通道 ====================

class WebSocketUploader:
    """通过 WebSocket 实时上报数据到 Spring Boot"""

    def __init__(self, ws_url, device_id):
        self.ws_url = ws_url
        self.device_id = device_id
        self._ws = None
        self._connected = False
        self._lock = threading.Lock()
        self._sent_count = 0
        self._reconnect_thread = None

    def connect(self):
        """连接 WebSocket"""
        try:
            import websocket
            self._ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self._on_open,
                on_close=self._on_close,
                on_error=self._on_error,
            )
            # 在后台线程运行 WebSocket 事件循环
            self._reconnect_thread = threading.Thread(
                target=self._ws.run_forever,
                kwargs={'reconnect': WS_RECONNECT_DELAY},
                daemon=True
            )
            self._reconnect_thread.start()
            log.info(f"WebSocket 连接中: {self.ws_url}")
        except ImportError:
            log.error("请安装 websocket-client: pip install websocket-client")
            sys.exit(1)

    def _on_open(self, ws):
        self._connected = True
        self._sent_count = 0
        # 发送注册消息
        reg_msg = json.dumps({
            'type': 'register',
            'deviceId': self.device_id,
            'timestamp': datetime.now().isoformat(),
        })
        ws.send(reg_msg)
        log.info("WebSocket 已连接并注册")

    def _on_close(self, ws, close_status, close_msg):
        self._connected = False
        log.warning(f"WebSocket 断开: {close_status} {close_msg}")

    def _on_error(self, ws, error):
        log.error(f"WebSocket 错误: {error}")

    def send_frame(self, frame_data):
        """发送一帧数据"""
        if not self._connected or not self._ws:
            return False

        try:
            msg = json.dumps({
                'type': 'emg_frame',
                'deviceId': self.device_id,
                'serverTime': datetime.now().isoformat(),
                'data': frame_data,
            })
            self._ws.send(msg)
            self._sent_count += 1
            return True
        except Exception as e:
            log.error(f"WebSocket 发送失败: {e}")
            return False

    @property
    def is_connected(self):
        return self._connected

    @property
    def sent_count(self):
        return self._sent_count


# ==================== HTTP 批量上报通道 ====================

class HttpBatchUploader:
    """通过 HTTP POST 批量上报数据到 Spring Boot REST API"""

    def __init__(self, base_url, device_id, batch_size=20, flush_interval=0.5):
        self.base_url = base_url.rstrip('/')
        self.device_id = device_id
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self._buffer = []
        self._lock = threading.Lock()
        self._last_flush = time.time()
        self._sent_count = 0

        # 启动定时刷新
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

    def add_frame(self, frame_data):
        """添加一帧到缓冲区"""
        frame_data['serverTime'] = datetime.now().isoformat()
        with self._lock:
            self._buffer.append(frame_data)

        if len(self._buffer) >= self.batch_size:
            self._flush()

    def _flush(self):
        """批量发送"""
        with self._lock:
            if not self._buffer:
                return
            batch = self._buffer.copy()
            self._buffer.clear()

        try:
            import requests
            url = f"{self.base_url}/api/emg/batch"
            payload = {
                'deviceId': self.device_id,
                'frames': batch,
                'count': len(batch),
                'uploadTime': datetime.now().isoformat(),
            }
            resp = requests.post(url, json=payload, timeout=5)
            if resp.status_code == 200:
                self._sent_count += len(batch)
            else:
                log.warning(f"HTTP 上报失败 [{resp.status_code}]: {resp.text[:200]}")
                # 失败时放回缓冲区
                with self._lock:
                    self._buffer = batch + self._buffer
        except Exception as e:
            log.error(f"HTTP 请求异常: {e}")
            with self._lock:
                self._buffer = batch + self._buffer

    def _flush_loop(self):
        while True:
            time.sleep(self.flush_interval)
            self._flush()

    @property
    def sent_count(self):
        return self._sent_count


# ==================== 命令行参数 ====================

def parse_args():
    parser = argparse.ArgumentParser(
        description='Windows EMG 数据上报工具 - 通过串口采集 EMG 臂带数据并上报到 Spring Boot 后端',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python windows_emg_uploader.py                       # 自动检测 COM 口
  python windows_emg_uploader.py --port COM5           # 指定 COM5
  python windows_emg_uploader.py --port COM5 --mode both
  python windows_emg_uploader.py --list-ports          # 列出所有可用串口
  python windows_emg_uploader.py --backend http://192.168.1.100:8080
        """
    )
    parser.add_argument('--port', '-p', type=str, default=None,
                        help='串口名称，如 COM3, COM5 (默认自动检测)')
    parser.add_argument('--baudrate', '-b', type=int, default=SERIAL_BAUDRATE,
                        help=f'波特率 (默认: {SERIAL_BAUDRATE})')
    parser.add_argument('--backend', type=str, default=None,
                        help=f'后端 HTTP 地址 (默认: {BACKEND_BASE_URL})')
    parser.add_argument('--ws-url', type=str, default=None,
                        help=f'后端 WebSocket 地址 (默认: {BACKEND_WS_URL})')
    parser.add_argument('--mode', '-m', type=str, default=UPLOAD_MODE,
                        choices=['websocket', 'http_batch', 'both'],
                        help=f'上报模式 (默认: {UPLOAD_MODE})')
    parser.add_argument('--device-id', type=str, default=DEVICE_ID,
                        help=f'设备标识 (默认: {DEVICE_ID})')
    parser.add_argument('--list-ports', '-l', action='store_true',
                        help='列出所有可用串口并退出')
    return parser.parse_args()


# ==================== 主循环 ====================

def main():
    args = parse_args()

    # 列出所有可用串口然后退出
    if args.list_ports:
        ports = list_com_ports()
        if not ports:
            print("  未检测到任何可用串口。")
            print("  请检查 EMG 臂带是否已连接，驱动是否已安装。")
        else:
            print(f"\n  检测到 {len(ports)} 个可用串口:\n")
            print(f"  {'端口':<10} {'描述':<40} {'硬件ID'}")
            print(f"  {'─'*10} {'─'*40} {'─'*30}")
            for p in ports:
                print(f"  {p['device']:<10} {p['description']:<40} {p['hwid']}")
        print()
        return

    print("+" + "=" * 62 + "+")
    print("|" + "  Windows EMG 数据上报服务 (v1.1)  ".center(62) + "|")
    print("+" + "=" * 62 + "+")
    print()

    # 0. 检查后端连通性
    backend_url = args.backend or BACKEND_BASE_URL
    print(f"[0/3] 检查后端连通性: {backend_url} ... ", end='', flush=True)
    try:
        import requests
        # 尝试访问公开接口
        resp = requests.get(f"{backend_url}/auth/hello", timeout=3)
        if resp.status_code == 200:
            print("OK")
        else:
            print(f"警告 (HTTP {resp.status_code})")
    except Exception as e:
        print(f"失败\n  [!]无法连接后端服务器，请检查网络或 IP 配置。")
        print(f"  错误详情: {e}")
        # 不强制退出，允许仅串口调试
        # sys.exit(1)

    # 确定串口
    serial_port = args.port or os.environ.get('EMG_SERIAL_PORT')
    if not serial_port:
        log.info("未指定串口，正在自动检测...")
        serial_port = auto_detect_emg_port()
        if serial_port:
            log.info(f"自动检测到串口: {serial_port}")
        else:
            log.error("未检测到可用串口！")
            log.info("提示: 请确认 EMG 臂带已通过 USB 连接到电脑")
            log.info("      运行 python windows_emg_uploader.py --list-ports 查看可用串口")
            log.info("      或用 --port COM5 手动指定串口")
            sys.exit(1)

    # 确定后端地址
    ws_url = args.ws_url or BACKEND_WS_URL
    if args.backend and not args.ws_url:
        # 如果只指定了 HTTP 地址，自动推导 WebSocket 地址
        clean_url = backend_url.replace('http://', '').replace('https://', '').rstrip('/')
        prefix = 'wss://' if backend_url.startswith('https') else 'ws://'
        ws_url = f"{prefix}{clean_url}/ws/emg"

    upload_mode = args.mode
    device_id = args.device_id

    print()
    print(f"  串口:       {serial_port} @ {args.baudrate}")
    print(f"  后端地址:   {backend_url}")
    print(f"  WebSocket:  {ws_url}")
    print(f"  上报模式:   {upload_mode}")
    print(f"  设备ID:     {device_id}")
    print()

    # 显示所有可用串口供参考
    ports = list_com_ports()
    if ports:
        print(f"  当前系统可用串口: {', '.join(p['device'] for p in ports)}")
        print()

    # 1. 连接串口
    log.info("[1/3] 连接 EMG 串口...")
    reader = SerialReader(serial_port, args.baudrate)
    try:
        reader.connect()
    except Exception as e:
        log.error(f"串口连接失败: {e}")
        log.info("可能的原因:")
        log.info(f"  1. 串口 {serial_port} 不存在或被占用（关闭串口助手等程序）")
        log.info("  2. EMG 臂带未连接/未上电")
        log.info("  3. USB 转串口驱动未安装（CH340/CP210x）")
        log.info(f"  4. 串口名称错误，运行 --list-ports 查看可用串口")
        sys.exit(1)

    # 2. 初始化上报通道
    ws_uploader = None
    http_uploader = None

    if upload_mode in ('websocket', 'both'):
        log.info("[2/3] 初始化 WebSocket 通道...")
        ws_uploader = WebSocketUploader(ws_url, device_id)
        ws_uploader.connect()
        time.sleep(1)  # 等待连接建立

    if upload_mode in ('http_batch', 'both'):
        log.info("[2/3] 初始化 HTTP 批量通道...")
        http_uploader = HttpBatchUploader(
            backend_url, device_id,
            batch_size=HTTP_BATCH_SIZE,
            flush_interval=HTTP_BATCH_INTERVAL
        )

    log.info("[3/3] 开始采集与上报...")
    print(f"  {'─' * 50}")
    print("  按 Ctrl+C 停止\n")

    # 3. 主循环
    last_status = time.time()
    total_frames = 0

    try:
        while True:
            frames = reader.read_frames()

            for frame in frames:
                total_frames += 1

                if ws_uploader:
                    ws_uploader.send_frame(frame)

                if http_uploader:
                    http_uploader.add_frame(frame)

            # 每 5 秒打印状态
            now = time.time()
            if now - last_status >= 5:
                ws_info = f"WS发送:{ws_uploader.sent_count}" if ws_uploader else ""
                http_info = f"HTTP发送:{http_uploader.sent_count}" if http_uploader else ""
                ws_status = "[已连接]" if (ws_uploader and ws_uploader.is_connected) else "[未连接]"
                log.info(f"采集帧数:{total_frames} | {ws_info} {http_info} | WS:{ws_status}")
                last_status = now

    except KeyboardInterrupt:
        print("\n  用户中断 (Ctrl+C)")
    finally:
        reader.close()
        log.info(f"总采集帧数: {total_frames}")
        print("\n  程序已退出。")


if __name__ == '__main__':
    main()

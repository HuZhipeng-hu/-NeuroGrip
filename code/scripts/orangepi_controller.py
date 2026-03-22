# -*- coding: utf-8 -*-
"""
OrangePi Controller for EMG Armband & Actuation
===============================================
Functionality:
1. Connect to EMG Armband to get real-time data (EMG + IMU)
2. Use EventOnset model for real-time gesture recognition
3. Map recognized gestures to actuation commands (e.g. Servo/Hand)
4. Execute actuation via PCA9685 or Standalone mock
5. Send data and recognition results to backend via WebSocket (optional)

Usage:
  python orangepi_controller.py --device_id orangepi_01 --ws_url ws://1.95.65.51:8080/ws/emg --actuator pca9685

Dependencies:
  pip install websocket-client numpy scipy pyserial smbus2
  (Optional) mindspore-lite for inference
"""

import sys
import os
import time
import json
import logging
import argparse
import threading
import traceback
import signal
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import websocket  # pip install websocket-client

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from event_onset.config import EventDataConfig, EventModelConfig
    from event_onset.actuation_mapping import load_and_validate_actuation_map
    from shared.preprocessing.stft import PreprocessPipeline
    from shared.config import HardwareConfig
    from runtime.hardware.factory import create_actuator
    from scripts import emg_armband
    # Try importing inference module
    from event_onset.inference import EventPredictor
    MS_LITE_AVAILABLE = True
except ImportError as e:
    print(f"Import failed: {e}")
    print(f"Please ensure you are running from {project_root} or have set the correct PYTHONPATH")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("OrangePiController")


class NumpyEncoder(json.JSONEncoder):
    """JSON Encoder for Numpy types"""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)


class OrangePiController(emg_armband.DeviceListener):
    def __init__(self, args):
        self.args = args
        self.device_id = args.device_id
        self.ws_url = args.ws_url
        self.ws = None
        self.ws_open = False
        self.running = True
        
        # Statistics
        self.frame_count = 0
        self.last_send_time = 0
        
        # Data Config
        self.data_config = EventDataConfig()
        self.feature_config = self.data_config.feature
        
        # Buffer (EMG 500Hz, IMU 50Hz)
        self.window_size = self.feature_config.context_samples(self.data_config.device_sampling_rate_hz)
        self.emg_buffer = deque(maxlen=self.window_size)
        self.imu_buffer = deque(maxlen=30) 
        
        # Inference timing
        self.last_inference_time = 0
        self.inference_interval = 0.02 # 20ms (50Hz)
        
        # Initialize Pipeline
        self._init_pipeline()
        
        # Initialize Actuator
        self._init_actuator()

        # Start WebSocket thread
        if self.ws_url:
            self.ws_thread = threading.Thread(target=self._ws_loop, daemon=True)
            self.ws_thread.start()
        else:
            logger.info("WebSocket URL not provided, running in offline mode.")

    def _init_pipeline(self):
        """Initialize Preprocessing and Inference Model"""
        # 1. Preprocessor
        preprocess_cfg = {
            "sampling_rate": self.data_config.device_sampling_rate_hz,
            "num_channels": 8,
            "stft_window": self.feature_config.emg_stft_window,
            "stft_hop": self.feature_config.emg_stft_hop,
            "n_fft": self.feature_config.emg_n_fft,
            "freq_bins_out": self.feature_config.emg_freq_bins,
            "normalize": "log",
            "device_sampling_rate": self.data_config.device_sampling_rate_hz,
            "target_length": self.window_size  # Ensure pipeline expects full window
        }
        
        try:
            self.pipeline = PreprocessPipeline(config=preprocess_cfg)
            logger.info("Preprocessing pipeline initialized successfully")
        except Exception as e:
            logger.error(f"Preprocessing pipeline failed to initialize: {e}")
            self.pipeline = None

        # 2. Inference Engine
        self.predictor = None
        if MS_LITE_AVAILABLE and self.pipeline:
            try:
                model_config = EventModelConfig()
                model_path = self.args.model_path
                if not os.path.exists(model_path):
                    default_path = os.path.join(project_root, "models", "event_onset_scr22.mindir")
                    if os.path.exists(default_path):
                        model_path = default_path
                    else:
                        logger.warning(f"Model file not found: {model_path}, inference disabled")
                        return

                logger.info(f"Loading model: {model_path}")
                self.predictor = EventPredictor(
                    backend="lite",
                    model_config=model_config,
                    model_path=model_path,
                    device_target="NPU"
                )
                logger.info("Inference engine initialized successfully")
                
                # Load metadata to get class names
                metadata_path = str(model_path).replace(".mindir", ".model_metadata.json")
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        meta = json.load(f)
                        self.class_names = meta.get("class_names", [])
                        logger.info(f"Loaded class names: {self.class_names}")
                else:
                    self.class_names = ["RELAX", "TENSE_OPEN", "V_SIGN", "OK_SIGN", "THUMB_UP", "WRIST_CW", "WRIST_CCW"]
                    logger.warning(f"Metadata not found, using default class names: {self.class_names}")
                    
            except Exception as e:
                logger.error(f"Inference engine failed to initialize: {e}")
                traceback.print_exc()

    def _init_actuator(self):
        """Initialize Actuator"""
        # Load mapping
        try:
            mapping_path = os.path.join(project_root, "configs", "event_actuation_mapping.yaml")
            self.label_to_gesture, _ = load_and_validate_actuation_map(
                mapping_path, 
                class_names=self.class_names
            )
            logger.info(f"Actuation mapping loaded.")
        except Exception as e:
            logger.error(f"Failed to load actuation mapping: {e}")
            self.label_to_gesture = {}

        # Create Actuator
        try:
            hw_config = HardwareConfig(actuator_mode=self.args.actuator)
            self.actuator = create_actuator(hw_config)
            if hasattr(self.actuator, 'connect'):
                self.actuator.connect()
            logger.info(f"Actuator initialized: {self.args.actuator}")
        except Exception as e:
            logger.error(f"Failed to initialize actuator: {e}")
            self.actuator = None

    # ================= WebSocket =================

    def _ws_loop(self):
        while self.running:
            try:
                logger.info(f"Connecting to backend: {self.ws_url}")
                self.ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self._on_ws_open,
                    on_error=self._on_ws_error,
                    on_close=self._on_ws_close
                )
                self.ws.run_forever(ping_interval=10, ping_timeout=5)
            except Exception as e:
                logger.error(f"WebSocket exception: {e}")
            
            if self.running:
                time.sleep(5)

    def _on_ws_open(self, ws):
        logger.info("WebSocket connected")
        self.ws_open = True
        register_msg = {
            "type": "register",
            "deviceId": self.device_id,
            "timestamp": int(time.time() * 1000)
        }
        self._send_json(register_msg)

    def _on_ws_error(self, ws, error):
        logger.error(f"WebSocket error: {error}")

    def _on_ws_close(self, ws, status, msg):
        logger.info(f"WebSocket closed: {status} {msg}")
        self.ws_open = False

    def _send_json(self, data):
        if self.ws and self.ws_open:
            try:
                self.ws.send(json.dumps(data, cls=NumpyEncoder))
            except Exception as e:
                logger.error(f"Send failed: {e}")
                self.ws_open = False

    # ================= Data Processing =================

    def on_frame(self, event: emg_armband.FrameEvent):
        """Called every frame (10ms-20ms)"""
        self.frame_count += 1
        current_time = time.time()
        
        # 1. Buffer Data
        emg_pack = event.emg_event.emg
        for sample in emg_pack:
            self.emg_buffer.append(sample)
            
        imu_ev = event.imu_event
        self.imu_buffer.append(imu_ev)

        # 2. Inference & Actuation
        gesture_result = "unknown"
        confidence_result = 0.0

        if self.predictor and len(self.emg_buffer) >= self.window_size:
            if current_time - self.last_inference_time >= self.inference_interval:
                try:
                    gesture_result, confidence_result, label_idx = self._run_inference()
                    self.last_inference_time = current_time
                    
                    # Actuation
                    if self.actuator and label_idx is not None:
                        if label_idx in self.label_to_gesture:
                            target_gesture = self.label_to_gesture[label_idx]
                            self.actuator.execute_gesture(target_gesture)
                        
                except Exception as e:
                    logger.error(f"Inference/Actuation error: {e}")
                    traceback.print_exc()

        # 3. Send Data (Optional)
        if self.ws_url:
            payload = {
                "type": "emg_frame",
                "deviceId": self.device_id,
                "data": {
                    "device_ts": event.timestamp,
                    "serverTime": datetime.now().isoformat(),
                    "emg": emg_pack,
                    "acc": imu_ev.acceleration.to_list(),
                    "gyro": imu_ev.gyroscope.to_list(),
                    "angle": imu_ev.orientation.to_list(),
                    "battery": event.battery_event.level,
                    "gesture": gesture_result,
                    "confidence": confidence_result
                }
            }
            self._send_json(payload)
        
        if self.frame_count % 100 == 0:
            logger.info(f"Processed {self.frame_count} frames | Gesture: {gesture_result} ({confidence_result:.2f})")

    def _run_inference(self):
        """Run single inference"""
        emg_data = np.array(list(self.emg_buffer), dtype=np.float32)
        spec = self.pipeline.process(emg_data)
        spec_input = spec[np.newaxis, ...]
        
        imu_seq = []
        needed = 16
        available = len(self.imu_buffer)
        for i in range(needed):
            idx = available - needed + i
            if idx >= 0:
                ev = self.imu_buffer[idx]
                vec = ev.acceleration.to_list() + ev.gyroscope.to_list()
                imu_seq.append(vec)
            else:
                imu_seq.append([0.0]*6)
                
        imu_input = np.array(imu_seq, dtype=np.float32).T 
        imu_input = imu_input[np.newaxis, ...] 
        
        detail = self.predictor.predict_detail(spec_input, imu_input)
        probs = detail.public_probs
        if probs.ndim == 2:
            probs = probs[0]
            
        label = np.argmax(probs)
        confidence = float(probs[label])
        
        gesture_name = self.class_names[label] if label < len(self.class_names) else f"Class_{label}"
        
        return gesture_name, confidence, label

    def stop(self):
        self.running = False
        if self.ws:
            self.ws.close()
        if self.actuator and hasattr(self.actuator, 'disconnect'):
            self.actuator.disconnect()


def main():
    parser = argparse.ArgumentParser(description="OrangePi Controller")
    parser.add_argument("--device_id", type=str, default="orangepi_01", help="Device ID")
    parser.add_argument("--ws_url", type=str, default="ws://1.95.65.51:8080/ws/emg", help="WebSocket URL (optional)")
    parser.add_argument("--port", type=str, default="/dev/ttyUSB0", help="Serial Port (e.g. )")
    parser.add_argument("--model_path", type=str, default="../models/event_onset_scr22.mindir", help="Model Path")
    parser.add_argument("--actuator", type=str, default="standalone", choices=["pca9685", "standalone"], help="Actuator Mode")
    
    args = parser.parse_args()
    
    logger.info(f"Starting OrangePi Controller - Device: {args.device_id}")
    
    try:
        # Assuming emg_armband.Hub is available
        hub = emg_armband.Hub(port=args.port)
        
        controller = OrangePiController(args)
        
        # 使用列表来存储停止状态，因为 bool 在闭包中不能直接修改（除非 python 3 nonlocal）
        stop_state = {"is_stopping": False}
        
        def signal_handler(sig, frame):
            if stop_state["is_stopping"]:
                logger.warning("检测到重复信号，强制退出！")
                os._exit(1)
            
            stop_state["is_stopping"] = True
            logger.info("正在停止... (如卡住请再次按下 Ctrl+C 强制退出)")
            
            # 启动一个守护线程，3秒后强制退出，防止 cleanup 卡死
            def force_kill():
                time.sleep(3)
                logger.warning("清理超时，强制退出")
                os._exit(0)
            
            t = threading.Thread(target=force_kill, daemon=True)
            t.start()

            try:
                controller.stop()
                hub.stop()
            except Exception as e:
                logger.error(f"停止时出错: {e}")
            finally:
                logger.info("退出完成")
                os._exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        logger.info("Starting collection loop...")
        hub.run(listener=controller)
        
    except Exception as e:
        logger.error(f"Runtime error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()

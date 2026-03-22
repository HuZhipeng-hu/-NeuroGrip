# -*- coding: utf-8 -*-
"""
OrangePi Client for EMG Armband
================================
功能：
1. 连接 EMG 臂环获取实时数据 (EMG + IMU)
2. 使用 EventOnset 模型进行实时手势识别
3. 通过 WebSocket 将数据和识别结果发送到后端

用法：
  python orangepi_client.py --device_id orangepi_01 --ws_url ws://1.95.65.51:8080/ws/emg

依赖：
  pip install websocket-client numpy scipy pyserial
  (可选) mindspore-lite 用于推理
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

import numpy as np
import websocket  # pip install websocket-client

# 添加项目根目录到路径，以便导入 event_onset 和 shared 模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from event_onset.config import EventDataConfig, EventModelConfig, EventInferenceConfig
    from shared.preprocessing.stft import PreprocessPipeline
    from scripts import emg_armband
except ImportError as e:
    print(f"导入模块失败: {e}")
    print(f"请确保在 {project_root} 目录下运行或设置正确的 PYTHONPATH")
    sys.exit(1)

# 尝试导入推理模块
try:
    from event_onset.inference import EventPredictor
    MS_LITE_AVAILABLE = True
except ImportError:
    MS_LITE_AVAILABLE = False
    print("警告: 未检测到 mindspore/mindspore_lite，将仅传输原始数据，不进行推理。")


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("OrangePiClient")


class NumpyEncoder(json.JSONEncoder):
    """处理 Numpy 类型的 JSON 编码器"""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)


class OrangePiClient(emg_armband.DeviceListener):
    def __init__(self, args):
        self.args = args
        self.device_id = args.device_id
        self.ws_url = args.ws_url
        self.ws = None
        self.ws_open = False
        self.running = True
        
        # 统计
        self.frame_count = 0
        self.last_send_time = 0
        
        # 数据配置
        self.data_config = EventDataConfig()
        self.feature_config = self.data_config.feature
        
        # 缓冲区 (EMG 500Hz, IMU 50Hz)
        # 窗口大小 240ms -> 120 samples @ 500Hz
        self.window_size = self.feature_config.context_samples(self.data_config.device_sampling_rate_hz)
        self.emg_buffer = deque(maxlen=self.window_size)
        self.imu_buffer = deque(maxlen=30) # 存少量 IMU 数据用于采样
        
        # 上一次推理时间
        self.last_inference_time = 0
        self.inference_interval = 0.02 # 20ms 推理一次 (50Hz)
        
        # 初始化处理流水线
        self._init_pipeline()
        
        # 启动 WebSocket 线程
        self.ws_thread = threading.Thread(target=self._ws_loop, daemon=True)
        self.ws_thread.start()

    def _init_pipeline(self):
        """初始化预处理和推理模型"""
        # 1. 预处理器配置
        preprocess_cfg = {
            "sampling_rate": self.data_config.device_sampling_rate_hz, # 500Hz
            "num_channels": 8,
            "stft_window": self.feature_config.emg_stft_window,
            "stft_hop": self.feature_config.emg_stft_hop,
            "n_fft": self.feature_config.emg_n_fft,
            "freq_bins_out": self.feature_config.emg_freq_bins,
            "normalize": "log",
            "device_sampling_rate": self.data_config.device_sampling_rate_hz
        }
        
        try:
            self.pipeline = PreprocessPipeline(config=preprocess_cfg)
            logger.info("预处理流水线初始化成功")
        except Exception as e:
            logger.error(f"预处理流水线初始化失败: {e}")
            self.pipeline = None

        # 2. 推理引擎配置
        self.predictor = None
        if MS_LITE_AVAILABLE and self.pipeline:
            try:
                model_config = EventModelConfig()
                # 查找模型文件
                model_path = self.args.model_path
                if not os.path.exists(model_path):
                    # 尝试在默认路径查找
                    default_path = os.path.join(project_root, "models", "event_onset_scr22.mindir")
                    if os.path.exists(default_path):
                        model_path = default_path
                    else:
                        logger.warning(f"模型文件未找到: {model_path}，将禁用推理")
                        return

                logger.info(f"加载模型: {model_path}")
                self.predictor = EventPredictor(
                    backend="lite", # 默认使用 MindSpore Lite
                    model_config=model_config,
                    model_path=model_path,
                    device_target="CPU"
                )
                logger.info("推理引擎初始化成功")
            except Exception as e:
                logger.error(f"推理引擎初始化失败: {e}")
                traceback.print_exc()

    # ================= WebSocket 处理 =================

    def _ws_loop(self):
        """WebSocket 连接维护循环"""
        while self.running:
            try:
                logger.info(f"正在连接到后端: {self.ws_url}")
                self.ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self._on_ws_open,
                    on_error=self._on_ws_error,
                    on_close=self._on_ws_close
                )
                self.ws.run_forever(ping_interval=10, ping_timeout=5)
            except Exception as e:
                logger.error(f"WebSocket 连接异常: {e}")
            
            if self.running:
                logger.info("5秒后重连...")
                time.sleep(5)

    def _on_ws_open(self, ws):
        logger.info("WebSocket 连接已建立")
        self.ws_open = True
        # 发送注册消息
        register_msg = {
            "type": "register",
            "deviceId": self.device_id,
            "timestamp": int(time.time() * 1000)
        }
        self._send_json(register_msg)

    def _on_ws_error(self, ws, error):
        logger.error(f"WebSocket 错误: {error}")

    def _on_ws_close(self, ws, status, msg):
        logger.info(f"WebSocket 连接断开: {status} {msg}")
        self.ws_open = False

    def _send_json(self, data):
        """发送 JSON 数据"""
        if self.ws and self.ws_open:
            try:
                self.ws.send(json.dumps(data, cls=NumpyEncoder))
            except Exception as e:
                logger.error(f"发送失败: {e}")
                self.ws_open = False

    # ================= 数据处理 =================

    def on_frame(self, event: emg_armband.FrameEvent):
        """每收到一帧原始数据回调 (10ms-20ms 一次)"""
        self.frame_count += 1
        current_time = time.time()
        
        # 1. 存入缓冲区
        # emg_armband 返回的是 10x8 的数据 List[List[int]]
        emg_pack = event.emg_event.emg
        for sample in emg_pack:
            self.emg_buffer.append(sample)
            
        # IMU 数据
        imu_ev = event.imu_event
        self.imu_buffer.append(imu_ev)

        # 2. 推理 (限制频率，例如 20ms 一次)
        gesture_result = "unknown"
        confidence_result = 0.0

        if self.predictor and len(self.emg_buffer) >= self.window_size:
            if current_time - self.last_inference_time >= self.inference_interval:
                try:
                    gesture_result, confidence_result = self._run_inference()
                    self.last_inference_time = current_time
                except Exception as e:
                    logger.error(f"推理出错: {e}")

        # 3. 构造发送数据
        # 我们每帧都发送原始数据给后端用于可视化，同时附带最新的推理结果
        payload = {
            "type": "emg_frame",
            "deviceId": self.device_id,
            "data": {
                "device_ts": event.timestamp,
                "serverTime": datetime.now().isoformat(),
                "emg": emg_pack,  # 原始 10x8 数据
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
            logger.info(f"已处理 {self.frame_count} 帧 | 最新手势: {gesture_result} ({confidence_result:.2f})")

    def _run_inference(self):
        """执行一次推理"""
        # 准备 EMG 数据 (Buffer -> Numpy)
        # Shape: (120, 8)
        emg_data = np.array(list(self.emg_buffer), dtype=np.float32)
        
        # 预处理 -> STFT Spectrogram
        # spec shape: (8, freq_bins, time_frames)
        spec = self.pipeline.process(emg_data)
        
        # 扩展 batch 维 -> (1, 8, F, T)
        spec_input = spec[np.newaxis, ...]
        
        # 准备 IMU 数据 (取buffer平均或最新)
        # 模型需要 (1, 6, 16) - 6维(acc+gyro), 16时间步
        # 这里简化：取最近 16 个点，不足则补零
        imu_seq = []
        needed = 16
        available = len(self.imu_buffer)
        
        for i in range(needed):
            idx = available - needed + i
            if idx >= 0:
                ev = self.imu_buffer[idx]
                # 6维向量: acc.x, acc.y, acc.z, gyro.x, gyro.y, gyro.z
                # 注意单位归一化，这里先传原始值，模型可能需要归一化
                vec = ev.acceleration.to_list() + ev.gyroscope.to_list()
                imu_seq.append(vec)
            else:
                imu_seq.append([0.0]*6)
                
        imu_input = np.array(imu_seq, dtype=np.float32).T # (6, 16)
        imu_input = imu_input[np.newaxis, ...] # (1, 6, 16)
        
        # 执行预测
        # detail: EventPredictionDetail
        # 使用 EventPredictor.predict_detail 统一处理 lite/ckpt 推理细节
        try:
            detail = self.predictor.predict_detail(spec_input, imu_input)
        except Exception as e:
            logger.error(f"推理内部错误: {e}")
            return "error", 0.0
            
        # 解析结果 (假设单阶段模型)
        # EventPredictor.predict_detail 通常返回 1D 概率分布 (7,)
        probs = detail.public_probs
        if probs.ndim == 2:
            probs = probs[0]
            
        label = np.argmax(probs)
        confidence = float(probs[label])
        
        # 映射 label 到 class name
        # 这里硬编码或从 metadata 获取
        class_names = ["RELAX", "TENSE_OPEN", "V_SIGN", "OK_SIGN", "THUMB_UP", "WRIST_CW", "WRIST_CCW"]
        gesture_name = class_names[label] if label < len(class_names) else f"Class_{label}"
        
        return gesture_name, confidence

    def stop(self):
        self.running = False
        if self.ws:
            self.ws.close()


def main():
    parser = argparse.ArgumentParser(description="OrangePi EMG Client")
    parser.add_argument("--device_id", type=str, default="orangepi_01", help="设备ID")
    parser.add_argument("--ws_url", type=str, default="ws://1.95.65.51:8080/ws/emg", help="WebSocket URL")
    parser.add_argument("--port", type=str, default="COM4", help="串口号 (Linux通常为 /dev/ttyUSB0)")
    parser.add_argument("--model_path", type=str, default="../models/event_onset_scr22.mindir", help="模型路径")
    
    args = parser.parse_args()
    
    logger.info(f"启动 OrangePi 客户端 - 设备ID: {args.device_id}")
    logger.info(f"串口: {args.port}")
    
    # 实例化 Hub
    # 如果没有真实设备，emg_armband 可能会报错，这里假设已有设备或模拟器
    try:
        hub = emg_armband.Hub(port=args.port)
        
        client = OrangePiClient(args)
        
        # 注册信号处理 (Ctrl+C)
        def signal_handler(sig, frame):
            logger.info("正在停止...")
            try:
                client.stop()
                hub.stop()
            except Exception as e:
                logger.error(f"停止时出错: {e}")
            finally:
                logger.info("强制退出")
                os._exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        # 运行 Hub (阻塞调用)
        logger.info("开始采集数据...")
        hub.run(listener=client)
        
    except Exception as e:
        logger.error(f"运行时错误: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()

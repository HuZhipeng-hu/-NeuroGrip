# 硬件连接与系统部署实施指南

## 📋 目录

- [系统架构总览](#系统架构总览)
- [硬件组件清单](#硬件组件清单)
- [连接拓扑](#连接拓扑)
- [串口连接详解](#串口连接详解)
- [逐步部署指南](#逐步部署指南)
- [网络配置](#网络配置)
- [数据流验证](#数据流验证)
- [故障排除](#故障排除)
- [性能优化建议](#性能优化建议)

---

## 🏗️ 系统架构总览

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                 华为 ICT EMG 手势识别系统全架构                      │
└─────────────────────────────────────────────────────────────────────┘

        ╔══════════════╗
        ║  EMG 臂带    ║  8通道肌电传感器
        ║  (1000Hz)    ║  采样率: 1000Hz
        ╚══════╤═══════╝  通道数: 8
               │
               │ RS-232 串口
               │ 波特率: 115200
               │ 数据位: 8
               │ 停止位: 1
               │ 校验: None
               │
    ┌──────────┴────────────┬────────────────────┐
    │                       │                    │
    ▼                       ▼                    ▼
╔═══════════╗        ╔═══════════╗       ╔═══════════╗
║ OrangePi  ║        ║ Windows   ║       ║   Linux   ║
║   5B      ║        ║    PC     ║       ║    PC     ║
║ (生产环境) ║        ║ (开发测试) ║       ║ (可选)    ║
╚═════╤═════╝        ╚═════╤═════╝       ╚═════╤═════╝
      │                    │                    │
      │ /dev/ttyUSB0       │ COM3/COM4          │ /dev/ttyUSB0
      │                    │                    │
      ├────────────────────┴────────────────────┘
      │
      │ WebSocket / HTTP
      │ 目标: 1.95.65.51:8080
      │
      ▼
╔═════════════════════════════════════════╗
║      华为云 ECS (Spring Boot)           ║
║      IP: 1.95.65.51                     ║
║      - WebSocket /ws/emg (设备上报)     ║
║      - WebSocket /ws/app (App订阅)      ║
║      - HTTP REST API                    ║
╚═══════════════╤═════════════════════════╝
                │
                ├──────────┬──────────────┐
                │          │              │
                ▼          ▼              ▼
        ┌───────────┐  ┌──────────┐  ┌─────────────┐
        │  华为云   │  │ 数据持久 │  │  HarmonyOS  │
        │   RDS     │  │    化    │  │     App     │
        │  MySQL    │  │          │  │ (监控展示)  │
        └───────────┘  └──────────┘  └─────────────┘
```

---

## 📦 硬件组件清单

### 1. 核心硬件

| 组件 | 型号/规格 | 数量 | 用途 | 备注 |
|------|----------|------|------|------|
| **EMG 臂带** | 8通道采集器 | 1 | 肌电信号采集 | 采样率 1000Hz |
| **OrangePi 5B** | RK3588, 8GB RAM | 1 | 边缘数据采集器 | 生产环境主设备 |
| **USB 转串口线** | CH340/CP2102/FTDI | 1-2 | 串口连接 | 用于 OrangePi 或 PC |
| **Windows PC** | - | 1 | 开发测试 | 可选，用于调试 |
| **华为云 ECS** | 2核4GB, Ubuntu 22.04 | 1 | 云端服务器 | IP: 1.95.65.51 |
| **华为云 RDS** | MySQL 8.0 | 1 | 数据库 | IP: 1.94.234.114 |

### 2. 软件依赖

#### OrangePi 5B (OpenEuler 24.03 LTS)
```bash
# 系统更新
sudo yum update -y

# Python 3环境
sudo yum install python3 python3-pip -y

# 核心依赖
pip3 install pyserial numpy requests websocket-client
```

#### Windows PC (开发测试)
```powershell
# Python 3.8+
pip install pyserial numpy requests websocket-client matplotlib
```

#### 华为云 ECS
```bash
# JDK 11 (Spring Boot 后端)
sudo apt install openjdk-11-jdk -y

# MySQL 客户端
sudo apt install mysql-client -y
```

### 3. 网络要求

| 连接 | 源 | 目标 | 协议 | 端口 | 说明 |
|------|------|------|------|------|------|
| 设备上报 | OrangePi | ECS | WebSocket | 8080 | 实时数据流 |
| 设备上报 | OrangePi | ECS | HTTP | 8080 | 批量数据备用 |
| App 订阅 | HarmonyOS | ECS | WebSocket | 8080 | 实时波形展示 |
| 数据存储 | ECS | RDS | MySQL | 3306 | 数据持久化 |
| SSH 管理 | 管理员 | OrangePi | SSH | 22 | 远程管理 |
| SSH 管理 | 管理员 | ECS | SSH | 22 | 服务器管理 |

---

## 🔌 串口连接详解

### 1. EMG 臂带硬件接口

#### 物理接口
- **接口类型**: USB Type-A（通过 USB转串口芯片）
- **支持的串口芯片**: 
  - CH340 / CH341 (常见，免驱或官方驱动)
  - CP2102 / CP2104 (Silicon Labs)
  - FTDI FT232 (稳定性最佳)
- **电源**: USB 5V 供电，功耗 < 500mA

#### 电气参数
- **波特率**: 115200 bps（固定）
- **数据位**: 8
- **停止位**: 1
- **校验**: None (无校验)
- **流控**: 无硬件流控

#### 数据帧协议
```
┌────────────────────────────────────────────────────────────┐
│                    EMG 数据帧结构                          │
├────────────────────────────────────────────────────────────┤
│ 帧头(2B)  │ 长度(1B)  │ 载荷(NB)  │ 校验(可选) │ 帧尾(1B) │
│  AA AA    │   [LEN]   │ [Payload] │    -      │    55    │
└────────────────────────────────────────────────────────────┘

载荷结构 (共 93 字节):
  ├─ 时间戳     : 4 字节 (uint32, 大端序)
  ├─ 加速度     : 3 字节 (int8 × 3, x/y/z)
  ├─ 陀螺仪     : 3 字节 (int8 × 3, x/y/z)
  ├─ 欧拉角     : 3 字节 (int8 × 3, pitch/roll/yaw)
  ├─ EMG 数据   : 80 字节 (10包 × 8通道, uint8)
  │   ├─ Pack 1: [ch0, ch1, ch2, ch3, ch4, ch5, ch6, ch7]
  │   ├─ Pack 2: [ch0, ch1, ch2, ch3, ch4, ch5, ch6, ch7]
  │   │   ...
  │   └─ Pack10: [ch0, ch1, ch2, ch3, ch4, ch5, ch6, ch7]
  └─ 电池电量   : 1 字节 (uint8, 0-100%)

总帧长: 2 + 1 + 93 + 1 = 97 字节
```

#### 数据速率
- **帧率**: 约 100 帧/秒
- **每帧时长**: 10ms
- **每帧 EMG 采样**: 10 个时间点 × 8 通道 = 80 个数据点
- **等效采样率**: 100帧/秒 × 10点/帧 = 1000Hz

---

### 2. Windows 连接配置

#### 2.1 驱动安装

**CH340/CH341 驱动**:
1. 下载驱动: http://www.wch.cn/downloads/CH341SER_EXE.html
2. 运行安装程序
3. 重启计算机（可能需要）

**CP2102 驱动**:
1. 下载驱动: https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers
2. 运行安装程序

**FTDI 驱动**:
- Windows 10/11 自动识别，无需额外安装

#### 2.2 查看串口号

**方法一：设备管理器**
1. 按 `Win + X`，选择"设备管理器"
2. 展开"端口 (COM 和 LPT)"
3. 找到"USB-SERIAL CH340 (COMx)" 或类似设备
4. 记录端口号（如 COM3、COM4）

**方法二：使用脚本**
```bash
# 使用项目提供的脚本
python windows_emg_uploader.py --list-ports
```

输出示例:
```
  检测到 2 个可用串口:

  端口       描述                                      硬件ID
  ────────── ──────────────────────────────────────── ──────────────────
  COM3       USB-SERIAL CH340 (COM3)                  USB\VID_1A86&PID_7523
  COM5       USB Serial Port (COM5)                   USB\VID_10C4&PID_EA60
```

#### 2.3 测试连接

```bash
# 1. 基础连接测试
python -c "import serial; s=serial.Serial('COM3', 115200); print('连接成功'); s.close()"

# 2. 使用 SDK 测试
python emg_example.py

# 3. 上报测试（连接到云端）
python windows_emg_uploader.py --port COM3
```

---

### 3. OrangePi 连接配置

#### 3.1 硬件连接

1. **USB 转串口线连接**:
   ```
   EMG 臂带 (USB-A) ──── USB 转串口线 ──── OrangePi USB 口
   ```

2. **查看串口设备**:
   ```bash
   # 列出所有串口设备
   ls /dev/ttyUSB* /dev/ttyACM*
   
   # 查看设备详细信息
   dmesg | grep tty
   
   # 查看 USB 设备
   lsusb
   ```

   典型输出:
   ```
   /dev/ttyUSB0    # CH340/CH341 或 FTDI
   /dev/ttyACM0    # CP2102 或某些 CDC 设备
   ```

#### 3.2 权限设置

```bash
# 将当前用户添加到 dialout 组（获取串口权限）
sudo usermod -a -G dialout $USER

# 临时授权（调试用）
sudo chmod 666 /dev/ttyUSB0

# 永久性规则（推荐）
echo 'KERNEL=="ttyUSB[0-9]*", MODE="0666"' | sudo tee /etc/udev/rules.d/50-emg-serial.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

#### 3.3 测试连接

```bash
# 1. 使用 minicom 工具测试（可选）
sudo yum install minicom -y
sudo minicom -D /dev/ttyUSB0 -b 115200

# 2. Python 测试
python3 -c "import serial; s=serial.Serial('/dev/ttyUSB0', 115200); print('连接成功'); s.close()"

# 3. 完整测试（上报到云端）
python3 orangepi_emg_uploader.py
```

---

## 📝 逐步部署指南

### 阶段一：本地开发环境搭建（Windows）

#### Step 1: 安装 Python 环境
```powershell
# 安装 Python 3.8+ (从 python.org 下载)
python --version  # 验证

# 安装依赖
cd "E:\桌面\HUAWEI ICT"
pip install pyserial numpy matplotlib requests websocket-client
```

#### Step 2: 连接 EMG 臂带
```powershell
# 1. 插入 USB 转串口线到 PC
# 2. 安装驱动（如需要）
# 3. 查看串口号
python windows_emg_uploader.py --list-ports

# 4. 测试数据采集
python emg_example.py
# 按提示选择 "1 - DeviceListener 回调模式"
```

#### Step 3: 本地可视化测试
```powershell
# 3D 实时波形查看
python emg_3d_viewer.py

# 按 Ctrl+C 停止
```

#### Step 4: 数据采集（可选）
```powershell
# 采集手势数据用于训练
python emg_to_csv.py --gesture fist --duration 60

# 数据保存到 emg_data.csv
```

---

### 阶段二：云端服务部署（华为云 ECS）

#### Step 1: 连接服务器
```bash
# SSH 连接（从本地电脑）
ssh ubuntu@1.95.65.51
```

#### Step 2: 部署 Spring Boot 后端

**方式一：直接运行 JAR**
```bash
# 上传 jar 包
scp springboot_backend/target/emg-backend-1.0.0.jar ubuntu@1.95.65.51:~/

# 运行服务
java -jar emg-backend-1.0.0.jar

# 后台运行
nohup java -jar emg-backend-1.0.0.jar > logs/app.log 2>&1 &
```

**方式二：systemd 守护进程（推荐）**
```bash
# 创建服务文件
sudo nano /etc/systemd/system/emg-backend.service
```

内容:
```ini
[Unit]
Description=EMG Backend Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu
ExecStart=/usr/bin/java -Xms512m -Xmx1024m -jar /home/ubuntu/emg-backend-1.0.0.jar
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务:
```bash
sudo systemctl daemon-reload
sudo systemctl enable emg-backend
sudo systemctl start emg-backend
sudo systemctl status emg-backend

# 查看日志
sudo journalctl -u emg-backend -f
```

#### Step 3: 验证服务

```bash
# 1. 检查端口监听
sudo netstat -tulnp | grep 8080

# 2. 测试 REST API
curl http://localhost:8080/api/emg/latest

# 3. 测试 WebSocket（从本地）
# 使用 Python 脚本测试（见"数据流验证"章节）
```

---

### 阶段三：OrangePi 边缘部署

#### Step 1: 系统初始化

```bash
# SSH 连接 OrangePi（替换为实际 IP）
ssh orangepi@192.168.1.100

# 更新系统
sudo yum update -y

# 安装 Python 和依赖
sudo yum install python3 python3-pip git -y
pip3 install --upgrade pip
```

#### Step 2: 部署上传脚本

```bash
# 从 PC 上传文件
scp orangepi_emg_uploader.py orangepi@192.168.1.100:~/
scp emg_armband.py orangepi@192.168.1.100:~/  # 如果需要 SDK

# 或克隆整个项目
git clone https://github.com/your-org/huawei-ict-emg.git
cd huawei-ict-emg

# 安装依赖
pip3 install pyserial numpy requests websocket-client
```

#### Step 3: 配置环境变量

```bash
# 创建配置文件
nano ~/.emg_config
```

内容:
```bash
export EMG_SERIAL_PORT=/dev/ttyUSB0
export BACKEND_URL=http://1.95.65.51:8080
export BACKEND_WS_URL=ws://1.95.65.51:8080/ws/emg
```

加载配置:
```bash
source ~/.emg_config
echo "source ~/.emg_config" >> ~/.bashrc
```

#### Step 4: 测试运行

```bash
# 1. 连接 EMG 臂带到 OrangePi USB 口
# 2. 检查串口
ls /dev/ttyUSB*

# 3. 测试运行
python3 orangepi_emg_uploader.py

# 输出应包含:
# ✅ WebSocket connected: ws://1.95.65.51:8080/ws/emg
# ✅ 串口已连接: /dev/ttyUSB0 @ 115200
# ✅ 开始采集与上报...
```

#### Step 5: 设置开机自启（可选）

**方式一：systemd 服务**
```bash
sudo nano /etc/systemd/system/emg-uploader.service
```

内容:
```ini
[Unit]
Description=EMG Data Uploader
After=network.target

[Service]
Type=simple
User=orangepi
WorkingDirectory=/home/orangepi
Environment="EMG_SERIAL_PORT=/dev/ttyUSB0"
Environment="BACKEND_URL=http://1.95.65.51:8080"
ExecStart=/usr/bin/python3 /home/orangepi/orangepi_emg_uploader.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动:
```bash
sudo systemctl daemon-reload
sudo systemctl enable emg-uploader
sudo systemctl start emg-uploader
sudo systemctl status emg-uploader
```

**方式二：crontab**
```bash
crontab -e
```

添加:
```
@reboot sleep 30 && cd /home/orangepi && python3 orangepi_emg_uploader.py >> logs/uploader.log 2>&1
```

---

### 阶段四：HarmonyOS App 配置

#### Step 1: 修改后端地址

编辑 `EmgRealtimePage.ets`:
```typescript
private readonly SERVER_URL: string = 'ws://1.95.65.51:8080/ws/app';
```

#### Step 2: 配置权限

`module.json5`:
```json
{
  "requestPermissions": [
    { "name": "ohos.permission.INTERNET" }
  ]
}
```

#### Step 3: 编译安装

```bash
# 在 DevEco Studio 中
1. 连接华为手机/模拟器
2. 点击 Run 按钮
3. 等待编译完成
```

#### Step 4: 测试连接

1. 打开 App 的"实时数据"页面
2. 观察 WebSocket 连接状态
3. 确认能看到实时 EMG 波形更新

---

## 🌐 网络配置

### 1. 防火墙设置

#### 华为云 ECS 安全组

登录华为云控制台 → ECS → 安全组 → 添加入站规则:

| 协议 | 端口 | 源地址 | 说明 |
|------|------|--------|------|
| TCP | 8080 | 0.0.0.0/0 | Spring Boot HTTP/WebSocket |
| TCP | 22 | 你的IP | SSH 管理 |
| TCP | 3306 | ECS内网IP | MySQL (RDS) |

#### OrangePi 防火墙（OpenEuler）

```bash
# 关闭防火墙（开发环境）
sudo systemctl stop firewalld
sudo systemctl disable firewalld

# 或只开放必要端口（生产环境）
sudo firewall-cmd --permanent --add-port=22/tcp
sudo firewall-cmd --reload
```

### 2. 网络测试

#### 从 OrangePi 测试到 ECS

```bash
# 1. Ping 测试
ping -c 4 1.95.65.51

# 2. TCP 端口测试
nc -zv 1.95.65.51 8080

# 3. HTTP 测试
curl http://1.95.65.51:8080/api/emg/latest

# 4. WebSocket 测试（使用 Python）
python3 -c "
import websocket
ws = websocket.WebSocket()
ws.connect('ws://1.95.65.51:8080/ws/emg')
ws.send('{\"type\":\"register\",\"deviceId\":\"test\"}')
print('WebSocket 连接成功')
ws.close()
"
```

#### 从本地 PC 测试

```powershell
# Windows PowerShell
Test-NetConnection -ComputerName 1.95.65.51 -Port 8080

# 或使用 curl
curl http://1.95.65.51:8080/api/emg/latest
```

---

## ✅ 数据流验证

### 端到端测试脚本

#### 测试脚本 1: 验证串口数据采集

```python
# test_serial_connection.py
import emg_armband as emg
import time

class TestListener(emg.DeviceListener):
    def __init__(self):
        self.frame_count = 0
        self.start_time = time.time()
    
    def on_frame(self, event):
        self.frame_count += 1
        elapsed = time.time() - self.start_time
        fps = self.frame_count / elapsed
        
        if self.frame_count % 100 == 0:
            print(f"✅ 已接收 {self.frame_count} 帧 | 帧率: {fps:.1f} fps | 电池: {event.battery}%")

# 运行测试
hub = emg.Hub(port='COM3')  # 或 /dev/ttyUSB0
print("开始串口数据测试（按 Ctrl+C 停止）...")
try:
    hub.run(TestListener(), duration=10)
    print("\n✅ 串口连接正常！")
except Exception as e:
    print(f"\n❌ 串口连接失败: {e}")
```

#### 测试脚本 2: 验证云端上报

```python
# test_cloud_upload.py
import requests
import json
import time

BACKEND_URL = "http://1.95.65.51:8080"

# 1. 测试 REST API
print("1️⃣ 测试 REST API...")
try:
    resp = requests.get(f"{BACKEND_URL}/api/emg/latest", timeout=5)
    if resp.status_code == 200:
        print(f"✅ REST API 正常: {resp.json()}")
    else:
        print(f"⚠️  API 返回异常: {resp.status_code}")
except Exception as e:
    print(f"❌ REST API 失败: {e}")

# 2. 测试 WebSocket
print("\n2️⃣ 测试 WebSocket...")
try:
    import websocket
    ws = websocket.create_connection(f"ws://1.95.65.51:8080/ws/emg")
    
    # 发送注册消息
    register_msg = {"type": "register", "deviceId": "test_device"}
    ws.send(json.dumps(register_msg))
    
    # 接收响应
    response = ws.recv()
    print(f"✅ WebSocket 正常: {response}")
    ws.close()
except Exception as e:
    print(f"❌ WebSocket 失败: {e}")

print("\n✅ 云端连接测试完成！")
```

#### 测试脚本 3: 完整数据流测试

```bash
# test_full_pipeline.sh

#!/bin/bash
echo "======================================"
echo "  完整数据流测试"
echo "======================================"

# 1. 检查串口
echo "1️⃣ 检查串口设备..."
if [ -e /dev/ttyUSB0 ]; then
    echo "✅ 串口设备: /dev/ttyUSB0"
else
    echo "❌ 未找到串口设备"
    exit 1
fi

# 2. 测试云端连接
echo -e "\n2️⃣ 测试云端连接..."
ping -c 2 1.95.65.51 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ 网络连通"
else
    echo "❌ 无法连接到云端"
    exit 1
fi

# 3. 测试 Spring Boot 服务
echo -e "\n3️⃣ 测试 Spring Boot 服务..."
curl -s -o /dev/null -w "%{http_code}" http://1.95.65.51:8080/api/emg/latest
if [ $? -eq 0 ]; then
    echo "✅ Spring Boot 服务正常"
else
    echo "❌ Spring Boot 服务异常"
    exit 1
fi

# 4. 启动上传脚本（前台运行 10 秒）
echo -e "\n4️⃣ 测试数据上报（10秒）..."
timeout 10s python3 orangepi_emg_uploader.py
echo -e "\n✅ 数据流测试完成！"
```

---

## 🔧 故障排除

### 常见问题 1: 串口连接失败

#### 症状
```
串口连接失败: [Errno 2] No such file or directory: '/dev/ttyUSB0'
```

#### 解决方案

**Windows**:
```powershell
# 1. 检查设备管理器中是否有黄色感叹号
# 2. 重新安装驱动
# 3. 更换 USB 口

# 4. 使用脚本自动检测
python windows_emg_uploader.py --list-ports
```

**Linux/OrangePi**:
```bash
# 1. 检查 USB 设备
lsusb
dmesg | grep -i usb

# 2. 检查串口权限
ls -l /dev/ttyUSB*
sudo chmod 666 /dev/ttyUSB0  # 临时解决

# 3. 添加用户到 dialout 组
sudo usermod -a -G dialout $USER
# 重新登录生效

# 4. 尝试其他串口
ls /dev/tty* | grep -E "USB|ACM"
```

---

### 常见问题 2: WebSocket 连接失败

#### 症状
```
❌ WebSocket 连接失败: [WinError 10061] 由于目标计算机积极拒绝，无法连接
```

#### 解决方案

```bash
# 1. 检查 Spring Boot 服务是否运行
curl http://1.95.65.51:8080/api/emg/latest

# 2. 检查防火墙
sudo firewall-cmd --list-ports  # Linux
netsh advfirewall show allprofiles  # Windows

# 3. 检查端口占用
sudo netstat -tulnp | grep 8080  # Linux
netstat -ano | findstr 8080      # Windows

# 4. 查看 Spring Boot 日志
sudo journalctl -u emg-backend -f
# 或
tail -f /var/log/emg-backend.log
```

---

### 常见问题 3: 数据不更新

#### 症状
- WebSocket 已连接
- 但前端页面数据不更新

#### 诊断步骤

```bash
# 1. 检查设备是否正在发送数据
# 在 OrangePi 上查看上传脚本输出
sudo systemctl status emg-uploader
sudo journalctl -u emg-uploader -f

# 2. 检查 Spring Boot 是否接收到数据
# 查看后端日志，应有类似输出:
# [WS] 设备注册: orangepi_01
# [WS] 收到 EMG 帧: deviceTs=1709894400

# 3. 使用浏览器开发者工具
# F12 → Network → WS → 查看 WebSocket 消息

# 4. 测试 App WebSocket 连接
# 在 HarmonyOS App 日志中查看连接状态
```

---

### 常见问题 4: 数据丢包严重

#### 症状
- 帧率低于 50 fps
- WebSocket 频繁断开

#### 优化方案

**1. 调整 WebSocket 缓冲区**

`application.yml`:
```yaml
server:
  tomcat:
    max-connections: 200
    threads:
      max: 200

spring:
  websocket:
    message-size-limit: 8192
    send-buffer-size-limit: 512000
```

**2. 启用批量上传**

`orangepi_emg_uploader.py`:
```python
UPLOAD_MODE = 'both'  # 同时使用 WebSocket 和 HTTP
HTTP_BATCH_SIZE = 50  # 增加批量大小
```

**3. 网络优化**

```bash
# OrangePi 网络优化
sudo sysctl -w net.core.rmem_max=16777216
sudo sysctl -w net.core.wmem_max=16777216
sudo sysctl -w net.ipv4.tcp_rmem='4096 87380 16777216'
sudo sysctl -w net.ipv4.tcp_wmem='4096 87380 16777216'
```

---

### 常见问题 5: 数据库连接超时

#### 症状
```
com.mysql.cj.jdbc.exceptions.CommunicationsException: Communications link failure
```

#### 解决方案

```bash
# 1. 检查 RDS 白名单
# 华为云控制台 → RDS → 安全组 → 添加 ECS IP

# 2. 测试数据库连接
mysql -h 1.94.234.114 -u root -p ict_db

# 3. 调整连接池配置
# application.yml
spring:
  datasource:
    druid:
      max-active: 50          # 增加最大连接数
      max-wait: 10000         # 增加等待时间
      test-while-idle: true
      validation-query: SELECT 1
```

---

## ⚡ 性能优化建议

### 1. 串口数据采集优化

```python
# emg_armband.py 优化建议
class Device:
    def __init__(self, ...):
        # 增加读取缓冲区
        self._max_buffer = 20000  # 默认 10000
        
    def read_frames(self):
        # 批量读取
        bytes_to_read = self.serial.in_waiting
        if bytes_to_read > 0:
            new_data = self.serial.read(bytes_to_read)
            # ...
```

### 2. 网络传输优化

```python
# orangepi_emg_uploader.py 优化
class WebSocketUploader:
    def __init__(self, ...):
        # 启用压缩
        self.ws = websocket.WebSocket(
            enable_multithread=True,
            # 可选: 启用数据压缩
        )
```

### 3. 数据库写入优化

```java
// EmgDataService.java
@Scheduled(fixedRate = 500)  // 改为 1000 (降低写入频率)
public void flushToDatabase() {
    if (writeBuffer.size() >= 100) {  // 增加批量大小
        // 批量插入
    }
}
```

### 4. OrangePi 系统优化

```bash
# 1. 禁用不必要的服务
sudo systemctl disable bluetooth
sudo systemctl disable avahi-daemon

# 2. CPU 性能模式
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# 3. 增加串口缓冲区
sudo sh -c 'echo 4096 > /sys/class/tty/ttyUSB0/rx_buffer_size'
```

---

## 📊 性能指标参考

### 正常运行指标

| 指标 | 期望值 | 可接受范围 | 说明 |
|------|--------|-----------|------|
| 串口帧率 | 100 fps | 95-105 fps | EMG 臂带输出 |
| WebSocket 延迟 | < 50ms | < 100ms | 设备到云端 |
| 数据库写入 TPS | > 500 | 300-800 | 批量插入 |
| App 刷新率 | 20-50 fps | > 15 fps | 前端显示 |
| 丢包率 | < 0.1% | < 1% | WebSocket 丢包 |
| CPU 占用 (OrangePi) | < 15% | < 30% | Python 进程 |
| 内存占用 (OrangePi) | < 100MB | < 200MB | Python 进程 |

### 监控命令

```bash
# OrangePi 资源监控
watch -n 1 'ps aux | grep python'

# Spring Boot 性能
curl http://1.95.65.51:8080/actuator/metrics

# 数据库连接数
mysql -h 1.94.234.114 -u root -p -e "SHOW STATUS LIKE 'Threads_connected';"
```

---

## 📚 相关文档

- 📖 [Spring Boot 后端功能介绍](SPRINGBOOT_BACKEND_GUIDE.md)
- 📖 [Training 页面 WebSocket 协议](TRAINING_PAGE_GUIDE.md)
- 📖 [模型部署指南](MODEL_DEPLOYMENT_GUIDE.md)
- 📖 [系统架构设计](ARCHITECTURE_DESIGN.md)

---

## 🤝 技术支持

遇到问题？

1. 📧 **邮件**: emg-support@huawei.com
2. 💬 **GitHub Issues**: https://github.com/your-org/huawei-ict-emg/issues
3. 📞 **技术支持**: 请联系项目负责人

---

**© 2024 华为 ICT 赛道 EMG 项目组**

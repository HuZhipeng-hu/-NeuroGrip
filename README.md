# NeuroGrip - 智能仿生机械臂控制系统

本项目实现了一套基于肌电信号（sEMG）的智能手势识别与机械臂控制系统。系统采用端云协同架构，利用 KunpengPro 进行边缘端实时采集与推理，通过 WebSocket 将数据传输至 Spring Boot 后端，并由 HarmonyOS App 提供可视化交互与训练管理。

## 📁 目录结构

```
NeuroGrip/
├── app/                        # HarmonyOS 客户端源码 (ArkTS)
│   ├── entry/src/main/ets/     # 页面与组件代码
│   └── ...
├── springboot_backend/         # 后端服务源码 (Java Spring Boot)
│   ├── src/main/java/          # Controller, WebSocketHandler, Service
│   └── pom.xml                 # Maven 依赖配置
├── code/                       # 算法与边缘端代码 (Python)
│   ├── code/
│   │   ├── event_onset/        # 手势识别模型定义 (MindSpore)
│   │   ├── shared/             # 预处理与公共工具库
│   │   ├── scripts/            # 边缘端运行脚本
│   │   │   ├── KunpengPro_client.py  # [核心] KunpengPro 采集与推理客户端
│   │   │   └── emg_armband.py      # 臂环驱动库
│   │   └── requirements.txt    # 依赖说明
│   └── ...
├── data/                       # 训练数据集与日志
├── docs/                       # 项目文档与数据库脚本
├── test_websocket_app.py       # WebSocket 调试工具 (模拟 App 接收数据)
└── windows_emg_uploader.py     # Windows 端数据上传工具 (测试用)
```

## 🛠️ 系统架构

1.  **感知层 (Edge)**: KunpengPro 连接 EMG 臂环，采集 8 通道肌电信号与 IMU 数据。
2.  **推理层 (AI)**: 运行在 KunpengPro 上的 MindSpore Lite 模型，实时识别手势（如拳头、张开、点赞等）。
3.  **服务层 (Cloud)**: Spring Boot 后端，提供 WebSocket 服务 (`/ws/emg`, `/ws/app`) 实现低延迟数据转发。
4.  **应用层 (User)**: HarmonyOS App，实时展示波形、训练进度，并接收手势指令控制虚拟/实体机械臂。

---

## 🚀 快速开始 (复现指南)

### 1. 环境准备

-   **后端**: JDK 17+, Maven 3.8+
-   **前端**: DevEco Studio 5.0.5+, HarmonyOS SDK API 10
-   **边缘端**: KunpengPro (Armbian/Ubuntu), Python 3.9+, MindSpore Lite

### 2. 启动后端服务

后端负责数据的广播与转发。

1.  进入 `springboot_backend` 目录。
2.  使用 Maven 运行项目：
    ```bash
    mvn spring-boot:run
    ```
3.  服务将启动在 `0.0.0.0:8080` (默认)。
    *   WebSocket 地址: `ws://localhost:8080/ws/app` (App端), `ws://localhost:8080/ws/emg` (设备端)

### 3.启动边缘端 (KunpengPro)

连接好 USB 臂环接收器后，在 KunpengPro 上运行客户端脚本。

1.  安装依赖:
    ```bash
    cd code/scripts
    pip install -r requirements_KunpengPro.txt
    ```
2.  运行采集与推理核心脚本:
    ```bash
    # 替换 --ws_url 为实际的后端 IP 地址
    python KunpengPro_client.py --device_id pi_01 --ws_url ws://192.168.1.100:8080/ws/emg
    ```
    *此时，KunpengPro LED 应闪烁，控制台显示“WebSocket 连接成功”，并开始发送数据。*

### 4. 运行 HarmonyOS App

1.  使用 DevEco Studio 打开 `app` 目录。
2.  修改配置文件（如 `AppConstants.ets` 或相关网络配置），将 WebSocket 服务器地址指向后端 IP。
3.  连接真机或启动模拟器，点击 Run 运行。
4.  在 App “训练”页面中，应能看到实时的 EMG 波形跳动，并显示当前识别的手势。

### 5. 调试工具

如果手头没有 KunpengPro 或 HarmonyOS 设备，可以使用项目根目录下的脚本进行模拟测试：

*   **模拟 App 端接收数据**:
    ```bash
    python test_websocket_app.py
    ```
    *此脚本会连接 `/ws/app` 并在终端打印接收到的手势和电量信息。*

---

## 🧠 算法模型

*   **模型架构**: 基于 CNN/RNN 的 `EventOnset` 模型，专为低功耗边缘设别优化。
*   **输入**: 8通道 EMG (500Hz) + 6轴 IMU (50Hz)。
*   **训练**: 详见 `code/README.md`。支持使用 `trainer.py` 进行微调。

## 🐞 常见问题

1.  **WebSocket 连接失败**:
    *   请检查防火墙设置，确保 8080 端口开放。
    *   确保 KunpengPro 和 后端服务器在同一局域网，或拥有公网 IP。
2.  **App 无法显示波形**:
    *   检查 KunpengPro 脚本是否正在运行且无报错。
    *   使用 `test_websocket_app.py` 验证后端是否接收到了数据。




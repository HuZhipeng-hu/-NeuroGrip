# -*- coding: utf-8 -*-
"""
WebSocket /ws/app 客户端测试脚本
实时接收 EMG 数据并打印到控制台
"""
import asyncio
import websockets
import json
from datetime import datetime

# 配置
SERVER_URL = "ws://1.95.65.51:8080/ws/app"

class EmgWebSocketClient:
    def __init__(self, url):
        self.url = url
        self.frame_count = 0
        
    async def connect(self):
        """连接到 WebSocket 服务器"""
        print("=" * 70)
        print(f"  EMG WebSocket 客户端测试")
        print("=" * 70)
        print(f"  连接目标: {self.url}")
        print(f"  启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()
        
        try:
            async with websockets.connect(self.url) as websocket:
                print("✓ WebSocket 连接成功！")
                print("  等待接收数据...\n")
                
                # 持续接收数据
                async for message in websocket:
                    self.handle_message(message)
                    
        except websockets.exceptions.WebSocketException as e:
            print(f"\n✗ WebSocket 连接失败: {e}")
            print("\n请检查:")
            print("  1. 后端服务是否运行: systemctl status emg-backend")
            print("  2. 防火墙端口是否开放")
            print("  3. URL 地址是否正确")
            
        except KeyboardInterrupt:
            print("\n\n用户中断，正在关闭...")
            
        except Exception as e:
            print(f"\n✗ 发生错误: {e}")
    
    def handle_message(self, message):
        """处理收到的消息"""
        try:
            data = json.loads(message)
            self.frame_count += 1
            
            # 打印分隔线
            print("─" * 70)
            print(f"📊 帧 #{self.frame_count} | {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            print("─" * 70)
            
            # 基本信息
            print(f"🔌 设备ID:    {data.get('deviceId', 'N/A')}")
            print(f"⏱️  设备时间:  {data.get('deviceTs', 'N/A')} ms")
            print(f"🕐 服务器时间: {data.get('serverTime', 'N/A')}")
            
            # 手势识别
            gesture = data.get('gesture')
            confidence = data.get('confidence')
            if gesture and gesture != 'unknown':
                conf_percent = confidence * 100 if confidence else 0
                print(f"👌 手势:      {gesture} ({conf_percent:.1f}%)")
            else:
                print(f"👌 手势:      RELAX")
            
            # 电池
            battery = data.get('battery')
            if battery is not None:
                battery_icon = "🔋" if battery > 20 else "🪫"
                print(f"{battery_icon} 电池:      {battery}%")
            
            # EMG 数据（显示第1包和第10包）
            emg = data.get('emg', [])
            if emg and len(emg) >= 10:
                print(f"\n📈 EMG 数据 (10包 x 8通道):")
                print(f"   第1包:  {emg[0]}")
                print(f"   第10包: {emg[9]}")
                
                # 计算平均值
                avg_values = [sum(col) / len(col) for col in zip(*emg)]
                print(f"   平均值: {[round(v, 1) for v in avg_values]}")
            
            # IMU 数据
            acc = data.get('acc', [])
            gyro = data.get('gyro', [])
            angle = data.get('angle', [])
            
            if acc:
                print(f"\n🎯 IMU 数据:")
                print(f"   加速度: {acc} (x, y, z)")
                if gyro:
                    print(f"   陀螺仪: {gyro} (x, y, z)")
                if angle:
                    print(f"   角度:   {angle} (pitch, roll, yaw)")
            
            print()
            
        except json.JSONDecodeError:
            print(f"✗ JSON 解析失败: {message}")
        except Exception as e:
            print(f"✗ 处理消息时出错: {e}")
    
    async def request_latest(self, websocket):
        """主动请求最新数据"""
        request = json.dumps({"action": "get_latest"})
        await websocket.send(request)
        print("→ 已发送请求: get_latest")


async def main():
    """主函数"""
    client = EmgWebSocketClient(SERVER_URL)
    
    try:
        await client.connect()
    except KeyboardInterrupt:
        print("\n\n程序已退出")


if __name__ == "__main__":
    # 检查依赖
    try:
        import websockets
    except ImportError:
        print("请先安装依赖:")
        print("  pip install websockets")
        exit(1)
    
    # 运行客户端
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n程序已退出")

// ==============================================================================
// EmgRealtimePage.ets - EMG 实时数据监控页面
// ==============================================================================
// 功能: 通过 WebSocket 实时接收并展示 EMG 肌电信号数据
// 集成到华为 ICT 赛道应用
// ==============================================================================

import webSocket from '@ohos.net.webSocket';
import http from '@ohos.net.http';
import { CustomAppBar } from './CustomAppBar';
import { BottomNavBar } from './BottomNavBar';
import { BASE_URL, WS_URL } from '../common/Config';
import { EmgData, GestureEvent } from '../models/EmgData';

// ==================== 配置 ====================
const SERVER_URL: string = WS_URL;
const REST_API_BASE: string = `${BASE_URL}/api/emg`;

// ==================== EMG 服务类 ====================
export class EmgService {
  private ws: webSocket.WebSocket | null = null;
  private connected: boolean = false;
  private reconnectTimer: number = -1;

  onDataReceived: (data: EmgData) => void = () => {};
  onConnectionChanged: (connected: boolean) => void = () => {};
  onError: (error: string) => void = () => {};

  connect(): void {
    this.ws = webSocket.createWebSocket();

    this.ws.on('open', () => {
      console.info('[EMG] WebSocket 已连接');
      this.connected = true;
      this.onConnectionChanged(true);
    });

    this.ws.on('message', (err, data) => {
      if (err) {
        console.error('[EMG] 消息错误:', JSON.stringify(err));
        return;
      }
      try {
        const emgData: EmgData = JSON.parse(data as string);
        this.onDataReceived(emgData);
      } catch (e) {
        console.error('[EMG] JSON解析失败');
      }
    });

    this.ws.on('close', () => {
      console.info('[EMG] WebSocket 已断开');
      this.connected = false;
      this.onConnectionChanged(false);
      this.scheduleReconnect();
    });

    this.ws.on('error', (err) => {
      console.error('[EMG] WebSocket 错误:', JSON.stringify(err));
      this.onError('WebSocket 连接错误');
    });

    this.ws.connect(SERVER_URL, (err, data) => {
      if (err) {
        console.error('[EMG] 连接失败:', JSON.stringify(err));
        this.onError('连接失败');
        this.scheduleReconnect();
      }
    });
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer !== -1) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = -1;
      console.info('[EMG] 尝试重连...');
      this.connect();
    }, 3000);
  }

  requestLatest(): void {
    if (this.ws && this.connected) {
      this.ws.send(JSON.stringify({ action: 'get_latest' }));
    }
  }

  disconnect(): void {
    if (this.reconnectTimer !== -1) {
      clearTimeout(this.reconnectTimer);
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.connected = false;
  }

  async fetchLatest(): Promise<EmgData | null> {
    let httpRequest = http.createHttp();
    try {
      let response = await httpRequest.request(
        `${REST_API_BASE}/latest`,
        { method: http.RequestMethod.GET, readTimeout: 5000, connectTimeout: 5000 }
      );
      if (response.responseCode === 200) {
        return JSON.parse(response.result as string) as EmgData;
      }
    } catch (e) {
      console.error('[EMG] HTTP请求失败');
    } finally {
      httpRequest.destroy();
    }
    return null;
  }
}

// ==================== UI 页面组件 ====================
@Entry
@Component
struct EmgRealtimePage {
  @State connected: boolean = false;
  @State detectedGesture: string = '等待连接...';
  @State confidence: number = 0;
  @State battery: number = 0;
  @State emgChannels: number[] = [0, 0, 0, 0, 0, 0, 0, 0];
  @State acc: number[] = [0, 0, 0];
  @State gyro: number[] = [0, 0, 0];
  @State angle: number[] = [0, 0, 0];
  @State frameCount: number = 0;
  @State gestureHistory: string[] = [];
  
  // ========== 数据可视化相关 ==========
  // 保存每个通道的历史数据（最近200个点）
  @State emgHistory: number[][] = [[], [], [], [], [], [], [], []];
  // 保存角度历史数据
  @State angleHistory: number[][] = [[], [], []];
  // 刷新画布标志
  @State refreshCanvas: boolean = false;
  
  private readonly MAX_HISTORY_POINTS: number = 200;
  private settings: RenderingContextSettings = new RenderingContextSettings(true);
  private emgContext: CanvasRenderingContext2D = new CanvasRenderingContext2D(this.settings);
  private gestureContext: CanvasRenderingContext2D = new CanvasRenderingContext2D(this.settings);
  private emgService: EmgService = new EmgService();
  private emgCanvasWidth: number = 0;
  private emgCanvasHeight: number = 0;
  private gestureCanvasWidth: number = 0;
  private gestureCanvasHeight: number = 0;
  
  // 初始化历史数据数组
  private initHistoryArrays() {
    for (let i = 0; i < 8; i++) {
      this.emgHistory[i] = [];
    }
    for (let i = 0; i < 3; i++) {
      this.angleHistory[i] = [];
    }
  }

  aboutToAppear() {
    this.initHistoryArrays();
    
    this.emgService.onDataReceived = (data: EmgData) => {
      this.frameCount++;
      this.detectedGesture = data.gesture || '未知';
      this.confidence = data.confidence || 0;
      this.battery = data.battery || 0;

      if (data.emg && data.emg.length > 0) {
        this.emgChannels = data.emg[0];
        
        // 更新EMG历史数据
        for (let i = 0; i < 8 && i < this.emgChannels.length; i++) {
          if (!this.emgHistory[i]) {
            this.emgHistory[i] = [];
          }
          this.emgHistory[i].push(this.emgChannels[i]);
          
          // 保持最多MAX_HISTORY_POINTS个数据点
          if (this.emgHistory[i].length > this.MAX_HISTORY_POINTS) {
            this.emgHistory[i].shift();
          }
        }

        // 直接重绘实时折线图
        if (this.emgCanvasWidth > 0 && this.emgCanvasHeight > 0) {
          this.drawEmgChart(this.emgContext, this.emgCanvasWidth, this.emgCanvasHeight);
        }
      }
      
      if (data.acc) this.acc = data.acc;
      if (data.gyro) this.gyro = data.gyro;
      if (data.angle) {
        this.angle = data.angle;
        
        // 更新角度历史数据
        for (let i = 0; i < 3 && i < this.angle.length; i++) {
          if (!this.angleHistory[i]) {
            this.angleHistory[i] = [];
          }
          this.angleHistory[i].push(this.angle[i]);
          
          if (this.angleHistory[i].length > this.MAX_HISTORY_POINTS) {
            this.angleHistory[i].shift();
          }
        }

        // 直接重绘 3D 手势姿态
        if (this.gestureCanvasWidth > 0 && this.gestureCanvasHeight > 0) {
          this.draw3DGesture(this.gestureContext, this.gestureCanvasWidth, this.gestureCanvasHeight);
        }
      }

      if (data.gesture && data.gesture !== 'unknown' && data.gesture !== 'rest') {
        if (this.gestureHistory.length === 0 ||
          this.gestureHistory[this.gestureHistory.length - 1] !== data.gesture) {
          const conf = data.confidence !== undefined ? data.confidence : 0;
          this.gestureHistory.push(`${data.gesture} (${(conf * 100).toFixed(0)}%)`);
          if (this.gestureHistory.length > 20) {
            this.gestureHistory.shift();
          }
        }
      }
      
      // 触发画布刷新
      this.refreshCanvas = !this.refreshCanvas;
    };

    this.emgService.onConnectionChanged = (connected: boolean) => {
      this.connected = connected;
      if (!connected) {
        this.detectedGesture = '已断开';
      }
    };

    this.emgService.connect();
  }

  // ========== 绘图方法 ==========
  
  // 绘制EMG折线图
  private drawEmgChart(ctx: CanvasRenderingContext2D | null, width: number, height: number) {
    if (!ctx) return;
    
    // 清画布
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, width, height);
    
    // 绘制网格
    ctx.strokeStyle = '#E5E7EB';
    ctx.lineWidth = 1;
    const gridStep = 20;
    for (let i = 0; i <= width; i += gridStep) {
      ctx.beginPath();
      ctx.moveTo(i, 0);
      ctx.lineTo(i, height);
      ctx.stroke();
    }
    for (let j = 0; j <= height; j += gridStep) {
      ctx.beginPath();
      ctx.moveTo(0, j);
      ctx.lineTo(width, j);
      ctx.stroke();
    }
    
    if (this.emgHistory.length === 0 || this.emgHistory[0].length === 0) return;
    
    // 8条通道的颜色
    const colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#14B8A6', '#6366F1'];
    const padding = 20;
    const chartWidth = width - 2 * padding;
    const chartHeight = height - 2 * padding;
    
    // 找到最大最小值
    let maxVal = 0;
    let minVal = 0;
    for (let ch = 0; ch < 8; ch++) {
      for (let val of this.emgHistory[ch]) {
        maxVal = Math.max(maxVal, val);
        minVal = Math.min(minVal, val);
      }
    }
    const valueRange = Math.max(maxVal - minVal, 1);
    
    // 绘制每条通道的曲线
    for (let ch = 0; ch < 8; ch++) {
      if (this.emgHistory[ch].length < 2) continue;
      
      ctx.strokeStyle = colors[ch];
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      
      const xStep = chartWidth / (this.emgHistory[ch].length - 1);
      for (let i = 0; i < this.emgHistory[ch].length; i++) {
        const x = padding + i * xStep;
        const val = this.emgHistory[ch][i];
        const y = padding + chartHeight - ((val - minVal) / valueRange) * chartHeight;
        
        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
    }
    
    // 绘制图例
    ctx.font = '12px Arial';
    ctx.textAlign = 'left';
    for (let i = 0; i < 8; i++) {
      ctx.fillStyle = colors[i];
      ctx.fillRect(width - 120, 10 + i * 18, 10, 10);
      ctx.fillStyle = '#374151';
      ctx.fillText(`CH${i + 1}`, width - 105, 19 + i * 18);
    }
  }
  
  // 绘制3D手势位置（使用等角投影）
  private draw3DGesture(ctx: CanvasRenderingContext2D | null, width: number, height: number) {
    if (!ctx) return;
    
    // 清画布
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, width, height);
    
    // 绘制背景网格
    ctx.strokeStyle = '#E5E7EB';
    ctx.lineWidth = 1;
    const gridStep = 30;
    for (let i = 0; i <= 6; i++) {
      ctx.beginPath();
      ctx.moveTo(50 + i * gridStep, 50);
      ctx.lineTo(50 + i * gridStep, height - 50);
      ctx.stroke();
      
      ctx.beginPath();
      ctx.moveTo(50, 50 + i * gridStep);
      ctx.lineTo(width - 50, 50 + i * gridStep);
      ctx.stroke();
    }
    
    // 计算中心
    const centerX = width / 2;
    const centerY = height / 2;
    const scale = 15; // 缩放因子
    
    // 根据IMU数据生成3D立方体顶点（简化版）
    // 使用pitch, roll, yaw进行旋转投影
    const pitch = this.angle[0] || 0;
    const roll = this.angle[1] || 0;
    const yaw = this.angle[2] || 0;
    
    // 立方体顶点（单位立方体）
    const vertices = [
      [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],  // 后面
      [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]       // 前面
    ];
    
    // 旋转矩阵应用（简化的欧拉角旋转）
    const rotatedVertices: number[][] = [];
    for (let v of vertices) {
      // 绕X轴旋转（pitch）
      const cosP = Math.cos(pitch * Math.PI / 180);
      const sinP = Math.sin(pitch * Math.PI / 180);
      const y1 = v[1] * cosP - v[2] * sinP;
      const z1 = v[1] * sinP + v[2] * cosP;
      
      // 绕Y轴旋转（roll）
      const cosR = Math.cos(roll * Math.PI / 180);
      const sinR = Math.sin(roll * Math.PI / 180);
      const x2 = v[0] * cosR + z1 * sinR;
      const z2 = -v[0] * sinR + z1 * cosR;
      
      // 绕Z轴旋转（yaw）
      const cosY = Math.cos(yaw * Math.PI / 180);
      const sinY = Math.sin(yaw * Math.PI / 180);
      const x3 = x2 * cosY - y1 * sinY;
      const y3 = x2 * sinY + y1 * cosY;
      
      // 等角投影
      const screenX = centerX + (x3 - z2) * scale * 0.866;
      const screenY = centerY + (y3 - (x3 + z2) * 0.5) * scale;
      
      rotatedVertices.push([screenX, screenY, z2]);
    }
    
    // 绘制立方体边
    ctx.strokeStyle = '#3B82F6';
    ctx.lineWidth = 2;
    
    const edges = [
      [0, 1], [1, 2], [2, 3], [3, 0],  // 后面
      [4, 5], [5, 6], [6, 7], [7, 4],  // 前面
      [0, 4], [1, 5], [2, 6], [3, 7]   // 连接
    ];
    
    for (let edge of edges) {
      const v1 = rotatedVertices[edge[0]];
      const v2 = rotatedVertices[edge[1]];
      ctx.beginPath();
      ctx.moveTo(v1[0], v1[1]);
      ctx.lineTo(v2[0], v2[1]);
      ctx.stroke();
    }
    
    // 绘制中心点
    ctx.fillStyle = '#EF4444';
    ctx.beginPath();
    ctx.arc(centerX, centerY, 5, 0, 2 * Math.PI);
    ctx.fill();
    
    // 绘制坐标轴标签和当前角度值
    ctx.font = '14px Arial';
    ctx.fillStyle = '#374151';
    ctx.textAlign = 'center';
    
    ctx.fillText(`Pitch: ${pitch.toFixed(1)}°`, width / 2, height - 40);
    ctx.fillText(`Roll: ${roll.toFixed(1)}°  Yaw: ${yaw.toFixed(1)}°`, width / 2, height - 20);
  }

  aboutToDisappear() {
    this.emgService.disconnect();
  }

  build() {
    Column() {
      // 顶部导航栏
      CustomAppBar({ title: 'EMG 实时监控', showSettings: false })

      Scroll() {
        Column() {
          // 连接状态卡片
          Row() {
            Text(this.connected ? '● 已连接' : '○ 已断开')
              .fontSize(16)
              .fontColor(this.connected ? '#10B981' : '#EF4444')
              .fontWeight(FontWeight.Medium)
            Blank()
            Text(`帧数: ${this.frameCount}`)
              .fontSize(14)
              .fontColor('#6B7280')
          }
          .width('100%')
          .padding(12)
          .backgroundColor(this.connected ? '#ECFDF5' : '#FEE2E2')
          .borderRadius(8)
          .margin({ bottom: 12 })

          // 手势识别卡片
          Column() {
            Text('🎯 手势识别')
              .fontSize(16)
              .fontWeight(FontWeight.Bold)
              .margin({ bottom: 12 })

            Text(this.getGestureEmoji(this.detectedGesture))
              .fontSize(64)
              .margin({ bottom: 8 })

            Text(this.detectedGesture)
              .fontSize(24)
              .fontWeight(FontWeight.Bold)
              .margin({ bottom: 12 })

            Progress({ value: this.confidence * 100, total: 100, type: ProgressType.Linear })
              .width('80%')
              .margin({ bottom: 8 })

            Text(`置信度: ${(this.confidence * 100).toFixed(1)}%`)
              .fontSize(14)
              .fontColor('#6B7280')
          }
          .width('100%')
          .padding(20)
          .backgroundColor(Color.White)
          .borderRadius(12)
          .shadow({ radius: 8, color: '#00000010', offsetX: 0, offsetY: 2 })
          .margin({ bottom: 12 })

          // EMG 8通道折线图
          Column() {
            Text('⚡ EMG 8通道信号')
              .fontSize(16)
              .fontWeight(FontWeight.Bold)
              .margin({ bottom: 12 })

            Canvas(this.emgContext)
              .width('100%')
              .height(240)
              .backgroundColor('#F3F4F6')
              .borderRadius(8)
              .onReady(() => {
                this.emgCanvasWidth = this.emgContext.width;
                this.emgCanvasHeight = this.emgContext.height;
                this.drawEmgChart(this.emgContext, this.emgCanvasWidth, this.emgCanvasHeight);
              })
              .key(`emg-chart-${this.refreshCanvas}`)
            
            // 当前通道值显示
            Row({ space: 8 }) {
              ForEach(this.emgChannels, (value: number, index: number) => {
                Column() {
                  Text(`CH${index + 1}`)
                    .fontSize(12)
                    .fontColor('#6B7280')
                  Text(`${value}`)
                    .fontSize(14)
                    .fontWeight(FontWeight.Bold)
                    .fontColor('#3B82F6')
                    .margin({ top: 2 })
                }
                .layoutWeight(1)
                .padding(8)
                .backgroundColor('#F3F4F6')
                .borderRadius(6)
                .alignItems(HorizontalAlign.Center)
              })
            }
            .width('100%')
            .margin({ top: 12 })
          }
          .width('100%')
          .padding(20)
          .backgroundColor(Color.White)
          .borderRadius(12)
          .shadow({ radius: 8, color: '#00000010', offsetX: 0, offsetY: 2 })
          .margin({ bottom: 12 })

          // IMU 3D手势可视化
          Column() {
            Row() {
              Column() {
                Text('🧭 3D 手势位置')
                  .fontSize(16)
                  .fontWeight(FontWeight.Bold)
              }
              .layoutWeight(1)
              
              Column() {
                Text('加速度')
                  .fontSize(12)
                  .fontColor('#6B7280')
                Text(`X:${this.acc[0]} Y:${this.acc[1]} Z:${this.acc[2]}`)
                  .fontSize(11)
                  .fontColor('#374151')
                  .margin({ top: 2 })
              }
              .padding(8)
              .backgroundColor('#F3F4F6')
              .borderRadius(6)
            }
            .width('100%')
            .margin({ bottom: 12 })

            Canvas(this.gestureContext)
              .width('100%')
              .height(280)
              .backgroundColor('#F3F4F6')
              .borderRadius(8)
              .onReady(() => {
                this.gestureCanvasWidth = this.gestureContext.width;
                this.gestureCanvasHeight = this.gestureContext.height;
                this.draw3DGesture(this.gestureContext, this.gestureCanvasWidth, this.gestureCanvasHeight);
              })
              .key(`gesture-3d-${this.refreshCanvas}`)
            
            Row({ space: 8 }) {
              Column() {
                Text('陀螺仪')
                  .fontSize(12)
                  .fontColor('#6B7280')
                Text(`X:${this.gyro[0]}°`)
                  .fontSize(11)
                  .fontColor('#374151')
                  .margin({ top: 2 })
              }
              .layoutWeight(1)
              .padding(8)
              .backgroundColor('#F3F4F6')
              .borderRadius(6)
              .alignItems(HorizontalAlign.Center)
              
              Column() {
                Text('陀螺仪')
                  .fontSize(12)
                  .fontColor('#6B7280')
                Text(`Y:${this.gyro[1]}°`)
                  .fontSize(11)
                  .fontColor('#374151')
                  .margin({ top: 2 })
              }
              .layoutWeight(1)
              .padding(8)
              .backgroundColor('#F3F4F6')
              .borderRadius(6)
              .alignItems(HorizontalAlign.Center)
              
              Column() {
                Text('陀螺仪')
                  .fontSize(12)
                  .fontColor('#6B7280')
                Text(`Z:${this.gyro[2]}°`)
                  .fontSize(11)
                  .fontColor('#374151')
                  .margin({ top: 2 })
              }
              .layoutWeight(1)
              .padding(8)
              .backgroundColor('#F3F4F6')
              .borderRadius(6)
              .alignItems(HorizontalAlign.Center)
            }
            .width('100%')
            .margin({ top: 12 })
          }
          .width('100%')
          .padding(20)
          .backgroundColor(Color.White)
          .borderRadius(12)
          .shadow({ radius: 8, color: '#00000010', offsetX: 0, offsetY: 2 })
          .margin({ bottom: 12 })

          // 设备状态
          Row({ space: 12 }) {
            Column() {
              Text('🔋')
                .fontSize(32)
              Text(`${this.battery}%`)
                .fontSize(20)
                .fontWeight(FontWeight.Bold)
                .margin({ top: 8 })
              Text('电量')
                .fontSize(12)
                .fontColor('#6B7280')
                .margin({ top: 4 })
            }
            .layoutWeight(1)
            .padding(16)
            .backgroundColor(Color.White)
            .borderRadius(12)
            .shadow({ radius: 8, color: '#00000010', offsetX: 0, offsetY: 2 })

            Column() {
              Text('📊')
                .fontSize(32)
              Text(`${this.frameCount}`)
                .fontSize(20)
                .fontWeight(FontWeight.Bold)
                .margin({ top: 8 })
              Text('总帧数')
                .fontSize(12)
                .fontColor('#6B7280')
                .margin({ top: 4 })
            }
            .layoutWeight(1)
            .padding(16)
            .backgroundColor(Color.White)
            .borderRadius(12)
            .shadow({ radius: 8, color: '#00000010', offsetX: 0, offsetY: 2 })
          }
          .width('100%')
          .margin({ bottom: 12 })

          // 手势历史
          if (this.gestureHistory.length > 0) {
            Column() {
              Text('📜 手势历史')
                .fontSize(16)
                .fontWeight(FontWeight.Bold)
                .margin({ bottom: 12 })

              ForEach(this.gestureHistory.slice(-10).reverse(), (item: string, index: number) => {
                Text(item)
                  .fontSize(14)
                  .fontColor('#374151')
                  .margin({ bottom: 6 })
              })
            }
            .width('100%')
            .padding(20)
            .backgroundColor(Color.White)
            .borderRadius(12)
            .shadow({ radius: 8, color: '#00000010', offsetX: 0, offsetY: 2 })
            .margin({ bottom: 20 })
          }
        }
        .padding({ left: 16, right: 16, top: 16, bottom: 80 })
      }
      .layoutWeight(1)

      // 底部导航栏 (currentIndex -1 表示无选中项)
      BottomNavBar({ currentIndex: -1 })
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F9FAFB')
  }

  getGestureEmoji(gesture: string): string {
    const emojiMap: Record<string, string> = {
      'rest': '✋',
      'relax': '✋',
      'fist': '✊',
      'open': '🖐',
      'pinch': '🤏',
      'ok': '👌',
      'ye': '✌️',
      'sidegrip': '🤝',
      'unknown': '❓',
    };
    return emojiMap[gesture.toLowerCase()] || '🤚';
  }
}

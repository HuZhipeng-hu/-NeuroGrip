import { CustomAppBar } from './CustomAppBar';
import { BottomNavBar } from './BottomNavBar';
import webSocket from '@ohos.net.webSocket';
import http from '@ohos.net.http';
import preferences from '@ohos.data.preferences';
import { BASE_URL, WS_URL } from '../common/Config';
import { EmgData } from '../models/EmgData';

const SERVER_URL: string = BASE_URL;

interface HttpHeaders {
  Authorization?: string;
  'Content-Type'?: string;
}

interface UserContext {
  userId?: number;
  username?: string;
}

interface StartRecordingRequestBody {
  gesture: string;
  duration: number;
  deviceId: string;
  userId?: number;
}

interface StopRecordingRequestBody {
  gesture: string;
  deviceId: string;
  userId?: number;
}

interface StopRecordingResponse {
  recordingId: string;
  sampleCount: number;
  gesture: string;
  qualityScore: number;
  uploadedTime: string;
}

@Entry
@Component
export struct Training {
  @State connected: boolean = false;
  @State detectedGesture: string = '等待连接';
  @State confidence: number = 0;
  @State battery: number = 0;
  @State gestureHistory: string[] = [];
  @State customGestures: string[] = [];
  @State newGestureName: string = '';
  @State showAddGesture: boolean = false;

  @State selectedGesture: string = 'fist';
  @State recordDuration: number = 3;
  @State isRecording: boolean = false;
  @State countdown: number = 0;
  @State statusMessage: string = '准备录制';
  @State deviceId: string = 'emg_device_' + Math.random().toString(36).substring(7);

  @State waveformData: number[][] = (() => {
    const arr: number[][] = [];
    for (let i = 0; i < 8; i++) {
      arr.push(new Array(100).fill(50));
    }
    return arr;
  })();

  private sensitivity: number = 50;
  private ws: webSocket.WebSocket | null = null;
  private countdownTimer: number = -1;
  private writeIndex: number = 0;
  private lastDrawTime: number = 0;
  private readonly drawInterval: number = 50;
  private settings: RenderingContextSettings = new RenderingContextSettings(true);
  private context: CanvasRenderingContext2D = new CanvasRenderingContext2D(this.settings);
  private canvasWidth: number = 0;
  private canvasHeight: number = 180;

  aboutToAppear() {
    this.syncAuthFromPreferences().then(() => {
      this.connectWebSocket();
    });
  }

  aboutToDisappear() {
    this.disconnectWs();
    if (this.countdownTimer !== -1) {
      clearInterval(this.countdownTimer);
    }
  }

  build() {
    Column() {
      CustomAppBar({ title: '训练', showSettings: false })

      Tabs({ barPosition: BarPosition.Start }) {
        TabContent() {
          Scroll() {
            Column({ space: 12 }) {
              this.buildStatusCard()
              this.buildWaveformCard()
              this.buildGestureHistoryCard()
            }
            .width('100%')
            .padding({ left: 14, right: 14, top: 10, bottom: 16 })
          }
          .width('100%')
          .height('100%')
          .backgroundColor('#F3F4F6')
        }
        .tabBar('实时显示')

        TabContent() {
          Scroll() {
            Column({ space: 12 }) {
              this.buildRecordingCard()
            }
            .width('100%')
            .padding({ left: 14, right: 14, top: 10, bottom: 16 })
          }
          .width('100%')
          .height('100%')
          .backgroundColor('#F3F4F6')
        }
        .tabBar('数据标注')
      }
      .layoutWeight(1)

      BottomNavBar({ currentIndex: 1 })
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F3F4F6')
  }

  @Builder
  private buildStatusCard() {
    Column({ space: 8 }) {
      Row() {
        Text(this.connected ? '🟢 已连接' : '⚪ 未连接')
          .fontSize(16)
          .fontWeight(FontWeight.Bold)
          .fontColor(this.connected ? '#10B981' : '#6B7280')
        Blank()
        Text(`电量 ${this.battery}%`)
          .fontSize(14)
          .fontColor('#6B7280')
      }

      Row() {
        Column({ space: 4 }) {
          Text(`手势: ${this.detectedGesture}`)
            .fontSize(16)
            .fontWeight(FontWeight.Medium)
          Text(`置信度: ${(this.confidence * 100).toFixed(0)}%`)
            .fontSize(14)
            .fontColor('#6B7280')
        }
        .layoutWeight(1)

        Column({ space: 4 }) {
          Text('设备ID')
            .fontSize(12)
            .fontColor('#9CA3AF')
          TextInput({ text: this.deviceId })
            .fontSize(14)
            .height(34)
            .backgroundColor('#F3F4F6')
            .borderRadius(8)
            .onChange((val: string) => {
              this.deviceId = val;
            })
        }
        .width('46%')
      }
    }
    .width('100%')
    .padding(16)
    .backgroundColor(Color.White)
    .borderRadius(12)
    .shadow({ radius: 8, color: '#00000010', offsetX: 0, offsetY: 2 })
  }

  @Builder
  private buildWaveformCard() {
    Column({ space: 8 }) {
      Row() {
        Text('实时肌电波形')
          .fontSize(16)
          .fontWeight(FontWeight.Medium)
        Blank()
        Text('灵敏度')
          .fontSize(12)
          .fontColor('#6B7280')
        Slider({ value: this.sensitivity, min: 10, max: 100, step: 5, style: SliderStyle.InSet })
          .width(120)
          .onChange((v: number) => { this.sensitivity = v; })
      }

      Canvas(this.context)
        .width('100%')
        .height(200)
        .backgroundColor('#F9FAFB')
        .borderRadius(12)
        .onReady(() => {
          this.canvasWidth = this.context.width;
          this.canvasHeight = this.context.height;
          this.drawWaveform();
        })
    }
    .width('100%')
    .padding(16)
    .backgroundColor(Color.White)
    .borderRadius(12)
    .shadow({ radius: 8, color: '#00000010', offsetX: 0, offsetY: 2 })
  }

  @Builder
  private buildRecordingCard() {
    Column({ space: 12 }) {
      Text('数据标注 / 录制')
        .fontSize(16)
        .fontWeight(FontWeight.Medium)

      Column({ space: 8 }) {
        Row() {
          Text('手势:').fontSize(14)
          Blank()
          Button(this.showAddGesture ? '收起' : '+ 自定义')
            .height(32)
            .fontSize(13)
            .backgroundColor('#E0F2FE')
            .fontColor('#1D4ED8')
            .onClick(() => {
              this.showAddGesture = !this.showAddGesture;
            })
        }
        Scroll() {
          Row({ space: 8 }) {
            ForEach(this.getGestureList(), (gesture: string) => {
              Text(this.selectedGesture === gesture ? `✓ ${gesture}` : gesture)
                .padding({ left: 12, right: 12, top: 8, bottom: 8 })
                .borderRadius(12)
                .backgroundColor(this.selectedGesture === gesture ? '#E0F2FE' : '#F3F4F6')
                .fontColor(this.selectedGesture === gesture ? '#1D4ED8' : '#374151')
                .onClick(() => {
                  this.selectedGesture = gesture;
                })
            })
          }
          .padding({ left: 4, right: 4 })
        }
        .width('100%')
        .height(48)
        .scrollBar(BarState.Off)
        .scrollable(ScrollDirection.Horizontal)

        if (this.showAddGesture) {
          Column({ space: 8 }) {
            Text('新增自定义手势').fontSize(14).fontColor('#374151')
            TextInput({ placeholder: '请输入手势名称，如 wave', text: this.newGestureName })
              .height(40)
              .fontSize(14)
              .backgroundColor('#F3F4F6')
              .borderRadius(8)
              .onChange((val: string) => {
                this.newGestureName = val;
              })
            Row({ space: 8 }) {
              Button('取消')
                .layoutWeight(1)
                .height(36)
                .backgroundColor('#E5E7EB')
                .fontColor('#374151')
                .onClick(() => {
                  this.newGestureName = '';
                  this.showAddGesture = false;
                })
              Button('添加')
                .layoutWeight(1)
                .height(36)
                .backgroundColor('#10B981')
                .onClick(() => {
                  this.addCustomGesture();
                })
            }
          }
          .padding({ top: 8, bottom: 8 })
        }
      }
      .width('100%')

      Row() {
        Text('录制时长').fontSize(14)
        Blank()
        Text(`${this.recordDuration}s`).fontSize(14).fontColor('#3B82F6')
      }
      Slider({ value: this.recordDuration, min: 1, max: 10, step: 1, style: SliderStyle.OutSet })
        .width('100%')
        .onChange((v: number) => { this.recordDuration = v; })

      if (this.isRecording) {
        Row({ space: 10 }) {
          Text('●')
            .fontSize(18)
            .fontColor('#EF4444')
          Text(`录制中… 倒计时 ${this.countdown}s`).fontSize(14).fontColor('#EF4444')
        }
      }

      Row({ space: 12 }) {
        Button(this.isRecording ? '停止录制' : '开始录制')
          .layoutWeight(1)
          .height(46)
          .fontSize(16)
          .backgroundColor(this.isRecording ? '#EF4444' : '#10B981')
          .onClick(() => {
            if (this.isRecording) {
              this.stopRecording();
            } else {
              this.startRecording();
            }
          })

        Button('刷新最新')
          .height(46)
          .backgroundColor('#3B82F6')
          .fontSize(14)
          .onClick(() => {
            this.requestLatestFrame();
          })
      }

      if (this.statusMessage) {
        Text(this.statusMessage)
          .fontSize(13)
          .fontColor('#6B7280')
      }
    }
    .width('100%')
    .padding(16)
    .backgroundColor(Color.White)
    .borderRadius(12)
    .shadow({ radius: 8, color: '#00000010', offsetX: 0, offsetY: 2 })
  }

  @Builder
  private buildGestureHistoryCard() {
    Column({ space: 8 }) {
      Text('手势历史').fontSize(15).fontWeight(FontWeight.Medium)
      if (this.gestureHistory.length === 0) {
        Text('暂无历史').fontSize(13).fontColor('#9CA3AF')
      } else {
        ForEach(this.gestureHistory.slice(-10), (item: string) => {
          Row() {
            Text(item).fontSize(14).fontColor('#374151')
          }
          .width('100%')
        })
      }
    }
    .width('100%')
    .padding(14)
    .backgroundColor(Color.White)
    .borderRadius(12)
    .shadow({ radius: 8, color: '#00000010', offsetX: 0, offsetY: 2 })
  }

  private startRecording() {
    if (this.isRecording) return;
    this.isRecording = true;
    this.countdown = this.recordDuration;
    this.statusMessage = `🔴 正在录制 ${this.selectedGesture}`;
    this.startRecordingRequest();
    this.countdownTimer = setInterval(() => {
      this.countdown -= 1;
      if (this.countdown <= 0) {
        this.stopRecording();
      }
    }, 1000) as number;
  }

  private stopRecording() {
    if (!this.isRecording) return;
    this.isRecording = false;
    if (this.countdownTimer !== -1) {
      clearInterval(this.countdownTimer);
      this.countdownTimer = -1;
    }
    this.countdown = 0;
    this.statusMessage = '⏹ 录制已停止，上传中…';
    this.stopRecordingRequest();
  }

  private async startRecordingRequest() {
    try {
      const httpRequest = http.createHttp();
      const userCtx = this.getUserContext();
      const body: StartRecordingRequestBody = {
        gesture: this.selectedGesture,
        duration: this.recordDuration,
        deviceId: this.deviceId,
        userId: userCtx.userId
      };
      const resp = await httpRequest.request(
        `${SERVER_URL}/api/annotation/start`,
        {
          method: http.RequestMethod.POST,
          header: this.getJsonHeaders(),
          extraData: JSON.stringify(body),
          connectTimeout: 5000,
          readTimeout: 10000
        }
      );
      if (resp.responseCode !== 200) {
        this.statusMessage = `录制启动失败 (${resp.responseCode})`;
      }
    } catch (e) {
      const err = e as Error;
      this.statusMessage = `录制启动异常: ${err.message}`;
    }
  }

  private async stopRecordingRequest() {
    try {
      const httpRequest = http.createHttp();
      const userCtx = this.getUserContext();
      const body: StopRecordingRequestBody = {
        gesture: this.selectedGesture,
        deviceId: this.deviceId,
        userId: userCtx.userId
      };
      const resp = await httpRequest.request(
        `${SERVER_URL}/api/annotation/stop`,
        {
          method: http.RequestMethod.POST,
          header: this.getJsonHeaders(),
          extraData: JSON.stringify(body),
          connectTimeout: 5000,
          readTimeout: 10000
        }
      );
      if (resp.responseCode === 200) {
        try {
          const data: StopRecordingResponse = JSON.parse(resp.result as string) as StopRecordingResponse;
          this.statusMessage = `✅ 保存 ${data?.sampleCount ?? 0} 样本`;
        } catch (e) {
          this.statusMessage = '✅ 保存完成';
        }
      } else {
        this.statusMessage = `停止录制失败 (${resp.responseCode})`;
      }
    } catch (e) {
      const err = e as Error;
      this.statusMessage = `停止录制异常: ${err.message}`;
    }
  }

  private async requestLatestFrame() {
    try {
      const httpRequest = http.createHttp();
      const resp = await httpRequest.request(
        `${SERVER_URL}/api/emg/latest`,
        { method: http.RequestMethod.GET, readTimeout: 5000, connectTimeout: 5000 }
      );
      if (resp.responseCode === 200) {
        const data = JSON.parse(resp.result as string) as EmgData;
        this.handleIncomingEmg(data);
      }
    } catch (e) {
      // ignore fetch errors
    }
  }

  private connectWebSocket() {
    this.disconnectWs();
    this.ws = webSocket.createWebSocket();

    this.ws.on('open', () => {
      this.connected = true;
    });

    this.ws.on('close', () => {
      this.connected = false;
    });

    this.ws.on('error', () => {
      this.connected = false;
    });

    this.ws.on('message', (err, data) => {
      if (err) {
        return;
      }
      try {
        const text = typeof data === 'string' ? data : String.fromCharCode(...new Uint8Array(data as ArrayBuffer));
        const emgData = JSON.parse(text) as EmgData;
        this.handleIncomingEmg(emgData);
      } catch (e) {
        // ignore parse errors
      }
    });

    this.ws.connect(WS_URL, () => {});
  }

  private disconnectWs() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
      this.connected = false;
    }
  }

  private handleIncomingEmg(data: EmgData) {
    this.detectedGesture = data.gesture ?? 'unknown';
    this.confidence = data.confidence ?? 0;
    this.battery = data.battery ?? 0;

    const packet = data.emg && data.emg.length > 0 ? data.emg[0] : [];
    if (packet.length >= 8) {
      this.updateWaveforms(packet.slice(0, 8));
    }

    if (data.gesture && data.gesture !== 'unknown' && data.gesture !== 'rest') {
      const label = `${data.gesture} (${((data.confidence ?? 0) * 100).toFixed(0)}%)`;
      if (this.gestureHistory.length === 0 || this.gestureHistory[this.gestureHistory.length - 1] !== label) {
        this.gestureHistory.push(label);
        if (this.gestureHistory.length > 30) {
          this.gestureHistory.shift();
        }
      }
    }
  }

  private updateWaveforms(newValues: number[]): void {
    if (newValues.length < 8) return;
    const base = 127;
    const scale = this.sensitivity / 10;
    for (let i = 0; i < 8; i++) {
      const delta = newValues[i] - base;
      let scaled = 50 + delta * scale;
      if (scaled < 5) scaled = 5;
      if (scaled > 95) scaled = 95;
      this.waveformData[i][this.writeIndex] = scaled;
    }
    this.writeIndex = (this.writeIndex + 1) % 100;
    this.drawWaveform();
  }

  private getGestureList(): string[] {
    return ['fist', 'ok', 'pinch', 'relax', 'sidegrip', 'ye', ...this.customGestures];
  }

  private addCustomGesture() {
    const name = this.newGestureName.trim();
    if (!name) {
      this.statusMessage = '请输入手势名称';
      return;
    }
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/ig, '_').replace(/^_+|_+$/g, '') || `custom_${Date.now()}`;
    if (this.getGestureList().includes(slug)) {
      this.statusMessage = '手势已存在';
      return;
    }
    this.customGestures.push(slug);
    this.selectedGesture = slug;
    this.newGestureName = '';
    this.showAddGesture = false;
    this.statusMessage = `已添加手势 ${slug}`;
    this.uploadCustomGestureToServer(slug, name);
  }

  private async uploadCustomGestureToServer(gestureId: string, label: string) {
    try {
      const httpRequest = http.createHttp();
      const resp = await httpRequest.request(
        `${SERVER_URL}/api/annotation/custom-gestures`,
        {
          method: http.RequestMethod.POST,
          header: this.getJsonHeaders(),
          extraData: JSON.stringify({
            deviceId: this.deviceId,
            gestureId: gestureId,
            gestureLabel: label,
            gestureIcon: '✋'
          }),
          connectTimeout: 10000,
          readTimeout: 10000
        }
      );
      if (resp.responseCode !== 200) {
        this.statusMessage = `自定义手势保存失败 (${resp.responseCode})`;
      }
    } catch (e) {
      const err = e as Error;
      this.statusMessage = `上传自定义手势异常: ${err.message}`;
    }
  }

  private drawWaveform(): void {
    const now = Date.now();
    if (now - this.lastDrawTime < this.drawInterval) return;
    this.lastDrawTime = now;
    if (!this.context || this.canvasWidth <= 0 || this.canvasHeight <= 0) return;

    this.context.clearRect(0, 0, this.canvasWidth, this.canvasHeight);
    const colors: string[] = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4', '#F97316'];
    const stepX = this.canvasWidth / 99;

    for (let ch = 0; ch < 8; ch++) {
      const data = this.waveformData[ch];
      this.context.beginPath();
      this.context.strokeStyle = colors[ch];
      this.context.lineWidth = 1.1;
      for (let i = 0; i < 100; i++) {
        const x = i * stepX;
        const y = (data[i] / 100) * this.canvasHeight;
        if (i === 0) {
          this.context.moveTo(x, y);
        } else {
          this.context.lineTo(x, y);
        }
      }
      this.context.stroke();
    }
  }

  private toSafeString(value: string | number | bigint | boolean | object): string {
    if (typeof value === 'string') return value;
    if (typeof value === 'number' || typeof value === 'bigint') return value.toString();
    if (typeof value === 'boolean') return value ? 'true' : 'false';
    return '';
  }

  private syncAuthFromPreferences(): Promise<void> {
    return new Promise((resolve) => {
      try {
        const ctx = getContext(this) as Context;
        preferences.getPreferences(ctx, 'login_prefs', (err, prefs) => {
          if (err || !prefs) {
            resolve();
            return;
          }
          try {
            const tokenVal = this.toSafeString(prefs.getSync('auth_token', ''));
            if (tokenVal.length > 0) {
              AppStorage.SetOrCreate<string>('token', tokenVal);
            }
            const uidVal = this.toSafeString(prefs.getSync('user_id', ''));
            if (uidVal.length > 0) {
              AppStorage.SetOrCreate<string>('userId', uidVal);
            }
            const unameVal = this.toSafeString(prefs.getSync('username', ''));
            if (unameVal.length > 0) {
              AppStorage.SetOrCreate<string>('username', unameVal);
            }
          } catch (e) {
            // ignore
          }
          resolve();
        });
      } catch (e) {
        resolve();
      }
    });
  }

  private getAuthHeaders(): HttpHeaders {
    const token = AppStorage.Get<string>('token');
    if (token && token.length > 0) {
      return { Authorization: `Bearer ${token}` } as HttpHeaders;
    }
    return {} as HttpHeaders;
  }

  private getJsonHeaders(): HttpHeaders {
    const auth = this.getAuthHeaders();
    return {
      Authorization: auth.Authorization,
      'Content-Type': 'application/json'
    } as HttpHeaders;
  }

  private getUserContext(): UserContext {
    const ctx: UserContext = {};
    try {
      const uidStr = AppStorage.Get<string>('userId');
      if (uidStr) {
        const parsed = parseInt(uidStr);
        if (!Number.isNaN(parsed)) ctx.userId = parsed;
      }
      const uname = AppStorage.Get<string>('username');
      if (uname && uname.length > 0) ctx.username = uname;
    } catch (e) {
      // ignore
    }
    return ctx;
  }
}



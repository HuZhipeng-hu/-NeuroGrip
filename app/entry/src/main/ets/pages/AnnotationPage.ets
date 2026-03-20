// ==============================================================================
// AnnotationPage.ets - 数据标注与采集页面
// ==============================================================================
// 功能:
// 1. 选择手势类型（FIST, OK, PINCH, RELAX, SIDEGRIP, YE）
// 2. 配置录制时长（1-10秒）
// 3. 一键开始/停止录制
// 4. 数据自动上传到 MySQL 数据库
// 5. 标注统计信息与手势分布展示
// 集成到华为 ICT 赛道应用
// ==============================================================================

import http from '@ohos.net.http';
import router from '@ohos.router';
import { CustomAppBar } from './CustomAppBar';
import { BottomNavBar } from './BottomNavBar';
import preferences from '@ohos.data.preferences';

const SERVER_URL: string = 'http://1.95.65.51:8080';

// ==================== 数据模型 ====================
interface GestureStat {
  gesture: string;
  count: number;
  label: string;
  icon: string;
}

interface AnnotationRecord {
  id: number;
  gesture: string;
  duration: number;
  sampleCount: number;
  quality: number;
  createdTime: string;
}

interface GestureCount {
  gesture: string;
  count: number;
}

interface AnnotationStatsResponse {
  gestureCounts: GestureCount[];
  totalSamples: number;
  cachedSamples: number;
}

interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

interface StartRecordingResponse {
  recordingId: string;
  gesture: string;
  duration: number;
  startTime: string;
}

interface StopRecordingResponse {
  recordingId: string;
  sampleCount: number;
  gesture: string;
  qualityScore: number;
  uploadedTime: string;
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

interface RecordsListResponse {
  records: AnnotationRecord[];
  total: number;
}
interface HttpHeaders {
  Authorization?: string;
  'Content-Type'?: string;
}

interface UserContext {
  userId?: number;
  username?: string;
}

// ==================== 主页面 ====================
@Entry
@Component
struct AnnotationPage {
  // 手势选择
  @State selectedGesture: string = 'fist';
  @State recordDuration: number = 3;
  // 录制状态
  @State isRecording: boolean = false;
  @State countdown: number = 0;
  @State statusMessage: string = '选择手势并开始录制';
  // 统计数据
  @State gestureStats: GestureStat[] = [];
  @State customGestures: GestureStat[] = [];
  @State recentRecords: AnnotationRecord[] = [];
  @State totalSamples: number = 0;
  @State isLoading: boolean = false;
  // 缓存预览
  @State cachedSamples: number = 0;
  // 自定义手势管理
  @State showCustomDialog: boolean = false;
  @State customGestureName: string = '';
  @State customGestureIcon: string = '🤚';
  // 用户和设备标识
  @State deviceId: string = 'emg_device_' + Math.random().toString(36).substring(7);
  private recordTimer: number = -1;
  private countdownTimer: number = -1;
  private readonly STORAGE_KEY_CUSTOM: string = 'custom_gestures';
  private readonly GESTURES: GestureStat[] = [
    {
      gesture: 'fist',
      label: '握拳',
      icon: '✊',
      count: 0
    },
    {
      gesture: 'ok',
      label: 'OK',
      icon: '👌',
      count: 0
    },
    {
      gesture: 'pinch',
      label: '捏合',
      icon: '🤏',
      count: 0
    },
    {
      gesture: 'relax',
      label: '放松',
      icon: '🖐',
      count: 0
    },
    {
      gesture: 'sidegrip',
      label: '侧握',
      icon: '🤙',
      count: 0
    },
    {
      gesture: 'ye',
      label: 'YE',
      icon: '🤟',
      count: 0
    },
  ];

  aboutToAppear() {
    this.syncAuthFromPreferences();
    this.gestureStats = this.GESTURES.map((g: GestureStat): GestureStat => ({
      gesture: g.gesture,
      label: g.label,
      icon: g.icon,
      count: g.count
    }));
    this.loadCustomGestures();
    this.loadStats();
  }

  aboutToDisappear() {
    this.stopRecording();
    this.saveCustomGestures();
  }

  private syncAuthFromPreferences() {
    try {
      const context = getContext(this) as Context;
      preferences.getPreferences(context, 'login_prefs', (err, prefs) => {
        if (err || !prefs) {
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
          // ignore read errors
        }
      });
    } catch (e) {
      // ignore context errors
    }
  }

  private toSafeString(value: string | number | bigint | boolean | object): string {
    if (typeof value === 'string') {
      return value;
    }
    if (typeof value === 'number' || typeof value === 'bigint') {
      return value.toString();
    }
    if (typeof value === 'boolean') {
      return value ? 'true' : 'false';
    }
    return '';
  }

  // ======================== 自定义手势管理 ========================

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
        if (!Number.isNaN(parsed)) {
          ctx.userId = parsed;
        }
      }
      const uname = AppStorage.Get<string>('username');
      if (uname) {
        ctx.username = uname;
      }
    } catch (e) {
      // ignore storage errors
    }
    return ctx;
  }

  private loadCustomGestures() {
    try {
      const stored = AppStorage.Get<string>(this.STORAGE_KEY_CUSTOM);
      if (stored) {
        this.customGestures = JSON.parse(stored) as GestureStat[];
      } else {
        this.customGestures = [];
      }
    } catch (e) {
      const err = e as Error;
      console.warn('[Annotation] 加载自定义手势失败:', JSON.stringify(err));
      this.customGestures = [];
    }
  }

  private saveCustomGestures() {
    try {
      AppStorage.SetOrCreate<string>(this.STORAGE_KEY_CUSTOM, JSON.stringify(this.customGestures));
    } catch (e) {
      const err = e as Error;
      console.warn('[Annotation] 保存自定义手势失败:', JSON.stringify(err));
    }
  }

  addCustomGesture() {
    const name = this.customGestureName.trim();
    if (!name) {
      this.statusMessage = '请输入手势名称';
      return;
    }

    // 将名称转为可复用的手势 ID（用于上传）
    const slug = name
      .toLowerCase()
      .replace(/[^a-z0-9]+/ig, '_')
      .replace(/^_+|_+$/g, '') || `custom_${Date.now()}`;

    // 重复校验：同名或同 ID 不重复添加
    const exists = this.getAllGestures().some(g => g.gesture === slug || g.label === name);
    if (exists) {
      this.statusMessage = '手势已存在，请更换名称';
      return;
    }

    const newGesture: GestureStat = {
      gesture: slug,
      label: name,
      icon: this.customGestureIcon,
      count: 0
    };

    this.customGestures.push(newGesture);
    this.saveCustomGestures();
    
    // 同时上传到服务器
    this.uploadCustomGestureToServer(newGesture);
    
    this.selectedGesture = slug;
    this.showCustomDialog = false;
    this.statusMessage = `✅ 已添加自定义手势：${name}`;

    // 重置输入
    this.customGestureName = '';
    this.customGestureIcon = '🤚';
  }

  // 上传自定义手势到服务器
  private async uploadCustomGestureToServer(gesture: GestureStat) {
    try {
      const httpRequest = http.createHttp();
      const response = await httpRequest.request(
        `${SERVER_URL}/api/annotation/custom-gestures`,
        {
          method: http.RequestMethod.POST,
          header: this.getJsonHeaders(),
          extraData: JSON.stringify({
            deviceId: this.deviceId,
            gestureId: gesture.gesture,
            gestureLabel: gesture.label,
            gestureIcon: gesture.icon
          }),
          connectTimeout: 10000,
          readTimeout: 10000
        }
      );
      
      try {
        const respBody = response.result as string;
        const respObj = JSON.parse(respBody) as ApiResponse<Object>;
        if (respObj.code === 200) {
          console.log('[Annotation] 自定义手势已保存到服务器:', gesture.label);
        } else {
          console.warn('[Annotation] 服务器保存失败:', respObj.message);
        }
      } catch (e) {
        const err = e as Error;
        console.warn('[Annotation] 解析响应失败:', JSON.stringify(err));
      }
    } catch (e) {
      const err = e as Error;
      console.warn('[Annotation] 上传请求异常:', JSON.stringify(err));
    }
  }

  // 删除自定义手势，同时从服务器删除
  private async deleteCustomGestureWithServer(id: string) {
    this.customGestures = this.customGestures.filter(g => g.gesture !== id);
    this.saveCustomGestures();
    
    // 从服务器删除
    try {
      const httpRequest = http.createHttp();
      const response = await httpRequest.request(
        `${SERVER_URL}/api/annotation/custom-gestures?deviceId=${this.deviceId}&gestureId=${id}`,
        {
          method: http.RequestMethod.DELETE,
          header: this.getJsonHeaders(),
          connectTimeout: 10000,
          readTimeout: 10000
        }
      );
      
      try {
        const respBody = response.result as string;
        const respObj = JSON.parse(respBody) as ApiResponse<Object>;
        if (respObj.code === 200) {
          console.log('[Annotation] 自定义手势已从服务器删除:', id);
        } else {
          console.warn('[Annotation] 服务器删除失败:', respObj.message);
        }
      } catch (e) {
        const err = e as Error;
        console.warn('[Annotation] 解析响应失败:', JSON.stringify(err));
      }
    } catch (e) {
      const err = e as Error;
      console.warn('[Annotation] 删除请求异常:', JSON.stringify(err));
    }
    
    if (this.selectedGesture === id) {
      this.selectedGesture = 'fist';
    }
    this.statusMessage = '✅ 已删除自定义手势';
  }

  getAllGestures(): GestureStat[] {
    return [...this.gestureStats, ...this.customGestures];
  }

  // ======================== 网络请求 ========================

  private async loadStats() {
    this.isLoading = true;
    try {
      const httpRequest = http.createHttp();
      const response = await httpRequest.request(
        `${SERVER_URL}/api/annotation/stats`,
        {
          method: http.RequestMethod.GET,
          header: this.getAuthHeaders(),
          connectTimeout: 5000,
          readTimeout: 5000
        }
      );
      
      if (response.responseCode === 200) {
        try {
          const data: AnnotationStatsResponse = JSON.parse(response.result as string) as AnnotationStatsResponse;
          const countsMap: Map<string, number> = new Map();
          (data?.gestureCounts ?? []).forEach((s: GestureCount) => {
            countsMap.set(s.gesture, s.count ?? 0);
          });

          // 内置手势统计
          this.gestureStats = this.GESTURES.map((g: GestureStat): GestureStat => ({
            gesture: g.gesture,
            label: g.label,
            icon: g.icon,
            count: countsMap.get(g.gesture) ?? 0
          }));

          // 自定义手势统计（包含服务器返回但本地未缓存的手势）
          const customMap: Map<string, GestureStat> = new Map();
          this.customGestures.forEach((g: GestureStat) => {
            customMap.set(g.gesture, {
              gesture: g.gesture,
              label: g.label,
              icon: g.icon,
              count: countsMap.get(g.gesture) ?? g.count ?? 0
            });
          });

          // 将服务器返回但本地没有的自定义手势加入列表
          (data?.gestureCounts ?? []).forEach((s: GestureCount) => {
            const isBuiltIn = this.GESTURES.some(def => def.gesture === s.gesture);
            if (!isBuiltIn && !customMap.has(s.gesture)) {
              customMap.set(s.gesture, {
                gesture: s.gesture,
                label: s.gesture,
                icon: '✋',
                count: s.count ?? 0
              });
            }
          });

          this.customGestures = Array.from(customMap.values());
          this.saveCustomGestures();

          this.totalSamples = data?.totalSamples ?? 0;
          this.cachedSamples = data?.cachedSamples ?? 0;
        } catch (e) {
          const err = e as Error;
          console.warn('[Annotation] 解析统计失败:', JSON.stringify(err));
        }
      } else {
        console.warn('[Annotation] 加载统计失败，响应码:', response.responseCode);
      }
    } catch (e) {
      const err = e as Error;
      console.warn('[Annotation] 加载统计异常:', JSON.stringify(err));
    } finally {
      this.isLoading = false;
    }
  }

  private async loadRecentRecords() {
    try {
      const httpRequest = http.createHttp();
      const response = await httpRequest.request(
        `${SERVER_URL}/api/annotation/records?limit=10`,
        {
          method: http.RequestMethod.GET,
          header: this.getAuthHeaders(),
          connectTimeout: 5000,
          readTimeout: 5000
        }
      );
      
      if (response.responseCode === 200) {
        try {
          const responseData: AnnotationRecord[] = JSON.parse(response.result as string) as AnnotationRecord[];
          this.recentRecords = responseData.map((r: AnnotationRecord): AnnotationRecord => ({
            id: r.id ?? 0,
            gesture: r.gesture ?? '',
            duration: r.duration ?? 0,
            sampleCount: r.sampleCount ?? 0,
            quality: r.quality ?? 0,
            createdTime: r.createdTime ?? ''
          }));
        } catch (e) {
          const err = e as Error;
          console.warn('[Annotation] 解析记录失败:', JSON.stringify(err));
        }
      } else {
        console.warn('[Annotation] 加载记录失败，响应码:', response.responseCode);
      }
    } catch (e) {
      const err = e as Error;
      console.warn('[Annotation] 加载记录异常:', JSON.stringify(err));
    }
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
      const response = await httpRequest.request(
        `${SERVER_URL}/api/annotation/start`,
        {
          method: http.RequestMethod.POST,
          header: this.getJsonHeaders(),
          extraData: JSON.stringify(body),
          connectTimeout: 5000,
          readTimeout: 10000
        }
      );
      
      if (response.responseCode === 200) {
        try {
          const data: StartRecordingResponse = JSON.parse(response.result as string) as StartRecordingResponse;
          console.info('[Annotation] 录制启动:', JSON.stringify(data));
        } catch (e) {
          const err = e as Error;
          console.warn('[Annotation] 解析启动响应失败:', JSON.stringify(err));
        }
      } else {
        this.statusMessage = `录制启动失败 (${response.responseCode})`;
      }
    } catch (e) {
      const err = e as Error;
      console.warn('[Annotation] 录制请求异常:', JSON.stringify(err));
      this.statusMessage = '无法连接服务器，使用本地录制模式';
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
      const response = await httpRequest.request(
        `${SERVER_URL}/api/annotation/stop`,
        {
          method: http.RequestMethod.POST,
          header: this.getJsonHeaders(),
          extraData: JSON.stringify(body),
          connectTimeout: 5000,
          readTimeout: 10000
        }
      );
      
      if (response.responseCode === 200) {
        try {
          const data: StopRecordingResponse = JSON.parse(response.result as string) as StopRecordingResponse;
          this.statusMessage = `✅ 已保存 ${data?.sampleCount ?? 0} 个样本`;
          await this.loadStats();
        } catch (e) {
          const err = e as Error;
          console.warn('[Annotation] 解析停止响应失败:', JSON.stringify(err));
        }
      } else {
        console.warn('[Annotation] 停止录制请求失败，响应码:', response.responseCode);
      }
    } catch (e) {
      const err = e as Error;
      console.warn('[Annotation] 停止录制异常:', JSON.stringify(err));
    }
  }

  // ======================== 录制控制 ========================

  startRecording() {
    if (this.isRecording) return;
    this.isRecording = true;
    this.countdown = this.recordDuration;
    this.statusMessage = `🔴 正在录制 ${this.getGestureLabel(this.selectedGesture)}...`;
    this.startRecordingRequest();

    // 倒计时
    this.countdownTimer = setInterval((): void => {
      this.countdown -= 1;
      if (this.countdown <= 0) {
        this.stopRecording();
      }
    }, 1000) as number;
  }

  stopRecording() {
    if (!this.isRecording) return;
    this.isRecording = false;
    clearInterval(this.countdownTimer);
    this.countdownTimer = -1;
    this.countdown = 0;
    this.statusMessage = '⏹ 录制已停止，正在上传...';
    this.stopRecordingRequest();
  }

  private getGestureLabel(gesture: string): string {
    const allGestures = this.getAllGestures();
    const found = allGestures.find(g => g.gesture === gesture);
    return found ? `${found.icon} ${found.label}` : gesture;
  }

  private getMaxCount(): number {
    return Math.max(...this.getAllGestures().map(g => g.count), 1);
  }

  // ======================== UI 构建 ========================

  build() {
    Stack() {
      Column() {
        // 顶部导航栏
        CustomAppBar({ title: '数据标注' })

        Tabs({ barPosition: BarPosition.Start }) {

          // ——— Tab 1: 采集 ———
          TabContent() {
            Scroll() {
              Column() {

                // 手势选择卡片
                Column() {
                  Row() {
                    Text('选择手势类型')
                      .fontSize(16)
                      .fontWeight(FontWeight.Bold)
                    Blank()
                    Button('+ 新增', { type: ButtonType.Normal, stateEffect: true })
                      .fontSize(13)
                      .height(30)
                      .padding({ left: 12, right: 12 })
                      .backgroundColor('#10B981')
                      .onClick(() => {
                        this.showCustomDialog = true;
                      })
                  }
                  .width('100%')
                  .margin({ bottom: 14 })
                  .alignItems(VerticalAlign.Center)

                  GridRow({ columns: 3, gutter: { x: 10, y: 10 } }) {
                    ForEach(this.gestureStats, (g: GestureStat) => {
                      GridCol() {
                        Column() {
                          Text(g.icon)
                            .fontSize(30)
                            .margin({ bottom: 4 })
                          Text(g.label)
                            .fontSize(14)
                            .fontColor(this.selectedGesture === g.gesture ? Color.White : '#374151')
                        }
                        .width('100%')
                        .padding({ top: 12, bottom: 12 })
                        .backgroundColor(this.selectedGesture === g.gesture ? '#3B82F6' : '#F3F4F6')
                        .borderRadius(10)
                        .justifyContent(FlexAlign.Center)
                        .onClick(() => {
                          if (!this.isRecording) {
                            this.selectedGesture = g.gesture;
                          }
                        })
                      }
                    })

                    ForEach(this.customGestures, (g: GestureStat) => {
                      GridCol() {
                        Stack({ alignContent: Alignment.TopEnd }) {
                          Column() {
                            Text(g.icon)
                              .fontSize(30)
                              .margin({ bottom: 4 })
                            Text(g.label)
                              .fontSize(14)
                              .fontColor(this.selectedGesture === g.gesture ? Color.White : '#374151')
                              .maxLines(1)
                              .textOverflow({ overflow: TextOverflow.Ellipsis })
                          }
                          .width('100%')
                          .padding({ top: 12, bottom: 12 })
                          .backgroundColor(this.selectedGesture === g.gesture ? '#8B5CF6' : '#F3E8FF')
                          .borderRadius(10)
                          .justifyContent(FlexAlign.Center)
                          .onClick(() => {
                            if (!this.isRecording) {
                              this.selectedGesture = g.gesture;
                            }
                          })

                          Button('X', { type: ButtonType.Circle, stateEffect: true })
                            .width(24)
                            .height(24)
                            .fontSize(12)
                            .backgroundColor('#EF4444')
                            .fontColor(Color.White)
                            .margin({ top: 4, right: 4 })
                            .onClick(() => {
                              this.deleteCustomGestureWithServer(g.gesture);
                            })
                        }
                        .width('100%')
                      }
                    })
                  }
                }
                .width('100%')
                .padding(16)
                .backgroundColor(Color.White)
                .borderRadius(12)
                .shadow({
                  radius: 8,
                  color: '#00000010',
                  offsetX: 0,
                  offsetY: 2
                })
                .margin({ bottom: 14 })

                // 录制时长配置
                Column() {
                  Row() {
                    Text('录制时长')
                      .fontSize(16)
                      .fontWeight(FontWeight.Bold)
                    Blank()
                    Text(`${this.recordDuration} 秒`)
                      .fontSize(16)
                      .fontColor('#3B82F6')
                      .fontWeight(FontWeight.Bold)
                  }
                  .width('100%')
                  .margin({ bottom: 12 })

                  Slider({
                    value: this.recordDuration,
                    min: 1,
                    max: 10,
                    step: 1,
                    style: SliderStyle.OutSet
                  })
                    .width('100%')
                    .trackColor('#E5E7EB')
                    .selectedColor('#3B82F6')
                    .onChange((value: number) => {
                      if (!this.isRecording) {
                        this.recordDuration = Math.round(value);
                      }
                    })

                  Row() {
                    Text('1 秒').fontSize(12).fontColor('#9CA3AF')
                    Blank()
                    Text('10 秒').fontSize(12).fontColor('#9CA3AF')
                  }
                  .width('100%')
                  .margin({ top: 4 })
                }
                .width('100%')
                .padding(16)
                .backgroundColor(Color.White)
                .borderRadius(12)
                .shadow({
                  radius: 8,
                  color: '#00000010',
                  offsetX: 0,
                  offsetY: 2
                })
                .margin({ bottom: 14 })

                // 录制控制面板
                Column() {
                  // 状态提示
                  Text(this.statusMessage)
                    .fontSize(15)
                    .fontColor('#6B7280')
                    .textAlign(TextAlign.Center)
                    .margin({ bottom: 16 })

                  // 倒计时显示
                  if (this.isRecording) {
                    Stack() {
                      Circle({ width: 100, height: 100 })
                        .fill('#FEE2E2')
                      Text(`${this.countdown}`)
                        .fontSize(42)
                        .fontWeight(FontWeight.Bold)
                        .fontColor('#EF4444')
                    }
                    .margin({ bottom: 20 })
                  }

                  // 录制按钮
                  Button(this.isRecording ? '⏹ 停止录制' : '🔴 开始录制')
                    .width('70%')
                    .height(52)
                    .fontSize(18)
                    .backgroundColor(this.isRecording ? '#EF4444' : '#10B981')
                    .onClick(() => {
                      if (this.isRecording) {
                        this.stopRecording();
                      } else {
                        this.startRecording();
                      }
                    })
                }
                .width('100%')
                .padding(20)
                .backgroundColor(Color.White)
                .borderRadius(12)
                .shadow({
                  radius: 8,
                  color: '#00000010',
                  offsetX: 0,
                  offsetY: 2
                })
                .margin({ bottom: 14 })

                // 缓存信息
                if (this.cachedSamples > 0) {
                  Row() {
                    Text(`📦 本地缓存: ${this.cachedSamples} 帧`)
                      .fontSize(14)
                      .fontColor('#F59E0B')
                    Blank()
                    Button('同步上传')
                      .fontSize(13)
                      .height(32)
                      .backgroundColor('#F59E0B')
                      .onClick(() => {
                        this.loadStats();
                      })
                  }
                  .width('100%')
                  .padding({
                    left: 16,
                    right: 16,
                    top: 12,
                    bottom: 12
                  })
                  .backgroundColor('#FFFBEB')
                  .borderRadius(10)
                  .margin({ bottom: 80 })
                }

              }
              .width('100%')
              .padding({ left: 16, right: 16, top: 16 })
            }
          }
          .tabBar('采集')

          // ——— Tab 2: 统计 ———
          TabContent() {
            Scroll() {
              Column() {

                // 总量卡片
                Row() {
                  Column() {
                    Text(`${this.totalSamples}`)
                      .fontSize(36)
                      .fontWeight(FontWeight.Bold)
                      .fontColor('#3B82F6')
                    Text('总样本数')
                      .fontSize(13)
                      .fontColor('#6B7280')
                  }
                  .layoutWeight(1)
                  .alignItems(HorizontalAlign.Center)

                  Column() {
                    Text(`${this.getAllGestures().filter(g => g.count > 0).length}`)
                      .fontSize(36)
                      .fontWeight(FontWeight.Bold)
                      .fontColor('#10B981')
                    Text('已覆盖手势')
                      .fontSize(13)
                      .fontColor('#6B7280')
                  }
                  .layoutWeight(1)
                  .alignItems(HorizontalAlign.Center)

                  Column() {
                    Text(`${this.getAllGestures().length}`)
                      .fontSize(36)
                      .fontWeight(FontWeight.Bold)
                      .fontColor('#8B5CF6')
                    Text('手势类别')
                      .fontSize(13)
                      .fontColor('#6B7280')
                  }
                  .layoutWeight(1)
                  .alignItems(HorizontalAlign.Center)
                }
                .width('100%')
                .padding(20)
                .backgroundColor(Color.White)
                .borderRadius(12)
                .shadow({
                  radius: 8,
                  color: '#00000010',
                  offsetX: 0,
                  offsetY: 2
                })
                .margin({ bottom: 14 })

                // 手势分布柱状图
                Column() {
                  Row() {
                    Text('手势数据分布')
                      .fontSize(16)
                      .fontWeight(FontWeight.Bold)
                    Blank()
                    if (this.isLoading) {
                      LoadingProgress().width(20).height(20).color('#3B82F6')
                    } else {
                      Button('刷新')
                        .fontSize(13)
                        .height(30)
                        .backgroundColor('#EFF6FF')
                        .fontColor('#3B82F6')
                        .onClick(() => {
                          this.loadStats();
                        })
                    }
                  }
                  .width('100%')
                  .margin({ bottom: 16 })

                  ForEach(this.getAllGestures(), (g: GestureStat) => {
                    Row() {
                      Text(`${g.icon} ${g.label}`)
                        .fontSize(14)
                        .width(80)
                        .fontColor('#374151')

                      Stack({ alignContent: Alignment.Start }) {
                        Rect()
                          .width('100%')
                          .height(24)
                          .fill('#F3F4F6')
                          .radius(4)
                        Rect()
                          .width(`${Math.max(g.count / this.getMaxCount() * 100, 2)}%`)
                          .height(24)
                          .fill('#3B82F6')
                          .radius(4)
                      }
                      .layoutWeight(1)
                      .margin({ left: 10, right: 10 })

                      Text(`${g.count}`)
                        .fontSize(14)
                        .width(40)
                        .textAlign(TextAlign.End)
                        .fontColor('#6B7280')
                    }
                    .width('100%')
                    .margin({ bottom: 10 })
                  })
                }
                .width('100%')
                .padding(16)
                .backgroundColor(Color.White)
                .borderRadius(12)
                .shadow({
                  radius: 8,
                  color: '#00000010',
                  offsetX: 0,
                  offsetY: 2
                })
                .margin({ bottom: 14 })

                // 最近记录
                Column() {
                  Row() {
                    Text('最近标注记录')
                      .fontSize(16)
                      .fontWeight(FontWeight.Bold)
                    Blank()
                    Button('加载')
                      .fontSize(13)
                      .height(30)
                      .backgroundColor('#EFF6FF')
                      .fontColor('#3B82F6')
                      .onClick(() => {
                        this.loadRecentRecords();
                      })
                  }
                  .width('100%')
                  .margin({ bottom: 12 })

                  if (this.recentRecords.length > 0) {
                    ForEach(this.recentRecords, (r: AnnotationRecord) => {
                      Row() {
                        Column() {
                          Text(this.getGestureLabel(r.gesture))
                            .fontSize(15)
                            .fontWeight(FontWeight.Medium)
                          Text(r.createdTime)
                            .fontSize(12)
                            .fontColor('#9CA3AF')
                            .margin({ top: 2 })
                        }
                        .alignItems(HorizontalAlign.Start)
                        .layoutWeight(1)

                        Column() {
                          Text(`${r.sampleCount} 帧`)
                            .fontSize(14)
                            .fontColor('#6B7280')
                          Text(`质量 ${(r.quality * 100).toFixed(0)}%`)
                            .fontSize(12)
                            .fontColor(r.quality >= 0.8 ? '#10B981' : '#F59E0B')
                            .margin({ top: 2 })
                        }
                        .alignItems(HorizontalAlign.End)
                      }
                      .width('100%')
                      .padding({ top: 10, bottom: 10 })
                      .borderStyle(BorderStyle.Dashed)
                    })
                  } else {
                    Column() {
                      Text('📋')
                        .fontSize(48)
                        .margin({ bottom: 10 })
                      Text('暂无记录，点击"加载"获取')
                        .fontSize(14)
                        .fontColor('#9CA3AF')
                    }
                    .width('100%')
                    .height(120)
                    .justifyContent(FlexAlign.Center)
                  }
                }
                .width('100%')
                .padding(16)
                .backgroundColor(Color.White)
                .borderRadius(12)
                .shadow({
                  radius: 8,
                  color: '#00000010',
                  offsetX: 0,
                  offsetY: 2
                })
                .margin({ bottom: 80 })

              }
              .width('100%')
              .padding({ left: 16, right: 16, top: 16 })
            }
          }
          .tabBar('统计')

        }
        .width('100%')
        .layoutWeight(1)
        .barMode(BarMode.Fixed)

        // 底部导航栏
        BottomNavBar({ currentIndex: -1 })
      }
      .width('100%')
      .height('100%')
      .backgroundColor('#F9FAFB')

      // 自定义手势对话框 - 叠加层
      if (this.showCustomDialog) {
        Column() {
          Blank().layoutWeight(1)

          Column() {
            Row() {
              Text('添加自定义手势')
                .fontSize(18)
                .fontWeight(FontWeight.Bold)
              Blank()
              // 实时预览
              Column() {
                Text(this.customGestureIcon)
                  .fontSize(40)
                  .margin({ bottom: 4 })
                Text(this.customGestureName || '输入名称')
                  .fontSize(12)
                  .fontColor(this.customGestureName ? '#374151' : '#9CA3AF')
                  .maxLines(1)
                  .textOverflow({ overflow: TextOverflow.Ellipsis })
              }
              .padding({ left: 12, right: 12, top: 8, bottom: 8 })
              .backgroundColor('#F3F4F6')
              .borderRadius(8)
              .alignItems(HorizontalAlign.Center)
            }
            .width('100%')
            .margin({ bottom: 20 })
            .alignItems(VerticalAlign.Center)

            // 手势图标选择
            Text('手势图标:')
              .fontSize(14)
              .margin({ bottom: 8 })

            Scroll() {
              GridRow({ columns: 4, gutter: { x: 8, y: 8 } }) {
                ForEach(['👊', '👋', '🤘', '🤟', '✌️', '🤞', '🤝', '👐',
                  '🙌', '👏', '🤲', '🙏', '💪', '☝️', '👆', '👇'], (icon: string) => {
                  GridCol() {
                    Text(icon)
                      .fontSize(28)
                      .width('100%')
                      .height(50)
                      .textAlign(TextAlign.Center)
                      .backgroundColor(this.customGestureIcon === icon ? '#3B82F6' : '#F3F4F6')
                      .borderRadius(8)
                      .onClick(() => {
                        this.customGestureIcon = icon;
                      })
                  }
                })
              }
              .width('100%')
            }
            .width('100%')
            .height(180)
            .scrollable(ScrollDirection.Vertical)
            .margin({ bottom: 16 })

            // 手势名称输入
            Column() {
              Row() {
                Text('手势名称:')
                  .fontSize(14)
                  .width(70)
                Text(`${this.customGestureName.length}/15`)
                  .fontSize(12)
                  .fontColor(this.customGestureName.length > 15 ? '#EF4444' : '#9CA3AF')
              }
              .width('100%')
              .margin({ bottom: 8 })

              TextInput({
                placeholder: '请输入手势名称（如：胜利、Peace）',
                text: this.customGestureName
              })
                .width('100%')
                .height(40)
                .padding({ left: 12, right: 12 })
                .backgroundColor('#F3F4F6')
                .borderRadius(8)
                .maxLength(15)
                .onChange((value: string) => {
                  this.customGestureName = value;
                })
            }
            .width('100%')
            .margin({ bottom: 24 })

            // 操作按钮
            Row() {
              Button('取消')
                .layoutWeight(1)
                .height(44)
                .backgroundColor('#E5E7EB')
                .fontColor('#374151')
                .onClick(() => {
                  this.showCustomDialog = false;
                  this.customGestureName = '';
                  this.customGestureIcon = '👋';
                })

              Blank().width(12)

              // 确定按钮：只有输入手势名称才能点击
              Button(this.customGestureName.trim() ? '添加手势' : '请输入名称')
                .layoutWeight(1)
                .height(44)
                .backgroundColor(this.customGestureName.trim() ? '#10B981' : '#D1D5DB')
                .fontColor(this.customGestureName.trim() ? '#FFFFFF' : '#9CA3AF')
                .enabled(this.customGestureName.trim().length > 0)
                .onClick(() => {
                  this.addCustomGesture();
                })
            }
            .width('100%')
            .margin({ top: 8 })
          }
          .width('90%')
          .padding(20)
          .backgroundColor(Color.White)
          .borderRadius(16)
          .shadow({
            radius: 8,
            color: '#00000020',
            offsetX: 0,
            offsetY: 2
          })

          Blank().layoutWeight(1)
        }
        .width('100%')
        .height('100%')
        .backgroundColor('rgba(0,0,0,0.5)')
        .justifyContent(FlexAlign.Center)
        .alignItems(HorizontalAlign.Center)
        .zIndex(1000)
        .onClick(() => {
          this.showCustomDialog = false;
        })
      }
    }
  }
}
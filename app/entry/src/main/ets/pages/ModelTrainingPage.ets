// ==============================================================================
// ModelTrainingPage.ets - 模型训练管理页面
// ==============================================================================
// 功能:
// 1. 查看标注数据统计
// 2. 配置训练参数（Epochs、Batch Size、Learning Rate等）
// 3. 发起训练任务
// 4. 实时查看训练进度和结果
// 集成到华为 ICT 赛道应用
// ==============================================================================

import http from '@ohos.net.http';
import webSocket from '@ohos.net.webSocket';
import preferences from '@ohos.data.preferences';
import { CustomAppBar } from './CustomAppBar';
import { BottomNavBar } from './BottomNavBar';

const SERVER_URL: string = 'http://1.95.65.51:8080';

interface HttpHeaders {
  Authorization?: string;
  'Content-Type'?: string;
}

interface UserContext {
  userId?: number;
  username?: string;
}

interface TrainingTask {
  task_id: number;
  task_name: string;
  status: string;
  progress: number;
  current_epoch: number;
  total_epochs: number;
  accuracy: number;
  created_time: string;
  error_message?: string;
}

interface TrainingTaskRaw {
  task_id?: number;
  id?: number;
  task_name?: string;
  taskName?: string;
  status?: string;
  taskStatus?: string;
  progress?: number;
  progressPercent?: number;
  current_epoch?: number;
  currentEpoch?: number;
  total_epochs?: number;
  totalEpochs?: number;
  accuracy?: number;
  test_accuracy?: number;
  testAccuracy?: number;
  val_accuracy?: number;
  valAccuracy?: number;
  train_accuracy?: number;
  trainAccuracy?: number;
  best_val_accuracy?: number;
  bestValAccuracy?: number;
  created_time?: string;
  createdTime?: string;
  error_message?: string;
  errorMessage?: string;
}

interface TrainingConfig {
  epochs: number;
  batchSize: number;
  learningRate: number;
  windowSize: number;
  modelType: string;
}

interface TrainingDataFilter {
  gestures: string[];
  minQualityScore: number;
}

interface CreateTrainingTaskRequest {
  taskName: string;
  config: TrainingConfig;
  dataFilter: TrainingDataFilter;
  createdBy: string;
}

interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

interface CreateTrainingTaskData {
  task_id: number;
}

@Entry
@Component
struct ModelTrainingPage {
  @State taskName: string = '训练任务_' + new Date().toISOString().split('T')[0];
  @State epochs: number = 50;
  @State batchSize: number = 32;
  @State learningRate: number = 0.001;
  @State windowSize: number = 150;
  
  @State trainingTasks: TrainingTask[] = [];
  @State currentTask: TrainingTask | null = null;
  @State statusMessage: string = '';
  
  private ws: webSocket.WebSocket | null = null;
  private pollingTimer: number = -1;

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
      if (uname && uname.length > 0) {
        ctx.username = uname;
      }
    } catch (e) {
      // ignore storage errors
    }
    return ctx;
  }

  private normalizeTrainingTask(raw: TrainingTaskRaw): TrainingTask {
    const accuracyCandidates: Array<number | undefined> = [
      raw?.best_val_accuracy,
      raw?.bestValAccuracy,
      raw?.test_accuracy,
      raw?.testAccuracy,
      raw?.val_accuracy,
      raw?.valAccuracy,
      raw?.accuracy,
      raw?.train_accuracy,
      raw?.trainAccuracy
    ];
    const accuracyValue = accuracyCandidates.find((v) => typeof v === 'number') ?? 0;

    return {
      task_id: raw?.task_id ?? raw?.id ?? 0,
      task_name: raw?.task_name ?? raw?.taskName ?? '',
      status: raw?.status ?? raw?.taskStatus ?? '',
      progress: raw?.progress ?? raw?.progressPercent ?? 0,
      current_epoch: raw?.current_epoch ?? raw?.currentEpoch ?? 0,
      total_epochs: raw?.total_epochs ?? raw?.totalEpochs ?? 0,
      accuracy: accuracyValue,
      created_time: raw?.created_time ?? raw?.createdTime ?? '',
      error_message: raw?.error_message ?? raw?.errorMessage ?? ''
    };
  }

  /**
   * 创建训练任务
   */
  async createTrainingTask() {
    const httpRequest = http.createHttp();
    const userCtx = this.getUserContext();
    const createdBy = userCtx.username && userCtx.username.length > 0 ? userCtx.username : 'app_user';
    
    const requestBody: CreateTrainingTaskRequest = {
      taskName: this.taskName,
      config: {
        epochs: this.epochs,
        batchSize: this.batchSize,
        learningRate: this.learningRate,
        windowSize: this.windowSize,
        modelType: 'cnn_lstm'
      },
      dataFilter: {
        gestures: ['fist', 'ok', 'pinch', 'relax', 'sidegrip', 'ye'],
        minQualityScore: 0.8
      },
      createdBy: createdBy
    };
    
    try {
      const response = await httpRequest.request(
        `${SERVER_URL}/api/training/create`,
        {
          method: http.RequestMethod.POST,
          header: this.getJsonHeaders(),
          extraData: JSON.stringify(requestBody),
          readTimeout: 10000,
          connectTimeout: 5000
        }
      );
      
      const result: ApiResponse<CreateTrainingTaskData> =
        JSON.parse(response.result as string) as ApiResponse<CreateTrainingTaskData>;
      
      if (result.code === 200) {
        this.statusMessage = '训练任务已创建，等待执行...';
        const taskId = result.data.task_id;
        this.startPollingTaskStatus(taskId);
      } else {
        this.statusMessage = `创建失败: ${result.message || ''}`;
      }
    } catch (error) {
      this.statusMessage = `创建失败: ${JSON.stringify(error)}`;
    }
  }

  /**
   * 轮询任务状态
   */
  async startPollingTaskStatus(taskId: number) {
    if (this.pollingTimer !== -1) {
      clearInterval(this.pollingTimer);
    }
    
    this.pollingTimer = setInterval(async () => {
      try {
        const task = await this.getTaskStatus(taskId);
        this.currentTask = task;
        
        if (task.status === 'completed' || task.status === 'failed') {
          clearInterval(this.pollingTimer);
          this.pollingTimer = -1;
          this.statusMessage = task.status === 'completed' 
            ? `训练完成！准确率: ${(task.accuracy * 100).toFixed(2)}%`
            : '训练失败';
          
          this.loadTrainingTasks();
        }
      } catch (error) {
        console.error('轮询任务状态失败:', error);
      }
    }, 2000);
  }

  /**
   * 获取任务状态
   */
  async getTaskStatus(taskId: number): Promise<TrainingTask> {
    const httpRequest = http.createHttp();
    
    const response = await httpRequest.request(
      `${SERVER_URL}/api/training/task/${taskId}`,
      {
        method: http.RequestMethod.GET,
        header: this.getAuthHeaders(),
        readTimeout: 5000,
        connectTimeout: 5000
      }
    );
    
    const result: ApiResponse<TrainingTaskRaw> =
      JSON.parse(response.result as string) as ApiResponse<TrainingTaskRaw>;
    
    if (result.code !== 200) {
      throw new Error(result.message);
    }
    
    return this.normalizeTrainingTask(result.data);
  }

  /**
   * 加载训练任务列表
   */
  async loadTrainingTasks() {
    const httpRequest = http.createHttp();
    
    try {
      const response = await httpRequest.request(
        `${SERVER_URL}/api/training/tasks?limit=10`,
        {
          method: http.RequestMethod.GET,
          header: this.getAuthHeaders(),
          readTimeout: 5000,
          connectTimeout: 5000
        }
      );
      
      const result: ApiResponse<TrainingTaskRaw[]> =
        JSON.parse(response.result as string) as ApiResponse<TrainingTaskRaw[]>;
      
      if (result.code === 200) {
        const list: TrainingTaskRaw[] = result.data ?? [];
        this.trainingTasks = list.map((item: TrainingTaskRaw) => this.normalizeTrainingTask(item));
      }
    } catch (error) {
      console.error('加载任务列表失败:', error);
    }
  }

  aboutToAppear() {
    this.syncAuthFromPreferences();
    this.loadTrainingTasks();
  }

  aboutToDisappear() {
    if (this.pollingTimer !== -1) {
      clearInterval(this.pollingTimer);
    }
    if (this.ws) {
      this.ws.close();
    }
  }

  build() {
    Column() {
      // 顶部导航栏
      CustomAppBar({ title: '模型训练', showSettings: false })

      Tabs() {
        // Tab 1: 新建训练
        TabContent() {
          Scroll() {
            Column() {
              // 训练参数配置卡片
              Column() {
                Text('⚙️ 训练参数配置')
                  .fontSize(18)
                  .fontWeight(FontWeight.Bold)
                  .margin({ bottom: 15 })
                
                // 任务名称
                Row() {
                  Text('任务名称:')
                    .fontSize(14)
                    .width('30%')
                  TextInput({ text: this.taskName })
                    .width('70%')
                    .onChange((value: string) => {
                      this.taskName = value;
                    })
                }
                .width('100%')
                .margin({ bottom: 12 })
                
                // Epochs
                Row() {
                  Text('训练轮数:')
                    .fontSize(14)
                    .width('30%')
                  Slider({
                    value: this.epochs,
                    min: 10,
                    max: 100,
                    step: 10
                  })
                    .width('50%')
                    .onChange((value: number) => {
                      this.epochs = value;
                    })
                  Text(`${this.epochs}`)
                    .fontSize(14)
                    .width('20%')
                    .textAlign(TextAlign.End)
                }
                .width('100%')
                .margin({ bottom: 12 })
                
                // Batch Size
                Row() {
                  Text('批次大小:')
                    .fontSize(14)
                    .width('30%')
                  Slider({
                    value: this.batchSize,
                    min: 16,
                    max: 128,
                    step: 16
                  })
                    .width('50%')
                    .onChange((value: number) => {
                      this.batchSize = value;
                    })
                  Text(`${this.batchSize}`)
                    .fontSize(14)
                    .width('20%')
                    .textAlign(TextAlign.End)
                }
                .width('100%')
                .margin({ bottom: 12 })
                
                // Window Size
                Row() {
                  Text('窗口大小:')
                    .fontSize(14)
                    .width('30%')
                  Slider({
                    value: this.windowSize,
                    min: 50,
                    max: 300,
                    step: 50
                  })
                    .width('50%')
                    .onChange((value: number) => {
                      this.windowSize = value;
                    })
                  Text(`${this.windowSize}`)
                    .fontSize(14)
                    .width('20%')
                    .textAlign(TextAlign.End)
                }
                .width('100%')
              }
              .width('100%')
              .padding(20)
              .backgroundColor(Color.White)
              .borderRadius(12)
              .shadow({ radius: 8, color: '#00000010', offsetX: 0, offsetY: 2 })
              .margin({ bottom: 15 })

              // 开始训练按钮
              Button('🚀 开始训练')
                .width('90%')
                .height(50)
                .fontSize(18)
                .backgroundColor('#3B82F6')
                .onClick(() => {
                  this.createTrainingTask();
                })
              
              if (this.statusMessage) {
                Text(this.statusMessage)
                  .fontSize(14)
                  .fontColor('#6B7280')
                  .margin({ top: 10 })
                  .textAlign(TextAlign.Center)
              }

              // 当前训练进度
              if (this.currentTask && this.currentTask.status === 'running') {
                Column() {
                  Text('⏳ 训练中...')
                    .fontSize(18)
                    .fontWeight(FontWeight.Bold)
                    .margin({ bottom: 12 })
                  
                  Progress({
                    value: this.currentTask.progress || 0,
                    total: 100,
                    type: ProgressType.Linear
                  })
                    .width('100%')
                    .margin({ bottom: 12 })
                  
                  Text(`Epoch: ${this.currentTask.current_epoch}/${this.currentTask.total_epochs}`)
                    .fontSize(16)
                    .margin({ bottom: 6 })
                  
                  Text(`进度: ${(this.currentTask.progress || 0).toFixed(1)}%`)
                    .fontSize(16)
                }
                .width('100%')
                .padding(20)
                .backgroundColor('#FEF3C7')
                .borderRadius(12)
                .margin({ top: 15, bottom: 80 })
              }
            }
            .width('100%')
            .padding({ left: 16, right: 16, top: 16 })
          }
        }
        .tabBar('新建训练')

        // Tab 2: 训练历史
        TabContent() {
          Scroll() {
            Column() {
              if (this.trainingTasks.length > 0) {
                ForEach(this.trainingTasks, (task: TrainingTask) => {
                  Column() {
                    Row() {
                      Text(task.task_name)
                        .fontSize(16)
                        .fontWeight(FontWeight.Medium)
                      Blank()
                      Text(task.status)
                        .fontSize(14)
                        .fontColor(task.status === 'completed' ? '#10B981' : '#F59E0B')
                    }
                    .width('100%')
                    .margin({ bottom: 8 })
                    
                    if (task.status === 'completed') {
                      Text(`准确率: ${(task.accuracy * 100).toFixed(2)}%`)
                        .fontSize(14)
                        .fontColor('#6B7280')
                        .margin({ bottom: 6 })
                    }

                    if (task.status === 'failed' && task.error_message) {
                      Text(`错误: ${task.error_message}`)
                        .fontSize(12)
                        .fontColor('#EF4444')
                        .margin({ bottom: 6 })
                    }
                    if (task.status === 'completed' && task.error_message) {
                      Text(`警告: ${task.error_message}`)
                        .fontSize(12)
                        .fontColor('#F59E0B')
                        .margin({ bottom: 6 })
                    }
                    
                    Text(`创建时间: ${task.created_time}`)
                                        .fontSize(12)
                      .fontColor('#9CA3AF')
                  }
                  .width('100%')
                  .padding(15)
                  .backgroundColor(Color.White)
                  .borderRadius(10)
                  .shadow({ radius: 8, color: '#00000010', offsetX: 0, offsetY: 2 })
                  .margin({ bottom: 10 })
                })
              } else {
                Column() {
                  Text('📋')
                    .fontSize(64)
                    .margin({ bottom: 12 })
                  Text('暂无训练任务')
                    .fontSize(16)
                    .fontColor('#9CA3AF')
                }
                .width('100%')
                .height(200)
                .justifyContent(FlexAlign.Center)
              }
            }
            .width('100%')
            .padding({ left: 16, right: 16, top: 16, bottom: 80 })
          }
        }
        .tabBar('训练历史')
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
  }
}

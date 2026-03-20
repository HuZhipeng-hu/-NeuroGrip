// ==============================================================================
// ModelManagePage.ets - 模型管理页面
// ==============================================================================
// 功能:
// 1. 查看所有模型版本列表
// 2. 部署模型到OrangePi边缘设备
// 3. 激活/切换模型版本
// 4. 查看模型性能指标和元数据
// 集成到华为 ICT 赛道应用
// ==============================================================================

import http from '@ohos.net.http';
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

interface ModelVersion {
  id: number;
  version: string;
  modelName: string;
  accuracy: number;
  modelSizeMb: number;
  isActive: boolean;
  createdTime: string;
  modelFormat: string;
}

interface ModelVersionRaw {
  id?: number;
  version?: string;
  modelName?: string;
  model_name?: string;
  accuracy?: number;
  modelSizeMb?: number;
  model_size_mb?: number;
  isActive?: boolean;
  is_active?: boolean;
  createdTime?: string;
  created_time?: string;
  modelFormat?: string;
  model_format?: string;
}

interface DeployModelRequest {
  version: string;
  targetType: string;
  targetDeviceId: string;
  setAsActive: boolean;
  deployMethod: string;
  deployedBy: string;
}

interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

@Entry
@Component
struct ModelManagePage {
  @State modelVersions: ModelVersion[] = [];
  @State selectedVersion: string = '';
  @State deployTarget: string = 'orangepi';
  @State deviceId: string = 'orangepi_01';
  @State statusMessage: string = '';

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

  private parseJsonSafe<T>(text: string): T | null {
    try {
      if (!text || text.length === 0) return null;
      return JSON.parse(text) as T;
    } catch (e) {
      return null;
    }
  }

  private normalizeModelVersion(raw: ModelVersionRaw): ModelVersion {
    return {
      id: raw?.id ?? 0,
      version: raw?.version ?? '',
      modelName: raw?.modelName ?? raw?.model_name ?? '',
      accuracy: raw?.accuracy ?? 0,
      modelSizeMb: raw?.modelSizeMb ?? raw?.model_size_mb ?? 0,
      isActive: raw?.isActive ?? raw?.is_active ?? false,
      createdTime: raw?.createdTime ?? raw?.created_time ?? '',
      modelFormat: raw?.modelFormat ?? raw?.model_format ?? ''
    };
  }

  /**
   * 加载模型版本列表
   */
  async loadModelVersions() {
    const httpRequest = http.createHttp();
    
    try {
      const response = await httpRequest.request(
        `${SERVER_URL}/api/model/versions?limit=20`,
        {
          method: http.RequestMethod.GET,
          header: this.getAuthHeaders(),
          readTimeout: 5000,
          connectTimeout: 5000
        }
      );
      const result = this.parseJsonSafe<ApiResponse<ModelVersionRaw[]>>(response.result as string);
      if (result && result.code === 200) {
        const list: ModelVersionRaw[] = result.data ?? [];
        this.modelVersions = list.map((item: ModelVersionRaw) => this.normalizeModelVersion(item));
      } else {
        this.statusMessage = `加载失败: ${response.responseCode}`;
      }
    } catch (error) {
      console.error('加载模型版本失败:', error);
      this.statusMessage = `加载失败: ${error}`;
    }
  }

  /**
   * 部署模型
   */
  async deployModel(version: string) {
    const httpRequest = http.createHttp();
    const userCtx = this.getUserContext();
    const deployedBy = userCtx.username && userCtx.username.length > 0 ? userCtx.username : 'app_user';
    
    const requestBody: DeployModelRequest = {
      version: version,
      targetType: this.deployTarget,
      targetDeviceId: this.deviceId,
      setAsActive: true,
      deployMethod: 'auto_download',
      deployedBy: deployedBy
    };
    
    try {
      const response = await httpRequest.request(
        `${SERVER_URL}/api/model/deploy`,
        {
          method: http.RequestMethod.POST,
          header: this.getJsonHeaders(),
          extraData: JSON.stringify(requestBody),
          readTimeout: 10000,
          connectTimeout: 5000
        }
      );
      const result = this.parseJsonSafe<ApiResponse<Record<string, string | number | boolean>>>(response.result as string);
      if (result && result.code === 200) {
        this.statusMessage = `模型 ${version} 部署成功！`;
        this.loadModelVersions();
      } else {
        this.statusMessage = `部署失败: ${result ? result.message : 'empty response'}`;
      }
    } catch (error) {
      this.statusMessage = `部署失败: ${JSON.stringify(error)}`;
    }
  }

  /**
   * 激活模型版本
   */
  async activateModel(version: string) {
    const httpRequest = http.createHttp();
    
    try {
      const response = await httpRequest.request(
        `${SERVER_URL}/api/model/${version}/activate`,
        {
          method: http.RequestMethod.POST,
          header: this.getAuthHeaders(),
          readTimeout: 5000,
          connectTimeout: 5000
        }
      );
      const result = this.parseJsonSafe<ApiResponse<Record<string, string | number | boolean>>>(response.result as string);
      if (result && result.code === 200) {
        this.statusMessage = `模型 ${version} 已激活`;
        this.loadModelVersions();
      } else {
        this.statusMessage = `激活失败: ${result ? result.message : 'empty response'}`;
      }
    } catch (error) {
      this.statusMessage = `激活失败: ${JSON.stringify(error)}`;
    }
  }

  aboutToAppear() {
    this.syncAuthFromPreferences().then(() => {
      this.loadModelVersions();
    });
  }

  build() {
    Column() {
      // 顶部导航栏
      CustomAppBar({ title: '模型管理', showSettings: false })

      Tabs() {
        // Tab 1: 模型列表
        TabContent() {
          Scroll() {
            Column() {
              // 模型版本列表
              if (this.modelVersions.length > 0) {
                ForEach(this.modelVersions, (model: ModelVersion) => {
                  Column() {
                    Row() {
                      Column() {
                        Text(model.version)
                          .fontSize(18)
                          .fontWeight(FontWeight.Bold)
                        
                        Text(model.modelName)
                          .fontSize(14)
                          .fontColor('#6B7280')
                          .margin({ top: 5 })
                      }
                      .alignItems(HorizontalAlign.Start)
                      
                      Blank()
                      
                      if (model.isActive) {
                        Text('激活中')
                          .fontSize(12)
                          .fontColor(Color.White)
                          .padding({ left: 10, right: 10, top: 5, bottom: 5 })
                          .backgroundColor('#10B981')
                          .borderRadius(5)
                      }
                    }
                    .width('100%')
                    .margin({ bottom: 10 })

                    // 模型指标
                    Row() {
                      Column() {
                        Row() {
                          Text('准确率: ')
                            .fontSize(14)
                            .fontColor('#6B7280')
                          Text(`${(model.accuracy * 100).toFixed(2)}%`)
                            .fontSize(14)
                            .fontColor('#10B981')
                            .fontWeight(FontWeight.Bold)
                        }
                        Text(`大小: ${model.modelSizeMb?.toFixed(1) || 'N/A'} MB`)
                          .fontSize(14)
                          .fontColor('#6B7280')
                          .margin({ top: 5 })
                      }
                      .alignItems(HorizontalAlign.Start)
                      
                      Blank()
                      
                      Column() {
                        Text(`格式: ${model.modelFormat}`)
                          .fontSize(14)
                          .fontColor('#6B7280')
                        Text(`时间: ${model.createdTime?.substring(0, 10) || 'N/A'}`)
                          .fontSize(14)
                          .fontColor('#6B7280')
                          .margin({ top: 5 })
                      }
                      .alignItems(HorizontalAlign.Start)
                    }
                    .width('100%')
                    .margin({ bottom: 10 })

                    // 操作按钮
                    Row() {
                      Button('部署')
                        .height(35)
                        .fontSize(14)
                        .backgroundColor('#3B82F6')
                        .onClick(() => {
                          this.selectedVersion = model.version;
                          this.deployModel(model.version);
                        })
                      
                      if (!model.isActive) {
                        Button('激活')
                          .height(35)
                          .fontSize(14)
                          .backgroundColor('#F59E0B')
                          .margin({ left: 10 })
                          .onClick(() => {
                            this.activateModel(model.version);
                          })
                      }
                      
                      Button('详情')
                        .height(35)
                        .fontSize(14)
                        .backgroundColor('#6B7280')
                        .margin({ left: 10 })
                        .onClick(() => {
                          this.statusMessage = `模型 ${model.version} 详情查看功能开发中`;
                        })
                    }
                    .width('100%')
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
                  Text('🤖')
                    .fontSize(64)
                    .margin({ bottom: 12 })
                  Text('暂无模型版本')
                    .fontSize(16)
                    .fontColor('#9CA3AF')
                }
                .width('100%')
                .height(200)
                .justifyContent(FlexAlign.Center)
              }
              
              // 状态消息
              if (this.statusMessage) {
                Column() {
                  Text(this.statusMessage)
                    .fontSize(14)
                    .fontColor('#3B82F6')
                    .textAlign(TextAlign.Center)
                }
                .width('100%')
                .padding(12)
                .backgroundColor('#EFF6FF')
                .borderRadius(8)
                .margin({ top: 10, bottom: 80 })
              }
            }
            .width('100%')
            .padding({ left: 16, right: 16, top: 16 })
          }
        }
        .tabBar('模型列表')

        // Tab 2: 部署设置
        TabContent() {
          Scroll() {
            Column() {
              Column() {
                Text('⚙️ 部署配置')
                  .fontSize(18)
                  .fontWeight(FontWeight.Bold)
                  .margin({ bottom: 15 })
                
                // 部署目标
                Row() {
                  Text('部署目标:')
                    .fontSize(16)
                    .width('30%')
                  
                  Row() {
                    Radio({ value: 'orangepi', group: 'deployTarget' })
                      .checked(this.deployTarget === 'orangepi')
                      .onChange(() => {
                        this.deployTarget = 'orangepi';
                      })
                    Text('OrangePi')
                      .fontSize(16)
                      .margin({ left: 5 })
                  }
                  .width('35%')
                  
                  Row() {
                    Radio({ value: 'cloud', group: 'deployTarget' })
                      .checked(this.deployTarget === 'cloud')
                      .onChange(() => {
                        this.deployTarget = 'cloud';
                      })
                    Text('云端')
                      .fontSize(16)
                      .margin({ left: 5 })
                  }
                  .width('35%')
                }
                .width('100%')
                .margin({ bottom: 15 })
                
                // 设备ID（仅OrangePi）
                if (this.deployTarget === 'orangepi') {
                  Row() {
                    Text('设备ID:')
                      .fontSize(16)
                      .width('30%')
                    
                    TextInput({ text: this.deviceId })
                      .width('70%')
                      .onChange((value: string) => {
                        this.deviceId = value;
                      })
                  }
                  .width('100%')
                  .margin({ bottom: 15 })
                }
                
                Divider().margin({ top: 10, bottom: 10 })
                
                Text('📝 部署说明')
                  .fontSize(16)
                  .fontWeight(FontWeight.Medium)
                  .margin({ bottom: 10 })
                
                Text('• OrangePi部署: 模型将推送到边缘设备进行本地推理，延迟更低')
                  .fontSize(14)
                  .fontColor('#6B7280')
                  .margin({ bottom: 6 })
                
                Text('• 云端部署: 模型将部署到云端推理服务，便于管理和更新')
                  .fontSize(14)
                  .fontColor('#6B7280')
                  .margin({ bottom: 6 })
                
                Text('• 推荐使用OrangePi部署以获得最低延迟(<50ms)')
                  .fontSize(14)
                  .fontColor('#F59E0B')
                  .fontWeight(FontWeight.Medium)
              }
              .width('100%')
              .padding(20)
              .backgroundColor(Color.White)
              .borderRadius(12)
              .shadow({ radius: 8, color: '#00000010', offsetX: 0, offsetY: 2 })
            }
            .width('100%')
            .padding({ left: 16, right: 16, top: 16, bottom: 80 })
          }
        }
        .tabBar('部署设置')
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

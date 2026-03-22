// pages/HomePage.ets  ← 建议重命名文件
import { BottomNavBar } from './BottomNavBar';
import { CustomAppBar } from './CustomAppBar';
import http from '@ohos.net.http';

import router from '@ohos.router';
import { EmgService } from '../services/EmgService';
import { EmgData } from '../models/EmgData';
// 👇 新增以下两行（SDK 10 必须）


// ========== 主页组件（包含网络请求和完整 UI）==========
@Entry
@Component
export struct HomePage {
  @State isTraining: boolean = false;

  // Device States
  @State armbandStatus: string = '🔴 未连接';
  @State armbandSignal: string = '';
  @State armbandBattery: number = 0;
  @State armbandBatteryText: string = '🔋 0%';


  private emgService: EmgService | null = null;

  aboutToAppear() {
    this.emgService = new EmgService();
    this.initEmgService();
  }

  aboutToDisappear() {
    this.emgService?.disconnect();
  }

  initEmgService() {
    if (!this.emgService) return;

    this.emgService.onDataReceived = (data: EmgData) => {
      this.armbandStatus = '🟢 已连接';
      this.armbandSignal = '📶 强';
      this.armbandBattery = data.battery || 0;
      this.armbandBatteryText = `🔋 ${this.armbandBattery}%`;


    };

    this.emgService.onConnectionChanged = (connected: boolean) => {
      if (connected) {
         this.armbandStatus = '🟢 已连接';
         this.armbandSignal = '📶 强';
      } else {
         this.armbandStatus = '🔴 未连接';
         this.armbandSignal = '';
         this.armbandBattery = 0;
         this.armbandBatteryText = '🔋 0%';
      }
    };

    this.emgService.connect();
  }

  build() {
    Column() {
      // 内部主页内容（原 HomePage）
      this.HomePageContent();
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#FFFFFF');
  }


  @Builder
  HomePageContent() {
    Column() {
      // 使用 Scroll 组件包裹主体内容，实现滚动效果
      Scroll() {
        Column() {
          // ========== 自定义顶部栏 ==========
          CustomAppBar({ title: '仿生机械臂', showSettings: true })

          // ========== 状态卡片 ==========
          Column() {
            Image($r('app.media.robot4'))
              .width('100%')
              .height('100%')
              .objectFit(ImageFit.Cover)
              .borderRadius(12);
          }
          .width('100%')
          .height(240)
          .justifyContent(FlexAlign.Center)
          .backgroundColor('#F9FAFB')
          .borderRadius(12)
          .border({ width: 1, color: '#E5E7EB' })
          .margin({ top: 12, bottom: 12 });

          // ========== 设备区 ==========
          SectionTitle({ title: '设备' });

          Column({ space: 8 }) {
            DeviceCard({
              icon: '🔘',
              name: '肌电臂环',
              status: this.armbandStatus,
              battery: this.armbandBattery,
              batteryText: this.armbandBatteryText,
              signal: this.armbandSignal
            });

          }
          .width('100%');

          // ========== EMG 系统快捷功能 ==========
          SectionTitle({ title: 'EMG 系统' });

          Grid() {
            GridItem() {
              QuickActionButton({
                icon: '⚡',
                label: '实时监控',
                color: '#3B82F6',
                onTap: () => {
                  router.pushUrl({ url: 'pages/EmgRealtimePage' });
                }
              });
            }

            GridItem() {
              QuickActionButton({
                icon: '📝',
                label: '数据标注',
                color: '#10B981',
                onTap: () => {
                  router.pushUrl({ url: 'pages/AnnotationPage' });
                }
              });
            }

            GridItem() {
              QuickActionButton({
                icon: '🎯',
                label: '模型训练',
                color: '#8B5CF6',
                onTap: () => {
                  router.pushUrl({ url: 'pages/ModelTrainingPage' });
                }
              });
            }

            GridItem() {
              QuickActionButton({
                icon: '🤖',
                label: '模型管理',
                color: '#F59E0B',
                onTap: () => {
                  router.pushUrl({ url: 'pages/ModelManagePage' });
                }
              });
            }
          }
          .columnsTemplate('1fr 1fr')
          .rowsTemplate('1fr 1fr')
          .columnsGap(10)
          .rowsGap(10)
          .width('100%')
          .height(180)

          // ========== 训练建议 ==========
          SectionTitle({ title: '使用建议' });

          Column({ space: 8 }) {
            TodayProgress({
              progress: 64,
              best: 100,
              label: '成功执行 3 次精细操作'
            });

            TrainingProgress({
              progress: 85,
              best: 92,
              label: ' 今日操控成功率：85% | 历史最佳：92%'
            });
          }
          .width('100%');

          // 底部留白，防止内容贴底
          Blank().height(20);
        }
      }
      .layoutWeight(1) // Scroll 占据剩余空间
      .scrollBar(BarState.Off) // 隐藏滚动条
      .align(Alignment.Top);

      // ========== 底部导航栏 ==========
      BottomNavBar({ currentIndex: 0 });
    }
    .width('100%')
    .height('100%')
    .padding({ left: 16, right: 16, top: 0, bottom: 0 })
    .backgroundColor('#FFFFFF');
  }
}

// ========== 所有子组件保持不变 ==========
@Component
struct SectionTitle {
  @Prop title: string;

  build() {
    Text(this.title)
      .fontSize(18)
      .fontWeight(FontWeight.Medium)
      .fontColor('#1E40AF')
      .margin({ top: 12, bottom: 8 })
      .width('100%');
  }
}

@Component
struct InfoItem {
  @Prop title: string;
  @Prop content: string;

  build() {
    Column() {
      Text(this.title)
        .fontSize(14)
        .fontWeight(FontWeight.Bold)
        .fontColor('#1E40AF');
      Text(this.content)
        .fontSize(14)
        .fontColor('#4B5563');
    }
    .width('100%')
    .padding({ left: 16, right: 16, top: 8, bottom: 8 })
    .borderRadius(12)
    .backgroundColor('#F9FAFB')
    .border({ width: 1, color: '#E5E7EB' });
  }
}

@Component
struct DeviceCard {
  @Prop icon: string;
  @Prop name: string;
  @Prop status: string;
  @Prop signal: string;
  @Prop battery: number;
  @Prop batteryText: string;

  build() {
    Column({ space: 8 }) {
      Row({ space: 16 }) {
        Column() {
          Text(this.icon).fontSize(24);
        }

        Column({ space: 4 }) {
          Text(this.name)
            .fontSize(14)
            .fontWeight(FontWeight.Medium)
            .fontColor('#1E40AF');
          Text(this.status)
            .fontSize(12)
            .fontColor('#4B5563');
        }

        Column({ space: 4 }) {
          Text(this.signal)
            .fontSize(12)
            .fontColor('#4B5563');

          Row() {
            Text(`${this.battery}%`)
              .fontSize(12)
              .fontColor('#4B5563')
              .margin({ right: 4 });

            Progress({ value: this.battery, total: 100 })
              .width(80)
              .height(6)
              .backgroundColor('#E5E7EB')
              .foregroundColor('#10B981');
          }.width(100);
        }
      }
    }
    .width('100%')
    .padding({ left: 16, right: 16, top: 12, bottom: 12 })
    .borderRadius(16)
    .backgroundColor('#F9FAFB')
    .border({ width: 1, color: '#E5E7EB' });
  }
}

@Component
struct TrainingProgress {
  @Prop progress: number;
  @Prop best: number;
  @Prop label: string;

  build() {
    Column() {
      Row() {
        Text('📊').fontSize(16).margin({ right: 4 });
        Text('使用表现')
          .fontSize(14)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1E40AF');
      }

      Row({ space: 8 }) {
        Text('✅').fontSize(16).fontColor('#10B981');
        Text(this.label).fontSize(14).fontColor('#4B5563');
      }

      Row() {
        Progress({ value: this.progress, total: 100 })
          .width('100%')
          .height(10)
          .backgroundColor('#E5E7EB')
          .foregroundColor('#3B82F6');
      }
      .width('100%')
      .margin({ top: 8 });
    }
    .width('100%')
    .padding({ left: 16, right: 16, top: 12, bottom: 12 })
    .borderRadius(16)
    .backgroundColor('#F9FAFB')
    .border({ width: 1, color: '#E5E7EB' });
  }
}

// ========== QuickActionButton 组件 ==========
@Component
struct QuickActionButton {
  @Prop icon: string;
  @Prop label: string;
  @Prop color: ResourceColor;
  private onTap: () => void = () => {};

  build() {
    Column() {
      Text(this.icon)
        .fontSize(36)
        .margin({ bottom: 8 })

      Text(this.label)
        .fontSize(14)
        .fontColor('#374151')
        .fontWeight(FontWeight.Medium)
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
    .backgroundColor(Color.White)
    .borderRadius(12)
    .shadow({ radius: 8, color: '#00000010', offsetX: 0, offsetY: 2 })
    .onClick(() => {
      this.onTap();
    })
    .stateStyles({
      normal: {
        .scale({ x: 1.0, y: 1.0 })
      },
      pressed: {
        .scale({ x: 0.95, y: 0.95 })
      }
    })
  }
}

@Component
struct TodayProgress {
  @Prop progress: number;
  @Prop best: number;
  @Prop label: string;

  build() {
    Column() {
      Row() {
        Text('🎯').fontSize(16).margin({ right: 4 });
        Text('今日目标')
          .fontSize(14)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1E40AF');
      }

      Row({ space: 8 }) {
        Text('✅').fontSize(16).fontColor('#10B981');
        Text(this.label).fontSize(14).fontColor('#4B5563');
      }

      Row() {
        Progress({ value: this.progress, total: 100 })
          .width('100%')
          .height(10)
          .backgroundColor('#E5E7EB')
          .foregroundColor('#3B82F6');
      }
      .width('100%')
      .margin({ top: 8 });
    }
    .width('100%')
    .padding({ left: 16, right: 16, top: 12, bottom: 12 })
    .borderRadius(16)
    .backgroundColor('#F9FAFB')
    .border({ width: 1, color: '#E5E7EB' });
  }
}


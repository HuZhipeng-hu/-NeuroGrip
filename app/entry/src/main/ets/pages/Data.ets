// pages/DataPage.ets

import {BottomNavBar} from './BottomNavBar'
import { CustomAppBar } from './CustomAppBar';

interface ChartData {
  label: string;
  value: number;
  unit?: string;
}

@Entry // ✅ 先保留 @Entry，后续集成到 MainPage 时再移除
@Component
export struct DataPage {
  private weeklyData: ChartData[] = [
    { label: '周一', value: 65, unit: '次' },
    { label: '周二', value: 78, unit: '次' },
    { label: '周三', value: 90, unit: '次' },
    { label: '周四', value: 81, unit: '次' },
    { label: '周五', value: 56, unit: '次' },
    { label: '周六', value: 95, unit: '次' },
    { label: '周日', value: 88, unit: '次' },
  ];

  build() {
    Column() {
      // ========== 顶部栏 ==========
      CustomAppBar({ title: '仿生义肢', showSettings: true })

      Scroll() {
        Column({ space: 16 }) {
          // ✅ 1. 统计卡片区域
          Row({ space: 12 }) {
            StatCard({
              title: '今日使用次数',
              value: '88',
              unit: '次',
              icon: '🤖',
              color: '#3B82F6'
            });

            StatCard({
              title: '舒适度评分',
              value: '4.8',
              unit: '/5',
              icon: '😊',
              color: '#10B981'
            });
          }
          .width('100%')
          .justifyContent(FlexAlign.SpaceBetween)

          // ✅ 2. 使用习惯分析卡片 - 修复显示所有星期
          Column() {
            Row() {
              Text('本周每日使用频率')
                .fontSize(18)
                .fontWeight(FontWeight.Medium)
                .fontColor('#1E293B')
              Blank()
              Text('详情 >')
                .fontSize(14)
                .fontColor('#64748B')
            }
            .width('100%')
            .padding({ left: 20, top: 20, right: 20, bottom: 12 })

            Divider().color('#F1F5F9')

            // ✅ 添加使用感受提示
            Text('👍 周六使用最频繁 (95次)，继续保持！')
              .fontSize(12)
              .fontColor('#10B981')
              .padding({ left: 20, top: 8, bottom: 4 })
              .width('100%')

            // ✅ 条形图 - 现在会显示所有7天的数据
            StableBarChart({
              data: this.weeklyData,
              maxValue: 100
            })
          }
          .width('100%')
          .backgroundColor('#FFFFFF')
          .borderRadius(16)
          .shadow({
            radius: 12,
            color: '#00000010',
            offsetX: 0,
            offsetY: 4
          })

          // ✅ 3. 适配分析与建议卡片
          AdaptTrendCard()
        }
        .width('100%')
        .padding({ left: 16, right: 16, top: 16, bottom: 10 })
      }
      .layoutWeight(1)
      .backgroundColor('#F8FAFC')

      BottomNavBar({ currentIndex: 2 });
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F8FAFC')
  }
}

// ========== ✅ 统计卡片组件 ==========
@Component
struct StatCard {
  @Prop title: string;
  @Prop value: string;
  @Prop unit: string;
  @Prop icon: string;
  @Prop color: string;

  build() {
    Column() {
      Row({ space: 8 }) {
        Text(this.icon)
          .fontSize(24)
          .fontColor(this.color);
        Text(this.title)
          .fontSize(14)
          .fontColor('#64748B');
      }
      .width('100%')
      .justifyContent(FlexAlign.Start);

      Text(`${this.value}${this.unit}`)
        .fontSize(32)
        .fontWeight(FontWeight.Bold)
        .fontColor('#1E293B')
        .margin({ top: 12 });
    }
    .width('48%')
    .height(110)
    .padding(16)
    .backgroundColor('#FFFFFF')
    .borderRadius(16)
    .shadow({
      radius: 8,
      color: '#00000008',
      offsetX: 0,
      offsetY: 2
    })
  }
}

// ========== ✅ 修复后的条形图组件 - 确保显示所有星期 ==========
@Component
struct StableBarChart {
  @Prop data: ChartData[];
  @Prop maxValue: number = 100;

  build() {
    Column({ space: 12 }) {
      // ✅ 使用ForEach遍历所有数据，确保显示全部7天
      ForEach(this.data, (item: ChartData, index) => {
        Row({ space: 12 }) {
          // 星期标签
          Text(item.label)
            .fontSize(14)
            .fontColor('#64748B')
            .width(40)
            .textAlign(TextAlign.Start);

          // 进度条容器
          Row() {
            // 进度条
            Progress({ value: item.value, total: this.maxValue })
              .height(20)
              .color(this.getBarColor(item.value))
              .borderRadius(10)
              .width('100%')
          }
          .layoutWeight(1)
          .height(20)
          .backgroundColor('#F1F5F9')
          .borderRadius(10)
          .alignItems(VerticalAlign.Center);

          // 数值标签
          Text(`${item.value}${item.unit || ''}`)
            .fontSize(14)
            .fontColor('#1E293B')
            .fontWeight(FontWeight.Medium)
            .width(45)
            .textAlign(TextAlign.End);
        }
        .width('100%')
        .alignItems(VerticalAlign.Center)
        .padding({ top: index === 0 ? 0 : 4, bottom: 4 })
      }, (item: ChartData) => item.label) // 使用label作为唯一键
    }
    .width('100%')
    .padding({ left: 20, right: 20, top: 12, bottom: 20 })
  }

  // ✅ 根据数值返回不同颜色的辅助函数
  private getBarColor(value: number): ResourceColor {
    if (value >= 90) return '#10B981'; // 绿色 - 优秀
    if (value >= 70) return '#3B82F6'; // 蓝色 - 良好
    if (value >= 50) return '#F59E0B'; // 橙色 - 一般
    return '#EF4444'; // 红色 - 需关注
  }
}

// ========== ✅ 适配分析与建议卡片 ==========
@Component
struct AdaptTrendCard {
  build() {
    Column() {
      Row() {
        Text('🦾')
          .fontSize(20)
          .margin({ right: 8 })
        Text('适配分析')
          .fontSize(18)
          .fontWeight(FontWeight.Medium)
          .fontColor('#1E293B')
      }
      .width('100%')
      .padding({ left: 20, top: 20, right: 20, bottom: 12 })

      Divider().color('#F1F5F9')

      Column({ space: 16 }) {
        // ✅ 使用习惯分析
        Row({ space: 16 }) {
          AdaptItem({
            label: '平均每日使用',
            value: '79 次',
            trend: '↑ 较上周',
            trendValue: '+12%',
            isPositive: true
          })
            .layoutWeight(1)

          AdaptItem({
            label: '单日最高',
            value: '95 次',
            trend: '周六',
            trendValue: '活跃日',
            isPositive: true
          })
            .layoutWeight(1)
        }
        .width('100%')

        // ✅ 舒适度反馈
        Row({ space: 16 }) {
          AdaptItem({
            label: '佩戴舒适度',
            value: '舒适',
            trend: '↑ 提升',
            trendValue: '5%',
            isPositive: true
          })
            .layoutWeight(1)

          AdaptItem({
            label: '适应阶段',
            value: '进阶期',
            trend: '第',
            trendValue: '4周',
            isPositive: true
          })
            .layoutWeight(1)
        }
        .width('100%')

        // ✅ 个性化建议
        Column() {
          Row() {
            Text('💡')
              .fontSize(16)
              .margin({ right: 6 })
            Text('今日小贴士')
              .fontSize(14)
              .fontWeight(FontWeight.Medium)
              .fontColor('#1E293B')
          }

          Text('• 尝试用义肢拿取轻质物品，逐步增加握力训练')
            .fontSize(13)
            .fontColor('#64748B')
            .margin({ top: 8 })
            .width('100%')

          Text('• 佩戴2小时后建议休息5分钟，保持舒适度')
            .fontSize(13)
            .fontColor('#64748B')
            .margin({ top: 4 })
            .width('100%')
        }
        .width('100%')
        .padding(12)
        .backgroundColor('#F0F9FF')
        .borderRadius(12)
        .margin({ top: 8 })
      }
      .width('100%')
      .padding({ left: 20, right: 20, top: 12, bottom: 20 })
    }
    .width('100%')
    .backgroundColor('#FFFFFF')
    .borderRadius(16)
    .shadow({
      radius: 12,
      color: '#00000010',
      offsetX: 0,
      offsetY: 4
    })
  }
}

// ========== ✅ 适配项组件 ==========
@Component
struct AdaptItem {
  @Prop label: string;
  @Prop value: string;
  @Prop trend: string;
  @Prop trendValue: string;
  @Prop isPositive: boolean;

  build() {
    Column() {
      Text(this.label)
        .fontSize(12)
        .fontColor('#64748B')
        .width('100%')

      Row({ space: 4 }) {
        Text(this.value)
          .fontSize(16)
          .fontWeight(FontWeight.Medium)
          .fontColor('#1E293B')

        if (this.trendValue) {
          Row({ space: 2 }) {
            Text(this.isPositive ? '↑' : '→')
              .fontSize(10)
              .fontColor(this.isPositive ? '#10B981' : '#64748B')
            Text(this.trendValue)
              .fontSize(10)
              .fontColor(this.isPositive ? '#10B981' : '#64748B')
          }
          .padding({ left: 6, right: 6, top: 2, bottom: 2 })
          .backgroundColor(this.isPositive ? '#ECFDF5' : '#F8FAFC')
          .borderRadius(10)
        }
      }
      .width('100%')
      .margin({ top: 4 })
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
  }
}
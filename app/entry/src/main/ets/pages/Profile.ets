// pages/Profile.ets

import router from '@ohos.router';
import { BottomNavBar } from './BottomNavBar';
import { CustomAppBar } from './CustomAppBar';

@Entry
@Component
struct Profile {
  build() {
    Column() {
      // ========== 顶部栏 ==========
      CustomAppBar({ title: '我的', showSettings: true })

      Column({ space: 20 }) {
        // ========== 个人资料与数据卡片 ==========
        Column() {
          // 用户信息区
          Row({ space: 16 }) {
            // 头像
            Text('👤')
              .fontSize(36)
              .fontColor('#FFFFFF')
              .width(72)
              .height(72)
              .textAlign(TextAlign.Center)
              .borderRadius(36)
              .backgroundColor('#3B82F6');

            // 用户名和邮箱
            Column({ space: 4 }) {
              Text('小为')
                .fontSize(22)
                .fontWeight(FontWeight.Bold)
                .fontColor('#1E293B');
              Text('harmony_user@example.com')
                .fontSize(14)
                .fontColor('#64748B');
            }
            .alignItems(HorizontalAlign.Start)
            .layoutWeight(1)
          }
          .width('100%')
          .justifyContent(FlexAlign.Start)
          .margin({ bottom: 24 })

          // 数据统计区
          Row() {
            StatItem({ title: '今日使用', value: '2.5', unit: 'h', color: '#3B82F6' })
            Divider().vertical(true).height(30).color('#E2E8F0').margin({ left: 20, right: 20 })
            StatItem({ title: '识别成功率', value: '98.5', unit: '%', color: '#10B981' })
          }
          .width('100%')
          .justifyContent(FlexAlign.SpaceEvenly)
          .padding({ top: 20, bottom: 20 })
          .backgroundColor('#F8FAFC')
          .borderRadius(12)
        }
        .width('100%')
        .padding(20)
        .backgroundColor('#FFFFFF')
        .borderRadius(16)
        .shadow({
          radius: 12,
          color: '#00000010',
          offsetX: 0,
          offsetY: 4
        })

        // ========== 功能入口区 ==========
        Column({ space: 0 }) {
          ProfileItem({ icon: '📱', title: '我的设备', subtitle: 'NeuroGripPro v1.0', onItemClick: () => {
            AlertDialog.show({ message: 'NeuroGripPro v1.0' })
          }});

          Divider().color('#F1F5F9').margin({ left: 20, right: 20 })

          ProfileItem({ icon: '⏰', title: '使用时长', subtitle: '查看详细统计', onItemClick: () => {
            router.pushUrl({ url: 'pages/UsageHistory' });
          }});

          Divider().color('#F1F5F9').margin({ left: 20, right: 20 })

          ProfileItem({ icon: '📍', title: '设备定位', subtitle: '查看最后连接位置', onItemClick: () => {
            router.pushUrl({ url: 'pages/Location' });
          }});

          Divider().color('#F1F5F9').margin({ left: 20, right: 20 })

          ProfileItem({ icon: '💬', title: '帮助与反馈', subtitle: '常见问题与建议', onItemClick: () => {
            AlertDialog.show({ message: '请联系工作人员' })
          }});

          Divider().color('#F1F5F9').margin({ left: 20, right: 20 })

          ProfileItem({ icon: '📄', title: '关于项目', subtitle: 'NeuroGripPro v1.0', onItemClick: () => {
            AlertDialog.show({ message: 'NeuroGripPro v1.0\n\n© 2026 ICT Team' })
          }});

        }
        .layoutWeight(1)
        .backgroundColor('#FFFFFF')
        .borderRadius(16)
        .clip(true)
        .shadow({
          radius: 12,
          color: '#00000010',
          offsetX: 0,
          offsetY: 4
        })

      }
      .width('100%')
      .layoutWeight(1)
      .padding({ left: 16, right: 16, top: 16, bottom: 16 }) // ✅ 恢复正常的padding

      BottomNavBar({ currentIndex: 3 });
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F8FAFC')
  }
}

// ========== ✅ 新增：数据统计项组件 ==========
@Component
struct StatItem {
  @Prop title: string;
  @Prop value: string;
  @Prop unit: string;
  @Prop color: string;

  build() {
    Column({ space: 4 }) {
      Text(`${this.value}${this.unit}`)
        .fontSize(24)
        .fontWeight(FontWeight.Bold)
        .fontColor(this.color);
      Text(this.title)
        .fontSize(12)
        .fontColor('#64748B');
    }
    .justifyContent(FlexAlign.Center)
  }
}


// ==========功能项组件 ==========
@Component
struct ProfileItem {
  @Prop icon: string;
  @Prop title: string;
  @Prop subtitle: string;
  onItemClick?: () => void;

  build() {
    Row() {
      Text(this.icon)
        .fontSize(22)
        .fontColor('#3B82F6')
        .margin({ right: 16 });

      Column({ space: 4 }) {
        Text(this.title)
          .fontSize(16)
          .fontWeight(FontWeight.Medium)
          .fontColor('#1E293B');
        Text(this.subtitle)
          .fontSize(13)
          .fontColor('#94A3B8');
      }
      .alignItems(HorizontalAlign.Start)
      .layoutWeight(1);

      Text('>')
        .fontSize(16)
        .fontColor('#CBD5E1');
    }
    .width('100%')
    .padding({ left: 20, right: 20, top: 18, bottom: 18 })
    .justifyContent(FlexAlign.Start)
    .alignItems(VerticalAlign.Center)
    .onClick(() => {
      if (this.onItemClick) {
        this.onItemClick();
      }
    })
    .stateStyles({
      normal: {
        .backgroundColor('#FFFFFF')
      },
      pressed: {
        .backgroundColor('#F8FAFC')
      }
    })
  }
}


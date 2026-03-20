// pages/Location.ets
import router from '@ohos.router';
import { CustomAppBar } from './CustomAppBar';


@Entry
@Component
struct Location {
  build() {
    Column() {
      // ========== 顶部栏 ==========
      CustomAppBar({ title: '定位', onBack: () => { router.back() } })

      // ========== 地图区域：仅图标 ==========
      Column() {
        Image($r("app.media.map1"))
          .width('100%')
          .height('100%')
          .objectFit(ImageFit.Cover)
          .borderRadius(12);
      }
      .width('100%')
      .height('50%')
      .backgroundColor('#F0F9FF')
      .borderRadius(12)
      .justifyContent(FlexAlign.Center)
      .margin({ top: 12, bottom: 16 });

      // ========== 标题 + 地址（左对齐） ==========
      Column() {
        Text('定位详情')
          .fontSize(18)
          .fontWeight(FontWeight.Medium)
          .fontColor('#1E40AF')
          .textAlign(TextAlign.Start);

        Text('(华中师范大学南湖校区)')
          .fontSize(14)
          .fontColor('#6B7280')
          .textAlign(TextAlign.Start)
          .margin({ top: 4 });
      }
      .width('100%');

      // ========== 信息项 ==========
      Column({ space: 12 }) {
        InfoItem({
          title: '更新时间',
          content: '2025-11-16 20:30'
        });

        InfoItem({
          title: 'GPS 状态',
          content: '✅ 已开启'
        });
      }
      .width('100%')
      .margin({ top: 12 });

      // ========== 历史轨迹卡片 ==========
      HistoryCard({
        label: '历史轨迹',
        onTap: () => {
          console.log('查看历史轨迹...');
        }
      })
        .margin({ top: 16 });

      // 推动底部导航到底部（虽然本页没用 BottomNavBar，但保留结构）
      Blank().layoutWeight(1);
    }
    .width('100%')
    .height('100%')
    .padding({ left: 16, right: 16 })
    .backgroundColor('#FFFFFF');
  }
}

// ========== 内联组件：InfoItem ==========
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

// ========== 内联组件：HistoryCard ==========
@Component
struct HistoryCard {
  @Prop label: string;
  private onTap: () => void = () => {};

  build() {
    Row() {
      Text(this.label)
        .fontSize(14)
        .fontWeight(FontWeight.Medium)
        .fontColor('#1E40AF');
    }
    .width('100%')
    .height(48)
    .justifyContent(FlexAlign.Center)
    .backgroundColor('#F9FAFB')
    .border({ width: 1, color: '#E5E7EB' })
    .borderRadius(12)
    .onClick(() => {
      this.onTap();
    });
  }
}





































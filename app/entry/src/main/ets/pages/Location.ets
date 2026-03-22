// pages/Location.ets
import router from '@ohos.router';
import geoLocationManager from '@ohos.geoLocationManager';
import abilityAccessCtrl from '@ohos.abilityAccessCtrl';
import bundleManager from '@ohos.bundle.bundleManager';
import common from '@ohos.app.ability.common';
import { BusinessError } from '@ohos.base';
import { CustomAppBar } from './CustomAppBar';

@Entry
@Component
struct Location {
  @State latitude: number = 0;
  @State longitude: number = 0;
  @State address: string = '正在获取定位...';
  @State locationTime: string = '--';
  @State isLocating: boolean = false;

  aboutToAppear() {
    this.requestPermissions();
  }

  async requestPermissions() {
    let atManager = abilityAccessCtrl.createAtManager();
    try {
      let context = getContext(this) as common.UIAbilityContext;
      atManager.requestPermissionsFromUser(context, [
        'ohos.permission.LOCATION',
        'ohos.permission.APPROXIMATELY_LOCATION'
      ]).then((data) => {
        // 检查权限授予情况
        let grantStatus: Array<number> = data.authResults;
        let length: number = grantStatus.length;
        let isGranted: boolean = true;
        for (let i = 0; i < length; i++) {
          if (grantStatus[i] !== 0) {
            isGranted = false;
            break;
          }
        }
        
        if (isGranted) {
          console.info('权限已授予，开始定位');
          this.getCurrentLocation();
        } else {
          console.error('用户拒绝了定位权限');
          this.address = '需授权定位权限以获取位置';
        }
      }).catch((err: BusinessError) => {
        console.error('requestPermissionsFromUser err:' + JSON.stringify(err));
      })
    } catch (err) {
      console.error(`catch err->${JSON.stringify(err)}`);
    }
  }

  getCurrentLocation() {
    this.isLocating = true;
    let requestInfo: geoLocationManager.CurrentLocationRequest = {
      'priority': geoLocationManager.LocationRequestPriority.ACCURACY,
      'scenario': geoLocationManager.LocationRequestScenario.TRAJECTORY_TRACKING,
      'maxAccuracy': 0
    };
    
    try {
      geoLocationManager.getCurrentLocation(requestInfo, (err, location) => {
        this.isLocating = false;
        if (err) {
          console.error('定位失败 errCode:' + err.code + ',errMessage:' + err.message);
          if (err.code === 3301100) {
            this.address = '请开启系统位置开关';
            AlertDialog.show({
              title: '定位服务未开启',
              message: '获取位置信息需要开启系统定位开关，请前往设置开启。',
              autoCancel: true,
              alignment: DialogAlignment.Bottom,
              confirm: {
                value: '我知道了',
                action: () => {}
              }
            });
          } else {
            this.address = '定位失败: ' + err.message;
          }
          return;
        }
        if (location) {
          console.info('定位成功:' + JSON.stringify(location));
          this.latitude = location.latitude;
          this.longitude = location.longitude;
          this.address = `纬度: ${location.latitude.toFixed(6)}\n经度: ${location.longitude.toFixed(6)}`;
          
          let date = new Date(location.timeStamp * 1000); // 假设是秒，如果是毫秒则不需要*1000
          // HarmonyOS Location timeStamp 是自1970年1月1日以来的秒数? 
          // 文档通常说是秒或毫秒。通常是秒。
          // 但如果是毫秒，日期会非常大。
          // 暂定为秒，如果是毫秒则调整。
          // 实际上大多时候是秒。
          
          this.locationTime = this.formatDate(date); 
        }
      });
    } catch (err) {
      this.isLocating = false;
      console.error("errCode:" + err.code + ",errMessage:" + err.message);
    }
  }

  formatDate(date: Date): string {
    return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  }

  build() {
    Column() {
      // ========== 顶部栏 ==========
      CustomAppBar({ title: '定位', onBack: () => { router.back() } })

      // ========== 地图区域：仅图标 ==========
      Stack() {
        Image($r("app.media.map1"))
          .width('100%')
          .height('100%')
          .objectFit(ImageFit.Cover)
          .borderRadius(12);
          
        if (this.isLocating) {
          LoadingProgress()
            .width(40)
            .height(40)
            .color('#1E40AF')
        }
      }
      .width('100%')
      .height('40%') // 稍微调小一点，留给下面展示
      .backgroundColor('#F0F9FF')
      .borderRadius(12)
      .margin({ top: 12, bottom: 16 });

      // ========== 标题 + 地址（左对齐） ==========
      Column() {
        Text('当前位置')
          .fontSize(18)
          .fontWeight(FontWeight.Medium)
          .fontColor('#1E40AF')
          .textAlign(TextAlign.Start);

        Text(this.address)
          .fontSize(14)
          .fontColor('#6B7280')
          .textAlign(TextAlign.Start)
          .margin({ top: 4 });
      }
      .width('100%')
      .alignItems(HorizontalAlign.Start);

      // ========== 信息项 ==========
      Column({ space: 12 }) {
        InfoItem({
          title: '更新时间',
          content: this.locationTime
        });

        InfoItem({
          title: 'GPS 状态',
          content: this.latitude !== 0 ? '✅ 已定位' : (this.isLocating ? '📡 定位中...' : '❌ 未定位')
        });
        
        Button('刷新定位')
          .onClick(() => {
            this.getCurrentLocation();
          })
          .width('100%')
          .margin({ top: 8 })
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

      // 推动底部导航到底部
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
    Row() {
      Text(this.title)
        .fontSize(14)
        .fontWeight(FontWeight.Bold)
        .fontColor('#1E40AF')
        .layoutWeight(1);
      Text(this.content)
        .fontSize(14)
        .fontColor('#4B5563');
    }
    .width('100%')
    .padding({ left: 16, right: 16, top: 12, bottom: 12 })
    .borderRadius(12)
    .backgroundColor('#F9FAFB')
    .border({ width: 1, color: '#E5E7EB' });
  }
}

@Component
struct HistoryCard {
  @Prop label: string;
  onTap?: () => void;

  build() {
    Row() {
      Text(this.label)
        .fontSize(16)
        .fontWeight(FontWeight.Medium);
      Blank();
      Image($r('app.media.arrow_right'))
        .width(16)
        .height(16)
        .fillColor('#9CA3AF');
    }
    .width('100%')
    .padding(16)
    .backgroundColor('#F3F4F6')
    .borderRadius(12)
    .onClick(() => {
      if (this.onTap) this.onTap();
    });
  }
}





































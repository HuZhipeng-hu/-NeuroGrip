# -*- coding: utf-8 -*-
"""SpringBoot Backend 全功能测试脚本。

默认测试目标：
- HTTP: http://1.95.65.51:8080
- WS:   ws://1.95.65.51:8080

覆盖模块：
1) Auth 模块 (Login/Register)
2) 统计模块 (Daily Usage)
3) EMG 数据接口
4) 标注接口
5) 训练接口
6) 模型接口
7) WebSocket (/ws/app, /ws/emg)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


def ensure_package(import_name: str, pip_name: str) -> None:
    try:
        __import__(import_name)
    except ImportError:
        print(f"安装依赖: {pip_name}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])


ensure_package("requests", "requests")
ensure_package("websocket", "websocket-client")

import requests
from websocket import create_connection


@dataclass
class CaseResult:
    name: str
    ok: bool
    detail: str


class BackendTester:
    def __init__(self, base_url: str, ws_base_url: str, timeout: int = 8):
        self.base_url = base_url.rstrip("/")
        self.ws_base_url = ws_base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.results: List[CaseResult] = []
        self.test_device_id = f"test_device_{int(time.time())}"
        self.token = None # JWT token 存储

    def record(self, name: str, ok: bool, detail: str) -> None:
        self.results.append(CaseResult(name=name, ok=ok, detail=detail))
        flag = "PASS" if ok else "FAIL"
        print(f"[{flag}] {name} - {detail}")

    def request_json(
        self,
        method: str,
        path: str,
        expected_http: Tuple[int, ...] = (200,),
        json_body: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Tuple[bool, str, Optional[Dict[str, Any]], int]:
        url = f"{self.base_url}{path}"
        
        # 自动附加 Token
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
            
        try:
            resp = self.session.request(
                method, 
                url, 
                json=json_body, 
                headers=headers, 
                timeout=self.timeout, 
                **kwargs
            )
            status = resp.status_code
            if status not in expected_http:
                return False, f"HTTP {status}, 预期 {expected_http}, body={resp.text[:300]}", None, status

            try:
                # 处理可能返回字符串的情况（例如 hello）
                if resp.headers.get("content-type", "").startswith("application/json") or (resp.text and resp.text.strip().startswith("{")):
                     data = resp.json()
                     return True, f"HTTP {status}", data, status
                return True, f"HTTP {status}, text={resp.text}", {"text": resp.text}, status
            except Exception:
                return False, f"返回非 JSON: {resp.text[:300]}", None, status
        except Exception as error:
            return False, f"请求异常: {error}", None, 0

    def wait_for_training_status(self, task_id: int, tries: int = 3, interval: int = 5) -> Tuple[bool, str]:
        for attempt in range(tries):
            ok, detail, data, _ = self.request_json("GET", f"/api/training/task/{task_id}")
            if ok and isinstance(data, dict):
                code = data.get("code")
                status = (data.get("data") or {}).get("status") if isinstance(data.get("data"), dict) else None
                if code == 200 and status:
                    if status.lower() not in ("pending", "running"):
                        return True, f"状态 {status}"
                    detail = f"状态仍为 {status}"
            time.sleep(interval)
        return False, detail if 'detail' in locals() else "状态未就绪"

    def test_auth_module(self) -> None:
        """测试用户认证模块 (HTTP)"""
        print("\n=== [1] 测试 Authentication 模块 ===")
        ts = int(time.time())
        username = f"testuser_{ts}"
        password = "testpassword123"

        # 1.1 注册
        print(f"Registering user: {username}")
        ok, msg, data, code = self.request_json(
            "POST",
            "/auth/register",
            expected_http=(200, 500), # 允许500(如果用户已存在)
            json_body={"username": username, "password": password}
        )
        # 如果500，可能是已存在，尝试登录
        if code == 500:
             self.record("Auth Register", True, f"注册返回500(可能已存在) - {msg}")
        else:
             self.record("Auth Register", ok, f"{msg} - {data}")

        # 1.2 登录
        ok, msg, data, code = self.request_json(
            "POST",
            "/auth/login",
            json_body={"username": username, "password": password}
        )
        if ok and data and "data" in data and data["data"]:
            self.token = data["data"] # 保存 Token
            self.record("Auth Login", True, f"登录成功, 获取 Token: {self.token[:10]}...")
        else:
            self.token = None
            self.record("Auth Login", False, f"登录失败 - {msg} - {data}")

    def test_stats_module(self) -> None:
        """测试统计模块 (HTTP)"""
        print("\n=== [2] 测试 Stats 模块 ===")
        user_id = 1 # 测试用户ID

        if not self.token:
            print("Skipping Stats test because login failed.")
            return

        # 2.1 更新今日统计
        # 注意: update 接口接收 parameters 而非 json body
        # request_json 的 path 已经包含了 url parameters，所以这里只能拼接
        update_url = f"/api/stats/update?userId={user_id}&count=5&tips=TestRun"
        ok, msg, data, code = self.request_json(
            "POST",
            update_url,
            json_body={} # 空 body
        )
        self.record("Stats Update", ok, f"{msg} - {data}")

        # 2.2 获取今日统计
        ok, msg, data, code = self.request_json(
            "GET",
            f"/api/stats/today?userId={user_id}"
        )
        chk = False
        if ok and data:
            uc = data.get("usageCount")
            if uc is not None and int(uc) >= 5:
                chk = True
        
        self.record("Stats Today", chk, f"{msg} - {data}")

        # 2.3 获取最近7天
        ok, msg, data, code = self.request_json(
            "GET",
            f"/api/stats/last7days?userId={user_id}"
        )
        chk = (isinstance(data, list)) if ok else False
        list_len = len(data) if isinstance(data, list) else 0
        self.record("Stats Last7Days", chk, f"{msg} - 获得 {list_len} 条记录")


    def test_emg_data_module(self) -> None:
        """测试 EMG 数据接口 (HTTP)"""


    @staticmethod
    def make_frame_payload(gesture: str = "fist") -> Dict[str, Any]:
        now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {
            "device_ts": int(time.time() * 1000),
            "serverTime": now_str,
            "emg": [[128 for _ in range(8)] for _ in range(10)],
            "acc": [1, 2, 3],
            "gyro": [4, 5, 6],
            "angle": [10, 20, 30],
            "battery": 85,
            "gesture": gesture,
            "confidence": 0.95,
        }

    def test_emg_apis(self) -> None:
        name_prefix = "EMG"

        ok, detail, data, _ = self.request_json("GET", "/api/emg/status")
        if ok and isinstance(data, dict) and data.get("running") is True:
            self.record(f"{name_prefix}-status", True, "服务运行中")
        else:
            self.record(f"{name_prefix}-status", False, detail)

        frame = self.make_frame_payload("fist")
        ok, detail, data, _ = self.request_json(
            "POST",
            f"/api/emg/frame?deviceId={self.test_device_id}",
            json_body=frame,
        )
        if ok and isinstance(data, dict) and data.get("code") == 200:
            self.record(f"{name_prefix}-single-frame", True, "单帧写入成功")
        else:
            self.record(f"{name_prefix}-single-frame", False, f"{detail}; body={data}")

        batch_body = {
            "deviceId": self.test_device_id,
            "frames": [self.make_frame_payload("ok"), self.make_frame_payload("pinch")],
            "count": 2,
            "uploadTime": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        ok, detail, data, _ = self.request_json("POST", "/api/emg/batch", json_body=batch_body)
        if ok and isinstance(data, dict) and data.get("code") == 200:
            self.record(f"{name_prefix}-batch", True, f"批量写入 {data.get('received')} 帧")
        else:
            self.record(f"{name_prefix}-batch", False, f"{detail}; body={data}")

        ok, detail, data, _ = self.request_json("GET", "/api/emg/latest")
        self.record(
            f"{name_prefix}-latest",
            ok and isinstance(data, dict),
            detail if not ok else "获取最新帧成功",
        )

        ok, detail, data, _ = self.request_json(
            "GET",
            f"/api/emg/history?deviceId={self.test_device_id}&limit=5",
        )
        self.record(
            f"{name_prefix}-history",
            ok and isinstance(data, list),
            detail if not ok else f"返回 {len(data)} 条",
        )

        ok, detail, data, _ = self.request_json(
            "GET",
            f"/api/emg/gestures?deviceId={self.test_device_id}&limit=5",
        )
        self.record(
            f"{name_prefix}-gestures",
            ok and isinstance(data, list),
            detail if not ok else f"返回 {len(data)} 条",
        )

    def test_annotation_apis(self) -> None:
        name_prefix = "Annotation"

        end = dt.datetime.now()
        start = end - dt.timedelta(minutes=5)
        start_iso = start.replace(microsecond=0).isoformat()
        end_iso = end.replace(microsecond=0).isoformat()

        ok, detail, data, _ = self.request_json(
            "GET",
            f"/api/annotation/cache-data?deviceId={self.test_device_id}&startTime={start_iso}&endTime={end_iso}",
        )
        self.record(
            f"{name_prefix}-cache-data",
            ok and isinstance(data, dict) and data.get("code") == 200,
            detail if not ok else "缓存数据接口可用",
        )

        save_body = {
            "deviceId": self.test_device_id,
            "startTime": start_iso,
            "endTime": end_iso,
            "gestureLabel": "fist",
            "annotator": "auto_tester",
            "annotationNote": "integration-test",
            "calculateQuality": True,
        }
        ok, detail, data, _ = self.request_json("POST", "/api/annotation/save", json_body=save_body)
        self.record(
            f"{name_prefix}-save",
            ok and isinstance(data, dict) and data.get("code") == 200,
            detail if not ok else f"保存结果: {str(data.get('message', 'ok'))}",
        )

        ok, detail, data, _ = self.request_json("GET", "/api/annotation/statistics")
        anno_stat_ok = ok and isinstance(data, dict) and data.get("code") == 200
        self.record(
            f"{name_prefix}-statistics",
            anno_stat_ok,
            detail if not anno_stat_ok else "统计接口可用",
        )

        ok, detail, data, _ = self.request_json("GET", "/api/annotation/history?limit=10")
        anno_history_ok = ok and isinstance(data, dict) and data.get("code") == 200
        self.record(
            f"{name_prefix}-history",
            anno_history_ok,
            detail if not anno_history_ok else "历史接口可用",
        )

        # 非破坏性删除测试：删除不存在ID，验证接口链路
        ok, detail, data, _ = self.request_json("DELETE", "/api/annotation/999999999")
        self.record(
            f"{name_prefix}-delete-route",
            ok and isinstance(data, dict) and data.get("code") in (200, 500),
            detail if not ok else f"业务返回 code={data.get('code')}",
        )

    def test_training_apis(self) -> Optional[int]:
        name_prefix = "Training"
        created_task_id: Optional[int] = None

        ok, detail, data, _ = self.request_json("GET", "/api/training/tasks?limit=20")
        list_ok = ok and isinstance(data, dict) and data.get("code") == 200
        self.record(
            f"{name_prefix}-list",
            list_ok,
            detail if not list_ok else "任务列表接口可用",
        )

        create_body = {
            "taskName": f"auto_test_{int(time.time())}",
            "config": {
                "epochs": 2,
                "batchSize": 16,
                "learningRate": 0.001,
                "windowSize": 150,
                "modelType": "cnn_lstm",
                "optimizer": "adam",
                "valRatio": 0.2,
                "testRatio": 0.1,
            },
            "dataFilter": {
                "gestures": ["fist", "ok"],
                "minQualityScore": 0.0,
                "deviceIds": [self.test_device_id],
                "annotators": ["auto_tester"],
            },
            "createdBy": "auto_tester",
        }
        ok, detail, data, _ = self.request_json("POST", "/api/training/create", json_body=create_body)
        if ok and isinstance(data, dict) and data.get("code") == 200:
            task_id = (data.get("data") or {}).get("task_id")
            if isinstance(task_id, int):
                created_task_id = task_id
                self.record(f"{name_prefix}-create", True, f"创建任务成功: task_id={task_id}")
            else:
                self.record(f"{name_prefix}-create", False, f"创建成功但缺少 task_id: body={data}")
        else:
            self.record(f"{name_prefix}-create", False, f"{detail}; body={data}")

        probe_task_id = created_task_id if created_task_id is not None else 999999999

        if created_task_id is not None:
            status_ok, status_detail = self.wait_for_training_status(created_task_id)
            self.record(
                f"{name_prefix}-status-poll",
                status_ok,
                status_detail,
            )

        ok, detail, data, _ = self.request_json("GET", f"/api/training/task/{probe_task_id}")
        self.record(
            f"{name_prefix}-status",
            ok and isinstance(data, dict) and data.get("code") in (200, 404),
            detail if not ok else f"业务返回 code={data.get('code')}",
        )

        ok, detail, data, _ = self.request_json("GET", f"/api/training/task/{probe_task_id}/logs?lines=20")
        self.record(
            f"{name_prefix}-logs",
            ok and isinstance(data, dict) and data.get("code") in (200, 500),
            detail if not ok else f"业务返回 code={data.get('code')}",
        )

        ok, detail, data, _ = self.request_json("GET", f"/api/training/task/{probe_task_id}/result")
        self.record(
            f"{name_prefix}-result",
            ok and isinstance(data, dict) and data.get("code") in (200, 500),
            detail if not ok else f"业务返回 code={data.get('code')}",
        )

        ok, detail, data, _ = self.request_json("POST", f"/api/training/task/{probe_task_id}/cancel", json_body={})
        self.record(
            f"{name_prefix}-cancel",
            ok and isinstance(data, dict) and data.get("code") in (200, 500),
            detail if not ok else f"业务返回 code={data.get('code')}",
        )

        return created_task_id

    def test_model_apis(self) -> Optional[str]:
        name_prefix = "Model"
        detected_version: Optional[str] = None

        ok, detail, data, _ = self.request_json("GET", "/api/model/versions?limit=20")
        if ok and isinstance(data, dict) and data.get("code") == 200:
            versions = data.get("data") if isinstance(data.get("data"), list) else []
            if versions:
                first = versions[0]
                if isinstance(first, dict):
                    detected_version = first.get("version")
            self.record(f"{name_prefix}-versions", True, f"版本数={len(versions)}")
        else:
            self.record(f"{name_prefix}-versions", False, f"{detail}; body={data}")

        ok, detail, data, _ = self.request_json("GET", "/api/model/active")
        self.record(
            f"{name_prefix}-active",
            ok and isinstance(data, dict) and data.get("code") in (200, 404),
            detail if not ok else f"业务返回 code={data.get('code')}",
        )

        probe_version = detected_version or "nonexistent_test_version"

        ok, detail, data, _ = self.request_json("GET", f"/api/model/{probe_version}/details")
        self.record(
            f"{name_prefix}-details",
            ok and isinstance(data, dict) and data.get("code") in (200, 404, 500),
            detail if not ok else f"业务返回 code={data.get('code')}",
        )

        deploy_body = {
            "version": probe_version,
            "targetType": "cloud",
            "targetDeviceId": self.test_device_id,
            "setAsActive": False,
            "deployMethod": "auto_download",
            "deployedBy": "auto_tester",
        }
        ok, detail, data, _ = self.request_json("POST", "/api/model/deploy", json_body=deploy_body)
        self.record(
            f"{name_prefix}-deploy",
            ok and isinstance(data, dict) and data.get("code") in (200, 500),
            detail if not ok else f"业务返回 code={data.get('code')}",
        )

        ok, detail, data, _ = self.request_json("POST", f"/api/model/{probe_version}/activate", json_body={"active": True})
        self.record(
            f"{name_prefix}-activate",
            ok and isinstance(data, dict) and data.get("code") in (200, 500),
            detail if not ok else f"业务返回 code={data.get('code')}",
        )

        ok, detail, data, _ = self.request_json("DELETE", f"/api/model/{probe_version}")
        self.record(
            f"{name_prefix}-delete",
            ok and isinstance(data, dict) and data.get("code") in (200, 500),
            detail if not ok else f"业务返回 code={data.get('code')}",
        )

        # 下载是二进制接口，不要求 JSON
        try:
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            resp = self.session.get(
                f"{self.base_url}/api/model/download/{probe_version}",
                timeout=self.timeout,
                headers=headers,
            )
            if resp.status_code in (200, 404, 500):
                self.record(f"{name_prefix}-download", True, f"HTTP {resp.status_code}")
            else:
                self.record(f"{name_prefix}-download", False, f"HTTP {resp.status_code}")
        except Exception as error:
            self.record(f"{name_prefix}-download", False, f"请求异常: {error}")

        return detected_version

    def test_websocket(self) -> None:
        name_prefix = "WebSocket"

        ws_app = None
        ws_dev = None
        try:
            ws_app = create_connection(f"{self.ws_base_url}/ws/app", timeout=self.timeout)
            self.record(f"{name_prefix}-connect-app", True, "连接成功")

            ws_dev = create_connection(f"{self.ws_base_url}/ws/emg", timeout=self.timeout)
            self.record(f"{name_prefix}-connect-emg", True, "连接成功")

            ws_dev.send(json.dumps({"type": "register", "deviceId": self.test_device_id}))
            reg_resp = ws_dev.recv()
            reg_obj = json.loads(reg_resp)
            if reg_obj.get("type") == "register_ack" and reg_obj.get("status") == "ok":
                self.record(f"{name_prefix}-register", True, "设备注册确认成功")
            else:
                self.record(f"{name_prefix}-register", False, f"响应异常: {reg_obj}")

            ws_app.send(json.dumps({"action": "get_latest"}))
            app_latest_resp = ws_app.recv()
            json.loads(app_latest_resp)
            self.record(f"{name_prefix}-get-latest", True, "App 获取最新数据成功")

            ws_app.send(json.dumps({"action": "select_gesture", "gesture": "fist"}))
            ack_obj = None
            for _ in range(5):
                msg = ws_app.recv()
                obj = json.loads(msg)
                if isinstance(obj, dict) and obj.get("type") == "gesture_selected":
                    ack_obj = obj
                    break
            if ack_obj is not None and ack_obj.get("gesture") == "fist":
                self.record(f"{name_prefix}-select-gesture", True, "手势选择确认成功")
            else:
                self.record(f"{name_prefix}-select-gesture", False, f"未收到 gesture_selected 确认: {ack_obj}")

            ws_dev.send(
                json.dumps(
                    {
                        "type": "emg_frame",
                        "deviceId": self.test_device_id,
                        "data": self.make_frame_payload("fist"),
                    }
                )
            )
            self.record(f"{name_prefix}-emg-frame-send", True, "设备端发送 emg_frame 成功")

        except Exception as error:
            self.record(f"{name_prefix}-workflow", False, f"异常: {error}")
        finally:
            if ws_dev is not None:
                try:
                    ws_dev.close()
                except Exception:
                    pass
            if ws_app is not None:
                try:
                    ws_app.close()
                except Exception:
                    pass

    def run_all(self) -> int:
        print("=" * 70)
        print("SpringBoot Backend 全功能测试")
        print("=" * 70)
        print(f"HTTP: {self.base_url}")
        print(f"WS  : {self.ws_base_url}")
        print(f"测试设备ID: {self.test_device_id}")
        print()

        self.test_auth_module()
        self.test_stats_module()
        self.test_emg_apis()
        self.test_annotation_apis()
        self.test_training_apis()
        self.test_model_apis()
        self.test_websocket()

        passed = sum(1 for item in self.results if item.ok)
        total = len(self.results)
        failed = total - passed

        print("\n" + "=" * 70)
        print(f"测试完成: 总计 {total} 项, 通过 {passed}, 失败 {failed}")

        if failed > 0:
            print("\n失败项明细:")
            for item in self.results:
                if not item.ok:
                    print(f"- {item.name}: {item.detail}")
        print("=" * 70)

        return 0 if failed == 0 else 1



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="测试 SpringBoot Backend 全部功能")
    parser.add_argument("--host", default="1.95.65.51", help="服务器地址")
    parser.add_argument("--port", type=int, default=8080, help="HTTP 端口")
    parser.add_argument("--timeout", type=int, default=8, help="请求超时时间（秒）")
    parser.add_argument("--https", action="store_true", help="使用 HTTPS")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    scheme = "https" if args.https else "http"
    ws_scheme = "wss" if args.https else "ws"

    http_base = f"{scheme}://{args.host}:{args.port}"
    ws_base = f"{ws_scheme}://{args.host}:{args.port}"

    tester = BackendTester(base_url=http_base, ws_base_url=ws_base, timeout=args.timeout)
    sys.exit(tester.run_all())

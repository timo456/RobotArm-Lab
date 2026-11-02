# RobotArm-Lab 使用文件

這是一套可實際操作、可重現驗證的六軸機械手臂**運動學模擬**。模型 RAL-6
為本專案原創幾何，不代表任何特定廠牌。它示範運動學、軌跡時間參數化與碰撞拒絕，
不包含實體伺服控制、安全 PLC、力矩控制或工業安全認證。

## 安裝與啟動

建議 Windows 10、Python 3.12（含 Tcl/Tk）。PyBullet 3.2.7 在此 Windows 組合須
從原始碼編譯，需要已安裝的 Visual Studio 2022 Build Tools、C++ 桌面開發工具與
Windows SDK。請參照英文 README 的完整安裝命令，或在專案根目錄執行：

```powershell
.\scripts\bootstrap.ps1
.\.venv\Scripts\python.exe -m robotarm_lab gui
```

安裝腳本只建立專案內的 `.venv`、`.tmp` 與 `.cache`，不修改全域 Python。
本交付位於 `E:\GitHubProjects\RobotArm-Lab`；執行前請確認 E 槽已連接。
若 PowerShell 阻擋腳本，可直接使用 README 的逐行命令，不需更改系統執行原則。

## 操作

- 六個滑桿以「度」設定關節目標，再按 Execute joint target。滑桿本身不移動手臂。
- Home 會規劃平滑回歸路徑；若途中有障礙物，同樣拒絕執行。
- Reset scene 是明確的模擬重置，會清除障礙物並直接回 Home，不代表真機復歸程序。
- Demo 會移往展示姿態；Add blocker 可插入阻擋展示路線的障礙物。
- Clear obstacles 清除障礙物。程式 API 的 `World.add_box(center, half_extents)`
  支援任意軸對齊箱型障礙物，數值單位是公尺，尺寸輸入為半長。
- TCP 欄位 X/Y/Z 使用公尺；Roll/Pitch/Yaw 使用度，採固定軸 XYZ 順序。
  按 Solve IK + execute，求解後還需通過位置誤差、姿態誤差、關節限制與路徑碰撞驗證。
- STOP / FREEZE 立即凍結模擬。真實機械手臂不可能如此瞬間停止，此處不模擬煞車距離。
- 視角滑桿旋轉相機；Save viewport PNG 將目前 3D 畫面存入輸出目錄。

狀態列顯示 IDLE、RUNNING、STOPPED、BLOCKED；拒絕指令會顯示原因。
監控包含六軸角度、TCP、最大關節速度、障礙物數量與模擬時間。
執行中的新命令會被拒絕；請先等待完成或停止。GUI 不是即時控制系統；畫面較慢時，
模擬時間可能落後真實時間。規劃期間 GUI 暫時同步等待，手臂尚未開始移動。

## 測試與報告

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m robotarm_lab benchmark --output outputs\benchmark
.\.venv\Scripts\python.exe -m robotarm_lab demo --output outputs\demo
```

批次驗證使用固定種子 20261102，門檻於第一次驗證前存入 `acceptance.json`。
`results.json` 保留每個成功與失敗案例，`report.md` 提供摘要。
測試包含 FK 與 PyBullet 的交叉比較、正常／接近關節界限的 IK、不可達目標、
障礙物拒絕、軌跡速度／加速度與執行結果。正常 IK 從 Home 冷啟動；極限 IK
使用接近解的擾動種子，兩者成功率不可混為一談。運動學可解不代表無碰撞可達。

示範產生 `demo.gif`、`demo.png`、逐步 `telemetry.csv` 與 `demo.jsonl`。
互動紀錄位於 `outputs/gui/session.jsonl`，採一行一筆 JSON。
請參閱 [實測範圍](VALIDATION.md) 與 [限制](LIMITATIONS.md)。

## 常見錯誤

| 訊息 | 原因與處理 |
|---|---|
| Joint limit exceeded | 輸入超過六軸角度範圍，降低目標角度 |
| Unreachable target | 目標超出保守最大伸展距離 |
| IK rejected | 有界求解未達位姿門檻；不代表數學上絕對無解 |
| Collision clearance rejected | 路徑碰撞或距離小於安全餘裕；調整姿態或障礙物 |
| Busy | 目前仍在運動中，先等待或停止 |
| BLOCKED | 移動途中碰撞檢查失敗，已凍結，需修改場景或重置 |

預設每段關節插值最大 0.01 rad、碰撞餘裕 3 mm，屬離散取樣檢查，可能漏掉
非常薄或高速相對運動的障礙物。不得據此宣稱真機安全、零碰撞保證或安全認證。

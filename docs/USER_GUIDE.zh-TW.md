# RobotArm-Lab 0.2.0 繁體中文操作指南

這是六軸機械手臂的 **運動學模擬工作站**。控制核心會檢查關節限制與離散路徑碰撞，
但沒有真實馬達、硬體控制器、力矩追蹤或實體安全認證。外觀殼件、夾爪與工作台是視覺模型；
碰撞仍使用原始 RAL-6 代理幾何。請開啟 Collision proxies 查看實際檢查的形狀。

## 安裝與啟動

專案位於 `E:\GitHubProjects\RobotArm-Lab`，v0.2 使用獨立 `.venv-workstation`，保留舊 `.venv`。
需要 Windows 10、Python 3.12 及可用 OpenGL 桌面。

```powershell
cd E:\GitHubProjects\RobotArm-Lab
powershell -File scripts\bootstrap.ps1
.\.venv-workstation\Scripts\python.exe -m robotarm_lab gui
```

PyBullet 3.2.7 沒有官方 Windows Python 3.12 wheel。首次安裝需可信任的本機 wheel，
放在 `.cache/wheelhouse`；或安裝 Visual Studio 2022 Build Tools 的 C++ 桌面開發與 Windows SDK，
再明確執行 `powershell -File scripts\bootstrap.ps1 -AllowSourceBuild`。安裝器不會偷偷編譯。
所有下載、快取與暫存都在專案內。沒有全域 Python 套件修改。

遇到顯示卡／遠端桌面 OpenGL 問題，可在啟動前設定 `$env:QT_OPENGL = 'software'`。
這使用 Qt 軟體渲染，效能依機器而異。刪除該環境變數後重新啟動即可恢復 GPU。
完整手動安裝與 Ubuntu 3.11 指令見英文 README。

## 第一段操作：預覽，再執行

1. 左側 **Joint jog** 輸入六軸目標角度（度）。按 **Preview target**，會顯示透明預覽機械臂與 TCP 路徑。
2. 拖曳視窗中央下方時間軸查看沿途姿態。實際機械臂不會因預覽或拖曳而移動。
3. 按 **Execute preview** 執行。改動目標、障礙物、速度或起始姿態後，必須重新預覽。
4. 手動模式下，用每軸 −／+ 做有限角度點動。這是經規劃、限速與碰撞檢查的短段移動。

**TCP / IK** 的 XYZ 是世界座標毫米；Roll/Pitch/Yaw 是 extrinsic XYZ 歐拉角（度）。
按 **Use current TCP** 可帶入當前位姿。IK 成功還需通過獨立位姿驗證及碰撞檢查。
不可達、關節超限或碰撞目標會顯示拒絕原因，保持原本姿態。Python API 使用公尺與弧度。

## 運動與模式

| 控制 | 行為 |
|---|---|
| Home / F5 | 經檢查規劃至 Home |
| Demo / F6 | 切換 Auto，依序執行三個展示姿態，最後回 Home |
| Pause / Space | 固定目前模擬姿態；Resume 從靜止重新規劃剩餘段 |
| Speed | 10–100%；影響速度與加速度限制。執行中變速先保持再重規劃 |
| Freeze / Esc | 取消待處理命令，終止可取消的路徑驗證，保持模擬姿態 |
| Reset / F9 | 清除障礙物、預覽與運動狀態，將模擬姿態直接恢復 Home |
| Manual / Auto | Manual 允許點動；Auto 允許教導點序列；執行中不可切換 |

Pause／Freeze 是運動學保持，沒有物理減速或制動模型；Reset 是明確的模擬重置。
規劃在背景執行，GUI 保持回應。IK 有原始求解預算，但無法在每一個數值運算中立刻中斷。

## 教導點

在靜止時切換 **Teach**，輸入名稱並按 **Capture current pose**。清單可選取預覽／執行，
也可刪除。Auto 模式下 **Play library sequence** 依清單順序播放，每一段都重新驗證。
最多 100 個教導點；同名儲存會更新既有姿態。

資料以原子替換方式寫入 `outputs/gui/teach-points.json`。重新啟動使用同一輸出資料夾才會載入。
可用 `--output outputs\my-cell` 分開不同工作站資料。損毀的檔案會顯示錯誤，不會偷偷接受無效角度；
修正或備份移除損毀資料後重新啟動。Reset 不會刪除教導點。

## 障礙物與碰撞示範

右側 **Scene** 輸入箱體中心與完整長寬高（毫米），可新增、選取後更新、刪除或全部清除。
**Add demo blocker** 在展示路徑放入障礙物，再按 Demo 可看到預覽拒絕。
執行期間插入障礙物，控制器會使用原始逐步碰撞檢查並轉入 BLOCKED。
若新障礙物直接與當前姿態重疊，停止無法消除既有重疊；移除障礙物或 Reset 後再操作。

碰撞是離散採樣與安全間距檢查，沒有連續碰撞保證，也不會自動繞障礙。
外觀殼件可能超出碰撞代理，不能用外觀表面距離推斷安全性。

## 視角、狀態與記錄

滑鼠左鍵拖曳旋轉視角、右鍵拖曳平移、滾輪縮放。Reset view 還原視角。
Capture 儲存實際 Qt 視窗 PNG。中央有軌跡、世界與 TCP 座標軸、透明目標及時間進度。
右側顯示關節角度、TCP 位姿、峰值關節速度、序列進度與碰撞間距接觸數。

小視窗使用分割面板與捲動區；預覽／執行按鈕固定在左側底部。事件表保留最近 500 筆，
完整 JSONL 寫入 `outputs/gui/session.jsonl`。軌跡尾跡最多 2048 點，磁碟日誌不自動輪替。
日誌無法寫入時進入 FAULT；排除磁碟／權限問題後 Reset。渲染故障會保持運動，需修復顯示環境後重啟。

## 驗證與交付界線

執行 README 的 pytest、benchmark、hardening、workstation_verify、workstation_soak 與
clean_environment 指令可重現結果。`workstation_soak` 包含 30 秒暖機與 600 秒持續播放。
視窗測試使用真正 Qt Widgets／OpenGL、QTest 輸入與 Qt 擷取，沒有合成示意圖。
125%／150% 測試使用 Qt 縮放因子，不代表改動全域 Windows 顯示設定。

精確數據、失敗紀錄、遠端 CI 狀態與未驗證項目見 [驗證報告](WORKSTATION_VALIDATION.md)。
舊 Tk 介面可用 `python -m robotarm_lab gui-legacy`；原本演算法與驗收門檻仍保留。

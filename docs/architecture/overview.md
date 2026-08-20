# OpenSprite architecture

## 目標

新架構先建立清楚、淺層且可從根目錄辨識的邊界。前端先完成使用流程，後端再依實際契約補上最小能力。

```text
Frontend -> Contracts <- Backend
                 ^
                 |
             Installers
```

## 邊界

- Frontend 只透過明確契約與未來後端溝通，不讀取 Python implementation。
- Backend 不依賴 frontend source；它只實作已批准的契約與服務能力。
- Contracts 不包含 UI、資料庫或 provider implementation。
- Installers 只處理部署與 lifecycle，不承擔產品行為。
- Scripts 只承擔可重現的 repository 驗證與維護工作。

## 目前階段

本階段只建立 frontend-first foundation。Frontend 尚不可執行；Backend、contracts 與 installers 都只有責任說明和資料夾位置。

## 長期限制

- 不建立應用程式 CLI。
- 不恢復關鍵字任務分類或舊 Task lifecycle。
- 不用相容 alias、停用開關或死碼保留舊架構。
- 不在需求出現前預建抽象層、registry 或跨功能 shared service。
- 舊版存檔只能作為行為參考，所有新程式必須依目前需求重新建立。

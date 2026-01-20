# VNPY Mac DMG 自动打包说明

## 项目信息

- **源项目**: https://github.com/xucongyong/vnpy_uv_macos
- **你的仓库**: https://github.com/l11223/vnpy_uv_macos
- **VNPY 版本**: 4.3.0

## 你的设备

- MacBook Air M4 2025
- Apple Silicon (ARM64)
- 使用 `macos-14` 运行器（ARM64 原生）

## GitHub Actions 工作流

工作流文件: `.github/workflows/build_dmg.yml`

### 触发方式

1. **推送触发**: 推送到 `main` 分支自动构建
2. **手动触发**: GitHub 仓库 -> Actions -> 点击 "Run workflow"

### 构建步骤

1. 安装系统依赖 (ta-lib, create-dmg)
2. 安装 Python 依赖 (PySide6, numpy, pandas, talib 等)
3. PyInstaller 打包 (--onefile --windowed)
4. 创建 DMG 镜像

### 包含的功能模块

- VNPY 4.3.0 核心框架
- CTA策略引擎 (vnpy_ctastrategy)
- CTA回测模块 (vnpy_ctabacktester)
- 富途接口 (vnpy_futu)
- AI量化模块 (vnpy.alpha)
- SQLite 数据库 (vnpy_sqlite)

## 下载 DMG

1. 进入 GitHub 仓库
2. 点击 "Actions" 标签
3. 选择最新成功的构建
4. 在底部 "Artifacts" 下载 `VNPY-Mac-DMG`

## 安装说明

1. 双击下载的 DMG 文件
2. 将 VNPY.app 拖到 Applications 文件夹
3. 首次运行：右键点击 -> 打开

如遇安全提示，在终端执行：
```bash
xattr -d com.apple.quarantine /Applications/VNPY.app
```

## 系统要求

- macOS 11.0+ (Big Sur 或更新)
- Apple Silicon (M1/M2/M3/M4)

## 依赖版本

- Python 3.12
- PySide6 6.8.2.1
- numpy 2.2.3
- TA-Lib 0.6.4
- pandas 2.2.3

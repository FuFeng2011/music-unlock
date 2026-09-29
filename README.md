# 音乐解锁（Music Unlock）

本地离线解密网易云音乐与酷狗音乐的加密音频文件，转换为通用的 FLAC / MP3。
纯本地处理，文件不会上传到任何网络服务。

- 网易云音乐：`.ncm`
- 酷狗音乐：`.kgm`（新旧两种格式）、`.kgma`（当前新格式）、`.vpr`

输出格式根据解密后的音频魔数自动判定：`fLaC` → FLAC，其余 → MP3。NCM 会读取内嵌元数据命名（歌名 - 歌手）并提取封面。

## 用法

### 单文件桌面版（推荐）

`dist\MusicUnlock.exe` —— 双击即用，内嵌 WebView2 窗口加载界面，**无需安装 Python、无需浏览器**。输出保存在 exe 同目录的 `output` 文件夹。

兼容性：Windows 10/11 开箱即用（系统自带 WebView2 运行时）；Windows 7/8.1 需先安装一次 [WebView2 运行时](https://developer.microsoft.com/microsoft-edge/webview2/)；不支持 32 位 Windows。首次运行如被杀毒软件拦截，请选择"允许"（PyInstaller 单文件打包的常见误报）。

重新打包：`build\venv\Scripts\pyinstaller.exe MusicUnlock.spec`（先 `build\venv\Scripts\python.exe -m pip install -r build\requirements.txt` 恢复构建环境）。

### 图形界面（网页版，开发调试用）

```powershell
& "D:\Tool-ComfyUI-aki\ComfyUI-aki-v2\python\python.exe" "D:\Tool-MusicUnlock\gui.py"
```

浏览器自动打开 `http://127.0.0.1:7867`，把文件（可多个）拖进界面即可，结果保存在 `output` 文件夹。

### 命令行

```powershell
python cli.py convert <文件/目录/通配符...> --output-dir <目录> --json
python cli.py capabilities --json
```

支持整目录与通配符批量转换：

```powershell
python cli.py convert "D:\Music\*.kgma" "D:\Music\网易云" --output-dir "D:\Music\out" --json
```

### ZCode skill

另附 `~\.zcode\skills\music-unlock\`（SKILL.md + scripts/run.ps1），可让 ZCode 代理直接调用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.zcode\skills\music-unlock\scripts\run.ps1" convert <文件...> --output-dir <目录> --json
```

## 测试

```powershell
python test_roundtrip.py   # 9 项加密→解密往返测试
```

## ⚠️ 使用声明

- 本工具仅用于转换**你个人合法获得或缓存的音乐文件**（例如你已购买/订阅后下载到本机的文件）。
- **请勿**将其用于破解付费限制、绕过授权，或传播、贩卖任何音乐内容。由此产生的一切后果由使用者自行承担。

## 许可证

本项目以 GNU Affero General Public License v3.0 或更新版本（AGPL-3.0-or-later）发布，详见 [LICENSE](LICENSE)。核心算法移植自其他开源项目，详见 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)。

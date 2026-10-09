# 网易云音乐下载器 · Windows 版

可直接安装的单文件程序位于 [`../dist/网易云音乐下载器-安装程序-Windows-x64.exe`](https://github.com/wangchuanao2008/netease-music-downloader/releases/download/v1.1.0/%E7%BD%91%E6%98%93%E4%BA%91%E9%9F%B3%E4%B9%90%E4%B8%8B%E8%BD%BD%E5%99%A8-%E5%AE%89%E8%A3%85%E7%A8%8B%E5%BA%8F-Windows-x64.exe)。双击后按向导安装；安装完成后从开始菜单启动，首次使用时选择保存目录。安装器为当前用户安装，无需管理员权限，也不要求另装 Python。可选创建桌面快捷方式，之后可在 Windows“已安装的应用”中卸载。

此文件夹包含可独立复制到 Windows 的完整源码。支持网易云单曲完整链接、`163cn.tv` 分享短链、整段分享文字和一次粘贴多个单曲链接。程序自动排队下载，可选 GD Studio 同一网易云歌曲 ID 的备用来源。QQ 音乐、歌名搜索、歌单和专辑不在本版范围内。

## 运行源码

如果使用上面的安装程序，无需执行本节。要运行源码，请准备 Windows 10/11 x64 系统及 x64 Python 3.10 或更新版本。建议安装 Python 时启用 `py` 启动器。在 PowerShell 中进入本文件夹：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

首次使用时选择保存目录。之后粘贴网易云单曲链接即可自动入队。下载列表可取消、重试或在资源管理器中显示文件。默认保留实际音频格式和音质；界面上的格式、码率和无损状态从保存后的文件读取。

转换为 MP3 需要 `ffmpeg.exe`。从 [FFmpeg 官网](https://ffmpeg.org/download.html)获取 Windows 版本，将其加入 `PATH`，或放在 `run.py` 旁边；使用打包应用时也可放在 `.exe` 旁边。不转换时无需 FFmpeg。

依赖：PySide6 Essentials、httpx、mutagen，版本见 `requirements.txt`。应用数据与重复下载记录使用 Windows 用户的 Qt 应用数据目录；保存目录由用户选择。应用不要求登录，也不保存账号凭据。

## 在 Windows 上打包

准备 x64 Python 3.10+ 和 [Inno Setup 7](https://jrsoftware.org/isdl.php)。在本文件夹用 PowerShell 执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_windows.ps1
```

脚本会创建虚拟环境、安装依赖、运行测试，用 PyInstaller 生成应用文件夹，再用 Inno Setup 7 生成 `dist\installer\网易云音乐下载器-安装程序-Windows-x64.exe`。只需分发这一个安装程序文件。打包程序默认不包含 FFmpeg；选择“转换为 MP3”仍需按上文安装 `ffmpeg.exe`。安装器没有代码签名，下载后可能触发 Windows SmartScreen 提示。

PyInstaller [要求在目标操作系统上分别打包](https://pyinstaller.org/en/latest/usage.html)。本安装程序已在 Parallels Windows 11 ARM64 虚拟机中使用 x64 Python 和 Inno Setup 7 构建，并在 Windows 的 x64 兼容层中完成静默安装、安装文件和卸载程序检查、启动及首次目录选择界面检查。原生 x64 Windows 硬件仍未实测。

## 功能与限制

- 歌曲信息来自网易云 `music.163.com/api/song/detail/`；优先使用公开音频地址，备用来源通过 [GD Studio](https://music.gdstudio.xyz/) 查询同一个网易云歌曲 ID，并仅接受网易云 CDN 地址。第三方服务的稳定性及其上游授权情况无法由本程序保证。
- 保存前验证音频格式与时长；试听片段或无法解码的内容不会显示为成功。支持 MP3、M4A 和 FLAC，转换为 MP3 需另装 FFmpeg。
- 文件名默认“歌手 - 歌曲名”；尽可能写入歌曲名、歌手、专辑和封面。Windows 不允许的文件名字符会被替换。
- 版权、会员、地区限制和接口变化可能导致某些歌曲无法取得完整音频，失败原因会显示在任务状态中。

## 测试

在 Windows 安装依赖后运行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Windows 虚拟机运行了 6 项单元测试：5 项通过，1 项依赖 FFmpeg 生成测试音频而跳过。用于手工验收的网易云示例：`https://music.163.com/song?id=33894312`（公开音频）和 `https://music.163.com/song?id=210049`（备用来源样本）。本机 macOS 测得前者为约 267 秒的 128 kbps MP3，后者为约 294.6 秒的 FLAC，并能完整解码；Windows 下的真实下载和播放尚未实测。

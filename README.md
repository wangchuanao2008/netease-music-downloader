# 网易云音乐下载器（macOS / Apple Silicon）

粘贴网易云音乐的单曲分享链接或整段分享文字，程序先提取链接、读取歌曲信息和该曲的音质目录。选择歌曲及音质并点击“下载所选歌曲”后，才会请求并保存完整音频。一次可以粘贴多个单曲链接，并为每首歌分别选择音质；选好后也可点击“下载全部已选音质”。此版本仅支持网易云音乐，不提供歌名搜索或 QQ 音乐解析。

## 下载

现成的 macOS Apple Silicon 应用、Windows x64 安装程序和 Android APK 可在 [GitHub Releases](https://github.com/wangchuanao2008/netease-music-downloader/releases/latest) 下载。各平台功能与验证情况见下文及对应平台说明。

## 启动

要求 macOS 13 或更新版本、Apple Silicon、Python 3.10+。本机验证环境为 macOS 26、Apple M5、Python 3.14。

```sh
cd netease-music-downloader
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m musicdown
```

首次启动时选择保存目录。之后可点击“官网登录”，在应用内打开的网易云官网点击“用户登录”，用网易云音乐 App 扫码并完成网易云要求的安全验证；验证后的登录会话仅保存在 macOS 钥匙串中，可在软件内退出。粘贴链接约 0.65 秒后开始后台解析，不会自动下载。点击已解析的歌曲行后，音质菜单会启用该曲目录中有记录的标准、较高、极高、无损、Hi-Res、超清母带、高清臻音、沉浸环绕声、臻音全景声和杜比全景声等档位，其他档位不可选；各档位标注通常所需的会员等级。必须再选择音质并点击下载按钮。空间音频是不同混音，不参与“自动最高可用”的普通音质排序。选定具体音质时，如果网易云实际降级或只返回试听，任务会失败并显示原因；“自动”会优先取账号可用的最高普通音质。下载列表显示歌曲、歌手、封面、该曲目录列出的音质类别、实际音质、进度和状态；可取消、失败重试、在 Finder 中显示文件。目录档位不等于账号有权限下载，实际成功与音质以保存文件校验为准。默认保留源音频格式。转换为 MP3 需安装 FFmpeg：

```sh
brew install ffmpeg
```

依赖：PySide6 Essentials/Addons 用于界面和内嵌官方网页登录页，httpx 用于网络，mutagen 用于识别音频和写入标签，pycryptodome 用于网易云音质请求，keyring 将登录凭据存入 macOS 钥匙串。FFprobe 用于精确识别音频编码、码率和空间音频容器；FFmpeg 用于转换 MP3。两者可通过上述 Homebrew 命令安装，打包的应用不内置。

## 支持的链接与来源

- 网易云单曲链接：`music.163.com/song?id=...`、`music.163.com/#/song?id=...`、`y.music.163.com/m/song?id=...`，以及跳转到这些地址的 `163cn.tv` 分享短链。歌单和专辑链接不在本版范围内。
- 歌曲信息来自 `music.163.com/api/song/detail/`。音频优先通过网易云的 `interface3.music.163.com/eapi/song/enhance/player/url/v1` 按所选音质请求，登录后携带账号会话。自动音质失败时再尝试 `music.163.com/song/media/outer/url` 公开音频；仍失败且勾选备用来源时，通过 GD Studio 查询同一个网易云歌曲 ID。具体音质选项只使用网易云音质接口，不静默改用低音质或第三方。只接受网易云音频 CDN `*.music.126.net` 的音质接口地址。
- 单曲目录音质来自 `music.163.com/api/song/music/detail/get?songId=...` 的 `l/m/h/sq/hr/jm/je/sk/sks/vi/db` 字段；字段缺失或为空时相应档位不可选。目录查询失败会显示解析失败，可重试解析。这个目录是平台提供的档位信息，不表示会员权限、当前设备支持或可导出完整音频。会员标注为通常要求：标准/较高/极高的音质功能本身无需会员，会员歌曲仍可能需要付费权益；无损/Hi-Res/高清臻音通常需要 VIP；超清母带/沉浸环绕声/杜比全景声/臻音全景声通常需要 SVIP。具体以网易云实时授权为准。
- 保存前检测文件格式和时长；只有可解析、时长与歌曲信息相符的音频才标为成功。界面上的编码、码率和无损状态来自保存后的文件检测，不依赖接口标称音质。文件名默认“歌手 - 歌曲名”，尽可能写入歌曲名、歌手、专辑和封面。

原平台音质接口调用方法参考 [yt-dlp 的网易云提取器](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/neteasemusic.py) 与 [NeteaseCloudMusicApiEnhanced](https://github.com/NeteaseCloudMusicApiEnhanced/api-enhanced)；单曲目录接口参考该项目的 [song_music_detail 模块](https://github.com/NeteaseCloudMusicApiEnhanced/api-enhanced/blob/main/module/song_music_detail.js)。会员等级标注参考 [荣耀与网易云互通音乐服务的会员权益说明](https://www.honor.com/cn/support/content/zh-cn15851976/)和[音质权益说明](https://www.honor.com/cn/support/content/zh-cn15851939/)，其中部分细分档位是根据相近权益推定，界面统一标为“通常要求”，不能替代网易云实时的歌曲授权判断。旧版自绘二维码实际扫码后被网易云拒绝；后续网页版二维码又要求额外安全验证，因此改为内嵌 `https://music.163.com/` 官方网页，让用户直接完成网页登录和验证，应用只读取该站设置的登录会话。网易云没有为本软件提供稳定的公开下载 API；接口可能变化。备用来源由 [GD Studio](https://music.gdstudio.xyz/) 提供，接口可用性和上游取得音频的授权或凭据情况无法由本程序核实。

## 已知限制

- 仅支持网易云音乐单曲分享链接；QQ 音乐及其他平台链接会显示“不支持”。没有歌名或歌手搜索框。
- 会员音质需要用户自己的账号具备对应权益；扫码登录不要求在本软件中输入密码。登录凭据只存在本机钥匙串，不发送给 GD Studio。第三方备用接口可能停用、限流，或只提供部分歌曲；不保证每首会员曲均可取得完整文件。
- 十个选项表示尝试向网易云请求对应档位，不表示每首歌都提供十种文件。超清母带等普通档位按接口返回的实际等级和文件无损属性核对；空间音频需单独选择。杜比请求还会检查文件是否为 AC-3/E-AC-3，但仅凭编码无法证明文件带有 Atmos 元数据，因此杜比全景声档位尚需真实文件验收。臻音全景声在已测试歌曲上返回 `av3a`（AVS3 Audio Vivid）编码：程序可以原样保存 `.m4a`，核对容器、时长和全部音频包，并标为“已保存（未验证解码）”。本机标准版 FFmpeg 8.1.2 没有该音频解码器，因此无法保证 macOS 普通播放器可以播放，也不能把这一档转换为 MP3。转换其他音质为 MP3 后音频为有损格式，空间音效和母带属性不能保留。
- 用户提供的 SVIP 账号已实测超清母带、无损、Hi-Res、高清臻音和沉浸环绕声的完整保存流程；其余档位是否能用于某首歌仍取决于平台实际返回。账号即使可播放，也可能因版权、地区、单曲购买或平台导出限制而无法取得完整可保存音频。
- 下载文件若明显短于歌曲详情时长，会标为试听片段并删除临时文件。歌曲详情时长有误时可能误判。
- 音频来源、可用音质、版权和地区限制会变化。无法取得封面或写入标签时，仍会保存可播放音频，但可能缺少部分元数据。
- 重启后通过应用数据目录下的 `downloads.json` 避免重复下载；手动移动或删除文件后会重新下载。

## 验证

本机验证的网易云示例；同一首歌从不同接口取得的音质可能不同：

| 示例链接 | 文件 | 实际结果 |
| --- | --- | --- |
| `https://music.163.com/song?id=33894312` | `群星 - 情非得已 (童声版).mp3` | 新版自动音质：网易云音质接口返回 MP3、320 kbps、267.3 秒；从界面粘贴到保存成功，FFmpeg 全文件解码成功。旧版公开地址返回过 128 kbps MP3 |
| `https://music.163.com/song?id=210049` | `蔡依林、周杰伦 - 布拉格广场.flac` | 旧版 GD Studio 备用来源验证：FLAC、约 948 kbps、294.6 秒；FFmpeg 全文件解码成功 |

已在重建的 arm64 `.app` 中实测：点击“官网登录”可打开网易云官网和官方扫码入口；登录会话存于钥匙串，重启后仍能显示已登录。钥匙串读取移至后台线程，避免启动时卡住界面。未登录选择会员音质会明确报错。

用户提供的 `https://163cn.tv/bhj6ytbM` 已解析为网易云歌曲 `28191836`（《Merry Christmas Mr. Lawrence》，335.107 秒）。未登录实测十个音质请求均被网易云降到标准 MP3 试听地址；程序不会把它标为母带或完整歌曲。已登录账号在本版 `.app` 中实测：“超清母带”保存为 192 kHz/24 bit 双声道 FLAC，文件约 203 MB、335.107 秒、约 4840 kbps；“无损”保存为 44.1 kHz/16 bit FLAC，约 24 MB、335.107 秒。两个文件均经 FFprobe 检测，母带文件由 FFmpeg 全文件解码成功。该曲的 Hi-Res 请求被网易云降为“无损”，界面正确显示失败。

用户提供的 `https://163cn.tv/bhklO9m4` 已解析为网易云歌曲 `2041026502`（林俊杰《愿与愁》，231.586 秒）。已登录账号实测 Hi-Res 为 48 kHz/24 bit FLAC、高清臻音为 96 kHz/24 bit FLAC、沉浸环绕声为 44.1 kHz/16 bit 六声道 FLAC。臻音全景声经完整下载保存为 `validation-output/audio-vivid/林俊杰 - 愿与愁.m4a`，文件约 24.1 MB，容器时长 231.596 秒，44.1 kHz、12 声道、约 832 kbps；FFprobe 扫描的 9,974 个音频包与容器记录一致。歌曲名、歌手、专辑和封面均已写入文件。截断到 50% 和 90% 的副本会因音频包不足而失败。FFmpeg 解码测试仍返回“找不到解码器”，因此未验证可播放性。两首歌的网易云目录都未列出杜比档位，因此杜比全景声尚无真实文件验收样本。

当前版 `.app` 已实测一次粘贴上述两条短链：两首歌均显示歌曲信息、封面和目录音质，状态保持“等待选择音质”、进度为零；未点击下载按钮时不会进入下载队列。界面流程测试还验证了选择档位后点击按钮才会提交任务。另测试了拒绝非网易云链接、无效链接、503 下载失败、试听片段不落盘、取消、重试和重复下载。运行 `.venv/bin/python -m unittest discover -s tests -v` 可复核本地测试。`validation-output/` 保留早期版本产生的验证文件；其中可能包含旧版其他平台的样本，不代表当前版本支持该平台。

## 打包

在 Apple Silicon Mac 上运行 `zsh build_mac.sh`，输出 `dist/音乐下载器.app`。本机另提供可复制的 `dist/音乐下载器-macOS-arm64.zip`；要自行生成压缩包，可运行 `ditto -c -k --sequesterRsrc --keepParent 'dist/音乐下载器.app' 'dist/音乐下载器-macOS-arm64.zip'`。PyInstaller 打包用依赖会自动安装。脚本会修复 Qt WebEngine 在 PyInstaller 中的 framework 资源布局、给辅助进程补上 Qt 所需签名权限，并验证包的签名；启动入口会在 macOS 上使用 Qt 的 OpenGL 渲染后端，避开当前构建环境中的 Metal 着色器闪退。生成的是 arm64 应用，仅有本地临时签名，未使用开发者证书签名或 Apple 公证；分发到其他 Mac 需要开发者签名与公证。本地如被 Gatekeeper 阻止，可在系统设置的“隐私与安全性”中批准。

Windows 安装版已生成单文件 [网易云音乐下载器-安装程序-Windows-x64.exe](https://github.com/wangchuanao2008/netease-music-downloader/releases/download/v1.1.0/netease-music-downloader-windows-x64-setup.exe)。构建步骤、限制和验证记录见 [windows/README.md](windows/README.md)。

Android 版源码位于 [android/](android/)，当前 APK 为 [网易云音乐下载器-Android-v1.1.0.apk](https://github.com/wangchuanao2008/netease-music-downloader/releases/download/v1.1.0/netease-music-downloader-android-v1.1.0.apk)。本版先解析歌曲和音质目录，用户选定音质并点击下载后才开始传输。使用方式、构建步骤、签名和设备验收记录见 [android/README.md](android/README.md)。

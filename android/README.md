# 网易云音乐下载器 · Android 版

当前 APK：[`../dist/网易云音乐下载器-Android-v1.1.0.apk`](https://github.com/wangchuanao2008/netease-music-downloader/releases/download/v1.1.0/netease-music-downloader-android-v1.1.0.apk)，包名 `com.musicdown.netease`，`versionCode 3`，最低 Android 8.0（API 26），目标 Android 15（API 35）。应用只申请联网权限；保存通过 Android 系统文件夹选择器完成。

## 使用方式

粘贴或分享网易云单曲链接、`163cn.tv` 短链或包含多条链接的文字。应用获取歌曲信息、封面和该曲音质目录，显示可选档位及通常会员等级；这一阶段进度保持 0，不开始下载。目录失败可点“重试目录”。为单曲选定音质并点“下载”后才会请求音频。会员音质可在“官网登录”中打开网易云官方网页完成扫码及安全验证，应用校验账号后保存会话；不会要求在本应用输入密码。会话使用 Android Keystore 的 AES-GCM 密钥加密，退出时可删除；Android 云备份和设备迁移备份均排除了应用数据。

具体音质只请求网易云原站接口，检查接口实际档位、音频编码和时长；发生降级、试听或明显截断时不会保存为成功，也不会以第三方音源补低音质。只有“自动”档位允许尝试公开来源及用户启用的 GD Studio 备用来源。重复记录按歌曲、音质、账号和保存目录区分。失败与取消会清理临时文件；重试会重新请求。保存目录授权失效时会要求重新选择。

Android `MediaExtractor` 无法可靠确认某些空间音频的编码和元数据，因此杜比、沉浸环绕声和臻音全景声会明确提示当前无法验证，不会被标为成功。Android 默认保留文件编码，不提供 MP3 转换或重写标签。下载在应用进程内执行：后台时通常可以继续，但系统结束进程后任务不会自动恢复，需要重新打开并重试。

## 构建

项目固定使用 Java 17、Android Gradle Plugin 8.5.2、Gradle 8.7、compile/target SDK 35。安装 Android Studio 与 Android SDK 35 后运行：

```sh
cd android
./build_android.sh
```

脚本执行干净构建、Lint、单元测试和 Release 打包；打包前后比较现有 1.0.1 基线 APK 与新包的证书 SHA-256，不一致时拒绝交付，以保护覆盖安装。输出为 `dist/网易云音乐下载器-Android-v1.1.0.apk`。项目目前使用 Android Debug 签名，仅适合侧载/升级同一开发证书构建的版本，不是商店发布证书。

## 1.1.0 构建记录（2026-09-28）

- 现有基线 APK：包名 `com.musicdown.netease`，版本 `1.0.1` / `versionCode 2`；签名证书 SHA-256：`acc56f5c827230bf24a783e215919cb09db65c75c32d5816bd0139af3f0ef781`。
- 新 APK：版本 `1.1.0` / `versionCode 3`；证书 SHA-256 与基线完全一致。APK SHA-256：`c94d04bc5fd75b2d5483635b2ba26d92a2b69ed7d6d66b2fd2b61aed88a60e57`。`apksigner` 使用 APK Signature Scheme v2 验证通过。
- 固定 Gradle 8.7 执行 `clean`、`:app:lint`、`:app:test` 和 `:app:assembleRelease` 成功；单元测试 8 项通过，Lint 0 errors（10 warnings）。测试覆盖音质目录、会员标签、空间音频目录变体、账号资料校验、指定音质降级拒绝、试听标记、传输字节数、短时长文件判断和取消后重试。
- 尚未完成真机/模拟器安装、官网登录、系统分享、免费/会员音质及 SAF 保存验收。ADB 设备列表为空，SDK 没有已安装的模拟器系统镜像，且此环境没有 `sdkmanager`。因而本 APK 虽已构建及签名核验，仍不能视为完成了用户验收要求中的设备验证。

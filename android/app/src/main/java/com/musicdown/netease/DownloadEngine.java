package com.musicdown.netease;

import static com.musicdown.netease.Models.AppException;
import static com.musicdown.netease.Models.AudioInfo;
import static com.musicdown.netease.Models.AudioSource;
import static com.musicdown.netease.Models.Result;
import static com.musicdown.netease.Models.Song;

import android.content.Context;
import android.graphics.Bitmap;
import android.net.Uri;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

final class DownloadEngine {
    interface Listener {
        void state(String text);
        void song(Song song, Bitmap cover);
        void catalog(Song song, Bitmap cover, boolean retry);
        void progress(int percent);
        void completed(String state, Result result, String message);
    }

    private final Context context;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Set<String> active = ConcurrentHashMap.newKeySet();
    DownloadEngine(Context context) { this.context = context.getApplicationContext(); }

    Models.Control preview(String url, Listener listener) {
        Models.Control control = new Models.Control();
        executor.execute(() -> {
            try {
                listener.state("解析链接");
                String finalUrl = MusicApi.resolveShareUrl(url, control);
                String id = LinkParser.songId(finalUrl);
                listener.state("获取歌曲信息和封面");
                Song basic = MusicApi.song(id, control);
                Bitmap cover = MusicApi.cover(basic.coverUrl, control);
                listener.song(basic, cover);
                listener.state("查询该曲音质目录");
                java.util.Map<String, String> catalog = MusicApi.qualityCatalog(id, control);
                Song ready = new Song(basic.id, basic.title, basic.artist, basic.album, basic.coverUrl,
                        basic.durationSeconds, basic.restriction, catalog);
                listener.catalog(ready, cover, false);
            } catch (AppException e) {
                listener.catalog(null, null, true);
                listener.completed(control.cancelled.get() ? "已取消" : "目录查询失败", null, e.getMessage());
            } catch (Exception e) {
                listener.catalog(null, null, true);
                listener.completed("解析失败", null, e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage());
            }
        });
        return control;
    }

    Models.Control enqueue(Song song, Uri tree, boolean useAlternate, String quality,
                           Models.Account account, Listener listener) {
        Models.Control control = new Models.Control();
        executor.execute(() -> run(song, tree, useAlternate, quality, account, control, listener));
        return control;
    }

    void shutdown() { executor.shutdownNow(); }

    private void run(Song song, Uri tree, boolean useAlternate, String quality, Models.Account account,
                     Models.Control control, Listener listener) {
        String key = "quality-v1:" + song.id + ":" + quality + ":" + (account == null ? "public" : account.userId) + ":" + tree;
        try {
            if (!active.add(key)) throw new AppException("同一歌曲、音质和目录已在下载队列中");
            SafStore store = new SafStore(context, tree);
            Result old = store.existing(key, null);
            if (old != null) { listener.completed("已存在", old, old.fileName); return; }
            List<AudioSource> sources;
            String primaryFailure = "";
            if (quality.equals("auto")) {
                try { listener.state("请求网易云自动音质"); sources = MusicApi.memberSources(song, account, quality, control); }
                catch (AppException e) {
                    if (control.cancelled.get()) throw e;
                    primaryFailure = e.getMessage(); sources = new ArrayList<>();
                }
                if (sources.isEmpty()) {
                    listener.state("尝试公开音源"); sources.addAll(MusicApi.primary(song));
                    if (useAlternate) {
                        try { sources.addAll(MusicApi.alternate(song, control)); }
                        catch (AppException ignored) { if (sources.isEmpty()) throw ignored; }
                    }
                }
            } else {
                listener.state("请求所选网易云音质");
                sources = MusicApi.memberSources(song, account, quality, control);
            }
            listener.state("下载所选音质");
            Downloaded downloaded = downloadAny(song, sources, quality, control, listener);
            try {
                listener.state("保存文件");
                Result result = store.save(downloaded.file, song, downloaded.info, downloaded.sourceLabel, key, control);
                listener.progress(100); listener.completed("已完成", result, result.fileName);
            } finally { //noinspection ResultOfMethodCallIgnored
                downloaded.file.delete();
            }
        } catch (AppException e) {
            listener.completed(control.cancelled.get() ? "已取消" : "失败", null, e.getMessage());
        } catch (Exception e) {
            listener.completed(control.cancelled.get() ? "已取消" : "失败", null,
                    "网络或文件错误：" + (e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage()));
        } finally { active.remove(key); }
    }

    private Downloaded downloadAny(Song song, List<AudioSource> sources, String quality,
                                   Models.Control control, Listener listener) throws AppException {
        StringBuilder errors = new StringBuilder();
        for (AudioSource source : sources) {
            MusicApi.checkCancelled(control); File temp = null; HttpURLConnection connection = null;
            try {
                temp = File.createTempFile("musicdown-", ".part", context.getCacheDir());
                connection = MusicApi.open(source.url, true, 45_000);
                int code = connection.getResponseCode(); if (code >= 400) throw new AppException("HTTP " + code);
                String type = connection.getContentType();
                if (type != null && (type.contains("html") || type.contains("json"))) throw new AppException("服务器返回网页而非音频");
                long total = connection.getContentLengthLong(), received = 0;
                try (InputStream input = connection.getInputStream(); FileOutputStream output = new FileOutputStream(temp)) {
                    byte[] buffer = new byte[128 * 1024]; int read;
                    while ((read = input.read(buffer)) != -1) {
                        MusicApi.checkCancelled(control); output.write(buffer, 0, read); received += read;
                        listener.progress(total > 0 ? (int)Math.min(99, received * 100 / total) : -1);
                    }
                }
                if (!DownloadRules.completeTransfer(total, received)) throw new AppException("传输字节数不完整（" + received + "/" + total + "），临时文件已清理");
                AudioInfo info = AudioInspector.inspect(temp);
                if (!DownloadRules.completeDuration(song.durationSeconds, info.durationSeconds))
                    throw new AppException(String.format(java.util.Locale.CHINA, "仅取得试听或截断片段（%.0f/%.0f 秒），未保存", info.durationSeconds, song.durationSeconds));
                validateSelectedQuality(quality, source, info);
                return new Downloaded(temp, info, source.label);
            } catch (AppException e) {
                if (temp != null) //noinspection ResultOfMethodCallIgnored
                    temp.delete();
                if (errors.length() > 0) errors.append("；"); errors.append(source.label).append("：").append(e.getMessage());
                if (control.cancelled.get()) throw e;
            } catch (Exception e) {
                if (temp != null) //noinspection ResultOfMethodCallIgnored
                    temp.delete();
                if (errors.length() > 0) errors.append("；"); errors.append(source.label).append("：").append(e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage());
            } finally { if (connection != null) connection.disconnect(); }
        }
        throw new AppException(errors.length() == 0 ? "没有可下载的音频" : errors.toString());
    }

    private static void validateSelectedQuality(String quality, AudioSource source, AudioInfo info) throws AppException {
        String failure = DownloadRules.qualityFailure(quality, source.actualLevel, source.label, info.lossless, info.codec);
        if (!failure.isEmpty()) throw new AppException(failure);
    }

    private static final class Downloaded {
        final File file; final AudioInfo info; final String sourceLabel;
        Downloaded(File file, AudioInfo info, String sourceLabel) { this.file = file; this.info = info; this.sourceLabel = sourceLabel; }
    }
}
